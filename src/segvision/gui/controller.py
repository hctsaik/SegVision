"""Thin, toolkit-neutral desktop workflow controller.

PySide6 (or another view toolkit) can bind widgets to this controller.  The
controller contains no tensors, file writes, or rendering-specific state and
is therefore fully usable in headless E2E tests.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from segvision.adapters.png_sidecar import AcceptedStore, PersistedPair, ReviewStore
from segvision.core.api import AnnotationSession
from segvision.core.errors import SegVisionError
from segvision.core.types import Candidate, CommitResult, ReviewResult


class WorkflowState(StrEnum):
    IMAGE_OPEN = "IMAGE_OPEN"
    ROI_LOCKED = "ROI_LOCKED"
    PROPOSING = "PROPOSING"
    PROPOSAL_READY = "PROPOSAL_READY"
    MANUAL_EMPTY = "MANUAL_EMPTY"
    REFINE_PENDING = "REFINE_PENDING"
    REFINED_READY = "REFINED_READY"
    LOCAL_EDITING = "LOCAL_EDITING"
    VALIDATING = "VALIDATING"
    COMMITTING = "COMMITTING"
    SAVING = "SAVING"
    SAVE_FAILED = "SAVE_FAILED"
    REVIEW_SAVING = "REVIEW_SAVING"
    REVIEW_SAVE_FAILED = "REVIEW_SAVE_FAILED"
    ACCEPTED = "ACCEPTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class InvalidTransition(SegVisionError):
    pass


class AnnotationController:
    def __init__(
        self,
        session: AnnotationSession,
        *,
        accepted_store: AcceptedStore | None = None,
        review_store: ReviewStore | None = None,
        actor: str = "interactive_user",
    ) -> None:
        self.session = session
        self.state = WorkflowState.IMAGE_OPEN
        self.accepted_store = accepted_store
        self.review_store = review_store
        self.actor = actor
        self.last_result: Any = None
        self.last_error: str | None = None
        self._accept_pending: CommitResult | None = None
        self._review_pending: ReviewResult | None = None
        self._brush_mode = False

    @property
    def next_enabled(self) -> bool:
        return self.state in (WorkflowState.ACCEPTED, WorkflowState.NEEDS_REVIEW)

    @property
    def elapsed_ms(self) -> float:
        return max(0.0, (time.monotonic() - self.session.first_roi_locked_at) * 1000.0)

    @property
    def visible_candidates(self) -> tuple[Candidate, ...]:
        return self.session.candidates

    @property
    def controls(self) -> dict[str, bool]:
        c = self.session.selected_candidate
        editable = self.state in {
            WorkflowState.PROPOSAL_READY,
            WorkflowState.REFINED_READY,
            WorkflowState.LOCAL_EDITING,
        }
        frozen_regions = getattr(self.session, "frozen_regions", ())
        foreground_regions = tuple(region for region in frozen_regions if region.label == 1)
        prompt_points = getattr(self.session, "prompt_points", ())
        return {
            "roi": self.state not in (WorkflowState.ACCEPTED, WorkflowState.NEEDS_REVIEW),
            "refine": bool(c and c.can_refine),
            "local_edit": bool(c and c.can_local_edit) or self.state == WorkflowState.MANUAL_EMPTY,
            "accept": bool(c and c.can_commit),
            "needs_review": self.state
            in {
                WorkflowState.ROI_LOCKED,
                WorkflowState.PROPOSING,
                WorkflowState.PROPOSAL_READY,
                WorkflowState.MANUAL_EMPTY,
                WorkflowState.REFINE_PENDING,
                WorkflowState.REFINED_READY,
                WorkflowState.LOCAL_EDITING,
                WorkflowState.SAVE_FAILED,
            },
            "next": self.next_enabled,
            "fusion": False,
            "lock_region": bool(c and editable),
            "unlock_region": bool(frozen_regions and editable),
            "next_region": bool(frozen_regions and editable),
            # Flatten protected foreground regions into the active manual
            # layer.  Background locks deliberately stay separate and are
            # preserved by the core merge operation.
            "merge_regions": bool(foreground_regions and c and editable),
            "delete_prompt": bool(prompt_points and c and c.can_refine and editable),
        }

    def lock_roi(self) -> None:
        if self.state != WorkflowState.IMAGE_OPEN:
            raise InvalidTransition(f"cannot lock ROI from {self.state}")
        self.session._record("roi_drag_started")
        self.state = WorkflowState.ROI_LOCKED
        self.session._record("roi_locked")  # controller-owned workflow event
        self.state = WorkflowState.PROPOSING
        try:
            proposal = self.session.propose()
            self.state = (
                WorkflowState.PROPOSAL_READY if proposal.candidates else WorkflowState.MANUAL_EMPTY
            )
            if proposal.candidates:
                self.session.select(proposal.candidates[0].candidate_id)
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self.state = WorkflowState.MANUAL_EMPTY

    def redraw_roi(self, roi: Sequence[object]) -> None:
        if self.state in (WorkflowState.ACCEPTED, WorkflowState.NEEDS_REVIEW):
            raise InvalidTransition("terminal workflow")
        self.session._record("roi_drag_started")
        self.session.update_roi(roi)
        self.session._record("roi_redrawn")
        self.state = WorkflowState.ROI_LOCKED
        self.state = WorkflowState.PROPOSING
        try:
            p = self.session.propose()
            self.state = (
                WorkflowState.PROPOSAL_READY if p.candidates else WorkflowState.MANUAL_EMPTY
            )
            if p.candidates:
                self.session.select(p.candidates[0].candidate_id)
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self.state = WorkflowState.MANUAL_EMPTY

    def select(self, card: int) -> Candidate | None:
        if self.state not in (
            WorkflowState.PROPOSAL_READY,
            WorkflowState.REFINED_READY,
            WorkflowState.LOCAL_EDITING,
        ):
            return None
        candidates = self.session.candidates
        if card < 1 or card > len(candidates):
            return None
        return self.session.select(candidates[card - 1].candidate_id)

    def clear_selection(self) -> None:
        if self.state not in (WorkflowState.PROPOSAL_READY, WorkflowState.REFINED_READY):
            raise InvalidTransition("candidate selection cannot be cleared in this state")
        self.session.clear_selection()

    def point(self, x: int, y: int, label: int = 1) -> Candidate:
        if self.state not in (WorkflowState.PROPOSAL_READY, WorkflowState.REFINED_READY):
            raise InvalidTransition("point input is not available")
        self.state = WorkflowState.REFINE_PENDING
        try:
            c = self.session.refine(self.session.selected_candidate.candidate_id, (x, y), label)  # type: ignore[union-attr]
            self.state = WorkflowState.REFINED_READY
            return c
        except Exception:
            self.state = WorkflowState.PROPOSAL_READY
            raise

    def delete_prompt(self, point_id: str) -> Candidate:
        if self.state not in (WorkflowState.PROPOSAL_READY, WorkflowState.REFINED_READY):
            raise InvalidTransition("prompt deletion is not available")
        previous = self.state
        self.state = WorkflowState.REFINE_PENDING
        try:
            candidate = self.session.delete_prompt(point_id)
            self.state = WorkflowState.REFINED_READY
            return candidate
        except Exception:
            self.state = previous
            raise

    def lock_region(self, x: int, y: int, *, label: int = 1) -> Any:
        if self.state not in (
            WorkflowState.PROPOSAL_READY,
            WorkflowState.REFINED_READY,
            WorkflowState.LOCAL_EDITING,
        ):
            raise InvalidTransition("region locking is not available")
        return self.session.lock_component((x, y), label=label)

    def unlock_region(self, region_id: str | None = None) -> Candidate | None:
        if self.state not in (
            WorkflowState.PROPOSAL_READY,
            WorkflowState.REFINED_READY,
            WorkflowState.LOCAL_EDITING,
        ):
            raise InvalidTransition("region unlocking is not available")
        regions = getattr(self.session, "frozen_regions", ())
        if region_id is None:
            if not regions:
                raise InvalidTransition("no frozen region is available")
            region_id = regions[-1].region_id
        return self.session.unlock_region(region_id)

    def start_next_region(self) -> None:
        if self.state not in (
            WorkflowState.PROPOSAL_READY,
            WorkflowState.REFINED_READY,
            WorkflowState.LOCAL_EDITING,
        ):
            raise InvalidTransition("next-region segmentation is not available")
        self.session.next_region()
        # The active pass is intentionally empty.  The next user action is to
        # draw and lock a fresh ROI; locked regions remain visible in the
        # composed full-image layer while SAM tools stay disabled until then.
        self.state = WorkflowState.IMAGE_OPEN

    def undo(self) -> Candidate | None:
        """Undo through the session and restore the visible workflow state."""
        previous_state = self.state
        candidate = self.session.undo()
        if candidate is None:
            return None
        # Undo is a local editing operation from the operator's perspective:
        # keep the edit tools available even when the restored checkpoint is
        # the original SAM candidate.  This lets a user undo a mistaken brush
        # stroke and immediately draw again without re-entering the mode.
        if previous_state == WorkflowState.LOCAL_EDITING and candidate.can_local_edit:
            self.state = WorkflowState.LOCAL_EDITING
        else:
            self.state = self._state_for_candidate(candidate)
        return candidate

    def _state_for_candidate(self, candidate: Candidate) -> WorkflowState:
        if candidate.source.value in {"manual_edit", "manual_empty"}:
            return (
                WorkflowState.LOCAL_EDITING
                if candidate.source.value == "manual_edit" and bool(candidate.mask.any())
                else WorkflowState.MANUAL_EMPTY
            )
        if candidate.can_refine:
            return (
                WorkflowState.REFINED_READY
                if getattr(self.session, "prompt_points", ())
                else WorkflowState.PROPOSAL_READY
            )
        return WorkflowState.PROPOSAL_READY

    def redo(self) -> Candidate | None:
        """Redo through the session without invoking model inference."""
        candidate = self.session.redo()
        if candidate is not None:
            self.state = self._state_for_candidate(candidate)
        return candidate

    def update_prompt(self, point_id: str, point: tuple[int, int] | None = None, label: int | None = None) -> Candidate:
        candidate = self.session.update_prompt(point_id, point, label)
        self.state = self._state_for_candidate(candidate)
        return candidate

    def expand_roi(self) -> None:
        if self.state in (WorkflowState.ACCEPTED, WorkflowState.NEEDS_REVIEW):
            raise InvalidTransition("terminal workflow")
        previous = self.state
        try:
            self.session.expand_roi()
        except Exception as exc:
            self.last_error = str(exc)
            self.state = previous
            raise
        self.state = WorkflowState.PROPOSING
        try:
            proposal = self.session.propose()
            self.state = (
                WorkflowState.PROPOSAL_READY if proposal.candidates else WorkflowState.MANUAL_EMPTY
            )
            if proposal.candidates:
                self.session.select(proposal.candidates[0].candidate_id)
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self.state = WorkflowState.MANUAL_EMPTY

    def edit(self, operation: str, **kwargs: Any) -> Candidate:
        if self.state not in (
            WorkflowState.PROPOSAL_READY,
            WorkflowState.REFINED_READY,
            WorkflowState.LOCAL_EDITING,
            WorkflowState.MANUAL_EMPTY,
        ):
            raise InvalidTransition("local edit is not available")
        c = self.session.edit(operation, **kwargs)
        self.state = WorkflowState.LOCAL_EDITING
        return c

    def manual_empty(self) -> Candidate:
        if self.state not in (WorkflowState.MANUAL_EMPTY, WorkflowState.PROPOSAL_READY):
            raise InvalidTransition("manual fallback unavailable")
        c = self.session.begin_manual()
        self.state = WorkflowState.MANUAL_EMPTY
        return c

    def accept(self, *, acknowledge_warnings: Sequence[str] = ()) -> CommitResult | PersistedPair:
        if self.state not in (
            WorkflowState.PROPOSAL_READY,
            WorkflowState.REFINED_READY,
            WorkflowState.LOCAL_EDITING,
        ):
            raise InvalidTransition("accept is not available")
        self.state = WorkflowState.VALIDATING
        try:
            result = self.session.accept(
                acknowledge_warnings=acknowledge_warnings,
                human=self.actor in {"interactive_user", "scripted_test"},
                acceptance_actor=self.actor,
            )
        except Exception as exc:
            self.last_error = str(exc)
            self.state = WorkflowState.LOCAL_EDITING
            raise
        self._accept_pending = result
        self.last_result = result
        self.state = WorkflowState.COMMITTING
        if self.accepted_store is None:
            self.state = WorkflowState.ACCEPTED
            return result
        self.state = WorkflowState.SAVING
        self.session._record("save_started", candidate_id=result.candidate_id)
        try:
            pair = self.accepted_store.save(result, actor=self.actor)
            self.last_result = pair
            self.state = WorkflowState.ACCEPTED
            self.session._record("save_finished", candidate_id=result.candidate_id)
            return pair
        except Exception as exc:
            self.last_error = str(exc)
            self.state = WorkflowState.SAVE_FAILED
            self.session._record("save_failed", reason=str(exc))
            raise

    def retry_save(self) -> PersistedPair:
        if (
            self.state != WorkflowState.SAVE_FAILED
            or self._accept_pending is None
            or self.accepted_store is None
        ):
            raise InvalidTransition("no pending accepted result")
        self.state = WorkflowState.SAVING
        self.session._record("save_started", retry=True)
        try:
            pair = self.accepted_store.save(self._accept_pending, actor=self.actor)
            self.last_result = pair
            self.state = WorkflowState.ACCEPTED
            self.session._record("save_finished", retry=True)
            return pair
        except Exception as exc:
            self.last_error = str(exc)
            self.state = WorkflowState.SAVE_FAILED
            self.session._record("save_failed", retry=True, reason=str(exc))
            raise

    def needs_review(self, reason: str, *, include_draft: bool = True) -> ReviewResult | Any:
        if not self.controls["needs_review"]:
            raise InvalidTransition("review is unavailable")
        self.state = WorkflowState.REVIEW_SAVING
        result = self.session.needs_review(reason, include_draft=include_draft)
        self._review_pending = result
        self.last_result = result
        if self.review_store is None:
            self.state = WorkflowState.NEEDS_REVIEW
            return result
        self.session._record("review_save_started")
        try:
            path = self.review_store.save_review(result, actor=self.actor)
            self.last_result = path
            self.state = WorkflowState.NEEDS_REVIEW
            self.session._record("review_save_finished")
            return path
        except Exception as exc:
            self.last_error = str(exc)
            self.state = WorkflowState.REVIEW_SAVE_FAILED
            self.session._record("review_save_failed", reason=str(exc))
            raise

    def retry_review(self) -> Any:
        if (
            self.state != WorkflowState.REVIEW_SAVE_FAILED
            or self._review_pending is None
            or self.review_store is None
        ):
            raise InvalidTransition("no pending review")
        self.state = WorkflowState.REVIEW_SAVING
        self.session._record("review_save_started", retry=True)
        try:
            path = self.review_store.save_review(self._review_pending, actor=self.actor)
            self.last_result = path
            self.state = WorkflowState.NEEDS_REVIEW
            self.session._record("review_save_finished", retry=True)
            return path
        except Exception as exc:
            self.last_error = str(exc)
            self.state = WorkflowState.REVIEW_SAVE_FAILED
            self.session._record("review_save_failed", retry=True, reason=str(exc))
            raise

    def next_image(self) -> bool:
        if not self.next_enabled:
            raise InvalidTransition("next disabled until a durable outcome")
        self.session._record("next_image")
        return True

    def key(self, key: str) -> Any:
        if key in {"1", "2", "3"}:
            return self.select(int(key))
        if key.upper() == "B":
            self._brush_mode = True
            return self._brush_mode
        if key == "[":
            return self.edit("shrink")
        if key == "]":
            return self.edit("grow")
        if key.upper() == "F":
            return self.edit("fill_holes")
        if key.upper() == "X":
            return self.expand_roi()
        if key.upper() == "Z":
            return self.undo()
        if key == " ":
            return self.accept()
        if key.upper() == "N":
            return self.next_image()
        return None
