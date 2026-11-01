"""Immutable annotation policy and governance loaders."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class AnnotationPolicy:
    policy_id: str = "segvision-visible-pixels-default-v1"
    visible_pixels_only: bool = True
    hallucinate_occluded_region: bool = False
    include_visible_disconnected_pieces: bool = True
    retain_visible_background_holes: bool = True
    include_cast_shadow: bool = False
    include_reflection_outside_physical_object: bool = False
    image_boundary: str = "clip to visible image extent and record truncation acknowledgement"
    ambiguous_boundary: str = "prefer Needs Review over guessed Accept"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "policy_id": self.policy_id,
            "scope": "one selected physical foreground object per image",
            "rules": {
                "visible_pixels_only": self.visible_pixels_only,
                "hallucinate_occluded_region": self.hallucinate_occluded_region,
                "include_visible_disconnected_pieces_of_same_object": self.include_visible_disconnected_pieces,
                "retain_visible_background_holes": self.retain_visible_background_holes,
                "include_cast_shadow": self.include_cast_shadow,
                "include_reflection_outside_physical_object": self.include_reflection_outside_physical_object,
                "image_boundary": self.image_boundary,
                "ambiguous_boundary": self.ambiguous_boundary,
            },
        }


DEFAULT_POLICY = AnnotationPolicy()


def load_annotation_policy(path: str | Path | None = None) -> AnnotationPolicy:
    if path is None:
        return DEFAULT_POLICY
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("policy_id") != DEFAULT_POLICY.policy_id:
        raise ConfigurationError("unknown annotation policy")
    rules = data.get("rules", {})
    expected = DEFAULT_POLICY.to_dict()["rules"]
    if any(rules.get(k) != v for k, v in expected.items()):
        raise ConfigurationError("per-image or mutable policy overrides are not permitted")
    return DEFAULT_POLICY


def reject_policy_override(_: Mapping[str, Any]) -> None:
    raise ConfigurationError("annotation policy is immutable for a v1 session")
