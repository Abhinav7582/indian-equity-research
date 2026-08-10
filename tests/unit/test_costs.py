"""Indian equity transaction costs.

Expected values are worked by hand in the comments and match the figures in
the original feasibility research, so a change to the code cannot quietly
change the cost assumptions every backtest depends on.
"""

from __future__ import annotations

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
