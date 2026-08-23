#!/usr/bin/env python3
"""Run H2 on the development window and score it against its rejection criteria.

Usage
-----
    uv run python scripts/run_h2.py
    uv run python scripts/run_h2.py --sell-orders 1.5
    uv run python scripts/run_h2.py --end 2021-12-31

Runs the specification fixed by **Amendment A9**: 10 holdings, top decile of
12-1 momentum in the point-in-time Nifty 100, equal weight, monthly.

This spends trial budget
------------------------
Unlike `breadth_frontier.py` and `build_membership.py`, this **reads returns**.
Every distinct configuration run here is a trial and belongs in the trial
register in `HYPOTHESES.md`, including any that is run and then abandoned.
Running it twice with different parameters is two trials, whatever is reported.

The holdout is not reachable from here without saying so. `run_h2` refuses a
window overlapping 2022-2025 unless explicitly permitted.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.prices import build_bars
from indian_equity_research.market.identity import canonical_symbols
from indian_equity_research.market.membership import roll_back
from indian_equity_research.research.h2_experiment import H2Config, H2Result, load_tri, run_h2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_membership import isins_by_symbol, parsed_changes

ROSTERS = Path("data/raw/archive/nse_nifty100_constituents")
TRI = Path("data/raw/indices/nifty100_tri")


def score(result: H2Result) -> list[tuple[str, str, str, bool]]:
    """Every H2 rejection criterion, as ``(name, observed, required, passed)``.

    H2 is rejected if **any** of these fails. They are listed in the order
    ``HYPOTHESES.md`` gives them so the two can be read side by side.
    """
    excess = result.excess_cagr
    t_stat = abs(result.excess_test.t_statistic)
    drawdown_ratio = (
        result.strategy_max_drawdown / result.benchmark_max_drawdown
        if result.benchmark_max_drawdown > 0
        else float("inf")
    )
    return [
        (
            "Net return exceeds Nifty 100 TRI",
            f"{result.net_cagr:.2%} vs {result.benchmark_net_cagr:.2%}",
            "strategy > benchmark",
            excess > 0,
        ),
        (
            "Newey-West |t| on net excess",
            f"{t_stat:.2f}",
            ">= 3.0",
            t_stat >= 3.0,
        ),
        (
            "Max drawdown vs benchmark",
            f"{result.strategy_max_drawdown:.2%} vs {result.benchmark_max_drawdown:.2%}"
            f" ({drawdown_ratio:.2f}x)",
            "<= 1.3x",
            drawdown_ratio <= 1.3,
        ),
    ]


def report(result: H2Result) -> None:
    """Print the result and its verdict."""
    print(f"\n{result.config.describe()}")
    print(f"Sessions {result.dates[0]} to {result.dates[-1]} ({len(result.dates)} sessions)")
    print(f"Rebalances: {result.rebalances}\n")

    if result.residual_warnings:
        print("UNEXPLAINED LARGE MOVES IN THE PRICE DATA")
        print("  Each is either an unadjusted action or a real collapse.")
        for line in result.residual_warnings:
            print(f"    {line}")
        print()

    print(f"{'':<34}{'strategy':>14}{'benchmark':>14}")
    print(f"{'Net CAGR':<34}{result.net_cagr:>14.2%}{result.benchmark_net_cagr:>14.2%}")
    print(
        f"{'Max drawdown':<34}{result.strategy_max_drawdown:>14.2%}"
        f"{result.benchmark_max_drawdown:>14.2%}"
    )
    print(
        f"{'Volatility':<34}{result.strategy.volatility:>14.2%}{result.benchmark.volatility:>14.2%}"
    )
    print(
        f"{'Final value':<34}{result.strategy_post_tax_curve[-1]:>14,.0f}"
        f"{result.benchmark_net_curve[-1]:>14,.0f}"
    )
    print(f"\nExcess (annualised): {result.excess_cagr:+.2%}")
    print(f"Monthly excess: {result.excess_test.describe()}\n")

    print("WHAT IT COST")
    print(f"  Turnover            {result.total_turnover:>12,.0f}")
    print(f"  Charges             {result.total_charges:>12,.0f}")
    print(f"  Capital gains tax   {result.tax.total_tax:>12,.0f}")
    print(f"  {result.tax.describe()}")
    for year in sorted(result.tax.years):
        print(f"    {result.tax.years[year].describe()}")
    if result.tax.unmatched_sales:
        print(f"  UNMATCHED SALES: {result.tax.unmatched_sales} -- the fills are incomplete")

    print("\nREJECTION CRITERIA")
    failures = 0
    for name, observed, required, passed in score(result):
        mark = "PASS" if passed else "FAIL"
        failures += 0 if passed else 1
        print(f"  [{mark}] {name:<34} {observed:>28}  (required {required})")
    print(
        "\n  Not scored here: DSR p-value, PBO, the 1.5x cost stress, and the\n"
        "  40% single-year concentration cap. Each asks whether a positive\n"
        "  excess return is real, so none can rescue a negative one."
    )
    verdict = "NOT REJECTED on these criteria" if failures == 0 else "REJECTED"
    print(f"\n  ==> H2 {verdict}")
    if failures == 0:
        print(
            "      Note: this is the development window only. The declared\n"
            "      holdout (2022-2025) has not been touched, and DSR/PBO are\n"
            "      scored separately once the trial count is settled."
        )


def main() -> int:
    """Build the inputs, run H2, print the verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2021-12-31")
    parser.add_argument("--holdings", type=int, default=10)
    parser.add_argument("--sell-orders", type=float, default=1.0)
    parser.add_argument("--capital", type=float, default=300_000.0)
    args = parser.parse_args()

    cfg = H2Config(
        holdings=args.holdings,
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        initial_capital=args.capital,
        sell_orders_per_exit=args.sell_orders,
    )

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
        for problem in history.unapplied:
            print(f"    {problem.describe()}")
        return 1

    universe: set[str] = set()
    for snapshot in history.snapshots:
        universe |= snapshot.members
    # Membership is keyed by canonical symbol; bars are keyed by the ticker that
    # traded. Load every ticker belonging to a member security, or a renamed
    # company vanishes from the universe on the day it changed name.
    tickers = {sym for sym, rep in canonical.items() if rep in universe}
    print(f"  {len(universe)} securities ever in the index, {len(tickers)} tickers")

    print("building back-adjusted bars...")
    history_bars = build_bars(symbols=tickers, start=cfg.start, end=cfg.end)
    print(f"  {history_bars.describe()}")

    # Bars are keyed by traded ticker; the strategy asks by canonical symbol.
    merged: dict[str, dict[date, object]] = {}
    for ticker, series in history_bars.bars.items():
        merged.setdefault(canonical.get(ticker, ticker), {}).update(series)

    print("loading the Nifty 100 TRI...")
    tri = load_tri(TRI)
    print(f"  {len(tri)} index levels\n")

    result = run_h2(
        merged,  # type: ignore[arg-type]
        history_bars.sessions,
        history,
        tri,
        config=cfg,
        residual_warnings=tuple(r.describe() for r in history_bars.residuals),
    )
    report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
