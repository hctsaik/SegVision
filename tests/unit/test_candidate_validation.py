import numpy as np

from segvision.core.candidate_policy import validate_candidate_mask
from segvision.core.geometry import create_crop_context


def test_candidate_validation():
    c = create_crop_context((5, 5), (1, 1, 3, 3))
    m = np.zeros(c.shape, bool)
    assert validate_candidate_mask(m, c)[2] == "EMPTY_MASK"
