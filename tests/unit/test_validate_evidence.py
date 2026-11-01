import json

from segvision.acceptance.evidence import make_minimal_evidence, validate_evidence


def test_valid_evidence_roundtrip(tmp_path):
    run_id = "sv-20260827T232308Z-2e186d64"
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(make_minimal_evidence("P00", run_id)), encoding="utf-8")
    assert validate_evidence(path)["count"] == 1
