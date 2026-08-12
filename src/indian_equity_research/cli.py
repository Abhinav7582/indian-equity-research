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
COMMANDS: Final[tuple[str, ...]] = (
    "version",
    "config-check",
    "db-health",
    "h4-regime",
    "archive",
    "reference",
    "bhavcopy",
    "circulars",
)

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
        "archive": "Snapshot sources that overwrite themselves. Read-only, one request per day.",
        "reference": "Report the trading calendar and instrument master built from local data.",
        "bhavcopy": "Plan, fetch or validate historical NSE bhavcopy files.",
        "circulars": "Collect and parse NSE index-change press releases.",
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
    archive = created["archive"]
    archive.add_argument(
        "--check",
        action="store_true",
        help="Test each source's reachability without saving anything.",
    )
    archive.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be captured without fetching or writing.",
    )
    archive.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Minimum seconds between requests (default: 3).",
    )
    bhav = created["bhavcopy"]
    bhav.add_argument(
        "--from", dest="date_from", type=str, default=None, help="First session date, YYYY-MM-DD."
    )
    bhav.add_argument(
        "--to", dest="date_to", type=str, default=None, help="Last session date, YYYY-MM-DD."
    )
    bhav.add_argument(
        "--check", action="store_true", help="Test one URL of each format without saving anything."
    )
    bhav.add_argument(
        "--fetch",
        action="store_true",
        help="Actually download. Without this, only a plan is printed.",
    )
    bhav.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N downloads. Use for a cautious first run.",
    )
    bhav.add_argument(
        "--delay", type=float, default=2.0, help="Minimum seconds between requests (floor: 1)."
    )
    bhav.add_argument(
        "--validate",
        action="store_true",
        help="Parse the local files and run the corporate-action validator.",
    )

    circ = created["circulars"]
    circ.add_argument(
        "--from-listings",
        action="store_true",
        help="Read saved /media pages in data/raw/circulars/listings/ and plan from them.",
    )
    circ.add_argument(
        "--sweep",
        action="store_true",
        help="Plan candidate URLs across the semi-annual review windows instead.",
    )
    circ.add_argument(
        "--first-year", type=int, default=2015, help="First year to sweep. Default 2015."
    )
    circ.add_argument(
        "--last-year", type=int, default=None, help="Last year to sweep. Defaults to this year."
    )
    circ.add_argument(
        "--fetch",
        action="store_true",
        help="Actually download. Without this, only a plan is printed.",
    )
    circ.add_argument(
        "--limit", type=int, default=None, help="Stop after N candidates. For a cautious first run."
    )
    circ.add_argument(
        "--delay", type=float, default=2.0, help="Minimum seconds between requests (floor: 1)."
    )
    circ.add_argument(
        "--parse",
        action="store_true",
        help="Read the downloaded PDFs and print the Nifty 100 changes found.",
    )
    circ.add_argument(
        "--index", default="Nifty 100", help="Index to extract when parsing. Default 'Nifty 100'."
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


def _run_archive(settings: Settings, *, check: bool, dry_run: bool, delay: float) -> int:
    """Capture sources that overwrite themselves, or test their reachability."""
    from indian_equity_research.constants import CONFIG_DIR
    from indian_equity_research.ingest.archive import ArchiveOutcome, DailyArchiver
    from indian_equity_research.ingest.fetcher import FetchError, UrlFetcher
    from indian_equity_research.ingest.sources import load_sources

    try:
        sources = load_sources(CONFIG_DIR / "archive_sources.yaml")
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return EXIT_FAILURE

    fetcher = UrlFetcher(delay_seconds=delay)

    if check:
        print("REACHABILITY CHECK - nothing is saved")
        print("=" * 72)
        print("Enable only the sources that return real data, in")
        print("configs/archive_sources.yaml\n")
        healthy = 0
        for source in sources:
            if source.manual:
                print(f"  MANUAL {source.name:22} by hand: {source.manual_url}")
                continue
            try:
                result = fetcher.fetch(source.url)
            except FetchError as exc:
                print(f"  FAIL  {source.name:22} {exc}")
                continue
            if result.looks_like_html() and not source.expect_html:
                print(f"  HTML  {source.name:22} returned a web page, not data - URL moved?")
                continue
            healthy += 1
            print(
                f"  OK    {source.name:22} {len(result.content):>9,} bytes  {result.content_type}"
            )
        print(f"\n  {healthy}/{len(sources)} source(s) returned usable data.")
        return EXIT_OK if healthy else EXIT_FAILURE

    archiver = DailyArchiver(root=settings.raw_dir / "archive", fetcher=fetcher)
    results = archiver.archive_all(sources, dry_run=dry_run)

    print("DAILY ARCHIVE" + ("  (dry run - nothing written)" if dry_run else ""))
    print("=" * 72)
    for r in results:
        detail = f"  {r.detail}" if r.detail else ""
        size = f"{r.bytes_written:>9,} B" if r.bytes_written else " " * 11
        print(f"  {r.outcome:18} {r.source:22} {size}{detail}")

    secured = sum(1 for r in results if r.ok)
    disabled = sum(1 for r in results if r.outcome == ArchiveOutcome.SKIPPED_DISABLED)
    manual = sum(1 for r in results if r.outcome == ArchiveOutcome.MANUAL)
    problems = [r for r in results if r.outcome in (ArchiveOutcome.FAILED, ArchiveOutcome.REJECTED)]

    print()
    print(f"  {secured} secured, {disabled} disabled, {manual} manual, {len(problems)} problem(s)")
    if disabled == len(results):
        print()
        print("  Every source is disabled. Run `archive --check` first, then enable")
        print("  the ones that returned real data. Nothing is being captured yet,")
        print("  and days not captured cannot be recovered later.")
        return EXIT_FAILURE
    return EXIT_FAILURE if problems else EXIT_OK


def _run_reference(settings: Settings) -> int:
    """Report what reference data exists, and what is missing."""
    from indian_equity_research.market.reference import build_reference

    ref = build_reference(settings.raw_dir)

    print("REFERENCE DATA")
    print("=" * 72)

    print("\nTrading calendar")
    if ref.calendar is None:
        print(f"  MISSING - {ref.calendar_problem}")
    else:
        cal = ref.calendar
        holidays = cal.missing_weekdays()
        span_years = (cal.last - cal.first).days / 365.25
        print(f"  source          {ref.calendar_source}")
        print(f"  sessions        {len(cal):,}")
        print(f"  range           {cal.first} .. {cal.last}  ({span_years:.1f} years)")
        print(f"  sessions/year   {len(cal) / span_years:.0f}")
        print(f"  weekday closures {len(holidays):,}  (exchange holidays)")
        if holidays:
            recent = [d.isoformat() for d in holidays[-5:]]
            print(f"  most recent     {', '.join(recent)}")

    print("\nInstrument master")
    if ref.symbols is None or ref.latest_snapshot is None:
        print(f"  MISSING - {ref.instrument_problem}")
    else:
        snap = ref.latest_snapshot
        hist = ref.symbols
        normal = sum(1 for r in snap.records.values() if r.is_normal_series)
        t2t = sum(1 for r in snap.records.values() if r.is_trade_to_trade)
        reused = hist.symbols_with_multiple_isins()
        renamed = hist.isins_with_multiple_symbols()
        days = (hist.observed_to - hist.observed_from).days
        print(f"  latest snapshot {snap.as_of}   securities {len(snap):,}")
        print(f"  EQ (tradeable)  {normal:,}")
        print(f"  BE/BZ (T2T)     {t2t:,}  - excluded by the universe rules")
        print(f"  observed window {hist.observed_from} .. {hist.observed_to}  ({days} days)")
        print(f"  reused symbols  {len(reused)}")
        print(f"  renamed ISINs   {len(renamed)}")
        for symbol, isins in list(reused.items())[:5]:
            print(f"      {symbol} -> {isins}")
        if days == 0:
            print()
            print("  Only one snapshot held, so symbol history has no depth yet.")
            print("  Resolutions for past dates will be ASSUMED_STABLE, not OBSERVED.")
            print("  This improves only by archiving daily - schedule it: make archive-install")

    print()
    if ref.is_complete:
        print("Both pieces available.")
        return EXIT_OK
    print("Reference data is incomplete. Phase 2c/2d depend on it.")
    return EXIT_FAILURE


def _run_circulars(settings: Settings, args: argparse.Namespace) -> int:
    """Collect and parse NSE index-change press releases.

    Three modes, deliberately separate:

    * ``--from-listings`` reads saved ``/media`` pages. Exact, because the
      listing is authoritative.
    * ``--sweep`` guesses candidate URLs across the review windows. Cheap, and
      it misses interim changes.
    * ``--parse`` reads what has been downloaded and prints the changes.

    Nothing is downloaded without ``--fetch``.
    """
    import time as _time
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from indian_equity_research.ingest.circulars_fetch import (
        CircularFetchConfig,
        extract_release_links,
        fetch_releases,
        is_possibly_relevant,
        plan_sweep,
        semi_annual_windows,
    )
    from indian_equity_research.ingest.fetcher import UrlFetcher
    from indian_equity_research.market.index_changes import (
        IndexChangeError,
        parse_index_section,
        read_release_pdf,
    )

    destination = settings.raw_dir / "circulars"
    listings_dir = destination / "listings"

    if args.parse:
        return _parse_circulars(destination, args.index, parse_index_section, read_release_pdf,
                                IndexChangeError)

    if not (args.from_listings or args.sweep):
        print("Specify --from-listings, --sweep, or --parse.")
        print()
        print("  --from-listings   preferred. Save one /media page per year to")
        print(f"                    {listings_dir}")
        print("                    (File > Save Page As > Webpage, HTML Only)")
        print("  --sweep           guess URLs across the Feb and Aug review windows")
        print("  --parse           read the PDFs already downloaded")
        return EXIT_FAILURE

    already = {p.name for p in destination.glob("ind_prs*.pdf")} if destination.exists() else set()
    urls: list[str] = []

    if args.from_listings:
        pages = sorted(listings_dir.glob("*.html")) if listings_dir.exists() else []
        if not pages:
            print(f"No saved listing pages in {listings_dir}")
            print()
            print("For each year 2015 to now:")
            print("  1. Open https://www.niftyindices.com/media")
            print("  2. Select the year")
            print("  3. File > Save Page As > Webpage, HTML Only")
            print(f"  4. Save as {listings_dir}/media_YYYY.html")
            print()
            print("The year filter runs in the browser, so the page cannot be")
            print("fetched per-year over HTTP. This is the reliable route.")
            return EXIT_FAILURE

        # Count after de-duplication, not before. Saved listing pages overlap
        # heavily - all twelve may hold the same links - so a running total
        # across pages reports a figure many times the real one, which is
        # alarming and useless.
        seen: set[str] = set()
        skipped: set[str] = set()
        for page in pages:
            for link in extract_release_links(page.read_text(encoding="utf-8", errors="replace")):
                if link.filename in already or link.filename in seen:
                    continue
                if is_possibly_relevant(link.title):
                    seen.add(link.filename)
                    urls.append(link.url)
                else:
                    skipped.add(link.filename)
        print(f"CIRCULARS - {len(pages)} saved listing page(s)")
        print("=" * 72)
        print(f"  {len(seen)} distinct relevant release(s), "
              f"{len(skipped)} skipped as clearly unrelated, "
              f"{len(already)} already held")

    if args.sweep:
        # UTC, not local time. The only consequence is which year the sweep
        # ends at, and a deterministic answer is worth more than a timezone.
        last = args.last_year or _datetime.now(_UTC).year
        windows = semi_annual_windows(args.first_year, last)
        swept = plan_sweep(windows, already_have=already)
        urls = list(dict.fromkeys([*urls, *swept]))
        print(f"CIRCULARS SWEEP - {args.first_year} to {last}")
        print("=" * 72)
        print(f"  {len(windows)} review windows, {len(swept)} base candidates")
        print("  Suffixes (_1, _2, ...) are followed only on dates that hit.")

    if args.limit is not None:
        urls = urls[: args.limit]

    print(f"  {len(urls)} URL(s) to try at {max(args.delay, 1.0):.1f}s each "
          f"(~{len(urls) * max(args.delay, 1.0) / 60:.0f} min)")
    if not args.fetch:
        print()
        print("DRY RUN - nothing downloaded. Add --fetch to proceed.")
        for url in urls[:5]:
            print(f"    {url}")
        if len(urls) > 5:
            print(f"    ... and {len(urls) - 5} more")
        return EXIT_OK

    config = CircularFetchConfig(
        destination=destination, delay_seconds=args.delay, enabled=True
    )
    fetcher = UrlFetcher(delay_seconds=config.delay_seconds)

    started = _time.monotonic()

    def _report(done: int, total: int, saved: int, absent: int) -> None:
        """Print progress. Silence for half an hour looks like a hang."""
        if done % 10 and done != total:
            return
        elapsed = _time.monotonic() - started
        rate = elapsed / max(done, 1)
        remaining = (total - done) * rate
        print(
            f"  [{done:>4}/{total}]  saved {saved:<4} missing {absent:<4} "
            f"~{remaining / 60:.0f} min left",
            flush=True,
        )

    print()
    print("  Downloading. Progress every 10 URLs; Ctrl-C is safe - files")
    print("  already saved are skipped on the next run.")
    written, missing = fetch_releases(urls, fetcher, config, progress=_report)
    print()
    print(f"  downloaded {len(written)}, {len(missing)} candidates returned nothing")
    print(f"  destination: {destination}")
    if args.sweep and not written:
        print()
        print("  No releases found. If the sweep windows are right this means")
        print("  the files are already held; otherwise check --check on bhavcopy")
        print("  to confirm niftyindices.com is reachable at all.")
    return EXIT_OK


def _parse_circulars(
    destination: Path,
    index_name: str,
    parse_index_section: object,
    read_release_pdf: object,
    error_type: type[Exception],
) -> int:
    """Read downloaded releases and print the changes for one index."""
    pdfs = sorted(destination.glob("ind_prs*.pdf")) if destination.exists() else []
    if not pdfs:
        print(f"No release PDFs in {destination}")
        return EXIT_FAILURE

    print(f"CIRCULARS PARSE - {index_name}")
    print("=" * 72)
    changes = []
    no_section = 0
    failures: list[tuple[str, str]] = []
    for pdf in pdfs:
        try:
            text = read_release_pdf(pdf)  # type: ignore[operator]
            change = parse_index_section(text, index_name, source=pdf.name)  # type: ignore[operator]
        except error_type as exc:
            message = str(exc)
            if "no section heading" in message:
                no_section += 1
            else:
                failures.append((pdf.name, message.split(".")[0]))
            continue
        changes.append(change)

    for change in sorted(changes, key=lambda c: c.effective_from):
        print(f"  {change.describe()}")

    print()
    print(f"  {len(pdfs)} PDF(s) read")
    print(f"  {len(changes)} touched {index_name}")
    print(f"  {no_section} did not mention it (normal - most releases do not)")
    if failures:
        print(f"  {len(failures)} could not be parsed:")
        for name, reason in failures[:10]:
            print(f"      {name}: {reason}")
    net = sum(c.net_size_change for c in changes)
    if changes and net != 0:
        print()
        print(f"  WARNING: net size change across all changes is {net:+d}, not 0.")
        print("  For a fixed-size index that means a release is missing or")
        print("  mis-parsed. Do not reconstruct membership until it is resolved.")
    return EXIT_OK


def _run_bhavcopy(settings: Settings, args: argparse.Namespace) -> int:
    """Plan, fetch or validate historical bhavcopy files."""
    from datetime import date as _date

    from indian_equity_research.ingest.bhavcopy_fetch import (
        BhavcopyFetchConfig,
        BhavcopyFetcher,
        FetchOutcome,
        plan_downloads,
    )
    from indian_equity_research.ingest.fetcher import FetchError, UrlFetcher
    from indian_equity_research.market.bhavcopy import (
        BhavcopyError,
        load_bhavcopy_directory,
        series_by_isin,
    )
    from indian_equity_research.market.corporate_actions import validate_price_series

    destination = settings.raw_dir / "bhavcopy"
    config = BhavcopyFetchConfig(delay_seconds=args.delay, enabled=bool(args.fetch))

    if args.check:
        print("BHAVCOPY URL CHECK - nothing is saved")
        print("=" * 72)
        probe = UrlFetcher(delay_seconds=config.effective_delay)
        healthy = 0
        for when, label in ((_date(2024, 7, 5), "LEGACY"), (_date(2024, 7, 8), "UDIFF")):
            url = config.url_for(when)
            try:
                result = probe.fetch(url)
            except FetchError as exc:
                print(f"  FAIL  {label:7} {exc}")
                continue
            if result.looks_like_html():
                print(f"  HTML  {label:7} returned a web page, not a zip - URL moved?")
                continue
            healthy += 1
            print(f"  OK    {label:7} {len(result.content):>9,} bytes  {url}")
        print(f"\n  {healthy}/2 URL templates returned usable data.")
        if healthy < 2:
            print("  Correct the templates in BhavcopyFetchConfig before fetching.")
        return EXIT_OK if healthy == 2 else EXIT_FAILURE

    if args.validate:
        try:
            records, report = load_bhavcopy_directory(destination)
        except BhavcopyError as exc:
            print(f"Could not load bhavcopy files: {exc}")
            return EXIT_FAILURE
        print("BHAVCOPY VALIDATION")
        print("=" * 72)
        print(f"  {report.summary()}")
        for name, reason in report.failures[:10]:
            print(f"      FAILED {name}: {reason}")
        if not records:
            return EXIT_FAILURE

        all_series, problems = series_by_isin(records)
        for problem in problems[:5]:
            print(f"      {problem}")

        # Without a market series every crash day is reported as unexplained.
        market = None
        try:
            from indian_equity_research.data.csv_series import load_price_series_glob

            market = load_price_series_glob(
                settings.raw_dir / "indices", "nifty100_pr*.csv", "Nifty 100 PR"
            )
            print("  Attributing market-wide moves using Nifty 100 PR.")
        except Exception:  # noqa: BLE001 - the market series is an aid, not a requirement
            print("  No index series available; crash days will read as UNEXPLAINED.")

        # ISINs are unreadable in a report; resolve them where possible.
        symbol_of: dict[str, str] = {}
        try:
            from indian_equity_research.market.instruments import (
                SymbolHistory,
                load_snapshots,
            )

            history = SymbolHistory.from_snapshots(load_snapshots(settings.raw_dir / "archive"))
            symbol_of = {span.isin: span.symbol for span in history.spans}
        except Exception:  # noqa: BLE001 - names are cosmetic
            pass

        tally: dict[str, int] = {}
        blocked_isins: list[tuple[str, int]] = []
        for isin, series in all_series.items():
            validation = validate_price_series(series, isin=isin, market=market)
            for name, count in validation.count_by_class().items():
                tally[name] = tally.get(name, 0) + count
            if not validation.passed:
                blocked_isins.append((isin, len(validation.blocking)))

        print()
        print(
            f"  {len(all_series):,} securities validated, "
            f"{len(blocked_isins):,} blocked, {len(problems):,} unusable."
        )
        print()
        print("  Large moves by classification:")
        for name, count in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"      {name:32} {count:>8,}")

        if blocked_isins:
            worst = sorted(blocked_isins, key=lambda kv: -kv[1])[:10]
            print()
            print("  Most-affected securities:")
            delisted = 0
            for isin, count in worst:
                ticker = symbol_of.get(isin)
                if ticker is None:
                    delisted += 1
                    label = "<delisted>"
                else:
                    label = ticker
                print(f"      {isin}  {label:<14} {count:,} unresolved move(s)")
            if delisted:
                print()
                print(
                    f"      {delisted} of these are no longer listed. Securities that "
                    f"collapsed or were"
                )
                print(
                    "      delisted dominate the violent-move list, which is exactly why they are"
                )
                print(
                    "      retained: a universe built from today's listings would hide "
                    "them entirely."
                )
            print()
            print("  These are the specification for the adjustment engine.")
            print("  SUSPECTED_UNADJUSTED_ACTION entries are corporate actions not yet")
            print("  applied; UNEXPLAINED entries need investigating individually.")
        return EXIT_FAILURE if blocked_isins else EXIT_OK

    if not args.date_from or not args.date_to:
        print("Specify --from and --to (YYYY-MM-DD), or use --check / --validate.")
        return EXIT_FAILURE
    try:
        start = _date.fromisoformat(args.date_from)
        end = _date.fromisoformat(args.date_to)
    except ValueError as exc:
        print(f"Invalid date: {exc}")
        return EXIT_FAILURE

    sessions: set[_date] | None = None
    try:
        from indian_equity_research.market.reference import calendar_from_index_series

        calendar, source = calendar_from_index_series(settings.raw_dir / "indices")
        sessions = set(calendar.sessions)
        print(f"Using observed sessions from {source} to skip non-trading days.\n")
    except Exception:  # noqa: BLE001 - the calendar is an optimisation, not a requirement
        print("No trading calendar available; every weekday will be requested.\n")

    plan = plan_downloads(start, end, destination, config, sessions)
    print("BHAVCOPY " + ("FETCH" if args.fetch else "PLAN (dry run)"))
    print("=" * 72)
    print(f"  {plan.describe()}")
    print(f"  destination  {destination}")

    if not args.fetch:
        print()
        print("  Nothing downloaded. Re-run with --fetch to proceed.")
        print("  Verify the URLs first with: bhavcopy --check")
        return EXIT_OK

    destination.mkdir(parents=True, exist_ok=True)
    fetcher = BhavcopyFetcher(destination, UrlFetcher(delay_seconds=config.effective_delay), config)
    results = fetcher.fetch_range(plan, limit=args.limit)
    outcome_counts: dict[str, int] = {}
    for outcome in (r.outcome for r in results):
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    print()
    for name, count in sorted(outcome_counts.items()):
        print(f"  {name:16} {count:,}")
    failures = [r for r in results if r.outcome in (FetchOutcome.FAILED, FetchOutcome.REJECTED)]
    for failure in failures[:5]:
        print(f"      {failure.when} {failure.detail}")
    return EXIT_FAILURE if failures else EXIT_OK


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
    if args.command == "archive":
        return _run_archive(settings, check=args.check, dry_run=args.dry_run, delay=args.delay)
    if args.command == "reference":
        return _run_reference(settings)
    if args.command == "bhavcopy":
        return _run_bhavcopy(settings, args)
    if args.command == "circulars":
        return _run_circulars(settings, args)

    # argparse enforces `required=True`, so this is defensive only.
    print(f"Unknown command: {args.command}")
    return EXIT_FAILURE
