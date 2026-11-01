"""Chromium E2E against Vite and a real localhost SegVision sidecar."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "apps" / "desktop-ui"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http(
    url: str, *, headers: dict[str, str] | None = None, timeout: float = 20.0
) -> None:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, headers=headers, timeout=1.0)
            if response.is_success:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
            continue
        time.sleep(0.2)
    raise RuntimeError(f"timeout waiting for {url}")


def _stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture
def dataset(tmp_path: Path) -> tuple[Path, np.ndarray, np.ndarray]:
    rgb = np.zeros((120, 160, 3), dtype=np.uint8)
    rgb[30:90, 45:125] = (80, 0, 0)
    Image.fromarray(rgb).save(tmp_path / "part.png")
    gold = np.zeros((120, 160), dtype=np.uint8)
    gold[30:90, 45:125] = 255
    Image.fromarray(gold, mode="L").save(tmp_path / "part_gold.png")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"class_id": "part", "items": ["part.png"]}), encoding="utf-8"
    )
    return tmp_path, rgb, gold


@pytest.mark.skipif(os.environ.get("SEGVISION_SKIP_PLAYWRIGHT") == "1", reason="playwright disabled")
@pytest.mark.parametrize("outcome", ["accept", "needs_review"])
def test_chromium_open_overlay_roi_and_persisted_outcome(
    dataset: tuple[Path, np.ndarray, np.ndarray], tmp_path: Path, outcome: str
):
    pytest.importorskip("playwright.sync_api")
    dataset_root, expected_rgb, expected_gold = dataset
    secret = "e2e-secret"
    ui_port = _free_port()
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    sidecar = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "segvision.transport.desktop_api",
            "--secret",
            secret,
            "--port",
            "0",
            "--actor",
            "scripted_test",
            "--dev-origin",
            f"http://127.0.0.1:{ui_port}",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert sidecar.stdout is not None
    ready = json.loads(sidecar.stdout.readline())
    sidecar_port = int(ready["port"])
    headers = {
        "X-SegVision-Launch-Secret": secret,
        "X-SegVision-Protocol-Version": "1.1",
        "X-SegVision-Host-Proxy": "1",
        "X-SegVision-Resolved-Path": str(dataset_root),
    }
    _wait_http(f"http://127.0.0.1:{sidecar_port}/v1/health", headers=headers)
    npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
    ui = subprocess.Popen(
        [npx, "vite", "--host", "127.0.0.1", "--port", str(ui_port)],
        cwd=str(UI),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_http(f"http://127.0.0.1:{ui_port}/")
        from playwright.sync_api import sync_playwright

        output = tmp_path / "out"
        output.mkdir()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page_errors: list[str] = []
            console_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            from urllib.parse import quote

            url = (
                f"http://127.0.0.1:{ui_port}/?e2e=1"
                f"&sidecar=http://127.0.0.1:{sidecar_port}"
                f"&secret={secret}"
                f"&dataset={quote(str(dataset_root), safe='')}"
                f"&output={quote(str(output))}"
            )
            page.goto(url)
            page.get_by_test_id("open-dataset").click()
            page.get_by_text("part.png").click()
            page.get_by_test_id("choose-output").click()
            assert page.get_by_test_id("output-grant").is_visible()
            page.wait_for_selector('[data-testid="workflow-state"][data-state="IMAGE_OPEN"]')
            canvas = page.get_by_test_id("annotation-canvas")
            page.wait_for_function(
                """() => {
                    const canvas = document.querySelector('[data-testid=annotation-canvas]');
                    return canvas?.getAttribute('data-image-width') === '160'
                        && canvas?.getAttribute('data-image-height') === '120';
                    }"""
            )
            box = canvas.bounding_box()
            assert box

            def image_css(x: int, y: int) -> tuple[float, float]:
                values = canvas.evaluate(
                    """(node) => ({
                        zoom: Number(node.getAttribute('data-zoom')),
                        panX: Number(node.getAttribute('data-pan-x')),
                        panY: Number(node.getAttribute('data-pan-y')),
                    })"""
                )
                return (
                    box["x"] + values["panX"] + (x + 0.5) * values["zoom"],
                    box["y"] + values["panY"] + (y + 0.5) * values["zoom"],
                )

            source_pixel = canvas.evaluate(
                    """(node) => {
                        const zoom = Number(node.getAttribute('data-zoom'));
                        const panX = Number(node.getAttribute('data-pan-x'));
                        const panY = Number(node.getAttribute('data-pan-y'));
                        const sx = node.width / node.clientWidth;
                        const sy = node.height / node.clientHeight;
                        return Array.from(node.getContext('2d').getImageData(
                            Math.round((panX + 1.5 * zoom) * sx),
                            Math.round((panY + 1.5 * zoom) * sy), 1, 1
                        ).data);
                    }"""
            )
            assert source_pixel == [*expected_rgb[1, 1].tolist(), 255]
            overlay_pixel = canvas.evaluate(
                    """(node) => {
                        const zoom = Number(node.getAttribute('data-zoom'));
                        const panX = Number(node.getAttribute('data-pan-x'));
                        const panY = Number(node.getAttribute('data-pan-y'));
                        const sx = node.width / node.clientWidth;
                        const sy = node.height / node.clientHeight;
                        return Array.from(node.getContext('2d').getImageData(
                            Math.round((panX + 60.5 * zoom) * sx),
                            Math.round((panY + 50.5 * zoom) * sy), 1, 1
                        ).data);
                    }"""
            )
            assert expected_gold[50, 60] == 255
            assert overlay_pixel[0] > expected_rgb[50, 60, 0]
            assert overlay_pixel[2] > expected_rgb[50, 60, 2], "viewer gold overlay was not composed"
            page.get_by_test_id("tool-roi").click()
            x0, y0 = image_css(70, 50)
            x1, y1 = image_css(130, 95)
            page.mouse.click(x0, y0)
            page.mouse.click(x1, y1)
            page.wait_for_timeout(1000)
            page.wait_for_function(
                "() => document.querySelector('[data-testid=annotation-canvas]')?.getAttribute('data-user-roi') === '70,50,131,96'"
            )
            assert page.get_by_test_id("candidate-1").is_visible()
            session_id = canvas.get_attribute("data-session-id")
            assert session_id
            import httpx

            snapshot = httpx.get(
                f"http://127.0.0.1:{sidecar_port}/v1/sessions/{session_id}", headers=headers
            ).json()
            assert snapshot["image_id"] == "part"
            assert snapshot["user_roi_full"] == [70, 50, 131, 96]
            crop = snapshot["crop_rect_full"]
            assert crop
            candidate_x, candidate_y = int(crop[2]) - 3, int(crop[1]) + 3
            assert expected_gold[candidate_y, candidate_x] == 0
            page.wait_for_function(
                """([x, y]) => {
                    const canvas = document.querySelector('[data-testid=annotation-canvas]');
                    if (!(canvas instanceof HTMLCanvasElement)) return false;
                    const zoom = Number(canvas.getAttribute('data-zoom'));
                    const panX = Number(canvas.getAttribute('data-pan-x'));
                    const panY = Number(canvas.getAttribute('data-pan-y'));
                    const sx = canvas.width / canvas.clientWidth;
                    const sy = canvas.height / canvas.clientHeight;
                    const pixel = canvas.getContext('2d')?.getImageData(
                        Math.round((panX + (x + 0.5) * zoom) * sx),
                        Math.round((panY + (y + 0.5) * zoom) * sy), 1, 1
                    ).data;
                    return Boolean(pixel && Math.max(pixel[0], pixel[1], pixel[2]) > 0);
                }""",
                arg=[candidate_x, candidate_y],
            )
            mask_token = snapshot["assets"]["mask"]
            assert mask_token
            mask_response = httpx.get(
                f"http://127.0.0.1:{sidecar_port}/v1/assets/{mask_token}", headers=headers
            )
            assert mask_response.headers["content-type"].startswith("image/png")
            actual_mask = np.asarray(Image.open(io.BytesIO(mask_response.content)).convert("L"))
            expected_mask = np.zeros_like(actual_mask)
            expected_mask[
                2 : max(6, actual_mask.shape[0] - 2),
                2 : max(6, actual_mask.shape[1] - 2),
            ] = 255
            assert hashlib.sha256(actual_mask.tobytes()).hexdigest() == hashlib.sha256(
                expected_mask.tobytes()
            ).hexdigest()
            if outcome == "accept":
                page.get_by_test_id("accept").click()
                page.wait_for_function(
                    "() => document.querySelector('[data-testid=workflow-state]')?.getAttribute('data-state') === 'ACCEPTED'"
                )
                assert list(output.glob("*.json"))
                assert list(output.glob("*.png"))
            else:
                page.get_by_test_id("save-bar-review").click()
                page.wait_for_function(
                    "() => document.querySelector('[data-testid=workflow-state]')?.getAttribute('data-state') === 'NEEDS_REVIEW'"
                )
                assert page.get_by_test_id("review-saved-bar").is_visible()
                assert page.get_by_test_id("next-after-review").is_enabled()
                reviewed = httpx.get(
                    f"http://127.0.0.1:{sidecar_port}/v1/sessions/{session_id}", headers=headers
                ).json()
                assert reviewed["workflow_state"] == "NEEDS_REVIEW"
                assert reviewed["persist"] == {
                    "kind": "needs_review",
                    "training_eligible": False,
                    "reason": "needs review",
                }
                review_path = output / "review" / "part.json"
                assert review_path.is_file()
                review_record = json.loads(review_path.read_text(encoding="utf-8"))
                assert review_record["status"] == "needs_review"
                assert review_record["training_eligible"] is False
                assert review_record["reason"] == "needs review"
                assert not list(output.glob("*.json")), "review must not publish an accepted sidecar"
                assert not list(output.glob("*.png")), "review must not publish an accepted mask"
                draft = review_record["draft"]
                assert draft and draft["filename"]
                draft_path = output / "review" / draft["filename"]
                assert draft_path.is_file()
                assert hashlib.sha256(draft_path.read_bytes()).hexdigest() == draft["sha256"]
            assert not page_errors
            assert not console_errors
            browser.close()
    finally:
        _stop(sidecar)
        _stop(ui)
