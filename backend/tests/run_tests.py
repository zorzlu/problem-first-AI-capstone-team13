"""Backend test entrypoint.

The suite is split across ``test_*.py`` modules in this package (per concern). This
runner discovers and executes all of them, so existing commands keep working:

    python -m backend.tests.run_tests
    uv run --project backend --frozen python -m backend.tests.run_tests
"""
import sys
import unittest
from pathlib import Path


def build_suite() -> unittest.TestSuite:
    tests_dir = Path(__file__).resolve().parent
    repo_root = tests_dir.parents[1]  # backend/tests -> backend -> repo root
    return unittest.TestLoader().discover(
        start_dir=str(tests_dir),
        pattern="test_*.py",
        top_level_dir=str(repo_root),
    )


def main() -> int:
    result = unittest.TextTestRunner(verbosity=1).run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
