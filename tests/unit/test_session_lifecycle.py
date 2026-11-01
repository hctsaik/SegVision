import numpy as np

from segvision import SegVisionEngine
from segvision.providers.fake import FakeBackend, FakeDecode


def test_session_lifecycle():
    b = FakeBackend(initial=FakeDecode(()))
    s = SegVisionEngine(b).start(np.zeros((4, 4, 3), np.uint8), "i", "c", (1, 1, 3, 3))
    assert s.revision == 1
