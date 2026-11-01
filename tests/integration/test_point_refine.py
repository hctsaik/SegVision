from tests.e2e.helpers import make_session


def test_point_refine_reuses_encoded_embedding():
    session, backend = make_session()
    proposal = session.propose()
    candidate = session.select(proposal.candidates[0].candidate_id)
    session.refine(candidate.candidate_id, (15, 15))
    assert backend.encode_calls == 1 and backend.decode_calls >= 2
