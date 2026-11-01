import numpy as np

from segvision.core.candidate_policy import fuse_majority

from .helpers import make_session


def test_hp_01():
    s, b = make_session()
    p = s.propose()
    assert 1 <= len(p.candidates) <= 3 and b.encode_calls == 1


def test_cand_00():
    s, _ = make_session(count=0)
    assert len(s.propose().candidates) == 0


def test_cand_01():
    s, _ = make_session(count=1)
    assert len(s.propose().candidates) == 1


def test_cand_02():
    s, _ = make_session(count=2)
    assert len(s.propose().candidates) == 2


def test_cand_03():
    s, _ = make_session(count=3)
    p = s.propose()
    assert len(p.candidates) == 3
    for i, c in enumerate(p.candidates, 1):
        assert s.select(c.candidate_id).candidate_id == c.candidate_id


def test_cand_cap():
    s, _ = make_session(count=3)
    assert len(s.propose().candidates) <= 3


def test_cand_point():
    s, _ = make_session(count=2)
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    assert s.refine(p.candidates[0].candidate_id, (15, 15), 1).prompt_points


def test_cand_edge():
    s, _ = make_session(count=1)
    p = s.propose()
    assert isinstance(p.uncertainty.crop_edge_risk_mask_roi, np.ndarray)


def test_cand_uncertainty():
    s, _ = make_session(count=3)
    p = s.propose()
    assert p.uncertainty.disagreement_mask_roi.shape == s.context.shape


def test_grid_01():
    s, _ = make_session(count=3)
    assert s.propose().diagnostics.encoder_calls == 1


def test_grid_02():
    s, b = make_session(count=1)
    s.propose()
    assert b.encode_calls == 1


def test_fuse_01():
    s, _ = make_session(count=3)
    p = s.propose()
    f = fuse_majority(p.candidates)
    assert f.mask.dtype == np.bool_


def test_fuse_02():
    s, _ = make_session(count=2)
    p = s.propose()
    import pytest
    with pytest.raises(ValueError):
        fuse_majority(p.candidates)
