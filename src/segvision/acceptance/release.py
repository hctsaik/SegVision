"""Evidence-bound release classification helpers.

This module never upgrades a missing gate to a pass.  It consumes only the
machine-readable scenario results and external-gate manifests present in the
run directory, then emits the repository release-verdict schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from segvision.core.errors import ContractValidationError

from .common import maintained_tree_hash, repo_root, sha256_file
from .external_gates import all_pending_manifests
from .verdict import classify_verdict


def classify_evidence_directory(
    evidence: str | Path, *, target_release_class: str = "engineering"
) -> dict[str, Any]:
    root = repo_root()
    change_dir = root / "openspec" / "changes" / "build-segvision-v1"
    manifest_path = change_dir / "acceptance" / "e2e-cases.json"
    run_dir = Path(evidence)
    run_dir = run_dir if run_dir.is_absolute() else root / run_dir
    scenario_path = run_dir / "scenario-results.json"
    if not scenario_path.is_file():
        raise ContractValidationError(f"scenario results not found: {scenario_path}")
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    scenario_schema = change_dir / "acceptance" / "scenario-results.schema.json"
    scenario_errors = sorted(
        Draft202012Validator(json.loads(scenario_schema.read_text(encoding="utf-8"))).iter_errors(scenario),
        key=lambda error: list(error.path),
    )
    if scenario_errors:
        raise ContractValidationError(f"scenario results: {scenario_errors[0].message}")
    if scenario["e2e_cases_sha256"].lower() != sha256_file(manifest_path).lower():
        raise ContractValidationError("scenario results E2E manifest hash mismatch")
    trace_path = change_dir / "acceptance" / "traceability.json"
    if scenario["traceability_sha256"].lower() != sha256_file(trace_path).lower():
        raise ContractValidationError("scenario results traceability hash mismatch")
    wheel_candidates = sorted((root / "dist").glob("*.whl"))
    results = scenario.get("results", [])
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_cases = manifest_data.get("cases", [])
    manifest_ids = {case["id"] for case in manifest_cases}
    result_ids = [str(result.get("case_id")) for result in results]
    if len(result_ids) != len(set(result_ids)):
        raise ContractValidationError("scenario results contain duplicate case IDs")
    unknown_results = set(result_ids) - manifest_ids
    if unknown_results:
        raise ContractValidationError(f"scenario results contain unknown cases: {sorted(unknown_results)}")
    expected_mandatory = {
        case["id"] for case in manifest_cases if bool(case.get("mandatory", False))
    }
    by_case = {str(result.get("case_id")): result for result in results}
    missing = expected_mandatory - set(by_case)
    mandatory = [by_case[case_id] for case_id in expected_mandatory if case_id in by_case]
    passed = sum(result.get("status") == "passed" for result in mandatory)
    failed = sum(result.get("status") == "failed" for result in mandatory) + len(missing)
    # A run containing only Tier A mechanics has not proved the reference CPU,
    # performance, or offline-install gates.  Keep those gates blocked until
    # their independent evidence artifacts exist.
    expected_tier_b = {
        case["id"] for case in manifest_cases if case.get("tier") == "B" and case.get("mandatory")
    }
    has_tier_b = bool(expected_tier_b) and all(
        by_case.get(case_id, {}).get("status") == "passed" for case_id in expected_tier_b
    )
    external_gaps: list[str] = []
    pending_dir = (
        root
        / "openspec"
        / "changes"
        / "build-segvision-v1"
        / "acceptance"
        / "external-gates"
    )
    if pending_dir.exists():
        for pending in all_pending_manifests(pending_dir):
            external_gaps.append(str(pending.get("manifest_id", pending.get("status", "pending"))))
    # Tier C/domain evidence is intentionally not an engineering dependency.
    # Keep it visible for a domain-target verdict while excluding it from the
    # engineering classification calculation.
    engineering_gaps = [gap for gap in external_gaps if "domain-inputs" not in gap]
    applicable_gaps = external_gaps if target_release_class == "domain" else engineering_gaps
    if not has_tier_b:
        external_gaps.append("Tier B reference CPU/performance evidence is unavailable")
    if missing:
        external_gaps.append("mandatory scenario evidence is incomplete")
    verdict = classify_verdict(
        run_id=scenario["run_id"],
        target_release_class=target_release_class,
        mandatory_required=len(mandatory),
        mandatory_passed=passed,
        mandatory_failed=failed,
        performance_gate="passed" if has_tier_b else "blocked",
        offline_passed=has_tier_b and (run_dir / "offline-install.json").is_file(),
        external_gaps=sorted(set(applicable_gaps)),
        engineering_gaps=sorted(set(engineering_gaps)),
        engineering_candidate_id=f"{scenario['run_id']}-candidate",
        bound_hashes={
            "source": None,
            "file_tree": maintained_tree_hash(root),
            "dependency_lock": sha256_file(root / "requirements" / "dev.lock"),
            "package": sha256_file(wheel_candidates[-1]) if wheel_candidates else None,
            "e2e_cases": sha256_file(manifest_path),
            "traceability": sha256_file(change_dir / "acceptance" / "traceability.json"),
            "acceptance_profile": sha256_file(change_dir / "acceptance" / "acceptance-profile.json"),
            "annotation_policy": sha256_file(change_dir / "acceptance" / "default-annotation-policy.json"),
            "task_graph": sha256_file(change_dir / "acceptance" / "task-graph.json"),
            "evidence_bundle": sha256_file(scenario_path),
        },
    )
    release_schema = change_dir / "acceptance" / "release-verdict.schema.json"
    errors = sorted(
        Draft202012Validator(json.loads(release_schema.read_text(encoding="utf-8"))).iter_errors(verdict),
        key=lambda e: list(e.path),
    )
    if errors:
        raise ContractValidationError(f"release verdict: {errors[0].message}")
    out = run_dir / "release-verdict.json"
    out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verdict["path"] = str(out)
    verdict["scenario_results_sha256"] = sha256_file(scenario_path)
    return verdict
