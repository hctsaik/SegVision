import pytest

from segvision.core.candidate_policy import fuse_majority
from segvision.core.errors import InvalidMask
from tests.e2e.helpers import make_session


def test_majority_fusion_requires_three_same_revision_candidates():
    session, _ = make_session(count=3)
    proposal = session.propose()
    assert fuse_majority(proposal.candidates).mask.shape == session.context.shape
    with pytest.raises(InvalidMask):
        fuse_majority(proposal.candidates[:2])
