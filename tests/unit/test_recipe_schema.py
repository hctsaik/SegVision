from segvision.core.recipe import CVRecipe, recipe_from_json, recipe_to_json


def test_recipe_schema():
    r = CVRecipe("r", "c", lab_l=(0, 255), lab_a=(0, 255), lab_b=(0, 255))
    assert recipe_from_json(recipe_to_json(r)).recipe_hash == r.recipe_hash
