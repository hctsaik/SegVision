from segvision.core.recipe import CVRecipe
from tests.e2e.helpers import make_session


def test_cv_direct_bridge_skips_model_encode():
    recipe = CVRecipe("direct", "part", enabled=True, threshold_low=200, threshold_high=255)
    session, backend = make_session(recipe=recipe)
    proposal = session.propose()
    assert proposal.candidates and proposal.candidates[0].source.value == "cv_direct"
    assert backend.encode_calls == 0
