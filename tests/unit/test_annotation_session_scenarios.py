import numpy as np
import pytest

from segvision import SegVisionEngine
from segvision.core.errors import InvalidImage
from segvision.providers.fake import FakeBackend


def test_session_copies_input_and_rejects_invalid_image():
    image = np.zeros((4, 5, 3), np.uint8)
    session = SegVisionEngine(FakeBackend()).start(image, "image", "class", (1, 1, 4, 3))
    image[0, 0] = 255
    assert int(session.crop.sum()) == 0
    with pytest.raises(InvalidImage):
        SegVisionEngine(FakeBackend()).start(np.zeros((4, 5), np.uint8), "image", "class", (0, 0, 1, 1))
