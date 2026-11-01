"""Run a data-driven SegVision core E2E pass over the MVTec AD 2 manifest.

The dataset is intentionally kept outside the repository.  This harness uses
the published gold mask as a deterministic replay backend so that the real
image/mask files exercise ROI geometry, candidate validation, Accept, full
image reconstruction, and boundary metrics without making a model-quality or
domain-validation claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from segvision.acceptance.quality import symmetric_boundary_f1
from segvision.core.api import SegVisionEngine
from segvision.core.types import BackendCapabilities, ModelIdentity, PromptBundle
from segvision.providers.base import EncodedState, RawMask

TIER_CATEGORIES: dict[str, tuple[str, ...]] = {
    "1": ("wallplugs", "can", "rice"),
    "2": ("vial", "fabric", "walnuts"),
    "3": ("sheet_metal", "fruit_jelly"),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _run_id() -> str:
    now = datetime.now(UTC)
    return f"sv-{now:%Y%m%dT%H%M%SZ}-a7ec0001"


def _safe_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"manifest path escapes dataset root: {relative}")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _load_mask(path: Path, expected_values: list[int]) -> np.ndarray:
    with Image.open(path) as image:
        if image.mode != "L":
            image = image.convert("L")
        array = np.asarray(image, dtype=np.uint8)
    values = sorted(int(value) for value in np.unique(array))
    if values != sorted(expected_values):
        raise ValueError(f"mask values {values} do not match {expected_values}: {path}")
    return array == 255


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        converted = image.convert("RGB")
        return np.asarray(converted, dtype=np.uint8).copy()


def _bbox_roi(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if not len(xs):
        raise ValueError("gold mask is empty")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    width, height = x1 - x0, y1 - y0
    margin_x = max(2, math.ceil(width * 0.10))
    margin_y = max(2, math.ceil(height * 0.10))
    return (max(0, x0 - margin_x), max(0, y0 - margin_y), x1 + margin_x, y1 + margin_y)


class GoldReplayBackend:
    """Deterministic backend that replays a record's gold crop mask."""

    def __init__(self, gold_mask: np.ndarray, crop_rect: tuple[int, int, int, int]) -> None:
        self._gold_mask = np.asarray(gold_mask, dtype=np.bool_)
        self._crop_rect = crop_rect
        self.ledger: list[dict[str, Any]] = []
        identity = ModelIdentity(
            "mvtec_gold_replay",
            "MVTec-AD2-gold-v1",
            _sha256_bytes(b"segvision-mvtec-gold-replay-v1"),
            "replay",
            "source-crop-v1",
        )
        self._capabilities = BackendCapabilities(model=identity)
        x0, y0, x1, y1 = crop_rect
        self._gold_crop = self._gold_mask[y0:y1, x0:x1].copy()

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def encode(
        self,
        crop_rgb: np.ndarray,
        *,
        session_id: str,
        revision: int,
        crop_fingerprint: str,
    ) -> EncodedState:
        if crop_rgb.shape[:2] != self._gold_crop.shape:
            raise ValueError("replay crop shape does not match gold crop")
        token = _sha256_bytes(crop_rgb.tobytes() + session_id.encode() + str(revision).encode())
        self.ledger.append({"op": "encode", "revision": revision, "token": token})
        return EncodedState(token, session_id, revision, crop_fingerprint, None)

    def decode(
        self, encoded: EncodedState, prompt: PromptBundle, *, multimask_count: int
    ) -> tuple[RawMask, ...]:
        self.ledger.append(
            {
                "op": "decode",
                "revision": encoded.revision,
                "multimask_count": multimask_count,
                "points": len(prompt.points_crop_xy),
            }
        )
        return (RawMask(self._gold_crop, 1.0, 1.0, 0, {"replay": True}),)

    def mask_prompt_from_binary(self, encoded: EncodedState, mask: np.ndarray) -> np.ndarray:
        array = np.asarray(mask, dtype=np.bool_)
        if array.shape != self._gold_crop.shape:
            raise ValueError("mask prompt shape mismatch")
        self.ledger.append({"op": "mask_prompt_from_binary", "revision": encoded.revision})
        return array.copy()

    def release(self, encoded: EncodedState) -> None:
        self.ledger.append({"op": "release", "revision": encoded.revision})


def _record_result(
    record: dict[str, Any],
    root: Path,
    *,
    sequence: int,
) -> dict[str, Any]:
    image_path = _safe_path(root, str(record["image"]["path"]))
    mask_path = _safe_path(root, str(record["mask"]["path"]))
    image_bytes = image_path.read_bytes()
    mask_bytes = mask_path.read_bytes()
    if _sha256_bytes(image_bytes).lower() != str(record["image"]["sha256"]).lower():
        raise ValueError(f"image hash mismatch: {record['record_id']}")
    if _sha256_bytes(mask_bytes).lower() != str(record["mask"]["sha256"]).lower():
        raise ValueError(f"mask hash mismatch: {record['record_id']}")
    image = _load_rgb(image_path)
    gold = _load_mask(mask_path, list(record["mask"]["values"]))
    if image.shape[:2] != gold.shape:
        raise ValueError(f"image/mask shape mismatch: {record['record_id']}")
    roi = _bbox_roi(gold)
    # _bbox_roi is clipped in the upper-left direction; clamp the other side
    # here so the public half-open ROI remains inside the source image.
    roi = (
        roi[0],
        roi[1],
        min(image.shape[1], roi[2]),
        min(image.shape[0], roi[3]),
    )
    # The backend receives the actual padded crop after the session context is
    # known, while the public session still owns all geometry decisions.
    from segvision.core.geometry import create_crop_context

    context = create_crop_context(image.shape[:2], roi)
    backend = GoldReplayBackend(gold, context.crop_rect_full)
    engine = SegVisionEngine(backend)
    started = time.perf_counter()
    session = engine.start(image, str(record["record_id"]), str(record["category"]), roi)
    proposal = session.propose()
    if len(proposal.candidates) != 1:
        raise AssertionError(f"expected one replay candidate, got {len(proposal.candidates)}")
    candidate = session.select(proposal.candidates[0].candidate_id)
    warnings = [warning.code for warning in candidate.warnings]
    commit = session.accept(acknowledge_warnings=warnings, acceptance_actor="scripted_test")
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    predicted = commit.full_image_mask
    exact = bool(np.array_equal(predicted, gold))
    boundary_f1 = symmetric_boundary_f1(predicted, gold)
    encode_calls = sum(item.get("op") == "encode" for item in backend.ledger)
    decode_calls = sum(item.get("op") == "decode" for item in backend.ledger)
    session.close()
    return {
        "sequence": sequence,
        "record_id": record["record_id"],
        "category": record["category"],
        "variant": record["variant"],
        "gold_subset": bool(record["gold_subset"]),
        "stratum": record["stratum"],
        "image_sha256": _sha256_bytes(image_bytes),
        "mask_sha256": _sha256_bytes(mask_bytes),
        "image_shape": [int(image.shape[0]), int(image.shape[1])],
        "roi": list(roi),
        "crop_rect_full": list(context.crop_rect_full),
        "candidate_count": len(proposal.candidates),
        "candidate_source": candidate.source.value,
        "encode_calls": encode_calls,
        "decode_calls": decode_calls,
        "warning_codes": warnings,
        "predicted_mask_sha256": _sha256_bytes(predicted.tobytes()),
        "gold_mask_pixels": int(gold.sum()),
        "predicted_mask_pixels": int(predicted.sum()),
        "exact_mask": exact,
        "boundary_f1": boundary_f1,
        "elapsed_ms": elapsed_ms,
        "event_count": len(session.events),
        "status": "passed" if exact and boundary_f1 == 1.0 else "failed",
    }


def load_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or "record_id" not in row:
                raise ValueError(f"invalid manifest row {line_number}")
            rows.append(row)
    if len({row["record_id"] for row in rows}) != len(rows):
        raise ValueError("manifest contains duplicate record IDs")
    return rows


def run(
    *,
    root: Path,
    manifest: Path,
    tier: str,
    gold_only: bool,
    limit: int | None,
    offset: int,
    run_id: str,
) -> dict[str, Any]:
    rows = load_manifest(manifest)
    categories = set(TIER_CATEGORIES[tier]) if tier != "all" else None
    selected = [
        row
        for row in rows
        if (categories is None or row["category"] in categories)
        and (not gold_only or bool(row["gold_subset"]))
    ]
    if offset < 0:
        raise ValueError("offset must be non-negative")
    selected = selected[offset:]
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        selected = selected[:limit]
    if not selected:
        raise ValueError("selection contains no manifest records")
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for sequence, row in enumerate(selected, 1):
        try:
            result = _record_result(row, root, sequence=sequence)
        except Exception as exc:  # noqa: BLE001 - retain every failed record
            result = {
                "sequence": sequence,
                "record_id": row.get("record_id"),
                "category": row.get("category"),
                "variant": row.get("variant"),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
            failures.append(result)
        records.append(result)
    passed = sum(row.get("status") == "passed" for row in records)
    boundary_values = [float(row["boundary_f1"]) for row in records if "boundary_f1" in row]
    elapsed_values = [float(row["elapsed_ms"]) for row in records if "elapsed_ms" in row]
    warning_counts = Counter(
        warning for row in records for warning in row.get("warning_codes", [])
    )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "dataset": {
            "dataset_id": "MVTec AD 2",
            "root": str(root),
            "manifest": str(manifest),
            "manifest_sha256": _sha256_file(manifest),
            "license": "CC BY-NC-SA 4.0",
            "commercial_use_authorized": False,
        },
        "selection": {
            "tier": tier,
            "categories": sorted(categories) if categories is not None else "all",
            "gold_only": gold_only,
            "offset": offset,
            "limit": limit,
        },
        "backend": {
            "kind": "deterministic_gold_replay",
            "model_quality_claim": False,
            "domain_validation_claim": False,
        },
        "summary": {
            "total_presented": len(records),
            "passed": passed,
            "failed": len(records) - passed,
            "exact_mask_count": sum(bool(row.get("exact_mask")) for row in records),
            "exact_mask_rate": sum(bool(row.get("exact_mask")) for row in records)
            / len(records),
            "boundary_f1_median": statistics.median(boundary_values) if boundary_values else None,
            "boundary_f1_min": min(boundary_values) if boundary_values else None,
            "elapsed_ms_median": statistics.median(elapsed_values) if elapsed_values else None,
            "elapsed_ms_p95": (
                float(np.percentile(np.asarray(elapsed_values), 95)) if elapsed_values else None
            ),
            "warning_counts": dict(sorted(warning_counts.items())),
            "category_counts": dict(sorted(Counter(row["category"] for row in records).items())),
            "gold_subset_count": sum(bool(row.get("gold_subset")) for row in records),
            "failures": failures,
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="extracted mvtec_ad_2 directory")
    parser.add_argument("--manifest", required=True, type=Path, help="JSONL dataset manifest")
    parser.add_argument("--tier", choices=("1", "2", "3", "all"), default="1")
    parser.add_argument("--gold-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output", required=True, type=Path, help="JSON report path")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest.resolve()
    if not root.is_dir():
        parser.error(f"dataset root is not a directory: {root}")
    if not manifest.is_file():
        parser.error(f"manifest is not a file: {manifest}")
    report = run(
        root=root,
        manifest=manifest,
        tier=args.tier,
        gold_only=args.gold_only,
        limit=args.limit,
        offset=args.offset,
        run_id=args.run_id or _run_id(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
