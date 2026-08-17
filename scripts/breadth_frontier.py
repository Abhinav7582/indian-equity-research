#!/usr/bin/env python3
"""The breadth frontier: what a full turnover costs, by number of holdings.

Usage
-----
    uv run python scripts/breadth_frontier.py
    uv run python scripts/breadth_frontier.py --capital 300000 1000000

Writes ``docs/breadth_frontier.md``.

Why this spends no trial budget
-------------------------------
This reads **no returns**. It is cost arithmetic on a declared turnover
schedule, using the validated cost model, and its output is the same whatever
the market did. No configuration is selected on performance, so no selection
occurs and the Deflated Sharpe denominator is untouched.

That distinction is the whole point of running it first. Choosing breadth by
*which N backtested best* is exactly the selection the statistical gates exist
to catch. Choosing breadth by *what it costs to trade* is not, and it can be
settled before any hypothesis is tested.

What it shows
-------------
Two costs at these position sizes are **fixed in rupees**, not proportional:

* the DP charge, ₹23.60 per **sell order**;
* brokerage, which hits its ₹5 floor below a ₹5,000 order.

Both therefore scale with the *number* of positions and orders, and are diluted
only by capital. That is the entire small-account problem, and it is arithmetic
rather than opinion.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.costs import Side, charges_for

OUT = Path("docs/breadth_frontier.md")
BREADTHS = (10, 15, 20, 30, 50, 100)
ORDER_SPLITS = (1.0, 1.5, 3.0)
AS_OF = dt.date(2026, 8, 18)


def round_trip(position: float, sell_orders: float) -> dict[str, float]:
    """Every charge on buying and then selling one position, in rupees."""
    buy = charges_for(position, Side.BUY, AS_OF)
    sell = charges_for(position, Side.SELL, AS_OF, sell_orders=sell_orders)
    dp = sell.dp_charge * (1.0 + sell.gst_rate)
    brokerage = (buy.brokerage + sell.brokerage) * (1.0 + buy.gst_rate)
    return {
        "dp": dp,
        "brokerage": brokerage,
        "statutory": buy.total + sell.total - dp - brokerage,
        "total": buy.total + sell.total,
    }


def main() -> int:
    """Build the frontier and write it out."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital", type=float, nargs="+", default=[300_000.0])
    args = parser.parse_args()

    lines = [
        "# The breadth frontier",
        "",
        f"Generated {dt.datetime.now(tz=dt.UTC).date()} by `scripts/breadth_frontier.py`,",
        "using the cost model validated against real contract notes",
        "(`docs/cost_model_validation.md`).",
        "",
        "**No returns are read.** This is cost arithmetic, so it spends no trial",
        "budget and can settle breadth before any hypothesis is tested. Choosing N",
        "by which value backtested best would be selection; choosing it by what",
        "trading costs is not.",
        "",
        "Every figure is the cost of **one full turnover** — buying and selling",
        "each position once — as a percentage of capital.",
        "",
    ]

    for capital in args.capital:
        print(f"\n{'=' * 78}\nCapital Rs {capital:,.0f}\n{'=' * 78}")
        header = (
            f"{'names':>6}{'position':>11}{'DP':>9}{'brokerage':>11}{'statutory':>11}{'TOTAL':>9}"
        )
        print(header)
        lines += [
            f"## Capital ₹{capital:,.0f}",
            "",
            "One sell order per exit — the optimistic case.",
            "",
            "| names | position | DP | brokerage | statutory | **total** |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
        for n in BREADTHS:
            position = capital / n
            parts = round_trip(position, 1.0)
            frac = {k: v * n / capital for k, v in parts.items()}
            print(
                f"{n:>6}{position:>11,.0f}{frac['dp']:>9.3%}{frac['brokerage']:>11.3%}"
                f"{frac['statutory']:>11.3%}{frac['total']:>9.3%}"
            )
            lines.append(
                f"| {n} | ₹{position:,.0f} | {frac['dp']:.3%} | {frac['brokerage']:.3%} "
                f"| {frac['statutory']:.3%} | **{frac['total']:.3%}** |"
            )

        lines += [
            "",
            "Total cost of one full turnover, by orders per exit:",
            "",
            "| names | 1 order | 1.5 orders | 3 orders |",
            "|---:|---:|---:|---:|",
        ]
        print(f"\n{'names':>6}{'1 order':>11}{'1.5 orders':>13}{'3 orders':>12}   (total cost)")
        for n in BREADTHS:
            position = capital / n
            totals = [round_trip(position, k)["total"] * n / capital for k in ORDER_SPLITS]
            print(f"{n:>6}{totals[0]:>11.3%}{totals[1]:>13.3%}{totals[2]:>12.3%}")
            lines.append(f"| {n} | {totals[0]:.3%} | {totals[1]:.3%} | {totals[2]:.3%} |")
        lines.append("")

        # The capital at which each breadth becomes affordable.
        lines += [
            "### Capital needed to keep one full turnover under 0.50%",
            "",
            "| names | required capital |",
            "|---:|---:|",
        ]
        for n in BREADTHS:
            low, high = 50_000.0, 100_000_000.0
            for _ in range(60):
                mid = (low + high) / 2
                cost = round_trip(mid / n, 1.0)["total"] * n / mid
                low, high = (mid, high) if cost > 0.005 else (low, mid)
            lines.append(f"| {n} | ₹{high:,.0f} |")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwritten to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
