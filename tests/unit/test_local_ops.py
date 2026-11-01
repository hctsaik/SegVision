import numpy as np

from segvision.core.mask_ops import grow, shrink


def test_local_ops():
    m = np.zeros((5, 5), bool)
    m[2, 2] = 1
    assert grow(m).sum() == 9 and shrink(grow(m)).sum() == 1
