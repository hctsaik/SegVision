import pytest

from segvision.core.errors import InvalidRoi, StaleRevision

from .helpers import make_session


def test_roi_pad():
    s, _ = make_session()
    assert s.context.crop_rect_full == (7, 5, 41, 39)


def test_roi_clamp():
    s, _ = make_session()
    s.update_roi((0, 0, 10, 10))
    assert s.context.crop_rect_full[0] == 0


def test_roi_invalid():
    s, _ = make_session()
    with pytest.raises(InvalidRoi):
        s.update_roi((5, 5, 5, 8))


def test_roi_stale_p():
    s, _ = make_session()
    p = s.propose()
    old = p.candidates[0].candidate_id
    s.update_roi((11, 9, 30, 30))
    with pytest.raises(StaleRevision):
        s.select(old)


def test_roi_stale_r():
    s, _ = make_session()
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    s.update_roi((11, 9, 30, 30))
    assert s.revision == 2


def test_roi_expand():
    s, _ = make_session()
    old = s.context
    s.expand_roi()
    assert s.revision == 2 and s.context != old


def test_roi_edge_sem():
    s, _ = make_session()
    assert s.context.user_roi_full != s.context.crop_rect_full


def test_roi_direct():
    s, _ = make_session()
    assert s.context.user_box_crop[0] > 0
