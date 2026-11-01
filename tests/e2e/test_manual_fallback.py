import pytest

from segvision.core.errors import AcceptValidationError, UnsupportedOperation

from .helpers import make_session


def test_man_backend_fail():
    s, _ = make_session(count=0)
    assert len(s.propose().candidates) == 0
    s.begin_manual()
    assert s.selected_candidate.source.value == "manual_empty"


def test_man_empty():
    s, _ = make_session(count=0)
    s.propose()
    s.begin_manual()
    with pytest.raises(AcceptValidationError):
        s.accept()


def test_man_erase():
    s, _ = make_session(count=1)
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    s.edit("erase", points=[(7, 7)], radius=20)
    assert not s.selected_candidate.mask.any()


def test_man_refine():
    s, _ = make_session(count=0)
    s.propose()
    s.begin_manual()
    with pytest.raises(UnsupportedOperation):
        s.refine(s.selected_candidate.candidate_id, (12, 12))
