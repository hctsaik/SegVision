import numpy as np
import pytest

from segvision.core.errors import ModelArtifactError
from segvision.core.types import PromptBundle, PromptPoint
from tests.mobile_sam_double import ControlledPredictor, controlled_backend


def test_mobile_adapter_requires_local_approved_checkpoint(tmp_path):
    backend = controlled_backend(tmp_path)
    encoded = backend.encode(np.zeros((4, 5, 3), dtype=np.uint8), session_id="s", revision=1, crop_fingerprint="f")
    outputs = backend.decode(encoded, PromptBundle((0, 0, 5, 4)), multimask_count=3)
    assert len(outputs) == 3 and outputs[0].mask.shape == (4, 5)
    with pytest.raises(ModelArtifactError):
        backend.mask_prompt_from_binary(encoded, np.zeros((4, 5), dtype=np.uint8))


def test_mobile_decode_reuses_previous_logits_and_converts_binary_prompt(tmp_path):
    backend = controlled_backend(tmp_path)
    encoded = backend.encode(
        np.zeros((8, 9, 3), dtype=np.uint8),
        session_id="s",
        revision=1,
        crop_fingerprint="f",
    )
    initial = backend.decode(encoded, PromptBundle((1, 1, 8, 7)), multimask_count=3)
    previous = initial[0].mask_state
    before = previous.copy()
    refined = backend.decode(
        encoded,
        PromptBundle((1, 1, 8, 7), (PromptPoint(4, 4, 1),), previous),
        multimask_count=1,
    )
    coarse = np.zeros((8, 9), dtype=np.bool_)
    coarse[2:6, 3:7] = True
    converted = backend.mask_prompt_from_binary(encoded, coarse)
    assisted = backend.decode_mask_prompt(encoded, PromptBundle((1, 1, 8, 7)), converted)

    assert len(refined) == len(assisted) == 1
    assert np.array_equal(previous, before)
    assert converted.shape == (1, 256, 256)
    assert converted.dtype == np.float32
    assert backend.ledger[-1]["op"] == "decode_mask_prompt"


def test_mobile_binary_mask_prompt_uses_nearest_neighbor(tmp_path):
    backend = controlled_backend(tmp_path)
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    encoded = backend.encode(
        image, session_id="s", revision=1, crop_fingerprint="f"
    )
    coarse = np.asarray([[True, False], [False, True]], dtype=np.bool_)

    prompt = backend.mask_prompt_from_binary(encoded, coarse)

    expected = np.repeat(np.repeat(coarse, 128, axis=0), 128, axis=1)
    assert prompt.shape == (1, 256, 256)
    assert prompt.dtype == np.float32
    assert np.array_equal(prompt[0] > 0, expected)


def test_mobile_refinement_adapts_model_logit_threshold_to_include_positive_point(tmp_path):
    backend = controlled_backend(tmp_path)
    encoded = backend.encode(
        np.zeros((8, 9, 3), dtype=np.uint8),
        session_id="s",
        revision=1,
        crop_fingerprint="f",
    )
    initial = backend.decode(encoded, PromptBundle((2, 2, 8, 7)), multimask_count=1)[0]
    predictor = backend._states[encoded.token].predictor
    assert isinstance(predictor, ControlledPredictor)
    original_predict = predictor.predict

    def weak_positive_predict(**kwargs):
        logits, qualities, low_res = original_predict(**kwargs)
        logits = np.array(logits, dtype=np.float32, copy=True)
        logits[0, 0, 0] = -0.25
        return logits, qualities, low_res

    predictor.predict = weak_positive_predict
    refined = backend.decode(
        encoded,
        PromptBundle((2, 2, 8, 7), (PromptPoint(0, 0, 1),), initial.mask_state),
        multimask_count=1,
    )[0]

    assert refined.mask[0, 0]
    assert backend.ledger[-1]["mask_thresholds"][0] < -0.25
    assert backend.ledger[-1]["point_constraints_satisfied"] == [True]
