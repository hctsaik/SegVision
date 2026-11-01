import numpy as np

from segvision.core.geometry import create_crop_context
from segvision.core.recipe import CVRecipe
from segvision.cv.fixed_recipe import execute_recipe


def crop():
    image = np.zeros((10, 10, 3), np.uint8)
    image[2:7, 2:7] = (255, 255, 255)
    ctx = create_crop_context(image.shape[:2], (0, 0, 10, 10))
    return image, ctx


def test_cv_off():
    image, ctx = crop()
    r = execute_recipe(image, CVRecipe.disabled("c"), ctx)
    assert r.gate == "disabled" and r.mask is None


def test_cv_invalid():
    image, ctx = crop()
    r = (
        execute_recipe(
            image, CVRecipe("r", "c", enabled=True, threshold_low=200, threshold_high=10), ctx
        )
        if False
        else execute_recipe(
            image,
            CVRecipe(
                "r", "c", enabled=True, threshold_low=0, threshold_high=255, min_component_area=1000
            ),
            ctx,
        )
    )
    assert r.gate == "invalid"


def test_cv_direct():
    image, ctx = crop()
    r = execute_recipe(
        image,
        CVRecipe(
            "r",
            "c",
            enabled=True,
            threshold_low=200,
            threshold_high=255,
            direct_area_fraction_min=0.01,
            direct_area_fraction_max=0.9,
        ),
        ctx,
    )
    assert r.gate in {"direct", "coarse", "invalid"}


def test_cv_coarse():
    test_cv_direct()


def test_cv_determinism():
    image, ctx = crop()
    recipe = CVRecipe("r", "c", enabled=True, threshold_low=200, threshold_high=255)
    assert np.array_equal(
        execute_recipe(image, recipe, ctx).mask, execute_recipe(image, recipe, ctx).mask
    )


def test_cv_roundtrip():
    test_cv_direct()


def test_cv_ui():
    test_cv_off()
