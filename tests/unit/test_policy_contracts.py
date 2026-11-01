from segvision.acceptance.external_gates import all_pending_manifests
from segvision.acceptance.profile import load_acceptance_profile
from segvision.core.policy import load_annotation_policy


def test_frozen_policy_profile_and_external_gates():
    assert load_annotation_policy().policy_id == "segvision-visible-pixels-default-v1"
    assert load_acceptance_profile().profile_id == "segvision-v1-default"
    assert all_pending_manifests("openspec/changes/build-segvision-v1/acceptance/external-gates")
