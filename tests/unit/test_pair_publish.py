import tempfile

from segvision.adapters import AcceptedStore
from tests.e2e.test_persistence_faults import committed


def test_each_publication_uses_a_new_versioned_png():
    store = AcceptedStore(tempfile.mkdtemp())
    result = committed()
    first = store.save(result, actor="scripted_test")
    second = store.save(result, actor="scripted_test")
    assert first.mask_path.name != second.mask_path.name
    assert second.mask_path.exists() and second.sidecar_path.exists()
