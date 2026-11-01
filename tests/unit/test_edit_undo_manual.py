import pytest
import numpy as np

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


@pytest.mark.parametrize("operation", ["brush", "erase"])
def test_two_point_work_area_clips_the_full_brush_radius_for_both_pixel_tools(operation):
    session, backend = make_session(count=0)
    if operation == "erase":
        session.import_mask(np.ones((40, 50), dtype=np.bool_))
    else:
        session.begin_manual()

    encode_calls = backend.encode_calls
    edited = session.edit(
        operation,
        points=[(3, 5)],
        radius=2,
        clip_rect=[4, 4, 8, 8],
    )

    # The 5 px brush crosses the left edge, but only its overlap with the
    # half-open [4, 8) x [4, 8) work area may change.
    changed = ~edited.mask if operation == "erase" else edited.mask
    expected = np.zeros_like(changed)
    expected[4, 4] = True
    expected[5, 4] = True
    expected[6, 4] = True
    expected[5, 5] = True
    assert np.array_equal(changed, expected)
    assert backend.encode_calls == encode_calls
