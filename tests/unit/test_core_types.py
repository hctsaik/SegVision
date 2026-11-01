import numpy as np

from segvision.core.types import Candidate, CandidateSource, GeneratorKind, Provenance


def test_candidate_mask_is_immutable_and_json_safe():
    c = Candidate(
        "c",
        "s",
        1,
        np.zeros((2, 2), bool),
        Provenance(GeneratorKind.MANUAL, CandidateSource.MANUAL_EDIT),
        False,
        True,
        True,
    )
    assert c.mask.flags.writeable is False and c.to_dict()["source"] == "manual_edit"
