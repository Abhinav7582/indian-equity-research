"""What a contemplated trade will cost, computed before it is made.

Phase 5 component 3. The cost model already prices charges to the paisa and the
tax module already matches lots FIFO; neither had a front door for the question
an owner actually asks, which is *"if I do this, what happens?"*

What this is not
----------------
It computes the consequences of a trade **that has been stated**. It does not
choose the trade, rank alternatives, name a security, or say whether the trade
is a good idea. A break-even figure is arithmetic — the move required to recover
the friction — and is **not** a forecast that the move will happen.

The four things a stated trade does that are easy to miss
---------------------------------------------------------
**1. The long-term cliff is a step, not a slope.** A lot sold on day 365 is taxed
at 20%; the same lot sold on day 366 is taxed at 12.5% with the first ₹1,25,000
of the year free. On a ₹1,00,000 gain that is ₹20,000 against nothing at all.
Nothing about the position changes overnight — only the section of the Act that
applies to it. :attr:`SaleConsequence.days_to_long_term` reports the distance to
that step and :func:`price_waiting` prices it, **at an unchanged price** — the
saving it reports is the tax difference alone, and holding for another month
puts the position at a month more of market risk that no tax table can offset.

**2. The ₹1,25,000 exemption is annual and it is consumed.** Two long-term sales
in one financial year do not each get it. The second is taxed on whatever the
first left, so the marginal rate on an identical gain depends entirely on what
has already been realised since April.

**3. The financial year turns on 1 April, not 1 January.** A sale deferred from
March to April lands against a *fresh* exemption. That interacts with the cliff:
waiting can move a gain across both boundaries at once, or across only one.

**4. Friction is paid on both legs and compounds with turnover.** Selling to buy
something else pays charges twice and tax once, and the replacement must earn
all of it back before the switch has broken even.

A realised loss
---------------
Selling below cost realises a loss, which nets against other gains in the same
financial year and reduces tax. That is reported as a negative tax figure when
there are gains for it to offset. Losses are **not** carried forward here, which
matches :mod:`indian_equity_research.backtest.tax` and overstates tax in a year
that ends in aggregate loss — conservative, in the only direction a cost model
should ever be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from indian_equity_research.backtest.costs import ChargeBreakdown, Side, charges_for
from indian_equity_research.backtest.tax import (
    LONG_TERM_DAYS,
    LTCG_EXEMPTION,
    LTCG_RATE,
    STCG_RATE,
    financial_year,
)

__all__ = [
    "Lot",
    "PreTradeError",
    "SaleConsequence",
    "SwitchConsequence",
    "WaitComparison",
    "next_financial_year_start",
    "price_sale",
    "price_switch",
    "price_waiting",
]


class PreTradeError(ValueError):
    """A contemplated trade could not be priced as stated."""


def next_financial_year_start(when: date) -> date:
    """The 1 April on or after ``when``.

    The exemption resets here, so a sale one day either side of it is charged
    against a different year's remaining allowance.
    """
    return date(when.year, 4, 1) if when.month < 4 else date(when.year + 1, 4, 1)


@dataclass(frozen=True, slots=True)
class Lot:
    """One purchase of one holding, as the Income Tax Act sees it.

    Attributes:
        name: What is held. Free text — this module never interprets it, and
            never looks anything up from it.
        quantity: Units held.
        buy_price: Price per unit paid, inclusive of the charges on that buy if
            they are known. Excluding them overstates the gain and therefore
            the tax, which is the conservative direction.
        bought_on: Purchase date. Decides the section that applies.
    """

    name: str
    quantity: float
    buy_price: float
    bought_on: date

    def __post_init__(self) -> None:
        """Reject a lot that cannot describe a real holding."""
        if self.quantity <= 0:
            raise PreTradeError(f"quantity must be positive, got {self.quantity}")
        if self.buy_price < 0:
            raise PreTradeError(f"buy_price must not be negative, got {self.buy_price}")

    @property
    def cost(self) -> float:
        """Total rupees paid for the lot."""
        return self.quantity * self.buy_price

    def held_days(self, on: date) -> int:
        """Calendar days held as at ``on``."""
        return (on - self.bought_on).days


@dataclass(frozen=True, slots=True)
class SaleConsequence:
    """What selling one lot on one date does, itemised.

    Attributes:
        lot: What is being sold.
        sell_on: Date of the contemplated sale.
        sell_price: Price per unit assumed.
        charges: Every transaction charge on the sell leg.
        ltcg_already_used: Long-term gain already realised this financial year,
            which decides how much exemption is left for this one.
        other_gains_this_year: Gains available for a loss to offset. Only
            consulted when this sale realises a loss.
    """

    lot: Lot
    sell_on: date
    sell_price: float
    charges: ChargeBreakdown
    ltcg_already_used: float
    other_gains_this_year: float

    @property
    def gross_proceeds(self) -> float:
        """Units times price, before any charge."""
        return self.lot.quantity * self.sell_price

    @property
    def net_proceeds(self) -> float:
        """Cash received after charges, before tax."""
        return self.gross_proceeds - self.charges.total

    @property
    def gain(self) -> float:
        """Taxable gain: proceeds net of sell charges, less cost."""
        return self.net_proceeds - self.lot.cost

    @property
    def holding_days(self) -> int:
        """Days the lot will have been held on the sale date."""
        return self.lot.held_days(self.sell_on)

    @property
    def is_long_term(self) -> bool:
        """Whether s.112A applies. Strictly more than 365 days, as in the Act."""
        return self.holding_days > LONG_TERM_DAYS

    @property
    def days_to_long_term(self) -> int:
        """Days until the lot turns long-term. Zero once it already has.

        The single most valuable number here: it is the distance to a step
        change in the rate, and it is invisible on any statement.
        """
        return max(0, LONG_TERM_DAYS + 1 - self.holding_days)

    @property
    def long_term_on(self) -> date:
        """The first date this lot can be sold long-term."""
        return self.lot.bought_on + timedelta(days=LONG_TERM_DAYS + 1)

    @property
    def exemption_left(self) -> float:
        """Unused ₹1,25,000 allowance in the financial year of the sale."""
        return max(0.0, LTCG_EXEMPTION - self.ltcg_already_used)

    @property
    def tax(self) -> float:
        """Tax on this sale, given what the year has already realised.

        Negative when the sale realises a loss and there are gains for it to
        offset — the loss reduces the year's bill rather than creating a refund
        on its own.
        """
        if self.gain <= 0:
            offset = min(-self.gain, max(0.0, self.other_gains_this_year))
            rate = LTCG_RATE if self.is_long_term else STCG_RATE
            return -offset * rate
        if not self.is_long_term:
            return self.gain * STCG_RATE
        return max(0.0, self.gain - self.exemption_left) * LTCG_RATE

    @property
    def proceeds_after_tax(self) -> float:
        """What is actually left to redeploy."""
        return self.net_proceeds - self.tax

    @property
    def total_friction(self) -> float:
        """Charges plus tax — everything the sale costs."""
        return self.charges.total + self.tax

    @property
    def financial_year(self) -> str:
        """The April-March year this sale falls in."""
        return financial_year(self.sell_on)

    def describe(self) -> str:
        """One line stating the outcome without judging it."""
        term = "long-term" if self.is_long_term else "SHORT-TERM"
        return (
            f"{self.lot.name}: sell {self.gross_proceeds:,.0f}, "
            f"gain {self.gain:+,.0f} ({term}, {self.holding_days}d), "
            f"charges {self.charges.total:,.0f}, tax {self.tax:,.0f}, "
            f"net {self.proceeds_after_tax:,.0f}"
        )


def price_sale(
    lot: Lot,
    sell_price: float,
    sell_on: date,
    *,
    sell_orders: float = 1.0,
    ltcg_already_used: float = 0.0,
    other_gains_this_year: float = 0.0,
) -> SaleConsequence:
    """Price one contemplated sale.

    Args:
        lot: The holding being sold, in full.
        sell_price: Price per unit assumed. An assumption, not a prediction.
        sell_on: Contemplated sale date. Selects both the charge schedule and
            the tax section.
        sell_orders: How many orders the exit takes. The DP charge is levied
            **per order**, so an exit worked in three slices pays it three
            times. Defaults to 1, the optimistic case.
        ltcg_already_used: Long-term gain already realised this financial year.
        other_gains_this_year: Gains a realised loss could offset.

    Returns:
        The itemised consequence.

    Raises:
        PreTradeError: if the price is negative, or the sale predates the
            purchase — which would produce a negative holding period and a
            confidently wrong tax rate.
    """
    if sell_price < 0:
        raise PreTradeError(f"sell_price must not be negative, got {sell_price}")
    if sell_on < lot.bought_on:
        raise PreTradeError(
            f"cannot sell {lot.name} on {sell_on}, before it was bought on "
            f"{lot.bought_on}. A negative holding period would be read as "
            f"short-term and taxed at {STCG_RATE:.0%} without complaint."
        )

    charges = charges_for(lot.quantity * sell_price, Side.SELL, sell_on, sell_orders=sell_orders)
    return SaleConsequence(
        lot=lot,
        sell_on=sell_on,
        sell_price=sell_price,
        charges=charges,
        ltcg_already_used=ltcg_already_used,
        other_gains_this_year=other_gains_this_year,
    )


@dataclass(frozen=True, slots=True)
class WaitComparison:
    """Selling now against selling on the first long-term date.

    Both legs are priced **at the same price**. That is the point and also the
    limitation: it isolates the tax difference by assuming the market does
    nothing, which it will not. The saving is real; it is simply not free.
    """

    now: SaleConsequence
    on_cliff: SaleConsequence

    @property
    def days(self) -> int:
        """Days that would have to be waited."""
        return (self.on_cliff.sell_on - self.now.sell_on).days

    @property
    def saves(self) -> float:
        """Tax avoided by waiting, at an unchanged price."""
        return self.now.tax - self.on_cliff.tax

    @property
    def saves_fraction(self) -> float:
        """The saving as a fraction of the position."""
        gross = self.now.gross_proceeds
        return self.saves / gross if gross > 0 else 0.0

    @property
    def crosses_financial_year(self) -> bool:
        """Whether waiting also moves the gain into a fresh exemption year.

        Reported because the two boundaries are independent and both matter: a
        sale can cross the 365-day cliff, the 1 April reset, both, or neither,
        and the combination decides the rate.
        """
        return self.now.financial_year != self.on_cliff.financial_year

    @property
    def break_even_fall(self) -> float:
        """How far the price may fall while waiting before the saving is lost.

        **Numerically identical to** :attr:`saves_fraction`, and that identity is
        the point rather than an accident: a tax saving worth 2% of the position
        is cancelled by a 2% fall in the position. Naming it twice is deliberate,
        because the two readings prompt opposite reactions and only one of them
        is usually offered — ₹8,000 saved sounds like a reason to wait until it
        is restated as *"a 2% dip erases this"*, and two percent in a month is an
        ordinary week in an equity index.
        """
        return self.saves_fraction

    def describe(self) -> str:
        """One line, carrying the counterweight with it."""
        crossing = ", crosses 1 April" if self.crosses_financial_year else ""
        return (
            f"waiting {self.days}d to {self.on_cliff.sell_on} saves "
            f"{self.saves:,.0f}{crossing}; a {self.break_even_fall:.2%} fall "
            f"meanwhile cancels it exactly"
        )


def price_waiting(
    lot: Lot,
    sell_price: float,
    sell_on: date,
    *,
    sell_orders: float = 1.0,
    ltcg_already_used: float = 0.0,
    ltcg_already_used_at_cliff: float | None = None,
    other_gains_this_year: float = 0.0,
) -> WaitComparison:
    """Price selling now against selling once the lot turns long-term.

    Args:
        lot: The holding.
        sell_price: Price per unit, held constant across both dates so the
            comparison isolates tax. It is an assumption, not a forecast.
        sell_on: The date "now" refers to.
        sell_orders: Orders the exit takes; the DP charge is per order.
        ltcg_already_used: Long-term gain realised so far this financial year.
        ltcg_already_used_at_cliff: The same figure for the financial year the
            cliff falls in, when waiting crosses 1 April. Defaults to
            ``ltcg_already_used`` when the two dates share a year, and to
            **zero** when they do not, since the allowance resets.
        other_gains_this_year: Gains a realised loss could offset.

    Returns:
        Both sales, and the difference between them.

    Raises:
        PreTradeError: if the lot is already long-term on ``sell_on``. There is
            no cliff left to wait for, and returning a zero saving would imply
            the question had been answered rather than misasked.
    """
    now = price_sale(
        lot,
        sell_price,
        sell_on,
        sell_orders=sell_orders,
        ltcg_already_used=ltcg_already_used,
        other_gains_this_year=other_gains_this_year,
    )
    if now.is_long_term:
        raise PreTradeError(
            f"{lot.name} is already long-term on {sell_on} ({now.holding_days} days "
            f"held). There is no waiting period left to price."
        )

    cliff = now.long_term_on
    if ltcg_already_used_at_cliff is None:
        same_year = financial_year(cliff) == financial_year(sell_on)
        ltcg_already_used_at_cliff = ltcg_already_used if same_year else 0.0

    on_cliff = price_sale(
        lot,
        sell_price,
        cliff,
        sell_orders=sell_orders,
        ltcg_already_used=ltcg_already_used_at_cliff,
        other_gains_this_year=other_gains_this_year,
    )
    return WaitComparison(now=now, on_cliff=on_cliff)


@dataclass(frozen=True, slots=True)
class SwitchConsequence:
    """Selling one holding to buy another, priced end to end.

    Attributes:
        sale: The exit leg, already priced.
        buy_charges: Charges on deploying the after-tax proceeds.
        into: What the proceeds go into. Free text, never interpreted.
    """

    sale: SaleConsequence
    buy_charges: ChargeBreakdown
    into: str

    @property
    def deployed(self) -> float:
        """Rupees actually working after both legs and the tax."""
        return self.sale.proceeds_after_tax - self.buy_charges.total

    @property
    def total_friction(self) -> float:
        """Everything lost to charges and tax across the switch."""
        return self.sale.total_friction + self.buy_charges.total

    @property
    def friction_fraction(self) -> float:
        """Friction as a fraction of the position being moved."""
        gross = self.sale.gross_proceeds
        return self.total_friction / gross if gross > 0 else 0.0

    @property
    def breakeven_move(self) -> float:
        """How much the replacement must gain to recover the friction.

        Arithmetic, not a forecast: the fraction by which the new holding must
        rise for the switch to have been worth making, relative to leaving the
        original alone. It says nothing about whether that will happen.
        """
        if self.deployed <= 0:
            return float("inf")
        return (self.sale.gross_proceeds - self.deployed) / self.deployed

    def describe(self) -> str:
        """One line for a result table."""
        return (
            f"{self.sale.lot.name} -> {self.into}: "
            f"friction {self.total_friction:,.0f} ({self.friction_fraction:.2%}), "
            f"deployed {self.deployed:,.0f}, "
            f"break-even {self.breakeven_move:+.2%}"
        )


def price_switch(
    lot: Lot,
    sell_price: float,
    sell_on: date,
    into: str,
    *,
    sell_orders: float = 1.0,
    ltcg_already_used: float = 0.0,
    other_gains_this_year: float = 0.0,
) -> SwitchConsequence:
    """Price selling one holding and putting the proceeds into another.

    The buy leg is sized at the **after-tax** proceeds, because that is the cash
    that exists. Sizing it at the gross would model a purchase funded partly by
    money already owed to the tax department.

    Args:
        lot: The holding being sold, in full.
        sell_price: Price per unit assumed on the exit.
        sell_on: Contemplated date for both legs.
        into: What the proceeds go into. Recorded, never interpreted.
        sell_orders: Orders the exit takes; the DP charge is per order.
        ltcg_already_used: Long-term gain already realised this financial year.
        other_gains_this_year: Gains a realised loss could offset.

    Returns:
        The switch, priced end to end.
    """
    sale = price_sale(
        lot,
        sell_price,
        sell_on,
        sell_orders=sell_orders,
        ltcg_already_used=ltcg_already_used,
        other_gains_this_year=other_gains_this_year,
    )
    buy_charges = charges_for(max(0.0, sale.proceeds_after_tax), Side.BUY, sell_on)
    return SwitchConsequence(sale=sale, buy_charges=buy_charges, into=into)
