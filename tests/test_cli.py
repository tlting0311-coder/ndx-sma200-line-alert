from __future__ import annotations

import os
import subprocess
import sys


def test_package_module_entrypoint_shows_help():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [sys.executable, "-m", "ndx_signal", "--help"],
        check=False,
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "check" in result.stdout
    assert "test-push" in result.stdout
