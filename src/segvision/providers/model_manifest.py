"""Compatibility entry points for provider-owned model manifests.

The runtime model manifest implementation lives in :mod:`segvision.models`
so that acquisition and metadata can be used without importing a backend.
The OpenSpec provider boundary historically names this module
``providers.model_manifest``; re-exporting the typed API keeps that boundary
stable while preserving the single validation implementation.
"""

from __future__ import annotations

from segvision.models.manifest import (
    ModelArtifact,
    ModelManifest,
    load_model_manifest,
    validate_model_manifest,
    verify_sha256,
)

__all__ = [
    "ModelArtifact",
    "ModelManifest",
    "load_model_manifest",
    "validate_model_manifest",
    "verify_sha256",
]
