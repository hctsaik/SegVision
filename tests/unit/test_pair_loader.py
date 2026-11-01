import json
import tempfile

from segvision.adapters import AcceptedStore
from tests.e2e.test_persistence_faults import committed


def test_loader_rejects_hash_mismatch():
    store = AcceptedStore(tempfile.mkdtemp())
    pair = store.save(committed(), actor="scripted_test")
    sidecar = json.loads(pair.sidecar_path.read_text(encoding="utf-8"))
    sidecar["mask"]["sha256"] = "0" * 64
    pair.sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    assert store.load() == []
