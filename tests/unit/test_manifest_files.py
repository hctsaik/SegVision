from segvision.acceptance.runner import validate_manifest


def test_normative_model_and_fixture_manifests_are_hash_bound():
    assert validate_manifest("models/manifest.json")["sha256"]
    assert validate_manifest("tests/fixtures/real_model/manifest.json")["sha256"]
