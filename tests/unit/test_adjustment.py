"""Back-adjustment with provenance, and delisting sensitivity."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from indian_equity_research.market.adjustment import (
    Adjustment,
    AdjustmentSource,
    adjustments_from_actions,
    adjustments_from_report,
    apply_adjustments,
    cumulative_factors,
    terminal_return,
    terminal_sensitivity,
)
from indian_equity_research.market.corporate_actions import (
    ActionType,
    CorporateAction,
    validate_price_series,
)
from indian_equity_research.market.delisting import DelistingRecord, TerminalReturnPolicy
from indian_equity_research.research.series import PriceSeries

START = date(2024, 1, 1)


def series(closes: list[float], name: str = "X") -> PriceSeries:
    dates = tuple(START + timedelta(days=i) for i in range(len(closes)))
    return PriceSeries(name, dates, tuple(closes))


def delisting(first: float, last: float, isin: str = "INE111A01011") -> DelistingRecord:
    return DelistingRecord(
        isin=isin,
        last_symbol="X",
        first_seen=START,
        last_seen=START + timedelta(days=100),
        first_close=first,
        last_close=last,
        sessions_observed=100,
        absent_days=300,
        still_listed=False,
    )


class TestAdjustmentValidation:
    def test_non_positive_multiplier_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            Adjustment(START, 0.0, AdjustmentSource.DOCUMENTED)


class TestBackAdjustment:
    def test_a_split_makes_the_series_continuous(self) -> None:
        """100, 102 then 51 after a 2-for-1 split becomes 50, 51, 51."""
        raw = series([100.0, 102.0, 51.0])
        adj = [Adjustment(START + timedelta(days=2), 0.5, AdjustmentSource.DOCUMENTED)]
        out = apply_adjustments(raw, adj)
        assert out.closes == pytest.approx((50.0, 51.0, 51.0))

    def test_the_factor_reaches_one_at_the_end(self) -> None:
        factors = cumulative_factors(
            series([1.0, 1.0, 1.0]).dates,
            [Adjustment(START + timedelta(days=2), 0.5, AdjustmentSource.DOCUMENTED)],
        )
        assert factors[-1][1] == pytest.approx(1.0)
        assert factors[0][1] == pytest.approx(0.5)

    def test_factors_rise_chronologically(self) -> None:
        """What validate_adjustment_factors expects: never unwinding."""
        factors = cumulative_factors(
            series([1.0] * 5).dates,
            [
                Adjustment(START + timedelta(days=1), 0.5, AdjustmentSource.DOCUMENTED),
                Adjustment(START + timedelta(days=3), 0.2, AdjustmentSource.DOCUMENTED),
            ],
        )
        values = [f for _, f in factors]
        assert values == sorted(values)

    def test_two_actions_compound(self) -> None:
        raw = series([100.0, 100.0, 100.0])
        adj = [
            Adjustment(START + timedelta(days=1), 0.5, AdjustmentSource.DOCUMENTED),
            Adjustment(START + timedelta(days=2), 0.5, AdjustmentSource.DOCUMENTED),
        ]
        out = apply_adjustments(raw, adj)
        assert out.closes[0] == pytest.approx(25.0)

    def test_no_adjustments_leaves_prices_alone(self) -> None:
        raw = series([100.0, 101.0])
        assert apply_adjustments(raw, []).closes == raw.closes


class TestProvenance:
    def test_documented_actions_convert(self) -> None:
        action = CorporateAction("X", START, ActionType.SPLIT, ratio_from=1, ratio_to=2)
        out = adjustments_from_actions([action])
        assert out[0].multiplier == 0.5
        assert out[0].source is AdjustmentSource.DOCUMENTED

    def test_cash_dividends_produce_no_price_adjustment(self) -> None:
        action = CorporateAction("X", START, ActionType.DIVIDEND, amount=5.0)
        assert adjustments_from_actions([action]) == []

    def test_suspected_actions_convert_as_inferred(self) -> None:
        report = validate_price_series(series([100.0, 50.0]), isin="X")
        out = adjustments_from_report(report)
        assert len(out) == 1
        assert out[0].source is AdjustmentSource.INFERRED
        assert out[0].multiplier == pytest.approx(0.5)

    def test_unexplained_moves_are_never_converted(self) -> None:
        """Assuming an unexplained 37% fall was a split would erase a collapse."""
        report = validate_price_series(series([100.0, 62.7]), isin="X")
        assert adjustments_from_report(report) == []

    def test_inferred_adjustments_can_be_excluded(self) -> None:
        """Re-running without them is how a result is tested for dependence."""
        raw = series([100.0, 50.0])
        adj = [Adjustment(START + timedelta(days=1), 0.5, AdjustmentSource.INFERRED)]
        with_inferred = apply_adjustments(raw, adj, include_inferred=True)
        without = apply_adjustments(raw, adj, include_inferred=False)
        assert with_inferred.closes[0] == pytest.approx(50.0)
        assert without.closes[0] == pytest.approx(100.0)


class TestTerminalReturn:
    def test_last_price_policy_returns_the_final_close(self) -> None:
        assert terminal_return(delisting(200.0, 8.0), TerminalReturnPolicy.LAST_PRICE) == 8.0

    def test_total_loss_policy_returns_zero(self) -> None:
        assert terminal_return(delisting(200.0, 8.0), TerminalReturnPolicy.TOTAL_LOSS) == 0.0

    def test_unknown_policy_refuses_to_assume(self) -> None:
        assert terminal_return(delisting(200.0, 8.0), TerminalReturnPolicy.UNKNOWN) is None


class TestSensitivity:
    def test_measures_how_many_had_already_collapsed(self) -> None:
        records = [
            delisting(200.0, 4.0, "INE111A01011"),  # 2% of first price
            delisting(100.0, 90.0, "INE222B01012"),  # taken out healthy
        ]
        sensitivity = terminal_sensitivity(records, collapse_threshold=0.10)
        assert sensitivity.securities == 2
        assert sensitivity.already_collapsed == 1
        assert sensitivity.collapsed_fraction == pytest.approx(0.5)

    def test_spread_is_the_whole_last_price_value(self) -> None:
        records = [delisting(200.0, 4.0), delisting(100.0, 90.0, "INE222B01012")]
        sensitivity = terminal_sensitivity(records)
        assert sensitivity.spread == pytest.approx(94.0)

    def test_decline_from_first(self) -> None:
        assert delisting(200.0, 4.0).decline_from_first == pytest.approx(0.02)

    def test_summary_reports_the_collapse_share(self) -> None:
        records = [delisting(200.0, 4.0)]
        assert "had already fallen" in terminal_sensitivity(records).summary()

    def test_empty_input(self) -> None:
        sensitivity = terminal_sensitivity([])
        assert sensitivity.securities == 0
        assert sensitivity.collapsed_fraction == 0.0
