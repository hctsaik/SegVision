"""Shared hashing and repository path helpers for acceptance tooling."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "openspec").exists() and (parent / "PRD.md").exists():
            return parent
    return Path.cwd()


def maintained_tree_hash(root: Path | None = None) -> str:
    root = root or repo_root()
    excluded = {
        ".venv",
        ".git",
        "evidence",
        "dist",
        "dist_final",
        "dist_final2",
        "build",
        "node_modules",
        "target",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
    }
    entries: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        # setuptools' egg-info is a generated build cache, analogous to the
        # excluded build/dist trees, and must not make source evidence drift.
        if any(part.endswith(".egg-info") for part in path.relative_to(root).parts):
            continue
        data = path.read_bytes()
        if rel.endswith("openspec/changes/build-segvision-v1/tasks.md"):
            text = data.decode("utf-8")
            import re

            data = re.sub(r"^- \[[ xX]\]", "- [ ]", text, flags=re.MULTILINE).encode("utf-8")
        entries.append((rel, sha256_bytes(data)))
    payload = "\n".join(f"{p}\0{h}" for p, h in sorted(entries)).encode("utf-8")
    return sha256_bytes(payload)


def hashed_path(path: Path, root: Path | None = None) -> dict[str, object]:
    path = Path(path)
    data = path.read_bytes()
    # Task checkbox markers are controller bookkeeping and are normalized in
    # the maintained source fingerprint.  Use that same canonical byte stream
    # whenever a task file is recorded as an evidence input or artifact.
    if path.name == "tasks.md" and "openspec" in path.parts and "changes" in path.parts:
        import re

        data = re.sub(
            rb"^- \[[ xX]\]", b"- [ ]", data, flags=re.MULTILINE
        )
    return {
        "path": path.as_posix() if root is None else path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(data),
        "size_bytes": path.stat().st_size,
    }
