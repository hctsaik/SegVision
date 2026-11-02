"""Crash-safe, isolated editable draft persistence.

Drafts are deliberately separate from :mod:`png_sidecar` Accepted/Review
stores.  The sidecar is published last so an interrupted write can never
replace the previous valid checkpoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from segvision.application.config import DRAFT_RETENTION, DRAFT_SCHEMA_VERSION
from segvision.core.errors import PersistenceError


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _mask_bytes(mask: np.ndarray) -> bytes:
    array = np.asarray(mask, dtype=np.bool_)
    if array.ndim != 2:
        raise PersistenceError("draft mask must be a 2-D array")
    from io import BytesIO

    buffer = BytesIO()
    Image.fromarray(array.astype(np.uint8) * 255, mode="L").save(buffer, format="PNG")
    return buffer.getvalue()


class DraftStore:
    """Persist and validate one editable draft namespace."""

    def __init__(self, root: str | Path, *, retention: int = DRAFT_RETENTION) -> None:
        self.root = Path(root).resolve() / "drafts"
        self.root.mkdir(parents=True, exist_ok=True)
        self.retention = max(1, int(retention))

    @staticmethod
    def _safe_key(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]

    def _item_dir(self, dataset_id: str, item_id: str) -> Path:
        path = self.root / self._safe_key(dataset_id) / self._safe_key(item_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(
        self,
        *,
        dataset_id: str,
        item_id: str,
        source_sha256: str,
        payload: dict[str, Any],
        mask: np.ndarray,
    ) -> dict[str, Any]:
        mask_bytes = _mask_bytes(mask)
        item_dir = self._item_dir(dataset_id, item_id)
        nonce = uuid.uuid4().hex
        mask_tmp = item_dir / f".{nonce}.mask.tmp"
        sidecar_tmp = item_dir / f".{nonce}.json.tmp"
        mask_name = f"{nonce}.mask.png"
        mask_path = item_dir / mask_name
        sidecar_path = item_dir / f"{nonce}.json"
        record = {
            "schema_version": DRAFT_SCHEMA_VERSION,
            "draft_id": nonce,
            "dataset_id": dataset_id,
            "item_id": item_id,
            "source_sha256": source_sha256,
            "mask": {
                "path": mask_name,
                "sha256": _sha256_bytes(mask_bytes),
                "height": int(np.asarray(mask).shape[0]),
                "width": int(np.asarray(mask).shape[1]),
            },
            **dict(payload),
        }
        try:
            mask_tmp.write_bytes(mask_bytes)
            with mask_tmp.open("r+b") as stream:
                os.fsync(stream.fileno())
            os.replace(mask_tmp, mask_path)
            sidecar_tmp.write_text(
                json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            with sidecar_tmp.open("r+b") as stream:
                os.fsync(stream.fileno())
            # The JSON commit marker is intentionally last.
            os.replace(sidecar_tmp, sidecar_path)
        except OSError as exc:
            for path in (mask_tmp, sidecar_tmp):
                path.unlink(missing_ok=True)
            raise PersistenceError(f"draft publication failed: {exc}") from exc
        self._compact(item_dir, keep=nonce)
        return record

    def _compact(self, item_dir: Path, *, keep: str) -> None:
        sidecars = sorted(item_dir.glob("*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
        for sidecar in sidecars[self.retention :]:
            try:
                record = json.loads(sidecar.read_text(encoding="utf-8"))
                mask_name = record.get("mask", {}).get("path")
                sidecar.unlink(missing_ok=True)
                if isinstance(mask_name, str):
                    (item_dir / mask_name).unlink(missing_ok=True)
            except (OSError, ValueError, TypeError):
                # Corrupt entries are retained for quarantine inspection.
                continue

    def _validate(self, sidecar: Path, *, source_sha256: str | None = None) -> dict[str, Any]:
        try:
            record = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PersistenceError("draft sidecar is invalid JSON") from exc
        if record.get("schema_version") != DRAFT_SCHEMA_VERSION:
            raise PersistenceError("draft schema version is unsupported")
        if source_sha256 is not None and record.get("source_sha256") != source_sha256:
            raise PersistenceError("draft source image fingerprint changed")
        mask = record.get("mask")
        if not isinstance(mask, dict) or not isinstance(mask.get("path"), str):
            raise PersistenceError("draft mask metadata is missing")
        path = sidecar.parent / mask["path"]
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise PersistenceError("draft mask payload is missing") from exc
        if _sha256_bytes(data) != mask.get("sha256"):
            raise PersistenceError("draft mask hash mismatch")
        return record

    def inspect(self, *, dataset_id: str, item_id: str) -> list[dict[str, Any]]:
        item_dir = self._item_dir(dataset_id, item_id)
        records: list[dict[str, Any]] = []
        for sidecar in sorted(item_dir.glob("*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True):
            try:
                record = self._validate(sidecar)
                records.append({"draft_id": record["draft_id"], "valid": True, "revision": record.get("revision")})
            except PersistenceError as exc:
                records.append({"draft_id": sidecar.stem, "valid": False, "error": str(exc)})
        return records

    def load(self, *, dataset_id: str, item_id: str, draft_id: str | None = None, source_sha256: str | None = None) -> dict[str, Any]:
        item_dir = self._item_dir(dataset_id, item_id)
        candidates = [item_dir / f"{draft_id}.json"] if draft_id else sorted(
            item_dir.glob("*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True
        )
        first_error: PersistenceError | None = None
        for sidecar in candidates:
            if not sidecar.is_file():
                continue
            try:
                return self._validate(sidecar, source_sha256=source_sha256)
            except PersistenceError as exc:
                first_error = first_error or exc
                if draft_id:
                    raise
        if first_error is not None and source_sha256 is not None:
            raise first_error
        raise PersistenceError("no valid resumable draft found")

    def load_with_mask(
        self,
        *,
        dataset_id: str,
        item_id: str,
        draft_id: str | None = None,
        source_sha256: str | None = None,
    ) -> tuple[dict[str, Any], np.ndarray]:
        """Load a verified sidecar and its mask payload as one pair.

        The sidecar is validated before the mask is decoded; callers can
        therefore never restore a mask whose hash or source fingerprint does
        not match the commit marker.
        """
        record = self.load(
            dataset_id=dataset_id,
            item_id=item_id,
            draft_id=draft_id,
            source_sha256=source_sha256,
        )
        item_dir = self._item_dir(dataset_id, item_id)
        path = item_dir / str(record["mask"]["path"])
        try:
            with Image.open(path) as image:
                mask = np.asarray(image.convert("L"), dtype=np.uint8) > 127
        except (OSError, ValueError) as exc:
            raise PersistenceError("draft mask payload is unreadable") from exc
        expected_shape = (int(record["mask"]["height"]), int(record["mask"]["width"]))
        if mask.shape != expected_shape:
            raise PersistenceError("draft mask dimensions do not match metadata")
        return record, np.ascontiguousarray(mask, dtype=np.bool_)

    def discard(self, *, dataset_id: str, item_id: str, draft_id: str | None = None) -> int:
        item_dir = self._item_dir(dataset_id, item_id)
        removed = 0
        sidecars = [item_dir / f"{draft_id}.json"] if draft_id else list(item_dir.glob("*.json"))
        for sidecar in sidecars:
            if not sidecar.is_file():
                continue
            try:
                record = json.loads(sidecar.read_text(encoding="utf-8"))
                mask_name = record.get("mask", {}).get("path")
            except (OSError, ValueError):
                mask_name = None
            sidecar.unlink(missing_ok=True)
            if isinstance(mask_name, str):
                (item_dir / mask_name).unlink(missing_ok=True)
            removed += 1
        return removed
