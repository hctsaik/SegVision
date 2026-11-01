import numpy as np

from segvision.core.geometry import create_crop_context
from segvision.core.recipe import CVRecipe
from segvision.cv.fixed_recipe import execute_recipe


def test_cv_disabled_and_invalid_gates_are_fail_closed():
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    context = create_crop_context(image.shape[:2], (0, 0, 8, 8))
    assert execute_recipe(image, CVRecipe.disabled("c"), context).gate == "disabled"
    invalid = CVRecipe("r", "c", enabled=True, min_component_area=1000)
    assert execute_recipe(image, invalid, context).gate == "invalid"
