"""Cancellable background job primitives with stale-result barriers."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event, Lock
from typing import Any


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise CancelledError()


class CancelledError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Job:
    session_id: str
    revision: int
    kind: str
    token: CancellationToken = field(default_factory=CancellationToken, compare=False)


@dataclass(frozen=True, slots=True)
class JobResult:
    job: Job
    value: Any = None
    error: BaseException | None = None
    stale: bool = False


class JobRunner:
    def __init__(self, max_workers: int = 1) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="segvision-cpu"
        )
        self._lock = Lock()
        self._current_revision: dict[str, int] = {}
        self._jobs: dict[str, set[Job]] = {}

    def submit(
        self,
        job: Job,
        fn: Callable[[CancellationToken], Any],
        callback: Callable[[JobResult], None] | None = None,
    ) -> Future[JobResult]:
        with self._lock:
            current = self._current_revision.get(job.session_id, 0)
            self._current_revision[job.session_id] = max(job.revision, current)
            self._jobs.setdefault(job.session_id, set()).add(job)
            if job.revision < current:
                job.token.cancel()

        def run() -> JobResult:
            if job.token.cancelled:
                with self._lock:
                    stale = job.revision < self._current_revision.get(job.session_id, job.revision)
                return JobResult(job, error=CancelledError(), stale=stale)
            try:
                value = fn(job.token)
                error = None
            except Exception as exc:  # noqa: BLE001
                value = None
                error = exc
            with self._lock:
                stale = job.revision < self._current_revision.get(job.session_id, job.revision)
            result = JobResult(job, value, error, stale)
            with self._lock:
                self._jobs.get(job.session_id, set()).discard(job)
            # A stale result is returned to the caller for diagnostics, but is
            # never delivered to a UI callback where it could resurrect an old
            # ROI proposal.
            if callback and not isinstance(error, CancelledError):
                # Re-check immediately before delivery to close the race where
                # a revision advances after the first stale check.
                with self._lock:
                    current = self._current_revision.get(job.session_id, job.revision)
                    stale = stale or job.revision < current
                    if stale:
                        result = JobResult(job, value, error, True)
                if not stale:
                    callback(result)
            return result

        return self._executor.submit(run)

    def advance_revision(self, session_id: str, revision: int) -> None:
        with self._lock:
            self._current_revision[session_id] = max(
                revision, self._current_revision.get(session_id, 0)
            )
            for job in self._jobs.get(session_id, set()):
                if job.revision < revision:
                    job.token.cancel()

    def cancel_session(self, session_id: str) -> None:
        with self._lock:
            for job in self._jobs.get(session_id, set()):
                job.token.cancel()
            self._current_revision.pop(session_id, None)
            self._jobs.pop(session_id, None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
