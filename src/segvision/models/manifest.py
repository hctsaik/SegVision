"""Fail-closed model/dependency manifest validation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from segvision.core.errors import ModelApprovalError, ModelArtifactError


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    name: str
    version: str
    source_url: str
    sha256: str
    license: str
    approved: bool = False
    local_path: str | None = None

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.name, self.version, self.source_url, self.sha256, self.license)
        ):
            raise ValueError("model artifact metadata must be non-empty strings")
        if re.fullmatch(r"[0-9a-fA-F]{64}", self.sha256) is None:
            raise ValueError("model artifact sha256 must be hexadecimal")
        if not isinstance(self.approved, bool):
            raise TypeError("artifact approval must be bool")


@dataclass(frozen=True, slots=True)
class ModelManifest:
    schema_version: int
    artifacts: tuple[ModelArtifact, ...]
    prohibited_sources: tuple[str, ...] = ("EdgeSAM", "SAM2", "SAM3", "HQ-SAM", "DINO", "VLM")


def validate_model_manifest(data: dict[str, Any], *, require_local: bool = False) -> ModelManifest:
    if not isinstance(data, dict):
        raise ModelApprovalError("model manifest must be an object")
    if data.get("schema_version") != 1:
        raise ModelApprovalError("unsupported model manifest schema")
    # The repository acceptance manifest uses ``entries`` and carries the
    # complete license/authority facts.  Convert it into the narrow runtime
    # representation after enforcing every release-time gate.
    items = data.get("artifacts")
    if items is None and "entries" in data:
        entries = data.get("entries")
        if not isinstance(entries, list) or len(entries) < 2:
            raise ModelApprovalError("manifest must include model code and model weights")
        items = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ModelApprovalError("manifest entry must be an object")
            kind = entry.get("artifact_kind")
            approval = entry.get("organizational_approval")
            included = entry.get("included_in_release") is True
            if kind in {"model_code", "model_weights"} and included:
                if entry.get("redistribution_status") not in {"allowed", "allowed_with_conditions"}:
                    raise ModelApprovalError(f"redistribution is not approved: {entry.get('artifact_id')}")
                if not isinstance(approval, dict) or approval.get("status") != "approved":
                    raise ModelApprovalError(f"organizational approval is pending: {entry.get('artifact_id')}")
                if not isinstance(entry.get("sha256"), str):
                    raise ModelArtifactError(f"release artifact has no checksum: {entry.get('artifact_id')}")
            source = str(entry.get("source_url", ""))
            if not re.match(r"^https?://", source):
                raise ModelApprovalError(f"artifact source must be an official URL: {entry.get('artifact_id')}")
            items.append(
                {
                    "name": entry.get("artifact_id", "unknown"),
                    "version": entry.get("source_revision", "unknown"),
                    "source_url": source,
                    "sha256": entry.get("sha256") or "0" * 64,
                    "license": entry.get("license_facts", {}).get("license_id", "UNKNOWN")
                    if isinstance(entry.get("license_facts"), dict)
                    else "UNKNOWN",
                    "approved": bool(
                        included
                        and isinstance(approval, dict)
                        and approval.get("status") == "approved"
                    ),
                }
            )
    if not isinstance(items, list) or not items:
        raise ModelApprovalError("manifest must list artifacts")
    artifacts: list[ModelArtifact] = []
    for item in items:
        required = {"name", "version", "source_url", "sha256", "license", "approved"}
        if not required <= set(item):
            raise ModelApprovalError(f"incomplete manifest entry: {item.get('name')}")
        if not isinstance(item["sha256"], str) or re.fullmatch(r"[0-9a-fA-F]{64}", item["sha256"]) is None:
            raise ModelApprovalError("invalid artifact checksum")
        if not isinstance(item["approved"], bool) or not item["approved"]:
            raise ModelApprovalError(f"artifact is not approved: {item['name']}")
        if any(
            term.lower() in str(item["name"]).lower()
            for term in ("edgesam", "sam2", "sam3", "hq-sam", "dino", "vlm")
        ):
            raise ModelApprovalError(f"prohibited model source: {item['name']}")
        local = item.get("local_path")
        if require_local and (not local or not Path(local).exists()):
            raise ModelArtifactError(f"approved artifact unavailable locally: {item['name']}")
        artifacts.append(
            ModelArtifact(
                item["name"],
                item["version"],
                item["source_url"],
                item["sha256"].lower(),
                item["license"],
                bool(item["approved"]),
                local,
            )
        )
    return ModelManifest(1, tuple(artifacts))


def load_model_manifest(path: str | Path, *, require_local: bool = False) -> ModelManifest:
    return validate_model_manifest(
        json.loads(Path(path).read_text(encoding="utf-8")), require_local=require_local
    )


def verify_sha256(path: str | Path, expected: str) -> str:
    if re.fullmatch(r"[0-9a-fA-F]{64}", str(expected)) is None:
        raise ModelArtifactError("expected checksum must be a hexadecimal SHA-256")
    h = hashlib.sha256()
    try:
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError as exc:
        raise ModelArtifactError(f"artifact is unavailable: {path}") from exc
    actual = h.hexdigest()
    if actual.lower() != expected.lower():
        raise ModelArtifactError(f"checksum mismatch: expected {expected}, got {actual}")
    return actual
