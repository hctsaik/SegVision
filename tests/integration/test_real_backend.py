import numpy as np

from segvision.core.types import PromptBundle
from tests.mobile_sam_double import controlled_backend


def test_approved_local_cpu_backend_roundtrip(tmp_path):
    backend = controlled_backend(tmp_path)
    encoded = backend.encode(np.zeros((3, 4, 3), np.uint8), session_id="s", revision=1, crop_fingerprint="f")
    assert backend.decode(encoded, PromptBundle((0, 0, 4, 3)), multimask_count=1)[0].mask.shape == (3, 4)
