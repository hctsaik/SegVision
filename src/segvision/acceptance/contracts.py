"""Fail-closed validation of the OpenSpec acceptance contract."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from segvision.core.errors import ContractValidationError

from .common import repo_root


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ContractValidationError(f"invalid JSON: {path}: {exc}") from exc


def _validate(instance: Any, schema: Any, path: Path) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        pointer = "/" + "/".join(str(p) for p in e.path)
        raise ContractValidationError(f"{path} {pointer}: {e.message}")


def _ids_from_specs(spec_dir: Path) -> tuple[set[str], set[str]]:
    requirements: set[str] = set()
    scenarios: set[str] = set()
    req_re = re.compile(r"\[([A-Z][A-Z0-9]+-R[0-9]{3})\]")
    scen_re = re.compile(r"\[([A-Z][A-Z0-9]+-R[0-9]{3}-S[0-9]{2,3})\]")
    for path in spec_dir.rglob("spec.md"):
        text = path.read_text(encoding="utf-8")
        requirements.update(req_re.findall(text))
        scenarios.update(scen_re.findall(text))
    return requirements, scenarios


def _task_ids_from_markdown(tasks_path: Path) -> tuple[dict[str, str], set[str]]:
    mapping: dict[str, str] = {}
    checklist: set[str] = set()
    pattern = re.compile(r"^- \[[ xX]\] [^`]*`([^`]+)`")
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            tid = m.group(1)
            checklist.add(tid)
            mapping[tid] = line
    return mapping, checklist


def _canonical_specs_sha256(change_dir: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(
        (change_dir / "specs").rglob("spec.md"),
        key=lambda p: p.relative_to(change_dir).as_posix(),
    ):
        digest.update(path.relative_to(change_dir).as_posix().encode("utf-8"))
        digest.update(b"\n")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _assert_pytest_node(target: str, root: Path) -> None:
    """Verify a manifest target names a real test function without running it."""
    match = re.fullmatch(r"(tests/.+\.py)::(test_[a-z0-9_]+)", target)
    if match is None:
        raise ContractValidationError(f"invalid pytest target: {target}")
    path = root / Path(match.group(1))
    if not path.is_file():
        raise ContractValidationError(f"missing pytest target file: {target}")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ContractValidationError(f"cannot parse pytest target: {target}: {exc}") from exc
    names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if match.group(2) not in names:
        raise ContractValidationError(f"missing pytest node: {target}")


def validate_contracts(change: str | Path) -> dict[str, Any]:
    change_dir = Path(change)
    # Accept a change name from the repository root for CLI ergonomics.  The
    # prescribed command uses ``--change build-segvision-v1`` rather than a
    # filesystem path, so resolve that form even though its basename is the
    # same as the directory name.
    if not change_dir.exists():
        candidate = Path.cwd() / "openspec" / "changes" / str(change)
        if candidate.exists():
            change_dir = candidate
    if not change_dir.exists():
        raise ContractValidationError(f"change does not exist: {change}")
    acceptance = change_dir / "acceptance"
    schema_paths = sorted(acceptance.glob("*.schema.json"))
    schemas = {p.name: _json(p) for p in schema_paths}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    # Validate every normative instance that has a matching schema.
    schema_name_for = {
        "acceptance-profile.json": "acceptance-profile.schema.json",
        "default-annotation-policy.json": "annotation-policy.schema.json",
        "e2e-cases.json": "e2e-cases.schema.json",
        "task-graph.json": "task-graph.schema.json",
        "traceability.json": "traceability.schema.json",
    }
    validated_instances: list[str] = []
    for path in sorted(acceptance.rglob("*.json")):
        if path.name.endswith(".schema.json") or path.name.endswith(".pending.json"):
            continue
        schema_name = schema_name_for.get(path.name)
        if schema_name and schema_name in schemas:
            _validate(_json(path), schemas[schema_name], path)
            validated_instances.append(str(path))
    req_ids, spec_scenarios = _ids_from_specs(change_dir / "specs")
    graph = _json(acceptance / "task-graph.json")
    e2e = _json(acceptance / "e2e-cases.json")
    trace = _json(acceptance / "traceability.json")
    tasks = graph.get("tasks", [])
    graph_ids = [t["id"] for t in tasks]
    if len(graph_ids) != len(set(graph_ids)):
        raise ContractValidationError("duplicate task graph IDs")
    task_map = {t["id"]: t for t in tasks}
    _markdown_map, markdown_ids = _task_ids_from_markdown(change_dir / "tasks.md")
    if set(graph_ids) != markdown_ids:
        raise ContractValidationError(
            f"task/checklist parity mismatch: graph-only={set(graph_ids) - markdown_ids}, checklist-only={markdown_ids - set(graph_ids)}"
        )
    e2e_cases = e2e.get("cases", e2e if isinstance(e2e, list) else [])
    e2e_ids = [c.get("id") for c in e2e_cases]
    if len(e2e_ids) != len(set(e2e_ids)):
        raise ContractValidationError("duplicate E2E IDs")
    if any(not i for i in e2e_ids):
        raise ContractValidationError("E2E case missing id")
    # The executable JSON catalog and the human acceptance table must describe
    # exactly the same cases and real pytest nodes.
    human_ids = set(
        re.findall(
            r"^\| `([A-Z][A-Z0-9-]+)` \| [ABC] \| `tests/",
            (change_dir / "e2e-acceptance.md").read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    )
    if human_ids != set(e2e_ids):
        raise ContractValidationError(
            f"human/machine E2E mismatch: human-only={human_ids - set(e2e_ids)}, machine-only={set(e2e_ids) - human_ids}"
        )
    for case in e2e_cases:
        _assert_pytest_node(str(case.get("test_target", "")), repo_root())
    declared_refs = {r for t in tasks for r in t.get("requirement_refs", [])}
    unknown = declared_refs - req_ids
    if unknown:
        raise ContractValidationError(f"unknown requirement refs: {sorted(unknown)}")
    declared_e2e = {r for t in tasks for r in t.get("e2e_refs", [])}
    unknown_e2e = declared_e2e - set(e2e_ids)
    if unknown_e2e:
        raise ContractValidationError(f"unknown E2E refs: {sorted(unknown_e2e)}")
    trace_entries = trace.get("entries", []) if isinstance(trace, dict) else []
    trace_by_scenario = {entry.get("scenario_id"): entry for entry in trace_entries}
    if set(trace_by_scenario) != spec_scenarios:
        raise ContractValidationError(
            f"traceability scenario coverage mismatch: missing={spec_scenarios - set(trace_by_scenario)}, extra={set(trace_by_scenario) - spec_scenarios}"
        )
    case_by_id = {case["id"]: case for case in e2e_cases}
    for case in e2e_cases:
        for scenario_id in case.get("scenario_refs", []):
            entry = trace_by_scenario.get(scenario_id)
            if entry is None or case["id"] not in entry.get("e2e_case_ids", []):
                raise ContractValidationError(
                    f"traceability is not reciprocal for {case['id']} / {scenario_id}"
                )
    for scenario_id, entry in trace_by_scenario.items():
        if entry.get("requirement_id") not in req_ids:
            raise ContractValidationError(f"traceability has unknown requirement: {scenario_id}")
        if any(case_id not in case_by_id for case_id in entry.get("e2e_case_ids", [])):
            raise ContractValidationError(f"traceability has unknown E2E case: {scenario_id}")
    if trace.get("specs_sha256") != _canonical_specs_sha256(change_dir):
        raise ContractValidationError("traceability specs_sha256 mismatch")
    for task in tasks:
        for dep in task.get("dependencies", []):
            if dep not in task_map:
                raise ContractValidationError(f"{task['id']} depends on unknown {dep}")
    # Detect cycles using DFS.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(tid: str) -> None:
        if tid in visiting:
            raise ContractValidationError(f"task graph cycle at {tid}")
        if tid in visited:
            return
        visiting.add(tid)
        for dep in task_map[tid].get("dependencies", []):
            visit(dep)
        visiting.remove(tid)
        visited.add(tid)

    for tid in graph_ids:
        visit(tid)
    # Traceability is intentionally checked for shape and known IDs; the JSON
    # schema handles required edge structure, while this verifies both sides.
    if isinstance(trace, dict):
        for key in ("requirements", "e2e_cases", "tasks"):
            values = trace.get(key, [])
            if isinstance(values, list):
                for edge in values:
                    if isinstance(edge, dict):
                        for value in edge.values():
                            if (
                                isinstance(value, str)
                                and (value.startswith("E2E-") or "-R" in value or value in task_map)
                                and value not in req_ids
                                and value not in set(e2e_ids)
                                and value not in task_map
                                and value not in spec_scenarios
                            ):
                                raise ContractValidationError(f"unknown traceability ID: {value}")
    return {
        "change": str(change_dir),
        "schema_count": len(schemas),
        "instances": validated_instances,
        "requirements": len(req_ids),
        "scenarios": len(spec_scenarios),
        "tasks": len(tasks),
        "e2e_cases": len(e2e_ids),
    }
