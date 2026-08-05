"""The Amendment A2 regime rule.

The scenario below is constructed so the correct answer is known by hand,
not inferred from the implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import pytest

from indian_equity_research.research.regime import (
    Regime,
    RegimeConfig,
    RegimeSeries,
    compute_regime,
    lag_states,
)
from indian_equity_research.research.series import PriceSeries

START = date(2020, 1, 1)

# Small windows so the scenario can be verified by hand.
TEST_CONFIG = RegimeConfig(sma_window=3, vix_quantile=0.8, vix_window=5)

#   i:                        0      1      2      3      4      5     6     7     8      9
MARKET: list[float] = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 90.0, 90.0, 90.0, 110.0]
VIX: list[float] = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 30.0, 10.0, 10.0, 10.0]

# Worked by hand:
#   3-day SMA known from i=2; 5-day VIX 80th percentile known from i=4.
#   i=6: close 90 < SMA 96.67  AND  VIX 30 > threshold 14      -> RISK_OFF
#   i=7: close 90 < SMA 93.33  but VIX 10 < threshold 14       -> RISK_ON
#   i=8: close 90 == SMA 90 (not below)                        -> RISK_ON
EXPECTED = [
    Regime.UNKNOWN,
    Regime.UNKNOWN,
    Regime.UNKNOWN,
    Regime.UNKNOWN,
    Regime.RISK_ON,
    Regime.RISK_ON,
    Regime.RISK_OFF,
    Regime.RISK_ON,
    Regime.RISK_ON,
    Regime.RISK_ON,
]


def series(name: str, values: Sequence[float]) -> PriceSeries:
    dates = tuple(START + timedelta(days=i) for i in range(len(values)))
    return PriceSeries(name, dates, tuple(float(v) for v in values))


@pytest.fixture
def computed() -> RegimeSeries:
    return compute_regime(series("NIFTY100", MARKET), series("VIX", VIX), TEST_CONFIG)


class TestRegimeConfig:
    def test_defaults_match_amendment_a2(self) -> None:
        """The declared parameters. Changing these requires a new amendment."""
        cfg = RegimeConfig()
        assert cfg.sma_window == 200
        assert cfg.vix_quantile == 0.80
        assert cfg.vix_window == 756  # three years at 252 sessions

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"sma_window": 1}, "sma_window"),
            ({"vix_quantile": 0.0}, "vix_quantile"),
            ({"vix_quantile": 1.0}, "vix_quantile"),
            ({"vix_window": 0}, "vix_window"),
        ],
    )
    def test_invalid_parameters_rejected(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            RegimeConfig(**kwargs)


class TestComputeRegime:
    def test_matches_the_hand_worked_scenario(self, computed: RegimeSeries) -> None:
        assert list(computed.states) == EXPECTED

    def test_warmup_is_unknown_never_risk_on(self, computed: RegimeSeries) -> None:
        """Defaulting warm-up to RISK_ON would assert a view with no evidence."""
        assert all(s is Regime.UNKNOWN for s in computed.states[:4])

    def test_trend_alone_does_not_trigger_risk_off(self, computed: RegimeSeries) -> None:
        # i=7 is below trend but volatility is not elevated.
        assert computed.states[7] is Regime.RISK_ON

    def test_volatility_alone_does_not_trigger_risk_off(self) -> None:
        # Rising market, one volatility spike: the AND condition must hold.
        market = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0]
        vix = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 99.0, 10.0, 10.0, 10.0]
        result = compute_regime(series("M", market), series("V", vix), TEST_CONFIG)
        assert Regime.RISK_OFF not in result.states

    def test_switch_count_ignores_warmup_boundary(self, computed: RegimeSeries) -> None:
        # RISK_ON, RISK_ON, RISK_OFF, RISK_ON, RISK_ON, RISK_ON -> 2 switches.
        assert computed.switch_count() == 2

    def test_fraction_risk_off(self, computed: RegimeSeries) -> None:
        assert computed.fraction_risk_off() == pytest.approx(1 / 6)

    def test_switches_per_year_is_annualised(self, computed: RegimeSeries) -> None:
        assert computed.switches_per_year() > 0

    def test_disjoint_series_rejected(self) -> None:
        a = PriceSeries("A", (START,), (100.0,))
        b = PriceSeries("B", (START + timedelta(days=99),), (10.0,))
        with pytest.raises(ValueError, match="No overlapping dates"):
            compute_regime(a, b, TEST_CONFIG)

    def test_states_align_with_dates(self, computed: RegimeSeries) -> None:
        assert len(computed.dates) == len(computed.states)


class TestCausality:
    """The property that prevents look-ahead. Worth more than every other test."""

    def test_appending_future_data_cannot_change_past_states(self) -> None:
        short = compute_regime(series("M", MARKET), series("V", VIX), TEST_CONFIG)
        extended_market = [*MARKET, 500.0, 500.0, 500.0, 10.0, 10.0]
        extended_vix = [*VIX, 1.0, 1.0, 1.0, 99.0, 99.0]
        long = compute_regime(series("M", extended_market), series("V", extended_vix), TEST_CONFIG)
        assert list(long.states[: len(short)]) == list(short.states)

    def test_truncating_the_future_cannot_change_past_states(self) -> None:
        full = compute_regime(series("M", MARKET), series("V", VIX), TEST_CONFIG)
        cut = compute_regime(series("M", MARKET[:8]), series("V", VIX[:8]), TEST_CONFIG)
        assert list(full.states[:8]) == list(cut.states)


class TestLagStates:
    def test_default_lag_of_one(self) -> None:
        states = (Regime.RISK_ON, Regime.RISK_OFF, Regime.RISK_ON)
        assert lag_states(states) == (Regime.UNKNOWN, Regime.RISK_ON, Regime.RISK_OFF)

    def test_preserves_length(self) -> None:
        states = (Regime.RISK_ON,) * 5
        assert len(lag_states(states, 3)) == 5

    def test_zero_lag_is_identity(self) -> None:
        states = (Regime.RISK_ON, Regime.RISK_OFF)
        assert lag_states(states, 0) == states

    def test_pads_with_unknown_not_risk_on(self) -> None:
        """No position may be implied before a signal existed."""
        assert lag_states((Regime.RISK_OFF, Regime.RISK_OFF), 2) == (
            Regime.UNKNOWN,
            Regime.UNKNOWN,
        )

    def test_negative_lag_rejected(self) -> None:
        with pytest.raises(ValueError, match="lag must not be negative"):
            lag_states((Regime.RISK_ON,), -1)
