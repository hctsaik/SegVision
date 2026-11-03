"""Backend adapters kept separate from the pure core."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .acquire import acquire_verified_artifact
from .base import Backend, EncodedState, RawMask
from .fake import FakeBackend, FakeDecode
from .model_manifest import (
    ModelArtifact,
    ModelManifest,
    load_model_manifest,
    validate_model_manifest,
)

if TYPE_CHECKING:
    from .mobile_sam_torch_cpu import MobileSAMCPUBackend


def __getattr__(name: str) -> Any:
    """Load the optional model runtime only when its backend is requested."""
    if name != "MobileSAMCPUBackend":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .mobile_sam_torch_cpu import MobileSAMCPUBackend

    globals()[name] = MobileSAMCPUBackend
    return MobileSAMCPUBackend


__all__ = [
    "Backend",
    "EncodedState",
    "FakeBackend",
    "FakeDecode",
    "MobileSAMCPUBackend",
    "ModelArtifact",
    "ModelManifest",
    "RawMask",
    "acquire_verified_artifact",
    "load_model_manifest",
    "validate_model_manifest",
]
