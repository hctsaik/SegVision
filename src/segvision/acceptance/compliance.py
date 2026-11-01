"""SBOM/third-party notice and license inventory generation."""

from __future__ import annotations

import importlib.metadata
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast


def dependency_inventory() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for dist in sorted(
        importlib.metadata.distributions(),
        key=lambda d: str(cast(Mapping[str, str], d.metadata).get("Name", "")).lower(),
    ):
        metadata = cast(Mapping[str, str], dist.metadata)
        name = str(metadata.get("Name", "unknown"))
        license_name = str(metadata.get("License", "UNKNOWN"))
        out.append({"name": name, "version": dist.version, "license": license_name})
    return out


def write_sbom(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "components": [{"type": "library", **x} for x in dependency_inventory()],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return p


def write_third_party_notices(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "SegVision third-party dependency inventory\n\n"
        + "\n".join(f"- {x['name']} {x['version']}: {x['license']}" for x in dependency_inventory())
        + "\n",
        encoding="utf-8",
    )
    return p
