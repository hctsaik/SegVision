"""Reference-machine performance harness with complete distributions."""

from __future__ import annotations

import os
import platform
import time
from collections.abc import Callable
from typing import Any

from .observability import aggregate_times


def measure(fn: Callable[[], Any], samples: int = 30) -> dict[str, Any]:
    values: list[float] = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        fn()
        values.append((time.perf_counter_ns() - start) / 1_000_000)
    stats = aggregate_times(values)
    stats["max"] = max(values) if values else 0.0
    stats["samples"] = len(values)
    return stats


def fingerprint() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count() or 1,
        "thread_policy": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "1"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS", "1"),
        },
    }
