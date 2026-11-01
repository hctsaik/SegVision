"""Candidate validation, ranking, allocation, uncertainty and fusion."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .errors import ConfigurationError, InvalidMask
from .geometry import CropContext, validate_crop_mask, work_crop_edge_warning
from .mask_ops import binary_iou
from .types import Candidate, CandidateSource, Uncertainty, WarningRecord


@dataclass(frozen=True, slots=True)
class CandidatePolicy:
    max_candidates: int = 3
    duplicate_iou_threshold: float = 0.995
    near_full_reject_fraction: float = 0.995
    safe_grid_max_points: int = 2
    safe_grid_margin_fraction: float = 0.01
    safe_grid_margin_min_px: int = 2
    fusion_enabled_by_default: bool = False

    def __post_init__(self) -> None:
        if self.max_candidates != 3 or self.safe_grid_max_points != 2:
            raise ConfigurationError(
                "v1 candidate policy requires max_candidates=3 and safe_grid_max_points=2"
            )
        if not (0 < self.duplicate_iou_threshold <= 1 and 0 < self.near_full_reject_fraction <= 1):
            raise ConfigurationError("candidate thresholds are invalid")


DEFAULT_CANDIDATE_POLICY = CandidatePolicy()


def validate_candidate_mask(
    mask: np.ndarray,
    context: CropContext,
    points: Sequence[tuple[int, int, int]] = (),
    policy: CandidatePolicy | None = None,
) -> tuple[np.ndarray, list[WarningRecord], str | None]:
    policy = policy or DEFAULT_CANDIDATE_POLICY
    try:
        arr = validate_crop_mask(mask, context)
    except InvalidMask:
        return np.asarray(mask), [], "INVALID_MASK"
    if not arr.any():
        return arr, [], "EMPTY_MASK"
    if float(arr.mean()) >= policy.near_full_reject_fraction:
        return arr, [], "NEAR_FULL_MASK"
    for x, y, label in points:
        cx, cy = x - context.crop_rect_full[0], y - context.crop_rect_full[1]
        if not (0 <= cy < arr.shape[0] and 0 <= cx < arr.shape[1]):
            return arr, [], "POINT_OUTSIDE_CROP"
        expected = bool(label)
        if bool(arr[cy, cx]) != expected:
            return arr, [], "POINT_CONSTRAINT_VIOLATION"
    warnings: list[WarningRecord] = []
    edge = work_crop_edge_warning(arr, context)
    if edge:
        warnings.append(edge)
    return arr, warnings, None


def rank_candidates(candidates: Sequence[Candidate]) -> list[Candidate]:
    return sorted(
        candidates, key=lambda c: (-c.quality, -c.stability, c.native_index, c.candidate_id)
    )


def deduplicate_candidates(
    candidates: Sequence[Candidate], threshold: float = 0.995
) -> tuple[list[Candidate], list[dict[str, object]]]:
    kept: list[Candidate] = []
    removed: list[dict[str, object]] = []
    for candidate in rank_candidates(candidates):
        duplicate = next(
            (other for other in kept if binary_iou(candidate.mask, other.mask) >= threshold), None
        )
        if duplicate is None:
            kept.append(candidate)
        else:
            removed.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "reason": "DUPLICATE",
                    "kept": duplicate.candidate_id,
                }
            )
    return kept, removed


def allocate_candidates(
    candidates: Sequence[Candidate], max_candidates: int = 3
) -> tuple[Candidate, ...]:
    if max_candidates != 3:
        raise ConfigurationError("v1 public candidate cap is exactly three")
    ranked = rank_candidates(candidates)
    boxes = [c for c in ranked if c.source == CandidateSource.SAM_BOX]
    grids = [c for c in ranked if c.source == CandidateSource.SAM_SAFE_GRID]
    cvs = [c for c in ranked if c.source == CandidateSource.SAM_CV]
    selected: list[Candidate] = []
    if boxes:
        selected.append(boxes[0])
        alternatives = boxes[1:] + grids
        if alternatives:
            selected.append(
                min(
                    alternatives,
                    key=lambda c: (
                        binary_iou(c.mask, selected[0].mask),
                        -c.quality,
                        -c.stability,
                        c.native_index,
                        c.candidate_id,
                    ),
                )
            )
    elif grids:
        selected.append(grids[0])
    if cvs and len(selected) < max_candidates:
        selected.append(cvs[0])
    for c in ranked:
        if len(selected) >= max_candidates:
            break
        if c in selected or c.source == CandidateSource.SAM_CV:
            continue
        if all(binary_iou(c.mask, x.mask) < 0.995 for x in selected):
            selected.append(c)
    return tuple(selected[:max_candidates])


def uncertainty(
    candidates: Sequence[Candidate], shape: tuple[int, int], context: CropContext
) -> Uncertainty:
    masks = [c.mask for c in candidates]
    if len(masks) >= 2:
        union = np.logical_or.reduce(masks)
        inter = np.logical_and.reduce(masks)
        disagreement = union & ~inter
    else:
        disagreement = np.zeros(shape, dtype=np.bool_)
    edge = np.zeros(shape, dtype=np.bool_)
    for c in masks:
        edge |= c
    if shape[0] and shape[1]:
        edge_mask = np.zeros(shape, dtype=np.bool_)
        edge_mask[0, :] = edge[0, :]
        edge_mask[-1, :] = edge[-1, :]
        edge_mask[:, 0] |= edge[:, 0]
        edge_mask[:, -1] |= edge[:, -1]
        edge = edge_mask
    return Uncertainty(disagreement, edge)


@dataclass(frozen=True, slots=True)
class FusionResult:
    mask: np.ndarray
    uncertainty: np.ndarray

    def __post_init__(self) -> None:
        for field in ("mask", "uncertainty"):
            arr = np.asarray(getattr(self, field), dtype=np.bool_).copy()
            arr.setflags(write=False)
            object.__setattr__(self, field, arr)


def fuse_majority(candidates: Sequence[Candidate]) -> FusionResult:
    if len(candidates) != 3:
        raise InvalidMask("majority fusion requires exactly three candidates")
    first = candidates[0]
    if any(
        c.revision != first.revision
        or c.session_id != first.session_id
        or c.mask.shape != first.mask.shape
        for c in candidates[1:]
    ):
        raise InvalidMask("fusion candidates must share session, revision, and shape")
    votes = np.sum(np.stack([c.mask for c in candidates], axis=0), axis=0)
    return FusionResult(votes >= 2, votes == 1)
