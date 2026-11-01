from segvision.core.geometry import create_crop_context


def test_roi_context():
    assert create_crop_context((10, 10), (2, 2, 5, 5)).crop_rect_full == (1, 1, 6, 6)
