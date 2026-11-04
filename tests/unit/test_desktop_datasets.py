from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from segvision.application.datasets import open_dataset
from segvision.application.errors import ProtocolError
from segvision.defaults import DEFAULT_CLASS_ID


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.zeros((8, 12, 3), dtype=np.uint8)).save(path)


def _create_directory_link(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError as exc:
        if os.name != "nt":
            raise AssertionError(f"could not create directory symlink: {exc}") from exc
        symlink_error = exc

    env = os.environ.copy()
    env["SEGVISION_LINK_PATH"] = str(link)
    env["SEGVISION_LINK_TARGET"] = str(target)
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "New-Item -ItemType Junction -Path $env:SEGVISION_LINK_PATH "
                "-Target $env:SEGVISION_LINK_TARGET | Out-Null"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "could not create directory junction without symlink privileges: "
            f"{result.stdout}\n{result.stderr}"
        ) from symlink_error


def test_dataset_discovers_one_nested_image_and_excludes_gold_files(tmp_path: Path) -> None:
    _write_image(tmp_path / "batch-a" / "part.png")
    Image.fromarray(np.ones((8, 12), dtype=np.uint8) * 255, mode="L").save(
        tmp_path / "batch-a" / "part_gold.png"
    )
    _write_image(tmp_path / "gold" / "not-an-item.png")

    dataset = open_dataset(str(tmp_path), grant_id="grant")

    assert [item.image_id for item in dataset.items] == ["batch-a/part"]
    assert dataset.class_id == DEFAULT_CLASS_ID
    assert dataset.items[0].class_id == DEFAULT_CLASS_ID
    assert dataset.items[0].gold_path == tmp_path / "batch-a" / "part_gold.png"


def test_empty_manifest_class_id_uses_defect_default(tmp_path: Path) -> None:
    _write_image(tmp_path / "part.png")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"class_id": "", "items": ["part.png"]}), encoding="utf-8"
    )

    dataset = open_dataset(str(tmp_path), grant_id="grant")

    assert dataset.class_id == DEFAULT_CLASS_ID
    assert dataset.items[0].class_id == DEFAULT_CLASS_ID


def test_dataset_pairs_mvtec_ground_truth_inside_explicit_test_public_grant(
    tmp_path: Path,
) -> None:
    root = tmp_path / "test_public"
    _write_image(root / "bad" / "000_regular.png")
    (root / "ground_truth" / "bad").mkdir(parents=True)
    Image.fromarray(np.ones((8, 12), dtype=np.uint8) * 255, mode="L").save(
        root / "ground_truth" / "bad" / "000_regular_mask.png"
    )

    dataset = open_dataset(str(root), grant_id="grant")

    assert [item.image_id for item in dataset.items] == ["bad/000_regular"]
    assert dataset.items[0].gold_path == (
        root / "ground_truth" / "bad" / "000_regular_mask.png"
    )


def test_manifest_cannot_escape_the_granted_dataset_root(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.png"
    _write_image(outside)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"class_id": "part", "items": ["../outside.png"]}), encoding="utf-8"
    )

    with pytest.raises(ProtocolError, match="manifest item") as excinfo:
        open_dataset(str(tmp_path), grant_id="grant")

    assert excinfo.value.code == "validation_failed"


def test_discovery_rejects_source_and_gold_links_outside_the_granted_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "dataset"
    root.mkdir()
    outside = tmp_path / "outside"
    _write_image(outside / "source.png")
    _write_image(outside / "gold.png")
    _write_image(outside / "part.png")

    source_link = root / "source-link.png"
    try:
        source_link.symlink_to(outside / "source.png")
        source_error = "source image escapes"
    except OSError:
        source_link = root / "source-link"
        _create_directory_link(source_link, outside)
        source_error = "dataset directory escapes"
    with pytest.raises(ProtocolError, match=source_error):
        open_dataset(str(root), grant_id="grant")

    if source_link.is_dir():
        source_link.rmdir()
    else:
        source_link.unlink()
    _write_image(root / "part.png")
    gold_link = root / "part_gold.png"
    try:
        gold_link.symlink_to(outside / "gold.png")
    except OSError:
        gold_link = root / "gold"
        _create_directory_link(gold_link, outside)

    with pytest.raises(ProtocolError, match="gold mask escapes"):
        open_dataset(str(root), grant_id="grant")

    if gold_link.is_dir():
        gold_link.rmdir()
    else:
        gold_link.unlink()
