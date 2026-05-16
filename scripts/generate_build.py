#!/usr/bin/env python
"""Generate stellashelf/_build.py with build info from git.

Usage:
    python scripts/generate_build.py
"""

import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_FILE = PROJECT_ROOT / "src" / "stellashelf" / "_build.py"


def _get_git_commit_count() -> str:
    try:
        count = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        ).decode().strip()
        return count
    except Exception:
        return "0"


def _get_git_short_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        ).decode().strip()
    except Exception:
        return "dev"


def _get_git_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        ).decode().strip()
    except Exception:
        return "unknown"


def main():
    count = _get_git_commit_count()
    hash_ = _get_git_short_hash()
    branch = _get_git_branch()
    build = f"b{count}.{hash_}.{branch}"

    BUILD_FILE.write_text(
        f'"""Auto-generated build info. Run scripts/generate_build.py to update."""\n'
        f'__build__ = {build!r}\n'
    )
    print(f"Generated {BUILD_FILE} → build={build}")


if __name__ == "__main__":
    main()
