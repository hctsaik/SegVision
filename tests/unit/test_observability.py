from segvision.acceptance.observability import EventLog


def test_observability():
    e = EventLog()
    e.emit("x", timestamp_ns=1)
    assert e.events[0]["sequence"] == 1
