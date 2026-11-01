import pytest

from segvision.core.errors import AcceptValidationError
from tests.e2e.helpers import make_session


def test_commit_requires_explicit_confirmation():
    session, _ = make_session(count=1)
    proposal = session.propose()
    session.select(proposal.candidates[0].candidate_id)
    with pytest.raises(AcceptValidationError):
        session.commit(acceptance={"explicit_confirmation": False})


def test_commit_returns_full_image_and_provenance():
    session, _ = make_session(count=1)
    proposal = session.propose()
    session.select(proposal.candidates[0].candidate_id)
    result = session.commit(acceptance={"explicit_confirmation": True, "acceptance_actor": "scripted_test"})
    assert result.outcome.value == "accepted"
    assert result.full_image_mask.shape == (session.image_height, session.image_width)
    assert result.provenance["source_sha256"]


def test_needs_review_requires_reason():
    session, _ = make_session(count=0)
    with pytest.raises(AcceptValidationError):
        session.needs_review(" ")
