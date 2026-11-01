from __future__ import annotations

import numpy as np

from segvision.application.backend import CropAwareFakeBackend
from segvision.core.types import PromptBundle


def test_crop_aware_fake_backend_keeps_masks_bound_to_each_encoded_crop() -> None:
    backend = CropAwareFakeBackend()
    first = backend.encode(
        np.zeros((12, 18, 3), dtype=np.uint8),
        session_id="first",
        revision=1,
        crop_fingerprint="first",
    )
    second = backend.encode(
        np.zeros((24, 30, 3), dtype=np.uint8),
        session_id="second",
        revision=1,
        crop_fingerprint="second",
    )

    first_masks = backend.decode(first, PromptBundle((0, 0, 18, 12)), multimask_count=3)
    second_masks = backend.decode(second, PromptBundle((0, 0, 30, 24)), multimask_count=3)

    assert {mask.mask.shape for mask in first_masks} == {(12, 18)}
    assert {mask.mask.shape for mask in second_masks} == {(24, 30)}
