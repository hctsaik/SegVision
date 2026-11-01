import pytest

from segvision.core.errors import AcceptValidationError, UnsupportedOperation
from tests.e2e.helpers import make_session


def test_local_edit_locks_model_until_undo():
    session, backend = make_session()
    proposal = session.propose()
    session.select(proposal.candidates[0].candidate_id)
    session.edit("brush", points=[(2, 2)], radius=0)
    calls = backend.encode_calls
    with pytest.raises(UnsupportedOperation):
        session.propose()
    session.undo()
    session.propose()
    assert backend.encode_calls == calls


def test_empty_manual_candidate_is_not_committable():
    session, _ = make_session(count=0)
    candidate = session.begin_manual_empty()
    assert candidate.source.value == "manual_empty"
    with pytest.raises(AcceptValidationError):
        session.accept()


def test_brush_clip_rect_keeps_pixels_inside_two_point_work_area():
    session, _ = make_session(count=0)
    session.begin_manual()
    edited = session.edit(
        "brush",
        points=[(4, 4)],
        radius=2,
        clip_rect=[4, 4, 5, 5],
    )

    assert edited.mask.sum() == 1
    assert edited.mask[4, 4]
    assert not edited.mask[:4, :].any()
    assert not edited.mask[5:, :].any()
    assert not edited.mask[:, :4].any()
    assert not edited.mask[:, 5:].any()
