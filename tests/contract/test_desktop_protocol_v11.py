from __future__ import annotations

import json

from fastapi.testclient import TestClient

from segvision.application.protocol import PROTOCOL_VERSION, operations, protocol_root
from segvision.transport.desktop_api.app import create_app


def test_protocol_11_is_exact_and_new_operations_are_allowlisted():
    assert PROTOCOL_VERSION == "1.1"
    assert "sessions.redo" in operations()
    assert "labelme.preview" in operations()
    assert len(json.loads((protocol_root() / "protocol.json").read_text())["error_codes"]) == 8


def test_mixed_10_client_is_rejected_before_session_mutation():
    secret = "contract-secret"
    app = create_app(secret=secret, prefer_real=False)
    client = TestClient(app)
    headers = {"X-SegVision-Launch-Secret": secret, "X-SegVision-Protocol-Version": "1.0"}
    response = client.get("/v1/health", headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "protocol_version_mismatch"
    assert app.state.application._sessions == {}


def test_mixed_header_and_body_versions_are_rejected_before_mutation():
    secret = "contract-secret"
    app = create_app(secret=secret, prefer_real=False)
    client = TestClient(app)
    headers = {
        "X-SegVision-Launch-Secret": secret,
        "X-SegVision-Protocol-Version": "1.1",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/v1/sessions",
        headers=headers,
        json={"protocol_version": "1.0", "request_id": "r", "base_revision": 0},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "protocol_version_mismatch"
    assert app.state.application._sessions == {}


def test_binary_control_payload_and_path_secret_are_not_exposed():
    secret = "contract-secret"
    app = create_app(secret=secret, prefer_real=False)
    client = TestClient(app)
    headers = {
        "X-SegVision-Launch-Secret": secret,
        "X-SegVision-Protocol-Version": "1.1",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/v1/sessions",
        headers=headers,
        json={"protocol_version": "1.1", "request_id": "r", "base_revision": 0, "pixels": "base64"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "validation_failed"
    assert "contract-secret" not in response.text
