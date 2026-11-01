from tests.e2e.helpers import make_session


def test_proposal_reuses_embedding_for_same_revision():
    session, backend = make_session()
    first = session.propose()
    second = session.propose()
    assert first.revision == second.revision == 1
    assert backend.encode_calls == 1
