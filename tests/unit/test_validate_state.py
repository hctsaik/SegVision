from segvision.acceptance.state import validate_state


def test_bootstrap_state_is_valid():
    result = validate_state("evidence/execution-state.json")
    assert result["tasks"] == 74
