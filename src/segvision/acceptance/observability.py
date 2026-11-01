"""Deterministic session telemetry and aggregate timing helpers."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventLog:
    events: list[dict[str, Any]] = field(default_factory=list)
    _last_ns: int = 0

    def emit(self, name: str, *, timestamp_ns: int | None = None, **payload: Any) -> dict[str, Any]:
        ns = time.monotonic_ns() if timestamp_ns is None else int(timestamp_ns)
        if ns < self._last_ns:
            raise ValueError("event timestamps must be monotonic")
        self._last_ns = ns
        event = {"sequence": len(self.events) + 1, "name": name, "timestamp_ns": ns, **payload}
        self.events.append(event)
        return event

    def to_json(self) -> str:
        return json.dumps(self.events, sort_keys=True, separators=(",", ":"))


def aggregate_times(values_ms: Iterable[float]) -> dict[str, float | int]:
    values = sorted(float(v) for v in values_ms)
    if not values:
        return {"count": 0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}

    def pct(p: float) -> float:
        return values[min(len(values) - 1, max(0, int((len(values) - 1) * p)))]

    return {
        "count": len(values),
        "p50": pct(0.5),
        "p90": pct(0.9),
        "p95": pct(0.95),
        "p99": pct(0.99),
    }


def aggregate_outcomes(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate final outcomes without dropping failed or unresolved images."""
    rows = list(records)
    accepted = [r for r in rows if r.get("outcome") == "accepted"]
    reviews = [r for r in rows if r.get("outcome") == "needs_review"]
    unresolved = [r for r in rows if r.get("outcome") in {None, "unresolved"}]
    valid_accepts = [r for r in rows if r.get("valid_accept") is True]
    under_30 = [
        r
        for r in accepted
        if isinstance(r.get("annotation_time_ms"), (int, float))
        and r["annotation_time_ms"] < 30_000
    ]
    timeouts = [r for r in rows if bool(r.get("timeout"))]
    return {
        "total_presented_images": len(rows),
        "final_accepted_count": len(accepted),
        "final_needs_review_count": len(reviews),
        "unresolved_at_cutoff_count": len(unresolved),
        "valid_accept_count": len(valid_accepts),
        "accepted_under_30_count": len(under_30),
        "accepted_over_30_count": max(0, len(accepted) - len(under_30)),
        "sessions_with_timeout_count": len(timeouts),
        "backend_failure_count": sum(bool(r.get("backend_failed")) for r in rows),
        "save_failure_count": sum(bool(r.get("save_failed")) for r in rows),
        "invalid_accept_attempt_count": sum(int(r.get("invalid_accept_attempts", 0)) for r in rows),
        "wrong_accept_count": sum(bool(r.get("wrong_accept")) for r in rows),
        "timeout_rate": len(timeouts) / len(rows) if rows else 0.0,
        "accepted_conditional_latency_ms": aggregate_times(
            r["annotation_time_ms"]
            for r in accepted
            if isinstance(r.get("annotation_time_ms"), (int, float))
        ),
        "all_image_accepted_under_30_rate": len(under_30) / len(rows) if rows else 0.0,
    }
