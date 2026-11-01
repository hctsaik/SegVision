from __future__ import annotations

import hashlib

import numpy as np
import pytest

from segvision.adapters.drafts import DraftStore
from segvision.core.errors import PersistenceError


def test_draft_store_isolated_and_hash_checked(tmp_path):
    source = np.zeros((8, 9, 3), dtype=np.uint8)
    source_sha = hashlib.sha256(source.tobytes()).hexdigest()
    store = DraftStore(tmp_path)
    record = store.save(
        dataset_id="dataset",
        item_id="item",
        source_sha256=source_sha,
        payload={"protocol_version": "1.1", "revision": 3, "class_id": "Defect"},
        mask=np.eye(8, 9, dtype=bool),
    )
    loaded = store.load(dataset_id="dataset", item_id="item", source_sha256=source_sha)
    assert loaded["draft_id"] == record["draft_id"]
    assert store.inspect(dataset_id="dataset", item_id="item")[0]["valid"] is True
    with pytest.raises(PersistenceError, match="fingerprint"):
        store.load(dataset_id="dataset", item_id="item", source_sha256="0" * 64)
    assert not (tmp_path / "accepted").exists()


def test_discard_targets_only_requested_item(tmp_path):
    store = DraftStore(tmp_path)
    for item in ("one", "two"):
        store.save(
            dataset_id="dataset",
            item_id=item,
            source_sha256="1" * 64,
            payload={"protocol_version": "1.1"},
            mask=np.ones((2, 2), dtype=bool),
        )
    assert store.discard(dataset_id="dataset", item_id="one") == 1
    assert store.inspect(dataset_id="dataset", item_id="two")[0]["valid"] is True
