#!/usr/bin/env python3
"""Amendment A12, trial #7 — does NSE's own momentum signal do better than ours?

Usage
-----
    uv run python scripts/run_risk_adjusted.py

Measures the rank information coefficient of **risk-adjusted** momentum — 6-month
and 12-month returns each divided by trailing volatility, cross-sectionally
standardised and averaged, no skip month — on the point-in-time Nifty 100, 2016
to 2021, gross.

**Identical to trial #3 in every respect except the signal.** Same universe,
same window, same monthly cadence, same forward returns, same excess, same IC,
same Newey-West statistic — the same lines of code from the ranking onward. Any
difference in the result is a difference in the signal, not in the harness.

Why this exists
---------------
Four trials varied the universe, the breadth, the costs, the tiers and the
window while holding one signal constant: raw 12-1 momentum. Baseline B3, scored
at last, showed the investable momentum index returning **25.10% a year** over
exactly the window our strategy returned 10.85%. So "momentum did not work in
India" is not the explanation, and the likeliest remaining one is that we tested
a different signal from the one that worked.

The registered prediction, from A12 and written before this ran
----------------------------------------------------------------
> The risk-adjusted score will produce a mean rank IC **materially above the raw
> 12-1 figure of +0.0378**.

Support requires **both**: a higher IC **and** Newey-West |t| >= 3.0 on it.
Higher-but-not-significant is a **suggestive positive**, recorded as such and
not as encouragement — the same standing A11 gave the mirror-image outcome in
trial #6.

**An honest limit.** Even full support would not explain the whole B3 gap. NSE's
25.10% comes from signal, universe, concentration and weighting together, and
this moves one of the four.

Trial accounting
----------------
**One trial, #7.** It reads returns.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.engine import Bar
from indian_equity_research.backtest.prices import build_bars
from indian_equity_research.market.reconstruction import (
    NIFTY_100,
    ReconstructionError,
    reconstruct,
)
from indian_equity_research.research.h1_experiment import H1Config, H1Result, run_h1
from indian_equity_research.research.h2_experiment import load_tri, month_start_sessions
from indian_equity_research.research.momentum import (
    FORMATION_SESSIONS,
    SKIP_SESSIONS,
    rank_by_momentum,
    rank_by_risk_adjusted_momentum,
)

TRI = Path("data/raw/indices/nifty100_tri")

# The raw 12-1 figure from trial #3, fixed in A12 as the number to beat. Written
# here rather than recomputed so the comparison cannot drift.
RAW_12_1_IC: float = 0.0378

# The warm-up must be the LONGER of the two signals' needs, so both are measured
# over identical dates. 12-1 needs 273 sessions; the risk-adjusted score needs
# 252. Using each signal's own minimum would give them different windows and
# make the comparison meaningless.
WARMUP = FORMATION_SESSIONS + SKIP_SESSIONS


def report(raw: H1Result, adjusted: H1Result) -> None:
    """Print both signals side by side and score the registered prediction."""
    print(f"\n{'':<32}{'raw 12-1':>14}{'risk-adjusted':>16}")
    print(f"{'Mean rank IC':<32}{raw.mean_ic:>14.4f}{adjusted.mean_ic:>16.4f}")
    print(
        f"{'Newey-West |t|':<32}"
        f"{abs(raw.ic_test.t_statistic):>14.2f}{abs(adjusted.ic_test.t_statistic):>16.2f}"
    )
    print(f"{'Rebalances':<32}{len(raw.observations):>14}{len(adjusted.observations):>16}")
    print(
        f"{'Securities ranked, min':<32}"
        f"{min(o.ranked for o in raw.observations):>14}"
        f"{min(o.ranked for o in adjusted.observations):>16}"
    )

    print("\nDECILE MEAN EXCESS RETURN, per month, gross")
    print(f"{'':<8}{'raw 12-1':>14}{'risk-adjusted':>16}")
    for index in range(len(raw.decile_mean_excess)):
        print(
            f"  D{index + 1:<5}{raw.decile_mean_excess[index]:>+14.3%}"
            f"{adjusted.decile_mean_excess[index]:>+16.3%}"
        )
    print(f"\n  D10-D1  {raw.top_minus_bottom:>+12.3%}{adjusted.top_minus_bottom:>+16.3%}")
    print(f"  monotonicity{raw.monotonicity:>+10.3f}{adjusted.monotonicity:>+16.3f}")

    print("\nTHE REGISTERED PREDICTION  (A12, written before this ran)")
    higher = adjusted.mean_ic > RAW_12_1_IC
    t_stat = abs(adjusted.ic_test.t_statistic)
    significant = t_stat >= 3.0
    print(f"  risk-adjusted IC {adjusted.mean_ic:+.4f} vs raw {RAW_12_1_IC:+.4f}")
    print(f"  [{'PASS' if higher else 'FAIL'}] beats the raw 12-1 figure")
    print(f"  [{'PASS' if significant else 'FAIL'}] |t| >= 3.0  (observed {t_stat:.2f})")

    if higher and significant:
        verdict = "SUPPORTED -- we were testing the wrong signal"
    elif higher:
        verdict = (
            "SUGGESTIVE POSITIVE -- higher, but not distinguishable from zero.\n"
            "        A12 forbids reading this as support."
        )
    else:
        verdict = "NOT SUPPORTED -- the signal is not the explanation"
    print(f"\n  ==> {verdict}")
    print(
        "\n  Even full support would not explain the whole B3 gap: NSE's 25.10%\n"
        "  comes from signal, universe, concentration and weighting together,\n"
        "  and this test moves one of the four."
    )


def main() -> int:
    """Build the universe once, measure both signals on it, score the prediction."""
    cfg = H1Config()
    print(f"reconstructing {NIFTY_100.describe()}...")
    try:
        universe = reconstruct(NIFTY_100, stop_at=cfg.start)
    except ReconstructionError as exc:
        print(f"\n  CANNOT BUILD THE UNIVERSE\n    {exc}")
        return 1
    print(f"  {universe.describe()}")
    if universe.history.unapplied:
        print("  REFUSING: membership could not be reconstructed cleanly.")
        return 1

    print("building back-adjusted bars...")
    built = build_bars(symbols=universe.tickers, start=cfg.start, end=cfg.end)
    print(f"  {built.describe()}")

    merged: dict[str, dict[date, Bar]] = {}
    for ticker, series in built.bars.items():
        merged.setdefault(universe.canonical.get(ticker, ticker), {}).update(series)

    sessions = sorted(built.sessions)
    rebalances = month_start_sessions(sessions[WARMUP:])
    tri = load_tri(TRI)

    # Both signals, same bars, same dates, same everything downstream. Spelled
    # out twice rather than unpacked from a shared tuple: a heterogeneous tuple
    # splatted into positional arguments is opaque to the type checker, and the
    # only way to keep it was a blanket ignore that would have hidden a genuine
    # mismatch just as readily.
    print(f"\nmeasuring both signals over {len(rebalances)} rebalance dates...")
    raw = run_h1(
        merged,
        sessions,
        universe.history,
        tri,
        rebalances,
        config=cfg,
        ranker=rank_by_momentum,
    )
    adjusted = run_h1(
        merged,
        sessions,
        universe.history,
        tri,
        rebalances,
        config=cfg,
        ranker=rank_by_risk_adjusted_momentum,
    )

    # The raw signal is re-measured here rather than quoted, so a drift between
    # this run and trial #3 would show up rather than hide. They must agree.
    drift = abs(raw.mean_ic - RAW_12_1_IC)
    if drift > 0.0005:
        print(
            f"\n  WARNING: the raw 12-1 IC re-measures at {raw.mean_ic:+.4f}, "
            f"against trial #3's {RAW_12_1_IC:+.4f}. Something changed in the "
            f"pipeline between the two runs, and the comparison below is not "
            f"like-for-like until that is explained."
        )
    report(raw, adjusted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
