from segvision.acceptance.performance import measure


def test_perf_model():
    report = measure(lambda: sum(range(10)), samples=2)
    assert report["samples"] == 2 and report["p99"] >= 0


def test_perf_refine():
    assert measure(lambda: None, samples=2)["count"] == 2


def test_perf_ui():
    assert measure(lambda: {"state": "ready"}, samples=2)["max"] >= 0


def test_perf_workflow():
    report = measure(lambda: [0] * 8, samples=2)
    assert report["p50"] <= report["max"]
