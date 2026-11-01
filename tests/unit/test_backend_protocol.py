import numpy as np

from segvision.providers.fake import FakeBackend, FakeDecode


def test_fake_backend_ledger_and_opaque_state():
    mask = np.zeros((2, 2), bool)
    mask[0, 0] = True
    backend = FakeBackend(initial=FakeDecode((mask,)))
    encoded = backend.encode(
        np.zeros((2, 2, 3), np.uint8), session_id="s", revision=1, crop_fingerprint="f"
    )
    assert (
        backend.decode(
            encoded,
            __import__("segvision").core.types.PromptBundle((0, 0, 2, 2)),
            multimask_count=1,
        )[0].mask.dtype
        == np.bool_
    )
