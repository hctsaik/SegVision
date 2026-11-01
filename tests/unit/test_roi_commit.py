import numpy as np

from segvision.core.geometry import create_crop_context, reconstruct_full_mask


def test_roi_commit():
    c = create_crop_context((10, 10), (2, 2, 5, 5))
    m = np.zeros(c.shape, bool)
    m[0, 0] = 1
    assert reconstruct_full_mask(m, c)[1, 1]
