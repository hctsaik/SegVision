import json
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from segvision.adapters import AcceptedStore, PersistenceFault, ReviewStore
from segvision.core.types import ReviewResult
from tests.e2e.test_persistence_faults import committed


def test_accepted_pair_roundtrip_and_binary_mask():
    result = committed()
    store = AcceptedStore(tempfile.mkdtemp())
    pair = store.save(result, actor="scripted_test")
    loaded = store.load()
    assert len(loaded) == 1
    assert (store.load_mask(loaded[0]) == result.full_image_mask).all()
    assert pair.sidecar["status"] == "accepted"
    assert pair.sidecar["schema_version"] == 2
    assert pair.sidecar["region_workflow"] == {"pass_index": 1, "frozen_regions": []}


def test_loader_remains_backward_compatible_with_v1_sidecar():
    result = committed()
    store = AcceptedStore(tempfile.mkdtemp())
    pair = store.save(result, actor="scripted_test")
    legacy = dict(pair.sidecar)
    legacy["schema_version"] = 1
    legacy.pop("region_workflow")
    pair.sidecar_path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = store.load()

    assert len(loaded) == 1
    assert loaded[0].sidecar["schema_version"] == 1


def test_sidecar_publication_failure_keeps_loader_empty():
    result = committed()

    def fault(stage: str) -> None:
        if stage == "sidecar_publish":
            raise PersistenceFault(stage)

    store = AcceptedStore(tempfile.mkdtemp(), fault=fault)
    with pytest.raises(PersistenceFault):
        store.save(result, actor="scripted_test")
    assert store.load() == []


def test_nested_image_ids_are_flattened_for_safe_persistence(tmp_path: Path):
    accepted = AcceptedStore(tmp_path)
    result = replace(committed(), image_id="batch-a/part")

    pair = accepted.save(result, actor="scripted_test")

    assert pair.sidecar_path.parent == tmp_path
    assert pair.mask_path.parent == tmp_path
    assert pair.sidecar["image"]["image_id"] == "batch-a/part"
    assert not (tmp_path / "batch-a").exists()

    reviewed = ReviewStore(tmp_path)
    review_path = reviewed.save_review(
        ReviewResult(
            session_id="session",
            revision=1,
            image_id="batch-a/part",
            class_id="part",
            policy_id="policy",
            reason="operator requested review",
        ),
        actor="scripted_test",
    )
    assert review_path.parent == tmp_path / "review"
    assert review_path.exists()
