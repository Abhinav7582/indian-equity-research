#!/usr/bin/env python3
"""Price a contemplated trade before making it — Phase 5 component 3.

Usage
-----
    # What does selling this cost me right now?
    uv run python scripts/price_trade.py --quantity 1000 --buy-price 400 \
        --bought 2024-06-03 --sell-price 500

    # And what if I switch it into something else?
    uv run python scripts/price_trade.py --quantity 1000 --buy-price 400 \
        --bought 2024-06-03 --sell-price 500 --into "MIDCAP INDEX FUND"

    # I have already realised Rs 80,000 of long-term gain this year
    uv run python scripts/price_trade.py ... --ltcg-used 80000

What this does, and what it refuses to do
------------------------------------------
It prices a trade **you have described**. It does not choose the trade, compare
alternatives, name anything to buy or sell, or say whether the trade is wise.
The break-even it prints is arithmetic — the move required to recover the
friction — and is **not** a claim that the move will happen.

Nothing here reads the portfolio file. Every figure comes from the arguments
given on the command line, so the holdings stay where they are.

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

from indian_equity_research.backtest.pretrade import (
    Lot,
    PreTradeError,
    SaleConsequence,
    price_sale,
    price_switch,
    price_waiting,
)

RULE = "-" * 72


def as_date(text: str) -> date:
    """Parse ``YYYY-MM-DD``, refusing anything else.

    ``date.fromisoformat`` rather than ``strptime``: a trade date is a calendar
    date, not an instant, and parsing it through a datetime would invite a
    timezone that has no meaning here and can only shift the day.
    """
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}") from exc


def show_sale(sale: SaleConsequence) -> None:
    """Print the exit leg, itemised."""
    term = "LONG-TERM (s.112A)" if sale.is_long_term else "SHORT-TERM (s.111A)"
    print(f"\nTHE SALE   {sale.sell_on}   {sale.financial_year}")
    print(f"  {'gross proceeds':<28}{sale.gross_proceeds:>14,.2f}")
    for name, amount in sale.charges.itemised().items():
        if amount:
            print(f"    {name:<26}{-amount:>14,.2f}")
    print(f"  {'net proceeds':<28}{sale.net_proceeds:>14,.2f}")
    print(f"  {'cost of the lot':<28}{-sale.lot.cost:>14,.2f}")
    print(f"  {'taxable gain':<28}{sale.gain:>+14,.2f}")
    print(f"\n  held {sale.holding_days} days -> {term}")
    if sale.is_long_term:
        print(f"  {'exemption left this year':<28}{sale.exemption_left:>14,.2f}")
    print(f"  {'tax':<28}{-sale.tax:>14,.2f}")
    print(f"  {'LEFT TO REDEPLOY':<28}{sale.proceeds_after_tax:>14,.2f}")
    print(
        f"  {'total friction':<28}{sale.total_friction:>14,.2f}"
        f"   ({sale.total_friction / sale.gross_proceeds:.2%} of the position)"
    )


def main() -> int:
    """Price one trade as described on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="THE HOLDING")
    parser.add_argument("--quantity", type=float, required=True)
    parser.add_argument("--buy-price", type=float, required=True)
    parser.add_argument("--bought", type=as_date, required=True)
    parser.add_argument("--sell-price", type=float, required=True)
    parser.add_argument("--on", type=as_date, default=None, help="Sale date. Defaults to today.")
    parser.add_argument("--into", default=None, help="Price a switch into this.")
    parser.add_argument("--sell-orders", type=float, default=1.0)
    parser.add_argument("--ltcg-used", type=float, default=0.0)
    parser.add_argument("--other-gains", type=float, default=0.0)
    args = parser.parse_args()

    sell_on = args.on or date.today()  # noqa: DTZ011 - a trade date is a local calendar date

    try:
        lot = Lot(
            name=args.name,
            quantity=args.quantity,
            buy_price=args.buy_price,
            bought_on=args.bought,
        )
        sale = price_sale(
            lot,
            args.sell_price,
            sell_on,
            sell_orders=args.sell_orders,
            ltcg_already_used=args.ltcg_used,
            other_gains_this_year=args.other_gains,
        )
    except PreTradeError as exc:
        print(f"\n  CANNOT PRICE THIS\n    {exc}")
        return 1

    print(f"\nPRE-TRADE CALCULATOR   {lot.name}")
    print(f"  {lot.quantity:,.0f} units bought {lot.bought_on} at {lot.buy_price:,.2f}")
    print(f"  contemplated sale at {args.sell_price:,.2f}, {args.sell_orders:g} sell order(s)")
    print(RULE)
    show_sale(sale)

    if not sale.is_long_term:
        print(RULE)
        waiting = price_waiting(
            lot,
            args.sell_price,
            sell_on,
            sell_orders=args.sell_orders,
            ltcg_already_used=args.ltcg_used,
            other_gains_this_year=args.other_gains,
        )
        print(f"\nTHE LONG-TERM CLIFF   {sale.days_to_long_term} days away")
        print(f"  first long-term date {waiting.on_cliff.sell_on}")
        print(f"  {'tax if sold now':<28}{waiting.now.tax:>14,.2f}")
        print(f"  {'tax if sold then':<28}{waiting.on_cliff.tax:>14,.2f}")
        print(f"  {'saving, at an unchanged price':<28}{waiting.saves:>14,.2f}")
        if waiting.crosses_financial_year:
            print("  the wait also crosses 1 April, so a fresh exemption applies")
        print(
            f"\n  AND THE COUNTERWEIGHT: a {waiting.break_even_fall:.2%} fall while "
            f"waiting\n  cancels the saving exactly. The tax table is certain; the "
            f"price is not."
        )

    if args.into:
        print(RULE)
        switch = price_switch(
            lot,
            args.sell_price,
            sell_on,
            args.into,
            sell_orders=args.sell_orders,
            ltcg_already_used=args.ltcg_used,
            other_gains_this_year=args.other_gains,
        )
        print(f"\nTHE SWITCH   into {args.into}")
        print(f"  {'left after the sale':<28}{switch.sale.proceeds_after_tax:>14,.2f}")
        print(f"  {'charges on the buy':<28}{-switch.buy_charges.total:>14,.2f}")
        print(f"  {'ACTUALLY DEPLOYED':<28}{switch.deployed:>14,.2f}")
        print(
            f"  {'friction, both legs':<28}{switch.total_friction:>14,.2f}"
            f"   ({switch.friction_fraction:.2%})"
        )
        print(
            f"\n  BREAK-EVEN: {args.into} must gain "
            f"{switch.breakeven_move:+.2%}\n  before this switch has recovered what it "
            f"cost. That is arithmetic,\n  not a forecast that it will."
        )

    print(RULE)
    print(
        "\n  This prices a trade you described. It does not recommend one, and\n"
        "  no figure above is a prediction. Rates are modelled as documented in\n"
        "  backtest/costs.py and backtest/tax.py; surcharge and cess are not\n"
        "  modelled, and losses are not carried forward.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
