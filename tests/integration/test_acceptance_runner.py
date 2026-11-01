from segvision.acceptance.runner import validate_manifest


def test_acceptance_runner():
    assert (
        validate_manifest("openspec/changes/build-segvision-v1/acceptance/e2e-cases.json")["cases"]
        == 94
    )
