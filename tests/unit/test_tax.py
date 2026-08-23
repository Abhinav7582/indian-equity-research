"""Tests for capital gains tax on a stock-level backtest.

The test that justifies the module is
:func:`test_monthly_rebalancing_is_taxed_at_the_short_term_rate`: at Indian
rates, turnover is taxed twice, and the second charge is the larger one.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.costs import ChargeBreakdown, Side
from indian_equity_research.backtest.engine import Fill
from indian_equity_research.backtest.tax import (
    LTCG_EXEMPTION,
    LTCG_RATE,
    STCG_RATE,
    financial_year,
    tax_on_fills,
)


def charges(side: Side, *, brokerage: float = 0.0) -> ChargeBreakdown:
    """A fill whose only charge is the one under test.

    Zero everywhere else so a test reads the tax arithmetic and nothing else.
    """
    return ChargeBreakdown(
        turnover=0.0,
        side=side,
        brokerage=brokerage,
        stt=0.0,
        stamp_duty=0.0,
        exchange_txn=0.0,
        sebi_fee=0.0,
        ipft=0.0,
        dp_charge=0.0,
        gst=0.0,
        gst_rate=0.0,
        schedule_label="test",
    )


def buy(symbol: str, when: dt.date, quantity: int, price: float) -> Fill:
    return Fill(when, symbol, Side.BUY, quantity, price, charges(Side.BUY))


def sell(symbol: str, when: dt.date, quantity: int, price: float) -> Fill:
    return Fill(when, symbol, Side.SELL, quantity, price, charges(Side.SELL))


def test_monthly_rebalancing_is_taxed_at_the_short_term_rate() -> None:
    """The charge most retail backtests omit, and it is the bigger one.

    A ₹10,000 gain realised inside twelve months costs ₹2,000 in tax. One full
    turnover of a ₹3,00,000 book costs about ₹1,374 in charges at ten holdings.
    Tax on a modest gain exceeds the entire cost of trading.
    """
    fills = [
        buy("X", dt.date(2020, 5, 1), 100, 100.0),
        sell("X", dt.date(2020, 9, 1), 100, 200.0),
    ]
    summary = tax_on_fills(fills)

    assert summary.total_realised_gain == pytest.approx(10_000.0)
    assert summary.total_tax == pytest.approx(10_000.0 * STCG_RATE)
    assert summary.years["2020-21"].long_term_gain == 0.0


def test_a_holding_over_twelve_months_gets_the_lower_rate_and_the_exemption() -> None:
    """12.5% above ₹1,25,000, and the first ₹1,25,000 free.

    The gap against 20% with no exemption is the entire argument for holding
    longer, and it is large enough to decide H2 on its own.
    """
    fills = [
        buy("X", dt.date(2019, 4, 1), 100, 1_000.0),
        sell("X", dt.date(2020, 10, 1), 100, 3_000.0),
    ]
    summary = tax_on_fills(fills)

    gain = 200_000.0
    assert summary.total_realised_gain == pytest.approx(gain)
    assert summary.total_tax == pytest.approx((gain - LTCG_EXEMPTION) * LTCG_RATE)


def test_exactly_365_days_is_still_short_term() -> None:
    """The boundary is *more than* twelve months, not twelve months.

    An off-by-one here silently reclassifies gains into the cheaper bracket.
    """
    bought = dt.date(2020, 4, 1)
    fills = [buy("X", bought, 10, 100.0), sell("X", bought + dt.timedelta(days=365), 10, 200.0)]
    summary = tax_on_fills(fills)
    assert not summary.gains[0].is_long_term
    assert summary.total_tax == pytest.approx(1_000.0 * STCG_RATE)

    later = [buy("X", bought, 10, 100.0), sell("X", bought + dt.timedelta(days=366), 10, 200.0)]
    assert tax_on_fills(later).gains[0].is_long_term


def test_lots_are_matched_first_in_first_out() -> None:
    """What the Income Tax Act requires for listed shares.

    Matching the most expensive lot first would minimise tax and would be
    modelling a different account from the one that exists.
    """
    fills = [
        buy("X", dt.date(2020, 4, 1), 10, 100.0),
        buy("X", dt.date(2020, 5, 1), 10, 300.0),
        sell("X", dt.date(2020, 6, 1), 10, 400.0),
    ]
    summary = tax_on_fills(fills)

    assert len(summary.gains) == 1
    assert summary.gains[0].bought == dt.date(2020, 4, 1)
    assert summary.gains[0].gain == pytest.approx(3_000.0)


def test_a_sale_spanning_two_lots_splits_across_both() -> None:
    """Each matched lot carries its own holding period.

    A single sell can be part long-term and part short-term, and collapsing it
    to one rate would be wrong in whichever direction the older lot fell.
    """
    fills = [
        buy("X", dt.date(2019, 1, 1), 10, 100.0),
        buy("X", dt.date(2020, 6, 1), 10, 100.0),
        sell("X", dt.date(2020, 8, 1), 20, 200.0),
    ]
    summary = tax_on_fills(fills)

    assert len(summary.gains) == 2
    assert [g.is_long_term for g in summary.gains] == [True, False]


def test_charges_reduce_taxable_gain_on_both_legs() -> None:
    """Costs are not profit.

    The cost of a lot is what was paid to acquire it and the proceeds are what
    was received net of charges, so a round trip that broke even before costs
    shows a taxable **loss**, not a gain.
    """
    fills = [
        Fill(dt.date(2020, 4, 1), "X", Side.BUY, 10, 100.0, charges(Side.BUY, brokerage=20.0)),
        Fill(dt.date(2020, 6, 1), "X", Side.SELL, 10, 100.0, charges(Side.SELL, brokerage=20.0)),
    ]
    summary = tax_on_fills(fills)

    assert summary.total_realised_gain == pytest.approx(-40.0)
    assert summary.total_tax == 0.0


def test_the_financial_year_runs_april_to_march() -> None:
    """Not the calendar year.

    Using January would move every Q4 gain into the wrong year, which changes
    when the LTCG exemption is consumed and therefore the tax actually paid.
    """
    assert financial_year(dt.date(2020, 4, 1)) == "2020-21"
    assert financial_year(dt.date(2021, 3, 31)) == "2020-21"
    assert financial_year(dt.date(2021, 4, 1)) == "2021-22"
    assert financial_year(dt.date(2021, 1, 15)) == "2020-21"


def test_a_losing_year_pays_nothing_and_carries_nothing_forward() -> None:
    """The declared simplification, and the direction it errs in.

    Indian law permits an eight-year loss carry-forward. Ignoring it overstates
    tax in every later profitable year, so a strategy can only look worse -- the
    safe direction for a simplification to run.
    """
    fills = [
        buy("X", dt.date(2020, 4, 1), 10, 100.0),
        sell("X", dt.date(2020, 6, 1), 10, 50.0),
        buy("Y", dt.date(2021, 5, 1), 10, 100.0),
        sell("Y", dt.date(2021, 7, 1), 10, 200.0),
    ]
    summary = tax_on_fills(fills)

    assert summary.years["2020-21"].total_tax == 0.0
    assert summary.years["2021-22"].total_tax == pytest.approx(1_000.0 * STCG_RATE)


def test_the_exemption_is_annual_not_lifetime() -> None:
    """₹1,25,000 per financial year, consumed and then restored."""
    fills = [
        buy("X", dt.date(2019, 4, 1), 100, 1_000.0),
        sell("X", dt.date(2020, 10, 1), 100, 2_000.0),
        buy("Y", dt.date(2020, 4, 1), 100, 1_000.0),
        sell("Y", dt.date(2021, 10, 1), 100, 2_000.0),
    ]
    summary = tax_on_fills(fills)
    taxable = max(100_000.0 - LTCG_EXEMPTION, 0.0)
    for label in ("2020-21", "2021-22"):
        assert summary.years[label].long_term_gain == pytest.approx(100_000.0)
        assert summary.years[label].long_term_tax == pytest.approx(taxable * LTCG_RATE)
    assert summary.total_tax == 0.0


def test_an_unmatched_sale_is_counted_not_ignored() -> None:
    """It should be impossible; a non-zero count means incomplete fills."""
    summary = tax_on_fills([sell("X", dt.date(2020, 6, 1), 10, 100.0)])
    assert summary.unmatched_sales == 10
