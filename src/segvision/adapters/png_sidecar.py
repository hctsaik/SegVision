"""Pair-consistent PNG + JSON sidecar persistence adapter."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator
from PIL import Image

from segvision.core.errors import InvalidMask, PersistenceError
from segvision.core.types import CommitResult, OutcomeKind, ReviewResult


class PersistenceFault(PersistenceError):
    pass


@dataclass(frozen=True, slots=True)
class PersistedPair:
    sidecar_path: Path
    mask_path: Path
    sidecar: dict[str, Any]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def _storage_key(key: str) -> str:
    """Return a bounded flat filename key while retaining the original image id in metadata."""
    if not isinstance(key, str) or not key:
        raise PersistenceError("persistence key must be a non-empty string")
    if len(key) <= 80 and all(char.isascii() and (char.isalnum() or char in "-_") for char in key):
        return key
    label = "".join(
        char if char.isascii() and (char.isalnum() or char in "-_") else "_" for char in key
    ).strip("_")[:48]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"{label or 'image'}-{digest}"


class AcceptedStore:
    """Writes accepted pairs with sidecar-last publication semantics."""

    def __init__(
        self,
        root: str | Path,
        *,
        review_root: str | Path | None = None,
        fault: Callable[[str], None] | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.review_root = Path(review_root) if review_root else self.root / "review"
        self.review_root.mkdir(parents=True, exist_ok=True)
        self.fault = fault

    def _stage(self, stage: str) -> None:
        if self.fault:
            self.fault(stage)

    def _next_mask_name(self, key: str) -> str:
        versions: list[int] = []
        for path in self.root.glob(f"{key}.v*.png"):
            try:
                versions.append(int(path.stem.rsplit(".v", 1)[1]))
            except (IndexError, ValueError):
                continue
        return f"{key}.v{max(versions, default=0) + 1}.png"

    def _build_sidecar(
        self, result: CommitResult, filename: str, mask_hash: str, actor: str
    ) -> dict[str, Any]:
        if actor not in {"interactive_user", "scripted_test"}:
            raise PersistenceError("invalid acceptance actor")
        p = result.provenance if isinstance(result.provenance, dict) else dict(result.provenance)
        geometry = p.get("geometry", {})
        candidate = p.get("candidate", {})
        prov = candidate.get("provenance", {}) if isinstance(candidate, dict) else {}
        source = (
            candidate.get("source", "manual_edit") if isinstance(candidate, dict) else "manual_edit"
        )
        model = prov.get("model")
        if model:
            generator = {
                "kind": "model",
                "backend": model.get("backend_name", "unknown"),
                "model_version": model.get("model_version", "unknown"),
                "checkpoint_sha256": model.get("checkpoint_sha256", "0" * 64),
                "runtime_version": model.get("runtime_version", "unknown"),
                "preprocessing_version": model.get("preprocessing_version", "unknown"),
            }
        elif prov.get("recipe_id"):
            generator = {
                "kind": "cv_recipe",
                "recipe_id": prov["recipe_id"],
                "recipe_sha256": prov.get("recipe_hash", "0" * 64),
            }
        else:
            generator = {"kind": "manual"}
        source_sha = p.get("source_sha256", "0" * 64)
        h, w = result.full_image_mask.shape
        prompt_history = p.get("prompt_points")
        if not isinstance(prompt_history, list):
            prompt_history = candidate.get("prompt_points", [])
        if not isinstance(prompt_history, list):
            prompt_history = []
        return {
            "schema_version": 2,
            "status": "accepted",
            "training_eligible": True,
            "acceptance_actor": actor,
            "image": {
                "image_id": result.image_id,
                "source_sha256": source_sha,
                "height": h,
                "width": w,
            },
            "mask": {
                "filename": filename,
                "sha256": mask_hash,
                "height": h,
                "width": w,
                "dtype": "uint8",
                "values": [0, 255],
            },
            "geometry": {
                "user_roi_full": geometry.get("user_roi_full", [0, 0, w, h]),
                "crop_rect_full": geometry.get("crop_rect_full", [0, 0, w, h]),
                "padding_fraction": 0.1,
                "image_boundary_truncated": any(
                    w.code == "IMAGE_BOUNDARY_TRUNCATED" for w in result.warnings
                ),
            },
            "annotation_policy": {
                "policy_id": result.policy_id,
                "sha256": p.get("policy_sha256", "0" * 64),
            },
            "class_id": result.class_id,
            "revision": result.revision,
            "selected_candidate": {
                "candidate_id": result.candidate_id,
                "source": source,
                "generator": generator,
                "parent_candidate_id": prov.get("parent_candidate_id"),
            },
            "ancestry": [
                *(
                    p.get("ancestry", [])
                    if isinstance(p.get("ancestry", []), list)
                    else []
                ),
                *(
                    []
                    if p.get("ancestry")
                    else [
                        {
                            "candidate_id": result.candidate_id,
                            "source": source,
                            "parent_candidate_id": prov.get("parent_candidate_id"),
                        }
                    ]
                ),
            ],
            "prompts": [
                {
                    **(
                        {"point_id": q["point_id"]}
                        if isinstance(q, dict) and isinstance(q.get("point_id"), str)
                        else {}
                    ),
                    "sequence": i + 1,
                    "kind": "point",
                    "x": q.get("x", 0),
                    "y": q.get("y", 0),
                    "label": "foreground" if q.get("label", 1) else "background",
                }
                for i, q in enumerate(prompt_history)
            ],
            "operations": p.get("operations", []),
            "region_workflow": {
                "pass_index": int(p.get("pass_index", 0)),
                "frozen_regions": (
                    p.get("frozen_regions", [])
                    if isinstance(p.get("frozen_regions", []), list)
                    else []
                ),
            },
            "warnings": sorted({w.code for w in result.warnings}),
            "acknowledgements": sorted(set(result.acknowledged_warning_codes)),
            "timing": {
                "first_roi_locked_ns": int(p.get("first_roi_locked_ns", 0)),
                "first_valid_accept_time_ms": float(p.get("first_valid_accept_time_ms", 0)),
                "annotation_time_ms": float(p.get("annotation_time_ms", 0)),
                "decision_time_ms": float(p.get("decision_time_ms", 0)),
                "within_30_accept": bool(p.get("within_30_accept", False)),
                "save_latency_ms": float(p.get("save_latency_ms", 0)),
                "had_timeout": bool(p.get("had_timeout", False)),
            },
            "runtime": p.get(
                "runtime",
                {
                    "os": "unknown",
                    "cpu": "unknown",
                    "python": "3.11",
                    "dependency_lock_sha256": "0" * 64,
                },
            ),
            "published_at": _now(),
        }

    def save(
        self,
        result: CommitResult,
        *,
        actor: str = "interactive_user",
        key: str | None = None,
        overwrite: bool = False,
    ) -> PersistedPair:
        if result.outcome != OutcomeKind.ACCEPTED:
            raise PersistenceError("only accepted CommitResult may be saved")
        mask = np.asarray(result.full_image_mask)
        if mask.ndim != 2 or mask.dtype != np.bool_ or not mask.any():
            raise InvalidMask("accepted mask must be non-empty 2-D bool")
        key = _storage_key(key or result.image_id)
        # Create and validate temporary files first.  The final sidecar is the
        # only reader-visible commit marker.
        filename = self._next_mask_name(key)
        final_mask, final_sidecar = self.root / filename, self.root / f"{key}.json"
        fd, tmp_mask_name = tempfile.mkstemp(prefix=f".{key}.", suffix=".png", dir=self.root)
        os.close(fd)
        fd, tmp_side_name = tempfile.mkstemp(prefix=f".{key}.", suffix=".json", dir=self.root)
        os.close(fd)
        tmp_mask, tmp_side = Path(tmp_mask_name), Path(tmp_side_name)
        try:
            self._stage("png_write")
            Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(tmp_mask, format="PNG")
            self._stage("png_flush")
            with tmp_mask.open("r+b") as f:
                os.fsync(f.fileno())
            self._stage("png_close")
            mh = _sha(tmp_mask)
            side = self._build_sidecar(result, filename, mh, actor)
            self._stage("sidecar_write")
            tmp_side.write_text(json.dumps(side, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            self._stage("sidecar_flush")
            with tmp_side.open("r+b") as f:
                os.fsync(f.fileno())
            self._stage("sidecar_close")
            self._stage("validation")
            self._validate_sidecar(side, tmp_mask)
            self._stage("png_publish")
            os.replace(tmp_mask, final_mask)
            self._stage("sidecar_publish")
            self._stage("atomic_sidecar_pointer")
            # Never overwrite the previous referenced PNG; replacing the
            # pointer sidecar is the commit marker.
            os.replace(tmp_side, final_sidecar)
            return PersistedPair(final_sidecar, final_mask, side)
        except Exception as exc:
            for p in (tmp_mask, tmp_side):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
            if isinstance(exc, PersistenceError):
                raise
            raise PersistenceError(str(exc)) from exc

    def _validate_sidecar(self, side: dict[str, Any], mask_path: Path) -> None:
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "openspec/changes/build-segvision-v1/acceptance/accepted-sidecar.schema.json"
        )
        if schema_path.exists():
            errors = sorted(
                Draft202012Validator(
                    json.loads(schema_path.read_text(encoding="utf-8"))
                ).iter_errors(side),
                key=lambda e: list(e.path),
            )
            if errors:
                raise PersistenceError(f"sidecar schema: {errors[0].message}")
        if _sha(mask_path) != side["mask"]["sha256"]:
            raise PersistenceError("mask hash mismatch")

    def load(self) -> list[PersistedPair]:
        result: list[PersistedPair] = []
        for side_path in sorted(self.root.glob("*.json")):
            try:
                side = json.loads(side_path.read_text(encoding="utf-8"))
                if side.get("status") != "accepted" or side.get("training_eligible") is not True:
                    continue
                mask_path = side_path.parent / side["mask"]["filename"]
                if not mask_path.exists() or _sha(mask_path) != side["mask"]["sha256"]:
                    continue
                self._validate_sidecar(side, mask_path)
                with Image.open(mask_path) as image:
                    arr = np.asarray(image.convert("L"))
                if arr.shape != (side["mask"]["height"], side["mask"]["width"]):
                    continue
                if not set(np.unique(arr).tolist()) <= {0, 255}:
                    continue
                result.append(PersistedPair(side_path, mask_path, side))
            except (OSError, ValueError, KeyError, json.JSONDecodeError, PersistenceError):
                continue
        return result

    def load_mask(self, pair: PersistedPair) -> np.ndarray:
        with Image.open(pair.mask_path) as image:
            arr = np.asarray(image.convert("L"))
        return arr == 255


class ReviewStore(AcceptedStore):
    """Review metadata is written under a namespace excluded by AcceptedStore.load."""

    def save_review(
        self, result: ReviewResult, *, actor: str = "interactive_user", key: str | None = None
    ) -> Path:
        if actor not in {"interactive_user", "scripted_test"}:
            raise PersistenceError("invalid review actor")
        key = _storage_key(key or result.image_id)
        side = {
            "schema_version": 1,
            "status": "needs_review",
            "training_eligible": False,
            "actor": actor,
            "image_id": result.image_id,
            "source_sha256": result.provenance.get("source_sha256", "0" * 64),
            "user_roi_full": result.provenance.get("geometry", {}).get(
                "user_roi_full", [0, 0, 1, 1]
            ),
            "crop_rect_full": result.provenance.get("geometry", {}).get(
                "crop_rect_full", [0, 0, 1, 1]
            ),
            "revision": result.revision,
            "reason": result.reason,
            "annotation_policy": {"policy_id": result.policy_id, "sha256": "0" * 64},
            "timing": {
                "decision_time_ms": float(result.provenance.get("decision_time_ms", 0.0)),
                "first_valid_accept_time_ms": result.provenance.get("first_valid_accept_time_ms"),
                "annotation_time_ms": result.provenance.get("annotation_time_ms"),
                "had_timeout": False,
            },
            "draft": None,
            "published_at": _now(),
        }
        draft_tmp: Path | None = None
        if result.draft_mask is not None:
            draft = np.asarray(result.draft_mask)
            if draft.ndim != 2 or draft.dtype != np.bool_ or not draft.any():
                raise InvalidMask("review draft must be a non-empty 2-D bool mask")
            geometry = result.provenance.get("geometry", {})
            crop_rect = geometry.get("crop_rect_full") if isinstance(geometry, dict) else None
            if isinstance(crop_rect, (list, tuple)) and len(crop_rect) == 4:
                expected_shape = (int(crop_rect[3] - crop_rect[1]), int(crop_rect[2] - crop_rect[0]))
                if draft.shape != expected_shape:
                    raise InvalidMask("review draft shape must match crop_rect_full")
            versions = []
            for path in self.review_root.glob(f"{key}.v*.png"):
                try:
                    versions.append(int(path.stem.rsplit(".v", 1)[1]))
                except (IndexError, ValueError):
                    continue
            filename = f"{key}.v{max(versions, default=0) + 1}.png"
            fd, tmp_name = tempfile.mkstemp(prefix=f".{key}.", suffix=".png", dir=self.review_root)
            os.close(fd)
            draft_tmp = Path(tmp_name)
            Image.fromarray((draft.astype(np.uint8) * 255), mode="L").save(draft_tmp, format="PNG")
            with draft_tmp.open("r+b") as f:
                os.fsync(f.fileno())
            side["draft"] = {
                "filename": filename,
                "sha256": _sha(draft_tmp),
                "height": int(draft.shape[0]),
                "width": int(draft.shape[1]),
                "ancestry": result.provenance.get("ancestry", []),
                "operations": result.provenance.get("operations", []),
            }
        target = self.review_root / f"{key}.json"
        tmp = target.with_name(f".{target.name}.tmp")
        try:
            schema_path = (
                Path(__file__).resolve().parents[3]
                / "openspec/changes/build-segvision-v1/acceptance/review-sidecar.schema.json"
            )
            if schema_path.exists():
                errors = sorted(
                    Draft202012Validator(
                        json.loads(schema_path.read_text(encoding="utf-8"))
                    ).iter_errors(side),
                    key=lambda e: list(e.path),
                )
                if errors:
                    raise PersistenceError(f"review sidecar schema: {errors[0].message}")
            if draft_tmp is not None:
                self._stage("review_draft_publish")
                os.replace(draft_tmp, self.review_root / side["draft"]["filename"])
            tmp.write_text(json.dumps(side, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            with tmp.open("r+b") as f:
                os.fsync(f.fileno())
            self._stage("review_publish")
            os.replace(tmp, target)
            return target
        except Exception as exc:
            if draft_tmp is not None:
                draft_tmp.unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)
            if isinstance(exc, PersistenceError):
                raise
            raise PersistenceError(str(exc)) from exc
