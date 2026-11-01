"""CPU backend selection for the desktop sidecar (fake or approved MobileSAM)."""

from __future__ import annotations

import json
import os
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

import numpy as np

from segvision.core.errors import BackendUnavailable, ModelApprovalError, ModelArtifactError
from segvision.providers.fake import FakeBackend, FakeDecode

from .errors import ProtocolError


class CropAwareFakeBackend(FakeBackend):
    """Fake backend that materializes masks for each encoded crop."""

    @staticmethod
    def _materialize(encoded: Any) -> tuple[FakeDecode, FakeDecode]:
        opaque = encoded.opaque if isinstance(encoded.opaque, dict) else {}
        shape = opaque.get("shape") or (32, 32, 3)
        h, w = int(shape[0]), int(shape[1])
        masks = []
        for i in range(3):
            mask = np.zeros((h, w), dtype=bool)
            y0, x0 = 2 + i, 2 + i
            y1, x1 = max(y0 + 4, h - 2 - i), max(x0 + 4, w - 2 - i)
            mask[y0:y1, x0:x1] = True
            masks.append(mask)
        return FakeDecode(tuple(masks)), FakeDecode((masks[0],))

    def decode(self, encoded, prompt, *, multimask_count: int):  # type: ignore[no-untyped-def]
        state = self._states.get(encoded.token)
        if state is None:
            raise ValueError("unknown encoded state")
        if encoded.session_id != state.session_id or encoded.revision != state.revision:
            raise ValueError("encoded state identity mismatch")
        if multimask_count < 1:
            raise ValueError("multimask_count must be positive")
        initial, refined = self._materialize(encoded)
        if prompt.points_crop_xy:
            if prompt.previous_mask_state is None and self.safe_grid_result is not None:
                result = self.safe_grid_result
                kind = "safe_grid"
            else:
                result = refined
                kind = "refine"
        elif prompt.previous_mask_state is not None:
            result = refined
            kind = "refine"
        else:
            result = initial
            kind = "box"
        self.ledger.append(
            {
                "op": "decode",
                "kind": kind,
                "revision": encoded.revision,
                "multimask_count": multimask_count,
                "points": [point.to_dict() for point in prompt.points_crop_xy],
            }
        )
        return self._convert(result, prompt, multimask_count)


def _resolve_config_path(value: str | Path | None) -> Path:
    configured = value or os.environ.get("SEGVISION_MOBILESAM_CONFIG")
    return Path(configured) if configured else Path("models") / "local-evaluation.json"


def _resolve_from_config(config_path: Path, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ModelApprovalError(f"MobileSAM runtime config requires {field}")
    path = Path(value)
    return path if path.is_absolute() else (config_path.parent / path).resolve()


def _verify_mobile_sam_package_source(
    source_revision: str, source_repository: Any, source_archive_sha256: Any
) -> None:
    try:
        package = distribution("mobile-sam")
    except PackageNotFoundError as exc:
        raise ModelArtifactError("official mobile_sam package is unavailable") from exc
    direct_url_text = package.read_text("direct_url.json")
    if direct_url_text:
        direct_url = json.loads(direct_url_text).get("url")
        if not isinstance(direct_url, str) or source_revision not in direct_url:
            raise ModelArtifactError("installed mobile_sam source revision mismatch")
        return

    provenance_value = os.environ.get("SEGVISION_MOBILESAM_PACKAGE_PROVENANCE")
    lock_value = os.environ.get("SEGVISION_MOBILESAM_LOCK")
    if not provenance_value or not lock_value:
        raise ModelArtifactError("installed mobile_sam source provenance is unavailable")
    try:
        package_provenance = json.loads(Path(provenance_value).read_text(encoding="utf-8"))
        lock_text = Path(lock_value).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelArtifactError("packaged mobile_sam provenance is unavailable") from exc

    version = package.version
    wheel_sha256 = (
        package_provenance.get("wheel_sha256")
        if isinstance(package_provenance, dict)
        else None
    )
    if (
        not isinstance(package_provenance, dict)
        or package_provenance.get("schema_version") != 1
        or package_provenance.get("package_name") != "mobile-sam"
        or package_provenance.get("package_version") != version
        or package_provenance.get("source_repository") != source_repository
        or source_repository != "https://github.com/ChaoningZhang/MobileSAM"
        or package_provenance.get("source_revision") != source_revision
        or package_provenance.get("source_archive_sha256") != source_archive_sha256
        or not isinstance(source_archive_sha256, str)
        or len(source_archive_sha256) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in source_archive_sha256)
        or package_provenance.get("scope") != "local_cpu_evaluation"
        or package_provenance.get("release_approved") is not False
        or not isinstance(wheel_sha256, str)
        or len(wheel_sha256) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in wheel_sha256)
    ):
        raise ModelArtifactError("packaged mobile_sam provenance does not match the approved revision")

    expected_pin = f"mobile-sam=={version}"
    matching_lines = []
    for line in lock_text.splitlines():
        stripped = line.strip()
        fields = stripped.split(maxsplit=1)
        if fields and fields[0].lower() == expected_pin.lower():
            matching_lines.append(stripped)
    expected_hash = f"--hash=sha256:{wheel_sha256.lower()}"
    if not any(expected_hash in line.lower() for line in matching_lines):
        raise ModelArtifactError("packaged mobile_sam wheel hash is not pinned by the App lock")


def _load_local_evaluation_backend(config_path: Path) -> tuple[Any, dict[str, Any]]:
    from segvision.providers.mobile_sam_torch_cpu import MobileSAMCPUBackend

    data = json.loads(config_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("mode") != "local_evaluation":
        raise ModelApprovalError("unsupported MobileSAM runtime config")
    checkpoint = _resolve_from_config(config_path, data.get("checkpoint_path"), "checkpoint_path")
    authorization_path = _resolve_from_config(
        config_path, data.get("authorization_path"), "authorization_path"
    )
    provenance_path = _resolve_from_config(
        config_path, data.get("provenance_path"), "provenance_path"
    )
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    expected_sha256 = data.get("checkpoint_sha256")
    if not isinstance(expected_sha256, str):
        raise ModelApprovalError("MobileSAM runtime config requires checkpoint_sha256")
    if authorization.get("scope", {}).get("local_cpu_evaluation") is not True:
        raise ModelApprovalError("MobileSAM checkpoint lacks local CPU evaluation authorization")
    if authorization.get("artifacts", {}).get("checkpoint_sha256") != expected_sha256:
        raise ModelApprovalError("authorization checkpoint identity mismatch")
    if provenance.get("checkpoint", {}).get("sha256") != expected_sha256:
        raise ModelApprovalError("provenance checkpoint identity mismatch")
    source_revision = provenance.get("source_revision")
    if not isinstance(source_revision, str) or not source_revision:
        raise ModelApprovalError("MobileSAM provenance lacks a source revision")
    if authorization.get("artifacts", {}).get("source_revision") != source_revision:
        raise ModelApprovalError("authorization source revision mismatch")
    _verify_mobile_sam_package_source(
        source_revision,
        provenance.get("source_repository"),
        provenance.get("source_archive", {}).get("sha256"),
    )
    backend = MobileSAMCPUBackend(
        checkpoint_path=str(checkpoint),
        checkpoint_sha256=expected_sha256,
        approved=True,
        model_version=f"MobileSAM-TinyViT@{source_revision[:12]}",
    )
    return backend, {
        "name": "mobilesam",
        "approved": True,
        "approval_scope": "local_evaluation",
        "release_approved": False,
        "setup_state": "ready",
        "cpu_only": True,
    }


def default_backend(
    *, prefer_real: bool = False, model_config_path: str | Path | None = None
) -> tuple[Any, dict[str, Any]]:
    setup = {"name": "fake", "approved": True, "setup_state": "ready", "cpu_only": True}
    if not prefer_real:
        return CropAwareFakeBackend(), setup
    try:
        config_path = _resolve_config_path(model_config_path)
        if not config_path.is_file():
            setup["setup_state"] = "missing_checkpoint"
            setup["approved"] = False
            return CropAwareFakeBackend(), setup
        return _load_local_evaluation_backend(config_path)
    except (
        ModelApprovalError,
        ModelArtifactError,
        BackendUnavailable,
        FileNotFoundError,
        AttributeError,
        OSError,
        ImportError,
        ValueError,
        RuntimeError,
    ) as exc:
        setup["setup_state"] = (
            "unapproved_checkpoint" if isinstance(exc, ModelApprovalError) else "model_unavailable"
        )
        setup["approved"] = False
        setup["diagnostic"] = type(exc).__name__
        return CropAwareFakeBackend(), setup


def refuse_gpu_flags(env: dict[str, str] | None = None) -> None:
    values = env or {}
    banned = ("CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES")
    for key in banned:
        if values.get(key) not in (None, "", "-1"):
            raise ProtocolError("engine_unavailable", "GPU device flags are forbidden")
