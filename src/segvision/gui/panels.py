"""Headless panel/view models for candidate cards and frozen controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from segvision.core.types import Candidate, ProposalDiagnostics


@dataclass(frozen=True, slots=True)
class CandidateCard:
    rank: int
    candidate_id: str
    source: str
    quality: float
    stability: float
    selected: bool
    can_refine: bool
    can_local_edit: bool
    can_commit: bool
    warning_codes: tuple[str, ...] = ()

    @classmethod
    def from_candidate(cls, candidate: Candidate, rank: int, *, selected: bool) -> CandidateCard:
        return cls(
            rank,
            candidate.candidate_id,
            candidate.source.value,
            float(candidate.quality),
            float(candidate.stability),
            selected,
            candidate.can_refine,
            candidate.can_local_edit,
            candidate.can_commit,
            tuple(w.code for w in candidate.warnings),
        )

    @property
    def accessible_name(self) -> str:
        return f"Candidate {self.rank}: {self.source}"


def candidate_cards(candidates: tuple[Candidate, ...], selected_id: str | None) -> tuple[CandidateCard, ...]:
    """Build cards from actual candidates; never pads or clones them."""

    if len(candidates) > 3:
        raise ValueError("candidate display cap exceeded")
    return tuple(
        CandidateCard.from_candidate(c, i + 1, selected=c.candidate_id == selected_id)
        for i, c in enumerate(candidates)
    )


@dataclass(frozen=True, slots=True)
class ControlPanelState:
    controls: dict[str, bool]
    state: str
    elapsed_ms: float
    diagnostics: ProposalDiagnostics | None
    status: str | None

    @property
    def accessible_controls(self) -> tuple[str, ...]:
        return tuple(sorted(key for key, enabled in self.controls.items() if enabled))


class AnnotationPanels:
    """View-model facade consumed by either Qt widgets or scripted tests."""

    def __init__(self, controller: Any) -> None:
        self.controller = controller

    @property
    def cards(self) -> tuple[CandidateCard, ...]:
        session = self.controller.session
        selected = session.selected_candidate.candidate_id if session.selected_candidate else None
        return candidate_cards(tuple(self.controller.visible_candidates), selected)

    @property
    def state(self) -> ControlPanelState:
        proposal = self.controller.session.current_proposal
        return ControlPanelState(
            dict(self.controller.controls),
            self.controller.state.value,
            float(self.controller.elapsed_ms),
            proposal.diagnostics if proposal else None,
            self.controller.last_error,
        )

    def select_card(self, rank: int) -> Candidate | None:
        return self.controller.select(rank)

    def accept(self, **kwargs: Any) -> Any:
        return self.controller.accept(**kwargs)

    def needs_review(self, reason: str, **kwargs: Any) -> Any:
        return self.controller.needs_review(reason, **kwargs)

    def erase(self, *, points: list[tuple[int, int]], radius: int = 0) -> Candidate:
        return self.controller.edit("erase", points=points, radius=radius)


CandidateCardModel = CandidateCard
PanelModel = AnnotationPanels

__all__ = ["AnnotationPanels", "CandidateCard", "CandidateCardModel", "ControlPanelState", "PanelModel", "candidate_cards"]
