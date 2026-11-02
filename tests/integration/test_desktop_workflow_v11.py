from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from segvision.transport.desktop_api.app import create_app

SECRET = "workflow-v11-secret"


def _headers(**extra: str) -> dict[str, str]:
    value = {
        "X-SegVision-Launch-Secret": SECRET,
        "X-SegVision-Protocol-Version": "1.1",
        "X-SegVision-Host-Proxy": "1",
    }
    value.update(extra)
    return value


def _rid() -> str:
    import uuid

    return uuid.uuid4().hex


def _dataset(root: Path) -> None:
    image = np.zeros((24, 32, 3), dtype=np.uint8)
    image[7:16, 9:23] = (180, 80, 40)
    Image.fromarray(image).save(root / "014.png")
    (root / "manifest.json").write_text(
        json.dumps({"class_id": "Defect", "items": ["014.png"]}), encoding="utf-8"
    )


def _open_and_create(client: TestClient, root: Path) -> tuple[dict, dict]:
    opened = client.post(
        "/v1/datasets/open",
        headers=_headers(**{"X-SegVision-Resolved-Path": str(root)}),
        json={"request_id": _rid(), "grant_id": "dataset-grant", "base_revision": 0},
    )
    assert opened.status_code == 200, opened.text
    dataset = opened.json()
    item_id = client.get(
        f"/v1/datasets/{dataset['dataset_id']}/items", headers=_headers()
    ).json()["items"][0]["item_id"]
    session = client.post(
        "/v1/sessions",
        headers=_headers(),
        json={
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": dataset["dataset_id"],
            "item_id": item_id,
        },
    )
    assert session.status_code == 200, session.text
    return dataset, {**session.json(), "item_id": item_id}


def test_v11_labelme_draft_qa_and_resume(tmp_path: Path):
    _dataset(tmp_path)
    app = create_app(secret=SECRET, actor="scripted_test")
    client = TestClient(app)
    dataset, created = _open_and_create(client, tmp_path)
    sid = created["protocol_session_id"]
    item_id = created["item_id"]
    document = {
        "version": "5.0.0",
        "imagePath": "014.png",
        "imageHeight": 24,
        "imageWidth": 32,
        "shapes": [
            {
                "label": "Defect",
                "shape_type": "polygon",
                "points": [[9, 7], [22, 7], [22, 15], [9, 15]],
            }
        ],
    }
    imported = client.post(
        "/v1/labelme/import",
        headers=_headers(),
        json={"request_id": _rid(), "base_revision": 0, "session_id": sid, "document": document},
    )
    assert imported.status_code == 200, imported.text
    imported_body = imported.json()
    assert imported_body["draft"]["source_json_sha256"]
    snapshot = imported_body["snapshot"]
    assert snapshot["workflow_state"] == "LOCAL_EDITING"
    assert snapshot["draft"]["state"] == "saved"

    qa = client.post(
        f"/v1/sessions/{sid}/qa",
        headers=_headers(),
        json={"session_id": sid},
    )
    assert qa.status_code == 200, qa.text
    assert qa.json()["schema_version"] == 1

    preview = client.post(
        "/v1/labelme/preview",
        headers=_headers(),
        json={"session_id": sid},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["label"] == "Defect"
    preview_body = preview.json()
    assert preview_body["assets"]["polygon_preview"]
    assert preview_body["assets"]["difference_preview"]
    assert client.get(
        f"/v1/assets/{preview_body['assets']['polygon_preview']}", headers=_headers()
    ).status_code == 200
    output = tmp_path / "exports"
    exported = client.post(
        "/v1/labelme/export",
        headers=_headers(**{"X-SegVision-Output-Path": str(output)}),
        json={"request_id": _rid(), "base_revision": snapshot["revision"], "session_id": sid},
    )
    assert exported.status_code == 200, exported.text
    assert (output / "014.json").is_file()

    status = client.get(f"/v1/datasets/{dataset['dataset_id']}/work-status", headers=_headers())
    assert status.status_code == 200, status.text
    assert status.json()["items"][0]["status"] == "draft"

    labels = client.get("/v1/labels", headers=_headers())
    assert labels.status_code == 200
    assert labels.json()["labels"][0]["id"] == "Defect"

    second = client.post(
        "/v1/sessions",
        headers=_headers(),
        json={
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": dataset["dataset_id"],
            "item_id": item_id,
        },
    ).json()
    resumed = client.post(
        "/v1/drafts/load",
        headers=_headers(),
        json={
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": dataset["dataset_id"],
            "item_id": item_id,
            "session_id": second["protocol_session_id"],
        },
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["snapshot"]["workflow_state"] == "LOCAL_EDITING"


def test_labelme_import_identity_mapping_and_dirty_guard(tmp_path: Path):
    _dataset(tmp_path)
    app = create_app(secret=SECRET, actor="scripted_test")
    client = TestClient(app)
    _dataset_info, created = _open_and_create(client, tmp_path)
    sid = created["protocol_session_id"]
    base_document = {
        "version": "5.0.0",
        "imagePath": "014.png",
        "imageHeight": 24,
        "imageWidth": 32,
        "shapes": [
            {
                "label": "Scratch",
                "shape_type": "polygon",
                "points": [[9, 7], [22, 7], [22, 15], [9, 15]],
            }
        ],
    }
    mismatched = {**base_document, "imagePath": "other.png"}
    rejected = client.post(
        "/v1/labelme/import",
        headers=_headers(),
        json={"request_id": _rid(), "base_revision": 0, "session_id": sid, "document": mismatched},
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "validation_failed"
    assert client.get(f"/v1/sessions/{sid}", headers=_headers()).json()["revision"] == 0

    imported = client.post(
        "/v1/labelme/import",
        headers=_headers(),
        json={
            "request_id": _rid(),
            "base_revision": 0,
            "session_id": sid,
            "document": base_document,
            "label_mapping": {"Scratch": "Defect"},
        },
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["draft"]["label_mapping"] == {"Scratch": "Defect"}
    dirty_revision = imported.json()["snapshot"]["revision"]
    app.state.application._sessions[sid].persist["draft"]["dirty"] = True
    dirty = client.post(
        "/v1/labelme/import",
        headers=_headers(),
        json={
            "request_id": _rid(),
            "base_revision": dirty_revision,
            "session_id": sid,
            "document": {**base_document, "shapes": [{**base_document["shapes"][0], "label": "Defect"}]},
        },
    )
    assert dirty.status_code == 400
    assert "未儲存草稿" in dirty.json()["message"]
