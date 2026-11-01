"""Full-image/ROI/crop geometry contracts.

All public rectangles are half-open ``(x0, y0, x1, y1)``.  The functions in
this module do not resize images and never silently repair invalid input.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .errors import InvalidImage, InvalidMask, InvalidPoint, InvalidRoi
from .types import WarningRecord

DEFAULT_PADDING_FRACTION = 0.10


def _finite_number(v: object) -> bool:
    return (
        not isinstance(v, (bool, np.bool_))
        and isinstance(v, (int, float, np.integer, np.floating))
        and math.isfinite(float(v))
    )


def image_shape(image: np.ndarray) -> tuple[int, int]:
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] != 3 or arr.dtype != np.uint8:
        raise InvalidImage("image must be uint8[height,width,3] RGB")
    h, w, _ = arr.shape
    if h < 1 or w < 1:
        raise InvalidImage("image dimensions must be positive")
    return int(h), int(w)


def validate_roi(roi: Sequence[object], image_shape_: tuple[int, int]) -> tuple[int, int, int, int]:
    if len(roi) != 4 or not all(_finite_number(v) for v in roi):
        raise InvalidRoi("ROI must contain four finite coordinates")
    vals = tuple(float(v) for v in roi)  # type: ignore[arg-type]
    if any(v != math.floor(v) for v in vals):
        raise InvalidRoi("public ROI coordinates must be integer source-pixel indices")
    x0, y0, x1, y1 = (int(v) for v in vals)
    h, w = image_shape_
    if x1 <= x0 or y1 <= y0:
        raise InvalidRoi("ROI must have positive width and height")
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        raise InvalidRoi("ROI must be fully contained in the image")
    return x0, y0, x1, y1


@dataclass(frozen=True, slots=True)
class CropContext:
    image_height: int
    image_width: int
    user_roi_full: tuple[int, int, int, int]
    crop_rect_full: tuple[int, int, int, int]
    padding_fraction: float = DEFAULT_PADDING_FRACTION
    padding_clamped: bool = False

    @property
    def crop_width(self) -> int:
        return self.crop_rect_full[2] - self.crop_rect_full[0]

    @property
    def crop_height(self) -> int:
        return self.crop_rect_full[3] - self.crop_rect_full[1]

    @property
    def shape(self) -> tuple[int, int]:
        return self.crop_height, self.crop_width

    @property
    def user_box_crop(self) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = self.user_roi_full
        cx0, cy0, _, _ = self.crop_rect_full
        return (x0 - cx0, y0 - cy0, x1 - cx0, y1 - cy0)

    def to_dict(self) -> dict[str, object]:
        return {
            "image_height": self.image_height,
            "image_width": self.image_width,
            "user_roi_full": list(self.user_roi_full),
            "crop_rect_full": list(self.crop_rect_full),
            "padding_fraction": self.padding_fraction,
            "padding_clamped": self.padding_clamped,
        }


def create_crop_context(
    image_shape_: tuple[int, int],
    user_roi_full: Sequence[object],
    padding_fraction: float = DEFAULT_PADDING_FRACTION,
) -> CropContext:
    h, w = (int(image_shape_[0]), int(image_shape_[1]))
    if h < 1 or w < 1:
        raise InvalidImage("image dimensions must be positive")
    if not _finite_number(padding_fraction) or float(padding_fraction) < 0:
        raise InvalidRoi("padding fraction must be finite and non-negative")
    roi = validate_roi(user_roi_full, (h, w))
    x0, y0, x1, y1 = roi
    rw, rh = x1 - x0, y1 - y0
    pad = float(padding_fraction)
    fx0, fy0 = x0 - pad * rw, y0 - pad * rh
    fx1, fy1 = x1 + pad * rw, y1 + pad * rh
    ux0, uy0 = math.floor(fx0), math.floor(fy0)
    ux1, uy1 = math.ceil(fx1), math.ceil(fy1)
    cx0, cy0 = max(0, ux0), max(0, uy0)
    cx1, cy1 = min(w, ux1), min(h, uy1)
    return CropContext(
        h, w, roi, (cx0, cy0, cx1, cy1), pad, (cx0 != ux0 or cy0 != uy0 or cx1 != ux1 or cy1 != uy1)
    )


def extract_crop(image: np.ndarray, context: CropContext) -> np.ndarray:
    h, w = image_shape(image)
    if (h, w) != (context.image_height, context.image_width):
        raise InvalidImage("image shape does not match crop context")
    x0, y0, x1, y1 = context.crop_rect_full
    crop = np.array(np.asarray(image)[y0:y1, x0:x1, :], copy=True)
    crop.setflags(write=False)
    return crop


def validate_point(
    point: Sequence[object],
    context: CropContext | None = None,
    image_shape_: tuple[int, int] | None = None,
) -> tuple[int, int]:
    if len(point) != 2 or not all(_finite_number(v) for v in point):
        raise InvalidPoint("point must contain two finite integer coordinates")
    x, y = (float(v) for v in point)  # type: ignore[arg-type]
    if x != math.floor(x) or y != math.floor(y):
        raise InvalidPoint("point coordinates must be integer source-pixel indices")
    ix, iy = int(x), int(y)
    if context is not None:
        x0, y0, x1, y1 = context.crop_rect_full
        if not (x0 <= ix < x1 and y0 <= iy < y1):
            raise InvalidPoint("point is outside the current work crop")
    elif image_shape_ is not None:
        h, w = image_shape_
        if not (0 <= ix < w and 0 <= iy < h):
            raise InvalidPoint("point is outside the image")
    return ix, iy


def full_to_crop_point(point: Sequence[object], context: CropContext) -> tuple[int, int]:
    x, y = validate_point(point, context)
    return x - context.crop_rect_full[0], y - context.crop_rect_full[1]


def crop_to_full_point(point: Sequence[object], context: CropContext) -> tuple[int, int]:
    if len(point) != 2 or not all(_finite_number(v) for v in point):
        raise InvalidPoint("point must contain two finite coordinates")
    x, y = (float(v) for v in point)  # type: ignore[arg-type]
    if x != math.floor(x) or y != math.floor(y):
        raise InvalidPoint("crop point coordinates must be integer")
    cx, cy = int(x), int(y)
    if not (0 <= cx < context.crop_width and 0 <= cy < context.crop_height):
        raise InvalidPoint("crop point outside crop")
    return cx + context.crop_rect_full[0], cy + context.crop_rect_full[1]


def full_to_crop_box(box: Sequence[object], context: CropContext) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = validate_roi(box, (context.image_height, context.image_width))
    # A prompt box must be contained in the work crop; unlike a public ROI it
    # is not clipped or reordered.
    cx0, cy0, cx1, cy1 = context.crop_rect_full
    if not (cx0 <= x0 < x1 <= cx1 and cy0 <= y0 < y1 <= cy1):
        raise InvalidRoi("box is outside the work crop")
    return (x0 - cx0, y0 - cy0, x1 - cx0, y1 - cy0)


def crop_to_full_box(box: Sequence[object], context: CropContext) -> tuple[int, int, int, int]:
    if len(box) != 4 or not all(_finite_number(v) for v in box):
        raise InvalidRoi("crop box must contain four finite integer coordinates")
    vals = tuple(float(v) for v in box)  # type: ignore[arg-type]
    if any(v != math.floor(v) for v in vals):
        raise InvalidRoi("crop box must use integer coordinates")
    x0, y0, x1, y1 = map(int, vals)
    if (
        x1 <= x0
        or y1 <= y0
        or x0 < 0
        or y0 < 0
        or x1 > context.crop_width
        or y1 > context.crop_height
    ):
        raise InvalidRoi("crop box outside crop")
    ox, oy, _, _ = context.crop_rect_full
    return (x0 + ox, y0 + oy, x1 + ox, y1 + oy)


def validate_crop_mask(mask: np.ndarray, context: CropContext) -> np.ndarray:
    arr = np.asarray(mask)
    if arr.ndim != 2 or arr.shape != context.shape or arr.dtype != np.bool_:
        raise InvalidMask(
            f"mask must be bool with shape {context.shape}, got {arr.dtype} {arr.shape}"
        )
    return np.array(arr, copy=True)


def reconstruct_full_mask(mask_crop: np.ndarray, context: CropContext) -> np.ndarray:
    mask = validate_crop_mask(mask_crop, context)
    out = np.zeros((context.image_height, context.image_width), dtype=np.bool_)
    x0, y0, x1, y1 = context.crop_rect_full
    out[y0:y1, x0:x1] = mask
    return out


def work_crop_edge_warning(mask_crop: np.ndarray, context: CropContext) -> WarningRecord | None:
    mask = validate_crop_mask(mask_crop, context)
    if mask.size and (
        mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any()
    ):
        return WarningRecord(
            "TOUCHES_WORK_CROP_EDGE", "foreground touches the padded work-crop boundary"
        )
    return None


def image_boundary_warning(full_mask: np.ndarray, context: CropContext) -> WarningRecord | None:
    arr = np.asarray(full_mask)
    if arr.shape != (context.image_height, context.image_width) or arr.dtype != np.bool_:
        raise InvalidMask("full mask shape/dtype mismatch")
    if arr.size and (arr[0, :].any() or arr[-1, :].any() or arr[:, 0].any() or arr[:, -1].any()):
        return WarningRecord(
            "IMAGE_BOUNDARY_TRUNCATED", "foreground reaches the source-image boundary"
        )
    return None


def can_expand(context: CropContext) -> bool:
    proposed = create_crop_context(
        (context.image_height, context.image_width),
        context.crop_rect_full,
        context.padding_fraction,
    )
    a, b = context.crop_rect_full, proposed.crop_rect_full
    return any((b[i] < a[i] if i in (0, 1) else b[i] > a[i]) for i in range(4)) and b != a


def expanded_context(context: CropContext) -> CropContext:
    proposed = create_crop_context(
        (context.image_height, context.image_width),
        context.crop_rect_full,
        context.padding_fraction,
    )
    if proposed.crop_rect_full == context.crop_rect_full:
        from .errors import UnsupportedOperation

        raise UnsupportedOperation("CANNOT_EXPAND_AT_IMAGE_BOUNDARY")
    return proposed
