from segvision.acceptance.compliance import dependency_inventory


def test_compliance():
    assert dependency_inventory()
