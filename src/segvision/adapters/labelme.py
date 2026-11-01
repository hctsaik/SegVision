"""Deterministic LabelMe polygon export for accepted SegVision masks.

The native workflow keeps a lossless binary mask as its source of truth.  This
adapter deliberately lives at the persistence boundary: it converts that mask
to ordinary LabelMe JSON without changing the accepted PNG or its provenance.
"""

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from segvision.defaults import DEFAULT_CLASS_ID

from segvision.core.errors import InvalidMask, PersistenceError
from segvision.core.mask_ops import fill_holes as fill_mask_holes

from .png_sidecar import AcceptedStore, PersistedPair


def _components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """Return deterministic 4-connected foreground components as (y, x) cells."""
    height, width = mask.shape
    seen = np.zeros(mask.shape, dtype=np.bool_)
    components: list[list[tuple[int, int]]] = []
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or seen[y, x]:
                continue
            queue: deque[tuple[int, int]] = deque([(y, x)])
            seen[y, x] = True
            cells: list[tuple[int, int]] = []
            while queue:
                cy, cx = queue.popleft()
                cells.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy, cx + 1), (cy + 1, cx), (cy, cx - 1)):
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((ny, nx))
            components.append(cells)
    return components


def _point_segment_distance(
    point: tuple[int, int], start: tuple[int, int], end: tuple[int, int]
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    if dx == 0 and dy == 0:
        return float(np.hypot(px - sx, py - sy))
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / float(dx * dx + dy * dy)))
    return float(np.hypot(px - (sx + t * dx), py - (sy + t * dy)))


def _rdp(points: list[tuple[int, int]], tolerance: float) -> list[tuple[int, int]]:
    """Ramer-Douglas-Peucker simplification for one open polyline."""
    if len(points) <= 2:
        return points
    start, end = points[0], points[-1]
    farthest_index = 0
    farthest_distance = 0.0
    for index, point in enumerate(points[1:-1], start=1):
        distance = _point_segment_distance(point, start, end)
        if distance > farthest_distance:
            farthest_index, farthest_distance = index, distance
    if farthest_distance <= tolerance:
        return [start, end]
    left = _rdp(points[: farthest_index + 1], tolerance)
    right = _rdp(points[farthest_index:], tolerance)
    return left[:-1] + right


def _simplify(points: list[tuple[int, int]], *, tolerance: float = 0.75) -> list[list[int]]:
    """Remove grid noise and simplify a closed boundary without opening it."""
    if len(points) < 3:
        return []
    cleaned: list[tuple[int, int]] = []
    for point in points:
        if not cleaned or point != cleaned[-1]:
            cleaned.append(point)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    changed = True
    while changed and len(cleaned) >= 3:
        changed = False
        kept: list[tuple[int, int]] = []
        count = len(cleaned)
        for index, point in enumerate(cleaned):
            previous = cleaned[index - 1]
            following = cleaned[(index + 1) % count]
            cross = (point[0] - previous[0]) * (following[1] - point[1]) - (
                point[1] - previous[1]
            ) * (following[0] - point[0])
            if cross == 0:
                changed = True
            else:
                kept.append(point)
        cleaned = kept
    if len(cleaned) < 3:
        return []
    if tolerance > 0:
        # Split the cyclic loop at a deterministic anchor and its farthest
        # vertex so RDP never treats the closed loop as a zero-length line.
        anchor_index = min(range(len(cleaned)), key=lambda index: cleaned[index])
        rotated = cleaned[anchor_index:] + cleaned[:anchor_index]
        farthest_index = max(
            range(1, len(rotated)),
            key=lambda index: (rotated[index][0] - rotated[0][0]) ** 2
            + (rotated[index][1] - rotated[0][1]) ** 2,
        )
        first = _rdp(rotated[: farthest_index + 1], tolerance)
        second = _rdp(rotated[farthest_index:] + [rotated[0]], tolerance)
        cleaned = first[:-1] + second[:-1]
    return [[int(x), int(y)] for x, y in cleaned] if len(cleaned) >= 3 else []


def _component_loops(
    cells: list[tuple[int, int]], *, simplify_tolerance: float
) -> list[list[list[int]]]:
    """Trace clockwise pixel-boundary loops for one 4-connected component."""
    cell_set = set(cells)
    # Each edge is oriented clockwise around foreground pixels.  The same
    # start vertex can occur more than once for a pathological diagonal join;
    # retaining a list keeps the traversal deterministic instead of dropping
    # a boundary edge.
    outgoing: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for y, x in sorted(cell_set):
        neighbours = (
            ((y - 1, x), ((x, y), (x + 1, y))),
            ((y, x + 1), ((x + 1, y), (x + 1, y + 1))),
            ((y + 1, x), ((x + 1, y + 1), (x, y + 1))),
            ((y, x - 1), ((x, y + 1), (x, y))),
        )
        for neighbour, (start, end) in neighbours:
            if neighbour not in cell_set:
                outgoing.setdefault(start, []).append(end)
    for values in outgoing.values():
        values.sort()

    loops: list[list[list[int]]] = []
    while outgoing:
        start = min(outgoing)
        current = start
        points: list[tuple[int, int]] = []
        guard = sum(len(values) for values in outgoing.values()) + 1
        while guard > 0:
            guard -= 1
            points.append(current)
            options = outgoing.get(current)
            if not options:
                break
            following = options.pop(0)
            if not options:
                outgoing.pop(current, None)
            current = following
            if current == start:
                polygon = _simplify(points, tolerance=simplify_tolerance)
                if polygon:
                    loops.append(polygon)
                break
    return loops


def _dilate(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    result = np.zeros_like(mask)
    for dy in range(3):
        for dx in range(3):
            result |= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return result


def _erode(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    result = np.ones_like(mask)
    for dy in range(3):
        for dx in range(3):
            result &= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    return result


def clean_mask_for_polygon(
    mask: np.ndarray, *, close_gaps: int = 1, fill_holes: bool = True
) -> np.ndarray:
    """Close only tiny pixel gaps and fill enclosed voids for export tracing.

    This returns a new mask and is used only to derive LabelMe geometry; the
    accepted PNG remains the untouched source of truth.  One closing pass is
    intentionally conservative: it joins one-pixel brush breaks without
    changing the outer extent of a region.
    """
    array = np.asarray(mask)
    if array.ndim != 2 or array.dtype != np.bool_:
        raise InvalidMask("LabelMe export requires a 2-D bool mask")
    if not array.any():
        raise InvalidMask("LabelMe export requires a non-empty mask")
    if not isinstance(close_gaps, int) or isinstance(close_gaps, bool) or close_gaps < 0:
        raise ValueError("close_gaps must be a non-negative integer")
    cleaned = array.copy()
    for _ in range(close_gaps):
        cleaned = _erode(_dilate(cleaned))
    return fill_mask_holes(cleaned) if fill_holes else cleaned


def mask_to_polygons(
    mask: np.ndarray,
    *,
    close_gaps: int = 1,
    fill_holes: bool = True,
    simplify_tolerance: float = 0.5,
) -> list[list[list[int]]]:
    """Convert a mask to cleaned, closed, deterministic LabelMe polygons."""
    array = np.asarray(mask)
    if array.ndim != 2 or array.dtype != np.bool_:
        raise InvalidMask("LabelMe export requires a 2-D bool mask")
    if not array.any():
        raise InvalidMask("LabelMe export requires a non-empty mask")
    if not isinstance(simplify_tolerance, (int, float)) or not np.isfinite(simplify_tolerance):
        raise ValueError("simplify_tolerance must be finite")
    if simplify_tolerance < 0:
        raise ValueError("simplify_tolerance must be non-negative")
    cleaned = clean_mask_for_polygon(array, close_gaps=close_gaps, fill_holes=fill_holes)
    polygons: list[list[list[int]]] = []
    for component in _components(cleaned):
        polygons.extend(_component_loops(component, simplify_tolerance=float(simplify_tolerance)))
    if not polygons:
        raise InvalidMask("LabelMe export could not trace a mask boundary")
    return polygons


def labelme_dict(
    mask: np.ndarray,
    *,
    image_path: str,
    label: str,
    version: str = "5.5.0",
) -> dict[str, Any]:
    """Build a standard LabelMe JSON document without embedding image bytes."""
    if not isinstance(image_path, str) or not image_path:
        raise ValueError("image_path is required")
    if not isinstance(label, str) or not label:
        raise ValueError("label is required")
    array = np.asarray(mask)
    polygons = mask_to_polygons(array)
    height, width = (int(value) for value in array.shape)
    return {
        "version": version,
        "flags": {},
        "shapes": [
            {
                "label": label,
                "points": polygon,
                "group_id": None,
                "description": "",
                "shape_type": "polygon",
                "flags": {},
            }
            for polygon in polygons
        ],
        "imagePath": image_path,
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width,
    }


def export_pair(
    pair: PersistedPair,
    output_path: str | Path,
    *,
    store: AcceptedStore,
    image_path: str | None = None,
    label: str | None = None,
) -> Path:
    """Export one accepted pair and return the written LabelMe JSON path."""
    mask = store.load_mask(pair)
    sidecar = pair.sidecar
    image = sidecar.get("image", {})
    image_id = str(image.get("image_id") or pair.sidecar_path.stem)
    document = labelme_dict(
        mask,
        image_path=image_path or f"{image_id}.png",
        label=label or str(sidecar.get("class_id") or DEFAULT_CLASS_ID),
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise PersistenceError(f"LabelMe export failed: {exc}") from exc
    return target


def export_directory(
    input_root: str | Path,
    output_root: str | Path,
    *,
    image_root: str | Path | None = None,
    label: str | None = None,
) -> list[Path]:
    """Export every accepted sidecar in a SegVision output directory."""
    store = AcceptedStore(input_root)
    destination = Path(output_root)
    destination.mkdir(parents=True, exist_ok=True)
    source_root = Path(image_root).resolve() if image_root else None
    exported: list[Path] = []
    for pair in store.load():
        sidecar = pair.sidecar
        image_id = str(sidecar.get("image", {}).get("image_id") or pair.sidecar_path.stem)
        image_path: str | None = None
        if source_root is not None:
            relative = Path(*image_id.split("/"))
            for suffix in (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"):
                candidate = source_root / relative.with_suffix(suffix)
                if candidate.is_file():
                    # LabelMe treats imagePath as a portable relative path;
                    # normalize Windows separators before serialising JSON.
                    image_path = os.path.relpath(candidate, destination).replace(os.sep, "/")
                    break
        target = destination / f"{pair.sidecar_path.stem}.json"
        exported.append(export_pair(pair, target, store=store, image_path=image_path, label=label))
    return exported


def rasterize_labelme(
    document: dict[str, Any], *, image_width: int, image_height: int
) -> tuple[np.ndarray, dict[str, Any]]:
    """Strictly validate and rasterize supported LabelMe polygons."""
    if not isinstance(document, dict):
        raise ValueError("LabelMe document must be an object")
    try:
        document_width = int(document.get("imageWidth", -1))
        document_height = int(document.get("imageHeight", -1))
    except (TypeError, ValueError) as exc:
        raise ValueError("LabelMe image dimensions are invalid") from exc
    if document_width != int(image_width) or document_height != int(image_height):
        raise ValueError("LabelMe image dimensions do not match the source image")
    shapes = document.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        raise ValueError("LabelMe document contains no shapes")
    canvas = np.zeros((image_height, image_width), dtype=np.bool_)
    labels: list[str] = []
    for index, shape in enumerate(shapes):
        if not isinstance(shape, dict) or shape.get("shape_type") != "polygon":
            raise ValueError(f"shape {index} is unsupported; only polygon is accepted")
        points = shape.get("points")
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError(f"shape {index} polygon requires at least three points")
        polygon: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(f"shape {index} contains an invalid point")
            try:
                x, y = float(point[0]), float(point[1])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"shape {index} contains an invalid point") from exc
            if not (
                np.isfinite(x)
                and np.isfinite(y)
                and 0 <= x < image_width
                and 0 <= y < image_height
            ):
                raise ValueError(f"shape {index} point is outside image bounds")
            polygon.append((x, y))
        label = str(shape.get("label") or "")
        if not label:
            raise ValueError(f"shape {index} label is required")
        labels.append(label)
        # Coordinates in a LabelMe polygon describe pixel boundaries.  Test
        # pixel centres explicitly so export/import does not grow every edge
        # by one pixel (PIL's inclusive polygon rasterizer does).
        min_x = max(0, int(np.floor(min(x for x, _ in polygon))))
        max_x = min(image_width - 1, int(np.ceil(max(x for x, _ in polygon))))
        min_y = max(0, int(np.floor(min(y for _, y in polygon))))
        max_y = min(image_height - 1, int(np.ceil(max(y for _, y in polygon))))
        for py in range(min_y, max_y + 1):
            cy = py + 0.5
            for px in range(min_x, max_x + 1):
                cx = px + 0.5
                inside = False
                for index in range(len(polygon)):
                    x0, y0 = polygon[index - 1]
                    x1, y1 = polygon[index]
                    if (y0 > cy) != (y1 > cy):
                        cross_x = (x1 - x0) * (cy - y0) / (y1 - y0) + x0
                        if cx < cross_x:
                            inside = not inside
                if inside:
                    canvas[py, px] = True
    return canvas, {
        "shape_count": len(shapes),
        "labels": labels,
        "rasterization": "PIL-ImageDraw-polygon-v1",
    }


def preview_mask(
    mask: np.ndarray, *, image_path: str, label: str = DEFAULT_CLASS_ID
) -> dict[str, Any]:
    """Return non-mutating LabelMe geometry and deterministic cleanup metrics."""
    array = np.asarray(mask)
    if array.ndim != 2 or array.dtype != np.bool_:
        raise InvalidMask("LabelMe preview requires a 2-D bool mask")
    cleaned = clean_mask_for_polygon(array)
    polygons = mask_to_polygons(cleaned, close_gaps=0, fill_holes=False)
    delta = abs(int(cleaned.sum()) - int(array.sum())) / float(max(1, int(array.sum())))
    import hashlib

    identity = hashlib.sha256(np.ascontiguousarray(cleaned).tobytes()).hexdigest()
    return {
        "schema_version": 1,
        "label": label or DEFAULT_CLASS_ID,
        "imagePath": image_path,
        "imageWidth": int(array.shape[1]),
        "imageHeight": int(array.shape[0]),
        "polygons": polygons,
        "component_count": len(_components(cleaned)),
        "polygon_count": len(polygons),
        "mask_area": int(array.sum()),
        "cleaned_area": int(cleaned.sum()),
        "area_delta_fraction": delta,
        "cleanup_identity": identity,
        "closed_gaps": bool(not np.array_equal(array, cleaned)),
    }
