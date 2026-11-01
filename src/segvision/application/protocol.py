"""Load the published desktop protocol documents."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PROTOCOL_VERSION = "1.1"
ERROR_CODES = (
    "protocol_version_mismatch",
    "revision_conflict",
    "unauthorized",
    "engine_unavailable",
    "validation_failed",
    "unsupported_operation",
    "not_found",
    "stale_job",
)
HOST_ERROR_CODES = ("grant_invalid", "filesystem_error")
EVENT_KINDS = ("progress", "completed", "cancelled", "stale", "failed")
ASSET_KINDS = (
    "source_image",
    "thumbnail",
    "mask",
    "polygon_preview",
    "difference_preview",
    "diagnostic_bundle",
)
SNAPSHOT_MUTATING = frozenset(
    {
        "sessions.lock_roi",
        "sessions.propose",
        "sessions.select",
        "sessions.refine",
        "sessions.delete_prompt",
        "sessions.lock_region",
        "sessions.unlock_region",
        "sessions.start_next_region",
        "sessions.edit",
        "sessions.undo",
        "sessions.redo",
        "sessions.update_prompt",
        "sessions.begin_manual_empty",
        "sessions.expand_roi",
        "sessions.acknowledge_warning",
        "sessions.accept",
        "sessions.needs_review",
        "sessions.close",
        "sessions.create",
        "drafts.flush",
        "drafts.load",
        "drafts.discard",
        "labelme.export",
        "labelme.import",
        "engine.restart",
        "labels.reclassify",
    }
)


def protocol_root() -> Path:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    return repo / "packages" / "desktop-protocol"


@lru_cache(maxsize=1)
def protocol_document() -> dict[str, Any]:
    return json.loads((protocol_root() / "protocol.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def operations() -> tuple[str, ...]:
    return tuple(op["name"] for op in protocol_document()["operations"])


@lru_cache(maxsize=1)
def event_schema() -> dict[str, Any]:
    return json.loads((protocol_root() / "events.schema.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def event_validator() -> Draft202012Validator:
    return Draft202012Validator(event_schema())


def operation_http(name: str) -> tuple[str, str]:
    for op in protocol_document()["operations"]:
        if op["name"] == name:
            return op["method"], op["path"]
    raise KeyError(name)
