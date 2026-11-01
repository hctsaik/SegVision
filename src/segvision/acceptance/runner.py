"""Manifest-driven E2E case and release orchestration utilities."""

from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from segvision.core.errors import ContractValidationError

from .common import repo_root, sha256_file


def validate_manifest(path: str | Path) -> dict[str, Any]:
    root = repo_root()
    p = Path(path)
    p = p if p.is_absolute() else root / p
    data = json.loads(p.read_text(encoding="utf-8"))
    # Most acceptance manifests live beside their schema.  Release assets and
    # fixture manifests live under the repository but are still normative, so
    # resolve their schema from the OpenSpec acceptance catalog as well.
    schema_path = p.with_name(p.stem + ".schema.json")
    if not schema_path.exists():
        schema_stem = {
            ("models", "manifest.json"): "model-manifest.schema.json",
            ("real_model", "manifest.json"): "fixture-manifest.schema.json",
        }.get((p.parent.name, p.name), f"{p.stem}.schema.json")
        schema_path = (
            root
            / "openspec"
            / "changes"
            / "build-segvision-v1"
            / "acceptance"
            / schema_stem
        )
    if not p.is_file():
        raise ContractValidationError(f"manifest not found: {p}")
    if schema_path.exists():
        errors = sorted(
            Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).iter_errors(
                data
            ),
            key=lambda e: list(e.path),
        )
        if errors:
            raise ContractValidationError(f"manifest: {errors[0].message}")
    if p.name == "e2e-cases.json":
        cases = data.get("cases", data if isinstance(data, list) else [])
        ids = [c.get("id") for c in cases]
        if len(ids) != len(set(ids)):
            raise ContractValidationError("duplicate E2E case IDs")
        for c in cases:
            target = c.get("test_target", "")
            if not re.match(r"^tests/.+\.py::test_[a-z0-9_]+$", target):
                raise ContractValidationError(f"invalid test target: {target}")
    if p.name == "manifest.json" and p.parent.name == "real_model":
        fixtures = data.get("fixtures", [])
        for fixture in fixtures:
            raw_path = str(fixture.get("path", ""))
            fixture_path = Path(raw_path)
            if fixture_path.is_absolute() or ".." in fixture_path.parts:
                raise ContractValidationError(f"unsafe fixture path: {raw_path}")
            resolved = root / fixture_path
            if not resolved.is_file():
                raise ContractValidationError(f"fixture not found: {raw_path}")
            digest = sha256_file(resolved)
            if digest.lower() != str(fixture.get("sha256", "")).lower():
                raise ContractValidationError(f"fixture hash mismatch: {raw_path}")
            expected = fixture.get("expected_sha256")
            if expected is not None and str(expected).lower() != digest.lower():
                raise ContractValidationError(f"fixture expected hash mismatch: {raw_path}")
    if p.name == "manifest.json" and p.parent.name == "models":
        # Pending entries are valid metadata and deliberately remain excluded
        # from the runtime until explicit approval; schema validation above
        # still catches missing source/license/authority fields.
        entries = data.get("entries", [])
        if not any(entry.get("artifact_kind") == "model_code" for entry in entries):
            raise ContractValidationError("model manifest lacks model_code entry")
        if not any(entry.get("artifact_kind") == "model_weights" for entry in entries):
            raise ContractValidationError("model manifest lacks model_weights entry")
    return {
        "path": str(p),
        "sha256": sha256_file(p),
        "cases": len(data.get("cases", [])) if isinstance(data, dict) else 0,
    }


def run_case(target: str, *, cwd: str | Path | None = None) -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", target, "-q"]
    proc = subprocess.run(command, cwd=cwd or repo_root(), capture_output=True, text=True, check=False)
    return {
        "test_target": target,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    now = datetime.now(UTC)
    # A run ID must remain unique even when Tier A/B/C runners start in the
    # same second (for example, from a CI fan-out).  The timestamp is human
    # readable; the random suffix prevents evidence directories colliding.
    return f"sv-{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def run_manifest(
    manifest: str | Path,
    *,
    tier: str | None = None,
    profile: str | Path | None = None,
    output_dir: str | Path = "evidence",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute each selected manifest case once and emit schema-shaped results.

    The runner deliberately records one subprocess result per case.  It never
    retries or changes a target, so a failed case cannot be hidden by a broad
    suite-level green result.
    """
    root = repo_root()
    manifest_path = Path(manifest)
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    validate_manifest(manifest_path)
    if profile is not None:
        from .profile import load_acceptance_profile

        loaded_profile = load_acceptance_profile(profile)
        if loaded_profile.profile_id != "segvision-v1-default":
            raise ContractValidationError("unsupported acceptance profile")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = list(data.get("cases", []))
    if tier is not None:
        if tier not in {"A", "B", "C"}:
            raise ContractValidationError(f"invalid tier: {tier}")
        cases = [case for case in cases if case.get("tier") == tier]
    if not cases:
        raise ContractValidationError("selected tier has no cases")
    run_id = run_id or _run_id()
    if not re.fullmatch(r"sv-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", run_id):
        raise ContractValidationError("invalid run id")
    started = _timestamp()
    results: list[dict[str, Any]] = []
    for case in cases:
        case_started = _timestamp()
        execution = run_case(case["test_target"], cwd=root)
        passed = execution["exit_code"] == 0
        case_finished = _timestamp()
        results.append(
            {
                "case_id": case["id"],
                "test_target": case["test_target"],
                "tier": case["tier"],
                "mandatory": bool(case.get("mandatory", False)),
                "status": "passed" if passed else "failed",
                "attempt_count": 1,
                "started_at": case_started,
                "finished_at": case_finished,
                "oracle_results": [
                    {
                        "oracle": "pytest_exit_code",
                        "passed": passed,
                        "actual": execution["exit_code"],
                        "evidence_ref": f"cases/{case['id']}/pytest.txt",
                    }
                ],
                "evidence_refs": [f"cases/{case['id']}/pytest.txt"],
                "_execution": execution,
            }
        )
    # Keep subprocess logs outside the schema object and write deterministic
    # machine-readable scenario results for later evidence hashing.
    output_root = Path(output_dir)
    output_root = output_root if output_root.is_absolute() else root / output_root
    run_root = output_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    for result in results:
        log_path = run_root / "cases" / result["case_id"] / "pytest.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        execution = result.pop("_execution")
        log_path.write_text(
            execution["stdout"] + ("\n" + execution["stderr"] if execution["stderr"] else ""),
            encoding="utf-8",
        )
    change_dir = root / "openspec" / "changes" / "build-segvision-v1"
    scenario = {
        "schema_version": 1,
        "run_id": run_id,
        "e2e_cases_sha256": sha256_file(manifest_path),
        "traceability_sha256": sha256_file(change_dir / "acceptance" / "traceability.json"),
        "results": results,
    }
    scenario_path = run_root / "scenario-results.json"
    scenario_path.write_text(json.dumps(scenario, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "run_id": run_id,
        "tier": tier,
        "cases": len(results),
        "passed": sum(r["status"] == "passed" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "scenario_results": str(scenario_path),
        "started_at": started,
        "finished_at": _timestamp(),
    }
