"""Stable importable acceptance CLI entry point."""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    # Keep argument parsing in one place so ``python -m segvision.acceptance``
    # and an installed console wrapper cannot drift.
    from .__main__ import main as package_main

    return package_main(list(argv) if argv is not None else None)


__all__ = ["main"]
