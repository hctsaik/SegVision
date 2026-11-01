"""Observational CPU MobileSAM on MVTec capsule scratches.

Local evaluation only. Not a domain gate, release signoff, or redistribution claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from segvision.acceptance.quality import symmetric_boundary_f1

NAMES = ("000.png", "002.png", "003.png")
PAD_PX = 16


def _local_input(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} to the required local input path")
    return Path(value).expanduser()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gold_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if xs.size == 0:
        raise ValueError("empty gold")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _pad_roi(
    box: tuple[int, int, int, int], shape: tuple[int, int], pad: int
) -> tuple[int, int, int, int]:
    h, w = shape
    x0, y0, x1, y1 = box
    return max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)


def _metrics(pred: np.ndarray, gold: np.ndarray) -> dict[str, float | int]:
    inter = int(np.logical_and(pred, gold).sum())
    union = int(np.logical_or(pred, gold).sum())
    return {
        "iou": float(inter / union) if union else 1.0,
        "boundary_f1": float(symmetric_boundary_f1(pred, gold)),
        "pred_pixels": int(pred.sum()),
        "gold_pixels": int(gold.sum()),
        "false_pos": int(np.logical_and(pred, np.logical_not(gold)).sum()),
        "false_neg": int(np.logical_and(gold, np.logical_not(pred)).sum()),
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
    crop = (
        max(0, x0 - margin),
        max(0, y0 - margin),
        min(w, x1 + margin),
        min(h, y1 + margin),
    )
    return image.crop(crop)


def _predict(predictor: Any, rgb: np.ndarray, roi: tuple[int, int, int, int]) -> tuple[list[np.ndarray], list[float], float]:
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
    full: list[np.ndarray] = []
    for mask in masks:
        canvas = np.zeros(rgb.shape[:2], dtype=bool)
        canvas[cy0:cy1, cx0:cx1] = mask.astype(bool)
        full.append(canvas)
    return full, [float(s) for s in scores], elapsed


def run(out_dir: Path) -> dict[str, Any]:
    capsule = _local_input("SEGVISION_MVTEC_CAPSULE_ROOT")
    source = _local_input("SEGVISION_MOBILESAM_SOURCE")
    checkpoint = _local_input("SEGVISION_MOBILESAM_CHECKPOINT")
    sys.path.insert(0, str(source))
    import torch
    from mobile_sam import SamPredictor, sam_model_registry

    torch.set_num_threads(1)
    model = sam_model_registry["vit_t"](checkpoint=str(checkpoint))
    model.eval()
    predictor = SamPredictor(model)

    images: dict[str, tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]] = {}
    for name in NAMES:
        rgb = np.asarray(Image.open(capsule / "test" / "scratch" / name).convert("RGB"))
        gold = np.asarray(Image.open(capsule / "ground_truth" / "scratch" / f"{Path(name).stem}_mask.png").convert("L")) == 255
        roi = _pad_roi(_gold_bbox(gold), rgb.shape[:2], PAD_PX)
        images[name] = (rgb, gold, roi)

    carried = images["000.png"][2]
    cases: list[dict[str, Any]] = []
    overlays = out_dir / "overlays"
    overlays.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("000.png", "oracle_roi", images["000.png"][2]),
        ("002.png", "oracle_roi", images["002.png"][2]),
        ("002.png", "carried_from_000", carried),
        ("003.png", "oracle_roi", images["003.png"][2]),
        ("003.png", "carried_from_000", carried),
    ]
    for name, mode, roi in jobs:
        rgb, gold, _ = images[name]
        masks, scores, elapsed = _predict(predictor, rgb, roi)
        candidates = []
        best_i = 0
        best_f1 = -1.0
        for i, (mask, score) in enumerate(zip(masks, scores)):
            m = _metrics(mask, gold)
            m["score"] = score
            m["index"] = i
            candidates.append(m)
            if float(m["boundary_f1"]) > best_f1:
                best_f1 = float(m["boundary_f1"])
                best_i = i
        best = masks[best_i]
        overlay_name = f"{Path(name).stem}-{mode}.png"
        _overlay(rgb, best, gold, roi).save(overlays / overlay_name)
        cases.append(
            {
                "image": name,
                "mode": mode,
                "roi": list(roi),
                "inference_ms": elapsed,
                "best_index": best_i,
                "candidates": candidates,
                "best_iou": candidates[best_i]["iou"],
                "best_boundary_f1": candidates[best_i]["boundary_f1"],
                "overlay": f"overlays/{overlay_name}",
            }
        )

    return {
        "schema_version": 1,
        "claim_scope": {
            "observational_local_eval": True,
            "quality_gate": False,
            "domain_validation": False,
            "prefer_real_sidecar": False,
        },
        "backend": "official MobileSAM vit_t CPU SamPredictor",
        "checkpoint_sha256": _sha256(checkpoint),
        "source": str(source),
        "dataset": str(capsule / "test" / "scratch"),
        "pad_px": PAD_PX,
        "legend": "green=pred∩gold  red=false positive  blue=missed gold  yellow=ROI",
        "cases": cases,
    }


def _html(report: dict[str, Any]) -> str:
    rows = []
    for case in report["cases"]:
        by_score = max(case["candidates"], key=lambda item: float(item["score"]))
        by_f1 = max(case["candidates"], key=lambda item: float(item["boundary_f1"]))
        rows.append(
            "<tr>"
            f"<td>{case['image']}<br><code>{case['mode']}</code></td>"
            f"<td>#{by_score['index']} score {by_score['score']:.3f}"
            f"<br>IoU {by_score['iou']:.3f} F1 {by_score['boundary_f1']:.3f}</td>"
            f"<td>#{by_f1['index']} F1 {by_f1['boundary_f1']:.3f}"
            f"<br>IoU {by_f1['iou']:.3f}</td>"
            f"<td>{case['inference_ms']:.0f} ms</td>"
            f"<td><img src='{case['overlay']}' width='640' alt='overlay'></td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<title>MobileSAM capsule scratch (observational)</title>
<style>
body {{ font-family: Segoe UI, sans-serif; background:#111; color:#eee; margin:24px; }}
table {{ border-collapse: collapse; width:100%; }}
td, th {{ border:1px solid #333; padding:8px; vertical-align:top; }}
img {{ max-width:100%; background:#000; }}
.note {{ color:#bbb; max-width:980px; line-height:1.45; }}
.bad {{ color:#ff8a80; }}
</style></head><body>
<h1>MobileSAM CPU on MVTec capsule scratch</h1>
<p class="note">Local observational eval only. Not a domain gate or release signoff.
Overlay uses the <b>best boundary F1</b> candidate (optimistic).
GUI default ranking uses SAM score, which is usually a larger blob.
Green = overlap, red = extra, blue = missed scratch, yellow = ROI.
<code>oracle_roi</code> = that image gold box + {report['pad_px']}px.
<code>carried_from_000</code> = Track A reuse of 000's ROI.</p>
<p class="bad">Desktop <code>--prefer-real</code> does not load this checkpoint today
(<code>MobileSamTorchCpu.from_manifest</code> is missing). This report used official
<code>SamPredictor</code> directly.</p>
<table>
<tr><th>Case</th><th>If GUI picks max SAM score</th><th>Best F1 among 3</th><th>Time</th><th>Overlay (best F1)</th></tr>
{''.join(rows)}
</table>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("playwright-report/mobilesam-capsule-scratch"))
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
                    "iou": round(c["best_iou"], 3),
                    "f1": round(c["best_boundary_f1"], 3),
                    "ms": round(c["inference_ms"], 1),
                }
                for c in report["cases"]
            ],
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
