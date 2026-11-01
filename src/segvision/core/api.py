"""Headless SegVision engine and annotation session."""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from segvision.cv.fixed_recipe import CVResult, execute_recipe
from segvision.providers.base import Backend, EncodedState, RawMask
from segvision.application.config import HISTORY_MAX_DEPTH

from .candidate_policy import (
    CandidatePolicy,
    allocate_candidates,
    deduplicate_candidates,
    uncertainty,
    validate_candidate_mask,
)
from .errors import (
    AcceptValidationError,
    CandidateNotFound,
    ForeignCandidate,
    InvalidImage,
    InvalidPoint,
    RecipeClassMismatch,
    StaleRevision,
    UnsupportedOperation,
)
from .geometry import (
    CropContext,
    create_crop_context,
    expanded_context,
    extract_crop,
    full_to_crop_box,
    image_boundary_warning,
    image_shape,
    reconstruct_full_mask,
    validate_point,
    validate_roi,
)
from .mask_ops import brush, connected_component, erase, fill_holes, grow, shrink
from .policy import DEFAULT_POLICY, AnnotationPolicy
from .recipe import CVRecipe
from .types import (
    Candidate,
    CandidateSource,
    CommitResult,
    FrozenRegion,
    GeneratorKind,
    OutcomeKind,
    PromptBundle,
    PromptPoint,
    ProposalDiagnostics,
    ProposalSet,
    Provenance,
    ReviewResult,
    WarningRecord,
)


def _mask_fingerprint(mask: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(mask).tobytes()).hexdigest()


class SegVisionEngine:
    """Factory for in-memory sessions.

    A backend is injected explicitly, which keeps import and session creation
    deterministic and makes filesystem/GUI/model concerns adapters rather than
    hidden side effects.
    """

    def __init__(
        self,
        backend: Backend,
        *,
        candidate_policy: CandidatePolicy | None = None,
        policy: AnnotationPolicy = DEFAULT_POLICY,
    ) -> None:
        self.backend = backend
        self.policy = policy
        self.candidate_policy = candidate_policy or CandidatePolicy()
        caps = backend.capabilities
        caps.validate_for_v1()

    def start(
        self,
        image: np.ndarray,
        image_id: str,
        class_id: str,
        roi: Sequence[object],
        recipe: CVRecipe | None = None,
    ) -> AnnotationSession:
        return AnnotationSession(self, image, image_id, class_id, roi, recipe)


class AnnotationSession:
    """Owns all opaque model state, revisions, candidate graph and undo."""

    def __init__(
        self,
        engine: SegVisionEngine,
        image: np.ndarray,
        image_id: str,
        class_id: str,
        roi: Sequence[object],
        recipe: CVRecipe | None,
    ) -> None:
        h, w = image_shape(image)
        if (
            not isinstance(image_id, str)
            or not image_id.strip()
            or not isinstance(class_id, str)
            or not class_id.strip()
        ):
            raise InvalidImage("image_id and class_id must be non-empty strings")
        self.engine = engine
        self.session_id = uuid.uuid4().hex
        self.image_id, self.class_id = image_id, class_id
        copied = np.array(image, copy=True, order="C")
        copied.setflags(write=False)
        self._image = copied
        self._source_sha256 = hashlib.sha256(copied.tobytes()).hexdigest()
        self.image_height, self.image_width = h, w
        self.context = create_crop_context((h, w), roi)
        self.recipe = recipe or CVRecipe.disabled(class_id)
        if self.recipe.class_id != class_id:
            raise RecipeClassMismatch("recipe class_id does not match session class_id")
        self.policy = engine.policy
        self.revision = 1
        self._encoded: EncodedState | None = None
        self._encoded_fingerprint: str | None = None
        self._candidates: dict[str, Candidate] = {}
        # Keep an immutable candidate history for provenance even after a
        # proposal is replaced by a local-edit or a refinement revision.
        self._history: dict[str, Candidate] = {}
        self._candidate_counter = 0
        self._current_id: str | None = None
        self._proposal: ProposalSet | None = None
        self._human_points: list[PromptPoint] = []
        self._point_counter = 0
        self._region_counter = 0
        self._pass_index = 1
        self._pass_base_candidate_id: str | None = None
        self._frozen_regions: dict[str, FrozenRegion] = {}
        # Locked decisions live in source-image coordinates so a later ROI
        # pass cannot silently drop a completed region.  Public properties
        # expose the current crop view for compatibility with v1 callers.
        self._frozen_region_full_masks: dict[str, np.ndarray] = {}
        self._locked_foreground = np.zeros((self.image_height, self.image_width), dtype=np.bool_)
        self._locked_background = np.zeros((self.image_height, self.image_width), dtype=np.bool_)
        self._working_mask: np.ndarray | None = None
        self._model_mask: np.ndarray | None = None
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []
        self._manual_mode = False
        self._operations: list[dict[str, Any]] = []
        self._accepted = False
        self._closed = False
        lock_ns = time.monotonic_ns()
        self._first_roi_locked_at = lock_ns / 1_000_000_000
        self.events: list[dict[str, Any]] = []
        self._record("image_visible", timestamp_ns=lock_ns)
        self._record("first_roi_locked", timestamp_ns=lock_ns)

    @property
    def first_roi_locked_at(self) -> float:
        return self._first_roi_locked_at

    @property
    def crop(self) -> np.ndarray:
        return extract_crop(self._image, self.context)

    @property
    def candidates(self) -> tuple[Candidate, ...]:
        return tuple(
            self._proposal.candidates
            if self._proposal and self._proposal.revision == self.revision
            else ()
        )

    @property
    def selected_candidate(self) -> Candidate | None:
        if self._current_id is None:
            return None
        return self._candidates.get(self._current_id)

    @property
    def prompt_points(self) -> tuple[PromptPoint, ...]:
        return tuple(self._human_points)

    @property
    def frozen_regions(self) -> tuple[FrozenRegion, ...]:
        return tuple(self._frozen_regions.values())

    @property
    def locked_foreground(self) -> np.ndarray:
        x0, y0, x1, y1 = self.context.crop_rect_full
        value = self._locked_foreground[y0:y1, x0:x1].copy()
        value.setflags(write=False)
        return value

    @property
    def locked_background(self) -> np.ndarray:
        x0, y0, x1, y1 = self.context.crop_rect_full
        value = self._locked_background[y0:y1, x0:x1].copy()
        value.setflags(write=False)
        return value

    @property
    def locked_foreground_full(self) -> np.ndarray:
        value = self._locked_foreground.copy()
        value.setflags(write=False)
        return value

    @property
    def locked_background_full(self) -> np.ndarray:
        value = self._locked_background.copy()
        value.setflags(write=False)
        return value

    @property
    def pass_index(self) -> int:
        return self._pass_index

    @property
    def composited_mask(self) -> np.ndarray | None:
        if self._working_mask is None:
            return None
        value = self._compose(self._working_mask)
        value.setflags(write=False)
        return value

    @property
    def current_proposal(self) -> ProposalSet | None:
        return self._proposal

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def operation_history(self) -> tuple[dict[str, Any], ...]:
        """Typed, immutable projection of authoritative local operations."""
        return tuple(dict(record) for record in self._operations)

    def _ensure_open(self) -> None:
        if self._closed:
            raise StaleRevision("session is closed")

    def _candidate(self, candidate_id: str) -> Candidate:
        self._ensure_open()
        c = self._candidates.get(candidate_id)
        if c is None:
            # Candidate identifiers carry their originating revision.  Once an
            # ROI change invalidates the graph, preserve the public stale-revision
            # contract instead of leaking an implementation-level not-found error.
            match = re.search(r"-r(\d+)-", candidate_id)
            if match is not None and int(match.group(1)) != self.revision:
                raise StaleRevision(candidate_id)
            raise CandidateNotFound(candidate_id)
        if c.session_id != self.session_id:
            raise ForeignCandidate(candidate_id)
        if c.revision != self.revision:
            raise StaleRevision(candidate_id)
        return c

    def _record(self, name: str, *, timestamp_ns: int | None = None, **payload: Any) -> None:
        name = {
            "proposal_ready": "all_candidates_ready",
            "roi_changed": "roi_relocked",
            "roi_redrawn": "roi_relocked",
            "roi_locked": "first_roi_locked",
            "local_edit_started": "first_local_edit",
            "manual_empty_started": "first_local_edit",
            "human_point_added": "refine_finished",
            "session_closed": "job_cancelled",
        }.get(name, name)
        ns = time.monotonic_ns() if timestamp_ns is None else int(timestamp_ns)
        previous = self.events[-1]["monotonic_ns"] if self.events else 0
        ns = max(ns, previous)
        job_id = payload.pop("job_id", None)
        candidate_id = payload.pop("candidate_id", None)
        actor = payload.pop("actor", "system")
        self.events.append(
            {
                "session_id": self.session_id,
                "revision": self.revision,
                "sequence": len(self.events) + 1,
                "monotonic_ns": ns,
                "event": name,
                "job_id": job_id,
                "candidate_id": candidate_id,
                "actor": actor,
                "details": payload,
            }
        )

    def event_ledger(self, *, run_id: str) -> dict[str, Any]:
        """Return the schema-shaped event stream without exposing opaque state."""
        return {"schema_version": 1, "run_id": run_id, "events": list(self.events)}

    def _make_candidate(
        self,
        raw: RawMask,
        source: CandidateSource,
        *,
        parent: Candidate | None = None,
        prompt_kind: str = "box",
        points: Sequence[PromptPoint] = (),
        recipe_result: CVResult | None = None,
    ) -> tuple[Candidate | None, dict[str, object] | None]:
        mask, warnings, reason = validate_candidate_mask(
            raw.mask,
            self.context,
            [(p.x, p.y, p.label) for p in points],
            self.engine.candidate_policy,
        )
        if reason:
            return None, {"native_index": raw.native_index, "reason": reason}
        if source in (CandidateSource.CV_DIRECT, CandidateSource.MANUAL_EDIT):
            gen = (
                GeneratorKind.CV_RECIPE
                if source == CandidateSource.CV_DIRECT
                else GeneratorKind.MANUAL
            )
            prov = Provenance(
                gen,
                source,
                recipe_id=recipe_result.recipe_id if recipe_result else None,
                recipe_hash=recipe_result.recipe_hash if recipe_result else None,
                parent_candidate_id=parent.candidate_id if parent else None,
                prompt_kind=prompt_kind,
            )
            can_refine, can_edit, can_commit = False, True, source != CandidateSource.MANUAL_EMPTY
        elif source == CandidateSource.MANUAL_EMPTY:
            prov = Provenance(
                GeneratorKind.MANUAL,
                source,
                parent_candidate_id=parent.candidate_id if parent else None,
                prompt_kind=prompt_kind,
            )
            can_refine, can_edit, can_commit = False, True, False
        else:
            prov = Provenance(
                GeneratorKind.MODEL,
                source,
                model=self.engine.backend.capabilities.model,
                parent_candidate_id=parent.candidate_id if parent else None,
                prompt_kind=prompt_kind,
            )
            can_refine, can_edit, can_commit = True, True, True
        self._candidate_counter += 1
        cid = f"{self.session_id[:8]}-r{self.revision}-{source.value}-{raw.native_index}-{self._candidate_counter}"
        c = Candidate(
            cid,
            self.session_id,
            self.revision,
            mask,
            prov,
            can_refine,
            can_edit,
            can_commit,
            float(raw.quality),
            float(raw.stability),
            int(raw.native_index),
            tuple(warnings),
            tuple(points),
            raw.mask_state,
        )
        self._history[c.candidate_id] = c
        return c, None

    def propose(self) -> ProposalSet:
        self._ensure_open()
        if self._manual_mode:
            raise UnsupportedOperation("model calls are locked after local editing; undo first")
        started = time.monotonic()
        self._record("proposal_started")
        self._manual_mode = False
        self._candidates.clear()
        self._current_id = None
        diagnostics: list[dict[str, object]] = []
        warnings: list[WarningRecord] = []
        cv = execute_recipe(self.crop, self.recipe, self.context)
        raw_candidates: list[Candidate] = []
        enc_calls_before = sum(
            c.get("op") == "encode" for c in getattr(self.engine.backend, "ledger", [])
        )
        dec_calls_before = sum(
            c.get("op") == "decode" or c.get("op") == "decode_mask_prompt"
            for c in getattr(self.engine.backend, "ledger", [])
        )
        if cv.gate == "direct" and cv.mask is not None:
            raw = RawMask(cv.mask, 1.0, 1.0, 0, {"cv_direct": True})
            c, reason = self._make_candidate(raw, CandidateSource.CV_DIRECT, recipe_result=cv)
            if c:
                raw_candidates.append(c)
            else:
                diagnostics.append(reason or {"reason": "invalid"})
        elif cv.gate in ("disabled", "invalid", "coarse"):
            fingerprint = _mask_fingerprint(self.crop)
            if self._encoded is None or self._encoded_fingerprint != fingerprint:
                self._record("encode_started")
                self._encoded = self.engine.backend.encode(
                    self.crop,
                    session_id=self.session_id,
                    revision=self.revision,
                    crop_fingerprint=fingerprint,
                )
                self._record("encode_finished")
                self._encoded_fingerprint = fingerprint
            prompt = PromptBundle(full_to_crop_box(self.context.user_roi_full, self.context))
            for raw in self.engine.backend.decode(self._encoded, prompt, multimask_count=3):
                c, reason = self._make_candidate(raw, CandidateSource.SAM_BOX)
                if c:
                    raw_candidates.append(c)
                    if len(raw_candidates) == 1:
                        self._record("first_candidate_ready", candidate_id=c.candidate_id)
                elif reason:
                    diagnostics.append(reason)
            if (
                cv.gate == "coarse"
                and cv.mask is not None
                and self.engine.backend.capabilities.supports_mask_prompt
            ):
                mask_state = self.engine.backend.mask_prompt_from_binary(self._encoded, cv.mask)
                if hasattr(self.engine.backend, "decode_mask_prompt"):
                    raws = self.engine.backend.decode_mask_prompt(self._encoded, prompt, mask_state)  # type: ignore[attr-defined]
                else:
                    raws = self.engine.backend.decode(
                        self._encoded,
                        PromptBundle(prompt.box_crop_xyxy, previous_mask_state=mask_state),
                        multimask_count=1,
                    )
                for raw in raws[:1]:
                    c, reason = self._make_candidate(
                        raw, CandidateSource.SAM_CV, recipe_result=cv, prompt_kind="box+mask"
                    )
                    if c:
                        raw_candidates.append(c)
                    elif reason:
                        diagnostics.append(reason)
            # Safe-grid points are selected only from >=2 valid native box masks.
            boxes = [c for c in raw_candidates if c.source == CandidateSource.SAM_BOX]
            if len(boxes) >= 2:
                stable = np.logical_and.reduce([c.mask for c in boxes])
                margin = max(
                    self.engine.candidate_policy.safe_grid_margin_min_px,
                    int(
                        np.ceil(
                            self.engine.candidate_policy.safe_grid_margin_fraction
                            * min(stable.shape)
                        )
                    ),
                )
                if stable.shape[0] > 2 * margin and stable.shape[1] > 2 * margin:
                    safe = np.zeros_like(stable)
                    safe[margin:-margin, margin:-margin] = stable[margin:-margin, margin:-margin]
                    ux0, uy0, ux1, uy1 = self.context.user_roi_full
                    grid = [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75), (0.25, 0.75), (0.75, 0.25)]
                    points: list[PromptPoint] = []
                    for gx, gy in grid:
                        x, y = (
                            int(ux0 + gx * max(0, ux1 - ux0 - 1)),
                            int(uy0 + gy * max(0, uy1 - uy0 - 1)),
                        )
                        cx, cy = (
                            x - self.context.crop_rect_full[0],
                            y - self.context.crop_rect_full[1],
                        )
                        if 0 <= cy < safe.shape[0] and 0 <= cx < safe.shape[1] and safe[cy, cx]:
                            points.append(PromptPoint(x, y, 1))
                        if len(points) >= 2:
                            break
                    if points:
                        raw_grid = self.engine.backend.decode(
                            self._encoded,
                            PromptBundle(
                                prompt.box_crop_xyxy,
                                tuple(
                                    PromptPoint(
                                        p.x - self.context.crop_rect_full[0],
                                        p.y - self.context.crop_rect_full[1],
                                        1,
                                    )
                                    for p in points
                                ),
                            ),
                            multimask_count=1,
                        )
                        for raw in raw_grid[:1]:
                            c, reason = self._make_candidate(
                                raw,
                                CandidateSource.SAM_SAFE_GRID,
                                points=points,
                                prompt_kind="box+safe_grid",
                            )
                            if c:
                                raw_candidates.append(c)
                            elif reason:
                                diagnostics.append(reason)
        deduped, removed = deduplicate_candidates(
            raw_candidates, self.engine.candidate_policy.duplicate_iou_threshold
        )
        diagnostics.extend(removed)
        selected = allocate_candidates(deduped, self.engine.candidate_policy.max_candidates)
        self._candidates = {c.candidate_id: c for c in selected}
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            tuple(selected),
            uncertainty(selected, self.context.shape, self.context),
            ProposalDiagnostics(
                tuple(diagnostics),
                sum(c.get("op") == "encode" for c in getattr(self.engine.backend, "ledger", []))
                - enc_calls_before,
                sum(
                    c.get("op") in ("decode", "decode_mask_prompt")
                    for c in getattr(self.engine.backend, "ledger", [])
                )
                - dec_calls_before,
                tuple(warnings),
            ),
            started,
            time.monotonic(),
        )
        self._record(
            "proposal_ready",
            candidate_count=len(selected),
            encoder_calls=self._proposal.diagnostics.encoder_calls,
            decoder_calls=self._proposal.diagnostics.decoder_calls,
        )
        return self._proposal

    def select(self, candidate_id: str) -> Candidate:
        c = self._candidate(candidate_id)
        if self._proposal is None or candidate_id not in {
            x.candidate_id for x in self._proposal.candidates
        }:
            raise StaleRevision(candidate_id)
        self._current_id = candidate_id
        if c.source in (
            CandidateSource.SAM_BOX,
            CandidateSource.SAM_SAFE_GRID,
            CandidateSource.SAM_CV,
        ):
            self._working_mask = np.array(c.mask, copy=True)
            self._model_mask = np.array(c.mask, copy=True)
            self._pass_base_candidate_id = c.candidate_id
            self._human_points.clear()
        self._record("candidate_selected", candidate_id=candidate_id)
        return c

    def clear_selection(self) -> None:
        if self._proposal is None or not self._proposal.candidates:
            raise UnsupportedOperation("no proposal candidates are available")
        self._current_id = None
        self._record("candidate_selection_cleared")

    def _validate_human_point(self, point: Sequence[object], label: int) -> PromptPoint:
        x, y = validate_point(point, self.context)
        if label not in (0, 1):
            raise InvalidPoint("label must be 0 or 1")
        self._point_counter += 1
        return PromptPoint(x, y, label, f"point-{self._point_counter}")

    def _compose(self, working_mask: np.ndarray) -> np.ndarray:
        value = np.asarray(working_mask, dtype=np.bool_).copy()
        x0, y0, x1, y1 = self.context.crop_rect_full
        locked_foreground = self._locked_foreground[y0:y1, x0:x1]
        locked_background = self._locked_background[y0:y1, x0:x1]
        value[locked_foreground] = True
        value[locked_background] = False
        return value

    @staticmethod
    def _raw_with_mask(raw: RawMask, mask: np.ndarray) -> RawMask:
        return RawMask(mask, raw.quality, raw.stability, raw.native_index, raw.mask_state)

    def refine(self, candidate_id: str, point: Sequence[object], label: int = 1) -> Candidate:
        c = self._candidate(candidate_id)
        if not c.can_refine or c.source not in (
            CandidateSource.SAM_BOX,
            CandidateSource.SAM_SAFE_GRID,
            CandidateSource.SAM_CV,
        ):
            raise UnsupportedOperation("candidate cannot refine")
        if self._encoded is None:
            raise StaleRevision("encoded state unavailable")
        if not self._human_points:
            self._pass_base_candidate_id = c.candidate_id
        p = self._validate_human_point(point, label)
        self._record("refine_started", candidate_id=candidate_id, label=label)
        self._human_points.append(p)
        prompt_points = tuple(
            PromptPoint(
                q.x - self.context.crop_rect_full[0],
                q.y - self.context.crop_rect_full[1],
                q.label,
                q.point_id,
            )
            for q in self._human_points
        )
        prompt = PromptBundle(
            full_to_crop_box(self.context.user_roi_full, self.context), prompt_points, c._mask_state
        )
        try:
            raws = self.engine.backend.decode(self._encoded, prompt, multimask_count=1)
        except Exception:
            self._human_points.pop()
            raise
        if not raws:
            self._human_points.pop()
            raise UnsupportedOperation("backend returned no refinement mask")
        raw = raws[0]
        new, reason = self._make_candidate(
            self._raw_with_mask(raw, self._compose(raw.mask)),
            c.source,
            parent=c,
            prompt_kind="box+human_points",
            points=self._human_points,
        )
        if new is None:
            self._human_points.pop()
            reason_code = str((reason or {}).get("reason", "REFINEMENT_REJECTED"))
            raise AcceptValidationError(f"refinement rejected: {reason_code}")
        self._snapshot(points=list(self._human_points[:-1]))
        self._working_mask = np.array(raw.mask, copy=True)
        self._model_mask = np.array(raw.mask, copy=True)
        self._candidates[new.candidate_id] = new
        self._current_id = new.candidate_id
        # Human input invalidates auto grid/fusion presentation by replacing proposal.
        shown = tuple(x for x in self._candidates.values() if x.revision == self.revision)[-3:]
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            shown,
            uncertainty(shown, self.context.shape, self.context),
            self._proposal.diagnostics if self._proposal else ProposalDiagnostics(),
        )
        self._record("human_point_added", candidate_id=new.candidate_id, label=label)
        self._record("refine_finished", candidate_id=new.candidate_id)
        return new

    def _capture_checkpoint(self, *, points: list[PromptPoint] | None = None) -> dict[str, Any]:
        return {
                "revision": self.revision,
                "candidates": dict(self._candidates),
                "current_id": self._current_id,
                "human_points": list(self._human_points if points is None else points),
                "operations": list(self._operations),
                "manual_mode": self._manual_mode,
                "pass_index": self._pass_index,
                "pass_base_candidate_id": self._pass_base_candidate_id,
                "frozen_regions": dict(self._frozen_regions),
                "frozen_region_full_masks": {
                    key: value.copy() for key, value in self._frozen_region_full_masks.items()
                },
                "locked_foreground": self._locked_foreground.copy(),
                "locked_background": self._locked_background.copy(),
                "working_mask": None if self._working_mask is None else self._working_mask.copy(),
                "model_mask": None if self._model_mask is None else self._model_mask.copy(),
                "encoded": self._encoded,
                "encoded_fingerprint": self._encoded_fingerprint,
            }

    def _snapshot(self, *, points: list[PromptPoint] | None = None) -> None:
        self._undo.append(self._capture_checkpoint(points=points))
        if len(self._undo) > HISTORY_MAX_DEPTH:
            del self._undo[: len(self._undo) - HISTORY_MAX_DEPTH]
        # A completed mutation after Undo starts a new branch.  Callers invoke
        # _snapshot only once the mutation has passed backend validation.
        self._redo.clear()

    def _restore_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        self.revision = checkpoint["revision"]
        self._candidates = checkpoint["candidates"]
        self._current_id = checkpoint["current_id"]
        self._human_points = checkpoint["human_points"]
        self._operations = checkpoint["operations"]
        self._manual_mode = checkpoint["manual_mode"]
        self._pass_index = checkpoint["pass_index"]
        self._pass_base_candidate_id = checkpoint["pass_base_candidate_id"]
        self._frozen_regions = checkpoint["frozen_regions"]
        self._frozen_region_full_masks = checkpoint["frozen_region_full_masks"]
        self._locked_foreground = checkpoint["locked_foreground"]
        self._locked_background = checkpoint["locked_background"]
        self._working_mask = checkpoint["working_mask"]
        self._model_mask = checkpoint["model_mask"]
        self._encoded = checkpoint["encoded"]
        self._encoded_fingerprint = checkpoint["encoded_fingerprint"]
        shown = tuple(self._candidates.values())
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            shown,
            uncertainty(shown, self.context.shape, self.context),
            self._proposal.diagnostics if self._proposal else ProposalDiagnostics(),
        )

    def edit(
        self,
        operation: str,
        *,
        points: Sequence[tuple[int, int]] = (),
        radius: int = 0,
        clip_rect: Sequence[object] | None = None,
    ) -> Candidate:
        if operation not in {
            "brush",
            "erase",
            "grow",
            "shrink",
            "fill",
            "fill_holes",
            "merge",
        }:
            raise UnsupportedOperation(f"unknown local edit: {operation}")
        if operation == "merge" and not any(region.label == 1 for region in self._frozen_regions.values()):
            raise UnsupportedOperation("merge requires at least one locked foreground region")
        current = self.selected_candidate
        if current is None:
            if operation != "brush":
                raise UnsupportedOperation("select a candidate before editing")
            mask = np.zeros(self.context.shape, dtype=np.bool_)
            parent = None
        else:
            if not current.can_local_edit:
                raise UnsupportedOperation("candidate cannot be locally edited")
            mask = self._working_mask if self._working_mask is not None else current.mask
            parent = current
        self._snapshot()
        edit_clip = validate_roi(clip_rect, self.context.shape) if clip_rect is not None else None
        x0, y0, x1, y1 = self.context.crop_rect_full
        if operation == "merge":
            # Flatten all protected foreground decisions into the active
            # editable layer.  Keep locked background as a separate guard so
            # later brush strokes cannot paint over explicit exclusions.
            foreground = self._locked_foreground[y0:y1, x0:x1]
            newmask = np.logical_or(mask, foreground)
            merged_region_ids = [
                region.region_id for region in self._frozen_regions.values() if region.label == 1
            ]
            for region_id in merged_region_ids:
                self._frozen_regions.pop(region_id, None)
                self._frozen_region_full_masks.pop(region_id, None)
            self._rebuild_locks()
        elif operation == "brush":
            newmask = brush(mask, list(points), radius, True, edit_clip)
        elif operation == "erase":
            newmask = erase(mask, list(points), radius, edit_clip)
        elif operation == "grow":
            newmask = grow(mask)
        elif operation == "shrink":
            newmask = shrink(mask)
        elif operation in ("fill", "fill_holes"):
            newmask = fill_holes(mask)
        self._working_mask = np.array(newmask, copy=True)
        composed = self._compose(newmask)
        raw = RawMask(composed, 1.0, 1.0, 0, None)
        c, _reason = self._make_candidate(
            raw,
            CandidateSource.MANUAL_EDIT if newmask.any() else CandidateSource.MANUAL_EMPTY,
            parent=parent,
            prompt_kind=f"local:{operation}",
        )
        if c is None:
            # Empty masks intentionally use manual_empty, which is not committable.
            c = Candidate(
                f"{self.session_id[:8]}-r{self.revision}-manual-empty-{self._candidate_counter + 1}",
                self.session_id,
                self.revision,
                # Keep the fallback candidate subject to the same locked
                # background/foreground composition as the normal path.
                composed,
                Provenance(
                    GeneratorKind.MANUAL,
                    CandidateSource.MANUAL_EMPTY,
                    parent_candidate_id=parent.candidate_id if parent else None,
                    prompt_kind=f"local:{operation}",
                ),
                False,
                True,
                False,
            )
            self._candidate_counter += 1
        self._history[c.candidate_id] = c
        self._manual_mode = True
        if not self._operations:
            self._record("first_local_edit", operation=operation)
        self._operations.append(
            {
                "sequence": len(self._operations) + 1,
                "kind": "merge_regions" if operation == "merge" else ("fill_holes" if operation == "fill" else operation),
                "parameters": {
                    "points": [list(p) for p in points],
                    "radius": radius,
                    **({"clip_rect": list(edit_clip)} if edit_clip is not None else {}),
                    **(
                        {"region_ids": merged_region_ids}
                        if operation == "merge"
                        else {}
                    ),
                },
            }
        )
        self._candidates = {c.candidate_id: c}
        self._current_id = c.candidate_id
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            (c,),
            uncertainty((c,), self.context.shape, self.context),
            self._proposal.diagnostics if self._proposal else ProposalDiagnostics(),
        )
        if operation == "merge":
            self._record(
                "regions_merged",
                candidate_id=c.candidate_id,
                region_ids=merged_region_ids,
            )
        return c

    def _publish_composite(self, parent: Candidate, *, prompt_kind: str) -> Candidate:
        working = self._working_mask if self._working_mask is not None else parent.mask
        mask = self._compose(working)
        provenance = Provenance(
            parent.provenance.generator_kind,
            parent.source,
            model=parent.provenance.model,
            recipe_id=parent.provenance.recipe_id,
            recipe_hash=parent.provenance.recipe_hash,
            parent_candidate_id=parent.candidate_id,
            prompt_kind=prompt_kind,
        )
        self._candidate_counter += 1
        candidate = Candidate(
            f"{self.session_id[:8]}-r{self.revision}-{parent.source.value}-0-{self._candidate_counter}",
            self.session_id,
            self.revision,
            mask,
            provenance,
            parent.can_refine,
            parent.can_local_edit,
            bool(mask.any()) and parent.can_commit,
            parent.quality,
            parent.stability,
            parent.native_index,
            parent.warnings,
            tuple(self._human_points),
            parent._mask_state,
        )
        self._history[candidate.candidate_id] = candidate
        self._candidates = {candidate.candidate_id: candidate}
        self._current_id = candidate.candidate_id
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            (candidate,),
            uncertainty((candidate,), self.context.shape, self.context),
            self._proposal.diagnostics if self._proposal else ProposalDiagnostics(),
        )
        return candidate

    def _rebuild_locks(self) -> None:
        foreground = np.zeros((self.image_height, self.image_width), dtype=np.bool_)
        background = np.zeros((self.image_height, self.image_width), dtype=np.bool_)
        for region in self._frozen_regions.values():
            full = self._frozen_region_full_masks.get(region.region_id)
            if full is None:
                x0, y0, x1, y1 = self.context.crop_rect_full
                full = np.zeros_like(foreground)
                full[y0:y1, x0:x1] = region.mask
                self._frozen_region_full_masks[region.region_id] = full
            (foreground if region.label else background).__ior__(full)
        if np.logical_and(foreground, background).any():
            raise UnsupportedOperation("foreground and background locks overlap")
        self._locked_foreground = foreground
        self._locked_background = background

    def lock_region(
        self,
        mask: np.ndarray,
        label: int,
        *,
        source_candidate_id: str | None = None,
    ) -> FrozenRegion:
        current = self.selected_candidate
        if current is None:
            raise UnsupportedOperation("select a candidate before locking a region")
        value = np.asarray(mask)
        if value.dtype != np.bool_ or value.shape != self.context.shape or not value.any():
            raise InvalidPoint("frozen region must be a non-empty crop-resolution bool mask")
        if label not in (0, 1) or isinstance(label, bool):
            raise InvalidPoint("frozen region label must be 0 or 1")
        opposite = self._locked_background if label else self._locked_foreground
        full_value = np.zeros((self.image_height, self.image_width), dtype=np.bool_)
        x0, y0, x1, y1 = self.context.crop_rect_full
        full_value[y0:y1, x0:x1] = value
        if np.logical_and(full_value, opposite).any():
            raise UnsupportedOperation("frozen region conflicts with an opposite lock")
        source_id = source_candidate_id or current.candidate_id
        if source_id not in self._history:
            raise CandidateNotFound(source_id)
        self._snapshot()
        self._region_counter += 1
        region = FrozenRegion(
            f"region-{self._region_counter}", label, value, source_id, self._pass_index
        )
        self._frozen_regions[region.region_id] = region
        self._frozen_region_full_masks[region.region_id] = full_value
        self._rebuild_locks()
        self._operations.append(
            {
                "sequence": len(self._operations) + 1,
                "kind": "lock_region",
                "parameters": region.to_dict(),
            }
        )
        self._publish_composite(current, prompt_kind="region_lock")
        self._record(
            "region_locked",
            candidate_id=self._current_id,
            region_id=region.region_id,
            label=label,
            mask_sha256=region.to_dict()["mask_sha256"],
        )
        return region

    def lock_component(self, point: Sequence[object], label: int = 1) -> FrozenRegion:
        current = self.selected_candidate
        if current is None:
            raise UnsupportedOperation("select a candidate before locking a component")
        x, y = validate_point(point, self.context)
        cx = x - self.context.crop_rect_full[0]
        cy = y - self.context.crop_rect_full[1]
        source = current.mask if label == 1 else ~current.mask
        try:
            component = connected_component(source, (cx, cy))
        except Exception as exc:
            raise InvalidPoint("point is not inside the requested component") from exc
        return self.lock_region(component, label)

    def unlock_region(self, region_id: str) -> Candidate | None:
        if region_id not in self._frozen_regions:
            raise CandidateNotFound(region_id)
        current = self.selected_candidate
        if current is None:
            raise UnsupportedOperation("no current candidate")
        self._snapshot()
        self._frozen_regions.pop(region_id)
        self._frozen_region_full_masks.pop(region_id, None)
        self._rebuild_locks()
        self._operations.append(
            {
                "sequence": len(self._operations) + 1,
                "kind": "unlock_region",
                "parameters": {"region_id": region_id},
            }
        )
        candidate = self._publish_composite(current, prompt_kind="region_unlock")
        self._record("region_unlocked", candidate_id=candidate.candidate_id, region_id=region_id)
        return candidate

    def _latest_model_candidate(self) -> Candidate | None:
        current = self.selected_candidate
        seen: set[str] = set()
        while current is not None and current.candidate_id not in seen:
            seen.add(current.candidate_id)
            if current.source in (
                CandidateSource.SAM_BOX,
                CandidateSource.SAM_SAFE_GRID,
                CandidateSource.SAM_CV,
            ):
                return current
            parent_id = current.provenance.parent_candidate_id
            current = self._history.get(parent_id) if parent_id else None
        return None

    def next_region(self) -> None:
        model = self._latest_model_candidate()
        if model is None or self._encoded is None:
            raise UnsupportedOperation("no SAM checkpoint is available for another region")
        self._snapshot()
        self._pass_index += 1
        # A new pass is a new revision boundary. Keep the encoded checkpoint
        # alive until the next ROI is locked so Undo can restore the prior pass;
        # update_roi() releases it before the next encode.
        self.revision += 1
        self._human_points.clear()
        self._pass_base_candidate_id = None
        self._manual_mode = False
        self._working_mask = None
        self._model_mask = None
        self._candidates.clear()
        self._current_id = None
        self._proposal = None
        self._operations.append(
            {
                "sequence": len(self._operations) + 1,
                "kind": "next_region",
                "parameters": {"pass_index": self._pass_index},
            }
        )
        self._record(
            "region_pass_started", candidate_id=None, pass_index=self._pass_index
        )

    def delete_prompt(self, point_id: str) -> Candidate:
        if not isinstance(point_id, str) or not point_id:
            raise InvalidPoint("point_id is required")
        current = self.selected_candidate
        if current is None or not current.can_refine or self._encoded is None:
            raise UnsupportedOperation("prompt deletion requires an active SAM candidate")
        if not any(point.point_id == point_id for point in self._human_points):
            raise InvalidPoint("prompt point was not found in the active pass")
        base = self._history.get(self._pass_base_candidate_id or "")
        if base is None or base._mask_state is None:
            raise StaleRevision("prompt replay baseline is unavailable")
        remaining = [point for point in self._human_points if point.point_id != point_id]
        crop_points = tuple(
            PromptPoint(
                point.x - self.context.crop_rect_full[0],
                point.y - self.context.crop_rect_full[1],
                point.label,
                point.point_id,
            )
            for point in remaining
        )
        prompt = PromptBundle(
            full_to_crop_box(self.context.user_roi_full, self.context),
            crop_points,
            base._mask_state,
        )
        raws = self.engine.backend.decode(self._encoded, prompt, multimask_count=1)
        if not raws:
            raise UnsupportedOperation("backend returned no prompt replay mask")
        raw = raws[0]
        new, reason = self._make_candidate(
            self._raw_with_mask(raw, self._compose(raw.mask)),
            base.source,
            parent=current,
            prompt_kind="box+human_points:prompt_removed",
            points=remaining,
        )
        if new is None:
            reason_code = str((reason or {}).get("reason", "REFINEMENT_REJECTED"))
            raise AcceptValidationError(f"prompt replay rejected: {reason_code}")
        self._snapshot()
        self._human_points = remaining
        self._working_mask = np.array(raw.mask, copy=True)
        self._model_mask = np.array(raw.mask, copy=True)
        self._candidates = {new.candidate_id: new}
        self._current_id = new.candidate_id
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            (new,),
            uncertainty((new,), self.context.shape, self.context),
            self._proposal.diagnostics if self._proposal else ProposalDiagnostics(),
        )
        self._operations.append(
            {
                "sequence": len(self._operations) + 1,
                "kind": "prompt_removed",
                "parameters": {"point_id": point_id, "pass_index": self._pass_index},
            }
        )
        self._record("prompt_removed", candidate_id=new.candidate_id, point_id=point_id)
        return new

    def update_prompt(
        self, point_id: str, point: Sequence[object] | None = None, label: int | None = None
    ) -> Candidate:
        """Move or relabel one prompt using decoder-only deterministic replay."""
        if not isinstance(point_id, str) or not point_id:
            raise InvalidPoint("point_id is required")
        current = self.selected_candidate
        if current is None or not current.can_refine or self._encoded is None:
            raise UnsupportedOperation("prompt update requires an active SAM candidate")
        base = self._history.get(self._pass_base_candidate_id or "")
        if base is None or base._mask_state is None:
            raise StaleRevision("prompt replay baseline is unavailable")
        if point is None and label is None:
            raise InvalidPoint("point or label is required")
        found = False
        updated: list[PromptPoint] = []
        for existing in self._human_points:
            if existing.point_id != point_id:
                updated.append(existing)
                continue
            found = True
            x, y = (existing.x, existing.y) if point is None else validate_point(point, self.context)
            next_label = existing.label if label is None else int(label)
            if next_label not in (0, 1):
                raise InvalidPoint("label must be 0 or 1")
            updated.append(PromptPoint(x, y, next_label, existing.point_id))
        if not found:
            raise InvalidPoint("prompt point was not found in the active pass")
        crop_points = tuple(
            PromptPoint(
                p.x - self.context.crop_rect_full[0],
                p.y - self.context.crop_rect_full[1],
                p.label,
                p.point_id,
            )
            for p in updated
        )
        prompt = PromptBundle(
            full_to_crop_box(self.context.user_roi_full, self.context),
            crop_points,
            base._mask_state,
        )
        prior = self._capture_checkpoint()
        try:
            raws = self.engine.backend.decode(self._encoded, prompt, multimask_count=1)
            if not raws:
                raise UnsupportedOperation("backend returned no prompt replay mask")
            raw = raws[0]
            new, reason = self._make_candidate(
                self._raw_with_mask(raw, self._compose(raw.mask)),
                base.source,
                parent=current,
                prompt_kind="box+human_points:prompt_updated",
                points=updated,
            )
            if new is None:
                reason_code = str((reason or {}).get("reason", "REFINEMENT_REJECTED"))
                raise AcceptValidationError(f"prompt replay rejected: {reason_code}")
        except Exception:
            self._restore_checkpoint(prior)
            raise
        self._snapshot()
        self._human_points = updated
        self._working_mask = np.array(raw.mask, copy=True)
        self._model_mask = np.array(raw.mask, copy=True)
        self._candidates = {new.candidate_id: new}
        self._current_id = new.candidate_id
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            (new,),
            uncertainty((new,), self.context.shape, self.context),
            self._proposal.diagnostics if self._proposal else ProposalDiagnostics(),
        )
        self._operations.append(
            {
                "sequence": len(self._operations) + 1,
                "kind": "prompt_updated",
                "parameters": {
                    "point_id": point_id,
                    "x": updated[[p.point_id for p in updated].index(point_id)].x,
                    "y": updated[[p.point_id for p in updated].index(point_id)].y,
                    "label": updated[[p.point_id for p in updated].index(point_id)].label,
                    "pass_index": self._pass_index,
                },
            }
        )
        self._record("prompt_updated", candidate_id=new.candidate_id, point_id=point_id)
        return new

    def undo(self) -> Candidate | None:
        if not self._undo:
            return self.selected_candidate
        self._redo.append(self._capture_checkpoint())
        checkpoint = self._undo.pop()
        self._restore_checkpoint(checkpoint)
        self._record("undo", candidate_id=self._current_id)
        return self.selected_candidate

    def redo(self) -> Candidate | None:
        if not self._redo:
            return self.selected_candidate
        self._undo.append(self._capture_checkpoint())
        checkpoint = self._redo.pop()
        self._restore_checkpoint(checkpoint)
        self._record("redo", candidate_id=self._current_id)
        return self.selected_candidate

    def begin_manual(self) -> Candidate:
        return self.begin_manual_empty()

    def begin_manual_empty(self) -> Candidate:
        """Create an all-background manual candidate without backend work."""
        self._ensure_open()
        mask = np.zeros(self.context.shape, dtype=np.bool_)
        self._snapshot()
        candidate = Candidate(
            f"{self.session_id[:8]}-r{self.revision}-manual-empty-{self._candidate_counter + 1}",
            self.session_id,
            self.revision,
            mask,
            Provenance(
                GeneratorKind.MANUAL, CandidateSource.MANUAL_EMPTY, prompt_kind="manual_empty"
            ),
            False,
            True,
            False,
        )
        self._candidate_counter += 1
        self._history[candidate.candidate_id] = candidate
        self._manual_mode = True
        self._working_mask = mask.copy()
        self._model_mask = None
        self._candidates = {candidate.candidate_id: candidate}
        self._current_id = candidate.candidate_id
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            (candidate,),
            uncertainty((candidate,), self.context.shape, self.context),
            self._proposal.diagnostics if self._proposal else ProposalDiagnostics(),
        )
        self._record("manual_empty_started")
        return candidate

    def import_mask(self, full_mask: np.ndarray) -> Candidate:
        """Install a validated full-image mask as the current editable draft.

        LabelMe/import adapters operate in source-image coordinates while the
        core keeps the active mask in the current crop.  The conversion is
        deliberately performed here so imported pixels follow the same lock,
        undo/redo, capability, and provenance rules as brush edits.
        """
        self._ensure_open()
        array = np.asarray(full_mask, dtype=np.bool_)
        if array.shape != (self.image_height, self.image_width):
            raise InvalidImage("imported mask dimensions do not match the source image")
        x0, y0, x1, y1 = self.context.crop_rect_full
        crop_mask = np.array(array[y0:y1, x0:x1], copy=True)
        current = self.selected_candidate
        self._snapshot()
        composed = self._compose(crop_mask)
        source = CandidateSource.MANUAL_EDIT if bool(composed.any()) else CandidateSource.MANUAL_EMPTY
        candidate, _reason = self._make_candidate(
            RawMask(composed, 1.0, 1.0, 0, {"labelme_import": True}),
            source,
            parent=current,
            prompt_kind="labelme_import",
        )
        if candidate is None:
            # Imports are allowed to touch image/crop boundaries; QA reports
            # those advisory conditions after the pixels are installed.
            candidate = Candidate(
                f"{self.session_id[:8]}-r{self.revision}-import-{self._candidate_counter + 1}",
                self.session_id,
                self.revision,
                composed,
                Provenance(
                    GeneratorKind.MANUAL,
                    source,
                    parent_candidate_id=current.candidate_id if current else None,
                    prompt_kind="labelme_import",
                ),
                False,
                True,
                source != CandidateSource.MANUAL_EMPTY,
            )
            self._candidate_counter += 1
            self._history[candidate.candidate_id] = candidate
        self._working_mask = crop_mask
        self._model_mask = None
        self._manual_mode = True
        self._human_points.clear()
        self._candidates = {candidate.candidate_id: candidate}
        self._current_id = candidate.candidate_id
        self._proposal = ProposalSet(
            self.session_id,
            self.revision,
            (candidate,),
            uncertainty((candidate,), self.context.shape, self.context),
            ProposalDiagnostics(),
        )
        self._record(
            "labelme_import",
            candidate_id=candidate.candidate_id,
            mask_area=int(crop_mask.sum()),
        )
        return candidate

    def update_roi(self, roi: Sequence[object]) -> CropContext:
        new_context = create_crop_context((self.image_height, self.image_width), roi)
        if new_context == self.context:
            return self.context
        if self._encoded is not None:
            self.engine.backend.release(self._encoded)
        self.context = new_context
        self.revision += 1
        self._encoded = None
        self._encoded_fingerprint = None
        self._candidates.clear()
        self._proposal = None
        self._current_id = None
        self._human_points.clear()
        self._undo.clear()
        self._manual_mode = False
        self._pass_base_candidate_id = None
        # Frozen regions are authoritative in full-image coordinates and must
        # survive a new ROI.  Their crop-sized metadata masks intentionally
        # remain tied to the originating pass; composition uses the full masks.
        self._rebuild_locks()
        self._working_mask = None
        self._model_mask = None
        self._record("roi_relocked")
        return self.context

    def expand_roi(self) -> CropContext:
        new_context = expanded_context(self.context)
        return self.update_roi(new_context.user_roi_full)

    def accept(
        self,
        *,
        acknowledge_warnings: Iterable[str] = (),
        human: bool = True,
        acceptance_actor: str = "interactive_user",
    ) -> CommitResult:
        if not human:
            raise AcceptValidationError("scripted acceptance cannot prove human acceptance")
        c = self.selected_candidate
        self._record("accept_attempted", candidate_id=c.candidate_id if c else None)
        if c is None or not c.can_commit:
            self._record("accept_validation_failed", reason="NO_COMMITTABLE_CANDIDATE")
            raise AcceptValidationError("no committable candidate")
        # Human points are hard constraints at the final commit boundary too;
        # local edits cannot silently erase the evidence supplied during
        # refinement.
        if self._human_points:
            for point in self._human_points:
                cx = point.x - self.context.crop_rect_full[0]
                cy = point.y - self.context.crop_rect_full[1]
                if not (0 <= cy < c.mask.shape[0] and 0 <= cx < c.mask.shape[1]):
                    raise AcceptValidationError("human point is outside the current work crop")
                if bool(c.mask[cy, cx]) != bool(point.label):
                    raise AcceptValidationError("committed mask violates a human point constraint")
        ack = tuple(acknowledge_warnings)
        required = {w.code for w in c.warnings}
        if required - set(ack):
            self._record(
                "accept_validation_failed",
                reason="WARNINGS_NOT_ACKNOWLEDGED",
                warning_codes=sorted(required - set(ack)),
            )
            raise AcceptValidationError("crop-edge warning requires explicit acknowledgement")
        self._record("commit_started", candidate_id=c.candidate_id)
        full = reconstruct_full_mask(c.mask, self.context)
        # The active candidate is crop-sized; merge any locked regions that
        # originated in earlier passes/ROIs in source-image coordinates.
        full[self._locked_foreground] = True
        full[self._locked_background] = False
        warnings = list(c.warnings)
        boundary = image_boundary_warning(full, self.context)
        if boundary:
            warnings.append(boundary)
        elapsed_ms = (time.monotonic() - self._first_roi_locked_at) * 1000.0
        provenance = {
            "candidate": c.to_dict(),
            "geometry": self.context.to_dict(),
            "policy_id": self.policy.policy_id,
            "source_sha256": self._source_sha256,
            "operations": list(self._operations),
            "prompt_points": [point.to_dict(include_id=True) for point in self._human_points],
            "pass_index": self._pass_index,
            "frozen_regions": [region.to_dict() for region in self._frozen_regions.values()],
            "first_roi_locked_ns": int(self._first_roi_locked_at * 1_000_000_000),
            "first_valid_accept_time_ms": elapsed_ms,
            "annotation_time_ms": elapsed_ms,
            "decision_time_ms": elapsed_ms,
            "within_30_accept": elapsed_ms < 30_000,
        }
        ancestry: list[dict[str, Any]] = []
        cursor: Candidate | None = c
        seen: set[str] = set()
        while cursor is not None and cursor.candidate_id not in seen:
            seen.add(cursor.candidate_id)
            ancestry.append(
                {
                    "candidate_id": cursor.candidate_id,
                    "source": cursor.source.value,
                    "parent_candidate_id": cursor.provenance.parent_candidate_id,
                    "provenance": cursor.provenance.to_dict(),
                    "prompt_points": [p.to_dict() for p in cursor.prompt_points],
                }
            )
            parent_id = cursor.provenance.parent_candidate_id
            cursor = self._history.get(parent_id) if parent_id else None
        provenance["ancestry"] = ancestry
        if acceptance_actor not in {"interactive_user", "scripted_test"}:
            raise AcceptValidationError("invalid acceptance actor")
        provenance["acceptance_actor"] = acceptance_actor
        result = CommitResult(
            OutcomeKind.ACCEPTED,
            self.session_id,
            self.revision,
            self.image_id,
            self.class_id,
            full,
            c.candidate_id,
            self.policy.policy_id,
            tuple(warnings),
            ack,
            provenance,
            True,
            acceptance_actor,
        )
        self._accepted = True
        self._record("accept_validation_passed", candidate_id=c.candidate_id)
        self._record("commit_finished", candidate_id=c.candidate_id)
        return result

    def commit(
        self,
        candidate_id: str | None = None,
        acceptance: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> CommitResult:
        """Compatibility spelling for the explicit public commit contract."""
        acceptance = dict(acceptance or {})
        if kwargs:
            acceptance.update(kwargs)
        explicit = acceptance.get("explicit_confirmation", True)
        actor = acceptance.get("acceptance_actor", "interactive_user")
        if not explicit:
            raise AcceptValidationError("explicit_confirmation is required")
        if candidate_id is not None:
            self.select(candidate_id)
        if actor not in {"interactive_user", "scripted_test"}:
            raise AcceptValidationError("invalid acceptance_actor")
        return self.accept(
            acknowledge_warnings=acceptance.get(
                "acknowledged_warning_codes", acceptance.get("acknowledge_warnings", ())
            ),
            human=True,
            acceptance_actor=actor,
        )

    def needs_review(self, reason: str, *, include_draft: bool = True) -> ReviewResult:
        if not reason or not reason.strip():
            raise AcceptValidationError("review reason is required")
        c = self.selected_candidate
        draft = c.mask if (include_draft and c is not None and c.mask.any()) else None
        result = ReviewResult(
            self.session_id,
            self.revision,
            self.image_id,
            self.class_id,
            self.policy.policy_id,
            reason,
            draft,
            {
                "geometry": self.context.to_dict(),
                "candidate_id": c.candidate_id if c else None,
                "source_sha256": self._source_sha256,
                "decision_time_ms": (time.monotonic() - self._first_roi_locked_at) * 1000.0,
            },
        )
        self._record("needs_review_requested", reason=reason)
        return result

    def mark_needs_review(self, reason: str, *, include_draft: bool = True) -> ReviewResult:
        return self.needs_review(reason, include_draft=include_draft)

    def close(self) -> None:
        if self._closed:
            return
        self._record("job_cancel_requested")
        if self._encoded is not None:
            self.engine.backend.release(self._encoded)
        self._encoded = None
        self._closed = True
        self._record("session_closed")
