#!/usr/bin/env python3
"""Where new money should go — Phase 5, the contribution router.

Usage
-----
    uv run python scripts/plan_contribution.py --amount 8500 \
        --holding "Equity=1698134" \
        --holding "Gold / precious metals=1648612" \
        --holding "Debt + cash=3191275" \
        --holding "US stocks + crypto=2251"

    # a bonus, and what a year of monthly SIPs would do
    uv run python scripts/plan_contribution.py --amount 150000 --horizon 0 ...

Why adding beats rebalancing
----------------------------
A contribution moves the allocation **without selling anything**, so it realises
no capital gain and pays no exit charge. `scripts/price_trade.py` measured the
alternative: switching a short-term holding costs **4.21%** of the position,
almost all of it tax. Steering by contribution costs the brokerage on a buy.

The catch, stated plainly: it is **slow**. This prints how many contributions
each gap needs, so the pace is visible rather than assumed.

What this does not do
---------------------
It states where money would go against a target **you declared**. It does not
say to send it, does not name a fund or a security, and does not forecast
anything. The buckets and weights come from `configs/target_allocation.yaml`.

Trial accounting
----------------
**None.** Reads no returns, fits nothing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.drift import (
    ContributionPlan,
    DriftError,
    load_policy,
    measure_drift,
    route_contribution,
)

POLICY = Path("configs/target_allocation.yaml")
RULE = "-" * 76


def as_holding(text: str) -> tuple[str, float]:
    """Parse ``Name=value``, keeping any ``=`` inside the name."""
    name, _, value = text.rpartition("=")
    if not name:
        raise argparse.ArgumentTypeError(f"expected Name=value, got {text!r}")
    try:
        return name.strip(), float(value.replace(",", "").strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from exc


def show(plan: ContributionPlan, per_period: float, label: str) -> None:
    """Print the split and what it does to each weight."""
    print(f"\nROUTING {plan.amount:,.0f}   ({plan.total_before:,.0f} -> {plan.total_after:,.0f})")
    print(f"\n  {'bucket':<26}{'gets':>12}{'now':>8}{'after':>8}{'target':>8}{'gap left':>10}")
    print(f"  {RULE[:72]}")
    for share in sorted(plan.shares, key=lambda s: -s.amount):
        left = share.target_pct - share.after_pct
        print(
            f"  {share.name:<26}{share.amount:>12,.0f}"
            f"{share.before_pct:>7.1f}%{share.after_pct:>7.1f}%{share.target_pct:>7.1f}%"
            f"{left:>+9.1f}pp"
        )
    print(f"  {RULE[:72]}")
    print(f"  {'total':<26}{sum(s.amount for s in plan.shares):>12,.0f}")

    if not plan.receiving:
        print("\n  Nothing is below target. Every bucket keeps its weight.")
        return

    print(f"\n  HOW LONG EACH GAP TAKES at {per_period:,.0f} {label}")
    for share in plan.receiving:
        n = share.months_to_target(per_period)
        if n <= 0:
            continue
        # The conditional applies to the years suffix only. Written as its own
        # variable because folding it into the f-string made the `else` swallow
        # the whole line, which is exactly what happened the first time.
        years = f"   ({n / 12:.1f} years)" if label.startswith("month") else ""
        print(
            f"    {share.name:<26}{share.gap_rupees_before:>12,.0f} short"
            f"   ~{n:>5.1f} {label}{years}"
        )
    print(
        "\n    Returns are ignored in that estimate. A bucket that outgrows the\n"
        "    rest closes its own gap sooner; one that falls takes longer. It is\n"
        "    an order of magnitude, not a schedule."
    )


def main() -> int:
    """Route one contribution against the declared policy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument(
        "--holding", type=as_holding, action="append", required=True, metavar="NAME=VALUE"
    )
    parser.add_argument("--policy", type=Path, default=POLICY)
    parser.add_argument("--on", default=None, help="Date, YYYY-MM-DD.")
    parser.add_argument(
        "--per-period",
        type=float,
        default=None,
        help="Recurring amount for the pace estimate. Defaults to --amount.",
    )
    parser.add_argument("--label", default="months", help="Unit for the pace estimate.")
    args = parser.parse_args()

    on = date.fromisoformat(args.on) if args.on else date.today()  # noqa: DTZ011
    try:
        policy = load_policy(args.policy)
        report = measure_drift(policy, dict(args.holding), on)
        plan = route_contribution(report, args.amount, on=on)
    except DriftError as exc:
        print(f"\n  REFUSED\n    {exc}\n")
        return 1

    print(f"\nCONTRIBUTION PLAN   {on}")
    print(f"  {policy.describe()}")
    show(plan, args.per_period or args.amount, args.label)
    print(
        f"\n{RULE}\n"
        "  Nothing is sold, so no capital gains tax and no exit charges — the\n"
        "  switching alternative costs 4.21% of a short-term position.\n"
        "  This states where money would go against a target you declared. It\n"
        "  does not say to send it, and it names no fund or security.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
