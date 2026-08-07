"""Corporate-action validation.

Written before the adjustment engine exists. These tests define what the
engine will have to satisfy.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from indian_equity_research.market.corporate_actions import (
    ActionType,
    AnomalyClass,
    CorporateAction,
    ValidationConfig,
    validate_adjustment_factors,
    validate_price_series,
)
from indian_equity_research.research.series import PriceSeries

START = date(2024, 1, 1)


def series(name: str, closes: list[float]) -> PriceSeries:
    dates = tuple(START + timedelta(days=i) for i in range(len(closes)))
    return PriceSeries(name, dates, tuple(closes))


class TestCleanSeries:
    def test_no_anomalies_in_a_quiet_series(self) -> None:
        report = validate_price_series(series("X", [100, 101, 102, 101, 103]))
        assert report.anomalies == []
        assert report.passed

    def test_moves_below_threshold_are_ignored(self) -> None:
        report = validate_price_series(series("X", [100, 120]))  # +20%
        assert report.anomalies == []

    def test_counts_observations_not_prices(self) -> None:
        assert validate_price_series(series("X", [100, 101, 102])).observations == 2


class TestUnadjustedActions:
    """The highest-value check: an unadjusted split is an exact ratio."""

    @pytest.mark.parametrize(
        ("after", "expected"),
        [
            (50.0, "1-for-1 bonus"),
            (100 / 3, "2-for-1 bonus"),
            (20.0, "5-for-1 split"),
            (10.0, "10-for-1 split"),
            (66.67, "1-for-2 bonus"),
        ],
    )
    def test_detects_a_split_shaped_drop(self, after: float, expected: str) -> None:
        report = validate_price_series(series("X", [100.0, after]))
        assert len(report.anomalies) == 1
        anomaly = report.anomalies[0]
        assert anomaly.classification is AnomalyClass.SUSPECTED_UNADJUSTED_ACTION
        assert expected in anomaly.detail
        assert anomaly.blocks

    def test_tolerates_a_normal_days_move_on_top_of_the_action(self) -> None:
        """A 2-for-1 split on a day the stock also fell 2% gives 0.49, not 0.50."""
        report = validate_price_series(series("X", [100.0, 49.0]))
        assert report.anomalies[0].classification is AnomalyClass.SUSPECTED_UNADJUSTED_ACTION

    @pytest.mark.parametrize("after", [62.7, 58.0, 71.0, 44.0, 36.0])
    def test_moves_matching_no_real_action_ratio_are_not_excused(self, after: float) -> None:
        """Moves matching no real action ratio must not be excused.

        Regression: matching any small-denominator fraction excused almost
        every large move, because the Farey sequence is dense. Real action
        ratios are a short, sparse list.
        """
        report = validate_price_series(series("X", [100.0, after]))
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED

    def test_detects_a_consolidation_shaped_rise(self) -> None:
        report = validate_price_series(series("X", [10.0, 100.0]))
        assert report.anomalies[0].classification is AnomalyClass.SUSPECTED_UNADJUSTED_ACTION
        assert "consolidation" in report.anomalies[0].detail

    def test_a_split_shaped_move_blocks_the_pipeline(self) -> None:
        report = validate_price_series(series("X", [100.0, 50.0]))
        assert report.passed is False
        assert len(report.blocking) == 1

    def test_a_messy_drop_is_not_mistaken_for_a_split(self) -> None:
        """-37.3% matches no simple ratio, so it must not be excused as one."""
        report = validate_price_series(series("X", [100.0, 62.7]))
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED


class TestDocumentedActions:
    def test_an_action_on_the_day_explains_the_move(self) -> None:
        action = CorporateAction(
            isin="INE111A01011",
            ex_date=START + timedelta(days=1),
            action_type=ActionType.SPLIT,
            ratio_from=1,
            ratio_to=2,
        )
        report = validate_price_series(
            series("X", [100.0, 50.0]), isin="INE111A01011", actions=[action]
        )
        assert report.anomalies[0].classification is AnomalyClass.EXPLAINED_BY_ACTION
        assert report.passed

    def test_an_action_within_the_window_still_explains_it(self) -> None:
        action = CorporateAction(
            isin="X",
            ex_date=START + timedelta(days=3),
            action_type=ActionType.BONUS,
            ratio_from=1,
            ratio_to=2,
        )
        report = validate_price_series(series("X", [100.0, 50.0]), actions=[action])
        assert report.anomalies[0].classification is AnomalyClass.EXPLAINED_BY_ACTION

    def test_an_action_far_away_does_not_explain_it(self) -> None:
        action = CorporateAction(
            isin="X",
            ex_date=START + timedelta(days=60),
            action_type=ActionType.SPLIT,
            ratio_from=1,
            ratio_to=2,
        )
        report = validate_price_series(series("X", [100.0, 50.0]), actions=[action])
        assert report.anomalies[0].classification is not AnomalyClass.EXPLAINED_BY_ACTION

    def test_price_multiplier_from_ratio(self) -> None:
        action = CorporateAction("X", START, ActionType.SPLIT, ratio_from=1, ratio_to=2)
        assert action.price_multiplier == 0.5

    def test_price_multiplier_is_none_without_a_ratio(self) -> None:
        action = CorporateAction("X", START, ActionType.DIVIDEND, amount=5.0)
        assert action.price_multiplier is None


class TestMarketExplanation:
    def test_a_crash_is_not_a_data_error(self) -> None:
        """Detected cross-sectionally, so no hardcoded event list to maintain."""
        stock = series("X", [100.0, 66.0])  # -34%
        market = series("NIFTY", [1000.0, 730.0])  # -27%
        report = validate_price_series(stock, market=market)
        assert report.anomalies[0].classification is AnomalyClass.EXPLAINED_BY_MARKET
        assert report.passed

    def test_an_idiosyncratic_move_is_not_excused_by_a_flat_market(self) -> None:
        stock = series("X", [100.0, 62.7])
        market = series("NIFTY", [1000.0, 1001.0])
        report = validate_price_series(stock, market=market)
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED

    def test_an_opposite_market_move_does_not_explain_it(self) -> None:
        stock = series("X", [100.0, 62.7])
        market = series("NIFTY", [1000.0, 1400.0])
        report = validate_price_series(stock, market=market)
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED

    def test_an_ordinary_market_day_does_not_excuse_a_large_move(self) -> None:
        """An ordinary market day cannot excuse an idiosyncratic move.

        A 1% index day is not a market event, so a 37% stock move on it must
        stay flagged. This test originally used a 5% index day, under a magnitude-ratio rule
        that could never fire. A 5% Nifty 100 day *is* a market event, and now
        correctly attributes.
        """
        stock = series("X", [100.0, 62.7])  # -37%
        market = series("NIFTY", [1000.0, 990.0])  # -1%
        report = validate_price_series(stock, market=market)
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED


class TestConfiguration:
    def test_threshold_is_configurable(self) -> None:
        cfg = ValidationConfig(outlier_threshold=0.05)
        report = validate_price_series(series("X", [100.0, 110.0]), config=cfg)
        assert len(report.anomalies) == 1

    def test_report_summary_names_the_verdict(self) -> None:
        report = validate_price_series(series("X", [100.0, 50.0]))
        assert "BLOCKED" in report.summary()

    def test_clean_summary_says_so(self) -> None:
        assert (
            "no moves beyond threshold"
            in validate_price_series(series("X", [100.0, 101.0])).summary()
        )


class TestAdjustmentFactors:
    def test_monotonic_factors_pass(self) -> None:
        factors = [(START, 1.0), (START + timedelta(days=1), 1.0), (START + timedelta(days=2), 2.0)]
        assert validate_adjustment_factors(factors) == []

    def test_a_fall_is_reported(self) -> None:
        """A cumulative factor that unwinds means an action was applied twice."""
        factors = [(START, 2.0), (START + timedelta(days=1), 1.0)]
        problems = validate_adjustment_factors(factors)
        assert any("fell from" in p for p in problems)

    def test_a_non_positive_factor_is_reported(self) -> None:
        assert any("not positive" in p for p in validate_adjustment_factors([(START, 0.0)]))

    def test_out_of_order_dates_are_reported(self) -> None:
        factors = [(START + timedelta(days=5), 1.0), (START, 1.0)]
        assert any("chronological" in p for p in validate_adjustment_factors(factors))

    def test_empty_input_is_reported(self) -> None:
        assert validate_adjustment_factors([]) == ["No adjustment factors supplied."]


class TestInverseMarketSeries:
    """Series that move against the market.

    A volatility index spikes when the market falls, so the same-direction
    test can never explain a spike and would report every one as a data error.
    """

    def test_a_vix_spike_is_unexplained_by_default(self) -> None:
        vix = series("VIX", [17.0, 28.0])  # +65%
        market = series("NIFTY", [1000.0, 941.0])  # -5.9%
        report = validate_price_series(vix, market=market)
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED

    def test_declaring_the_inverse_relationship_explains_it(self) -> None:
        vix = series("VIX", [17.0, 28.0])
        market = series("NIFTY", [1000.0, 941.0])
        cfg = ValidationConfig(market_moves_inversely=True)
        report = validate_price_series(vix, market=market, config=cfg)
        assert report.anomalies[0].classification is AnomalyClass.EXPLAINED_BY_MARKET
        assert report.passed

    def test_magnitude_is_not_required_for_an_inverse_series(self) -> None:
        """A 6% index fall routinely produces a 60% volatility spike."""
        vix = series("VIX", [12.0, 30.0])  # +150%
        market = series("NIFTY", [1000.0, 970.0])  # -3%
        cfg = ValidationConfig(market_moves_inversely=True)
        report = validate_price_series(vix, market=market, config=cfg)
        assert report.anomalies[0].classification is AnomalyClass.EXPLAINED_BY_MARKET

    def test_a_spike_on_a_rising_market_is_still_unexplained(self) -> None:
        vix = series("VIX", [17.0, 28.0])
        market = series("NIFTY", [1000.0, 1050.0])
        cfg = ValidationConfig(market_moves_inversely=True)
        report = validate_price_series(vix, market=market, config=cfg)
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED


class TestMarketExtremeDays:
    """Regression: the magnitude-ratio rule was dead above the threshold.

    Requiring the market to move 60% as far as the stock meant a 30% stock
    move needed an 18% index day. The worst Nifty 100 day on record is 17.3%,
    so the rule never fired once across 4.7 million real returns.
    """

    def test_a_stock_crash_on_an_extreme_market_day_is_attributed(self) -> None:
        stock = series("X", [100.0, 70.0])  # -30%
        market = series("NIFTY", [1000.0, 920.0])  # -8%: nowhere near 0.6 x 30%
        report = validate_price_series(stock, market=market)
        assert report.anomalies[0].classification is AnomalyClass.EXPLAINED_BY_MARKET

    def test_a_quiet_market_day_does_not_attribute(self) -> None:
        stock = series("X", [100.0, 70.0])
        market = series("NIFTY", [1000.0, 990.0])  # -1%, below the extreme threshold
        report = validate_price_series(stock, market=market)
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED

    def test_direction_still_matters_on_an_extreme_day(self) -> None:
        stock = series("X", [100.0, 70.0])  # -30%
        market = series("NIFTY", [1000.0, 1080.0])  # +8%, opposite way
        report = validate_price_series(stock, market=market)
        assert report.anomalies[0].classification is AnomalyClass.UNEXPLAINED

    def test_the_threshold_is_configurable(self) -> None:
        stock = series("X", [100.0, 70.0])
        market = series("NIFTY", [1000.0, 970.0])  # -3%
        strict = ValidationConfig(market_extreme_threshold=0.05)
        loose = ValidationConfig(market_extreme_threshold=0.02)
        assert (
            validate_price_series(stock, market=market, config=strict).anomalies[0].classification
            is AnomalyClass.UNEXPLAINED
        )
        assert (
            validate_price_series(stock, market=market, config=loose).anomalies[0].classification
            is AnomalyClass.EXPLAINED_BY_MARKET
        )
