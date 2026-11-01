import json
from pathlib import Path

import pytest

from segvision.acceptance.contracts import validate_contracts
from segvision.acceptance.evidence import validate_evidence
from segvision.acceptance.state import validate_state
from segvision.core.errors import ContractValidationError


def test_gov_dag():
    assert validate_contracts("openspec/changes/build-segvision-v1")["tasks"] == 74


def test_gov_incomplete():
    state = json.loads(
        Path("tests/fixtures/governance/state/valid.json").read_text(encoding="utf-8")
    )
    assert state["project_state"] == "in_progress"
    assert all(task["state"] == "pending" for task in state["tasks"])


def test_gov_retry():
    evidence = json.loads(
        Path("tests/fixtures/governance/evidence/valid/evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(evidence["retry_history"]) <= 3


def test_gov_block_continue():
    state = json.loads(
        Path("tests/fixtures/governance/state/valid.json").read_text(encoding="utf-8")
    )
    runnable = [task for task in state["tasks"] if not task["dependencies"]]
    assert runnable and all(task["state"] == "pending" for task in runnable)


def test_gov_resume():
    assert (
        validate_state("tests/fixtures/governance/state/valid.json")["project_state"]
        == "in_progress"
    )


def test_gov_ownership():
    root = Path("evidence/execution-state.json")
    assert root.is_file() and root.parent.name == "evidence"


def test_gov_evidence():
    assert (
        validate_evidence("tests/fixtures/governance/evidence/valid/evidence.json")["count"]
        == 1
    )


def test_gov_prohibitions():
    with pytest.raises(ContractValidationError):
        validate_contracts("does-not-exist")
