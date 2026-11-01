import pytest

from segvision.core.errors import InvalidRoi, UnsupportedOperation
from segvision.core.geometry import create_crop_context, expanded_context


def test_padding_is_outward_and_clamped():
    context = create_crop_context((100, 120), (20, 30, 60, 70))
    assert context.crop_rect_full == (16, 26, 64, 74)
    edge = create_crop_context((10, 10), (0, 0, 2, 2))
    assert edge.padding_clamped


def test_invalid_roi_and_boundary_expand_are_typed():
    with pytest.raises(InvalidRoi):
        create_crop_context((10, 10), (0, 0, 0, 1))
    context = create_crop_context((10, 10), (0, 0, 10, 10))
    with pytest.raises(UnsupportedOperation):
        expanded_context(context)
