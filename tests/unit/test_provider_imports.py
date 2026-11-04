"""Optional model dependencies must not block a fresh fake-backend import."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_importing_fake_providers_does_not_load_optional_mobile_runtime() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_root = repo_root / "src"
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), existing_pythonpath) if value
    )
    script = (
        "import sys\n"
        "from segvision import providers\n"
        "assert providers.FakeBackend is not None\n"
        "assert 'segvision.providers.mobile_sam_torch_cpu' not in sys.modules\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
