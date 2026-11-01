import tempfile

from segvision.adapters import AcceptedStore
from segvision.gui.controller import AnnotationController, WorkflowState
from tests.e2e.helpers import make_session


def test_durable_accept_enables_next_and_exposes_elapsed_time():
    controller = AnnotationController(make_session()[0], accepted_store=AcceptedStore(tempfile.mkdtemp()))
    controller.lock_roi()
    controller.accept()
    assert controller.state == WorkflowState.ACCEPTED
    assert controller.next_enabled and controller.elapsed_ms >= 0
