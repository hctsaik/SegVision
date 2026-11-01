import pytest

from segvision.core.errors import AcceptValidationError, UnsupportedOperation
from segvision.core.recipe import CVRecipe

from .helpers import make_session


def test_ref_01():
    s, b = make_session()
    p = s.propose()
    c = s.select(p.candidates[0].candidate_id)
    s.refine(c.candidate_id, (15, 15))
    assert b.encode_calls == 1 and b.decode_calls >= 2


def test_ref_02():
    s, b = make_session(count=2)
    p = s.propose()
    s.select(p.candidates[1].candidate_id)
    s.refine(p.candidates[1].candidate_id, (16, 16))
    assert b.encode_calls == 1


def test_ref_03():
    s, _ = make_session()
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    s.refine(p.candidates[0].candidate_id, (20, 20), 0)


def test_ref_unsupported():
    recipe = CVRecipe(
        "direct",
        "part",
        enabled=True,
        threshold_low=200,
        threshold_high=255,
        direct_area_fraction_min=0.01,
        direct_area_fraction_max=0.9,
    )
    s, b = make_session(count=1, recipe=recipe)
    p = s.propose()
    assert p.candidates[0].source.value == "cv_direct"
    with pytest.raises(UnsupportedOperation):
        s.refine(p.candidates[0].candidate_id, (15, 15))
    assert b.encode_calls == 0


def test_edit_01():
    s, b = make_session()
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    before = b.decode_calls
    c = s.edit("brush", points=[(2, 2)])
    assert c.source.value == "manual_edit" and b.decode_calls == before


def test_edit_02():
    s, _ = make_session()
    s.propose()
    s.edit("brush", points=[(2, 2)])
    assert s.undo() is None


def test_edit_grow():
    s, _ = make_session()
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    before = s.selected_candidate.mask.sum()
    assert s.edit("grow").mask.sum() >= before


def test_edit_fill():
    s, _ = make_session()
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    assert s.edit("fill_holes").mask.any()


def test_val_point():
    s, _ = make_session(count=0)
    s.propose()
    s.begin_manual()
    with pytest.raises(AcceptValidationError):
        s.accept()
