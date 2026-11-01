"""Deterministic reports built from complete acceptance denominators."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .observability import aggregate_outcomes, aggregate_times


def strict_within_30(annotation_time_ms: float | None) -> bool:
    """Return the frozen strict SLO result (30,000 ms itself does not pass)."""

    return isinstance(annotation_time_ms, (int, float)) and float(annotation_time_ms) < 30_000.0


def build_report(
    records: Iterable[dict[str, Any]],
    *,
    events: Iterable[dict[str, Any]] = (),
    run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = list(records)
    report: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "outcomes": aggregate_outcomes(rows),
        "events": list(events),
        "metadata": dict(metadata or {}),
    }
    report["annotation_times_ms"] = aggregate_times(
        row["annotation_time_ms"]
        for row in rows
        if isinstance(row.get("annotation_time_ms"), (int, float))
    )
    return report


def write_report(path: str | Path, report: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


__all__ = ["aggregate_outcomes", "aggregate_times", "build_report", "strict_within_30", "write_report"]
