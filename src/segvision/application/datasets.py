"""Dataset open/list using host-resolved canonical paths."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from segvision.defaults import DEFAULT_CLASS_ID
from segvision.application.config import DEFAULT_PROJECT_LABELS

from .errors import ProtocolError

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


@dataclass
class DatasetItem:
    item_id: str
    image_id: str
    class_id: str
    path: Path
    gold_path: Path | None
    recipe_id: str | None = None


@dataclass
class Dataset:
    dataset_id: str
    display_name: str
    root: Path
    class_id: str
    items: list[DatasetItem] = field(default_factory=list)
    labels: tuple[dict[str, str], ...] = field(default_factory=tuple)


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def _is_source_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in _IMAGE_EXT
        and path.parent.name.lower() != "gold"
        and not path.stem.lower().endswith("_gold")
    )


def _path_within(root: Path, candidate: Path, *, message: str) -> Path:
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ProtocolError("validation_failed", message) from exc
    return resolved


def _manifest_paths(root: Path, manifest: Path) -> tuple[str, list[Path]]:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("validation_failed", "dataset manifest is invalid") from exc
    if not isinstance(data, dict):
        raise ProtocolError("validation_failed", "dataset manifest must be an object")
    raw_items = data.get("items", [])
    if not isinstance(raw_items, list) or not all(isinstance(name, str) and name for name in raw_items):
        raise ProtocolError("validation_failed", "dataset manifest items are invalid")
    paths: list[Path] = []
    for name in raw_items:
        path = _path_within(root, root / name, message="dataset manifest item escapes the granted root")
        if not _is_source_image(path):
            raise ProtocolError("validation_failed", "dataset manifest item is not a supported source image")
        paths.append(path)
    return str(data.get("class_id") or DEFAULT_CLASS_ID), paths


def _manifest_labels(manifest: Path) -> tuple[dict[str, str], ...]:
    """Read bounded project labels, failing before any session is mutable."""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("validation_failed", "dataset manifest is invalid") from exc
    raw = data.get("labels") if isinstance(data, dict) else None
    if raw is None:
        return tuple(dict(label) for label in DEFAULT_PROJECT_LABELS)
    if not isinstance(raw, list) or not (1 <= len(raw) <= 32):
        raise ProtocolError("validation_failed", "project labels must contain 1 to 32 entries")
    result: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    seen_shortcuts: set[str] = set()
    for label in raw:
        if not isinstance(label, dict):
            raise ProtocolError("validation_failed", "project label metadata is invalid")
        values = {
            "id": str(label.get("id") or "").strip(),
            "display_name": str(label.get("display_name") or "").strip(),
            "shortcut": str(label.get("shortcut") or "").strip(),
            "labelme_name": str(label.get("labelme_name") or "").strip(),
        }
        if not values["id"] or not values["display_name"] or not values["labelme_name"]:
            raise ProtocolError("validation_failed", "project label fields are required")
        if len(values["id"]) > 64 or len(values["labelme_name"]) > 64 or len(values["shortcut"]) > 2:
            raise ProtocolError("validation_failed", "project label fields exceed bounds")
        if values["id"] in seen_ids or values["labelme_name"] in seen_names or (values["shortcut"] and values["shortcut"] in seen_shortcuts):
            raise ProtocolError("validation_failed", "project label identifiers must be unique")
        seen_ids.add(values["id"])
        seen_names.add(values["labelme_name"])
        if values["shortcut"]:
            seen_shortcuts.add(values["shortcut"])
        result.append(values)
    return tuple(result)


def _discover_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()

    def add_source(path: Path) -> None:
        if _is_source_image(path):
            paths.add(
                _path_within(
                    root,
                    path,
                    message="dataset source image escapes the granted root",
                )
            )

    for path in root.iterdir():
        add_source(path)
    for child in root.iterdir():
        if child.is_dir() and child.name.lower() != "gold":
            directory = _path_within(
                root,
                child,
                message="dataset directory escapes the granted root",
            )
            if directory.name.lower() == "gold":
                continue
            for path in directory.iterdir():
                add_source(path)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def _find_gold(root: Path, path: Path) -> Path | None:
    relative = path.relative_to(root)
    candidates = (
        path.with_name(f"{path.stem}_gold.png"),
        path.parent / "gold" / f"{path.stem}.png",
        root / "gold" / relative.with_suffix(".png"),
        # MVTec's public layout keeps masks under a sibling tree inside the
        # explicitly granted ``test_public`` root:
        # ``bad/x.png`` -> ``ground_truth/bad/x_mask.png``.
        root / "ground_truth" / relative.parent / f"{path.stem}_mask.png",
    )
    for candidate in candidates:
        if candidate.is_file():
            return _path_within(
                root,
                candidate,
                message="dataset gold mask escapes the granted root",
            )
    return None


def open_dataset(resolved_path: str, *, grant_id: str) -> Dataset:
    root = Path(resolved_path)
    if not root.exists():
        raise ProtocolError("not_found", "dataset path does not exist")
    if not root.is_dir():
        raise ProtocolError("validation_failed", "dataset grant must be a directory")
    root = root.resolve()
    manifest = root / "manifest.json"
    if manifest.is_file():
        class_id, paths = _manifest_paths(root, manifest)
        labels = _manifest_labels(manifest)
    else:
        class_id = DEFAULT_CLASS_ID
        paths = _discover_paths(root)
        labels = tuple(dict(label) for label in DEFAULT_PROJECT_LABELS)
    items: list[DatasetItem] = []
    for path in paths:
        relative = path.relative_to(root)
        item_id = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
        items.append(
            DatasetItem(
                item_id=item_id,
                image_id=relative.with_suffix("").as_posix(),
                class_id=class_id,
                path=path,
                gold_path=_find_gold(root, path),
            )
        )
    if not items:
        raise ProtocolError("validation_failed", "dataset contains no images")
    dataset_id = hashlib.sha256(f"{grant_id}:{root}".encode()).hexdigest()[:16]
    return Dataset(dataset_id, root.name, root, class_id, items, labels)


def read_item_image(item: DatasetItem) -> np.ndarray:
    return _load_rgb(item.path)


def read_gold(item: DatasetItem) -> np.ndarray | None:
    if item.gold_path is None:
        return None
    with Image.open(item.gold_path) as im:
        arr = np.asarray(im.convert("L"))
        return arr > 0
