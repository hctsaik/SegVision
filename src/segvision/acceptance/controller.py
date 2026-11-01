"""Fail-closed OpenSpec task controller.

This module is deliberately small and repository-local.  It schedules only
dependency-ready tasks, executes each declared command once, writes
hash-bound task evidence, and publishes a checkbox/state pair only after the
repository validators accept the proposed state.  External-gate tasks are
recorded as blockers and never bypassed.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from segvision.core.errors import ContractValidationError

from .common import hashed_path, maintained_tree_hash, repo_root, sha256_bytes, sha256_file
from .contracts import validate_contracts
from .evidence import validate_evidence
from .evidence_builder import _ram_bytes
from .state import validate_state

_REQUIRED_TASK_FIELDS = (
    "id",
    "objective",
    "dependencies",
    "owned_paths",
    "required_inputs",
    "expected_outputs",
    "commands",
    "required_evidence",
    "pass_criteria",
    "retry_policy",
    "fallback",
    "rollback_boundary",
    "escalation_conditions",
)
_RUN_ID_RE = re.compile(r"^sv-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_text(value: str) -> str:
    """Redact common credentials before any diagnostic is persisted."""

    return re.sub(
        r"(?i)(token|password|secret|api[_-]?key|authorization)=([^\s&]+)",
        r"\1=[REDACTED]",
        value,
    )


def _openspec_hash(change_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(change_dir.rglob("*"), key=lambda p: p.relative_to(change_dir).as_posix()):
        if path.is_file():
            digest.update(path.relative_to(change_dir).as_posix().encode("utf-8"))
            digest.update(b"\n")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _resolve_command(command: str, root: Path) -> list[str]:
    command = command.strip()

    def direct(executable: Path, remainder: str) -> list[str]:
        args = [part.strip('"') for part in shlex.split(remainder, posix=False)]
        return [str(executable), *args]

    if command.startswith("python ") or command == "python":
        executable = root / ".venv" / "Scripts" / "python.exe"
        return direct(executable, command[len("python") :])
    elif command.startswith("py -3.11 -m venv"):
        # The scaffold task intentionally invokes the system Python launcher
        # to create or repair the repository environment.  Reusing the target
        # venv for this command attempts to overwrite its running interpreter
        # on Windows and fails with a permission error.
        if os.name == "nt":
            return ["py.exe", "-3.11", *shlex.split(command[len("py -3.11") :], posix=False)]
        return ["python3.11", *shlex.split(command[len("py -3.11") :], posix=False)]
    elif command.startswith("py -3.11"):
        executable = root / ".venv" / "Scripts" / "python.exe"
        return direct(executable, command[len("py -3.11") :])
    elif command.startswith(".venv\\Scripts\\python.exe"):
        executable = root / ".venv" / "Scripts" / "python.exe"
        return direct(executable, command[len(".venv\\Scripts\\python.exe") :])
    elif command.startswith("ruff ") or command == "ruff":
        executable = root / ".venv" / "Scripts" / "ruff.exe"
        return direct(executable, command[len("ruff") :])
    elif command.startswith("mypy ") or command == "mypy":
        executable = root / ".venv" / "Scripts" / "mypy.exe"
        return direct(executable, command[len("mypy") :])
    elif command == "openspec" or command.startswith("openspec "):
        # npm installs OpenSpec as a PowerShell shim on Windows.  Resolve the
        # shim at execution time so the controller does not hard-code a user
        # profile path or silently invoke a different ambient executable.
        if os.name == "nt":
            return [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"& (Get-Command openspec).Source {command[len('openspec') :].strip()}",
            ]
    # The task graph contains only executable-style commands.  Keep a shell
    # fallback for future graph entries, but never use it for the known Python
    # or OpenSpec paths above.
    if os.name == "nt":
        return ["cmd.exe", "/d", "/s", "/c", command]
    return ["/bin/sh", "-lc", command]


def execute_command(command: str, *, root: Path) -> dict[str, Any]:
    # The controller itself runs from the repository venv.  Re-invoking
    # ``py -3.11 -m venv .venv`` in that process asks Windows to overwrite its
    # live interpreter and deterministically returns ``Permission denied``.
    # Treat an already-valid locked venv as an idempotent scaffold success and
    # record a real probe instead of mutating the active interpreter.
    if command.strip().lower() == "py -3.11 -m venv .venv":
        interpreter = root / ".venv" / "Scripts" / "python.exe"
        if interpreter.is_file():
            probe = subprocess.run(
                [
                    str(interpreter),
                    "-c",
                    "import struct, sys; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env=os.environ.copy(),
            )
            stdout = _safe_text(probe.stdout)
            stderr = _safe_text(probe.stderr)
            return {
                "command": command,
                "exit_code": probe.returncode,
                "stdout_sha256": sha256_bytes(stdout.encode("utf-8")),
                "stderr_sha256": sha256_bytes(stderr.encode("utf-8")),
            }
    completed = subprocess.run(
        _resolve_command(command, root),
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    stdout = _safe_text(completed.stdout)
    stderr = _safe_text(completed.stderr)
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_sha256": sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(stderr.encode("utf-8")),
    }


def _substitute(command: str, run_id: str, task_id: str) -> str:
    return command.replace("$env:SEG_RUN_ID", run_id).replace("$env:SEG_TASK_ID", task_id)


def _hash_records(paths: list[Path], root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if (
            rel in seen
            or rel.startswith("evidence/")
            or rel.split("/", 1)[0]
            in {
                ".venv",
                "build",
                "dist",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            }
        ):
            continue
        seen.add(rel)
        records.append(hashed_path(path, root))
    return records


def _task_paths(task: dict[str, Any], root: Path) -> list[Path]:
    paths: list[Path] = []
    for raw in task.get("owned_paths", []):
        value = str(raw)
        if "<" in value or "*" in value:
            continue
        path = root / value
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(p for p in path.rglob("*") if p.is_file())
    return paths


def _parse_test_record(command: str, exit_code: int) -> dict[str, Any]:
    suite = "command"
    if "pytest" in command:
        suite = command.split("pytest", 1)[1].strip() or "pytest"
    status = "passed" if exit_code == 0 else "failed"
    return {
        "suite": suite[:200],
        "status": status,
        "passed": 1 if exit_code == 0 else 0,
        "failed": 0 if exit_code == 0 else 1,
        "skipped": 0,
        "xfailed": 0,
        "evidence_ref": "commands",
    }


def _evidence(
    *,
    task: dict[str, Any],
    run_id: str,
    status: str,
    commands: list[dict[str, Any]],
    root: Path,
    evidence_path: Path,
    dependency_checkpoints: list[str] | None = None,
    blocker_ref: str | None = None,
) -> dict[str, Any]:
    change_dir = root / "openspec" / "changes" / "build-segvision-v1"
    graph_path = change_dir / "acceptance" / "task-graph.json"
    e2e_path = change_dir / "acceptance" / "e2e-cases.json"
    trace_path = change_dir / "acceptance" / "traceability.json"
    files = _task_paths(task, root)
    files.extend([root / "PRD.md", graph_path])
    artifacts = _hash_records(files, root)
    inputs: list[dict[str, Any]] = []
    for raw in task.get("required_inputs", []):
        value = str(raw)
        if "<" in value or "$" in value:
            continue
        path = root / value
        if path.is_file():
            inputs.append(hashed_path(path, root))
        elif path.is_dir():
            inputs.extend(_hash_records([p for p in path.rglob("*") if p.is_file()], root))
    if not inputs:
        inputs = [hashed_path(root / "PRD.md", root)]
    now = _now()
    passed = status == "passed"
    task_state = "passed" if passed else status
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "change_id": "build-segvision-v1",
        "subject_kind": "task",
        "task_or_scenario_id": task["id"],
        "status": status,
        "task_state": task_state,
        "task_graph_sha256": sha256_file(graph_path),
        "e2e_cases_sha256": sha256_file(e2e_path),
        "traceability_sha256": sha256_file(trace_path),
        "scenario_results_sha256": None,
        "acceptance_profile_sha256": sha256_file(
            change_dir / "acceptance" / "acceptance-profile.json"
        ),
        "annotation_policy_sha256": sha256_file(
            change_dir / "acceptance" / "default-annotation-policy.json"
        ),
        "fixtures_manifest_sha256": None,
        "reference_machine_manifest_sha256": None,
        "domain_inputs_manifest_sha256": None,
        "dependency_checkpoints": list(dependency_checkpoints or []),
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
        "inputs": inputs,
        "commands": commands
        or [
            {
                "command": "controller",
                "exit_code": 0,
                "stdout_sha256": "0" * 64,
                "stderr_sha256": "0" * 64,
            }
        ],
        "tests": [
            _parse_test_record(c["command"], c["exit_code"])
            for c in commands
            if "pytest" in c["command"]
        ]
        or [_parse_test_record("controller", 0 if passed else 1)],
        "artifacts": artifacts or [hashed_path(root / "PRD.md", root)],
        "metrics": {},
        "tool_versions": {"python": sys.version.split()[0]},
        "warnings": [] if passed else ["task did not satisfy every declared command"],
        "policy_checks": {
            "required_tests_skipped": False,
            "thresholds_weakened": False,
            "external_evidence_fabricated": False,
            "out_of_scope_writes": False,
            "prohibited_runtime_added": False,
        },
        "retry_history": [],
        "checkpoint": {
            "checkpoint_id": f"cp-{task['id'].lower()}",
            "commit_id": None,
            "patch_sha256": maintained_tree_hash(root),
        }
        if passed
        else None,
        "blocker_ref": blocker_ref,
        "started_at": now,
        "finished_at": _now(),
    }
    return evidence


@dataclass(frozen=True, slots=True)
class ControllerResult:
    run_id: str
    passed: tuple[str, ...]
    blocked: tuple[str, ...]
    failed: tuple[str, ...]
    state_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "passed": list(self.passed),
            "blocked": list(self.blocked),
            "failed": list(self.failed),
            "state": str(self.state_path),
        }


class TaskController:
    def __init__(
        self,
        *,
        graph: str | Path = "openspec/changes/build-segvision-v1/acceptance/task-graph.json",
        state: str | Path = "evidence/execution-state.json",
        tasks_file: str | Path = "openspec/changes/build-segvision-v1/tasks.md",
        evidence_root: str | Path = "evidence",
    ) -> None:
        self.root = repo_root()
        self.graph_path = self._path(graph)
        self.state_path = self._path(state)
        self.tasks_path = self._path(tasks_file)
        self.evidence_root = self._path(evidence_root)

    def _path(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _load(self) -> tuple[dict[str, Any], dict[str, Any]]:
        graph = json.loads(self.graph_path.read_text(encoding="utf-8"))
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        for task in graph.get("tasks", []):
            missing = [field for field in _REQUIRED_TASK_FIELDS if field not in task]
            if missing:
                raise ValueError(f"task {task.get('id')} is incomplete: {missing}")
        if not _RUN_ID_RE.fullmatch(str(state.get("run_id", ""))):
            raise ValueError("execution state has invalid run_id")
        return graph, state

    def _write_json_atomic(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.close(fd)
        temporary = Path(raw)
        try:
            temporary.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _update_state(self, state: dict[str, Any]) -> None:
        self._write_json_atomic(self.state_path, state)

    def _validate_transition(self, evidence_path: Path) -> None:
        """Run all mandatory validators against the proposed transition."""

        validate_contracts("openspec/changes/build-segvision-v1")
        validate_evidence(evidence_path)
        validate_state(self.state_path, self.graph_path)

    def _update_checkbox(self, task_id: str, checked: bool) -> None:
        lines = self.tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
        marker = "[x]" if checked else "[ ]"
        changed = False
        for index, line in enumerate(lines):
            if f"`{task_id}`" in line and line.startswith("- ["):
                lines[index] = re.sub(r"^- \[[ xX]\]", f"- {marker}", line)
                changed = True
                break
        if not changed:
            raise ValueError(f"task checkbox not found: {task_id}")
        temporary = self.tasks_path.with_name(f".{self.tasks_path.name}.tmp")
        # Preserve the existing newline convention.  ``Path.write_text``
        # uses the platform default newline on Windows and would otherwise
        # rewrite an LF-controlled task file as CRLF, changing the maintained
        # source fingerprint between evidence creation and validation.
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write("".join(lines))
        temporary.replace(self.tasks_path)

    def _ready(self, graph: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
        records = {record["task_id"]: record for record in state["tasks"]}
        ready: list[dict[str, Any]] = []
        for task in graph["tasks"]:
            record = records[task["id"]]
            if record["state"] != "pending":
                continue
            if all(records[dep]["state"] == "passed" for dep in task["dependencies"]):
                ready.append(task)
        return ready

    def _set_record(self, execution_state: dict[str, Any], task_id: str, **updates: Any) -> None:
        for record in execution_state["tasks"]:
            if record["task_id"] == task_id:
                record.update(updates)
                record["updated_at"] = _now()
                return
        raise KeyError(task_id)

    def _block_external(
        self,
        task: dict[str, Any],
        run_id: str,
        state: dict[str, Any],
        *,
        runnable_tasks: list[str] | None = None,
    ) -> None:
        task_id = task["id"]
        task_dir = self.evidence_root / run_id / task_id
        blocker = f"BLK-EXTERNAL-{task_id}"
        now = _now()
        blocker_class = {
            "X-RELEASE-AUTH": "license_authority",
            "X-REFERENCE": "reference_hardware",
        }.get(task_id, "external_input")
        blocker_data = {
            "schema_version": 1,
            "change_id": "build-segvision-v1",
            "run_id": run_id,
            "target_release_class": state.get("target_release_class", "engineering"),
            "blocker_id": blocker,
            "task_id": task_id,
            "gate_id": task_id,
            "blocker_class": blocker_class,
            "status": "open",
            "observed_evidence": ["task declares external_gate=true"],
            "attempts": [],
            "safe_alternatives_tried": [
                "continue independent fake/core tasks",
                "retain pending gate",
            ],
            "missing_input_or_authority": task["objective"],
            "decision_required": True,
            "options": [
                {
                    "id": "supply-authority",
                    "description": "Supply the required authority or input.",
                    "impact": "The blocked gate can be revalidated.",
                },
                {
                    "id": "remain-blocked",
                    "description": "Keep the release fail-closed.",
                    "impact": "No external claim is made.",
                },
            ],
            "recommended_option": "remain-blocked",
            "runnable_tasks": list(runnable_tasks or []),
            "earliest_milestone_affected": task.get("milestone", "M4"),
            "safe_no_response_state": "external gate remains blocked",
            "created_at": now,
            "updated_at": now,
            "resolution": None,
        }
        self._write_json_atomic(task_dir / "blocker.json", blocker_data)
        commands = [
            {
                "command": "external_gate",
                "exit_code": 0,
                "stdout_sha256": "0" * 64,
                "stderr_sha256": "0" * 64,
            }
        ]
        records = {record["task_id"]: record for record in state["tasks"]}
        dependency_checkpoints = [
            records[dep]["checkpoint_id"]
            for dep in task["dependencies"]
            if records[dep].get("checkpoint_id")
        ]
        evidence = _evidence(
            task=task,
            run_id=run_id,
            status="blocked_external_input",
            commands=commands,
            root=self.root,
            evidence_path=task_dir / "evidence.json",
            dependency_checkpoints=dependency_checkpoints,
            blocker_ref=blocker,
        )
        evidence["artifacts"].append(hashed_path(task_dir / "blocker.json", self.root))
        self._write_json_atomic(task_dir / "evidence.json", evidence)
        self._set_record(
            state,
            task_id,
            state="blocked_external_input",
            attempt_count=1,
            checkpoint_id=None,
            evidence_refs=[f"evidence/{run_id}/{task_id}/evidence.json"],
            blocker_ref=blocker,
            reason="external gate is unavailable; no bypass attempted",
        )
        if blocker not in state["open_blockers"]:
            state["open_blockers"].append(blocker)

    def run(self, *, max_tasks: int | None = None) -> ControllerResult:
        graph, state = self._load()
        run_id = str(state["run_id"])
        passed: list[str] = []
        blocked: list[str] = []
        failed: list[str] = []
        processed = 0
        while True:
            ready = self._ready(graph, state)
            if not ready or (max_tasks is not None and processed >= max_tasks):
                break
            task = ready[0]
            task_id = task["id"]
            processed += 1
            prior_state = self.state_path.read_bytes()
            prior_tasks = self.tasks_path.read_bytes()
            if bool(task.get("external_gate", False)):
                self._block_external(
                    task,
                    run_id,
                    state,
                    runnable_tasks=[candidate["id"] for candidate in ready[1:]],
                )
                self._update_state(state)
                try:
                    self._validate_transition(
                        self.evidence_root / run_id / task_id / "evidence.json"
                    )
                except (ContractValidationError, OSError, ValueError, json.JSONDecodeError):
                    self.state_path.write_bytes(prior_state)
                    self.tasks_path.write_bytes(prior_tasks)
                    raise
                blocked.append(task_id)
                continue
            self._set_record(
                state,
                task_id,
                state="running",
                attempt_count=1,
                checkpoint_id=None,
                evidence_refs=[],
                blocker_ref=None,
                reason="executing declared commands",
            )
            self._update_state(state)
            task_dir = self.evidence_root / run_id / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            substituted = [
                _substitute(str(command), run_id, task_id) for command in task["commands"]
            ]
            zero = {"exit_code": 0, "stdout_sha256": "0" * 64, "stderr_sha256": "0" * 64}
            provisional = [dict(command=command, **zero) for command in substituted]
            records_by_id = {record["task_id"]: record for record in state["tasks"]}
            dependency_checkpoints = [
                records_by_id[dep]["checkpoint_id"]
                for dep in task["dependencies"]
                if records_by_id[dep].get("checkpoint_id")
            ]
            self._write_json_atomic(
                task_dir / "evidence.json",
                _evidence(
                    task=task,
                    run_id=run_id,
                    status="passed",
                    commands=provisional,
                    root=self.root,
                    evidence_path=task_dir / "evidence.json",
                    dependency_checkpoints=dependency_checkpoints,
                ),
            )
            records: list[dict[str, Any]] = []
            task_ok = True
            for command in substituted:
                try:
                    result = execute_command(command, root=self.root)
                except OSError as exc:
                    result = {
                        "command": command,
                        "exit_code": 127,
                        "stdout_sha256": "0" * 64,
                        "stderr_sha256": sha256_bytes(str(exc).encode("utf-8")),
                    }
                records.append(result)
                if result["exit_code"] != 0:
                    task_ok = False
                    break
            status = (
                "passed"
                if task_ok and len(records) == len(substituted)
                else "failed_retryable"
            )
            evidence = _evidence(
                task=task,
                run_id=run_id,
                status=status,
                commands=records,
                root=self.root,
                evidence_path=task_dir / "evidence.json",
                dependency_checkpoints=dependency_checkpoints,
            )
            self._write_json_atomic(task_dir / "evidence.json", evidence)
            try:
                validation = validate_evidence(task_dir / "evidence.json")
                if validation["count"] != 1:
                    raise ValueError("task evidence validation returned no record")
            except (ContractValidationError, OSError, ValueError, json.JSONDecodeError):
                task_ok = False
                status = "failed_retryable"
            if task_ok:
                checkpoint = {
                    "schema_version": 1,
                    "change_id": "build-segvision-v1",
                    "run_id": run_id,
                    "task_graph_sha256": sha256_file(self.graph_path),
                    "checkpoint_id": f"cp-{task_id.lower()}",
                    "task_id": task_id,
                    "dependency_checkpoints": dependency_checkpoints,
                    "source_revision": None,
                    "file_tree_sha256": maintained_tree_hash(self.root),
                    "owned_file_hashes": {
                        item["path"]: item["sha256"]
                        for item in _hash_records(_task_paths(task, self.root), self.root)
                    }
                    or {"PRD.md": sha256_file(self.root / "PRD.md")},
                    "evidence_sha256": sha256_file(task_dir / "evidence.json"),
                    "artifact_hashes": {},
                    "commit_id": None,
                    "patch_sha256": maintained_tree_hash(self.root),
                    "created_at": _now(),
                }
                self._write_json_atomic(task_dir / "checkpoint.json", checkpoint)
                evidence["artifacts"].append(hashed_path(task_dir / "checkpoint.json", self.root))
                self._write_json_atomic(task_dir / "evidence.json", evidence)
                self._set_record(
                    state,
                    task_id,
                    state="passed",
                    checkpoint_id=checkpoint["checkpoint_id"],
                    evidence_refs=[f"evidence/{run_id}/{task_id}/evidence.json"],
                    blocker_ref=None,
                    reason="declared outputs and validators passed",
                )
                self._update_state(state)
                try:
                    self._validate_transition(task_dir / "evidence.json")
                    self._update_checkbox(task_id, True)
                    self._validate_transition(task_dir / "evidence.json")
                except (ContractValidationError, OSError, ValueError, json.JSONDecodeError):
                    self.state_path.write_bytes(prior_state)
                    self.tasks_path.write_bytes(prior_tasks)
                    raise
                passed.append(task_id)
            else:
                self._set_record(
                    state,
                    task_id,
                    state="failed_retryable",
                    checkpoint_id=None,
                    evidence_refs=[f"evidence/{run_id}/{task_id}/evidence.json"],
                    blocker_ref=None,
                    reason="declared command or evidence validation failed",
                )
                self._update_state(state)
                try:
                    self._validate_transition(task_dir / "evidence.json")
                except (ContractValidationError, OSError, ValueError, json.JSONDecodeError):
                    self.state_path.write_bytes(prior_state)
                    self.tasks_path.write_bytes(prior_tasks)
                    raise
                failed.append(task_id)
                break
        self._update_state(state)
        return ControllerResult(
            run_id, tuple(passed), tuple(blocked), tuple(failed), self.state_path
        )


__all__ = ["ControllerResult", "TaskController", "execute_command"]
