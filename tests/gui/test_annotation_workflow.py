import tempfile

from segvision.adapters import AcceptedStore
from segvision.gui.controller import AnnotationController, WorkflowState
from tests.e2e.helpers import make_session


def test_gui_resp():
    s, _ = make_session()
    c = AnnotationController(s)
    c.lock_roi()
    assert c.state == WorkflowState.PROPOSAL_READY


def test_gui_scope():
    s, _ = make_session()
    c = AnnotationController(s)
    assert c.controls["fusion"] is False


def test_key_123():
    s, _ = make_session()
    c = AnnotationController(s)
    c.lock_roi()
    assert c.key("1") is not None


def test_key_cap():
    s, _ = make_session(count=1)
    c = AnnotationController(s)
    c.lock_roi()
    assert c.key("3") is None


def test_key_local():
    s, _ = make_session()
    c = AnnotationController(s)
    c.lock_roi()
    c.key("B")
    c.edit("brush", points=[(2, 2)])
    assert c.state == WorkflowState.LOCAL_EDITING


def test_key_space_n():
    s, _ = make_session()
    c = AnnotationController(s, accepted_store=AcceptedStore(tempfile.mkdtemp()))
    c.lock_roi()
    c.key(" ")
    assert c.next_enabled


def test_key_xz():
    s, _ = make_session()
    c = AnnotationController(s)
    c.lock_roi()
    c.key("]")
    c.key("Z")
    assert c.state == WorkflowState.LOCAL_EDITING


def test_mouse_fg_bg():
    s, _ = make_session()
    c = AnnotationController(s)
    c.lock_roi()
    c.point(15, 15, 1)
    assert c.session.events
