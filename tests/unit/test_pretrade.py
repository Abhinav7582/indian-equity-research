"""Tests for pricing a contemplated trade before it is made.

The ones that matter most are the boundary tests. A tax rate that steps from 20%
to 12.5% overnight, and an exemption that resets on a date unrelated to the
holding period, are exactly the conditions under which an off-by-one produces a
plausible number rather than an error.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.pretrade import (
    Lot,
    PreTradeError,
    next_financial_year_start,
    price_sale,
    price_switch,
    price_waiting,
)
from indian_equity_research.backtest.tax import LONG_TERM_DAYS, LTCG_EXEMPTION

BOUGHT = dt.date(2024, 6, 3)


def lot(quantity: float = 1000, price: float = 400.0, bought: dt.date = BOUGHT) -> Lot:
    return Lot(name="TEST", quantity=quantity, buy_price=price, bought_on=bought)


# ---------------------------------------------------------------------------
# The long-term cliff
# ---------------------------------------------------------------------------


def test_the_cliff_falls_strictly_after_three_hundred_and_sixty_five_days() -> None:
    """s.112A needs *more than* 365 days, not 365.

    Selling on day 365 exactly is short-term. An inclusive comparison here would
    apply 12.5% to a gain the Act taxes at 20%, and understate the bill by a
    third with nothing in the output to show for it.
    """
    holding = lot()
    on_365 = price_sale(holding, 500.0, BOUGHT + dt.timedelta(days=LONG_TERM_DAYS))
    on_366 = price_sale(holding, 500.0, BOUGHT + dt.timedelta(days=LONG_TERM_DAYS + 1))
    assert not on_365.is_long_term
    assert on_366.is_long_term


def test_one_day_across_the_cliff_changes_the_tax_by_a_step() -> None:
    """The rate does not slope. A day either side is a different section."""
    holding = lot()
    day_before = price_sale(holding, 500.0, BOUGHT + dt.timedelta(days=LONG_TERM_DAYS))
    day_after = price_sale(holding, 500.0, BOUGHT + dt.timedelta(days=LONG_TERM_DAYS + 1))
    # A Rs 1,00,000 gain: 20% short-term against nothing at all long-term,
    # because the whole gain fits inside the annual exemption.
    assert day_before.tax == pytest.approx(day_before.gain * 0.20)
    assert day_after.tax == 0.0


def test_days_to_long_term_reaches_zero_only_once_it_has_arrived() -> None:
    holding = lot()
    at_364 = price_sale(holding, 500.0, BOUGHT + dt.timedelta(days=364))
    at_366 = price_sale(holding, 500.0, BOUGHT + dt.timedelta(days=366))
    assert at_364.days_to_long_term == 2
    assert at_366.days_to_long_term == 0
    assert at_364.long_term_on == BOUGHT + dt.timedelta(days=366)


def test_pricing_a_wait_on_a_lot_that_is_already_long_term_is_refused() -> None:
    """Returning a zero saving would imply the question had been answered."""
    with pytest.raises(PreTradeError, match="already long-term"):
        price_waiting(lot(), 500.0, BOUGHT + dt.timedelta(days=400))


# ---------------------------------------------------------------------------
# The exemption, and the financial year it lives in
# ---------------------------------------------------------------------------


def test_the_exemption_is_consumed_by_earlier_sales() -> None:
    """Two long-term sales in one year do not each get Rs 1,25,000."""
    holding = lot()
    sell_on = BOUGHT + dt.timedelta(days=400)
    fresh = price_sale(holding, 500.0, sell_on)
    used = price_sale(holding, 500.0, sell_on, ltcg_already_used=LTCG_EXEMPTION)
    assert fresh.tax == 0.0
    assert used.tax == pytest.approx(used.gain * 0.125)


def test_only_the_gain_above_the_remaining_exemption_is_taxed() -> None:
    holding = lot()
    sale = price_sale(holding, 500.0, BOUGHT + dt.timedelta(days=400), ltcg_already_used=75_000.0)
    assert sale.exemption_left == pytest.approx(50_000.0)
    assert sale.tax == pytest.approx((sale.gain - 50_000.0) * 0.125)


def test_the_financial_year_turns_on_the_first_of_april() -> None:
    """Not 1 January. The exemption resets here and nowhere else."""
    assert next_financial_year_start(dt.date(2026, 3, 31)) == dt.date(2026, 4, 1)
    assert next_financial_year_start(dt.date(2026, 4, 1)) == dt.date(2027, 4, 1)
    assert price_sale(lot(), 500.0, dt.date(2026, 3, 31)).financial_year == "2025-26"
    assert price_sale(lot(), 500.0, dt.date(2026, 4, 1)).financial_year == "2026-27"


def test_waiting_across_april_gets_a_fresh_exemption() -> None:
    """The two boundaries are independent, and both change the rate.

    A lot bought in April turns long-term the following April — so the wait
    crosses the cliff *and* the reset. Assuming the current year's consumed
    allowance still applies would tax a gain that is in fact exempt.
    """
    bought = dt.date(2025, 4, 10)
    holding = lot(bought=bought)
    comparison = price_waiting(
        holding,
        500.0,
        dt.date(2026, 3, 20),
        ltcg_already_used=LTCG_EXEMPTION,
    )
    assert comparison.crosses_financial_year
    assert comparison.on_cliff.exemption_left == pytest.approx(LTCG_EXEMPTION)
    assert comparison.on_cliff.tax == 0.0


def test_a_wait_inside_one_financial_year_keeps_the_consumed_allowance() -> None:
    """The reset must not be applied where no reset happens."""
    comparison = price_waiting(lot(), 500.0, dt.date(2025, 5, 20), ltcg_already_used=LTCG_EXEMPTION)
    assert not comparison.crosses_financial_year
    assert comparison.on_cliff.exemption_left == 0.0
    assert comparison.on_cliff.tax > 0.0


# ---------------------------------------------------------------------------
# The counterweight
# ---------------------------------------------------------------------------


def test_the_break_even_fall_equals_the_saving_as_a_fraction() -> None:
    """The identity is the finding, not a coincidence.

    A saving worth 2% of a position is wiped out by a 2% fall in that position.
    Stating the saving in rupees alone is what makes waiting look free.
    """
    comparison = price_waiting(lot(), 500.0, BOUGHT + dt.timedelta(days=300))
    assert comparison.break_even_fall == pytest.approx(comparison.saves_fraction)
    assert comparison.saves > 0
    assert 0 < comparison.break_even_fall < 0.05


def test_waiting_saves_nothing_when_the_gain_is_a_loss() -> None:
    """A loss is a loss under either section when nothing offsets it."""
    comparison = price_waiting(lot(), 300.0, BOUGHT + dt.timedelta(days=300))
    assert comparison.now.gain < 0
    assert comparison.saves == 0.0


# ---------------------------------------------------------------------------
# Losses
# ---------------------------------------------------------------------------


def test_a_realised_loss_reduces_tax_only_against_gains_that_exist() -> None:
    """No gains to offset means no benefit, not a refund."""
    alone = price_sale(lot(), 300.0, BOUGHT + dt.timedelta(days=100))
    offset = price_sale(
        lot(), 300.0, BOUGHT + dt.timedelta(days=100), other_gains_this_year=500_000.0
    )
    assert alone.gain < 0
    assert alone.tax == 0.0
    assert offset.tax == pytest.approx(offset.gain * 0.20)
    assert offset.tax < 0


def test_a_loss_cannot_offset_more_than_the_gains_available() -> None:
    sale = price_sale(lot(), 300.0, BOUGHT + dt.timedelta(days=100), other_gains_this_year=10_000.0)
    assert sale.tax == pytest.approx(-10_000.0 * 0.20)


# ---------------------------------------------------------------------------
# Charges, and the switch
# ---------------------------------------------------------------------------


def test_the_dp_charge_is_levied_once_per_sell_order() -> None:
    """A8: an exit worked in three slices pays it three times."""
    one = price_sale(lot(), 500.0, dt.date(2026, 1, 5), sell_orders=1)
    three = price_sale(lot(), 500.0, dt.date(2026, 1, 5), sell_orders=3)
    assert three.charges.dp_charge == pytest.approx(one.charges.dp_charge * 3)
    assert three.charges.total > one.charges.total


def test_the_buy_leg_is_sized_at_the_after_tax_proceeds() -> None:
    """Sizing it gross would fund the purchase with money owed to the state."""
    switch = price_switch(lot(), 500.0, BOUGHT + dt.timedelta(days=100), into="SOMETHING ELSE")
    assert switch.sale.tax > 0
    assert switch.buy_charges.turnover == pytest.approx(switch.sale.proceeds_after_tax)
    assert switch.deployed < switch.sale.net_proceeds


def test_the_break_even_move_recovers_exactly_the_friction() -> None:
    """Deployed capital grown by the break-even must restore the gross."""
    switch = price_switch(lot(), 500.0, BOUGHT + dt.timedelta(days=100), into="SOMETHING ELSE")
    restored = switch.deployed * (1 + switch.breakeven_move)
    assert restored == pytest.approx(switch.sale.gross_proceeds)


def test_a_short_term_switch_costs_far_more_than_a_long_term_one() -> None:
    """The tax leg dominates the charge leg, and only the date separates them."""
    early = price_switch(lot(), 500.0, BOUGHT + dt.timedelta(days=200), into="OTHER")
    late = price_switch(lot(), 500.0, BOUGHT + dt.timedelta(days=400), into="OTHER")
    assert early.total_friction > late.total_friction * 5


# ---------------------------------------------------------------------------
# Inputs that cannot describe a real trade
# ---------------------------------------------------------------------------


def test_selling_before_buying_is_refused() -> None:
    """A negative holding period would be read as short-term without complaint."""
    with pytest.raises(PreTradeError, match="before it was bought"):
        price_sale(lot(), 500.0, BOUGHT - dt.timedelta(days=1))


def test_a_non_positive_quantity_is_refused() -> None:
    with pytest.raises(PreTradeError, match="quantity must be positive"):
        Lot(name="TEST", quantity=0, buy_price=100.0, bought_on=BOUGHT)


def test_a_negative_price_is_refused() -> None:
    with pytest.raises(PreTradeError, match="must not be negative"):
        price_sale(lot(), -1.0, BOUGHT + dt.timedelta(days=10))


def test_no_output_names_an_action() -> None:
    """This prices a stated trade. It does not choose one.

    The guard is that no field exists which could be read as advice, mirroring
    the same rule in the belief checker.
    """
    switch = price_switch(lot(), 500.0, BOUGHT + dt.timedelta(days=400), into="OTHER")
    forbidden = {"recommendation", "verdict", "should_sell", "advice", "signal", "action"}
    assert not forbidden & set(dir(switch))
    assert not forbidden & set(dir(switch.sale))
