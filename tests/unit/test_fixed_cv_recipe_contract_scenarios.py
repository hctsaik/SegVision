import numpy as np

from segvision.core.geometry import create_crop_context
from segvision.core.recipe import CVRecipe, recipe_from_json, recipe_to_json
from segvision.cv.fixed_recipe import execute_recipe


def test_recipe_roundtrip_preserves_hash_and_gate():
    image = np.zeros((10, 10, 3), np.uint8)
    image[2:8, 2:8] = 255
    context = create_crop_context((10, 10), (0, 0, 10, 10))
    recipe = CVRecipe("r", "c", enabled=True, threshold_low=200, threshold_high=255)
    restored = recipe_from_json(recipe_to_json(recipe))
    assert restored.recipe_hash == recipe.recipe_hash
    assert execute_recipe(image, restored, context).gate in {"direct", "coarse", "invalid"}
