"""Narrow interactive backend protocol.

The protocol deliberately uses opaque ``EncodedState``/``mask_state`` values;
the session stores them and never exposes them through public results.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from segvision.core.types import BackendCapabilities, PromptBundle


@dataclass(frozen=True, slots=True)
class EncodedState:
    token: str
    session_id: str
    revision: int
    crop_fingerprint: str
    opaque: Any

    def __post_init__(self) -> None:
        if (
            not isinstance(self.token, str)
            or not self.token
            or not isinstance(self.session_id, str)
            or not self.session_id
            or not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
            or not isinstance(self.crop_fingerprint, str)
            or not self.crop_fingerprint
        ):
            raise ValueError("encoded state identity is invalid")


@dataclass(frozen=True, slots=True)
class RawMask:
    mask: np.ndarray
    quality: float
    stability: float
    native_index: int
    mask_state: Any

    def __post_init__(self) -> None:
        arr = np.asarray(self.mask)
        if arr.dtype != np.bool_ or arr.ndim != 2:
            raise ValueError("backend RawMask must be a 2-D bool mask")
        if (
            not math.isfinite(float(self.quality))
            or not math.isfinite(float(self.stability))
            or not isinstance(self.native_index, int)
            or isinstance(self.native_index, bool)
            or self.native_index < 0
        ):
            raise ValueError("backend RawMask metrics/index are invalid")
        copied = arr.copy()
        copied.setflags(write=False)
        object.__setattr__(self, "mask", copied)


class Backend(Protocol):
    @property
    def capabilities(self) -> BackendCapabilities: ...

    def encode(
        self, crop_rgb: np.ndarray, *, session_id: str, revision: int, crop_fingerprint: str
    ) -> EncodedState: ...

    def decode(
        self, encoded: EncodedState, prompt: PromptBundle, *, multimask_count: int
    ) -> Sequence[RawMask]: ...

    def mask_prompt_from_binary(self, encoded: EncodedState, mask: np.ndarray) -> Any: ...

    def release(self, encoded: EncodedState) -> None: ...
