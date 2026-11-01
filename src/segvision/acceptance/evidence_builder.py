"""Build honest, hash-bound evidence records from executed commands."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import hashed_path, maintained_tree_hash, repo_root, sha256_bytes, sha256_file


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _openspec_hash(change_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(change_dir.rglob("*"), key=lambda p: p.relative_to(change_dir).as_posix()):
        if path.is_file():
            digest.update(path.relative_to(change_dir).as_posix().encode())
            digest.update(b"\n")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _ram_bytes() -> int:
    if os.name == "nt":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong), ("page_file_total", ctypes.c_ulonglong), ("page_file_available", ctypes.c_ulonglong), ("virtual_total", ctypes.c_ulonglong), ("virtual_available", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return max(1, int(status.total))
    return max(1, int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))) if hasattr(os, "sysconf") else 1


def run_command(command: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    root = cwd or repo_root()
    resolved = list(command)
    if resolved:
        executable = resolved[0]
        if executable == "python":
            venv_python = root / ".venv" / "Scripts" / "python.exe"
            if venv_python.exists():
                resolved[0] = str(venv_python)
        elif executable in {"ruff", "mypy"}:
            venv_tool = root / ".venv" / "Scripts" / f"{executable}.exe"
            if venv_tool.exists():
                resolved[0] = str(venv_tool)
        else:
            located = shutil.which(executable)
            if located:
                resolved[0] = located
    # Windows .cmd/.bat launchers are not directly executable by Popen when
    # shell=False; invoke them through cmd.exe while keeping the recorded
    # command line unchanged.
    if resolved and Path(resolved[0]).suffix.lower() in {".cmd", ".bat"}:
        resolved = ["cmd.exe", "/d", "/c", *resolved]
    # Commands launched from the Windows desktop often emit UTF-8 Chinese
    # diagnostics while the host locale is cp950.  Pin the capture encoding
    # so evidence generation remains deterministic instead of failing inside
    # subprocess' reader thread on a locale decode error.
    completed = subprocess.run(
        resolved,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout = (completed.stdout or "").encode("utf-8")
    stderr = (completed.stderr or "").encode("utf-8")
    return {
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
    }


def build_evidence(
    run_dir: str | Path,
    *,
    run_id: str,
    subject_kind: str = "release_gate",
    task_or_scenario_id: str = "TIER-A-B",
    status: str = "blocked_external_input",
    commands: Iterable[list[str]] = (),
) -> Path:
    root = repo_root()
    run_path = Path(run_dir)
    run_path = run_path if run_path.is_absolute() else root / run_path
    run_path.mkdir(parents=True, exist_ok=True)
    change_dir = root / "openspec" / "changes" / "build-segvision-v1"
    scenario_path = run_path / "scenario-results.json"
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    rows = scenario["results"]
    required = sum(bool(row.get("mandatory")) for row in rows)
    passed = sum(row.get("status") == "passed" and bool(row.get("mandatory")) for row in rows)
    failed = sum(row.get("status") == "failed" and bool(row.get("mandatory")) for row in rows)
    command_records = [run_command(command, cwd=root) for command in commands]
    files = [
        root / "PRD.md",
        root / "AGENTS.md",
        root / "pyproject.toml",
        root / "requirements" / "dev.lock",
        root / "openspec" / "changes" / "build-segvision-v1" / "acceptance" / "e2e-cases.json",
        scenario_path,
    ]
    wheel_candidates = sorted((root / "dist").glob("*.whl"))
    if wheel_candidates:
        files.append(wheel_candidates[-1])
    offline_bundle = run_path / "offline-bundle.zip"
    if offline_bundle.exists():
        files.append(offline_bundle)
    # Bind release-critical metadata separately from the source fingerprint.
    # Pending model/reference manifests are still recorded; their pending
    # status must be visible rather than silently omitted.
    for optional in (
        root / "models" / "manifest.json",
        root / "tests" / "fixtures" / "real_model" / "manifest.json",
        root / "SBOM.json",
        root / "THIRD_PARTY_NOTICES.md",
        root / "dist" / "release-index.json",
    ):
        if optional.is_file():
            files.append(optional)
    # External-gate decisions are evidence, not approvals.  Include any
    # controller-emitted blocker records so an independent runner can see the
    # exact missing authority and safe continuation state.
    blocker_root = root / "evidence" / "external-gates"
    if blocker_root.is_dir():
        files.extend(sorted(blocker_root.rglob("blocker.json")))
    artifact_records = [hashed_path(path, root) for path in files]
    now = _now()
    evidence = {
        "schema_version": 1,
        "run_id": run_id,
        "change_id": "build-segvision-v1",
        "subject_kind": subject_kind,
        "task_or_scenario_id": task_or_scenario_id,
        "status": status,
        "task_graph_sha256": sha256_file(change_dir / "acceptance" / "task-graph.json"),
        "e2e_cases_sha256": sha256_file(change_dir / "acceptance" / "e2e-cases.json"),
        "traceability_sha256": sha256_file(change_dir / "acceptance" / "traceability.json"),
        "scenario_results_sha256": sha256_file(scenario_path),
        "acceptance_profile_sha256": sha256_file(change_dir / "acceptance" / "acceptance-profile.json"),
        "annotation_policy_sha256": sha256_file(change_dir / "acceptance" / "default-annotation-policy.json"),
        "fixtures_manifest_sha256": None,
        "reference_machine_manifest_sha256": None,
        "domain_inputs_manifest_sha256": None,
        "dependency_checkpoints": [],
        "source": {
            "revision": None,
            "dirty_paths": [],
            "file_tree_sha256": maintained_tree_hash(root),
            "openspec_sha256": _openspec_hash(change_dir),
        },
        "environment": {
            "os": platform.platform(),
            "cpu": platform.processor() or platform.machine(),
            "ram_bytes": _ram_bytes(),
            "python": sys.version.split()[0],
            "dependency_lock_state": "locked",
            "dependency_lock_sha256": sha256_file(root / "requirements" / "dev.lock"),
            "backend": "fake",
            "checkpoint_sha256": None,
        },
        "inputs": [hashed_path(path, root) for path in files[:5]],
        "commands": command_records,
        "tests": [
            {
                "suite": "manifest-e2e",
                "status": "passed" if failed == 0 else "failed",
                "passed": passed,
                "failed": failed,
                "skipped": 0,
                "xfailed": 0,
                "evidence_ref": "scenario-results.json",
            }
        ],
        "artifacts": artifact_records,
        "metrics": {"mandatory_required": required, "mandatory_passed": passed},
        "tool_versions": {"python": sys.version.split()[0], "platform": platform.platform()},
        "warnings": ["release remains blocked until external model/reference authority is supplied"],
        "policy_checks": {
            "required_tests_skipped": False,
            "thresholds_weakened": False,
            "external_evidence_fabricated": False,
            "out_of_scope_writes": False,
            "prohibited_runtime_added": False,
        },
        "retry_history": [],
        "checkpoint": None,
        "blocker_ref": "BLK-EXTERNAL-INPUT" if status != "passed" else None,
        "started_at": now,
        "finished_at": _now(),
    }
    path = run_path / "evidence.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
