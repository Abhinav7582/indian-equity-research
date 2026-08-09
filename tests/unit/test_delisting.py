"""Delisting register derived from observed trading."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from indian_equity_research.market.bhavcopy import BhavRecord
from indian_equity_research.market.delisting import (
    TerminalReturnPolicy,
    build_delisting_register,
)

START = date(2020, 1, 1)


def rec(isin: str, day: date, close: float = 100.0, symbol: str = "X") -> BhavRecord:
    return BhavRecord(
        trade_date=day,
        isin=isin,
        symbol=symbol,
        series="EQ",
        open=close,
        high=close,
        low=close,
        close=close,
        previous_close=close,
        volume=1000,
        turnover=close * 1000,
    )


def run(isin: str, days: list[int], close: float = 100.0) -> list[BhavRecord]:
    return [rec(isin, START + timedelta(days=d), close) for d in days]


class TestDetection:
    def test_a_security_trading_to_the_end_is_not_delisted(self) -> None:
        records = run("INE111A01011", [0, 100, 200, 400])
        assert len(build_delisting_register(records)) == 0

    def test_a_security_that_vanishes_is_detected(self) -> None:
        records = run("INE111A01011", [0, 10, 20]) + run("INE222B01012", [0, 400])
        register = build_delisting_register(records)
        assert "INE111A01011" in register.records
        assert "INE222B01012" not in register.records

    def test_records_the_final_session_and_price(self) -> None:
        records = [
            rec("INE111A01011", START, 100.0),
            rec("INE111A01011", START + timedelta(days=5), 42.0),
            *run("INE222B01012", [400]),
        ]
        entry = build_delisting_register(records).records["INE111A01011"]
        assert entry.last_seen == START + timedelta(days=5)
        assert entry.last_close == 42.0
        assert entry.sessions_observed == 2

    def test_absence_threshold_is_configurable(self) -> None:
        records = run("INE111A01011", [0, 100]) + run("INE222B01012", [0, 400])
        assert len(build_delisting_register(records, absence_days=180)) == 1
        assert len(build_delisting_register(records, absence_days=365)) == 0

    def test_no_records_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="no records"):
            build_delisting_register([])


class TestSuspendedVersusDelisted:
    """A suspension can end; a delisting cannot. The distinction matters."""

    def test_absent_but_still_listed_is_suspended(self) -> None:
        records = run("INE111A01011", [0, 10]) + run("INE222B01012", [400])
        register = build_delisting_register(records, currently_listed={"INE111A01011"})
        assert register.records["INE111A01011"].still_listed
        assert len(register.suspended) == 1
        assert len(register.delisted) == 0

    def test_absent_and_unlisted_is_delisted(self) -> None:
        records = run("INE111A01011", [0, 10]) + run("INE222B01012", [400])
        register = build_delisting_register(records, currently_listed=set())
        assert len(register.delisted) == 1
        assert len(register.suspended) == 0


class TestTerminalReturnPolicy:
    def test_defaults_to_refusing_to_assume(self) -> None:
        """Assuming the last traded price was recoverable flatters results."""
        records = run("INE111A01011", [0, 10]) + run("INE222B01012", [400])
        entry = build_delisting_register(records).records["INE111A01011"]
        assert entry.policy is TerminalReturnPolicy.UNKNOWN

    def test_policy_can_be_declared(self) -> None:
        records = run("INE111A01011", [0, 10]) + run("INE222B01012", [400])
        register = build_delisting_register(records, policy=TerminalReturnPolicy.TOTAL_LOSS)
        assert register.records["INE111A01011"].policy is TerminalReturnPolicy.TOTAL_LOSS

    def test_summary_is_informative(self) -> None:
        records = run("INE111A01011", [0, 10]) + run("INE222B01012", [400])
        assert "delisted" in build_delisting_register(records).summary()


class TestFinalTrajectory:
    """Distinguishing *how a security ended* from *how it did over its life*.

    ``decline_from_first`` is confounded by however long the security traded:
    a company that triples over eight years and then collapses 95% in its last
    six months scores the same as a slow decliner. The trailing-window
    measures are not confounded that way.
    """

    def _rows(self, closes: list[float], isin: str = "INE111A01011") -> list[BhavRecord]:
        return [rec(isin, START + timedelta(days=i), c) for i, c in enumerate(closes)]

    def test_a_collapse_scores_low_on_final_decline(self) -> None:
        # Rises to 300 then falls to 10 just before vanishing.
        closes = [100.0] * 20 + [300.0] * 20 + [10.0]
        records = self._rows(closes) + run("INE222B01012", [900])
        entry = build_delisting_register(records).records["INE111A01011"]
        assert entry.final_decline == pytest.approx(10 / 300)

    def test_an_acquisition_scores_high_on_final_decline(self) -> None:
        # Trades normally and delists at its recent high.
        closes = [100.0] * 20 + [118.0, 120.0]
        records = self._rows(closes) + run("INE222B01012", [900])
        entry = build_delisting_register(records).records["INE111A01011"]
        assert entry.final_decline == pytest.approx(1.0)

    def test_lifetime_return_cannot_tell_them_apart(self) -> None:
        """Both end at 3x their first price; only one collapsed."""
        collapsed = [100.0] * 10 + [900.0] * 10 + [300.0]
        acquired = [100.0] * 20 + [300.0]
        a = build_delisting_register(
            self._rows(collapsed, "INE111A01011") + run("INE999Z01019", [900])
        ).records["INE111A01011"]
        b = build_delisting_register(
            self._rows(acquired, "INE222B01012") + run("INE999Z01019", [900])
        ).records["INE222B01012"]
        assert a.decline_from_first == pytest.approx(b.decline_from_first)  # identical
        assert a.final_decline < b.final_decline  # distinguishable

    def test_terminal_slide_catches_a_sharp_final_fall(self) -> None:
        closes = [100.0] * 100 + [5.0]
        records = self._rows(closes) + run("INE222B01012", [900])
        entry = build_delisting_register(records, slide_window=60).records["INE111A01011"]
        assert entry.terminal_slide == pytest.approx(0.05)

    def test_windows_are_configurable(self) -> None:
        closes = [500.0] + [100.0] * 30 + [50.0]
        records = self._rows(closes) + run("INE222B01012", [900])
        wide = build_delisting_register(records, trailing_window=100).records["INE111A01011"]
        narrow = build_delisting_register(records, trailing_window=10).records["INE111A01011"]
        assert wide.peak_close == 500.0
        assert narrow.peak_close == 100.0

    def test_short_history_does_not_crash(self) -> None:
        records = self._rows([42.0]) + run("INE222B01012", [900])
        entry = build_delisting_register(records).records["INE111A01011"]
        assert entry.final_decline == pytest.approx(1.0)
        assert entry.terminal_slide == pytest.approx(1.0)
