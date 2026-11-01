import hashlib

import pytest

from segvision.core.errors import ModelApprovalError, ModelArtifactError
from segvision.models.acquire import acquire_verified_artifact
from segvision.models.manifest import ModelArtifact


def test_acquisition_is_offline_first_and_checksum_bound(tmp_path):
    payload = b"approved checkpoint"
    digest = hashlib.sha256(payload).hexdigest()
    artifact = ModelArtifact("weights", "1", "https://example.invalid/weights", digest, "Apache-2.0", True)

    def download(_url, destination):
        destination.write_bytes(payload)

    target = acquire_verified_artifact(artifact, tmp_path / "weights.bin", downloader=download)
    assert target.read_bytes() == payload
    assert acquire_verified_artifact(artifact, target, downloader=None) == target


def test_unapproved_or_bad_download_fails_closed(tmp_path):
    artifact = ModelArtifact("weights", "1", "https://example.invalid/weights", "0" * 64, "Apache-2.0", False)
    with pytest.raises(ModelApprovalError):
        acquire_verified_artifact(artifact, tmp_path / "weights.bin")
    approved = ModelArtifact("weights", "1", "https://example.invalid/weights", "0" * 64, "Apache-2.0", True)
    with pytest.raises(ModelArtifactError):
        acquire_verified_artifact(approved, tmp_path / "weights.bin", downloader=lambda _, p: p.write_bytes(b"bad"))
