from __future__ import annotations

import numpy as np

from segvision import SegVisionEngine
from segvision.core.recipe import CVRecipe
from segvision.providers.fake import FakeBackend, FakeDecode


def make_session(*, count: int = 3, refine: bool = True, recipe: CVRecipe | None = None):
    shape = (34, 34)
    masks = []
    for i in range(count):
        m = np.zeros(shape, dtype=bool)
        m[5 + i : 12 + i, 5:12] = True
        masks.append(m)
    backend = FakeBackend(
        initial=FakeDecode(tuple(masks)),
        refine=FakeDecode((masks[0],)) if refine and masks else None,
    )
    image = np.zeros((40, 50, 3), dtype=np.uint8)
    image[14:28, 18:32] = 255
    session = SegVisionEngine(backend).start(image, "e2e-image", "part", (10, 8, 38, 36), recipe)
    return session, backend
