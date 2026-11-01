"""Fail-closed loaders for pending external gate manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from segvision.core.errors import ConfigurationError


def load_pending_manifest(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if p.suffixes[-2:] != [".pending", ".json"] and not p.name.endswith(".pending.json"):
        raise ConfigurationError("only pending external manifests may be loaded")

    def has_pending(value: Any) -> bool:
        if isinstance(value, dict):
            if (
                value.get("status") in {"pending", "pending_external_input", "blocked"}
                or value.get("approval_status") == "pending"
            ):
                return True
            return any(has_pending(v) for v in value.values())
        if isinstance(value, list):
            return any(has_pending(v) for v in value)
        return False

    pending_shape = has_pending(data)
    if not pending_shape:
        raise ConfigurationError("external manifest cannot be presented as approved")
    if data.get("approved") is True or data.get("release_authorized") is True:
        raise ConfigurationError("pending manifest cannot assert approval")
    return data


def all_pending_manifests(directory: str | Path) -> list[dict[str, Any]]:
    return [load_pending_manifest(p) for p in sorted(Path(directory).glob("*.pending.json"))]
