#!/usr/bin/env python3
"""Route 2 of Amendment A11 — is momentum stronger further down the size curve?

Usage
-----
    uv run python scripts/run_size_tiers.py

Measures 12-1 momentum's rank information coefficient **within** the Nifty 50
and **within** the Nifty Next 50, over the same 2016-2021 window, gross,
identical to trial #3 in every respect except the universe.

The registered prediction
-------------------------
If momentum lives further down the size curve, the mean rank IC in the **Nifty
Next 50** will exceed that in the **Nifty 50**. That was written into A11 before
this ran.

**The comparison is informative only if the smaller tier is also distinguishable
from zero:** Next 50 IC > Nifty 50 IC **and** Newey-West |t| >= 3.0 on the Next
50. Passing the first while failing the second is a suggestive negative, not
support.

Why rank IC and not deciles
---------------------------
Fifty names give decile buckets of five, which is too thin for a bucket mean to
mean anything. The IC uses all fifty every month and is the statistic H1 was
registered on. Quintiles are printed for shape and are secondary.

Why one benchmark for both tiers
--------------------------------
Rank correlation is unchanged by subtracting a constant from every observation
in a cross-section, so **the benchmark cannot affect the IC at all**. Using the
Nifty 100 TRI for both tiers therefore costs nothing on the primary metric, and
it makes the secondary quintile means directly comparable across tiers rather
than each being measured against a different yardstick.

Trial accounting
----------------
**One trial, #6.** Neither tier's IC may be reported as a standalone finding —
the registered claim is the difference between them. A11 binds this.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.prices import build_bars
from indian_equity_research.market.identity import canonical_symbols
from indian_equity_research.market.membership import MembershipHistory
from indian_equity_research.market.reconstruction import (
    NIFTY_NEXT_50_DERIVED,
    ReconstructionError,
    isins_by_symbol,
    reconstruct_difference,
)
from indian_equity_research.research.h1_experiment import H1Config, H1Result, run_h1
from indian_equity_research.research.h2_experiment import load_tri, month_start_sessions
from indian_equity_research.research.momentum import FORMATION_SESSIONS, SKIP_SESSIONS

WARMUP = FORMATION_SESSIONS + SKIP_SESSIONS
TRI = Path("data/raw/indices/nifty100_tri")

# Quintiles, not deciles. Fifty names, ten per bucket.
BUCKETS = 5


def measure(
    name: str,
    history: MembershipHistory,
    canonical: dict[str, str],
    cfg: H1Config,
) -> H1Result:
    """Build bars for one tier and measure 12-1 momentum inside it."""
    securities: set[str] = set()
    for snapshot in history.snapshots:
        securities |= snapshot.members
    tickers = {symbol for symbol, rep in canonical.items() if rep in securities}

    print(f"  {name}: {len(securities)} securities, {len(tickers)} tickers")
    built = build_bars(symbols=tickers, start=cfg.start, end=cfg.end)
    print(f"    {built.describe()}")

    merged: dict[str, dict[date, object]] = {}
    for ticker, series in built.bars.items():
        merged.setdefault(canonical.get(ticker, ticker), {}).update(series)

    sessions = sorted(built.sessions)
    return run_h1(
        merged,  # type: ignore[arg-type]
        sessions,
        history,
        load_tri(TRI),
        month_start_sessions(sessions[WARMUP:]),
        config=cfg,
    )


def report(bigger: H1Result, smaller: H1Result) -> None:
    """Print both tiers side by side and score the registered prediction."""
    print(f"\n{'':<34}{'Nifty 50':>14}{'Nifty Next 50':>16}")
    print(f"{'Mean rank IC':<34}{bigger.mean_ic:>14.4f}{smaller.mean_ic:>16.4f}")
    print(
        f"{'Newey-West |t|':<34}"
        f"{abs(bigger.ic_test.t_statistic):>14.2f}{abs(smaller.ic_test.t_statistic):>16.2f}"
    )
    print(f"{'Rebalances':<34}{len(bigger.observations):>14}{len(smaller.observations):>16}")
    print(
        f"{'Securities ranked, min':<34}"
        f"{min(o.ranked for o in bigger.observations):>14}"
        f"{min(o.ranked for o in smaller.observations):>16}"
    )

    print("\nQUINTILE MEAN EXCESS RETURN, per month, gross (secondary)")
    print(f"{'':<8}{'Nifty 50':>14}{'Nifty Next 50':>16}")
    for i in range(BUCKETS):
        print(
            f"  Q{i + 1:<5}{bigger.decile_mean_excess[i]:>+14.3%}"
            f"{smaller.decile_mean_excess[i]:>+16.3%}"
        )

    gap = smaller.mean_ic - bigger.mean_ic
    smaller_t = abs(smaller.ic_test.t_statistic)
    print("\nTHE REGISTERED PREDICTION")
    print(f"  Next 50 IC minus Nifty 50 IC: {gap:+.4f}")
    higher = gap > 0
    significant = smaller_t >= 3.0
    print(f"  [{'PASS' if higher else 'FAIL'}] smaller tier scores higher")
    print(f"  [{'PASS' if significant else 'FAIL'}] Next 50 |t| >= 3.0  (observed {smaller_t:.2f})")

    if higher and significant:
        verdict = "SUPPORTED -- momentum is stronger further down the size curve"
    elif higher:
        verdict = (
            "SUGGESTIVE NEGATIVE -- the smaller tier scores higher but is not\n"
            "        distinguishable from zero. A11 forbids reading this as support."
        )
    else:
        verdict = "NOT SUPPORTED -- the smaller tier does not score higher"
    print(f"\n  ==> {verdict}")
    print(
        "\n  A11 binds: neither tier's IC may be reported as a standalone\n"
        "  finding. The registered claim is the difference between them."
    )


def main() -> int:
    """Reconstruct both tiers, measure each, score the prediction."""
    cfg = H1Config(buckets=BUCKETS)
    print("reconstructing both tiers (shared identity map)...")
    canonical = canonical_symbols(isins_by_symbol())
    try:
        # One call builds all three: the difference reconstructs the Nifty 100
        # and the Nifty 50 to subtract them, so asking for the Nifty 50
        # separately would parse 1,038 releases a second time for no gain.
        derived, hundred, nifty50 = reconstruct_difference(
            NIFTY_NEXT_50_DERIVED, stop_at=cfg.start, canonical=canonical
        )
    except ReconstructionError as exc:
        print(f"\n  CANNOT BUILD THE UNIVERSE\n    {exc}")
        return 1

    for label, built in (("Nifty 50", nifty50), ("Nifty 100", hundred), ("Next 50", derived)):
        history = built.history
        sizes = sorted({s.size for s in history.snapshots})
        print(f"  {label:<14} {len(history.unapplied)} unapplied, sizes {sizes}")

    if nifty50.history.unapplied or derived.history.unapplied:
        print("\n  REFUSING: a tier did not reconstruct cleanly.")
        for problem in (*nifty50.history.unapplied, *derived.history.unapplied):
            print(f"    {problem.describe()}")
        return 1

    print("\nbuilding bars...")
    bigger = measure("Nifty 50", nifty50.history, canonical, cfg)
    smaller = measure("Nifty Next 50", derived.history, canonical, cfg)
    report(bigger, smaller)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
