import numpy as np
import pytest

from segvision.core.errors import InvalidMask, InvalidPoint
from segvision.core.geometry import create_crop_context, full_to_crop_point, reconstruct_full_mask


def test_geometry_roundtrip_and_strict_mask_dtype():
    context = create_crop_context((10, 12), (2, 3, 8, 9))
    ox, oy, _, _ = context.crop_rect_full
    assert full_to_crop_point((ox, oy), context) == (0, 0)
    mask = np.zeros(context.shape, dtype=bool)
    mask[1, 2] = True
    full = reconstruct_full_mask(mask, context)
    assert full[context.crop_rect_full[1] + 1, context.crop_rect_full[0] + 2]
    with pytest.raises(InvalidMask):
        reconstruct_full_mask(mask.astype(np.uint8), context)
    with pytest.raises(InvalidPoint):
        full_to_crop_point((2.5, 3), context)
