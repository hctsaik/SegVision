from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from segvision.transport.desktop_api.app import create_app, decode_host_path

SECRET = "test-secret-not-for-production"
HEADERS = {
    "X-SegVision-Launch-Secret": SECRET,
    "X-SegVision-Protocol-Version": "1.1",
    "X-SegVision-Host-Proxy": "1",
}


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    rgb = np.zeros((40, 50, 3), dtype=np.uint8)
    rgb[14:28, 18:32] = 200
    Image.fromarray(rgb).save(tmp_path / "part.png")
    gold = np.zeros((40, 50), dtype=np.uint8)
    gold[14:28, 18:32] = 255
    Image.fromarray(gold, mode="L").save(tmp_path / "part_gold.png")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"class_id": "part", "items": ["part.png"]}), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def client(dataset: Path) -> TestClient:
    app = create_app(secret=SECRET, actor="scripted_test")
    return TestClient(app)


def _rid() -> str:
    return uuid.uuid4().hex


def _open(client: TestClient, dataset: Path) -> dict:
    headers = {**HEADERS, "X-SegVision-Resolved-Path": str(dataset)}
    r = client.post(
        "/v1/datasets/open",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "grant_id": "g-dataset",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_health_exact_version(client: TestClient):
    r = client.get("/v1/health", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["protocol_version"] == "1.1"
    assert body["cpu_only"] is True
    assert body["ready"] is True


@pytest.mark.parametrize("version", ["1", "1.0.0", "1.0", "v1.0", "", None])
def test_health_rejects_incompatible_version(client: TestClient, version):
    headers = {**HEADERS}
    if version is None:
        headers.pop("X-SegVision-Protocol-Version")
    else:
        headers["X-SegVision-Protocol-Version"] = version
    r = client.get("/v1/health", headers=headers)
    assert r.status_code == 400
    assert r.json()["code"] == "protocol_version_mismatch"


def test_missing_secret_unauthorized(client: TestClient):
    r = client.get("/v1/health", headers={"X-SegVision-Protocol-Version": "1.0"})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


def test_unknown_operation(client: TestClient):
    r = client.post("/v1/explode", headers=HEADERS, json={"protocol_version": "1.1"})
    assert r.json()["code"] == "unsupported_operation"


def test_control_plane_rejects_base64_image(client: TestClient):
    r = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={"protocol_version": "1.1", "request_id": _rid(), "image": "aaaa"},
    )
    assert r.json()["code"] == "validation_failed"


def test_open_list_and_binary_assets(client: TestClient, dataset: Path):
    opened = _open(client, dataset)
    items = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()
    assert len(items["items"]) == 1
    token = items["items"][0]["thumbnail_token"]
    gold = items["items"][0]["gold_mask_token"]
    img = client.get(f"/v1/assets/{token}", headers=HEADERS)
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"
    assert img.content[:8] == b"\x89PNG\r\n\x1a\n"
    mask = client.get(f"/v1/assets/{gold}", headers=HEADERS)
    pixels = np.array(Image.open(io.BytesIO(mask.content)))
    assert set(np.unique(pixels).tolist()) <= {0, 255}


def test_asset_token_rejects_path_traversal(client: TestClient):
    r = client.get("/v1/assets/..%2Fetc%2Fpasswd", headers=HEADERS)
    assert r.json()["code"] in {"unauthorized", "not_found"}


def test_create_is_image_open_revision_zero(client: TestClient, dataset: Path):
    opened = _open(client, dataset)
    item_id = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()["items"][0]["item_id"]
    snap = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": item_id,
        },
    ).json()
    assert snap["workflow_state"] == "IMAGE_OPEN"
    assert snap["revision"] == 0
    assert snap["user_roi_full"] is None
    assert snap["class_id"] is None


def test_two_point_work_area_can_start_manual_brush_before_sam(client: TestClient, dataset: Path):
    opened = _open(client, dataset)
    item_id = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()["items"][0]["item_id"]
    created = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": item_id,
        },
    ).json()
    sid = created["protocol_session_id"]
    manual = client.post(
        f"/v1/sessions/{sid}/manual-empty",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "roi_xyxy": [10, 10, 30, 30],
        },
    )
    assert manual.status_code == 200, manual.text
    manual_snap = manual.json()
    assert manual_snap["workflow_state"] == "MANUAL_EMPTY"
    assert manual_snap["controls"]["local_edit"] is True
    edited = client.post(
        f"/v1/sessions/{sid}/edits",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": manual_snap["revision"],
            "operation": "brush",
            "points": [[1, 1]],
            "radius": 3,
            "clip_rect": [1, 1, 2, 2],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["workflow_state"] == "LOCAL_EDITING"


def test_annotation_loop_select_refine_edit_accept(client: TestClient, dataset: Path, tmp_path: Path):
    opened = _open(client, dataset)
    item_id = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()["items"][0]["item_id"]
    created = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": item_id,
        },
    ).json()
    sid = created["protocol_session_id"]
    out = tmp_path / "out"
    out.mkdir()
    headers = {**HEADERS, "X-SegVision-Resolved-Path": str(dataset), "X-SegVision-Output-Path": str(out)}
    locked = client.post(
        f"/v1/sessions/{sid}/lock-roi",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "session_id": sid,
            "base_revision": 0,
            "class_id": "part",
            "roi_xyxy": [10, 8, 38, 36],
        },
    )
    assert locked.status_code == 200, locked.text
    snap = locked.json()
    assert snap["revision"] == 1
    assert 1 <= len(snap["candidates"]) <= 3
    warning_codes = [warning["code"] for warning in snap["warnings"]]
    assert len(warning_codes) == len(set(warning_codes))
    cid = snap["candidates"][0]["candidate_id"]
    selected = client.post(
        f"/v1/sessions/{sid}/select",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "candidate_id": cid,
        },
    ).json()
    assert selected["selected_candidate_id"] == cid
    cancelled = client.post(
        f"/v1/sessions/{sid}/select",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "candidate_id": None,
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["selected_candidate_id"] is None
    assert cancelled.json()["controls"]["accept"] is False
    assert len(cancelled.json()["candidates"]) == len(snap["candidates"])
    selected = client.post(
        f"/v1/sessions/{sid}/select",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "candidate_id": cid,
        },
    ).json()
    assert selected["selected_candidate_id"] == cid
    refined = client.post(
        f"/v1/sessions/{sid}/refinements",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "x": 20,
            "y": 20,
            "label": 1,
        },
    )
    assert refined.status_code == 200, refined.text
    refined_snap = refined.json()
    refined_candidate = next(
        candidate
        for candidate in refined_snap["candidates"]
        if candidate["candidate_id"] == refined_snap["selected_candidate_id"]
    )
    assert refined_candidate["prompt_points"] == [{"x": 20, "y": 20, "label": 1}]
    edited = client.post(
        f"/v1/sessions/{sid}/edits",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "operation": "erase",
            "points": [[0, 0]],
            "radius": 3,
            "clip_rect": [0, 0, 1, 1],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["workflow_state"] == "LOCAL_EDITING"
    stale = client.post(
        f"/v1/sessions/{sid}/edits",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "operation": "grow",
        },
    )
    assert stale.json()["code"] == "revision_conflict"
    acks = [w["code"] for w in edited.json()["warnings"]]
    accepted = client.post(
        f"/v1/sessions/{sid}/accept",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "acknowledge_warnings": acks,
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workflow_state"] == "ACCEPTED"
    assert accepted.json()["persist"]["training_eligible"] is True
    assert str(out) not in json.dumps(accepted.json())


def test_prompt_delete_and_frozen_region_roundtrip(
    client: TestClient, dataset: Path, tmp_path: Path
):
    opened = _open(client, dataset)
    item_id = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()["items"][0]["item_id"]
    created = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": item_id,
        },
    ).json()
    sid = created["protocol_session_id"]
    output = tmp_path / "frozen-output"
    output.mkdir()
    headers = {**HEADERS, "X-SegVision-Output-Path": str(output)}
    locked = client.post(
        f"/v1/sessions/{sid}/lock-roi",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "class_id": "part",
            "roi_xyxy": [10, 8, 38, 36],
        },
    )
    assert locked.status_code == 200, locked.text

    refined = client.post(
        f"/v1/sessions/{sid}/refinements",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "x": 20,
            "y": 20,
            "label": 1,
        },
    )
    assert refined.status_code == 200, refined.text
    prompt = refined.json()["prompt_points"][0]
    assert prompt["point_id"]

    deleted = client.post(
        f"/v1/sessions/{sid}/prompts/delete",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "prompt_id": prompt["point_id"],
        },
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["prompt_points"] == []
    assert deleted.json()["revision"] == 1

    frozen = client.post(
        f"/v1/sessions/{sid}/regions/lock",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "x": 20,
            "y": 20,
            "guard": True,
        },
    )
    assert frozen.status_code == 200, frozen.text
    snap = frozen.json()
    assert len(snap["frozen_regions"]) == 1
    assert snap["assets"]["locked_foreground"]
    region_id = snap["frozen_regions"][0]["region_id"]

    unfrozen = client.post(
        f"/v1/sessions/{sid}/regions/unlock",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "region_id": region_id,
        },
    )
    assert unfrozen.status_code == 200, unfrozen.text
    assert unfrozen.json()["frozen_regions"] == []

    frozen = client.post(
        f"/v1/sessions/{sid}/regions/lock",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "x": 20,
            "y": 20,
        },
    )
    assert frozen.status_code == 200, frozen.text
    next_region = client.post(
        f"/v1/sessions/{sid}/regions/next",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
        },
    )
    assert next_region.status_code == 200, next_region.text
    snap = next_region.json()
    assert snap["pass_index"] == 2
    assert snap["revision"] == 2
    assert snap["candidates"] == []
    assert len(snap["frozen_regions"]) == 1
    assert snap["controls"]["roi"] is True

    # A new pass starts empty; locking a fresh ROI re-enables MobileSAM.
    relocked = client.post(
        f"/v1/sessions/{sid}/lock-roi",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 2,
            "class_id": "part",
            "roi_xyxy": [11, 8, 39, 36],
        },
    )
    assert relocked.status_code == 200, relocked.text
    snap = relocked.json()
    assert snap["revision"] == 3
    assert snap["controls"]["refine"] is True

    accepted = client.post(
        f"/v1/sessions/{sid}/accept",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 3,
            "acknowledge_warnings": [warning["code"] for warning in snap["warnings"]],
        },
    )
    assert accepted.status_code == 200, accepted.text
    sidecar = json.loads(next(output.glob("*.json")).read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == 2
    assert sidecar["region_workflow"]["pass_index"] == 2
    assert len(sidecar["region_workflow"]["frozen_regions"]) == 1


def test_merge_edit_flattens_foreground_region_and_undoes(
    client: TestClient, dataset: Path
):
    """The existing edits endpoint exposes the explicit foreground merge."""
    opened = _open(client, dataset)
    item_id = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()["items"][0]["item_id"]
    created = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": item_id,
        },
    ).json()
    sid = created["protocol_session_id"]
    locked = client.post(
        f"/v1/sessions/{sid}/lock-roi",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "class_id": "part",
            "roi_xyxy": [10, 8, 38, 36],
        },
    )
    assert locked.status_code == 200, locked.text
    region = client.post(
        f"/v1/sessions/{sid}/regions/lock",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "x": 20,
            "y": 20,
            "guard": True,
        },
    )
    assert region.status_code == 200, region.text
    assert len(region.json()["frozen_regions"]) == 1

    merged = client.post(
        f"/v1/sessions/{sid}/edits",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "operation": "merge",
            "points": [],
            "radius": 0,
        },
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["workflow_state"] == "LOCAL_EDITING"
    assert merged.json()["frozen_regions"] == []
    assert merged.json()["controls"]["merge_regions"] is False

    undone = client.post(
        f"/v1/sessions/{sid}/undo",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
        },
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["workflow_state"] == "PROPOSAL_READY"
    assert len(undone.json()["frozen_regions"]) == 1


def test_decode_host_path_accepts_raw_and_percent_encoded_unicode():
    raw = r"C:\Users\資料\masks"
    assert decode_host_path(raw) == raw
    assert decode_host_path(quote(raw, safe="")) == raw
    assert decode_host_path("") is None
    assert decode_host_path(None) is None


def test_accept_reads_percent_encoded_unicode_output_header(tmp_path: Path, dataset: Path):
    client = TestClient(create_app(secret=SECRET, actor="scripted_test"))
    opened = _open(client, dataset)
    items = client.get(f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS).json()
    created = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": items["items"][0]["item_id"],
        },
    ).json()
    out = tmp_path / "輸出"
    out.mkdir()
    headers = {
        **HEADERS,
        "X-SegVision-Resolved-Path": str(dataset),
        "X-SegVision-Output-Path": quote(str(out), safe=""),
    }
    sid = created["protocol_session_id"]
    locked = client.post(
        f"/v1/sessions/{sid}/lock-roi",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "session_id": sid,
            "base_revision": 0,
            "class_id": "part",
            "roi_xyxy": [10, 8, 38, 36],
        },
    )
    assert locked.status_code == 200, locked.text
    snap = locked.json()
    accepted = client.post(
        f"/v1/sessions/{sid}/accept",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "session_id": sid,
            "base_revision": snap["revision"],
            "acknowledge_warnings": [warning["code"] for warning in snap["warnings"]],
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workflow_state"] == "ACCEPTED"
    assert list(out.glob("*.json"))


def test_nested_dataset_accept_publishes_a_flat_output_pair(tmp_path: Path):
    dataset = tmp_path / "dataset"
    nested = dataset / "batch-a"
    nested.mkdir(parents=True)
    rgb = np.zeros((40, 50, 3), dtype=np.uint8)
    rgb[14:28, 18:32] = 200
    Image.fromarray(rgb).save(nested / "part.png")
    client = TestClient(create_app(secret=SECRET, actor="scripted_test"))

    opened = _open(client, dataset)
    items = client.get(f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS).json()
    assert items["items"][0]["image_id"] == "batch-a/part"
    created = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": items["items"][0]["item_id"],
        },
    ).json()
    output = tmp_path / "out"
    output.mkdir()
    headers = {
        **HEADERS,
        "X-SegVision-Resolved-Path": str(dataset),
        "X-SegVision-Output-Path": str(output),
    }
    sid = created["protocol_session_id"]
    locked = client.post(
        f"/v1/sessions/{sid}/lock-roi",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "session_id": sid,
            "base_revision": 0,
            "class_id": "Defect",
            "roi_xyxy": [10, 8, 38, 36],
        },
    )
    assert locked.status_code == 200, locked.text
    snap = locked.json()
    accepted = client.post(
        f"/v1/sessions/{sid}/accept",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "session_id": sid,
            "base_revision": snap["revision"],
            "acknowledge_warnings": [warning["code"] for warning in snap["warnings"]],
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workflow_state"] == "ACCEPTED"
    assert list(output.glob("*.json"))
    assert not (output / "batch-a").exists()


def test_needs_review_not_training_eligible(client: TestClient, dataset: Path, tmp_path: Path):
    opened = _open(client, dataset)
    item_id = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()["items"][0]["item_id"]
    created = client.post(
        "/v1/sessions",
        headers=HEADERS,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "dataset_id": opened["dataset_id"],
            "item_id": item_id,
        },
    ).json()
    sid = created["protocol_session_id"]
    out = tmp_path / "review"
    out.mkdir()
    headers = {**HEADERS, "X-SegVision-Resolved-Path": str(dataset), "X-SegVision-Output-Path": str(out)}
    locked = client.post(
        f"/v1/sessions/{sid}/lock-roi",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 0,
            "class_id": "part",
            "roi_xyxy": [10, 8, 38, 36],
        },
    )
    assert locked.status_code == 200, locked.text
    reviewed = client.post(
        f"/v1/sessions/{sid}/needs-review",
        headers=headers,
        json={
            "protocol_version": "1.1",
            "request_id": _rid(),
            "base_revision": 1,
            "reason": "uncertain edge",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["workflow_state"] == "NEEDS_REVIEW"
    assert reviewed.json()["persist"]["training_eligible"] is False
    review_sidecar = out / "review" / "part.json"
    assert review_sidecar.is_file()
    review_record = json.loads(review_sidecar.read_text(encoding="utf-8"))
    assert review_record["status"] == "needs_review"
    assert review_record["training_eligible"] is False
    assert review_record["reason"] == "uncertain edge"
    assert review_record["draft"] is not None
    assert (out / "review" / review_record["draft"]["filename"]).is_file()
    assert not list(out.glob("*.json")), "Needs Review must not publish an accepted sidecar"
    assert not list(out.glob("*.png")), "Needs Review must not publish an accepted mask"


def test_idempotent_request_id(client: TestClient, dataset: Path):
    opened = _open(client, dataset)
    item_id = client.get(
        f"/v1/datasets/{opened['dataset_id']}/items", headers=HEADERS
    ).json()["items"][0]["item_id"]
    rid = _rid()
    body = {
        "protocol_version": "1.1",
        "request_id": rid,
        "base_revision": 0,
        "dataset_id": opened["dataset_id"],
        "item_id": item_id,
    }
    a = client.post("/v1/sessions", headers=HEADERS, json=body).json()
    b = client.post("/v1/sessions", headers=HEADERS, json=body).json()
    assert a["protocol_session_id"] == b["protocol_session_id"]


def test_real_localhost_process_health(dataset: Path):
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "segvision.transport.desktop_api",
            "--secret",
            SECRET,
            "--port",
            "0",
            "--actor",
            "scripted_test",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    try:
        line = proc.stdout.readline() if proc.stdout else ""
        info = json.loads(line)
        port = int(info["port"])
        deadline = time.time() + 10
        last = None
        while time.time() < deadline:
            try:
                last = httpx.get(
                    f"http://127.0.0.1:{port}/v1/health",
                    headers=HEADERS,
                    timeout=1.0,
                )
                if last.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        assert last is not None and last.status_code == 200
        denied = httpx.get(
            f"http://127.0.0.1:{port}/v1/health",
            headers={"X-SegVision-Protocol-Version": "1.0"},
            timeout=1.0,
        )
        assert denied.json()["code"] == "unauthorized"
        mismatch = httpx.get(
            f"http://127.0.0.1:{port}/v1/health",
            headers={**HEADERS, "X-SegVision-Protocol-Version": "1.0"},
            timeout=1.0,
        )
        assert mismatch.json()["code"] == "protocol_version_mismatch"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_import_segvision_does_not_bind_port():
    import importlib

    import segvision

    importlib.reload(segvision)
    assert hasattr(segvision, "SegVisionEngine")
