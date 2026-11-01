"""Domain-input and independent-review validators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from segvision.core.errors import ConfigurationError


def load_domain_inputs(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("approved") is not True:
        raise ConfigurationError("domain input authority is not approved")
    if data.get("synthetic") is True:
        raise ConfigurationError("synthetic data cannot satisfy domain gate")
    return data


def validate_reviewer_records(
    records: list[dict[str, Any]], *, minimum: int = 30
) -> dict[str, Any]:
    if len(records) < minimum:
        raise ConfigurationError(f"independent review count {len(records)} < {minimum}")
    wrong = sum(bool(r.get("wrong_accept")) for r in records)
    return {"count": len(records), "wrong_accept": wrong, "wrong_accept_rate": wrong / len(records)}
