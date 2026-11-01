from segvision.gui.controller import AnnotationController, InvalidTransition
from tests.e2e.helpers import make_session


def test_terminal_state_disables_roi_mutation():
    controller = AnnotationController(make_session()[0])
    controller.lock_roi()
    controller.accept()
    try:
        controller.redraw_roi((11, 9, 30, 30))
    except InvalidTransition:
        pass
    else:
        raise AssertionError("terminal workflow accepted an ROI mutation")
