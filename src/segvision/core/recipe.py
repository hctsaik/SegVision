"""Versioned immutable fixed-CV recipe schema."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import InvalidRecipe, RecipeClassMismatch, RecipeSchemaError


@dataclass(frozen=True, slots=True)
class CVRecipe:
    recipe_id: str
    class_id: str
    revision: int = 1
    enabled: bool = False
    working_long_side: int = 512
    algorithm: str = "lab_threshold"
    lab_l: tuple[int, int] | None = None
    lab_a: tuple[int, int] | None = None
    lab_b: tuple[int, int] | None = None
    median_blur_px: int = 3
    open_radius_px: int = 0
    close_radius_px: int = 0
    max_crop_border_fraction: float = 0.02
    max_components: int = 4
    bridge_policy: str = "direct_if_clean_else_mask_prompt"
    color_space: str = "LAB"
    channel: int = 0
    resize: tuple[int, int] = (256, 256)
    blur_kernel: tuple[int, int] = (3, 3)
    threshold_low: int = 0
    threshold_high: int = 255
    morphology_open: int = 0
    morphology_close: int = 0
    fill_holes: bool = False
    min_component_area: int = 0
    direct_area_fraction_min: float = 0.01
    direct_area_fraction_max: float = 0.85
    coarse_area_fraction_min: float = 0.001

    def __post_init__(self) -> None:
        if (
            not isinstance(self.recipe_id, str)
            or not self.recipe_id
            or not isinstance(self.class_id, str)
            or not self.class_id
        ):
            raise InvalidRecipe("recipe_id and class_id are required")
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
            or not isinstance(self.enabled, bool)
            or self.color_space != "LAB"
            or self.algorithm != "lab_threshold"
            or self.bridge_policy != "direct_if_clean_else_mask_prompt"
        ):
            raise InvalidRecipe("unsupported recipe version or color space")
        if (
            not isinstance(self.working_long_side, int)
            or isinstance(self.working_long_side, bool)
            or self.working_long_side < 1
            or not isinstance(self.median_blur_px, int)
            or isinstance(self.median_blur_px, bool)
            or self.median_blur_px < 0
            or (self.median_blur_px and self.median_blur_px % 2 == 0)
        ):
            raise InvalidRecipe("invalid working size or median blur")
        if (
            any(
                not isinstance(v, int)
                or isinstance(v, bool)
                or v < 0
                for v in (
                    self.open_radius_px,
                    self.close_radius_px,
                    self.morphology_open,
                    self.morphology_close,
                    self.min_component_area,
                )
            )
            or not isinstance(self.max_components, int)
            or isinstance(self.max_components, bool)
            or self.max_components < 1
        ):
            raise InvalidRecipe("invalid morphology/component parameters")
        for name, rng in (("L", self.lab_l), ("A", self.lab_a), ("B", self.lab_b)):
            if rng is not None and (
                len(rng) != 2
                or any(
                    not isinstance(v, int)
                    or isinstance(v, bool)
                    or v < 0
                    or v > 255
                    for v in rng
                )
                or rng[0] > rng[1]
            ):
                raise InvalidRecipe(f"invalid LAB {name} range")
        if len(self.resize) != 2 or any(
            not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in self.resize
        ):
            raise InvalidRecipe("resize must contain positive dimensions")
        if len(self.blur_kernel) != 2 or any(
            not isinstance(v, int) or isinstance(v, bool) or v < 1 or v % 2 == 0
            for v in self.blur_kernel
        ):
            raise InvalidRecipe("blur kernels must be positive odd dimensions")
        if (
            any(
                not isinstance(v, int) or isinstance(v, bool)
                for v in (self.threshold_low, self.threshold_high, self.channel)
            )
            or not isinstance(self.fill_holes, bool)
            or not (0 <= self.threshold_low <= self.threshold_high <= 255)
        ):
            raise InvalidRecipe("thresholds must be inclusive uint8 bounds")
        if self.channel not in (0, 1, 2):
            raise InvalidRecipe("LAB channel must be 0, 1, or 2")
        fractions = (
            self.max_crop_border_fraction,
            self.coarse_area_fraction_min,
            self.direct_area_fraction_min,
            self.direct_area_fraction_max,
        )
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(float(v))
            for v in fractions
        ):
            raise InvalidRecipe("area gates must be finite numbers")
        if not (0 <= self.direct_area_fraction_min <= self.direct_area_fraction_max <= 1):
            raise InvalidRecipe("direct area gate is invalid")
        if not (0 <= self.max_crop_border_fraction <= 1 and 0 <= self.coarse_area_fraction_min <= 1):
            raise InvalidRecipe("crop-border/coarse area gates are invalid")

    @property
    def recipe_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "recipe_id": self.recipe_id,
            "class_id": self.class_id,
            "enabled": self.enabled,
            "working_long_side": self.working_long_side,
            "algorithm": self.algorithm,
            "l_range": list(self.lab_l or (0, 255)),
            "a_range": list(self.lab_a or (0, 255)),
            "b_range": list(self.lab_b or (0, 255)),
            "median_blur_px": self.median_blur_px,
            "open_radius_px": self.open_radius_px,
            "close_radius_px": self.close_radius_px,
            "max_crop_border_fraction": self.max_crop_border_fraction,
            "max_components": self.max_components,
            "bridge": self.bridge_policy,
            "fill_holes": self.fill_holes,
            "min_component_area": self.min_component_area,
            "min_area_fraction": self.direct_area_fraction_min,
            "max_area_fraction": self.direct_area_fraction_max,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, expected_class_id: str | None = None
    ) -> CVRecipe:
        if data.get("schema_version") != 1:
            raise RecipeSchemaError("unsupported recipe schema version")
        required = {
            "recipe_id",
            "class_id",
            "enabled",
            "algorithm",
            "l_range",
            "a_range",
            "b_range",
            "bridge",
        }
        if not required <= set(data):
            raise RecipeSchemaError("recipe requires explicit LAB ranges and algorithm")
        allowed = {
            "schema_version",
            "recipe_id",
            "class_id",
            "enabled",
            "working_long_side",
            "algorithm",
            "l_range",
            "a_range",
            "b_range",
            "median_blur_px",
            "open_radius_px",
            "close_radius_px",
            "fill_holes",
            "min_component_area",
            "min_area_fraction",
            "max_area_fraction",
            "max_crop_border_fraction",
            "max_components",
            "bridge",
        }
        if set(data) - allowed:
            raise RecipeSchemaError(f"unknown recipe fields: {sorted(set(data) - allowed)}")
        if expected_class_id is not None and data.get("class_id") != expected_class_id:
            raise RecipeClassMismatch("recipe class binding mismatch")
        values = dict(data)
        values.pop("schema_version", None)
        values["lab_l"], values["lab_a"], values["lab_b"] = (
            tuple(values.pop("l_range")),
            tuple(values.pop("a_range")),
            tuple(values.pop("b_range")),
        )
        values["bridge_policy"] = values.pop("bridge")
        values["direct_area_fraction_min"] = values.pop("min_area_fraction", 0.01)
        values["direct_area_fraction_max"] = values.pop("max_area_fraction", 0.85)
        return cls(**values)

    @classmethod
    def disabled(cls, class_id: str) -> CVRecipe:
        return cls(
            recipe_id=f"{class_id}-disabled-v1",
            class_id=class_id,
            enabled=False,
            lab_l=(0, 255),
            lab_a=(0, 255),
            lab_b=(0, 255),
        )


def recipe_to_json(recipe: CVRecipe) -> str:
    return recipe.canonical_json()


def recipe_from_json(
    payload: str | Mapping[str, Any], *, expected_class_id: str | None = None
) -> CVRecipe:
    data = json.loads(payload) if isinstance(payload, str) else payload
    return CVRecipe.from_dict(data, expected_class_id=expected_class_id)
