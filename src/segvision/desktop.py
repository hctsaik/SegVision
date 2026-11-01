"""Launch the default Native App (Tauri + React + Python sidecar)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[2]


def main(argv: list[str] | None = None) -> int:
    _ = argv
    if os.environ.get("SEGVISION_GUI", "").lower() in {"pyside", "pyside6"}:
        from segvision.gui.app import main as pyside_main

        return pyside_main()
    root = repo_root()
    host = root / "apps" / "desktop-host"
    src_tauri = host / "src-tauri"
    env = os.environ.copy()
    venv_scripts = root / ".venv" / "Scripts"
    if venv_scripts.is_dir():
        env["PATH"] = str(venv_scripts) + os.pathsep + env.get("PATH", "")
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    npm = shutil.which("npm", path=env.get("PATH"))
    if npm and (host / "package.json").is_file():
        return subprocess.call(["npm", "run", "dev"], cwd=host, env=env)
    cargo = shutil.which("cargo", path=env.get("PATH"))
    if cargo is None:
        print("Native App launch requires cargo or apps/desktop-host npm scripts.", file=sys.stderr)
        return 2
    return subprocess.call(
        ["cargo", "tauri", "dev", "--config", str(src_tauri / "tauri.conf.json")],
        cwd=src_tauri,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
