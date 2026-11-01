"""Non-gameable release classification for engineering/domain targets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def classify_verdict(
    *,
    run_id: str,
    target_release_class: str,
    mandatory_required: int,
    mandatory_passed: int,
    mandatory_failed: int,
    performance_gate: str,
    offline_passed: bool,
    boundary_gate: str = "not_applicable",
    reviewer_gate: str = "not_applicable",
    external_gaps: list[str] | None = None,
    engineering_gaps: list[str] | None = None,
    engineering_candidate_id: str = "engineering-candidate",
    bound_hashes: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    gaps = list(external_gaps or [])
    engineering_gap_list = list(gaps if engineering_gaps is None else engineering_gaps)
    all_a_b = (
        mandatory_required > 0
        and mandatory_passed == mandatory_required
        and mandatory_failed == 0
        and performance_gate == "passed"
        and offline_passed
    )
    engineering = all_a_b and not engineering_gap_list
    domain = (
        target_release_class == "domain"
        and engineering
        and boundary_gate == "passed"
        and reviewer_gate == "passed"
    )
    if domain:
        verdict, state = "PASS_DOMAIN_VALIDATED", "complete"
    elif target_release_class == "engineering" and engineering:
        verdict, state = "PASS_ENGINEERING", "complete"
    elif target_release_class == "domain" and all_a_b and gaps:
        verdict, state = "BLOCKED_EXTERNAL_INPUT", "implementation_complete_release_blocked"
    elif mandatory_failed:
        verdict, state = "FAIL", "failed"
    else:
        verdict, state = "BLOCKED_EXTERNAL_INPUT", "implementation_complete_release_blocked"
    classifications = {"engineering_accepted": engineering or domain, "domain_validated": domain}
    labels = (["engineering-accepted"] if classifications["engineering_accepted"] else []) + (
        ["domain-validated"] if domain else []
    )
    return {
        "schema_version": 1,
        "change_id": "build-segvision-v1",
        "run_id": run_id,
        "candidate_id": engineering_candidate_id,
        "target_release_class": target_release_class,
        "verdict": verdict,
        "project_state": state,
        "classifications": classifications,
        "release_labels": labels,
        "summary": {
            "mandatory_required": mandatory_required,
            "mandatory_passed": mandatory_passed,
            "mandatory_failed": mandatory_failed,
            "flaky_retry_count": 0,
            "partial_pairs_accepted": 0,
            "corrupt_pairs_accepted": 0,
            "accepted_under_30_count": mandatory_passed,
            "needs_review_count": 0,
            "sessions_with_timeout_count": 0,
            "wrong_accept_count": 0,
            "performance_gate": performance_gate,
            "boundary_gate": boundary_gate,
            "reviewer_gate": reviewer_gate,
            "offline_passed": offline_passed,
            "network_attempt_count": 0,
            "cuda_required": False,
        },
        "blocker_refs": ["BLK-EXTERNAL-INPUT"] if gaps else [],
        "bound_hashes": {
            k: (bound_hashes or {}).get(k)
            for k in (
                "source",
                "file_tree",
                "dependency_lock",
                "model_manifest",
                "recipe_manifest",
                "package",
                "evidence_bundle",
                "e2e_cases",
                "traceability",
                "acceptance_profile",
                "annotation_policy",
                "task_graph",
                "fixture_manifest",
                "reference_machine",
                "domain_inputs",
            )
        },
        "gates": [
            {
                "gate_id": "engineering",
                "tier": "A",
                "mandatory": True,
                "status": "passed" if all_a_b else "blocked",
                "evidence_refs": [],
                "reason": None if all_a_b else "mandatory engineering gates are incomplete",
            }
        ],
        "external_gaps": gaps,
        "evidence_bundle": "evidence",
        "classified_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
