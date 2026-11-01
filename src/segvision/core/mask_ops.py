"""Deterministic copy-on-write mask operations."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

import numpy as np

from .errors import InvalidMask


def _mask(mask: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask)
    if arr.ndim != 2 or arr.dtype != np.bool_:
        raise InvalidMask("mask operations require a 2-D bool array")
    return arr


def brush(
    mask: np.ndarray,
    points: Sequence[tuple[int, int]],
    radius: int = 0,
    value: bool = True,
    clip_rect: Sequence[int] | None = None,
) -> np.ndarray:
    arr = _mask(mask).copy()
    if radius < 0:
        raise ValueError("radius must be non-negative")
    clip: tuple[int, int, int, int] | None = None
    if clip_rect is not None:
        if len(clip_rect) != 4:
            raise ValueError("clip_rect must contain four coordinates")
        try:
            clip = tuple(int(value) for value in clip_rect)  # type: ignore[assignment]
        except (TypeError, ValueError) as exc:
            raise ValueError("clip_rect must contain integer coordinates") from exc
        if tuple(float(value) for value in clip_rect) != tuple(clip):
            raise ValueError("clip_rect must contain integer coordinates")
        x0, y0, x1, y1 = clip
        h, w = arr.shape
        if x0 < 0 or y0 < 0 or x1 > w or y1 > h or x1 <= x0 or y1 <= y0:
            raise ValueError("clip_rect must be a positive rectangle inside the mask")
    for x, y in points:
        for yy in range(max(0, y - radius), min(arr.shape[0], y + radius + 1)):
            for xx in range(max(0, x - radius), min(arr.shape[1], x + radius + 1)):
                if (xx - x) ** 2 + (yy - y) ** 2 <= radius * radius:
                    if clip is not None and not (clip[0] <= xx < clip[2] and clip[1] <= yy < clip[3]):
                        continue
                    arr[yy, xx] = value
    return arr


def erase(
    mask: np.ndarray,
    points: Sequence[tuple[int, int]],
    radius: int = 0,
    clip_rect: Sequence[int] | None = None,
) -> np.ndarray:
    return brush(mask, points, radius, False, clip_rect)


def grow(mask: np.ndarray) -> np.ndarray:
    arr = _mask(mask)
    padded = np.pad(arr, 1, mode="constant")
    out = np.zeros_like(arr)
    for dy in range(3):
        for dx in range(3):
            out |= padded[dy : dy + arr.shape[0], dx : dx + arr.shape[1]]
    return out


def shrink(mask: np.ndarray) -> np.ndarray:
    arr = _mask(mask)
    padded = np.pad(arr, 1, mode="constant", constant_values=True)
    out = np.ones_like(arr)
    for dy in range(3):
        for dx in range(3):
            out &= padded[dy : dy + arr.shape[0], dx : dx + arr.shape[1]]
    return out


def fill_holes(mask: np.ndarray) -> np.ndarray:
    arr = _mask(mask)
    # Flood-fill background from the border; enclosed background becomes fill.
    background = ~arr
    seen = np.zeros_like(arr)
    q: deque[tuple[int, int]] = deque()
    h, w = arr.shape
    for x in range(w):
        q.append((x, 0))
        q.append((x, h - 1))
    for y in range(h):
        q.append((0, y))
        q.append((w - 1, y))
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y, x] or not background[y, x]:
            continue
        seen[y, x] = True
        q.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return arr | (background & ~seen)


def connected_component(mask: np.ndarray, point: tuple[int, int]) -> np.ndarray:
    """Return the 8-connected component containing ``point``."""
    arr = _mask(mask)
    x, y = point
    h, w = arr.shape
    if x < 0 or y < 0 or x >= w or y >= h or not arr[y, x]:
        raise InvalidMask("point is not inside the requested component")
    out = np.zeros_like(arr)
    out[y, x] = True
    q: deque[tuple[int, int]] = deque([(x, y)])
    while q:
        cx, cy = q.popleft()
        for yy in range(max(0, cy - 1), min(h, cy + 2)):
            for xx in range(max(0, cx - 1), min(w, cx + 2)):
                if not out[yy, xx] and arr[yy, xx]:
                    out[yy, xx] = True
                    q.append((xx, yy))
    return out


def binary_iou(a: np.ndarray, b: np.ndarray) -> float:
    aa, bb = _mask(a), _mask(b)
    if aa.shape != bb.shape:
        raise InvalidMask("IoU shapes differ")
    union = np.logical_or(aa, bb).sum()
    return 1.0 if union == 0 else float(np.logical_and(aa, bb).sum() / union)
