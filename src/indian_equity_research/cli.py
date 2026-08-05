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
from pathlib import Path
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
COMMANDS: Final[tuple[str, ...]] = ("version", "config-check", "db-health", "h4-regime")

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
        "h4-regime": "Score the H4 regime overlay against the Amendment A2 criteria.",
    }
    created = {
        command: subparsers.add_parser(command, help=help_by_command[command])
        for command in COMMANDS
    }
    created["h4-regime"].add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory of manually downloaded index CSVs (default: <raw_dir>/indices).",
    )
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


def _run_h4(directory: Path) -> int:
    """Run the H4 experiment and print the Amendment A2 scorecard."""
    from indian_equity_research.data.csv_series import CsvSeriesError
    from indian_equity_research.research.h4_experiment import (
        describe_inputs,
        load_inputs,
        run_experiment,
    )

    try:
        inputs = load_inputs(directory)
    except CsvSeriesError as exc:
        print(f"Could not load input data: {exc}")
        print()
        print(f"Expected these files in {directory}:")
        for filename in (
            "nifty200_momentum30_tri.csv",
            "nifty100_pr.csv",
            "india_vix.csv",
            "nifty200_momentum30_gsec_7525.csv  (required by A2 criterion 5)",
            "nifty_1d_rate.csv  (optional)",
        ):
            print(f"  - {filename}")
        print()
        print("Download them by hand from niftyindices.com and nseindia.com.")
        print("See docs/data_sources.md for why there is no scraper here.")
        return EXIT_FAILURE

    print("INPUT DATA")
    print("=" * 72)
    concerns = 0
    for report in describe_inputs(inputs):
        print(f"  {report.name:32} {report.observations:>6} rows  {report.first} to {report.last}")
        for warning in report.warnings:
            concerns += 1
            print(f"      WARNING: {warning}")
    if concerns:
        print()
        print(f"  {concerns} warning(s). Fix the input data before trusting any result below.")
    print()

    regime, windows = run_experiment(inputs)

    print("H4 REGIME OVERLAY - scored against Amendment A2")
    print("=" * 72)
    print(f"Rule       : Nifty 100 < {regime.config.sma_window}d SMA")
    print(
        f"             AND India VIX > trailing {regime.config.vix_window}d "
        f"{regime.config.vix_quantile:.0%} percentile"
    )
    print(f"Observations: {len(regime)}   RISK-OFF: {regime.fraction_risk_off():.1%} of dates")
    print()

    if not windows:
        print("Not enough overlapping history to evaluate any window.")
        return EXIT_FAILURE

    for window in windows:
        print("-" * 72)
        print(f"{window.label}: {window.description}")
        print()
        print(f"  {'':22} {'overlaid':>14} {'buy & hold':>14}")
        print(f"  {'net CAGR':22} {window.overlaid.cagr:>13.2%} {window.baseline.cagr:>13.2%}")
        print(
            f"  {'max drawdown':22} {window.overlaid.max_drawdown:>13.2%} "
            f"{window.baseline.max_drawdown:>13.2%}"
        )
        print(
            f"  {'volatility':22} {window.overlaid.volatility:>13.2%} "
            f"{window.baseline.volatility:>13.2%}"
        )
        print(
            f"  {'final value':22} {window.overlaid.final_value:>13,.0f} "
            f"{window.baseline.final_value:>13,.0f}"
        )
        print()
        print(f"  transaction costs paid : Rs {window.total_costs:,.0f}")
        print(f"  capital gains tax paid : Rs {window.total_tax:,.0f}")
        print()
        for c in window.criteria:
            mark = "PASS" if c.passed else "FAIL"
            if not c.evaluated:
                mark = "----"
            note = f"   ({c.note})" if c.note else ""
            print(f"  [{mark}] {c.name:22} {c.observed:>34}  required {c.required}{note}")
        print()
        if not window.fully_evaluated:
            verdict = "INCOMPLETE - a required criterion could not be scored"
        else:
            verdict = "SUPPORTED" if window.supported else "REJECTED"
        print(f"  {window.label} verdict: H4 {verdict}")
        print()

    governing = windows[-1]
    print("=" * 72)
    print(f"GOVERNING WINDOW: {governing.label} (A2: the live window governs)")
    if not governing.fully_evaluated:
        print("H4 VERDICT: INCOMPLETE")
        print()
        print("At least one A2 criterion could not be scored, so H4 cannot be")
        print("declared supported. An unscored criterion is not a pass.")
    else:
        print(f"H4 IS {'SUPPORTED' if governing.supported else 'REJECTED'}")
    print()
    print("Record this result in the HYPOTHESES.md trial register before acting on it.")
    return EXIT_OK


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
    if args.command == "h4-regime":
        directory = args.data_dir or (settings.raw_dir / "indices")
        return _run_h4(directory)

    # argparse enforces `required=True`, so this is defensive only.
    print(f"Unknown command: {args.command}")
    return EXIT_FAILURE
