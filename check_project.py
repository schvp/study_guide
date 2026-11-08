"""Run the same project checks locally that are required in CI."""

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def check_commands(include_tests=True):
    """Return ordered commands for project verification."""

    commands = [
        [sys.executable, "-m", "compileall", "-q", "app.py", "tests"],
        [sys.executable, "validate_course.py"],
        [sys.executable, "validate_library.py"],
    ]
    if include_tests:
        commands.append(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]
        )
    return commands


def run_checks(include_tests=True):
    """Execute project checks and stop at the first failure."""

    for command in check_commands(include_tests=include_tests):
        print(f"> {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip the complete unit and integration test suite",
    )
    arguments = parser.parse_args(argv)
    run_checks(include_tests=not arguments.quick)
    print("All project checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
