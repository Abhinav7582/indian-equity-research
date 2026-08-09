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
