"""Official MobileSAM TinyViT adapter for checksum-verified CPU inference."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from segvision.core.errors import ModelApprovalError, ModelArtifactError
from segvision.core.types import BackendCapabilities, ModelIdentity, PromptBundle

from .base import EncodedState, RawMask


@dataclass(slots=True)
class _PredictorState:
    predictor: Any
    session_id: str
    revision: int
    crop_fingerprint: str
    crop_shape: tuple[int, int]


class MobileSAMCPUBackend:
    """MobileSAM ``vit_t`` using one shared CPU model and per-encode predictors."""

    def __init__(
        self,
        *,
        checkpoint_path: str | None = None,
        checkpoint_sha256: str | None = None,
        approved: bool = False,
        model: Any = None,
        predictor_factory: Callable[[Any], Any] | None = None,
        model_version: str = "MobileSAM-TinyViT",
    ) -> None:
        if not approved:
            raise ModelApprovalError("MobileSAM checkpoint requires explicit approval")
        if checkpoint_path is None or checkpoint_sha256 is None:
            raise ModelArtifactError("local checksum-verified checkpoint required")

        from segvision.models.manifest import verify_sha256

        verified_sha256 = verify_sha256(checkpoint_path, checkpoint_sha256)
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise ModelArtifactError("PyTorch CPU runtime is unavailable") from exc

        if model is None:
            try:
                from mobile_sam import SamPredictor, sam_model_registry
            except ImportError as exc:  # pragma: no cover - dependency gate
                raise ModelArtifactError("official mobile_sam package is unavailable") from exc
            # Checksum validation above deliberately occurs before checkpoint deserialization.
            model = sam_model_registry["vit_t"](checkpoint=checkpoint_path)
            model.to(device="cpu")
            model.eval()
            predictor_factory = SamPredictor
        elif predictor_factory is None:
            raise ModelArtifactError("an injected model requires an injected predictor factory")

        self._model = model
        self._predictor_factory = predictor_factory
        self._identity = ModelIdentity(
            "mobile_sam_torch_cpu",
            model_version,
            verified_sha256,
            f"torch-{torch.__version__};device=cpu",
            "mobilesam-sam-predictor-v1",
        )
        self._capabilities = BackendCapabilities(model=self._identity)
        self._states: dict[str, _PredictorState] = {}
        self.ledger: list[dict[str, Any]] = []

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def encode(
        self, crop_rgb: np.ndarray, *, session_id: str, revision: int, crop_fingerprint: str
    ) -> EncodedState:
        arr = np.asarray(crop_rgb)
        if arr.ndim != 3 or arr.shape[2] != 3 or arr.dtype != np.uint8:
            raise ModelArtifactError("MobileSAM encode requires uint8[H,W,3] RGB crop")
        owned = np.array(arr, copy=True)
        token = hashlib.sha256(
            owned.tobytes()
            + session_id.encode("utf-8")
            + str(revision).encode("ascii")
            + crop_fingerprint.encode("utf-8")
            + self._identity.checkpoint_sha256.encode("ascii")
        ).hexdigest()
        assert self._predictor_factory is not None
        predictor = self._predictor_factory(self._model)
        predictor.set_image(owned, image_format="RGB")
        self._states[token] = _PredictorState(
            predictor,
            session_id,
            revision,
            crop_fingerprint,
            (int(owned.shape[0]), int(owned.shape[1])),
        )
        self.ledger.append(
            {"op": "encode", "session_id": session_id, "revision": revision, "token": token}
        )
        return EncodedState(token, session_id, revision, crop_fingerprint, None)

    def _state(self, encoded: EncodedState) -> _PredictorState:
        state = self._states.get(encoded.token)
        if (
            state is None
            or encoded.session_id != state.session_id
            or encoded.revision != state.revision
            or encoded.crop_fingerprint != state.crop_fingerprint
        ):
            raise ModelArtifactError("encoded state released or identity mismatch")
        return state

    @staticmethod
    def _stability(low_res_logits: np.ndarray) -> float:
        logits = np.asarray(low_res_logits, dtype=np.float32)
        high = int(np.count_nonzero(logits > 1.0))
        low = int(np.count_nonzero(logits > -1.0))
        return float(high / low) if low else 0.0

    @staticmethod
    def _mask_with_point_constraints(
        full_res_logits: np.ndarray,
        points: tuple[Any, ...],
        default_threshold: float,
    ) -> tuple[np.ndarray, float, bool]:
        logits = np.asarray(full_res_logits, dtype=np.float32)
        threshold = float(default_threshold)
        base_mask = logits > threshold
        if not points or all(bool(base_mask[p.y, p.x]) == bool(p.label) for p in points):
            return np.array(base_mask, dtype=np.bool_, copy=True), threshold, True

        positive = [float(logits[p.y, p.x]) for p in points if p.label == 1]
        negative = [float(logits[p.y, p.x]) for p in points if p.label == 0]
        lower = max(negative) if negative else -np.inf
        upper = (
            float(np.nextafter(np.float32(min(positive)), np.float32(-np.inf)))
            if positive
            else np.inf
        )
        if lower > upper:
            return np.array(base_mask, dtype=np.bool_, copy=True), threshold, False
        threshold = float(np.clip(threshold, lower, upper))
        constrained = logits > threshold
        satisfied = all(bool(constrained[p.y, p.x]) == bool(p.label) for p in points)
        return np.array(constrained, dtype=np.bool_, copy=True), threshold, satisfied

    def _decode(
        self,
        encoded: EncodedState,
        prompt: PromptBundle,
        *,
        multimask_count: int,
        ledger_op: str,
    ) -> tuple[RawMask, ...]:
        if multimask_count < 1 or multimask_count > 3:
            raise ModelArtifactError("MobileSAM supports one to three requested masks")
        state = self._state(encoded)
        points = prompt.points_crop_xy
        point_coords = (
            np.asarray([(point.x, point.y) for point in points], dtype=np.float32)
            if points
            else None
        )
        point_labels = (
            np.asarray([point.label for point in points], dtype=np.int32) if points else None
        )
        box = np.asarray(prompt.box_crop_xyxy, dtype=np.float32)
        mask_input = None
        if prompt.previous_mask_state is not None:
            mask_input = np.array(prompt.previous_mask_state, dtype=np.float32, copy=True)
            if mask_input.ndim != 3 or mask_input.shape[0] != 1:
                raise ModelArtifactError("previous MobileSAM mask state must be 1xHxW logits")

        full_res_logits, qualities, low_res_masks = state.predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            box=box,
            mask_input=mask_input,
            multimask_output=multimask_count > 1,
            return_logits=True,
        )
        full_res_logits = np.asarray(full_res_logits, dtype=np.float32)
        qualities = np.asarray(qualities)
        low_res_masks = np.asarray(low_res_masks)
        if full_res_logits.ndim != 3 or full_res_logits.shape[1:] != state.crop_shape:
            raise ModelArtifactError("MobileSAM returned masks with an invalid source shape")
        count = min(
            multimask_count,
            full_res_logits.shape[0],
            qualities.shape[0],
            low_res_masks.shape[0],
        )
        default_threshold = float(
            getattr(getattr(state.predictor, "model", None), "mask_threshold", 0.0)
        )
        human_refinement = prompt.previous_mask_state is not None and bool(points)
        applied_thresholds: list[float] = []
        constraints_satisfied: list[bool] = []
        outputs: list[RawMask] = []
        for index in range(count):
            output_points = points if human_refinement else ()
            mask, threshold, satisfied = self._mask_with_point_constraints(
                full_res_logits[index], output_points, default_threshold
            )
            applied_thresholds.append(threshold)
            constraints_satisfied.append(satisfied)
            logits = np.array(low_res_masks[index : index + 1], dtype=np.float32, copy=True)
            logits.setflags(write=False)
            outputs.append(
                RawMask(
                    mask,
                    float(qualities[index]),
                    self._stability(low_res_masks[index]),
                    index,
                    logits,
                )
            )
        self.ledger.append(
            {
                "op": ledger_op,
                "revision": encoded.revision,
                "multimask_count": multimask_count,
                "points": [point.to_dict() for point in points],
                "previous_state": prompt.previous_mask_state is not None,
                "mask_thresholds": applied_thresholds,
                "point_constraints_satisfied": constraints_satisfied,
            }
        )
        return tuple(outputs)

    def decode(
        self, encoded: EncodedState, prompt: PromptBundle, *, multimask_count: int
    ) -> tuple[RawMask, ...]:
        return self._decode(
            encoded, prompt, multimask_count=multimask_count, ledger_op="decode"
        )

    def mask_prompt_from_binary(self, encoded: EncodedState, mask: np.ndarray) -> np.ndarray:
        state = self._state(encoded)
        arr = np.asarray(mask)
        if arr.ndim != 2 or arr.shape != state.crop_shape or arr.dtype != np.bool_:
            raise ModelArtifactError("mask prompt must be a crop-resolution bool mask")
        target_size = (256, 256)
        prompt_encoder = getattr(getattr(state.predictor, "model", None), "prompt_encoder", None)
        configured = getattr(prompt_encoder, "mask_input_size", None)
        if configured is not None and len(configured) == 2:
            target_size = (int(configured[1]), int(configured[0]))
        resized = cv2.resize(
            arr.astype(np.uint8), target_size, interpolation=cv2.INTER_NEAREST
        ).astype(bool)
        logits = np.where(resized, 10.0, -10.0).astype(np.float32)[None, :, :]
        logits.setflags(write=False)
        self.ledger.append({"op": "mask_prompt_from_binary", "revision": encoded.revision})
        return logits

    def decode_mask_prompt(
        self, encoded: EncodedState, prompt: PromptBundle, mask_state: Any
    ) -> tuple[RawMask, ...]:
        converted = PromptBundle(
            prompt.box_crop_xyxy,
            prompt.points_crop_xy,
            np.array(mask_state, dtype=np.float32, copy=True),
        )
        return self._decode(
            encoded, converted, multimask_count=1, ledger_op="decode_mask_prompt"
        )

    def release(self, encoded: EncodedState) -> None:
        state = self._states.pop(encoded.token, None)
        if state is not None and hasattr(state.predictor, "reset_image"):
            state.predictor.reset_image()
        self.ledger.append({"op": "release", "token": encoded.token})
