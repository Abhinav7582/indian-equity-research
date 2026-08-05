"""Overlay mechanics: costs, tax, switching and the rebalance restriction.

The arithmetic below is worked by hand in the comments so the expected values
do not come from the implementation being tested.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from indian_equity_research.research.overlay import (
    OverlayConfig,
    apply_overlay,
    buy_and_hold,
    month_start_rebalance_dates,
)
from indian_equity_research.research.regime import Regime

CONFIG = OverlayConfig(initial_capital=100_000.0, round_trip_cost=0.0055)

# Monthly observations so every date is a rebalance date.
MONTHLY = [date(2021, 1, 1), date(2021, 2, 1), date(2021, 3, 1)]
RISING = [100.0, 110.0, 121.0]

# Hand-worked entry:
#   one-way cost = 0.0055 / 2 = 0.00275
#   entry cost   = 100,000 * 0.00275 = 275
#   deployed     = 99,725  ->  units = 997.25 at 100
ENTRY_COST = 275.0
DEPLOYED = 99_725.0


class TestBuyAndHold:
    def test_charges_one_entry_cost(self) -> None:
        result = buy_and_hold(MONTHLY, RISING, CONFIG)
        assert result.total_costs == pytest.approx(ENTRY_COST)
        assert result.post_tax_curve[0] == pytest.approx(DEPLOYED)

    def test_pays_no_tax(self) -> None:
        """A buy-and-hold investor realises nothing and defers tax indefinitely."""
        assert buy_and_hold(MONTHLY, RISING, CONFIG).total_tax == 0.0

    def test_tracks_the_index(self) -> None:
        result = buy_and_hold(MONTHLY, RISING, CONFIG)
        # 997.25 units * 121 = 120,667.25
        assert result.post_tax_curve[-1] == pytest.approx(120_667.25)

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            buy_and_hold([], [], CONFIG)


class TestOverlayWithoutSwitches:
    def test_always_invested_matches_buy_and_hold(self) -> None:
        states = [Regime.RISK_ON] * 3
        overlaid = apply_overlay(MONTHLY, RISING, states, config=CONFIG)
        baseline = buy_and_hold(MONTHLY, RISING, CONFIG)
        assert overlaid.post_tax_curve == pytest.approx(baseline.post_tax_curve)
        assert overlaid.total_tax == 0.0
        assert overlaid.cycle_count == 0

    def test_never_invested_stays_in_cash(self) -> None:
        states = [Regime.RISK_OFF] * 3
        result = apply_overlay(MONTHLY, RISING, states, config=CONFIG)
        assert result.post_tax_curve == pytest.approx([100_000.0] * 3)
        assert result.total_costs == 0.0

    def test_unknown_state_is_treated_as_not_invested(self) -> None:
        states = [Regime.UNKNOWN] * 3
        result = apply_overlay(MONTHLY, RISING, states, config=CONFIG)
        assert result.switch_count == 0


class TestOverlayCostsAndTax:
    def test_exit_charges_cost_and_short_term_tax(self) -> None:
        # Enter 1 Jan at 100, exit 1 Feb at 110:
        #   gross    = 997.25 * 110       = 109,697.50
        #   exit cost= 109,697.50*0.00275 =      301.67
        #   proceeds =                      109,395.83
        #   gain     = 109,395.83 - 99,725 =   9,670.83
        #   31 days held -> STCG 20%       =   1,934.17
        #   cash     = 109,395.83 - 1,934.17 = 107,461.66
        states = [Regime.RISK_ON, Regime.RISK_OFF, Regime.RISK_OFF]
        result = apply_overlay(MONTHLY, RISING, states, config=CONFIG)
        exits = [s for s in result.switches if s.action == "EXIT"]
        assert len(exits) == 1
        assert exits[0].cost == pytest.approx(301.67, abs=0.05)
        assert exits[0].realised_gain == pytest.approx(9_670.83, abs=0.05)
        assert exits[0].tax_paid == pytest.approx(1_934.17, abs=0.05)
        assert exits[0].holding_days == 31
        assert result.post_tax_curve[-1] == pytest.approx(107_461.66, abs=0.05)

    def test_long_holding_uses_the_ltcg_rate_and_exemption(self) -> None:
        dates = [date(2021, 1, 1), date(2023, 1, 1)]
        closes = [100.0, 200.0]
        states = [Regime.RISK_ON, Regime.RISK_OFF]
        result = apply_overlay(dates, closes, states, config=CONFIG)
        exit_event = next(s for s in result.switches if s.action == "EXIT")
        assert exit_event.holding_days >= 365
        # Gain is roughly 99,177; the first 125,000 of LTCG each FY is exempt,
        # so no tax is due at all.
        assert exit_event.tax_paid == pytest.approx(0.0)

    def test_a_loss_attracts_no_tax(self) -> None:
        states = [Regime.RISK_ON, Regime.RISK_OFF]
        result = apply_overlay(
            [date(2021, 1, 1), date(2021, 2, 1)], [100.0, 50.0], states, config=CONFIG
        )
        exit_event = next(s for s in result.switches if s.action == "EXIT")
        assert exit_event.realised_gain < 0
        assert exit_event.tax_paid == 0.0

    def test_pre_tax_curve_isolates_the_tax_drag(self) -> None:
        states = [Regime.RISK_ON, Regime.RISK_OFF, Regime.RISK_OFF]
        result = apply_overlay(MONTHLY, RISING, states, config=CONFIG)
        assert result.pre_tax_curve[-1] > result.post_tax_curve[-1]
        assert result.pre_tax_curve[-1] - result.post_tax_curve[-1] == pytest.approx(
            result.total_tax
        )

    def test_round_trip_charges_two_legs(self) -> None:
        states = [Regime.RISK_ON, Regime.RISK_OFF, Regime.RISK_ON]
        result = apply_overlay(MONTHLY, RISING, states, config=CONFIG)
        assert result.cycle_count == 1
        assert result.switch_count == 3  # enter, exit, re-enter


class TestCashReturns:
    def test_cash_accrues_while_de_risked(self) -> None:
        states = [Regime.RISK_OFF] * 3
        result = apply_overlay(MONTHLY, RISING, states, cash_returns=[0.01, 0.01], config=CONFIG)
        assert result.post_tax_curve[-1] == pytest.approx(100_000.0 * 1.01 * 1.01)

    def test_default_cash_return_is_zero(self) -> None:
        """Understating cash yield biases against H4, which is the safe direction."""
        states = [Regime.RISK_OFF] * 3
        result = apply_overlay(MONTHLY, RISING, states, config=CONFIG)
        assert result.post_tax_curve[-1] == pytest.approx(100_000.0)

    def test_wrong_length_rejected(self) -> None:
        with pytest.raises(ValueError, match="cash_returns"):
            apply_overlay(MONTHLY, RISING, [Regime.RISK_ON] * 3, cash_returns=[0.01])


class TestRebalanceRestriction:
    def test_mid_month_signal_is_not_acted_on(self) -> None:
        """A2 restricts action to rebalance dates. This proves it is enforced."""
        dates = [date(2021, 1, 1), date(2021, 1, 15), date(2021, 2, 1)]
        closes = [100.0, 90.0, 80.0]
        states = [Regime.RISK_ON, Regime.RISK_OFF, Regime.RISK_OFF]
        result = apply_overlay(dates, closes, states, config=CONFIG)
        exits = [s for s in result.switches if s.action == "EXIT"]
        assert len(exits) == 1
        assert exits[0].when == date(2021, 2, 1)  # not the 15th

    def test_month_start_selection(self) -> None:
        dates = [
            date(2021, 1, 4),
            date(2021, 1, 20),
            date(2021, 2, 1),
            date(2021, 2, 15),
            date(2021, 3, 2),
        ]
        assert month_start_rebalance_dates(dates) == {
            date(2021, 1, 4),
            date(2021, 2, 1),
            date(2021, 3, 2),
        }


class TestOverlayConfig:
    def test_one_way_cost_is_half_the_round_trip(self) -> None:
        assert OverlayConfig(round_trip_cost=0.0055).one_way_cost == pytest.approx(0.00275)

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"initial_capital": 0.0}, "initial_capital"),
            ({"round_trip_cost": 1.5}, "round_trip_cost"),
            ({"stcg_rate": 1.0}, "stcg_rate"),
            ({"ltcg_rate": -0.1}, "ltcg_rate"),
        ],
    )
    def test_invalid_parameters_rejected(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            OverlayConfig(**kwargs)

    def test_defaults_match_amendment_a2(self) -> None:
        cfg = OverlayConfig()
        assert cfg.round_trip_cost == 0.0055
        assert cfg.stcg_rate == 0.20
        assert cfg.ltcg_rate == 0.125
        assert cfg.initial_capital == 300_000.0
