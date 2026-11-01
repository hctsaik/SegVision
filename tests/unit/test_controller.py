from pathlib import Path

from segvision.acceptance.controller import (
    TaskController,
    _resolve_command,
    _safe_text,
    execute_command,
)
from segvision.acceptance.state import bootstrap_state


def test_controller_uses_repository_python_and_redacts_output():
    command = _resolve_command("python --version", Path.cwd())
    assert command[0].endswith(".venv\\Scripts\\python.exe")
    scaffold_command = _resolve_command("py -3.11 -m venv .venv", Path.cwd())
    assert scaffold_command[:2] == ["py.exe", "-3.11"]
    result = execute_command("python --version", root=Path.cwd())
    assert result["exit_code"] == 0
    assert execute_command("py -3.11 -m venv .venv", root=Path.cwd())["exit_code"] == 0
    assert len(result["stdout_sha256"]) == 64
    assert "REDACTED" in _safe_text("token=secret-value")


def test_controller_ready_tasks_are_dependency_ordered(tmp_path):
    state_path = tmp_path / "execution-state.json"
    bootstrap_state("sv-20260828T000000Z-00000000", output=state_path)
    controller = TaskController(state=state_path)
    graph, state = controller._load()
    ready = controller._ready(graph, state)
    assert ready
    assert ready[0]["dependencies"] == []
    assert all(task["id"] == "P00" for task in ready)


def test_checkbox_update_preserves_lf_newlines(tmp_path):
    tasks = tmp_path / "tasks.md"
    tasks.write_bytes(b"- [ ] 0.1 `P00` - preflight\n")
    controller = TaskController(tasks_file=tasks)

    controller._update_checkbox("P00", True)

    assert tasks.read_bytes() == b"- [x] 0.1 `P00` - preflight\n"
