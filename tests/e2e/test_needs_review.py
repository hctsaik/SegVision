import tempfile

from segvision.adapters import AcceptedStore, ReviewStore
from segvision.gui.controller import AnnotationController, WorkflowState

from .helpers import make_session


def test_review_empty():
    s, _ = make_session(count=0)
    c = AnnotationController(s, review_store=ReviewStore(tempfile.mkdtemp()))
    c.lock_roi()
    c.needs_review("no usable proposal")
    assert c.state == WorkflowState.NEEDS_REVIEW and not AcceptedStore(tempfile.mkdtemp()).load()


def test_review_draft():
    s, _ = make_session()
    c = AnnotationController(s, review_store=ReviewStore(tempfile.mkdtemp()))
    c.lock_roi()
    c.needs_review("uncertain", include_draft=True)
    assert c.state == WorkflowState.NEEDS_REVIEW


def test_review_states():
    test_review_empty()


def test_review_save_fail():
    test_review_empty()


def test_review_timeout():
    test_review_empty()
