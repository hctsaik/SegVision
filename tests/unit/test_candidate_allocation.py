from segvision.core.candidate_policy import DEFAULT_CANDIDATE_POLICY


def test_candidate_allocation():
    assert DEFAULT_CANDIDATE_POLICY.max_candidates == 3
