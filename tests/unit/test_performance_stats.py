from segvision.acceptance.performance import measure


def test_performance_stats():
    assert measure(lambda: None, samples=2)["samples"] == 2
