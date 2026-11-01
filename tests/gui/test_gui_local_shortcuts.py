from segvision.gui.controller import AnnotationController, WorkflowState
from tests.e2e.helpers import make_session


def test_local_shortcuts_drive_edit_and_undo():
    controller = AnnotationController(make_session()[0])
    controller.lock_roi()
    controller.key("B")
    controller.key("[")
    assert controller.state == WorkflowState.LOCAL_EDITING
    controller.key("Z")
