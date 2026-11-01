import numpy as np
import pytest

from segvision.core.errors import ModelApprovalError
from segvision.providers.mobile_sam_torch_cpu import MobileSAMCPUBackend
from tests.mobile_sam_double import ControlledPredictor, controlled_backend


def test_mobile_encode_requires_approval():
    with pytest.raises(ModelApprovalError):
        MobileSAMCPUBackend()


def test_mobile_encode_runs_predictor_and_preserves_input(tmp_path):
    backend = controlled_backend(tmp_path)
    image = np.arange(5 * 6 * 3, dtype=np.uint8).reshape(5, 6, 3)
    before = image.copy()

    encoded = backend.encode(image, session_id="session", revision=1, crop_fingerprint="crop")

    assert np.array_equal(image, before)
    state = backend._states[encoded.token]
    assert isinstance(state.predictor, ControlledPredictor)
    assert np.array_equal(state.predictor.image_copy, before)
    assert backend.ledger[-1]["op"] == "encode"
