"""Indian equity transaction costs.

Expected values are worked by hand in the comments and match the figures in
the original feasibility research, so a change to the code cannot quietly
change the cost assumptions every backtest depends on.
"""

from __future__ import annotations

import datetime as dt
from datetime import date

import pytest

from indian_equity_research.backtest.costs import (
    Side,
    charges_for,
    round_trip_cost,
    schedule_for,
)

WHEN = date(2025, 6, 2)

# Hand-worked, ₹30,000 delivery order on the current schedule:
#   brokerage = max(min(0.1% x 30,000 = 30, cap 20), floor 5) = 20.00
#   STT       = 0.1% x 30,000                                 = 30.00
#   stamp     = 0.015% x 30,000  (buy only)                   =  4.50
#   exchange  = 0.00297% x 30,000                             =  0.891
#   SEBI      = 0.0001% x 30,000                              =  0.03
#   IPFT      = 0.0001% x 30,000                              =  0.03
#   DP        = flat, sell only                               = 20.00
#   GST 18% on (brokerage + exchange + SEBI + IPFT + DP)
#     buy : 18% x 20.951 =  3.771  -> total 59.222
#     sell: 18% x 40.951 =  7.371  -> total 78.322
BUY_TOTAL = 59.222
SELL_TOTAL = 78.322


class TestHandWorkedExample:
    def test_buy_matches_the_research_figure(self) -> None:
        assert charges_for(30_000, Side.BUY, WHEN).total == pytest.approx(BUY_TOTAL, abs=0.01)

    def test_sell_matches_the_research_figure(self) -> None:
        assert charges_for(30_000, Side.SELL, WHEN).total == pytest.approx(SELL_TOTAL, abs=0.01)

    def test_round_trip_is_about_46_basis_points(self) -> None:
        cost = round_trip_cost(30_000, WHEN)
        assert cost == pytest.approx(137.54, abs=0.02)
        assert cost / 30_000 == pytest.approx(0.00459, abs=0.0001)

    def test_every_component_is_itemised(self) -> None:
        breakdown = charges_for(30_000, Side.SELL, WHEN)
        items = breakdown.itemised()
        assert items["brokerage"] == pytest.approx(20.0)
        assert items["stt"] == pytest.approx(30.0)
        assert items["stamp_duty"] == 0.0  # sell side
        assert items["dp_charge"] == pytest.approx(20.0)
        assert sum(items.values()) == pytest.approx(breakdown.total)


class TestAsymmetry:
    def test_stt_is_charged_on_both_legs(self) -> None:
        """0.1% each way - a round trip pays 0.2% in STT alone."""
        buy = charges_for(100_000, Side.BUY, WHEN)
        sell = charges_for(100_000, Side.SELL, WHEN)
        assert buy.stt == pytest.approx(100.0)
        assert sell.stt == pytest.approx(100.0)

    def test_stamp_duty_is_buy_only(self) -> None:
        assert charges_for(100_000, Side.BUY, WHEN).stamp_duty > 0
        assert charges_for(100_000, Side.SELL, WHEN).stamp_duty == 0.0

    def test_dp_charge_is_sell_only(self) -> None:
        assert charges_for(100_000, Side.BUY, WHEN).dp_charge == 0.0
        assert charges_for(100_000, Side.SELL, WHEN).dp_charge == pytest.approx(20.0)


class TestBrokerageTiers:
    @pytest.mark.parametrize(
        ("turnover", "expected"),
        [
            (3_000, 5.0),  # below the floor: 0.1% = 3 -> floored at 5
            (10_000, 10.0),  # in the percentage band
            (20_000, 20.0),  # exactly at the cap
            (100_000, 20.0),  # capped
        ],
    )
    def test_floor_and_cap(self, turnover: float, expected: float) -> None:
        assert charges_for(turnover, Side.BUY, WHEN).brokerage == pytest.approx(expected)


class TestFlatChargePunishesSmallOrders:
    """The term a flat basis-point cost model hides entirely."""

    @pytest.mark.parametrize(
        ("position", "max_fraction"),
        [(25_000, 0.004), (10_000, 0.006), (5_000, 0.010)],
    )
    def test_cost_fraction_rises_as_positions_shrink(
        self, position: float, max_fraction: float
    ) -> None:
        assert charges_for(position, Side.SELL, WHEN).as_fraction <= max_fraction

    def test_small_positions_cost_proportionally_more(self) -> None:
        big = charges_for(25_000, Side.SELL, WHEN).as_fraction
        small = charges_for(5_000, Side.SELL, WHEN).as_fraction
        assert small > big * 2

    def test_fixed_component_is_the_dp_charge_with_gst(self) -> None:
        breakdown = charges_for(25_000, Side.SELL, WHEN)
        assert breakdown.fixed_component == pytest.approx(23.60, abs=0.01)


class TestSchedules:
    def test_selects_by_date(self) -> None:
        assert schedule_for(date(2016, 5, 2)).label == "pre-2024"
        assert schedule_for(date(2025, 6, 2)).label == "current"

    def test_records_which_schedule_was_used(self) -> None:
        assert charges_for(10_000, Side.BUY, date(2016, 5, 2)).schedule_label == "pre-2024"

    def test_a_date_before_every_schedule_is_an_error(self) -> None:
        """Silently applying today's rates to 2001 would be quietly wrong."""
        with pytest.raises(ValueError, match="No cost schedule covers"):
            charges_for(10_000, Side.BUY, date(2001, 1, 1))


class TestEdgeCases:
    def test_zero_turnover_costs_nothing(self) -> None:
        assert charges_for(0, Side.BUY, WHEN).total == 0.0

    def test_negative_turnover_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be negative"):
            charges_for(-100, Side.BUY, WHEN)


# ---------------------------------------------------------------------------
# Validated against real Groww contract notes
# ---------------------------------------------------------------------------
#
# These are not illustrative figures. They are the charges actually paid, and
# they reconcile against the funds ledger to the paisa. See
# docs/cost_model_validation.md.


def test_dp_charge_matches_the_real_contract_note() -> None:
    """Rs 20 + 18% GST = Rs 23.60, split CDSL Rs 3.50 + Groww Rs 16.50."""
    charge = charges_for(20_000.0, Side.SELL, dt.date(2026, 8, 11))
    assert charge.dp_charge == pytest.approx(20.0)
    assert charge.fixed_component == pytest.approx(23.60)


def test_a_buy_never_pays_a_dp_charge() -> None:
    """Confirmed on both notes: DP appears only against sells."""
    assert charges_for(20_000.0, Side.BUY, dt.date(2026, 8, 11)).dp_charge == 0.0


def test_the_11_august_2026_day_reconciles() -> None:
    """The day that proved DP is charged per ORDER, not per scrip.

    Two securities were sold. One of them -- Jio Financial -- went out in two
    separate orders. The contract note charged **three** DP events:

        Ltm Limited        1 sell order
        Jio Fin Services   2 sell orders   (-8, then -20)
        ---------------------------------
        2 scrips, 3 orders  ->  Rs 70.80

    Per-scrip-per-day would predict Rs 47.20. The note says Rs 70.80, so the
    unit is the order. Charging per position -- which is what the engine does
    when it models one order per exit -- is the OPTIMISTIC case.
    """
    per_order = charges_for(5_000.0, Side.SELL, dt.date(2026, 8, 11)).fixed_component
    assert per_order == pytest.approx(23.60)
    assert 3 * per_order == pytest.approx(70.80)
    assert 2 * per_order == pytest.approx(47.20), "the per-scrip reading, which the note refutes"


def test_the_4_august_2026_day_reconciles() -> None:
    """Six securities, six sell orders, seven fills.

    One order filled in two trades and was charged **once**, so the unit is not
    the fill either.
    """
    per_order = charges_for(5_000.0, Side.SELL, dt.date(2026, 8, 4)).fixed_component
    assert 6 * per_order == pytest.approx(141.60)


def test_the_brokerage_floor_binds_at_realistic_position_sizes() -> None:
    """Brokerage is a second fixed cost at this account size, not a rate.

    On 11 August 2026, ten orders produced Rs 51.61 of brokerage -- an average
    of Rs 5.16, meaning almost every order hit the Rs 5 minimum rather than the
    0.1% rate. Any position below Rs 5,000 pays the floor.
    """
    small = charges_for(1_897.0, Side.BUY, dt.date(2026, 8, 11))
    assert small.brokerage == pytest.approx(5.0), "0.1% of Rs 1,897 is Rs 1.90; the floor binds"
    large = charges_for(50_000.0, Side.BUY, dt.date(2026, 8, 11))
    assert large.brokerage == pytest.approx(20.0), "0.1% of Rs 50,000 is Rs 50; the cap binds"


def test_a_split_exit_pays_the_dp_charge_once_per_order() -> None:
    """The correction the contract note forced.

    Modelling one order per exit is optimistic. An exit worked in three slices
    pays Rs 23.60 three times, and nothing else about the trade changes.
    """
    one = charges_for(20_000.0, Side.SELL, dt.date(2026, 8, 11), sell_orders=1)
    three = charges_for(20_000.0, Side.SELL, dt.date(2026, 8, 11), sell_orders=3)
    assert three.dp_charge == pytest.approx(3 * one.dp_charge)
    assert three.total - one.total == pytest.approx(2 * 23.60)
    # Everything that scales with turnover is untouched.
    assert three.stt == pytest.approx(one.stt)
    assert three.brokerage == pytest.approx(one.brokerage)


def test_splitting_a_buy_costs_nothing_extra() -> None:
    """No DP charge on the buy side, so the parameter must not leak into it."""
    one = charges_for(20_000.0, Side.BUY, dt.date(2026, 8, 11), sell_orders=1)
    five = charges_for(20_000.0, Side.BUY, dt.date(2026, 8, 11), sell_orders=5)
    assert five.total == pytest.approx(one.total)


def test_fewer_than_one_order_per_exit_is_refused() -> None:
    """A position cannot leave the book without being sold."""
    with pytest.raises(ValueError, match="at least 1"):
        charges_for(20_000.0, Side.SELL, dt.date(2026, 8, 11), sell_orders=0.5)
