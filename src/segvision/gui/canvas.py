"""Toolkit-neutral canvas transforms, layers, and input routing.

The model is intentionally usable in headless tests.  A Qt widget can bind to
it without receiving tensors or taking ownership of session state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from segvision.core.geometry import CropContext, full_to_crop_point
from segvision.core.types import ProposalSet


def _readonly_mask(mask: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray:
    if mask is None:
        arr = np.zeros(shape, dtype=np.bool_)
    else:
        arr = np.asarray(mask)
        if arr.dtype != np.bool_ or arr.shape != shape:
            raise ValueError(f"mask must be bool with shape {shape}")
        arr = arr.copy()
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True, slots=True)
class CanvasTransform:
    image_width: int
    image_height: int
    viewport_width: int
    viewport_height: int
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0

    def __post_init__(self) -> None:
        if min(self.image_width, self.image_height, self.viewport_width, self.viewport_height) < 1:
            raise ValueError("canvas dimensions must be positive")
        if not math.isfinite(self.zoom) or self.zoom <= 0:
            raise ValueError("zoom must be positive and finite")
        if not math.isfinite(self.pan_x) or not math.isfinite(self.pan_y):
            raise ValueError("pan must be finite")

    @property
    def fit_scale(self) -> float:
        return min(self.viewport_width / self.image_width, self.viewport_height / self.image_height)

    @property
    def scale(self) -> float:
        return self.fit_scale * self.zoom

    @property
    def origin(self) -> tuple[float, float]:
        return (
            (self.viewport_width - self.image_width * self.scale) / 2.0 + self.pan_x,
            (self.viewport_height - self.image_height * self.scale) / 2.0 + self.pan_y,
        )

    def image_to_view(self, x: float, y: float) -> tuple[float, float]:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("coordinates must be finite")
        ox, oy = self.origin
        return ox + x * self.scale, oy + y * self.scale

    def view_to_image(self, x: float, y: float, *, clamp: bool = False) -> tuple[float, float]:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("coordinates must be finite")
        ox, oy = self.origin
        point = ((x - ox) / self.scale, (y - oy) / self.scale)
        if clamp:
            return (
                min(max(point[0], 0.0), float(self.image_width - 1)),
                min(max(point[1], 0.0), float(self.image_height - 1)),
            )
        return point

    def view_to_pixel(self, x: float, y: float, *, clamp: bool = False) -> tuple[int, int]:
        px, py = self.view_to_image(x, y, clamp=clamp)
        ix, iy = math.floor(px), math.floor(py)
        if not (0 <= ix < self.image_width and 0 <= iy < self.image_height):
            raise ValueError("view coordinate is outside image")
        return ix, iy

    def resized(self, width: int, height: int) -> CanvasTransform:
        return CanvasTransform(
            self.image_width,
            self.image_height,
            int(width),
            int(height),
            self.zoom,
            self.pan_x,
            self.pan_y,
        )


ViewportTransform = CanvasTransform


@dataclass(frozen=True, slots=True)
class CanvasLayers:
    image_shape: tuple[int, int]
    user_roi_full: tuple[int, int, int, int]
    crop_rect_full: tuple[int, int, int, int]
    selected_mask_roi: np.ndarray
    disagreement_mask_roi: np.ndarray
    crop_edge_risk_mask_roi: np.ndarray
    candidate_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_mask_roi", _readonly_mask(self.selected_mask_roi, self.image_shape))
        object.__setattr__(self, "disagreement_mask_roi", _readonly_mask(self.disagreement_mask_roi, self.image_shape))
        object.__setattr__(self, "crop_edge_risk_mask_roi", _readonly_mask(self.crop_edge_risk_mask_roi, self.image_shape))


class AnnotationCanvasModel:
    """Presentation adapter that routes real input events to the controller."""

    def __init__(self, controller: Any, *, viewport_size: tuple[int, int] = (960, 640)) -> None:
        self.controller = controller
        session = controller.session
        self.transform = CanvasTransform(
            session.image_width,
            session.image_height,
            int(viewport_size[0]),
            int(viewport_size[1]),
        )
        self._drag_start: tuple[int, int] | None = None

    @property
    def context(self) -> CropContext:
        return self.controller.session.context

    def resize(self, width: int, height: int) -> None:
        self.transform = self.transform.resized(width, height)

    def set_zoom(self, zoom: float) -> None:
        self.transform = CanvasTransform(
            self.transform.image_width,
            self.transform.image_height,
            self.transform.viewport_width,
            self.transform.viewport_height,
            float(zoom),
            self.transform.pan_x,
            self.transform.pan_y,
        )

    def pan(self, dx: float, dy: float) -> None:
        self.transform = CanvasTransform(
            self.transform.image_width,
            self.transform.image_height,
            self.transform.viewport_width,
            self.transform.viewport_height,
            self.transform.zoom,
            self.transform.pan_x + float(dx),
            self.transform.pan_y + float(dy),
        )

    def _proposal(self) -> ProposalSet | None:
        return self.controller.session.current_proposal

    def layers(self) -> CanvasLayers:
        session = self.controller.session
        proposal = self._proposal()
        selected = session.selected_candidate
        if proposal is None:
            shape = session.context.shape
            disagreement = np.zeros(shape, dtype=np.bool_)
            edge = np.zeros(shape, dtype=np.bool_)
            count = 0
        else:
            disagreement = proposal.uncertainty.disagreement_mask_roi
            edge = proposal.uncertainty.crop_edge_risk_mask_roi
            count = len(proposal.candidates)
            shape = session.context.shape
        selected_mask = selected.mask if selected is not None else np.zeros(shape, dtype=np.bool_)
        return CanvasLayers(
            shape,
            session.context.user_roi_full,
            session.context.crop_rect_full,
            selected_mask,
            disagreement,
            edge,
            count,
        )

    def mouse_press(self, x: float, y: float, button: str) -> Any:
        """Route left/right clicks as foreground/background full-image points."""

        px, py = self.transform.view_to_pixel(x, y)
        if button.lower() in {"left", "primary", "1"}:
            return self.controller.point(px, py, 1)
        if button.lower() in {"right", "secondary", "2"}:
            return self.controller.point(px, py, 0)
        raise ValueError("button must be left or right")

    def brush_stroke(self, points_view: list[tuple[float, float]], *, radius: int = 0) -> Any:
        points = [self.transform.view_to_pixel(x, y, clamp=True) for x, y in points_view]
        return self.controller.edit("brush", points=points, radius=radius)

    def erase_stroke(self, points_view: list[tuple[float, float]], *, radius: int = 0) -> Any:
        points = [self.transform.view_to_pixel(x, y, clamp=True) for x, y in points_view]
        return self.controller.edit("erase", points=points, radius=radius)

    def key_press(self, key: str) -> Any:
        return self.controller.key(key)

    def candidate_point_to_crop(self, point_full: tuple[int, int]) -> tuple[int, int]:
        return full_to_crop_point(point_full, self.context)


CanvasModel = AnnotationCanvasModel

__all__ = [
    "AnnotationCanvasModel",
    "CanvasLayers",
    "CanvasModel",
    "CanvasTransform",
    "ViewportTransform",
]
