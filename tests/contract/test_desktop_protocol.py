from __future__ import annotations

import json
from pathlib import Path

import yaml

from segvision.application.protocol import (
    ERROR_CODES,
    EVENT_KINDS,
    PROTOCOL_VERSION,
    operations,
    protocol_root,
)

ROOT = protocol_root()


def test_protocol_json_matches_python_constants():
    data = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    assert data["protocol_version"] == PROTOCOL_VERSION
    assert tuple(data["error_codes"]) == ERROR_CODES
    assert tuple(data["event_kinds"]) == EVENT_KINDS
    assert tuple(op["name"] for op in data["operations"]) == operations()


def test_openapi_operation_ids_match_frozen_set():
    spec = yaml.safe_load((ROOT / "openapi.yaml").read_text(encoding="utf-8"))
    found = []
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method.startswith("x-"):
                continue
            found.append(op["operationId"])
            expected = next(item for item in json.loads((ROOT / "protocol.json").read_text())["operations"] if item["name"] == op["operationId"])
            assert expected["path"] == path
            assert expected["method"].lower() == method
    assert sorted(found) == sorted(operations())


def test_openapi_error_enum_is_exactly_eight_codes():
    spec = yaml.safe_load((ROOT / "openapi.yaml").read_text(encoding="utf-8"))
    codes = spec["components"]["schemas"]["ErrorCode"]["enum"]
    assert codes == list(ERROR_CODES)
    assert len(codes) == 8


def test_event_schema_kinds():
    schema = json.loads((ROOT / "events.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["kind"]["enum"] == list(EVENT_KINDS)


def test_generated_ts_and_rs_match_protocol_json():
    data = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    ts = (ROOT / "generated" / "protocol.ts").read_text(encoding="utf-8").strip()
    rs = (ROOT / "generated" / "protocol.rs").read_text(encoding="utf-8").strip()
    for name in (op["name"] for op in data["operations"]):
        assert name in ts
        assert name in rs
    for code in data["error_codes"]:
        assert code in ts
        assert code in rs
    rust_host = Path("apps/desktop-host/src-tauri/src/protocol.rs")
    if rust_host.is_file():
        copied = rust_host.read_text(encoding="utf-8").strip()
        assert copied == rs


def test_no_ninth_error_code_in_sources():
    data = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    assert "internal-failure" not in data["error_codes"]
    assert "internal_failure" not in data["error_codes"]
