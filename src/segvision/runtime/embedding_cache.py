"""Bounded session-owned encoded-state cache."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheKey:
    session_id: str
    revision: int
    backend_fingerprint: str
    preprocessing_version: str
    crop_fingerprint: str
    crop_rect_full: tuple[int, int, int, int]


class BoundedEmbeddingCache:
    def __init__(self, max_entries: int = 2) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._values: OrderedDict[CacheKey, Any] = OrderedDict()

    def put(self, key: CacheKey, value: Any) -> None:
        self._values.pop(key, None)
        self._values[key] = value
        while len(self._values) > self.max_entries:
            self._values.popitem(last=False)

    def get(self, key: CacheKey) -> Any | None:
        value = self._values.get(key)
        if value is not None:
            self._values.move_to_end(key)
        return value

    def release_session(self, session_id: str) -> None:
        for key in list(self._values):
            if key.session_id == session_id:
                self._values.pop(key, None)

    def clear(self) -> None:
        self._values.clear()

    def __len__(self) -> int:
        return len(self._values)
