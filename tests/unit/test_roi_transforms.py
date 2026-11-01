from segvision.core.geometry import create_crop_context, full_to_crop_point


def test_roi_transforms():
    assert full_to_crop_point((2, 2), create_crop_context((10, 10), (2, 2, 5, 5))) == (1, 1)
