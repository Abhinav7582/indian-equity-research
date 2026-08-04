#!/usr/bin/env python3
"""Verify that the installed environment actually works.

Run after ``uv sync``::

    uv run python scripts/verify_environment.py

Checks, in order:

1. The package imports and reports a version.
2. Configuration loads and validates.
3. Every configured data directory exists.
4. PostgreSQL connectivity (optional - reported, never fatal).

Exit codes:
    0  every required check passed
    1  a required check failed
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass(frozen=True)
class Result:
    """Outcome of a single verification step."""

    name: str
    ok: bool
    detail: str
    required: bool = True


def verify_import() -> Result:
    """Check that the package imports and reports a version."""
    try:
        import indian_equity_research
    except ImportError as exc:
        return Result("package import", False, f"{exc} - run `uv sync --extra dev`")
    return Result("package import", True, f"version {indian_equity_research.__version__}")


def verify_configuration() -> tuple[Result, object | None]:
    """Load and validate settings, returning the result and the settings."""
    from indian_equity_research.config import load_settings
    from indian_equity_research.exceptions import ConfigurationError

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        return Result("configuration", False, str(exc)), None
    detail = f"APP_ENV={settings.app_env.value}, target={settings.database_url_safe}"
    return Result("configuration", True, detail), settings


def verify_directories(settings: object) -> Result:
    """Check that every configured data directory exists."""
    from indian_equity_research.config import Settings

    assert isinstance(settings, Settings)
    missing = settings.missing_data_directories()
    if missing:
        listed = ", ".join(str(path) for path in missing)
        return Result("data directories", False, f"missing: {listed}")
    return Result("data directories", True, f"{len(settings.data_directories)} present")


def verify_database(settings: object) -> Result:
    """Check PostgreSQL connectivity. Optional: never fatal."""
    from indian_equity_research.config import Settings
    from indian_equity_research.database.health import check_database_health

    assert isinstance(settings, Settings)
    health = check_database_health(settings)
    if health.is_healthy:
        return Result("postgresql", True, f"server {health.server_version}", required=False)
    return Result(
        "postgresql",
        False,
        f"unavailable ({health.error}) - run `make db-up` if you need it",
        required=False,
    )


def _report(result: Result) -> None:
    if result.ok:
        marker, colour = "OK  ", GREEN
    elif result.required:
        marker, colour = "FAIL", RED
    else:
        marker, colour = "SKIP", YELLOW
    print(f"  {colour}{marker}{RESET}  {result.name.ljust(18)}  {result.detail}")


def main() -> int:
    """Run every verification step and print a report."""
    # This script prints its own structured report; library log records would
    # duplicate it on stderr, so the console handler is silenced here only.
    from indian_equity_research.domain.enums import LogLevel
    from indian_equity_research.logging_config import configure_logging

    configure_logging(LogLevel.CRITICAL)

    print(f"{BOLD}Verifying the Indian Equity Research environment{RESET}\n")
    results: list[Result] = []

    import_result = verify_import()
    results.append(import_result)
    _report(import_result)
    if not import_result.ok:
        print(f"\n{RED}Cannot continue without the package installed.{RESET}")
        return 1

    config_result, settings = verify_configuration()
    results.append(config_result)
    _report(config_result)
    if settings is None:
        print(f"\n{RED}Cannot continue without valid configuration.{RESET}")
        return 1

    for step in (verify_directories, verify_database):
        result = step(settings)
        results.append(result)
        _report(result)

    failed = [result for result in results if result.required and not result.ok]
    if failed:
        print(f"\n{RED}{len(failed)} required check(s) failed.{RESET}")
        return 1

    print(f"\n{GREEN}Environment verified. Phase 1 foundation is working.{RESET}")
    print("Reminder: this project performs no trading and holds no broker credentials.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
