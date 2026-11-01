"""CPU-only package and offline inventory helpers."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


def inventory(root: str | Path) -> list[dict[str, object]]:
    root = Path(root)
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rows.append(
                {
                    "path": p.relative_to(root).as_posix(),
                    "size_bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
            )
    return rows


def build_offline_bundle(source_root: str | Path, output: str | Path) -> Path:
    source, output = Path(source_root), Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output_resolved = output.resolve()
    entries = [
        item
        for item in inventory(source)
        if (source / str(item["path"])).resolve() != output_resolved
    ]
    metadata = json.dumps(entries, indent=2, sort_keys=True).encode("utf-8")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # Explicit ZipInfo records make bundles reproducible across machines
        # and avoid inheriting volatile source mtimes/permissions.
        for item in entries:
            name = str(item["path"])
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, (source / name).read_bytes())
        info = zipfile.ZipInfo("INVENTORY.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        z.writestr(info, metadata)
    return output


def verify_offline_bundle(bundle: str | Path) -> list[dict[str, object]]:
    """Verify every inventory entry in a bundle before it is installed."""
    bundle = Path(bundle)
    with zipfile.ZipFile(bundle, "r") as z:
        try:
            inventory_data = json.loads(z.read("INVENTORY.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValueError("offline bundle lacks a valid INVENTORY.json") from exc
        if not isinstance(inventory_data, list):
            raise TypeError("offline inventory must be a list")
        names = set(z.namelist())
        seen_paths: set[str] = set()
        for item in inventory_data:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise TypeError("invalid offline inventory item")
            path = item["path"]
            safe_path = PurePosixPath(path)
            if safe_path.is_absolute() or ".." in safe_path.parts:
                raise ValueError(f"unsafe offline inventory path: {path}")
            if path in seen_paths:
                raise ValueError(f"duplicate offline inventory path: {path}")
            seen_paths.add(path)
            if path not in names:
                raise ValueError(f"offline bundle is missing {path}")
            if not isinstance(item.get("size_bytes"), int) or not isinstance(item.get("sha256"), str):
                raise TypeError(f"invalid offline inventory metadata: {path}")
            data = z.read(path)
            if len(data) != item.get("size_bytes") or hashlib.sha256(data).hexdigest() != item.get(
                "sha256"
            ):
                raise ValueError(f"offline hash mismatch: {path}")
        return inventory_data
