"""Immutable loading of the repository acceptance profile."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from segvision.core.errors import ConfigurationError


class _FrozenDict(dict[str, Any]):
    """JSON-serialisable read-only mapping used by the profile snapshot."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("acceptance profile is immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class AcceptanceProfile:
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        def freeze(value: Any) -> Any:
            if isinstance(value, dict):
                return _FrozenDict({str(k): freeze(v) for k, v in value.items()})
            if isinstance(value, list):
                return tuple(freeze(v) for v in value)
            return value

        payload = copy.deepcopy(dict(self.data))
        payload["_immutable"] = True
        object.__setattr__(self, "data", freeze(payload))

    @staticmethod
    def _thaw(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): AcceptanceProfile._thaw(v) for k, v in value.items()}
        if isinstance(value, tuple):
            return [AcceptanceProfile._thaw(v) for v in value]
        return copy.deepcopy(value)

    @property
    def profile_id(self) -> str:
        return str(self.data["profile_id"])

    def __getitem__(self, key: str) -> Any:
        return self._thaw(self.data[key])

    def get(self, key: str, default: Any = None) -> Any:
        return self._thaw(self.data.get(key, default))


def load_acceptance_profile(path: str | Path | None = None) -> AcceptanceProfile:
    if path is None:
        path = (
            Path(__file__).resolve().parents[3]
            / "openspec/changes/build-segvision-v1/acceptance/acceptance-profile.json"
        )
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("profile_id") != "segvision-v1-default":
        raise ConfigurationError("unsupported acceptance profile")
    return AcceptanceProfile(data)
