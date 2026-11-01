import tempfile

from segvision.adapters import AcceptedStore
from tests.e2e.test_persistence_faults import committed


def test_annotation_persistence_scenarios():
    store = AcceptedStore(tempfile.mkdtemp())
    result = committed()
    pair = store.save(result, actor="scripted_test")
    assert (store.load_mask(pair) == result.full_image_mask).all()
