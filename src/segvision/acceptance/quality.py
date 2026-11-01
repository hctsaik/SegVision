"""Boundary and workflow quality metrics for optional domain validation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np


def boundary_pixels(mask: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask, dtype=np.bool_)
    if arr.ndim != 2:
        raise ValueError("mask must be two-dimensional")
    padded = np.pad(arr, 1, constant_values=False)
    boundary = arr & (
        ~padded[:-2, 1:-1]
        | ~padded[2:, 1:-1]
        | ~padded[1:-1, :-2]
        | ~padded[1:-1, 2:]
        | ~padded[:-2, :-2]
        | ~padded[:-2, 2:]
        | ~padded[2:, :-2]
        | ~padded[2:, 2:]
    )
    return boundary


def symmetric_boundary_f1(
    predicted: np.ndarray, gold: np.ndarray, tolerance_px: float = 2.0
) -> float:
    pred, truth = np.asarray(predicted, dtype=np.bool_), np.asarray(gold, dtype=np.bool_)
    if pred.shape != truth.shape:
        raise ValueError("mask shape mismatch")
    pb, gb = boundary_pixels(pred), boundary_pixels(truth)
    if not pb.any() and not gb.any():
        return 1.0
    if not pb.any() or not gb.any():
        return 0.0
    py, px = np.where(pb)
    gy, gx = np.where(gb)
    p = np.stack([py, px], axis=1)
    g = np.stack([gy, gx], axis=1)
    d = np.sqrt(((p[:, None, :] - g[None, :, :]) ** 2).sum(axis=2))
    precision = float((d.min(axis=1) <= tolerance_px).mean())
    recall = float((d.min(axis=0) <= tolerance_px).mean())
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def evaluate_domain_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    total = len(rows)
    accepted = sum(r.get("outcome") == "accepted" for r in rows)
    review = sum(r.get("outcome") == "needs_review" for r in rows)
    timeout = sum(bool(r.get("timeout")) for r in rows)
    return {
        "total_presented": total,
        "accepted_count": accepted,
        "needs_review_count": review,
        "timeout_count": timeout,
        "timeout_rate": timeout / total if total else 0.0,
        "accepted_under_30_count": sum(
            r.get("outcome") == "accepted" and r.get("annotation_time_ms", 1e99) < 30000
            for r in rows
        ),
        "accepted_conditional": [
            r.get("annotation_time_ms") for r in rows if r.get("outcome") == "accepted"
        ],
    }
