import numpy as np
import pytest

from segvision import SegVisionEngine
from segvision.core.errors import AcceptValidationError
from segvision.gui.controller import AnnotationController, WorkflowState
from segvision.providers.fake import FakeBackend, FakeDecode
from tests.e2e.helpers import make_session


def test_gui_point_refinement_transitions_state():
    controller = AnnotationController(make_session()[0])
    controller.lock_roi()
    refined = controller.point(15, 15, 1)
    assert refined.prompt_points and controller.state == WorkflowState.REFINED_READY


def test_rejected_point_refinement_preserves_previous_mask_and_prompt_history():
    mask = np.zeros((18, 18), dtype=bool)
    mask[3:8, 3:8] = True
    rejected = mask.copy()
    rejected[5, 4] = False
    backend = FakeBackend(initial=FakeDecode((mask,)), refine=FakeDecode((rejected,)))
    session = SegVisionEngine(backend).start(
        np.zeros((20, 30, 3), np.uint8), "image", "class", (8, 4, 22, 18)
    )
    controller = AnnotationController(session)
    controller.lock_roi()
    previous = session.selected_candidate

    with pytest.raises(AcceptValidationError, match="POINT_CONSTRAINT_VIOLATION"):
        controller.point(10, 7, 1)

    assert controller.state == WorkflowState.PROPOSAL_READY
    assert session.selected_candidate is previous
    assert np.array_equal(session.selected_candidate.mask, mask)

    backend.refine_result = FakeDecode((mask,))
    controller.point(10, 7, 1)
    last_decode = [entry for entry in backend.ledger if entry.get("kind") == "refine"][-1]
    assert len(last_decode["points"]) == 1
