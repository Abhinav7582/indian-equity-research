#!/usr/bin/env python3
"""Check local prerequisites and print the exact setup steps.

This script is deliberately inert: it inspects the machine and prints
guidance. It installs nothing, creates nothing and modifies nothing.

It uses only the standard library so that it runs before the project's
virtual environment exists.

Exit codes:
    0  every required prerequisite is present
    1  at least one required prerequisite is missing
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_PYTHON = (3, 12)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass(frozen=True)
class Check:
    """Outcome of a single prerequisite check."""

    name: str
    ok: bool
    detail: str
    required: bool


def _tool_version(executable: str, *args: str) -> str | None:
    """Return the first line of a tool's version output, or None if absent."""
    path = shutil.which(executable)
    if path is None:
        return None
    try:
        completed = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "installed (version unavailable)"
    output = (completed.stdout or completed.stderr).strip().splitlines()
    return output[0] if output else "installed"


def check_uv() -> Check:
    """Check that uv is installed; it provisions Python and the venv."""
    version = _tool_version("uv", "--version")
    return Check(
        name="uv",
        ok=version is not None,
        detail=version or "not found - install from https://docs.astral.sh/uv/",
        required=True,
    )


def check_git() -> Check:
    """Check that git is installed."""
    version = _tool_version("git", "--version")
    return Check("git", version is not None, version or "not found", required=True)


def check_docker() -> Check:
    """Check for Docker and whether its daemon is running (optional)."""
    version = _tool_version("docker", "--version")
    if version is None:
        return Check("docker", False, "not found - PostgreSQL tests will skip", required=False)
    daemon_up = (
        subprocess.run(
            [str(shutil.which("docker")), "info"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    detail = version if daemon_up else f"{version} (daemon not running)"
    return Check("docker", daemon_up, detail, required=False)


def check_managed_python() -> Check:
    """Uv provisions Python itself, so the host interpreter version is advisory."""
    current = sys.version_info
    running = f"{current.major}.{current.minor}.{current.micro}"
    if current[:2] >= REQUIRED_PYTHON:
        return Check("python (host)", True, running, required=False)
    return Check(
        "python (host)",
        True,
        f"{running} - below 3.12, but `uv sync` installs 3.12 for the project",
        required=False,
    )


def check_env_file() -> Check:
    """Check whether a local .env has been created from the example."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.is_file():
        return Check(".env", True, "present", required=False)
    return Check(".env", False, "absent - copy .env.example to .env", required=False)


def main() -> int:
    """Run every check and print a report."""
    print(f"{BOLD}Indian Equity Research System - environment check{RESET}")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Platform     : {platform.system()} {platform.machine()}\n")

    checks = [
        check_managed_python(),
        check_uv(),
        check_git(),
        check_docker(),
        check_env_file(),
    ]

    width = max(len(check.name) for check in checks)
    for check in checks:
        if check.ok:
            marker, colour = "OK  ", GREEN
        elif check.required:
            marker, colour = "MISS", RED
        else:
            marker, colour = "WARN", YELLOW
        print(f"  {colour}{marker}{RESET}  {check.name.ljust(width)}  {check.detail}")

    missing = [check for check in checks if check.required and not check.ok]

    print(f"\n{BOLD}Next steps{RESET}")
    steps = [
        "uv sync --extra dev                     # create .venv and install",
        "cp .env.example .env                    # then edit values as needed",
        "make db-up                              # optional: start PostgreSQL",
        "make check                              # format, lint, typecheck, unit tests",
        "uv run python -m indian_equity_research config-check",
    ]
    for step in steps:
        print(f"  {step}")

    if missing:
        names = ", ".join(check.name for check in missing)
        print(f"\n{RED}Install the missing prerequisites first: {names}{RESET}")
        return 1

    print(f"\n{GREEN}All required prerequisites are present.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
