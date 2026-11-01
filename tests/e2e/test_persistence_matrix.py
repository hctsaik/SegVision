import tempfile

from segvision.adapters import AcceptedStore
from tests.e2e.test_persistence_faults import committed


def test_persistence_matrix():
    store = AcceptedStore(tempfile.mkdtemp())
    first = store.save(committed(), actor="scripted_test")
    second = store.save(committed(), actor="scripted_test")
    assert first.mask_path.name != second.mask_path.name
