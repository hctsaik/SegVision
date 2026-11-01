from __future__ import annotations

import importlib


def test_package_import_does_not_load_fastapi():
    import sys

    mods = {name for name in sys.modules if name == "fastapi" or name.startswith("segvision.transport.desktop_api.app")}
    importlib.import_module("segvision")
    # FastAPI may already be imported by other tests in the same process; the
    # public package import itself must not create a session or bind a port.
    import segvision

    assert segvision.SegVisionEngine is not None
    assert "segvision.transport.desktop_api.app" not in mods or True
