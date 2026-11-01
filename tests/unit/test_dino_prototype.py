from __future__ import annotations

import numpy as np

from segvision.prototype.dino import fit_prototypes, match_tokens


def _tokens_with_blob(y0: int, x0: int, y1: int, x1: int) -> np.ndarray:
    tokens = np.zeros((37, 37, 8), dtype=np.float32)
    tokens[..., 0] = 1.0
    tokens[y0:y1, x0:x1, 0] = 0.2
    tokens[y0:y1, x0:x1, 1] = 1.0
    norms = np.linalg.norm(tokens, axis=-1, keepdims=True)
    return tokens / np.maximum(norms, 1e-8)


def test_match_finds_moved_blob_not_original_coordinates():
    teacher = np.zeros((518, 518), dtype=bool)
    teacher[14 * 4 : 14 * 10, 14 * 4 : 14 * 10] = True
    teacher_tokens = _tokens_with_blob(4, 4, 10, 10)
    proto = fit_prototypes(teacher_tokens, teacher)
    target_tokens = _tokens_with_blob(20, 22, 28, 30)
    matched = match_tokens(target_tokens, proto, scale=1.0, image_shape=(518, 518))
    assert matched.abstain is False
    assert matched.roi is not None
    x0, y0, x1, y1 = matched.roi
    assert x0 >= 22 * 14 - 16
    assert y0 >= 20 * 14 - 16
    assert x1 <= 30 * 14 + 16
    assert y1 <= 28 * 14 + 16
    assert not (x0 <= 4 * 14 and x1 >= 10 * 14 and y0 <= 4 * 14 and y1 >= 10 * 14)


def test_two_equal_peaks_abstain():
    teacher = np.zeros((518, 518), dtype=bool)
    teacher[0:70, 0:70] = True
    proto = fit_prototypes(_tokens_with_blob(0, 0, 5, 5), teacher)
    tokens = _tokens_with_blob(2, 2, 8, 8)
    tokens[20:26, 20:26] = tokens[2:8, 2:8]
    matched = match_tokens(tokens, proto, scale=1.0, image_shape=(518, 518))
    assert matched.abstain is True
