"""Deterministic crop-only fixed CV recipe executor.

The implementation uses a small NumPy LAB conversion fallback so the core
does not depend on OpenCV.  Resize and return are nearest-neighbour and all
threshold bounds are inclusive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

import numpy as np

from segvision.core.geometry import CropContext
from segvision.core.mask_ops import fill_holes
from segvision.core.recipe import CVRecipe


@dataclass(frozen=True, slots=True)
class CVResult:
    gate: Literal["disabled", "invalid", "coarse", "direct"]
    mask: np.ndarray | None
    recipe_id: str
    recipe_hash: str
    diagnostics: dict[str, object]

    def __post_init__(self) -> None:
        if self.mask is not None:
            arr = np.asarray(self.mask)
            if arr.dtype != np.bool_:
                arr = arr.astype(np.bool_)
            arr = arr.copy()
            arr.setflags(write=False)
            object.__setattr__(self, "mask", arr)


def _resize_nearest(arr: np.ndarray, target: tuple[int, int]) -> np.ndarray:
    th, tw = target[1], target[0]  # public target is (width,height)
    y = np.minimum((np.arange(th) * arr.shape[0] / th).astype(int), arr.shape[0] - 1)
    x = np.minimum((np.arange(tw) * arr.shape[1] / tw).astype(int), arr.shape[1] - 1)
    return arr[np.ix_(y, x)]


def _lab_channel(rgb: np.ndarray, channel: int) -> np.ndarray:
    v = rgb.astype(np.float32) / 255.0
    # sRGB -> XYZ -> CIELAB D65, deterministic float32 arithmetic.
    v = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    xyz = np.einsum(
        "...c,dc->...d",
        v,
        np.array(
            [
                [0.4124564, 0.3575761, 0.1804375],
                [0.2126729, 0.7151522, 0.0721750],
                [0.0193339, 0.1191920, 0.9503041],
            ],
            dtype=np.float32,
        ),
    )
    xyz /= np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    e, k = 216 / 24389, 24389 / 27
    f = np.where(xyz > e, np.cbrt(xyz), (k * xyz + 16) / 116)
    l = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1]) + 128
    b = 200 * (f[..., 1] - f[..., 2]) + 128
    return np.stack([l * (255 / 100), a, b], axis=-1)[..., channel]


def _box_blur(arr: np.ndarray, kernel: tuple[int, int]) -> np.ndarray:
    ky, kx = kernel[1], kernel[0]
    py, px = ky // 2, kx // 2
    pad = np.pad(arr, ((py, py), (px, px)), mode="edge")
    out = np.zeros_like(arr, dtype=np.float32)
    for dy in range(ky):
        for dx in range(kx):
            out += pad[dy : dy + arr.shape[0], dx : dx + arr.shape[1]]
    return out / float(kx * ky)


def _median_blur(arr: np.ndarray, size: int) -> np.ndarray:
    if size <= 0:
        return arr
    p = size // 2
    padded = np.pad(arr, p, mode="edge")
    windows = np.stack(
        [
            padded[dy : dy + arr.shape[0], dx : dx + arr.shape[1]]
            for dy in range(size)
            for dx in range(size)
        ],
        axis=0,
    )
    return np.median(windows, axis=0)


def _component_filter(mask: np.ndarray, min_area: int) -> np.ndarray:
    if min_area <= 0:
        return mask
    out = mask.copy()
    seen = np.zeros_like(mask)
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(x, y)]
            seen[y, x] = True
            comp: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not dx and not dy:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((nx, ny))
            if len(comp) < min_area:
                for cx, cy in comp:
                    out[cy, cx] = False
    return out


def _component_count(mask: np.ndarray) -> int:
    return (
        int(_component_filter(mask, 1).sum() >= 0) if False else sum(1 for _ in _components(mask))
    )


def _components(mask: np.ndarray):
    seen = np.zeros_like(mask)
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(x, y)]
            seen[y, x] = True
            count = 0
            while stack:
                cx, cy = stack.pop()
                count += 1
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not dx and not dy:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((nx, ny))
            yield count


def _morph(mask: np.ndarray, iterations: int, op: str) -> np.ndarray:
    from segvision.core.mask_ops import grow, shrink

    out = mask
    for _ in range(iterations):
        out = grow(out) if op == "dilate" else shrink(out)
    return out


def execute_recipe(crop_rgb: np.ndarray, recipe: CVRecipe, context: CropContext) -> CVResult:
    if not recipe.enabled:
        return CVResult(
            "disabled", None, recipe.recipe_id, recipe.recipe_hash, {"reason": "disabled"}
        )
    if np.asarray(crop_rgb).shape[:2] != context.shape:
        return CVResult(
            "invalid", None, recipe.recipe_id, recipe.recipe_hash, {"reason": "crop_shape_mismatch"}
        )
    try:
        lab = _lab_channel(np.asarray(crop_rgb), recipe.channel)
        long_side = max(1, int(recipe.working_long_side))
        scale = long_side / max(crop_rgb.shape[:2])
        work_size = (
            max(1, round(crop_rgb.shape[1] * scale)),
            max(1, round(crop_rgb.shape[0] * scale)),
        )
        small = _resize_nearest(lab, work_size)
        blurred = _median_blur(small, recipe.median_blur_px) if recipe.median_blur_px else small
        if recipe.lab_l is not None and recipe.lab_a is not None and recipe.lab_b is not None:
            # Compute all three channels for the canonical recipe.
            rgb = np.asarray(crop_rgb).astype(np.float32) / 255.0
            rgb = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
            xyz = np.einsum(
                "...c,dc->...d",
                rgb,
                np.array(
                    [
                        [0.4124564, 0.3575761, 0.1804375],
                        [0.2126729, 0.7151522, 0.0721750],
                        [0.0193339, 0.1191920, 0.9503041],
                    ],
                    dtype=np.float32,
                ),
            ) / np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
            e, k = 216 / 24389, 24389 / 27
            f = np.where(xyz > e, np.cbrt(xyz), (k * xyz + 16) / 116)
            lab_full = np.stack(
                [
                    116 * f[..., 1] - 16,
                    500 * (f[..., 0] - f[..., 1]) + 128,
                    200 * (f[..., 1] - f[..., 2]) + 128,
                ],
                axis=-1,
            )
            lab_work = np.stack(
                [_resize_nearest(lab_full[..., i], work_size) for i in range(3)], axis=-1
            )
            lab_work = (
                _median_blur(lab_work, recipe.median_blur_px) if recipe.median_blur_px else lab_work
            )
            ranges = (recipe.lab_l, recipe.lab_a, recipe.lab_b)
            coarse_small = np.logical_and.reduce(
                [
                    (lab_work[..., i] >= lo) & (lab_work[..., i] <= hi)
                    for i, (lo, hi) in enumerate(ranges)
                ]
            )
        else:
            coarse_small = (blurred >= recipe.threshold_low) & (blurred <= recipe.threshold_high)
        mask = _resize_nearest(
            coarse_small.astype(np.uint8), (context.crop_width, context.crop_height)
        ).astype(np.bool_)
        open_radius = recipe.open_radius_px or recipe.morphology_open
        close_radius = recipe.close_radius_px or recipe.morphology_close
        if open_radius:
            mask = _morph(_morph(mask, open_radius, "erode"), open_radius, "dilate")
        if close_radius:
            mask = _morph(_morph(mask, close_radius, "dilate"), close_radius, "erode")
        if recipe.fill_holes:
            mask = fill_holes(mask)
        mask = _component_filter(mask, recipe.min_component_area)
        area = float(mask.mean()) if mask.size else 0.0
        border_total = 2 * mask.shape[0] + 2 * mask.shape[1] - 4 if min(mask.shape) else 1
        border_contact = float(
            np.r_[mask[0, :], mask[-1, :], mask[1:-1, 0], mask[1:-1, -1]].sum()
            / max(1, border_total)
        )
        if (
            not mask.any()
            or area < recipe.direct_area_fraction_min
            or area > recipe.direct_area_fraction_max
        ):
            gate = "invalid"
        elif (
            _component_count(mask) <= recipe.max_components
            and border_contact <= recipe.max_crop_border_fraction
        ):
            gate = "direct"
        else:
            gate = "coarse"
        return CVResult(
            cast(Literal["disabled", "invalid", "coarse", "direct"], gate),
            mask,
            recipe.recipe_id,
            recipe.recipe_hash,
            {
                "area_fraction": area,
                "shape": list(mask.shape),
                "component_count": _component_count(mask),
                "border_contact_fraction": border_contact,
                "EMPTY_MASK": not bool(mask.any()),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return CVResult(
            "invalid",
            None,
            recipe.recipe_id,
            recipe.recipe_hash,
            {"reason": type(exc).__name__, "message": str(exc)},
        )


class FixedRecipeExecutor:
    def run(self, crop_rgb: np.ndarray, recipe: CVRecipe, context: CropContext) -> CVResult:
        return execute_recipe(crop_rgb, recipe, context)
