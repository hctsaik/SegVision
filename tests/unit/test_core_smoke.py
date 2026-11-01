import numpy as np
import pytest

from segvision import SegVisionEngine
from segvision.core.errors import AcceptValidationError, InvalidRoi
from segvision.core.geometry import create_crop_context, full_to_crop_point, reconstruct_full_mask
from segvision.providers.fake import FakeBackend, FakeDecode


def masks(shape=(18, 18)):
    a = np.zeros(shape, dtype=bool)
    a[3:8, 3:8] = True
    b = a.copy()
    b[8:10, 8:10] = True
    return a, b


def test_geometry_padding_and_reconstruction():
    ctx = create_crop_context((100, 100), (10, 20, 21, 31))
    assert ctx.crop_rect_full == (8, 18, 23, 33)
    assert full_to_crop_point((10, 20), ctx) == (2, 2)
    m = np.zeros(ctx.shape, dtype=bool)
    m[0, 0] = True
    out = reconstruct_full_mask(m, ctx)
    assert out.shape == (100, 100) and out[18, 8]


def test_invalid_roi_is_not_clipped():
    with pytest.raises(InvalidRoi):
        create_crop_context((20, 20), (-1, 0, 5, 5))


def test_session_proposal_refine_edit_accept():
    a, b = masks()
    backend = FakeBackend(initial=FakeDecode((a, b, a.copy())), refine=FakeDecode((b,)))
    session = SegVisionEngine(backend).start(
        np.zeros((20, 30, 3), np.uint8), "image", "class", (8, 4, 22, 18)
    )
    proposal = session.propose()
    assert 1 <= len(proposal.candidates) <= 3
    selected = session.select(proposal.candidates[0].candidate_id)
    refined = session.refine(selected.candidate_id, (10, 7), 1)
    assert refined.revision == 1 and backend.encode_calls == 1
    edited = session.edit("grow")
    assert edited.source.value == "manual_edit"
    session.undo()
    result = session.accept()
    assert result.full_image_mask.dtype == np.bool_


def test_manual_empty_is_not_accepted():
    backend = FakeBackend(initial=FakeDecode(()))
    session = SegVisionEngine(backend).start(
        np.zeros((10, 10, 3), np.uint8), "image", "class", (2, 2, 5, 5)
    )
    session.propose()
    session.begin_manual()
    with pytest.raises(AcceptValidationError):
        session.accept()
