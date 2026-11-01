from segvision.acceptance.verdict import classify_verdict


def test_rel_verdict():
    v = classify_verdict(
        run_id="sv-20260101T000000Z-abcdef12",
        target_release_class="engineering",
        mandatory_required=1,
        mandatory_passed=1,
        mandatory_failed=0,
        performance_gate="passed",
        offline_passed=True,
    )
    assert v["verdict"] == "PASS_ENGINEERING"


def test_rel_rollback():
    v = classify_verdict(
        run_id="sv-20260101T000000Z-abcdef12",
        target_release_class="domain",
        mandatory_required=1,
        mandatory_passed=1,
        mandatory_failed=0,
        performance_gate="passed",
        offline_passed=True,
        external_gaps=["gold data"],
    )
    assert v["project_state"] == "implementation_complete_release_blocked"
