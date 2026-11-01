from segvision.runtime.jobs import Job, JobRunner


def test_runtime_stale_result_is_marked_and_not_delivered():
    runner = JobRunner()
    seen = []
    try:
        runner.advance_revision("s", 2)
        result = runner.submit(Job("s", 1, "encode"), lambda _: "stale", seen.append).result(timeout=2)
        assert result.stale and seen == []
    finally:
        runner.shutdown()
