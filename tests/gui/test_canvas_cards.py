from segvision.gui.controller import AnnotationController, WorkflowState
from tests.e2e.helpers import make_session


def test_canvas_cards_expose_at_most_three_selectable_candidates():
    session, _ = make_session(count=3)
    controller = AnnotationController(session)
    controller.lock_roi()
    assert controller.state == WorkflowState.PROPOSAL_READY
    assert len(controller.visible_candidates) <= 3
    assert controller.select(1) is not None


def test_candidate_selection_can_be_switched_and_cancelled_before_accept():
    session, _ = make_session(count=3)
    controller = AnnotationController(session)
    controller.lock_roi()
    first = controller.select(1)
    second = controller.select(2)

    assert first is not None and second is not None
    assert session.selected_candidate is second
    controller.clear_selection()
    assert session.selected_candidate is None
    assert controller.controls["accept"] is False
