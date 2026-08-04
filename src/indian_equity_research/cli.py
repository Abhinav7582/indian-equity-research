"""Command-line interface.

Three read-only commands::

    python -m indian_equity_research version
    python -m indian_equity_research config-check
    python -m indian_equity_research db-health

Exit codes:

* ``0`` success
* ``1`` the requested check failed (invalid configuration, unreachable
  database)
* ``2`` usage error (supplied by ``argparse``)

There is deliberately no command that fetches data, runs a strategy or
contacts a broker. None of that exists in this phase.

The standard library ``argparse`` is used rather than a CLI framework; three
subcommands do not justify a dependency.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Final

from indian_equity_research import __version__
from indian_equity_research.config import Settings, load_settings
from indian_equity_research.database.health import check_database_health
from indian_equity_research.exceptions import (
    ConfigurationError,
    DatabaseConnectionError,
)
from indian_equity_research.logging_config import configure_logging

__all__ = ["COMMANDS", "build_parser", "main"]

EXIT_OK: Final = 0
EXIT_FAILURE: Final = 1

#: Every command this CLI supports. Read-only by construction.
#:
#: This tuple is the enforced scope boundary for Phase 1: a test asserts it
#: equals exactly these three entries, so adding an execution command cannot
#: pass review unnoticed.
COMMANDS: Final[tuple[str, ...]] = ("version", "config-check", "db-health")

_PROGRAM = "indian-equity-research"
_DESCRIPTION = (
    "Indian Equity Research System - research tooling only. "
    "This program cannot place orders and has no broker connectivity."
)


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser.

    Returns:
        A parser with the ``version``, ``config-check`` and ``db-health``
        subcommands registered.
    """
    parser = argparse.ArgumentParser(prog=_PROGRAM, description=_DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    help_by_command = {
        "version": "Print the package version.",
        "config-check": "Validate configuration and print a summary with secrets masked.",
        "db-health": "Check PostgreSQL connectivity. Exits non-zero when unavailable.",
    }
    for command in COMMANDS:
        subparsers.add_parser(command, help=help_by_command[command])
    return parser


def _print_version() -> int:
    print(__version__)
    return EXIT_OK


def _print_config(settings: Settings) -> int:
    """Print a configuration summary. Never prints a secret value."""
    missing = settings.missing_data_directories()
    rows: list[tuple[str, str]] = [
        ("app_env", settings.app_env.value),
        ("app_name", settings.app_name),
        ("log_level", settings.log_level.value),
        ("data_root", str(settings.data_root)),
        ("raw_dir", str(settings.raw_dir)),
        ("interim_dir", str(settings.interim_dir)),
        ("processed_dir", str(settings.processed_dir)),
        ("reference_dir", str(settings.reference_dir)),
        ("database_host", settings.database_host),
        ("database_port", str(settings.database_port)),
        ("database_name", settings.database_name),
        ("database_user", settings.database_user),
        ("database_password", "<set>" if settings.database_password else "<not set>"),
        ("database_ssl_mode", settings.database_ssl_mode.value),
        ("database_pool_size", str(settings.database_pool_size)),
        ("database_url", settings.database_url_safe),
    ]
    width = max(len(key) for key, _ in rows)
    print("Configuration OK. Secret values are masked below.\n")
    for key, value in rows:
        print(f"  {key.ljust(width)}  {value}")

    if missing:
        print("\nData directories not present yet:")
        for path in missing:
            print(f"  - {path}")
        print("Create them with: make install   (or mkdir -p as listed above)")
    return EXIT_OK


def _check_database(settings: Settings) -> int:
    """Run the health check and translate it into an exit code."""
    try:
        health = check_database_health(settings)
    except DatabaseConnectionError as exc:
        print(f"FAIL  {exc}")
        return EXIT_FAILURE
    print(health.describe())
    return EXIT_OK if health.is_healthy else EXIT_FAILURE


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the command-line interface.

    Args:
        argv: Argument vector excluding the program name. Defaults to
            ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
    args = build_parser().parse_args(argv)

    if args.command == "version":
        return _print_version()

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return EXIT_FAILURE

    configure_logging(settings.log_level)

    if args.command == "config-check":
        return _print_config(settings)
    if args.command == "db-health":
        return _check_database(settings)

    # argparse enforces `required=True`, so this is defensive only.
    print(f"Unknown command: {args.command}")
    return EXIT_FAILURE
