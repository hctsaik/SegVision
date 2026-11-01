from segvision.acceptance.contracts import validate_contracts


def test_contracts_validate_all_instances():
    result = validate_contracts("openspec/changes/build-segvision-v1")
    assert result["tasks"] == 74 and result["e2e_cases"] >= 90
