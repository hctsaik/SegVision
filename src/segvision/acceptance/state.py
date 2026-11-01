"""Execution-state and task-graph validator."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from segvision.core.errors import ContractValidationError

from .common import repo_root, sha256_file


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_state(
    state: str | Path,
    graph: str | Path = "openspec/changes/build-segvision-v1/acceptance/task-graph.json",
) -> dict[str, Any]:
    root = repo_root()
    sp = Path(state)
    gp = Path(graph)
    if not sp.is_absolute():
        sp = root / sp
    if not gp.is_absolute():
        gp = root / gp
    if not sp.exists() or not gp.exists():
        raise ContractValidationError("state or graph not found")
    graph_data = _read(gp)
    state_data = _read(sp)
    schema_dir = gp.parent
    for name, data in (
        ("task-graph.schema.json", graph_data),
        ("execution-state.schema.json", state_data),
    ):
        schema = _read(schema_dir / name)
        errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
        if errors:
            raise ContractValidationError(f"{name}: {errors[0].message}")
    tasks = graph_data["tasks"]
    graph_ids = {t["id"] for t in tasks}
    state_tasks = {t["task_id"]: t for t in state_data["tasks"]}
    if graph_ids != set(state_tasks):
        raise ContractValidationError("state/task graph parity mismatch")
    if state_data["task_graph_sha256"].lower() != sha256_file(gp).lower():
        raise ContractValidationError("task graph hash mismatch")
    for task in tasks:
        state_rec = state_tasks[task["id"]]
        if state_rec["dependencies"] != task["dependencies"]:
            raise ContractValidationError(f"dependency mismatch for {task['id']}")
        if state_rec["state"] == "passed" and any(
            state_tasks[d]["state"] != "passed" for d in task["dependencies"]
        ):
            raise ContractValidationError(f"passed task has unpassed dependency: {task['id']}")
        if state_rec["state"] in {"pending", "runnable"} and state_rec["attempt_count"] != 0:
            raise ContractValidationError(f"pending task has attempts: {task['id']}")
    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {t["id"]: t for t in tasks}

    def visit(tid: str) -> None:
        if tid in visiting:
            raise ContractValidationError(f"cycle at {tid}")
        if tid in visited:
            return
        visiting.add(tid)
        for dep in by_id[tid]["dependencies"]:
            visit(dep)
        visiting.remove(tid)
        visited.add(tid)

    for tid in by_id:
        visit(tid)
    if state_data["project_state"] == "in_progress" and state_data["latest_verdict"] is not None:
        raise ContractValidationError("in-progress state cannot carry verdict")
    return {
        "state": str(sp),
        "tasks": len(tasks),
        "passed": sum(t["state"] == "passed" for t in state_data["tasks"]),
        "project_state": state_data["project_state"],
    }


def bootstrap_state(
    run_id: str,
    graph: str | Path = "openspec/changes/build-segvision-v1/acceptance/task-graph.json",
    output: str | Path = "evidence/execution-state.json",
) -> dict[str, Any]:
    """Create the one-time pending execution state for a fresh run."""
    import datetime

    if not re.fullmatch(r"sv-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", run_id):
        raise ContractValidationError("invalid run id")
    root = repo_root()
    gp = Path(graph)
    gp = gp if gp.is_absolute() else root / gp
    data = _read(gp)
    now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    tasks = [
        {
            "task_id": t["id"],
            "state": "pending",
            "dependencies": t["dependencies"],
            "attempt_count": 0,
            "checkpoint_id": None,
            "evidence_refs": [],
            "blocker_ref": None,
            "reason": None,
            "updated_at": now,
        }
        for t in data["tasks"]
    ]
    from .common import maintained_tree_hash

    state = {
        "schema_version": 1,
        "change_id": "build-segvision-v1",
        "run_id": run_id,
        "task_graph_sha256": sha256_file(gp),
        "source": {
            "revision": None,
            "file_tree_sha256": maintained_tree_hash(root),
            "dirty_paths": [],
        },
        "target_release_class": "engineering",
        "project_state": "in_progress",
        "tasks": tasks,
        "open_blockers": [],
        "latest_verdict": None,
        "started_at": now,
        "updated_at": now,
    }
    out = Path(output)
    out = out if out.is_absolute() else root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state
