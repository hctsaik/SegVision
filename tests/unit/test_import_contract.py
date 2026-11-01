import importlib


def test_import_has_no_runtime_side_effects():
    module = importlib.import_module("segvision")
    assert hasattr(module, "SegVisionEngine")
