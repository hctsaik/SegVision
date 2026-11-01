import json
from pathlib import Path

import pytest

from segvision.core.errors import ModelApprovalError, ModelArtifactError
from segvision.models.manifest import validate_model_manifest


def test_pending_style_manifest_is_rejected_until_approval():
    manifest = json.loads(
        Path(
            "openspec/changes/build-segvision-v1/acceptance/external-gates/model-artifact-manifest.pending.json"
        ).read_text(encoding="utf-8")
    )
    with pytest.raises((ModelApprovalError, ModelArtifactError)) as error:
        validate_model_manifest(manifest)
    assert "approved" in str(error.value) or "redistribution" in str(error.value)
