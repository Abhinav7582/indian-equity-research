#!/usr/bin/env python3
"""Amendment A13 — test a claim about market state against the archive.

Usage
-----
    uv run python scripts/check_belief.py
    uv run python scripts/check_belief.py --subject niftysmallcap250_tri \
        --comparator nifty100_tri --horizon 12

What this prints, and what it refuses to print
----------------------------------------------
It prints a distribution and a percentile. It does **not** print an allocation,
a weight, a target or a recommendation, and A13 rule 1 forbids adding one. The
question it answers is *"is this unusual?"* — not *"will it continue?"*

Why the comparator matters more than it looks
---------------------------------------------
The natural comparator for a mid-cap claim is the **Nifty 100**, which is
large-cap. The Nifty 200 is *not* a substitute: it contains the Nifty Midcap 100,
so measuring mid-caps against it compares a set against a set that includes it
and **understates the gap**. The default comparator is therefore the Nifty 100,
and when its archive does not span the requested window the check **refuses**
rather than quietly answering a shorter question (A13 rule 5).

Trial accounting
----------------
**None.** A13 rule 2: belief checks select nothing and fit nothing, so they
cannot inflate a Deflated Sharpe denominator that exists to count selection.
This spends no trial-register slot. If a check is used to choose an allocation,
that is a decision rather than a description, and it is the owner's to make.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.research.beliefs import (
    BeliefCheck,
    BeliefError,
    Series,
    check_belief,
    load_index_series,
)

INDICES = Path("data/raw/indices")

# The claim as it was actually said, recorded verbatim. A tidied restatement
# would drift towards whatever the data turned out to support.
DEFAULT_CLAIM = (
    "In the past 1 yr Nifty Midcap 150 and Nifty smallcap 250 has beaten my "
    "portfolio by a little over 1-2% and slightly more in Nifty smallcap 250 "
    "if you take from the time that I started investing."
)

HORIZONS = (3, 6, 12, 36, 60)


def report(check: BeliefCheck) -> None:
    """Print one horizon's distribution without interpreting it."""
    print(f"\n  {check.horizon_months} MONTHS   {check.first_session} to {check.last_session}")
    print(
        f"    windows {check.observations:,}"
        f"   independent ~{check.independent_observations:.0f}"
        f"   (adjacent windows share all but a few days of their data)"
    )
    print(
        f"    latest   {check.latest.relative:+7.1%}"
        f"   -> {check.percentile:3.0f}th percentile"
        f"   [{check.latest.start} to {check.latest.end}]"
    )
    print(
        f"    beats    {check.hit_rate:6.0%} of windows"
        f"   avg win {check.mean_win:+.1%}   avg loss {check.mean_loss:+.1%}"
    )
    values = check.relatives
    print(
        f"    spread   worst {values[0]:+.1%}"
        f"   p10 {check.quantile(0.10):+.1%}"
        f"   median {check.quantile(0.50):+.1%}"
        f"   p90 {check.quantile(0.90):+.1%}"
        f"   best {values[-1]:+.1%}"
    )


def drawdown(series: Series) -> tuple[float, str, str]:
    """Worst peak-to-trough fall in the level path, and when it happened.

    Reported because a hit rate says how often the subject wins and nothing at
    all about what has to be sat through in between.
    """
    peak = float("-inf")
    worst, peak_at, trough_at, running_peak = 0.0, None, None, None
    for day in series.sessions:
        level = series.levels[day]
        if level > peak:
            peak, running_peak = level, day
        fall = level / peak - 1.0
        if fall < worst:
            worst, peak_at, trough_at = fall, running_peak, day
    return worst, str(peak_at), str(trough_at)


def main() -> int:
    """Check one claim across every declared horizon."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="niftymidcap150_tri")
    parser.add_argument("--comparator", default="nifty100_tri")
    parser.add_argument("--claim", default=DEFAULT_CLAIM)
    parser.add_argument("--horizon", type=int, default=None, help="One horizon, in months.")
    args = parser.parse_args()

    try:
        subject = load_index_series(INDICES / args.subject)
        comparator = load_index_series(INDICES / args.comparator)
    except BeliefError as exc:
        print(f"\n  CANNOT LOAD\n    {exc}")
        return 1

    print("\nBELIEF CHECK  (Amendment A13 — describes, does not recommend)")
    print(f'\n  claim: "{args.claim}"')
    print(f"\n  subject     {subject.describe()}")
    print(f"  comparator  {comparator.describe()}")

    horizons = (args.horizon,) if args.horizon else HORIZONS
    checks: list[BeliefCheck] = []
    for months in horizons:
        try:
            checks.append(check_belief(args.claim, subject, comparator, horizon_months=months))
        except BeliefError as exc:
            print(f"\n  REFUSED at {months} months\n    {exc}")
            return 1

    for check in checks:
        report(check)

    print("\n  WORST PEAK-TO-TROUGH FALL, level path")
    for series in (subject, comparator):
        worst, peak_at, trough_at = drawdown(series)
        print(f"    {series.name:<22}{worst:>8.1%}   {peak_at} -> {trough_at}")

    print(
        "\n  A13 binds this output. It says where the present sits in its own\n"
        "  history. It does not say what happens next, and it names no weight,\n"
        "  target or amount. An encouraging reading requires confirmation on a\n"
        "  non-overlapping second window before it may inform any decision."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
