"""Measure toolkit-neutral overlay/brush latency on the current CPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from segvision.acceptance.performance import fingerprint, measure
from segvision.core.mask_ops import brush


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gui_latency")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=1000)
    args = parser.parse_args(argv)
    mask = np.zeros((256, 256), dtype=np.bool_)
    index = 0

    def operation() -> None:
        nonlocal index
        brush(mask, [(index % 256, (index * 7) % 256)], 2)
        index += 1

    stats = measure(operation, samples=max(1, args.samples))
    report = {"fingerprint": fingerprint(), "metric_id": "overlay_brush", "metrics": stats}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

