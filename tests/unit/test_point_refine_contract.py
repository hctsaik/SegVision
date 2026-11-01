import pytest

from segvision.core.errors import InvalidPoint, UnsupportedOperation
from tests.e2e.helpers import make_session


def test_refine_accumulates_points_and_rejects_outside_crop():
    session, _ = make_session()
    proposal = session.propose()
    candidate = session.select(proposal.candidates[0].candidate_id)
    refined = session.refine(candidate.candidate_id, (15, 15), 1)
    assert len(refined.prompt_points) == 1
    with pytest.raises(InvalidPoint):
        session.refine(refined.candidate_id, (0, 0), 1)


def test_direct_cv_candidate_cannot_refine():
    from segvision.core.recipe import CVRecipe

    session, _ = make_session(
        count=1,
        recipe=CVRecipe("direct", "part", enabled=True, threshold_low=200, threshold_high=255),
    )
    proposal = session.propose()
    with pytest.raises(UnsupportedOperation):
        session.refine(proposal.candidates[0].candidate_id, (15, 15), 1)
