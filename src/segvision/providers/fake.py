"""Deterministic scripted backend used by headless tests and E2E."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from segvision.core.types import BackendCapabilities, ModelIdentity, PromptBundle

from .base import EncodedState, RawMask


@dataclass(frozen=True, slots=True)
class FakeDecode:
    masks: tuple[np.ndarray, ...]
    qualities: tuple[float, ...] = ()
    stabilities: tuple[float, ...] = ()


class FakeBackend:
    """Scriptable backend with immutable inputs and a public call ledger."""

    def __init__(
        self,
        *,
        initial: FakeDecode | None = None,
        refine: FakeDecode | None = None,
        safe_grid: FakeDecode | None = None,
        cv: FakeDecode | None = None,
        model_name: str = "fake",
    ) -> None:
        identity = ModelIdentity(model_name, "fake-v1", "0" * 64, "python", "fake-preprocess-v1")
        self._capabilities = BackendCapabilities(model=identity)
        self.initial = initial
        self.refine_result = refine
        self.safe_grid_result = safe_grid
        self.cv_result = cv
        self.ledger: list[dict[str, Any]] = []
        self._states: dict[str, EncodedState] = {}

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    @property
    def encode_calls(self) -> int:
        return sum(c["op"] == "encode" for c in self.ledger)

    @property
    def decode_calls(self) -> int:
        return sum(c["op"] == "decode" for c in self.ledger)

    def encode(
        self, crop_rgb: np.ndarray, *, session_id: str, revision: int, crop_fingerprint: str
    ) -> EncodedState:
        copied = np.array(crop_rgb, copy=True)
        token = hashlib.sha256(copied.tobytes() + f"{session_id}:{revision}".encode()).hexdigest()[
            :16
        ]
        state = EncodedState(token, session_id, revision, crop_fingerprint, {"shape": copied.shape})
        self._states[token] = state
        self.ledger.append(
            {"op": "encode", "session_id": session_id, "revision": revision, "token": token}
        )
        return state

    def _convert(
        self, result: FakeDecode | None, prompt: PromptBundle, multimask_count: int
    ) -> tuple[RawMask, ...]:
        if result is None:
            return ()
        out: list[RawMask] = []
        for i, mask in enumerate(result.masks[:multimask_count]):
            q = result.qualities[i] if i < len(result.qualities) else 1.0 - i * 0.01
            s = result.stabilities[i] if i < len(result.stabilities) else 1.0 - i * 0.01
            out.append(
                RawMask(
                    mask,
                    float(q),
                    float(s),
                    i,
                    {"fake": True, "index": i, "points": len(prompt.points_crop_xy)},
                )
            )
        return tuple(out)

    def decode(
        self, encoded: EncodedState, prompt: PromptBundle, *, multimask_count: int
    ) -> Sequence[RawMask]:
        state = self._states.get(encoded.token)
        if state is None:
            raise ValueError("unknown encoded state")
        if encoded.session_id != state.session_id or encoded.revision != state.revision:
            raise ValueError("encoded state identity mismatch")
        if multimask_count < 1:
            raise ValueError("multimask_count must be positive")
        result: FakeDecode | None
        if prompt.points_crop_xy:
            # Automatic safe-grid prompts carry no previous state; human
            # refinement always carries the selected opaque state.
            if prompt.previous_mask_state is None and self.safe_grid_result is not None:
                result = self.safe_grid_result
                kind = "safe_grid"
            else:
                result = self.refine_result
                kind = "refine"
        elif prompt.previous_mask_state is not None:
            result = self.refine_result
            kind = "refine"
        else:
            result = self.initial
            kind = "box"
        self.ledger.append(
            {
                "op": "decode",
                "kind": kind,
                "revision": encoded.revision,
                "multimask_count": multimask_count,
                "points": [p.to_dict() for p in prompt.points_crop_xy],
            }
        )
        return self._convert(result, prompt, multimask_count)

    def decode_mask_prompt(
        self, encoded: EncodedState, prompt: PromptBundle, mask_state: Any
    ) -> Sequence[RawMask]:
        if encoded.token not in self._states:
            raise ValueError("unknown encoded state")
        self.ledger.append(
            {"op": "decode_mask_prompt", "revision": encoded.revision, "multimask_count": 1}
        )
        return self._convert(self.cv_result, prompt, 1)

    def mask_prompt_from_binary(self, encoded: EncodedState, mask: np.ndarray) -> Any:
        arr = np.asarray(mask)
        self.ledger.append(
            {
                "op": "mask_prompt_from_binary",
                "revision": encoded.revision,
                "shape": list(arr.shape),
            }
        )
        return {"binary_mask": arr.copy()}

    def release(self, encoded: EncodedState) -> None:
        self._states.pop(encoded.token, None)
        self.ledger.append({"op": "release", "token": encoded.token})
