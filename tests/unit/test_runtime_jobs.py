from segvision.runtime.jobs import CancellationToken, Job, JobRunner


def test_runtime_jobs():
    t = CancellationToken()
    t.cancel()
    assert t.cancelled


def test_stale_revision_never_reaches_callback():
    runner = JobRunner(max_workers=1)
    seen = []
    try:
        old = Job("session", 1, "proposal")
        runner.advance_revision("session", 2)
        result = runner.submit(old, lambda token: "old", seen.append).result(timeout=2)
        assert result.stale and seen == []
    finally:
        runner.shutdown()


def test_cancelled_token_is_reported_without_callback():
    runner = JobRunner(max_workers=1)
    seen = []
    token = CancellationToken()
    token.cancel()
    try:
        result = runner.submit(Job("session", 1, "proposal", token), lambda _: "bad", seen.append).result(timeout=2)
        assert result.error is not None and seen == []
    finally:
        runner.shutdown()
