import tempfile

import numpy as np
import pytest

from segvision.adapters import AcceptedStore, PersistenceFault

from .helpers import make_session


def committed():
    s, _ = make_session(count=1)
    p = s.propose()
    s.select(p.candidates[0].candidate_id)
    return s.accept()


def test_save_ok():
    result = committed()
    store = AcceptedStore(tempfile.mkdtemp())
    pair = store.save(result)
    assert len(store.load()) == 1 and store.load_mask(pair).shape == result.full_image_mask.shape


def test_save_orphan():
    root = tempfile.mkdtemp()
    from PIL import Image

    Image.fromarray(np.zeros((2, 2), np.uint8)).save(
        __import__("pathlib").Path(root) / "orphan.png"
    )
    assert not AcceptedStore(root).load()


def test_save_overwrite():
    result = committed()
    store = AcceptedStore(tempfile.mkdtemp())
    p1 = store.save(result)
    p2 = store.save(result)
    assert p1.mask_path != p2.mask_path


def test_save_path():
    result = committed()
    store = AcceptedStore(tempfile.mkdtemp())
    assert store.save(result).sidecar_path.exists()


def _assert_save_fail(stage):
    result = committed()

    def fault(current):
        if current == stage:
            raise PersistenceFault(stage)

    store = AcceptedStore(tempfile.mkdtemp(), fault=fault)
    with pytest.raises(PersistenceFault):
        store.save(result)
    assert not store.load()


def test_save_fail_temp_png():
    _assert_save_fail("png_write")


def test_save_fail_temp_json():
    _assert_save_fail("sidecar_write")


def test_save_fail_png_publish():
    _assert_save_fail("png_publish")


def test_save_fail_json_publish():
    _assert_save_fail("sidecar_publish")


def test_save_fail_verify():
    _assert_save_fail("sidecar_flush")


def test_save_corrupt():
    result = committed()
    store = AcceptedStore(tempfile.mkdtemp())
    pair = store.save(result)
    pair.mask_path.write_bytes(b"corrupt")
    assert not store.load()
