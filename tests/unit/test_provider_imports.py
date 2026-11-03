"""Optional model dependencies must not block the fake-backend application."""

from __future__ import annotations

import sys

from segvision import providers


def test_importing_fake_providers_does_not_load_optional_mobile_runtime() -> None:
    assert providers.FakeBackend is not None
    assert "segvision.providers.mobile_sam_torch_cpu" not in sys.modules
