import json

import numpy as np
import pytest

from segvision.adapters import (
    AcceptedStore,
    PersistedPair,
    clean_mask_for_polygon,
    export_directory,
    export_pair,
    labelme_dict,
    mask_to_polygons,
    preview_mask,
    rasterize_labelme,
)
from tests.e2e.test_persistence_faults import committed


def test_mask_to_polygons_uses_pixel_boundary_coordinates():
    mask = np.zeros((5, 6), dtype=np.bool_)
    mask[1:4, 2:5] = True

    assert mask_to_polygons(mask) == [[[2, 1], [5, 1], [5, 4], [2, 4]]]


def test_cleanup_closes_one_pixel_break_and_fills_enclosed_void():
    mask = np.zeros((8, 12), dtype=np.bool_)
    mask[2:6, 1:5] = True
    mask[2:6, 6:10] = True  # one-pixel break at x=5
    cleaned = clean_mask_for_polygon(mask)
    assert cleaned[3, 5]
    assert cleaned.sum() == 36

    ring = np.zeros((7, 7), dtype=np.bool_)
    ring[1:6, 1] = ring[1:6, 5] = True
    ring[1, 1:6] = ring[5, 1:6] = True
    filled = clean_mask_for_polygon(ring)
    assert not filled.all()
    assert filled[3, 3]


def test_labelme_document_is_standard_and_does_not_embed_image_bytes():
    mask = np.zeros((3, 4), dtype=np.bool_)
    mask[1, 1:3] = True

    document = labelme_dict(mask, image_path="part.png", label="part")

    assert document["version"] == "5.5.0"
    assert document["imagePath"] == "part.png"
    assert document["imageData"] is None
    assert document["imageHeight"] == 3 and document["imageWidth"] == 4
    assert document["shapes"][0]["shape_type"] == "polygon"
    assert document["shapes"][0]["label"] == "part"


def test_export_pair_writes_labelme_json_next_to_requested_output(tmp_path):
    accepted = AcceptedStore(tmp_path / "accepted")
    pair = accepted.save(committed(), actor="scripted_test")
    output = tmp_path / "labelme" / "part.json"

    exported = export_pair(
        pair,
        output,
        store=accepted,
        image_path="../dataset/part.png",
        label="part",
    )

    assert exported == output
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["imagePath"] == "../dataset/part.png"
    assert document["shapes"]
    assert not (output.parent / ".part.json.tmp").exists()


def test_export_pair_uses_defect_when_sidecar_has_no_class_id(tmp_path):
    accepted = AcceptedStore(tmp_path / "accepted")
    pair = accepted.save(committed(), actor="scripted_test")
    sidecar = dict(pair.sidecar)
    sidecar.pop("class_id", None)
    pair_without_class = PersistedPair(pair.sidecar_path, pair.mask_path, sidecar)

    output = tmp_path / "labelme" / "part.json"
    export_pair(pair_without_class, output, store=accepted)

    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["shapes"][0]["label"] == "Defect"


def test_export_directory_resolves_matching_source_image(tmp_path):
    accepted_root = tmp_path / "accepted"
    accepted = AcceptedStore(accepted_root)
    pair = accepted.save(committed(), actor="scripted_test", key="part")
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    (dataset_root / "e2e-image.png").write_bytes(b"source-placeholder")

    output = export_directory(
        accepted_root,
        tmp_path / "labelme",
        image_root=dataset_root,
    )

    assert output == [tmp_path / "labelme" / "part.json"]
    document = json.loads(output[0].read_text(encoding="utf-8"))
    assert document["imagePath"] == "../dataset/e2e-image.png"
    assert pair.sidecar_path.exists()


def test_labelme_preview_and_polygon_import_are_deterministic():
    mask = np.zeros((12, 14), dtype=bool)
    mask[2:8, 3:10] = True
    preview = preview_mask(mask, image_path="014.png")
    assert preview["label"] == "Defect"
    assert preview["polygon_count"] == 1
    assert preview["cleanup_identity"] == preview_mask(mask, image_path="014.png")["cleanup_identity"]
    document = labelme_dict(mask, image_path="014.png", label="Defect")
    imported, meta = rasterize_labelme(document, image_width=14, image_height=12)
    assert meta["rasterization"] == "PIL-ImageDraw-polygon-v1"
    assert imported.shape == mask.shape
    assert abs(int(imported.sum()) - int(mask.sum())) <= 2


def test_labelme_import_rejects_unsupported_shape():
    with pytest.raises(TypeError, match="must be an object"):
        rasterize_labelme(None, image_width=4, image_height=4)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported"):
        rasterize_labelme(
            {"imageWidth": 4, "imageHeight": 4, "shapes": [{"shape_type": "circle", "label": "Defect", "points": [[1, 1]]}]},
            image_width=4,
            image_height=4,
        )
