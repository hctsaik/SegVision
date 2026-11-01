"""Offline-first official artifact acquisition with quarantine on failure."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from segvision.core.errors import ModelApprovalError, ModelArtifactError

from .manifest import ModelArtifact, verify_sha256


def acquire_verified_artifact(
    artifact: ModelArtifact,
    destination: str | Path,
    *,
    downloader: Callable[[str, Path], None] | None = None,
) -> Path:
    if not artifact.approved:
        raise ModelApprovalError("artifact lacks approval")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    quarantine = destination.parent / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        try:
            verify_sha256(destination, artifact.sha256)
            return destination
        except ModelArtifactError:
            bad = quarantine / f"{destination.name}.mismatch"
            shutil.move(str(destination), str(bad))
    if downloader is None:
        raise ModelArtifactError("no offline artifact available; network download is not implicit")
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    try:
        downloader(artifact.source_url, tmp)
        verify_sha256(tmp, artifact.sha256)
        tmp.replace(destination)
        return destination
    except Exception as exc:
        if tmp.exists():
            tmp.replace(quarantine / tmp.name)
        if isinstance(exc, ModelArtifactError):
            raise
        raise ModelArtifactError(str(exc)) from exc
