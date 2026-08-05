"""Performance and drawdown metrics."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from indian_equity_research.research.metrics import (
    annualised_volatility,
    cagr,
    drawdown_episodes,
    equity_curve,
    max_drawdown,
    summarise,
)

START = date(2020, 1, 1)


def dates_for(curve: list[float]) -> list[date]:
    return [START + timedelta(days=i) for i in range(len(curve))]


class TestEquityCurve:
    def test_compounds(self) -> None:
        assert equity_curve([0.1, 0.1], initial=100.0) == pytest.approx([100.0, 110.0, 121.0])

    def test_length_is_returns_plus_one(self) -> None:
        assert len(equity_curve([0.01] * 5)) == 6

    def test_empty_returns_gives_initial_only(self) -> None:
        assert equity_curve([], initial=7.0) == [7.0]


class TestCagr:
    def test_doubling_over_one_year(self) -> None:
        assert cagr(100.0, 200.0, 1.0) == pytest.approx(1.0)

    def test_doubling_over_two_years(self) -> None:
        assert cagr(100.0, 200.0, 2.0) == pytest.approx(2**0.5 - 1)

    def test_flat(self) -> None:
        assert cagr(100.0, 100.0, 5.0) == pytest.approx(0.0)

    def test_total_loss(self) -> None:
        assert cagr(100.0, 0.0, 1.0) == -1.0

    @pytest.mark.parametrize(("start", "years"), [(0.0, 1.0), (-1.0, 1.0), (100.0, 0.0)])
    def test_invalid_inputs_rejected(self, start: float, years: float) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            cagr(start, 100.0, years)


class TestMaxDrawdown:
    def test_known_drawdown(self) -> None:
        # 100 -> 120 -> 90: peak 120, trough 90 -> 25%
        assert max_drawdown([100.0, 120.0, 90.0, 110.0]) == pytest.approx(0.25)

    def test_monotonic_rise_has_none(self) -> None:
        assert max_drawdown([1.0, 2.0, 3.0]) == 0.0

    def test_uses_the_deepest_not_the_last(self) -> None:
        # First episode -50%, second -20%.
        assert max_drawdown([100.0, 50.0, 100.0, 80.0]) == pytest.approx(0.50)

    def test_empty_curve(self) -> None:
        assert max_drawdown([]) == 0.0


class TestDrawdownEpisodes:
    def test_separates_two_distinct_episodes(self) -> None:
        """A2 rejects H4 if the benefit comes from one episode, so they must separate."""
        curve = [100.0, 80.0, 100.0, 105.0, 84.0, 110.0]
        episodes = drawdown_episodes(dates_for(curve), curve, minimum_depth=0.10)
        assert len(episodes) == 2
        assert episodes[0].depth == pytest.approx(0.20)
        assert episodes[1].depth == pytest.approx(0.20)

    def test_ignores_shallow_dips(self) -> None:
        curve = [100.0, 98.0, 100.0, 99.0, 101.0]
        assert drawdown_episodes(dates_for(curve), curve, minimum_depth=0.10) == []

    def test_reports_an_unrecovered_drawdown_at_the_end(self) -> None:
        """Dropping an open drawdown would flatter the result."""
        curve = [100.0, 120.0, 60.0]
        episodes = drawdown_episodes(dates_for(curve), curve, minimum_depth=0.10)
        assert len(episodes) == 1
        assert episodes[0].recovery_date is None
        assert episodes[0].recovered is False
        assert episodes[0].depth == pytest.approx(0.50)

    def test_records_peak_trough_and_recovery_dates(self) -> None:
        curve = [100.0, 70.0, 100.0]
        d = dates_for(curve)
        episode = drawdown_episodes(d, curve, minimum_depth=0.10)[0]
        assert episode.peak_date == d[0]
        assert episode.trough_date == d[1]
        assert episode.recovery_date == d[2]
        assert episode.recovered is True

    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            drawdown_episodes([START], [1.0, 2.0])


class TestVolatility:
    def test_zero_for_constant_returns(self) -> None:
        assert annualised_volatility([0.01] * 10) == pytest.approx(0.0)

    def test_scales_with_square_root_of_time(self) -> None:
        daily = [0.01, -0.01] * 50
        assert annualised_volatility(daily, 252) > annualised_volatility(daily, 12)

    def test_too_few_observations(self) -> None:
        assert annualised_volatility([0.01]) == 0.0


class TestSummarise:
    def test_populates_every_scored_metric(self) -> None:
        returns = [0.10, -0.20, 0.30]
        curve = equity_curve(returns, initial=100.0)
        d = [START + timedelta(days=365 * i) for i in range(len(curve))]
        s = summarise("test", d, curve, returns)
        assert s.label == "test"
        assert s.start == d[0]
        assert s.end == d[-1]
        assert s.final_value == pytest.approx(114.4)
        assert s.total_return == pytest.approx(0.144)
        assert s.max_drawdown == pytest.approx(0.20)
        assert s.years == pytest.approx(3.0, rel=0.01)

    def test_empty_curve_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty curve"):
            summarise("x", [], [], [])

    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="differ"):
            summarise("x", [START], [1.0, 2.0], [1.0])
