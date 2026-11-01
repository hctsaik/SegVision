from segvision.gui.controller import AnnotationController, WorkflowState
from tests.e2e.helpers import make_session


def test_annotation_workflow_scenarios():
    controller = AnnotationController(make_session()[0], actor="scripted_test")
    controller.lock_roi()
    controller.point(15, 15, 1)
    controller.accept()
    assert controller.state == WorkflowState.ACCEPTED
