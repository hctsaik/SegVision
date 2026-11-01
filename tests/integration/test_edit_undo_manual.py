from tests.e2e.helpers import make_session


def test_edit_undo_restores_model_candidate_without_reencoding():
    session, backend = make_session()
    proposal = session.propose()
    session.select(proposal.candidates[0].candidate_id)
    before = session.selected_candidate.mask.copy()
    session.edit("brush", points=[(1, 1)])
    session.undo()
    assert session.selected_candidate is not None
    assert (session.selected_candidate.mask == before).all()
    assert backend.encode_calls == 1
