from __future__ import annotations

import numpy as np

from segvision.application.qa import analyze_mask


def test_empty_mask_is_blocking_and_machine_readable():
    result = analyze_mask(np.zeros((5, 6), dtype=bool))
    assert result["blocking"] is True
    assert result["issues"][0]["code"] == "EMPTY_MASK"
    assert result["issues"][0]["threshold_id"] == "segvision-qa-v1"


def test_tiny_component_and_boundary_are_advisory():
    mask = np.zeros((8, 8), dtype=bool)
    mask[0, 0] = True
    mask[3:6, 3:6] = True
    result = analyze_mask(mask)
    codes = {issue["code"] for issue in result["issues"]}
    assert "IMAGE_BOUNDARY_CONTACT" in codes
    assert "TINY_COMPONENT" in codes
    assert result["blocking"] is False


def test_hole_and_one_pixel_bridge_are_reported_once():
    mask = np.zeros((9, 11), dtype=bool)
    mask[2:7, 2] = True
    mask[2:7, 6] = True
    mask[2, 2:7] = True
    mask[6, 2:7] = True
    # A one-pixel connector between two wider lobes.
    mask[4, 7:10] = True
    mask[3:6, 9] = True
    result = analyze_mask(mask)
    codes = [issue["code"] for issue in result["issues"]]
    assert "ENCLOSED_HOLE" in codes
    assert "ONE_PIXEL_BRIDGE" in codes
    assert len(codes) == len({(issue["code"], tuple(issue["bbox"])) for issue in result["issues"]})
