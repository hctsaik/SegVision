"""Measure deterministic fake-backend encode/decode latency."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from segvision.acceptance.performance import fingerprint, measure
from segvision.core.types import PromptBundle
from segvision.providers.fake import FakeBackend, FakeDecode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="model_latency")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args(argv)
    mask = np.zeros((128, 128), dtype=np.bool_)
    mask[16:112, 16:112] = True
    backend = FakeBackend(initial=FakeDecode((mask,)))
    encoded = backend.encode(mask[..., None].repeat(3, axis=2).astype(np.uint8), session_id="benchmark", revision=1, crop_fingerprint="0" * 64)
    stats = measure(lambda: backend.decode(encoded, PromptBundle((16, 16, 112, 112)), multimask_count=3), samples=max(1, args.samples))
    report = {"fingerprint": fingerprint(), "metric_id": "fake_backend_decode", "metrics": stats}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

