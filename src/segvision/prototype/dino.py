"""DINOv2-small patch prototypes: appearance match, not ROI copy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

DINO_SIZE = 518
PATCH = 14
GRID = DINO_SIZE // PATCH
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True, slots=True)
class MatchResult:
    roi: tuple[int, int, int, int] | None
    abstain: bool
    reason: str
    margin_peak: float
    component_area: int
    second_area: int


def letterbox(rgb: np.ndarray, mask: np.ndarray | None) -> tuple[np.ndarray, np.ndarray | None, float]:
    height, width = rgb.shape[:2]
    scale = DINO_SIZE / max(height, width)
    nh, nw = max(1, round(height * scale)), max(1, round(width * scale))
    canvas = np.zeros((DINO_SIZE, DINO_SIZE, 3), dtype=np.uint8)
    canvas[:nh, :nw] = np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.Resampling.BILINEAR))
    out_mask = None
    if mask is not None:
        packed = np.zeros((DINO_SIZE, DINO_SIZE), dtype=bool)
        packed[:nh, :nw] = (
            np.asarray(
                Image.fromarray(mask.astype(np.uint8) * 255).resize((nw, nh), Image.Resampling.NEAREST)
            )
            > 127
        )
        out_mask = packed
    return canvas, out_mask, scale


def patch_frac(mask: np.ndarray) -> np.ndarray:
    frac = np.zeros((GRID, GRID), dtype=np.float32)
    for gy in range(GRID):
        for gx in range(GRID):
            cell = mask[gy * PATCH : (gy + 1) * PATCH, gx * PATCH : (gx + 1) * PATCH]
            frac[gy, gx] = float(cell.mean()) if cell.size else 0.0
    return frac


def fit_prototypes(tokens: np.ndarray, gold_letterbox: np.ndarray) -> dict[str, Any]:
    gold_img = Image.fromarray(gold_letterbox.astype(np.uint8) * 255)
    fg = np.asarray(gold_img.filter(ImageFilter.MinFilter(3))) > 127
    near = np.asarray(gold_img.filter(ImageFilter.MaxFilter(9))) > 127
    frac_fg = patch_frac(fg)
    frac_near = patch_frac(near)
    sure_fg = frac_fg >= 0.35
    sure_bg = (frac_near <= 0.02) & (frac_fg <= 0.02)
    if int(sure_fg.sum()) < 3:
        sure_fg = patch_frac(gold_letterbox) >= 0.20
    if int(sure_bg.sum()) < 8:
        sure_bg = patch_frac(gold_letterbox) <= 0.02
    if int(sure_fg.sum()) < 1 or int(sure_bg.sum()) < 1:
        raise ValueError("teacher trimap has no FG or BG patches")
    fg_vec = tokens[sure_fg].mean(axis=0)
    bg_vec = tokens[sure_bg].mean(axis=0)
    fg_vec = fg_vec / max(1e-8, float(np.linalg.norm(fg_vec)))
    bg_vec = bg_vec / max(1e-8, float(np.linalg.norm(bg_vec)))
    return {"fg": fg_vec, "bg": bg_vec, "n_fg": int(sure_fg.sum()), "n_bg": int(sure_bg.sum())}


def margin_map(tokens: np.ndarray, proto: dict[str, Any]) -> np.ndarray:
    flat = tokens.reshape(-1, tokens.shape[-1])
    return (flat @ proto["fg"] - flat @ proto["bg"]).reshape(GRID, GRID)


def largest_component(binary: np.ndarray) -> tuple[np.ndarray, int, int]:
    height, width = binary.shape
    seen = np.zeros_like(binary, dtype=bool)
    best = np.zeros_like(binary, dtype=bool)
    best_area = 0
    second = 0
    for y in range(height):
        for x in range(width):
            if not binary[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]
            cells: list[tuple[int, int]] = []
            seen[y, x] = True
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny in (cy - 1, cy, cy + 1):
                    for nx in (cx - 1, cx, cx + 1):
                        if 0 <= ny < height and 0 <= nx < width and binary[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            if len(cells) > best_area:
                second = best_area
                best_area = len(cells)
                best = np.zeros_like(binary, dtype=bool)
                for cy, cx in cells:
                    best[cy, cx] = True
            elif len(cells) > second:
                second = len(cells)
    return best, best_area, second


def component_to_roi(
    component: np.ndarray, scale: float, image_shape: tuple[int, int], pad: int = 16
) -> tuple[int, int, int, int]:
    ys, xs = np.where(component)
    if xs.size == 0:
        raise ValueError("empty component")
    x0 = int(xs.min() * PATCH)
    y0 = int(ys.min() * PATCH)
    x1 = int((xs.max() + 1) * PATCH)
    y1 = int((ys.max() + 1) * PATCH)
    height, width = image_shape
    return (
        max(0, int(np.floor(x0 / scale)) - pad),
        max(0, int(np.floor(y0 / scale)) - pad),
        min(width, int(np.ceil(x1 / scale)) + pad),
        min(height, int(np.ceil(y1 / scale)) + pad),
    )


def match_tokens(
    tokens: np.ndarray, proto: dict[str, Any], scale: float, image_shape: tuple[int, int]
) -> MatchResult:
    margin = margin_map(tokens, proto)
    peak = float(margin.max()) if margin.size else 0.0
    binary = margin >= max(0.05, 0.45 * peak)
    component, area, second = largest_component(binary)
    if area < 2:
        return MatchResult(None, True, "no confident DINO component", peak, area, second)
    if second >= 0.6 * area:
        return MatchResult(None, True, "multiple similar DINO peaks; abstain", peak, area, second)
    roi = component_to_roi(component, scale, image_shape)
    if roi[2] - roi[0] < 8 or roi[3] - roi[1] < 8:
        return MatchResult(None, True, "proposed ROI is too small", peak, area, second)
    return MatchResult(roi, False, "DINO prototype matched.", peak, area, second)


class PrototypeStore:
    def __init__(self) -> None:
        self._model: Any = None
        self._proto: dict[str, Any] | None = None
        self._load_error: str | None = None

    @property
    def has_teacher(self) -> bool:
        return self._proto is not None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_error:
            raise RuntimeError(self._load_error)
        try:
            import os

            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            import timm
            import torch

            torch.set_num_threads(1)
            model = timm.create_model(
                "vit_small_patch14_dinov2.lvd142m",
                pretrained=True,
                num_classes=0,
                dynamic_img_size=True,
            )
            model.eval()
            self._model = model
            return model
        except Exception as exc:
            self._load_error = f"DINOv2 unavailable: {exc}"
            raise RuntimeError(self._load_error) from exc

    def tokens(self, letterbox_rgb: np.ndarray) -> np.ndarray:
        import torch

        model = self._ensure_model()
        tensor = torch.from_numpy(letterbox_rgb).permute(2, 0, 1).float() / 255.0
        tensor = (tensor - torch.from_numpy(MEAN)[:, None, None]) / torch.from_numpy(STD)[:, None, None]
        with torch.no_grad():
            feat = model.forward_features(tensor.unsqueeze(0))
        tokens = torch.nn.functional.normalize(feat[0, 1:, :], dim=-1)
        return tokens.cpu().numpy().reshape(GRID, GRID, -1)

    def fit(self, rgb: np.ndarray, mask: np.ndarray) -> None:
        boxed, gold, _ = letterbox(np.asarray(rgb), np.asarray(mask, dtype=bool))
        if gold is None or int(gold.sum()) == 0:
            raise ValueError("accepted mask is empty")
        self._proto = fit_prototypes(self.tokens(boxed), gold)

    def clear(self) -> None:
        self._proto = None

    def match(self, rgb: np.ndarray) -> MatchResult:
        if self._proto is None:
            return MatchResult(None, True, "no DINO teacher; Accept with prototype enabled first", 0.0, 0, 0)
        boxed, _, scale = letterbox(np.asarray(rgb), None)
        return match_tokens(self.tokens(boxed), self._proto, scale, rgb.shape[:2])
