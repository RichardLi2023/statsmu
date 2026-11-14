"""Prove the test step fails when any module has a failing test.

Plants selftest/test_planted_failure.py into a throwaway module, runs the same pytest
command CI uses, removes the module, and exits 0 only if pytest FAILED.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLANT = ROOT / "modules" / "99-selftest-plant"


def main() -> int:
    if PLANT.exists():
        shutil.rmtree(PLANT)
    try:
        (PLANT / "tests").mkdir(parents=True)
        (PLANT / "src").mkdir()
        shutil.copy(ROOT / "selftest" / "test_planted_failure.py", PLANT / "tests")
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pytest"], cwd=ROOT, capture_output=True, text=True
        )
    finally:
        shutil.rmtree(PLANT, ignore_errors=True)
    if result.returncode == 0:
        print("::error::Pipeline self-test FAILED: a planted failing test did not fail the run.")
        return 1
    if "test_planted_failure" not in result.stdout:
        print("::error::Pipeline self-test FAILED: the run failed, but not on the planted test.")
        print(result.stdout[-2000:])
        return 1
    print("Pipeline self-test passed: the planted failing test made the test step fail.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
