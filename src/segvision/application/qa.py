"""Deterministic, local mask quality checks for pre-save review."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from .config import QA_THRESHOLDS


def _components(mask: np.ndarray) -> list[tuple[int, tuple[int, int, int, int]]]:
    seen = np.zeros_like(mask, dtype=np.bool_)
    result: list[tuple[int, tuple[int, int, int, int]]] = []
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(y, x)])
            seen[y, x] = True
            count = 0
            minx = maxx = x
            miny = maxy = y
            while q:
                cy, cx = q.popleft()
                count += 1
                minx, maxx = min(minx, cx), max(maxx, cx)
                miny, maxy = min(miny, cy), max(maxy, cy)
                for ny, nx in ((cy - 1, cx), (cy, cx + 1), (cy + 1, cx), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            result.append((count, (minx, miny, maxx + 1, maxy + 1)))
    return result


def _holes(mask: np.ndarray) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Return enclosed 4-connected background components."""
    background = ~mask
    seen = np.zeros_like(mask, dtype=np.bool_)
    h, w = mask.shape
    result: list[tuple[int, tuple[int, int, int, int]]] = []
    for y in range(h):
        for x in range(w):
            if not background[y, x] or seen[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(y, x)])
            seen[y, x] = True
            pixels: list[tuple[int, int]] = []
            touches_edge = False
            while q:
                cy, cx = q.popleft()
                pixels.append((cy, cx))
                touches_edge |= cy in (0, h - 1) or cx in (0, w - 1)
                for ny, nx in ((cy - 1, cx), (cy, cx + 1), (cy + 1, cx), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and background[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if not touches_edge:
                xs = [cx for _, cx in pixels]
                ys = [cy for cy, _ in pixels]
                result.append((len(pixels), (min(xs), min(ys), max(xs) + 1, max(ys) + 1)))
    return result


def _one_pixel_bridges(mask: np.ndarray) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Find one-pixel-wide orthogonal connectors between foreground lobes."""
    h, w = mask.shape
    result: list[tuple[int, tuple[int, int, int, int]]] = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if not mask[y, x]:
                continue
            horizontal = mask[y, x - 1] and mask[y, x + 1] and not mask[y - 1, x] and not mask[y + 1, x]
            vertical = mask[y - 1, x] and mask[y + 1, x] and not mask[y, x - 1] and not mask[y, x + 1]
            if horizontal or vertical:
                result.append((1, (x, y, x + 1, y + 1)))
    return result


def analyze_mask(mask: np.ndarray, *, crop_rect: tuple[int, int, int, int] | None = None, polygon_mask: np.ndarray | None = None) -> dict[str, Any]:
    value = np.asarray(mask, dtype=np.bool_)
    if value.ndim != 2:
        raise ValueError("QA requires a 2-D binary mask")
    h, w = value.shape
    issues: list[dict[str, Any]] = []

    def issue(code: str, severity: str, bbox: list[int], measured: dict[str, Any], message: str) -> None:
        issues.append({
            "code": code,
            "severity": severity,
            "bbox": bbox,
            "measured": measured,
            "threshold_id": "segvision-qa-v1",
            "message": message,
        })

    foreground = int(value.sum())
    if foreground == 0:
        issue("EMPTY_MASK", "blocking", [0, 0, w, h], {"pixels": 0}, "遮罩是空的，無法儲存為 Accept。")
        return {"schema_version": 1, "thresholds": dict(QA_THRESHOLDS), "issues": issues, "blocking": True}
    fraction = foreground / float(h * w)
    if fraction >= QA_THRESHOLDS["near_full_fraction"]:
        issue("NEAR_FULL_MASK", "advisory", [0, 0, w, h], {"fraction": fraction}, "前景幾乎覆蓋整張影像，請確認範圍。")
    if bool(value[0, :].any() or value[-1, :].any() or value[:, 0].any() or value[:, -1].any()):
        issue("IMAGE_BOUNDARY_CONTACT", "advisory", [0, 0, w, h], {"pixels": foreground}, "前景接觸影像邊界。")
    if crop_rect is not None:
        x0, y0, x1, y1 = crop_rect
        ys, xs = np.nonzero(value)
        if bool(((xs == x0) | (ys == y0) | (xs == x1 - 1) | (ys == y1 - 1)).any()):
            issue("CROP_BOUNDARY_CONTACT", "advisory", [x0, y0, x1, y1], {"crop_rect": list(crop_rect)}, "前景接觸工作框邊界。")
    components = _components(value)
    for count, bbox in components:
        if count < QA_THRESHOLDS["tiny_component_pixels"]:
            issue("TINY_COMPONENT", "advisory", list(bbox), {"pixels": count}, "發現非常小的孤立區塊。")
    if len(components) > QA_THRESHOLDS["max_components"]:
        issue("COMPONENT_COUNT", "advisory", [0, 0, w, h], {"count": len(components)}, "區塊數量超過建議上限。")
    for count, bbox in _holes(value):
        issue("ENCLOSED_HOLE", "advisory", list(bbox), {"pixels": count}, "遮罩內含封閉孔洞，請確認是否為刻意保留")
    for count, bbox in _one_pixel_bridges(value):
        issue("ONE_PIXEL_BRIDGE", "advisory", list(bbox), {"pixels": count}, "偵測到單像素橋接，請確認輪廓是否需要修整")
    # Multiple equivalent detections should be displayed once while their
    # deterministic measurement remains available in the retained issue.
    unique: dict[tuple[str, tuple[int, ...]], dict[str, Any]] = {}
    for item in issues:
        unique.setdefault((str(item["code"]), tuple(int(v) for v in item["bbox"])), item)
    issues = list(unique.values())
    if polygon_mask is not None:
        poly = np.asarray(polygon_mask, dtype=np.bool_)
        if poly.shape != value.shape:
            raise ValueError("polygon preview shape mismatch")
        delta = abs(int(poly.sum()) - foreground) / float(max(1, foreground))
        if delta > QA_THRESHOLDS["labelme_area_delta_fraction"]:
            issue("LABELME_AREA_DELTA", "blocking", [0, 0, w, h], {"fraction": delta}, "LabelMe 多邊形與遮罩面積差異超過允許值。")
    return {
        "schema_version": 1,
        "thresholds": dict(QA_THRESHOLDS),
        "issues": issues,
        "blocking": any(item["severity"] == "blocking" for item in issues),
    }
