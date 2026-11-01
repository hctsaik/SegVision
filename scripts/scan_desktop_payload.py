"""Fail if a desktop payload contains forbidden corpora or GPL copies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FORBIDDEN_NAME_PARTS = (
    "mvtec",
    "ad2_test_public_gold",
    "edgesam",
    "x-anylabeling",
    "xanylabeling",
)


def scan(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*"):
        name = path.name.lower()
        if any(part in name for part in FORBIDDEN_NAME_PARTS):
            hits.append(str(path))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    args = parser.parse_args(argv)
    root = Path(args.root)
    hits = scan(root)
    print(json.dumps({"root": str(root), "hits": hits}))
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
