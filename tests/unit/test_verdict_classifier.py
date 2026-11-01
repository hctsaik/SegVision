from segvision.acceptance.verdict import classify_verdict


def test_verdict_classifier_distinguishes_engineering_pass_and_external_block():
    passed = classify_verdict(
        run_id="sv-20260101T000000Z-abcdef12",
        target_release_class="engineering",
        mandatory_required=2,
        mandatory_passed=2,
        mandatory_failed=0,
        performance_gate="passed",
        offline_passed=True,
    )
    blocked = classify_verdict(
        run_id="sv-20260101T000000Z-abcdef12",
        target_release_class="engineering",
        mandatory_required=2,
        mandatory_passed=2,
        mandatory_failed=0,
        performance_gate="blocked",
        offline_passed=False,
        external_gaps=["reference"],
    )
    assert passed["verdict"] == "PASS_ENGINEERING"
    assert blocked["project_state"] == "implementation_complete_release_blocked"
