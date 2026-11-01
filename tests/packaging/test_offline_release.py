from segvision.acceptance.compliance import write_sbom, write_third_party_notices
from segvision.acceptance.offline import build_offline_bundle, verify_offline_bundle
from segvision.acceptance.runner import validate_manifest


def test_pkg_install():
    assert (
        validate_manifest("openspec/changes/build-segvision-v1/acceptance/e2e-cases.json")["cases"]
        > 0
    )


def test_pkg_cpu():
    assert "cuda" not in " ".join(validate_manifest("openspec/changes/build-segvision-v1/acceptance/e2e-cases.json").keys()).lower()


def test_pkg_e2e():
    assert validate_manifest("openspec/changes/build-segvision-v1/acceptance/e2e-cases.json")["cases"] == 94


def test_pkg_compliance():
    import tempfile
    from pathlib import Path

    root = Path(tempfile.mkdtemp())
    assert write_sbom(root / "sbom.json").exists()
    assert write_third_party_notices(root / "NOTICES.txt").exists()


def test_pkg_net():
    import tempfile
    from pathlib import Path

    source = Path(tempfile.mkdtemp())
    (source / "payload.txt").write_text("offline", encoding="utf-8")
    bundle = build_offline_bundle(source, source.parent / "bundle.zip")
    assert verify_offline_bundle(bundle)[0]["path"] == "payload.txt"


def test_pkg_path():
    assert validate_manifest("openspec/changes/build-segvision-v1/acceptance/e2e-cases.json")["path"].endswith("e2e-cases.json")
