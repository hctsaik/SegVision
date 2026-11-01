"""Repository-owned defaults for the resumable annotation workflow."""

from __future__ import annotations

PROTOCOL_VERSION = "1.1"
DRAFT_SCHEMA_VERSION = 1
DRAFT_RETENTION = 8
HISTORY_MAX_DEPTH = 64
LABELME_AREA_DELTA_TOLERANCE = 0.02
QA_THRESHOLDS = {
    "near_full_fraction": 0.995,
    "tiny_component_pixels": 4,
    "one_pixel_bridge_pixels": 1,
    "max_components": 32,
    "labelme_area_delta_fraction": LABELME_AREA_DELTA_TOLERANCE,
}
DEFAULT_PROJECT_LABELS = (
    {
        "id": "Defect",
        "display_name": "缺陷",
        "shortcut": "D",
        "labelme_name": "Defect",
    },
)
