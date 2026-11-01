from segvision.gui.controller import AnnotationController
from tests.e2e.helpers import make_session


def test_gui_scope_keeps_fusion_disabled_in_v1():
    controller = AnnotationController(make_session()[0])
    assert controller.controls["fusion"] is False
