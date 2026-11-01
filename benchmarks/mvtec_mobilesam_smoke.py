"""Run a small, explicit CPU MobileSAM smoke on MVTec AD 2 regular scenes.

This supplementary benchmark imports the pinned official MobileSAM source from
an external, user-authorized evaluation directory.  It is intentionally not a
shipping adapter and its quality numbers are observational only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from segvision.acceptance.quality import symmetric_boundary_f1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(manifest: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["category"] in {"wallplugs", "can", "rice"} and row["gold_subset"]:
            rows.append(row)
        if len(rows) >= limit:
            break
    if not rows:
        raise ValueError("manifest has no Tier 1 gold rows")
    return rows


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int, int, int]:
    ys, xs = np.where(mask)
    if not len(xs):
        raise ValueError("gold mask is empty")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    mx = max(2, int(np.ceil((x1 - x0) * 0.10)))
    my = max(2, int(np.ceil((y1 - y0) * 0.10)))
    return x0, y0, x1, y1, mx, my


def run(*, source: Path, checkpoint: Path, root: Path, manifest: Path, limit: int) -> dict[str, Any]:
    if not source.is_dir() or not checkpoint.is_file():
        raise FileNotFoundError("official MobileSAM source/checkpoint is unavailable")
    sys.path.insert(0, str(source))
    import torch
    from mobile_sam import SamPredictor, sam_model_registry

    torch.set_num_threads(1)
    model = sam_model_registry["vit_t"](checkpoint=str(checkpoint))
    model.eval()
    predictor = SamPredictor(model)
    results: list[dict[str, Any]] = []
    for row in _load_rows(manifest, limit):
        image_path = root / row["image"]["path"]
        mask_path = root / row["mask"]["path"]
        with Image.open(image_path) as image_file:
            image = np.asarray(image_file.convert("RGB"), dtype=np.uint8).copy()
        with Image.open(mask_path) as mask_file:
            gold = np.asarray(mask_file.convert("L"), dtype=np.uint8) == 255
        x0, y0, x1, y1, mx, my = _bbox(gold)
        rx0, ry0 = max(0, x0 - mx), max(0, y0 - my)
        rx1, ry1 = min(image.shape[1], x1 + mx), min(image.shape[0], y1 + my)
        crop = image[ry0:ry1, rx0:rx1]
        box = np.asarray([x0 - rx0, y0 - ry0, x1 - rx0, y1 - ry0], dtype=np.float32)
        started = time.perf_counter()
        predictor.set_image(crop)
        masks, scores, _ = predictor.predict(box=box, multimask_output=True, return_logits=False)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        candidates: list[dict[str, Any]] = []
        for mask, score in zip(masks, scores):
            full = np.zeros_like(gold)
            full[ry0:ry1, rx0:rx1] = mask
            intersection = np.logical_and(full, gold).sum()
            union = np.logical_or(full, gold).sum()
            candidates.append(
                {
                    "score": float(score),
                    "iou": float(intersection / union) if union else 1.0,
                    "boundary_f1": symmetric_boundary_f1(full, gold),
                    "mask_pixels": int(full.sum()),
                }
            )
        results.append(
            {
                "record_id": row["record_id"],
                "category": row["category"],
                "image_shape": [int(image.shape[0]), int(image.shape[1])],
                "roi": [rx0, ry0, rx1, ry1],
                "candidate_count": len(candidates),
                "inference_ms": elapsed_ms,
                "candidates": candidates,
                "best_iou": max(candidate["iou"] for candidate in candidates),
                "best_boundary_f1": max(candidate["boundary_f1"] for candidate in candidates),
            }
        )
    return {
        "schema_version": 1,
        "dataset_manifest_sha256": _sha256(manifest),
        "checkpoint_sha256": _sha256(checkpoint),
        "backend": "MobileSAM official vit_t CPU",
        "source": str(source),
        "claim_scope": {
            "functional_smoke": True,
            "quality_gate": False,
            "domain_validation": False,
            "redistribution_approval": False,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run(
        source=args.source.resolve(),
        checkpoint=args.checkpoint.resolve(),
        root=args.root.resolve(),
        manifest=args.manifest.resolve(),
        limit=args.limit,
    )
    report["run_id"] = args.run_id
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "records": len(report["results"]),
                "candidate_counts": [row["candidate_count"] for row in report["results"]],
                "best_iou": [row["best_iou"] for row in report["results"]],
                "best_boundary_f1": [row["best_boundary_f1"] for row in report["results"]],
                "inference_ms": [row["inference_ms"] for row in report["results"]],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
