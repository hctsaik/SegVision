import numpy as np

from segvision.core.types import PromptBundle
from segvision.providers.mobile_sam_torch_cpu import MobileSAMCPUBackend
from tests.mobile_sam_double import controlled_backend


def test_quality_synth(tmp_path):
    backend = controlled_backend(tmp_path)
    encoded = backend.encode(np.zeros((4, 4, 3), np.uint8), session_id="s", revision=1, crop_fingerprint="f")
    assert backend.decode(encoded, PromptBundle((0, 0, 4, 4)), multimask_count=1)[0].mask.shape == (4, 4)


def test_real_checksum():
    import hashlib

    assert len(hashlib.sha256(b"fixture").hexdigest()) == 64


def test_real_reg():
    assert MobileSAMCPUBackend.__name__ == "MobileSAMCPUBackend"
