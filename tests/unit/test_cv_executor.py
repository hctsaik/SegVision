import numpy as np

from segvision.core.geometry import create_crop_context
from segvision.core.recipe import CVRecipe
from segvision.cv.fixed_recipe import FixedRecipeExecutor


def test_executor_is_deterministic_and_shape_preserving():
    image = np.zeros((12, 14, 3), dtype=np.uint8)
    image[3:9, 4:10] = 255
    context = create_crop_context(image.shape[:2], (1, 1, 13, 11))
    recipe = CVRecipe("r", "c", enabled=True, threshold_low=200, threshold_high=255)
    executor = FixedRecipeExecutor()
    from segvision.core.geometry import extract_crop

    crop = extract_crop(image, context)
    first = executor.run(crop, recipe, context)
    second = executor.run(crop, recipe, context)
    assert first.mask is not None and first.mask.shape == context.shape
    assert np.array_equal(first.mask, second.mask)
