#!/usr/bin/env python3
"""Measure the balance sheet against the declared target — Phase 5 component 2.

Usage
-----
    uv run python scripts/check_drift.py \
        --holding "Equity=1698134" \
        --holding "Gold / precious metals=1648612" \
        --holding "Debt + cash=3191275" \
        --holding "US stocks + crypto=2251"

Bucket names must match ``configs/target_allocation.yaml`` exactly. A name the
policy does not declare is refused rather than silently creating a bucket with
a 0% target while the real one reads empty.

Where the numbers come from
---------------------------
The **target** comes from ``configs/target_allocation.yaml``, which is committed
so that every change to it is visible and dated. A target editable without trace
after seeing the drift is not a commitment.

The **current values** come from the command line. This script does not read
``data/reference/portfolio.md`` and must not be changed to — that file is
git-ignored, and the boundary written at the top of it is the reason.

What this prints, and what it refuses to
-----------------------------------------
A gap, the rupees that would close it, and what closing it would cost. It does
**not** say whether to close it. A band breach is arithmetic; acting on one is a
decision, and the decision belongs to whoever owns the money.

Trial accounting
----------------
**None.** This reads no returns and fits nothing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.drift import (
    DriftError,
    DriftReport,
    load_policy,
    measure_drift,
)

POLICY = Path("configs/target_allocation.yaml")
RULE = "-" * 78


def as_holding(text: str) -> tuple[str, float]:
    """Parse ``Name=value``, keeping any ``=`` inside the name intact."""
    name, _, value = text.rpartition("=")
    if not name:
        raise argparse.ArgumentTypeError(f"expected Name=value, got {text!r}")
    try:
        return name.strip(), float(value.replace(",", "").strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from exc


def show(report: DriftReport) -> None:
    """Print every bucket against the policy."""
    print(f"\n{'bucket':<26}{'value':>14}{'now':>8}{'target':>8}{'gap':>8}{'band':>8}  state")
    print(RULE)
    for bucket in sorted(report.buckets, key=lambda b: -b.value):
        state = "DRIFTED" if bucket.is_drifted else "ok"
        print(
            f"{bucket.name:<26}{bucket.value:>14,.0f}"
            f"{bucket.current_pct:>7.1f}%{bucket.target_pct:>7.1f}%"
            f"{bucket.gap_pp:>+7.1f}{bucket.band_pp:>7.2f}  {state}"
        )
    print(RULE)
    print(f"{'total':<26}{report.total:>14,.0f}")


def show_corrections(report: DriftReport) -> None:
    """Print the trade each drifted bucket would need, and what it costs."""
    if not report.drifted:
        print("\n  Every bucket is inside its band. Nothing to report.")
        return

    print(f"\nTO CLOSE EACH GAP   ({len(report.drifted)} drifted)")
    print(f"\n  {'bucket':<26}{'trade':>14}{'charges':>11}{'as % moved':>12}")
    for bucket in report.drifted:
        action = "sell" if bucket.trade_rupees < 0 else "buy"
        charges = bucket.trade_charges or 0.0
        print(
            f"  {bucket.name:<26}{action:>5} {abs(bucket.trade_rupees):>8,.0f}"
            f"{charges:>11,.0f}{bucket.cost_fraction:>11.2%}"
        )
    print(f"\n  {'total turnover':<26}{report.total_turnover:>14,.0f}")

    skipped = set(report.drifted) - set(report.worth_making)
    if skipped:
        print("\n  BELOW THE DECLARED ECONOMIC FLOOR:")
        for bucket in sorted(skipped, key=lambda b: b.name):
            reason = (
                f"trade of {abs(bucket.trade_rupees):,.0f} is under the "
                f"{report.policy.min_trade_rupees:,.0f} minimum"
                if abs(bucket.trade_rupees) < report.policy.min_trade_rupees
                else f"friction {bucket.cost_fraction:.2%} exceeds the "
                f"{report.policy.max_cost_fraction:.2%} budget"
            )
            print(f"    {bucket.name}: {reason}")
        print(
            "    These buckets are genuinely drifted. The arithmetic says a\n"
            "    trade is not the cheapest way to fix them; a contribution is."
        )

    print(
        "\n  WHAT IS NOT MODELLED HERE: capital gains tax. Charges above are\n"
        "  transaction costs only. On a short-term lot the tax is 20% of the\n"
        "  gain and will dwarf every figure in the charges column — run\n"
        "  scripts/price_trade.py on any sale before treating it as priced."
    )


def main() -> int:
    """Measure the declared policy against holdings given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--holding",
        type=as_holding,
        action="append",
        required=True,
        metavar="NAME=VALUE",
        help="Repeat once per bucket. Names must match the policy exactly.",
    )
    parser.add_argument("--policy", type=Path, default=POLICY)
    parser.add_argument("--on", default=None, help="Measurement date, YYYY-MM-DD.")
    args = parser.parse_args()

    on = date.fromisoformat(args.on) if args.on else date.today()  # noqa: DTZ011

    try:
        policy = load_policy(args.policy)
        report = measure_drift(policy, dict(args.holding), on)
    except DriftError as exc:
        print(f"\n  REFUSED\n    {exc}\n")
        return 1

    print(f"\nDRIFT AGAINST THE DECLARED TARGET   {on}")
    print(f"  {policy.describe()}")
    show(report)
    show_corrections(report)
    print(
        f"\n{RULE}\n"
        "  This states a gap against a policy you declared. It does not say\n"
        "  whether to close it, and it names no trade you should make.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
