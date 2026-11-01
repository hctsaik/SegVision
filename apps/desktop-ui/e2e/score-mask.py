"""Score a predicted mask against MVTec gold and write an RGB overlay."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load_bool(path: Path) -> np.ndarray:
    arr = np.asarray(Image.open(path).convert("L"))
    return arr > 0


def place_crop(pred: np.ndarray, gold: np.ndarray, crop: list[int] | None) -> np.ndarray:
    if crop is None or pred.shape == gold.shape:
        h = min(pred.shape[0], gold.shape[0])
        w = min(pred.shape[1], gold.shape[1])
        full = np.zeros(gold.shape, dtype=bool)
        full[:h, :w] = pred[:h, :w]
        return full
    x0, y0, x1, y1 = crop
    full = np.zeros(gold.shape, dtype=bool)
    ph, pw = pred.shape
    y1 = min(gold.shape[0], max(y1, y0 + ph))
    x1 = min(gold.shape[1], max(x1, x0 + pw))
    hh = min(ph, gold.shape[0] - y0)
    ww = min(pw, gold.shape[1] - x0)
    if hh > 0 and ww > 0:
        full[y0 : y0 + hh, x0 : x0 + ww] = pred[:hh, :ww]
    return full


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: score-mask.py PRED GOLD OVERLAY [RGB [X0 Y0 X1 Y1]]", file=sys.stderr)
        return 2
    pred_path = Path(sys.argv[1])
    gold_path = Path(sys.argv[2])
    overlay_path = Path(sys.argv[3])
    rgb_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    crop = [int(v) for v in sys.argv[5:9]] if len(sys.argv) >= 9 else None
    pred = load_bool(pred_path)
    gold = load_bool(gold_path)
    pred = place_crop(pred, gold, crop)
    tp = int(np.logical_and(pred, gold).sum())
    fp = int(np.logical_and(pred, np.logical_not(gold)).sum())
    fn = int(np.logical_and(np.logical_not(pred), gold).sum())
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    h, w = gold.shape
    if rgb_path and rgb_path.is_file():
        rgb = np.asarray(Image.open(rgb_path).convert("RGB"))[:h, :w]
    else:
        rgb = np.stack([np.full((h, w), 32, np.uint8)] * 3, axis=-1)
    out = rgb.copy()
    out[np.logical_and(gold, np.logical_not(pred))] = (40, 90, 220)
    out[np.logical_and(pred, np.logical_not(gold))] = (220, 50, 50)
    out[np.logical_and(pred, gold)] = (40, 180, 80)
    Image.fromarray(out).save(overlay_path)
    sys.stdout.write(
        json.dumps(
            {
                "iou": round(iou, 4),
                "f1": round(f1, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "pred_area": int(pred.sum()),
                "gold_area": int(gold.sum()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
