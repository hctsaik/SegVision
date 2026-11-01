"""Validated, serialisable acceptance event records.

The core session already owns its event ledger.  This module provides the
acceptance-layer representation used by runners and independent auditors; it
never exposes model tensors or changes the session ledger.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SessionEvent:
    session_id: str
    revision: int
    sequence: int
    monotonic_ns: int
    event: str
    job_id: str | None = None
    candidate_id: str | None = None
    actor: str = "system"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("session_id is required")
        if not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in (self.revision, self.sequence, self.monotonic_ns)
        ):
            raise ValueError("event counters and time must be integers")
        if self.revision < 1 or self.sequence < 1 or self.monotonic_ns < 0:
            raise ValueError("event revision, sequence, and time must be positive")
        if not isinstance(self.event, str) or not self.event:
            raise ValueError("event name is required")
        if not isinstance(self.actor, str) or not self.actor:
            raise ValueError("event actor is required")
        if not isinstance(self.details, Mapping):
            raise TypeError("event details must be a mapping")
        object.__setattr__(self, "details", dict(self.details))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SessionEvent:
        # Core events use ``event`` while the standalone EventLog historically
        # used ``name``.  Accept both spellings at this boundary only.
        return cls(
            session_id=str(value.get("session_id", "")),
            revision=int(value.get("revision", 0)),
            sequence=int(value.get("sequence", 0)),
            monotonic_ns=int(value.get("monotonic_ns", value.get("timestamp_ns", -1))),
            event=str(value.get("event", value.get("name", ""))),
            job_id=value.get("job_id"),
            candidate_id=value.get("candidate_id"),
            actor=str(value.get("actor", "system")),
            details=value.get("details", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "revision": self.revision,
            "sequence": self.sequence,
            "monotonic_ns": self.monotonic_ns,
            "event": self.event,
            "job_id": self.job_id,
            "candidate_id": self.candidate_id,
            "actor": self.actor,
            "details": dict(self.details),
        }


def validate_event_stream(
    events: Iterable[Mapping[str, Any] | SessionEvent],
) -> tuple[SessionEvent, ...]:
    """Validate order and identity without filtering any event."""

    parsed = tuple(
        event if isinstance(event, SessionEvent) else SessionEvent.from_mapping(event)
        for event in events
    )
    previous_time = -1
    previous_sequence = 0
    session_id: str | None = None
    for event in parsed:
        if session_id is None:
            session_id = event.session_id
        elif event.session_id != session_id:
            raise ValueError("event stream mixes session identities")
        if event.sequence != previous_sequence + 1:
            raise ValueError("event sequence is not contiguous")
        if event.monotonic_ns < previous_time:
            raise ValueError("event timestamps must be monotonic")
        previous_sequence = event.sequence
        previous_time = event.monotonic_ns
    return parsed


@dataclass
class EventRecorder:
    """Small injectable-clock recorder for acceptance and GUI tests."""

    session_id: str
    revision: int = 1
    clock_ns: Any = None
    events: list[SessionEvent] = field(default_factory=list)

    def emit(
        self,
        event: str,
        *,
        revision: int | None = None,
        job_id: str | None = None,
        candidate_id: str | None = None,
        actor: str = "system",
        **details: Any,
    ) -> SessionEvent:
        if self.clock_ns is None:
            import time

            now = time.monotonic_ns()
        else:
            now = int(self.clock_ns())
        if self.events and now < self.events[-1].monotonic_ns:
            raise ValueError("event timestamps must be monotonic")
        item = SessionEvent(
            self.session_id,
            self.revision if revision is None else revision,
            len(self.events) + 1,
            now,
            event,
            job_id,
            candidate_id,
            actor,
            details,
        )
        self.events.append(item)
        return item

    def to_dict(self, *, run_id: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": 1,
            "events": [event.to_dict() for event in validate_event_stream(self.events)],
        }
        if run_id is not None:
            out["run_id"] = run_id
        return out

    def to_json(self, *, run_id: str | None = None) -> str:
        return json.dumps(self.to_dict(run_id=run_id), sort_keys=True, separators=(",", ":"))


__all__ = ["EventRecorder", "SessionEvent", "validate_event_stream"]
