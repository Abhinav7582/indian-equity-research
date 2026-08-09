"""Back-adjustment with provenance, and delisting sensitivity."""

from __future__ import annotations

from dataclasses import replace
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
from indian_equity_research.market.delisting import (
    DelistingOutcome,
    DelistingRecord,
    TerminalReturnPolicy,
    classify_delisting,
)
from indian_equity_research.research.series import PriceSeries

START = date(2024, 1, 1)


def series(closes: list[float], name: str = "X") -> PriceSeries:
    dates = tuple(START + timedelta(days=i) for i in range(len(closes)))
    return PriceSeries(name, dates, tuple(closes))


def delisting(
    first: float, last: float, isin: str = "INE111A01011", peak: float | None = None
) -> DelistingRecord:
    return DelistingRecord(
        isin=isin,
        last_symbol="X",
        first_seen=START,
        last_seen=START + timedelta(days=100),
        first_close=first,
        last_close=last,
        peak_close=peak if peak is not None else max(first, last),
        close_before_end=last,
        sessions_observed=100,
        absent_days=300,
        still_listed=False,
    )


def rising(
    before: float, last: float, isin: str = "INE111A01011", peak: float | None = None
) -> DelistingRecord:
    """A security whose price rose into its final session."""
    return replace(delisting(before, last, isin, peak=peak), close_before_end=before)


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


class TestClassifiedPolicy:
    def test_acquisition_recovers_the_last_close(self) -> None:
        record = rising(100.0, 120.0)
        assert terminal_return(record, TerminalReturnPolicy.CLASSIFIED) == 120.0

    def test_collapse_recovers_nothing(self) -> None:
        record = delisting(100.0, 5.0, peak=200.0)
        assert terminal_return(record, TerminalReturnPolicy.CLASSIFIED) == 0.0

    def test_uncertain_is_refused(self) -> None:
        """The majority. Refusing keeps it inside the reported band."""
        record = delisting(100.0, 60.0, peak=100.0)
        assert terminal_return(record, TerminalReturnPolicy.CLASSIFIED) is None

    def test_collapse_wins_over_a_dead_cat_bounce(self) -> None:
        """Far below its peak but rising at the end is still a collapse."""
        record = rising(100.0, 8.0, peak=200.0)
        assert classify_delisting(record) is DelistingOutcome.LIKELY_COLLAPSE


class TestSensitivity:
    def test_counts_the_three_outcomes(self) -> None:
        s = terminal_sensitivity(
            [
                rising(100.0, 120.0, isin="INE111A01011"),
                delisting(100.0, 5.0, "INE222B01012", peak=200.0),
                delisting(100.0, 60.0, "INE333C01013", peak=100.0),
            ]
        )
        assert (s.likely_acquisition, s.likely_collapse, s.uncertain) == (1, 1, 1)

    def test_classification_narrows_the_band(self) -> None:
        s = terminal_sensitivity(
            [
                rising(100.0, 120.0, isin="INE111A01011"),
                delisting(100.0, 5.0, "INE222B01012", peak=200.0),
                delisting(100.0, 60.0, "INE333C01013", peak=100.0),
            ]
        )
        assert s.outer_band == pytest.approx(185.0)
        assert s.classified_band == pytest.approx(60.0)
        assert s.band_narrowing == pytest.approx(1 - 60 / 185)

    def test_outer_band_is_never_discarded(self) -> None:
        """The full range stays reported so a dependence on the read is visible."""
        s = terminal_sensitivity([delisting(100.0, 60.0, peak=100.0)])
        assert s.outer_band == pytest.approx(60.0)
        assert s.value_at_total_loss == 0.0

    def test_uncertain_fraction(self) -> None:
        s = terminal_sensitivity(
            [
                delisting(100.0, 5.0, "INE111A01011", peak=200.0),
                delisting(100.0, 60.0, "INE222B01012", peak=100.0),
            ]
        )
        assert s.uncertain_fraction == pytest.approx(0.5)

    def test_final_decline_uses_the_peak_not_the_first_price(self) -> None:
        """A security that tripled then collapsed scores low, as it should."""
        record = delisting(100.0, 300.0, peak=900.0)
        assert record.decline_from_first == pytest.approx(3.0)
        assert record.final_decline == pytest.approx(1 / 3)

    def test_summary_reports_both_bands(self) -> None:
        text = terminal_sensitivity([delisting(100.0, 60.0, peak=100.0)]).summary()
        assert "uncertain" in text
        assert "narrower" in text

    def test_empty_input(self) -> None:
        s = terminal_sensitivity([])
        assert s.securities == 0
        assert s.uncertain_fraction == 0.0
        assert s.band_narrowing == 0.0
