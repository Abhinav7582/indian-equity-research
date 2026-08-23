#!/usr/bin/env python3
"""Run H1 on the development window and score it against its rejection criteria.

Usage
-----
    uv run python scripts/run_h1.py

Measures cross-sectional momentum structure in the point-in-time Nifty 100:
mean Spearman rank IC, decile monotonicity, and the decile 10 minus decile 1
spread across five non-overlapping sub-periods. **Gross** — H1 is a statement
about structure, not about tradeability, and H2 already answered the latter.

This spends trial budget
------------------------
It reads returns. This run is a trial and belongs in the register in
`HYPOTHESES.md`.

The holdout is not reachable from here: the window ends 2021-12-31 and the
script does not accept a later one.
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.prices import build_bars
from indian_equity_research.market.identity import canonical_symbols
from indian_equity_research.market.membership import roll_back
from indian_equity_research.research.h1_experiment import H1Config, H1Result, run_h1
from indian_equity_research.research.h2_experiment import load_tri, month_start_sessions
from indian_equity_research.research.momentum import FORMATION_SESSIONS, SKIP_SESSIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_membership import isins_by_symbol, parsed_changes

ROSTERS = Path("data/raw/archive/nse_nifty100_constituents")
TRI = Path("data/raw/indices/nifty100_tri")
WARMUP = FORMATION_SESSIONS + SKIP_SESSIONS


def score(result: H1Result) -> list[tuple[str, str, str, bool]]:
    """H1's rejection criteria, verbatim from ``HYPOTHESES.md``.

    H1 is rejected if **any** fails.
    """
    t_stat = abs(result.ic_test.t_statistic)
    return [
        ("Mean rank IC", f"{result.mean_ic:+.4f}", "> 0", result.mean_ic > 0),
        ("Newey-West |t| on mean IC", f"{t_stat:.2f}", ">= 3.0", t_stat >= 3.0),
        (
            "Decile monotonicity",
            f"{result.monotonicity:+.3f}",
            ">= 0.6",
            result.monotonicity >= 0.6,
        ),
        (
            "D10-D1 positive in sub-periods",
            f"{result.positive_sub_periods} of {len(result.sub_period_spreads)}",
            ">= 3 of 5",
            result.positive_sub_periods >= 3,
        ),
    ]


def report(result: H1Result) -> None:
    """Print the measurement and the verdict."""
    print(f"\n{result.config.describe()}")
    first = result.observations[0].when
    last = result.observations[-1].when
    print(f"{len(result.observations)} rebalances, {first} to {last}")
    ranked = [o.ranked for o in result.observations]
    print(f"Securities ranked per date: min {min(ranked)}, max {max(ranked)}")
    if result.incomplete_forward:
        print(
            f"{result.incomplete_forward} forward returns measured to a last print "
            f"inside the interval (suspended, delisted or acquired)"
        )

    print("\nDECILE MEAN EXCESS RETURN, per month, gross")
    peak = max(abs(v) for v in result.decile_mean_excess) or 1.0
    for index, value in enumerate(result.decile_mean_excess, start=1):
        width = round(abs(value) / peak * 34)
        bar = ("+" if value >= 0 else "-") * width
        print(f"  D{index:<3}{value:>+9.3%}  {bar}")
    print(f"\n  D10 - D1: {result.top_minus_bottom:+.3%} per month")
    print(f"  Monotonicity (rank corr of decile index vs mean): {result.monotonicity:+.3f}")

    print(f"\nINFORMATION COEFFICIENT\n  {result.ic_test.describe()}")

    print("\nD10-D1 BY NON-OVERLAPPING SUB-PERIOD")
    for start, end, spread in result.sub_period_spreads:
        mark = "+" if spread > 0 else "-"
        print(f"  [{mark}] {start} .. {end}  {spread:>+9.3%} per month")

    print("\nREJECTION CRITERIA")
    failures = 0
    for name, observed, required, passed in score(result):
        mark = "PASS" if passed else "FAIL"
        failures += 0 if passed else 1
        print(f"  [{mark}] {name:<32} {observed:>16}  (required {required})")
    verdict = "NOT REJECTED on these criteria" if failures == 0 else "REJECTED"
    print(f"\n  ==> H1 {verdict}")


def main() -> int:
    """Build the inputs, run H1, print the verdict."""
    cfg = H1Config()

    print("reconstructing point-in-time membership...")
    roster_path = sorted(ROSTERS.glob("*.csv"))[-1]
    roster_date = date.fromisoformat(roster_path.stem.split("_")[-1])
    with roster_path.open(encoding="utf-8") as handle:
        roster = [row["Symbol"].strip().upper() for row in csv.DictReader(handle)]
    changes, _, _ = parsed_changes()
    canonical = canonical_symbols(isins_by_symbol())
    history = roll_back(roster, roster_date, changes, canonical=canonical, stop_at=cfg.start)
    print(f"  {history.describe()}")
    if history.unapplied:
        print("  REFUSING: membership could not be reconstructed cleanly.")
        return 1

    universe: set[str] = set()
    for snapshot in history.snapshots:
        universe |= snapshot.members
    tickers = {sym for sym, rep in canonical.items() if rep in universe}

    print("building back-adjusted bars...")
    built = build_bars(symbols=tickers, start=cfg.start, end=cfg.end)
    print(f"  {built.describe()}")

    merged: dict[str, dict[date, object]] = {}
    for ticker, series in built.bars.items():
        merged.setdefault(canonical.get(ticker, ticker), {}).update(series)

    sessions = sorted(built.sessions)
    rebalances = month_start_sessions(sessions[WARMUP:])
    print("loading the Nifty 100 TRI...\n")

    result = run_h1(
        merged,  # type: ignore[arg-type]
        sessions,
        history,
        load_tri(TRI),
        rebalances,
        config=cfg,
    )
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
