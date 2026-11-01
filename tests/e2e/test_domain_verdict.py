import numpy as np

from segvision.acceptance.quality import symmetric_boundary_f1


def test_quality_domain():
    mask = np.zeros((8, 8), bool)
    mask[2:6, 2:6] = True
    assert symmetric_boundary_f1(mask, mask) == 1.0
