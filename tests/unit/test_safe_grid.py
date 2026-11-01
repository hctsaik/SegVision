from tests.e2e.helpers import make_session


def test_safe_grid_is_bounded_and_provenanced():
    session, _ = make_session(count=3)
    proposal = session.propose()
    assert len(proposal.candidates) <= 3
    assert all(c.source.value in {"sam_box", "sam_safe_grid"} for c in proposal.candidates)
    assert sum(c.source.value == "sam_safe_grid" for c in proposal.candidates) <= 1
