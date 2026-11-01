"""Immutable public values and JSON-safe result records.

Provider tensors and opaque mask state never leave the session.  Public
records contain only scalar values, IDs, NumPy crop masks, and serialisable
provenance.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

import numpy as np


class CandidateSource(StrEnum):
    SAM_BOX = "sam_box"
    SAM_SAFE_GRID = "sam_safe_grid"
    SAM_CV = "sam_cv"
    CV_DIRECT = "cv_direct"
    MANUAL_EMPTY = "manual_empty"
    MANUAL_EDIT = "manual_edit"


class GeneratorKind(StrEnum):
    MODEL = "model"
    CV_RECIPE = "cv_recipe"
    MANUAL = "manual"


class OutcomeKind(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    backend_name: str
    model_version: str
    checkpoint_sha256: str
    runtime_version: str
    preprocessing_version: str

    def __post_init__(self) -> None:
        values = (
            self.backend_name,
            self.model_version,
            self.checkpoint_sha256,
            self.runtime_version,
            self.preprocessing_version,
        )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("model identity fields must be non-empty strings")
        if re.fullmatch(r"[0-9a-fA-F]{64}", self.checkpoint_sha256) is None:
            raise ValueError("checkpoint_sha256 must be a hexadecimal SHA-256")

    def to_dict(self) -> dict[str, str]:
        return {
            "backend_name": self.backend_name,
            "model_version": self.model_version,
            "checkpoint_sha256": self.checkpoint_sha256,
            "runtime_version": self.runtime_version,
            "preprocessing_version": self.preprocessing_version,
        }


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    supports_box_prompt: bool = True
    supports_point_prompt: bool = True
    supports_previous_mask: bool = True
    supports_mask_prompt: bool = True
    initial_multimask_count: int = 3
    score_kind: str = "provider_local_quality"
    model: ModelIdentity | None = None

    def __post_init__(self) -> None:
        flags = (
            self.supports_box_prompt,
            self.supports_point_prompt,
            self.supports_previous_mask,
            self.supports_mask_prompt,
        )
        if any(not isinstance(flag, bool) for flag in flags):
            raise ValueError("backend capability flags must be bool")
        if (
            not isinstance(self.initial_multimask_count, int)
            or isinstance(self.initial_multimask_count, bool)
            or self.initial_multimask_count < 1
            or not isinstance(self.score_kind, str)
            or not self.score_kind
        ):
            raise ValueError("invalid backend capability values")
        if self.model is not None and not isinstance(self.model, ModelIdentity):
            raise TypeError("backend model must be a ModelIdentity")

    def validate_for_v1(self) -> None:
        from .errors import ConfigurationError

        if not (self.supports_box_prompt and self.supports_point_prompt):
            raise ConfigurationError("backend must support box and point prompts")
        if not self.supports_previous_mask:
            raise ConfigurationError("backend must support previous mask state")
        if self.initial_multimask_count < 3:
            raise ConfigurationError("backend must provide at least three initial masks")


@dataclass(frozen=True, slots=True)
class WarningRecord:
    code: str
    message: str
    severity: str = "warning"

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.code, self.message, self.severity)
        ):
            raise ValueError("warning code, message, and severity are required")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass(frozen=True, slots=True)
class PromptPoint:
    x: int
    y: int
    label: int  # 1 foreground, 0 background
    point_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.x, int)
            or isinstance(self.x, bool)
            or not isinstance(self.y, int)
            or isinstance(self.y, bool)
            or self.label not in (0, 1)
            or isinstance(self.label, bool)
            or (self.point_id is not None and (not isinstance(self.point_id, str) or not self.point_id))
        ):
            raise ValueError("prompt point requires integer x/y and label 0 or 1")

    def to_dict(self, *, include_id: bool = False) -> dict[str, int | str]:
        value: dict[str, int | str] = {"x": self.x, "y": self.y, "label": self.label}
        if include_id and self.point_id is not None:
            value["point_id"] = self.point_id
        return value


@dataclass(frozen=True, slots=True)
class FrozenRegion:
    """An immutable foreground/background decision retained across model passes."""

    region_id: str
    label: int
    mask: np.ndarray
    source_candidate_id: str
    pass_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.region_id, str) or not self.region_id:
            raise ValueError("region_id is required")
        if self.label not in (0, 1) or isinstance(self.label, bool):
            raise ValueError("frozen region label must be 0 or 1")
        if not isinstance(self.source_candidate_id, str) or not self.source_candidate_id:
            raise ValueError("source_candidate_id is required")
        if not isinstance(self.pass_index, int) or isinstance(self.pass_index, bool) or self.pass_index < 1:
            raise ValueError("pass_index must be a positive integer")
        object.__setattr__(self, "mask", _freeze_mask(self.mask))
        if not self.mask.any():
            raise ValueError("frozen region mask cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "label": self.label,
            "source_candidate_id": self.source_candidate_id,
            "pass_index": self.pass_index,
            "area": int(self.mask.sum()),
            "mask_sha256": hashlib.sha256(np.ascontiguousarray(self.mask).tobytes()).hexdigest(),
        }


@dataclass(frozen=True, slots=True)
class PromptBundle:
    box_crop_xyxy: tuple[int, int, int, int]
    points_crop_xy: tuple[PromptPoint, ...] = ()
    previous_mask_state: Any = None  # opaque and never serialised

    def __post_init__(self) -> None:
        box = tuple(self.box_crop_xyxy)
        if len(box) != 4 or any(
            not isinstance(value, int) or isinstance(value, bool) for value in box
        ):
            raise ValueError("box_crop_xyxy must contain four integer coordinates")
        object.__setattr__(self, "box_crop_xyxy", box)
        points = tuple(self.points_crop_xy)
        if any(not isinstance(point, PromptPoint) for point in points):
            raise TypeError("points_crop_xy must contain PromptPoint values")
        object.__setattr__(self, "points_crop_xy", points)


@dataclass(frozen=True, slots=True)
class Provenance:
    generator_kind: GeneratorKind
    source: CandidateSource
    model: ModelIdentity | None = None
    recipe_id: str | None = None
    recipe_hash: str | None = None
    parent_candidate_id: str | None = None
    prompt_kind: str = "box"

    def __post_init__(self) -> None:
        if not isinstance(self.generator_kind, GeneratorKind) or not isinstance(
            self.source, CandidateSource
        ):
            raise TypeError("provenance generator/source values are invalid")
        if not isinstance(self.prompt_kind, str) or not self.prompt_kind:
            raise ValueError("prompt_kind is required")
        for name in ("recipe_id", "recipe_hash", "parent_candidate_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{name} must be a non-empty string when supplied")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "generator_kind": self.generator_kind.value,
            "source": self.source.value,
            "recipe_id": self.recipe_id,
            "recipe_hash": self.recipe_hash,
            "parent_candidate_id": self.parent_candidate_id,
            "prompt_kind": self.prompt_kind,
        }
        out["model"] = self.model.to_dict() if self.model else None
        return out


def _freeze_mask(mask: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask)
    if arr.ndim != 2 or arr.dtype != np.bool_:
        raise ValueError("mask must be a two-dimensional numpy.bool_ array")
    arr = arr.copy()
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    session_id: str
    revision: int
    mask: np.ndarray
    provenance: Provenance
    can_refine: bool
    can_local_edit: bool
    can_commit: bool
    quality: float = 0.0
    stability: float = 0.0
    native_index: int = 0
    warnings: tuple[WarningRecord, ...] = ()
    prompt_points: tuple[PromptPoint, ...] = ()
    _mask_state: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.candidate_id, str)
            or not self.candidate_id
            or not isinstance(self.session_id, str)
            or not self.session_id
            or not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
            or not all(
                isinstance(value, bool)
                for value in (self.can_refine, self.can_local_edit, self.can_commit)
            )
            or not isinstance(self.native_index, int)
            or isinstance(self.native_index, bool)
            or self.native_index < 0
            or not math.isfinite(float(self.quality))
            or not math.isfinite(float(self.stability))
        ):
            raise ValueError("candidate identity, capability, or metric is invalid")
        if any(not isinstance(value, WarningRecord) for value in self.warnings):
            raise TypeError("candidate warnings must be WarningRecord values")
        if any(not isinstance(value, PromptPoint) for value in self.prompt_points):
            raise TypeError("candidate prompt_points must be PromptPoint values")
        object.__setattr__(self, "mask", _freeze_mask(self.mask))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "prompt_points", tuple(self.prompt_points))

    @property
    def source(self) -> CandidateSource:
        return self.provenance.source

    @property
    def has_edge_warning(self) -> bool:
        return any(w.code == "TOUCHES_WORK_CROP_EDGE" for w in self.warnings)

    def to_dict(self, *, include_mask: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "session_id": self.session_id,
            "revision": self.revision,
            "source": self.source.value,
            "provenance": self.provenance.to_dict(),
            "capabilities": {
                "can_refine": self.can_refine,
                "can_local_edit": self.can_local_edit,
                "can_commit": self.can_commit,
            },
            "quality": float(self.quality),
            "stability": float(self.stability),
            "native_index": int(self.native_index),
            "warnings": [w.to_dict() for w in self.warnings],
            "prompt_points": [p.to_dict() for p in self.prompt_points],
        }
        if include_mask:
            out["mask"] = self.mask.astype(np.uint8).tolist()
        return out


@dataclass(frozen=True, slots=True)
class ProposalDiagnostics:
    removed: tuple[dict[str, Any], ...] = ()
    encoder_calls: int = 0
    decoder_calls: int = 0
    warnings: tuple[WarningRecord, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.encoder_calls, int)
            or isinstance(self.encoder_calls, bool)
            or not isinstance(self.decoder_calls, int)
            or isinstance(self.decoder_calls, bool)
            or self.encoder_calls < 0
            or self.decoder_calls < 0
        ):
            raise ValueError("backend call counts cannot be negative")
        if any(not isinstance(value, WarningRecord) for value in self.warnings):
            raise TypeError("diagnostic warnings must be WarningRecord values")
        object.__setattr__(self, "removed", tuple(dict(item) for item in self.removed))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "removed": list(self.removed),
            "encoder_calls": self.encoder_calls,
            "decoder_calls": self.decoder_calls,
            "warnings": [w.to_dict() for w in self.warnings],
        }


@dataclass(frozen=True, slots=True)
class Uncertainty:
    disagreement_mask_roi: np.ndarray
    crop_edge_risk_mask_roi: np.ndarray

    def __post_init__(self) -> None:
        disagreement = _freeze_mask(self.disagreement_mask_roi)
        edge = _freeze_mask(self.crop_edge_risk_mask_roi)
        if disagreement.shape != edge.shape:
            raise ValueError("uncertainty masks must have the same shape")
        object.__setattr__(self, "disagreement_mask_roi", disagreement)
        object.__setattr__(self, "crop_edge_risk_mask_roi", edge)


@dataclass(frozen=True, slots=True)
class ProposalSet:
    session_id: str
    revision: int
    candidates: tuple[Candidate, ...]
    uncertainty: Uncertainty
    diagnostics: ProposalDiagnostics
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.session_id, str)
            or not self.session_id
            or not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
        ):
            raise ValueError("proposal identity is invalid")
        candidates = tuple(self.candidates)
        if any(
            not isinstance(candidate, Candidate)
            or candidate.session_id != self.session_id
            or candidate.revision != self.revision
            for candidate in candidates
        ):
            raise ValueError("proposal candidates must match proposal identity")
        if not isinstance(self.uncertainty, Uncertainty) or not isinstance(
            self.diagnostics, ProposalDiagnostics
        ):
            raise TypeError("proposal uncertainty and diagnostics are invalid")
        if not all(math.isfinite(float(value)) for value in (self.started_at, self.finished_at)):
            raise ValueError("proposal timings must be finite")
        object.__setattr__(self, "candidates", candidates)

    @property
    def timings(self) -> dict[str, float]:
        return {"elapsed_ms": max(0.0, (self.finished_at - self.started_at) * 1000.0)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "revision": self.revision,
            "candidates": [c.to_dict() for c in self.candidates],
            "uncertainty": {
                "disagreement_mask_roi": self.uncertainty.disagreement_mask_roi.astype(
                    np.uint8
                ).tolist(),
                "crop_edge_risk_mask_roi": self.uncertainty.crop_edge_risk_mask_roi.astype(
                    np.uint8
                ).tolist(),
            },
            "diagnostics": self.diagnostics.to_dict(),
            "timings": self.timings,
        }


@dataclass(frozen=True, slots=True)
class CommitResult:
    outcome: OutcomeKind
    session_id: str
    revision: int
    image_id: str
    class_id: str
    full_image_mask: np.ndarray
    candidate_id: str
    policy_id: str
    warnings: tuple[WarningRecord, ...] = ()
    acknowledged_warning_codes: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    accept_attempted: bool = True
    acceptance_actor: str = "interactive_user"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.outcome, OutcomeKind)
            or not isinstance(self.session_id, str)
            or not self.session_id
            or not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
            or not isinstance(self.image_id, str)
            or not self.image_id
            or not isinstance(self.class_id, str)
            or not self.class_id
            or not isinstance(self.candidate_id, str)
            or not self.candidate_id
            or not isinstance(self.policy_id, str)
            or not self.policy_id
            or not isinstance(self.accept_attempted, bool)
            or not isinstance(self.acceptance_actor, str)
            or not self.acceptance_actor
        ):
            raise ValueError("commit identity/outcome is invalid")
        if any(not isinstance(value, WarningRecord) for value in self.warnings):
            raise TypeError("commit warnings must be WarningRecord values")
        object.__setattr__(self, "full_image_mask", _freeze_mask(self.full_image_mask))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(
            self, "acknowledged_warning_codes", tuple(self.acknowledged_warning_codes)
        )
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "outcome": self.outcome.value,
            "session_id": self.session_id,
            "revision": self.revision,
            "image_id": self.image_id,
            "class_id": self.class_id,
            "candidate_id": self.candidate_id,
            "policy_id": self.policy_id,
            "mask_shape": list(self.full_image_mask.shape),
            "mask_sha256": hashlib.sha256(self.full_image_mask.tobytes()).hexdigest(),
            "warnings": [w.to_dict() for w in self.warnings],
            "acknowledged_warning_codes": list(self.acknowledged_warning_codes),
            "provenance": dict(self.provenance),
            "accept_attempted": self.accept_attempted,
            "acceptance_actor": self.acceptance_actor,
        }


@dataclass(frozen=True, slots=True)
class ReviewResult:
    session_id: str
    revision: int
    image_id: str
    class_id: str
    policy_id: str
    reason: str
    draft_mask: np.ndarray | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.session_id, str)
            or not self.session_id
            or not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
            or not isinstance(self.image_id, str)
            or not self.image_id
            or not isinstance(self.class_id, str)
            or not self.class_id
            or not isinstance(self.policy_id, str)
            or not self.policy_id
            or not isinstance(self.reason, str)
            or not self.reason.strip()
        ):
            raise ValueError("review identity and reason are required")
        if self.draft_mask is not None:
            object.__setattr__(self, "draft_mask", _freeze_mask(self.draft_mask))
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "outcome": OutcomeKind.NEEDS_REVIEW.value,
            "session_id": self.session_id,
            "revision": self.revision,
            "image_id": self.image_id,
            "class_id": self.class_id,
            "policy_id": self.policy_id,
            "reason": self.reason,
            "has_draft": self.draft_mask is not None,
            "provenance": dict(self.provenance),
        }


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
