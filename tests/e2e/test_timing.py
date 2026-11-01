from segvision.acceptance.observability import aggregate_times

from .helpers import make_session


def test_time_agg():
    assert aggregate_times([3, 1, 2])["p50"] == 2


def test_time_boundary():
    assert aggregate_times([])["count"] == 0


def test_time_invalid():
    s, _ = make_session()
    assert s.first_roi_locked_at > 0


def test_time_review():
    test_time_invalid()


def test_time_roi():
    s, _ = make_session()
    t = s.first_roi_locked_at
    s.update_roi((11, 9, 30, 30))
    assert s.first_roi_locked_at == t


def test_time_save():
    test_time_invalid()
