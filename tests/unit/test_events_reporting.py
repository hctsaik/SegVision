import pytest

from segvision.acceptance.events import EventRecorder, validate_event_stream
from segvision.acceptance.reporting import build_report, strict_within_30


def test_event_recorder_is_ordered_and_json_safe():
    now = iter([10, 20])
    recorder = EventRecorder("s", clock_ns=lambda: next(now))
    recorder.emit("first", revision=1)
    recorder.emit("second", revision=1, candidate_id="c")
    assert [e.sequence for e in validate_event_stream(recorder.events)] == [1, 2]
    assert '"schema_version":1' in recorder.to_json()


def test_event_stream_rejects_mixed_or_gapped_records():
    recorder = EventRecorder("s", clock_ns=lambda: 10)
    first = recorder.emit("first")
    with pytest.raises(ValueError):
        validate_event_stream([first, {**first.to_dict(), "sequence": 3}])


def test_report_keeps_reviews_and_uses_strict_boundary():
    report = build_report(
        [
            {"outcome": "accepted", "annotation_time_ms": 29999},
            {"outcome": "needs_review", "timeout": True},
        ]
    )
    assert report["outcomes"]["total_presented_images"] == 2
    assert strict_within_30(29999)
    assert not strict_within_30(30000)
