from __future__ import annotations

import numpy as np

from segvision.core.api import SegVisionEngine
from segvision.core.recipe import CVRecipe
from segvision.providers.fake import FakeBackend, FakeDecode


def test_redo_restores_manual_checkpoint_without_model_calls():
    backend = FakeBackend()
    session = SegVisionEngine(backend).start(
        np.zeros((10, 10, 3), dtype=np.uint8), "image", "Defect", [0, 0, 10, 10], CVRecipe.disabled("Defect")
    )
    session.begin_manual_empty()
    session.edit("brush", points=[(4, 4)], radius=0)
    expected = session.composited_mask.copy()
    session.undo()
    assert not session.composited_mask.any()
    encode_calls, decode_calls = backend.encode_calls, backend.decode_calls
    session.redo()
    assert np.array_equal(session.composited_mask, expected)
    assert (backend.encode_calls, backend.decode_calls) == (encode_calls, decode_calls)


def test_prompt_move_replays_decoder_only_and_preserves_id():
    initial = np.zeros((12, 12), dtype=bool)
    initial[2:10, 2:10] = True
    refined = initial.copy()
    backend = FakeBackend(initial=FakeDecode((initial,)), refine=FakeDecode((refined,)))
    session = SegVisionEngine(backend).start(
        np.zeros((12, 12, 3), dtype=np.uint8), "image", "Defect", [0, 0, 12, 12], CVRecipe.disabled("Defect")
    )
    proposal = session.propose()
    session.select(proposal.candidates[0].candidate_id)
    session.refine(proposal.candidates[0].candidate_id, (4, 4), 1)
    prompt_id = session.prompt_points[0].point_id
    encodes, decodes = backend.encode_calls, backend.decode_calls
    session.update_prompt(prompt_id, (5, 5), None)
    assert session.prompt_points[0].point_id == prompt_id
    assert session.prompt_points[0].x == 5
    assert backend.encode_calls == encodes
    assert backend.decode_calls == decodes + 1
