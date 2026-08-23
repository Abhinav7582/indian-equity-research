"""Capital gains tax on a stock-level backtest, computed from the fills.

Why this is a separate layer and not a cost
-------------------------------------------
Transaction charges are paid per order and reduce the cash from that order.
Tax is not: it is levied on a **realised gain**, matched lot by lot, at a rate
that depends on how long the lot was held, netted across the year, and paid
after the year ends. Folding it into ``charges_for`` would get every one of
those wrong.

It matters more here than in most markets, and more than most Indian retail
investors expect. At the rates below, a strategy that rebalances monthly hands
over **20%** of every gain, where one that holds for a year hands over 12.5% and
gets the first ₹1,25,000 free. Turnover is taxed twice: once in charges, and
again, larger, here.

The rates, and the one that surprises people
---------------------------------------------
* **STCG, s.111A — 20%.** Listed equity held under twelve months.
* **LTCG, s.112A — 12.5%**, on gains above ₹1,25,000 in a financial year.
* Both apply to listed equity with STT paid, which is every trade this engine
  models.

Deliberate simplifications, stated rather than buried
------------------------------------------------------
**Losses net within the financial year and are not carried forward.** Indian law
permits an eight-year carry-forward of capital losses. Ignoring it **overstates**
tax in any year that ends in aggregate loss, so the simplification is
conservative -- it can only make a strategy look worse.

**Surcharge and cess are not modelled.** They apply above income thresholds this
project's ₹3,00,000 book cannot reach on its own, but they depend on the
holder's total income rather than on this account. Omitting them understates
tax for a holder in a high bracket, and this is the one simplification here that
runs in the flattering direction, so it is stated plainly rather than left to be
discovered.

**The financial year is April to March**, as in Indian law, not the calendar
year.

**Lots are matched first-in, first-out.** This is what the Income Tax Act
requires for listed shares; it is not a choice, and choosing otherwise to
minimise tax would be modelling a different account.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from typing import Final

from indian_equity_research.backtest.costs import Side
from indian_equity_research.backtest.engine import Fill

__all__ = [
    "LONG_TERM_DAYS",
    "LTCG_EXEMPTION",
    "LTCG_RATE",
    "STCG_RATE",
    "RealisedGain",
    "TaxSummary",
    "TaxYear",
    "financial_year",
    "tax_on_fills",
]

#: Section 111A, listed equity with STT paid.
STCG_RATE: Final = 0.20
#: Section 112A.
LTCG_RATE: Final = 0.125
#: Section 112A annual exemption, per financial year.
LTCG_EXEMPTION: Final = 125_000.0
#: Holding period above which a listed equity gain is long-term.
LONG_TERM_DAYS: Final = 365


@dataclass(frozen=True, slots=True)
class RealisedGain:
    """One matched lot: what was sold, when it was bought, and the gain."""

    symbol: str
    bought: date
    sold: date
    quantity: int
    cost: float
    proceeds: float

    @property
    def gain(self) -> float:
        """Proceeds less cost, both inclusive of the charges on each leg."""
        return self.proceeds - self.cost

    @property
    def holding_days(self) -> int:
        """Days held, which decides the rate."""
        return (self.sold - self.bought).days

    @property
    def is_long_term(self) -> bool:
        """True when s.112A applies rather than s.111A."""
        return self.holding_days > LONG_TERM_DAYS


@dataclass(slots=True)
class TaxYear:
    """One April-March year's realised gains and the tax on them."""

    label: str
    short_term_gain: float = 0.0
    long_term_gain: float = 0.0
    short_term_tax: float = 0.0
    long_term_tax: float = 0.0

    @property
    def total_tax(self) -> float:
        """Tax payable for the year."""
        return self.short_term_tax + self.long_term_tax

    def describe(self) -> str:
        """One line for a result table."""
        return (
            f"{self.label}: STCG {self.short_term_gain:+,.0f} -> {self.short_term_tax:,.0f}, "
            f"LTCG {self.long_term_gain:+,.0f} -> {self.long_term_tax:,.0f}, "
            f"total {self.total_tax:,.0f}"
        )


@dataclass(slots=True)
class TaxSummary:
    """Every realised gain, grouped by financial year."""

    years: dict[str, TaxYear] = field(default_factory=dict)
    gains: list[RealisedGain] = field(default_factory=list)
    unmatched_sales: int = 0

    @property
    def total_tax(self) -> float:
        """Tax across every year."""
        return sum(year.total_tax for year in self.years.values())

    @property
    def total_realised_gain(self) -> float:
        """Net realised gain across every year, before tax."""
        return sum(gain.gain for gain in self.gains)

    @property
    def effective_rate(self) -> float:
        """Tax as a fraction of net realised gain, or zero if there was none."""
        net = self.total_realised_gain
        return self.total_tax / net if net > 0 else 0.0

    def describe(self) -> str:
        """One line, carrying the effective rate with it."""
        return (
            f"{len(self.gains)} realised lots across {len(self.years)} financial years, "
            f"net gain {self.total_realised_gain:+,.0f}, tax {self.total_tax:,.0f} "
            f"({self.effective_rate:.1%} of gains)"
        )


def financial_year(when: date) -> str:
    """The Indian financial year containing ``when``, as ``2020-21``.

    April to March, not January to December. Using the calendar year would move
    every January-to-March gain into the wrong year, which changes when the
    ₹1,25,000 LTCG exemption is consumed and therefore the tax actually paid.
    """
    start = when.year if when.month >= 4 else when.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def tax_on_fills(fills: list[Fill]) -> TaxSummary:
    """Match sells against buys FIFO and compute the tax on each financial year.

    Both legs are taken **inclusive of charges**: the cost of a lot is what was
    paid to acquire it, and the proceeds are what was received net of the
    charges on the sale. That is the correct base, and it means transaction
    costs reduce taxable gain rather than being taxed as though they were
    profit.

    Args:
        fills: Every fill from a backtest, in any order; they are sorted here.

    Returns:
        The realised lots, grouped into financial years with tax applied.

    Notes:
        A sell with no matching buy is counted in ``unmatched_sales`` rather
        than silently ignored. It should never happen -- the engine cannot sell
        what it does not hold -- so a non-zero count means the fills passed in
        are not a complete run.
    """
    lots: dict[str, deque[tuple[date, int, float]]] = defaultdict(deque)
    summary = TaxSummary()

    for fill in sorted(fills, key=lambda f: (f.date, f.symbol, f.side.value)):
        if fill.side is Side.BUY:
            unit_cost = (fill.turnover + fill.charges.total) / fill.quantity
            lots[fill.symbol].append((fill.date, fill.quantity, unit_cost))
            continue

        remaining = fill.quantity
        # Charges on the sale are spread across the units sold, so a partial
        # exit carries its share rather than the whole DP charge landing on the
        # first matched lot.
        unit_proceeds = (fill.turnover - fill.charges.total) / fill.quantity
        queue = lots[fill.symbol]
        while remaining > 0 and queue:
            bought, held, unit_cost = queue[0]
            matched = min(remaining, held)
            summary.gains.append(
                RealisedGain(
                    symbol=fill.symbol,
                    bought=bought,
                    sold=fill.date,
                    quantity=matched,
                    cost=matched * unit_cost,
                    proceeds=matched * unit_proceeds,
                )
            )
            remaining -= matched
            if matched == held:
                queue.popleft()
            else:
                queue[0] = (bought, held - matched, unit_cost)
        if remaining > 0:
            summary.unmatched_sales += remaining

    for gain in summary.gains:
        year = summary.years.setdefault(
            financial_year(gain.sold), TaxYear(financial_year(gain.sold))
        )
        if gain.is_long_term:
            year.long_term_gain += gain.gain
        else:
            year.short_term_gain += gain.gain

    for year in summary.years.values():
        # Tax is charged on a net positive gain only. A year that nets a loss
        # pays nothing and, by the simplification declared above, carries
        # nothing forward -- which overstates tax in every later profitable
        # year and is therefore the conservative direction.
        year.short_term_tax = max(year.short_term_gain, 0.0) * STCG_RATE
        taxable_long = max(year.long_term_gain - LTCG_EXEMPTION, 0.0)
        year.long_term_tax = taxable_long * LTCG_RATE

    return summary
