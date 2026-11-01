import pytest

from segvision.core.errors import ModelApprovalError
from segvision.models.manifest import validate_model_manifest


def test_model_manifest_fail_closed():
    with pytest.raises(ModelApprovalError):
        validate_model_manifest({"schema_version": 1, "artifacts": []})
