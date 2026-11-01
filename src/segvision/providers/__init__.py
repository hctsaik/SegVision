"""Backend adapters kept separate from the pure core."""

from .acquire import acquire_verified_artifact
from .base import Backend, EncodedState, RawMask
from .fake import FakeBackend, FakeDecode
from .mobile_sam_torch_cpu import MobileSAMCPUBackend
from .model_manifest import (
    ModelArtifact,
    ModelManifest,
    load_model_manifest,
    validate_model_manifest,
)

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
