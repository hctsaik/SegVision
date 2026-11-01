"""Track D observational spike: DINOv2 patch prototypes, not ROI copy.

Teacher = capsule scratch 000 gold (stand-in for Accept).
Targets = 002 and 003, whose scratches sit in a different place.
DINO proposes a box; official MobileSAM vit_t draws the edge.
Local CPU only. quality_gate=false. Not a v1 hot path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from segvision.acceptance.quality import symmetric_boundary_f1

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

NAMES = ("000.png", "002.png", "003.png")
DINO_SIZE = 518
PATCH = 14
GRID = DINO_SIZE // PATCH
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _load_pair(name: str, capsule: Path) -> tuple[np.ndarray, np.ndarray]:
    rgb = np.asarray(Image.open(capsule / "test" / "scratch" / name).convert("RGB"))
    gold = np.asarray(
        Image.open(capsule / "ground_truth" / "scratch" / f"{Path(name).stem}_mask.png").convert("L")
    ) == 255
    return rgb, gold


def _letterbox(rgb: np.ndarray, mask: np.ndarray | None) -> tuple[np.ndarray, np.ndarray | None, float]:
    h, w = rgb.shape[:2]
    scale = DINO_SIZE / max(h, w)
    nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
    canvas = np.zeros((DINO_SIZE, DINO_SIZE, 3), dtype=np.uint8)
    resized = np.asarray(Image.fromarray(rgb).resize((nw, nh), Image.Resampling.BILINEAR))
    canvas[:nh, :nw] = resized
    out_mask = None
    if mask is not None:
        m = np.zeros((DINO_SIZE, DINO_SIZE), dtype=bool)
        mr = np.asarray(
            Image.fromarray(mask.astype(np.uint8) * 255).resize((nw, nh), Image.Resampling.NEAREST)
        ) > 127
        m[:nh, :nw] = mr
        out_mask = m
    return canvas, out_mask, scale


def _patch_frac(mask: np.ndarray) -> np.ndarray:
    frac = np.zeros((GRID, GRID), dtype=np.float32)
    for gy in range(GRID):
        for gx in range(GRID):
            cell = mask[gy * PATCH : (gy + 1) * PATCH, gx * PATCH : (gx + 1) * PATCH]
            frac[gy, gx] = float(cell.mean()) if cell.size else 0.0
    return frac


def _dino_tokens(model: Any, letterbox_rgb: np.ndarray) -> np.ndarray:
    import torch

    x = torch.from_numpy(letterbox_rgb).permute(2, 0, 1).float() / 255.0
    x = (x - torch.from_numpy(MEAN)[:, None, None]) / torch.from_numpy(STD)[:, None, None]
    with torch.no_grad():
        feat = model.forward_features(x.unsqueeze(0))
    tokens = feat[0, 1:, :]
    tokens = torch.nn.functional.normalize(tokens, dim=-1)
    return tokens.cpu().numpy().reshape(GRID, GRID, -1)


def _fit_prototypes(tokens: np.ndarray, gold_letterbox: np.ndarray) -> dict[str, Any]:
    from PIL import ImageFilter

    gold_img = Image.fromarray(gold_letterbox.astype(np.uint8) * 255)
    fg = np.asarray(gold_img.filter(ImageFilter.MinFilter(3))) > 127
    near = np.asarray(gold_img.filter(ImageFilter.MaxFilter(9))) > 127
    frac_fg = _patch_frac(fg)
    frac_near = _patch_frac(near)
    sure_fg = frac_fg >= 0.35
    sure_bg = (frac_near <= 0.02) & (frac_fg <= 0.02)
    if int(sure_fg.sum()) < 3:
        sure_fg = _patch_frac(gold_letterbox) >= 0.20
    if int(sure_bg.sum()) < 8:
        sure_bg = _patch_frac(gold_letterbox) <= 0.02
    fg_vec = tokens[sure_fg].mean(axis=0)
    bg_vec = tokens[sure_bg].mean(axis=0)
    fg_vec = fg_vec / max(1e-8, np.linalg.norm(fg_vec))
    bg_vec = bg_vec / max(1e-8, np.linalg.norm(bg_vec))
    return {
        "fg": fg_vec,
        "bg": bg_vec,
        "n_fg": int(sure_fg.sum()),
        "n_bg": int(sure_bg.sum()),
    }


def _margin_map(tokens: np.ndarray, proto: dict[str, Any]) -> np.ndarray:
    flat = tokens.reshape(-1, tokens.shape[-1])
    sim_fg = flat @ proto["fg"]
    sim_bg = flat @ proto["bg"]
    return (sim_fg - sim_bg).reshape(GRID, GRID)


def _largest_component(binary: np.ndarray) -> tuple[np.ndarray, int, int]:
    h, w = binary.shape
    seen = np.zeros_like(binary, dtype=bool)
    best = np.zeros_like(binary, dtype=bool)
    best_area = 0
    second = 0
    for y in range(h):
        for x in range(w):
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
                        if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not seen[ny, nx]:
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


def _component_to_roi(
    component: np.ndarray, scale: float, image_shape: tuple[int, int], pad: int = 16
) -> tuple[int, int, int, int]:
    ys, xs = np.where(component)
    if xs.size == 0:
        raise ValueError("empty component")
    # letterbox pixels
    x0 = int(xs.min() * PATCH)
    y0 = int(ys.min() * PATCH)
    x1 = int((xs.max() + 1) * PATCH)
    y1 = int((ys.max() + 1) * PATCH)
    ix0 = int(np.floor(x0 / scale))
    iy0 = int(np.floor(y0 / scale))
    ix1 = int(np.ceil(x1 / scale))
    iy1 = int(np.ceil(y1 / scale))
    h, w = image_shape
    return (
        max(0, ix0 - pad),
        max(0, iy0 - pad),
        min(w, ix1 + pad),
        min(h, iy1 + pad),
    )


def _sam_predict(predictor: Any, rgb: np.ndarray, roi: tuple[int, int, int, int]) -> tuple[list[np.ndarray], list[float], float]:
    x0, y0, x1, y1 = roi
    mx = max(2, int(np.ceil((x1 - x0) * 0.10)))
    my = max(2, int(np.ceil((y1 - y0) * 0.10)))
    cx0, cy0 = max(0, x0 - mx), max(0, y0 - my)
    cx1, cy1 = min(rgb.shape[1], x1 + mx), min(rgb.shape[0], y1 + my)
    crop = rgb[cy0:cy1, cx0:cx1]
    box = np.asarray([x0 - cx0, y0 - cy0, x1 - cx0, y1 - cy0], dtype=np.float32)
    started = time.perf_counter()
    predictor.set_image(crop)
    masks, scores, _ = predictor.predict(box=box, multimask_output=True, return_logits=False)
    elapsed = (time.perf_counter() - started) * 1000.0
    full = []
    for mask in masks:
        canvas = np.zeros(rgb.shape[:2], dtype=bool)
        canvas[cy0:cy1, cx0:cx1] = mask.astype(bool)
        full.append(canvas)
    return full, [float(s) for s in scores], elapsed


def _metrics(pred: np.ndarray, gold: np.ndarray) -> dict[str, float | int]:
    inter = int(np.logical_and(pred, gold).sum())
    union = int(np.logical_or(pred, gold).sum())
    return {
        "iou": float(inter / union) if union else 1.0,
        "boundary_f1": float(symmetric_boundary_f1(pred, gold)),
        "pred_pixels": int(pred.sum()),
        "gold_pixels": int(gold.sum()),
    }


def _overlay(rgb: np.ndarray, pred: np.ndarray, gold: np.ndarray, roi: tuple[int, int, int, int]) -> Image.Image:
    vis = rgb.astype(np.float32)
    both = pred & gold
    fp = pred & np.logical_not(gold)
    fn = gold & np.logical_not(pred)
    vis[both] = vis[both] * 0.5 + np.array([0.0, 200.0, 80.0]) * 0.5
    vis[fp] = vis[fp] * 0.5 + np.array([220.0, 50.0, 40.0]) * 0.5
    vis[fn] = vis[fn] * 0.45 + np.array([40.0, 110.0, 255.0]) * 0.55
    image = Image.fromarray(np.clip(vis, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = roi
    draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(255, 210, 0), width=3)
    margin = 80
    h, w = gold.shape
    return image.crop(
        (max(0, x0 - margin), max(0, y0 - margin), min(w, x1 + margin), min(h, y1 + margin))
    )


def run(out_dir: Path) -> dict[str, Any]:
    import timm
    import torch

    capsule_value = os.environ.get("SEGVISION_MVTEC_CAPSULE_ROOT")
    source_value = os.environ.get("SEGVISION_MOBILESAM_SOURCE")
    checkpoint_value = os.environ.get("SEGVISION_MOBILESAM_CHECKPOINT")
    missing = [
        name
        for name, value in (
            ("SEGVISION_MVTEC_CAPSULE_ROOT", capsule_value),
            ("SEGVISION_MOBILESAM_SOURCE", source_value),
            ("SEGVISION_MOBILESAM_CHECKPOINT", checkpoint_value),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Set required local input paths: " + ", ".join(missing))
    capsule = Path(capsule_value).expanduser()
    source = Path(source_value).expanduser()
    checkpoint = Path(checkpoint_value).expanduser()

    sys.path.insert(0, str(source))
    from mobile_sam import SamPredictor, sam_model_registry

    torch.set_num_threads(1)
    dino = timm.create_model(
        "vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0, dynamic_img_size=True
    )
    dino.eval()
    sam = sam_model_registry["vit_t"](checkpoint=str(checkpoint))
    sam.eval()
    predictor = SamPredictor(sam)

    loaded = {name: _load_pair(name, capsule) for name in NAMES}
    teacher_rgb, teacher_gold = loaded["000.png"]
    lb_rgb, lb_gold, _ = _letterbox(teacher_rgb, teacher_gold)
    tokens_t = _dino_tokens(dino, lb_rgb)
    proto = _fit_prototypes(tokens_t, lb_gold)

    overlays = out_dir / "overlays"
    overlays.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []

    jobs = [
        ("000.png", "self_match"),
        ("002.png", "transfer_from_000"),
        ("003.png", "transfer_from_000"),
    ]
    for name, mode in jobs:
        rgb, gold = loaded[name]
        lb, _, scale = _letterbox(rgb, None)
        t0 = time.perf_counter()
        tokens = _dino_tokens(dino, lb)
        margin = _margin_map(tokens, proto)
        dino_ms = (time.perf_counter() - t0) * 1000.0
        peak = float(margin.max())
        binary = margin >= max(0.05, 0.45 * peak)
        component, area, second = _largest_component(binary)
        would_abstain = area < 2 or (second > 0 and second >= 0.6 * area)
        roi = _component_to_roi(component, scale, rgb.shape[:2])
        gold_ys, gold_xs = np.where(gold)
        gold_in_roi = 0.0
        if gold_xs.size:
            inside = (
                (gold_xs >= roi[0])
                & (gold_xs < roi[2])
                & (gold_ys >= roi[1])
                & (gold_ys < roi[3])
            )
            gold_in_roi = float(inside.mean())
        masks, scores, sam_ms = _sam_predict(predictor, rgb, roi)
        ranked = []
        best_f1_i = 0
        best_f1 = -1.0
        best_score_i = int(np.argmax(scores))
        for i, (mask, score) in enumerate(zip(masks, scores)):
            m = _metrics(mask, gold)
            m["score"] = score
            m["index"] = i
            ranked.append(m)
            if float(m["boundary_f1"]) > best_f1:
                best_f1 = float(m["boundary_f1"])
                best_f1_i = i
        overlay_name = f"{Path(name).stem}-{mode}.png"
        _overlay(rgb, masks[best_f1_i], gold, roi).save(overlays / overlay_name)
        cases.append(
            {
                "image": name,
                "mode": mode,
                "teacher": "000.png",
                "dino_ms": dino_ms,
                "sam_ms": sam_ms,
                "n_fg": proto["n_fg"],
                "n_bg": proto["n_bg"],
                "margin_peak": peak,
                "component_area_patches": area,
                "second_area_patches": second,
                "would_abstain": would_abstain,
                "proposed_roi": list(roi),
                "gold_fraction_inside_proposed_roi": gold_in_roi,
                "sam_score_pick": ranked[best_score_i],
                "best_f1_pick": ranked[best_f1_i],
                "candidates": ranked,
                "overlay": f"overlays/{overlay_name}",
            }
        )

    return {
        "schema_version": 1,
        "claim_scope": {
            "observational_local_eval": True,
            "quality_gate": False,
            "domain_validation": False,
            "v1_hot_path": False,
        },
        "method": "DINOv2-small patch14 mean FG/BG prototypes → largest margin CC → MobileSAM box",
        "not_method": "copy previous user_roi_full coordinates",
        "dino_model": "vit_small_patch14_dinov2.lvd142m",
        "cases": cases,
    }


def _html(report: dict[str, Any]) -> str:
    rows = []
    for case in report["cases"]:
        score = case["sam_score_pick"]
        f1 = case["best_f1_pick"]
        rows.append(
            "<tr>"
            f"<td>{case['image']}<br><code>{case['mode']}</code></td>"
            f"<td>{case['gold_fraction_inside_proposed_roi']:.2f}</td>"
            f"<td>IoU {score['iou']:.3f}<br>F1 {score['boundary_f1']:.3f}</td>"
            f"<td>IoU {f1['iou']:.3f}<br>F1 {f1['boundary_f1']:.3f}</td>"
            f"<td>{case['dino_ms']:.0f} + {case['sam_ms']:.0f} ms<br>abstain={case['would_abstain']}</td>"
            f"<td><img src='{case['overlay']}' width='640'></td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<title>Track D DINOv2 prototype (observational)</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#111;color:#eee;margin:24px}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #333;padding:8px;vertical-align:top}}
img{{max-width:100%}}
.note{{color:#bbb;max-width:980px;line-height:1.45}}
</style></head><body>
<h1>Track D: DINO patch prototype → SAM</h1>
<p class="note">Does <b>not</b> copy the previous ROI box. Teacher is scratch/000 gold.
Green=overlap, red=extra, blue=missed, yellow=<b>DINO-proposed</b> box.
<code>gold_fraction_inside_proposed_roi</code> is the localization score that Track A cannot claim
when the defect moved. Local observational only; DINO stays off the v1 hot path.</p>
<table>
<tr><th>Case</th><th>Gold inside DINO box</th><th>SAM score pick</th><th>Best F1 pick</th><th>Time / abstain</th><th>Overlay</th></tr>
{''.join(rows)}
</table>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("playwright-report/dino-prototype-scratch"))
    parser.add_argument("--from-json", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "report.json"
    if args.from_json:
        report = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        report = run(args.output_dir)
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "index.html").write_text(_html(report), encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    "image": c["image"],
                    "mode": c["mode"],
                    "gold_in_box": round(c["gold_fraction_inside_proposed_roi"], 3),
                    "score_iou": round(c["sam_score_pick"]["iou"], 3),
                    "best_f1": round(c["best_f1_pick"]["boundary_f1"], 3),
                    "abstain": c["would_abstain"],
                }
                for c in report["cases"]
            ],
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
