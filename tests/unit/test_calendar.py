"""Trading calendar built from observed sessions."""

from __future__ import annotations

from datetime import date

import pytest

from indian_equity_research.market.calendar import CalendarRangeError, TradingCalendar

# Mon 1 Jan 2024 .. Fri 5 Jan, then Mon 8 Jan. 6-7 Jan is a weekend.
# 4 Jan is deliberately omitted: a mid-week holiday.
SESSIONS = [
    date(2024, 1, 1),
    date(2024, 1, 2),
    date(2024, 1, 3),
    date(2024, 1, 5),
    date(2024, 1, 8),
    date(2024, 1, 9),
]


@pytest.fixture
def cal() -> TradingCalendar:
    return TradingCalendar.from_dates(SESSIONS)


class TestConstruction:
    def test_sorts_and_deduplicates(self) -> None:
        c = TradingCalendar.from_dates([SESSIONS[2], SESSIONS[0], SESSIONS[0], SESSIONS[1]])
        assert c.sessions == (SESSIONS[0], SESSIONS[1], SESSIONS[2])

    def test_empty_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one observed session"):
            TradingCalendar.from_dates([])

    def test_unsorted_direct_construction_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="strictly increasing"):
            TradingCalendar(sessions=(SESSIONS[1], SESSIONS[0]))

    def test_single_session_calendar(self) -> None:
        """Smallest case exposing a construction bug.

        The ordering check originally used ``zip(x, x[1:], strict=True)``,
        which raises on *any* input because the second argument is always one
        element shorter. Every calendar construction failed, not only
        single-element ones.
        """
        c = TradingCalendar.from_dates([SESSIONS[0]])
        assert len(c) == 1
        assert c.first == c.last == SESSIONS[0]

    def test_two_session_calendar(self) -> None:
        c = TradingCalendar.from_dates(SESSIONS[:2])
        assert len(c) == 2

    def test_duplicates_are_not_treated_as_unsorted(self) -> None:
        c = TradingCalendar.from_dates([SESSIONS[0], SESSIONS[0], SESSIONS[1]])
        assert len(c) == 2


class TestSessions:
    def test_known_session(self, cal: TradingCalendar) -> None:
        assert cal.is_session(date(2024, 1, 2))

    def test_weekend_is_not_a_session(self, cal: TradingCalendar) -> None:
        assert not cal.is_session(date(2024, 1, 6))

    def test_midweek_holiday_is_not_a_session(self, cal: TradingCalendar) -> None:
        """The case a weekday rule gets wrong."""
        holiday = date(2024, 1, 4)
        assert holiday.weekday() < 5
        assert not cal.is_session(holiday)

    def test_outside_the_range_raises_rather_than_lying(self, cal: TradingCalendar) -> None:
        """Answering False would be indistinguishable from a real holiday."""
        with pytest.raises(CalendarRangeError, match="outside the observed calendar"):
            cal.is_session(date(2025, 6, 1))


class TestNavigation:
    def test_previous_session_skips_the_holiday(self, cal: TradingCalendar) -> None:
        assert cal.previous_session(date(2024, 1, 5)) == date(2024, 1, 3)

    def test_previous_session_skips_the_weekend(self, cal: TradingCalendar) -> None:
        assert cal.previous_session(date(2024, 1, 8)) == date(2024, 1, 5)

    def test_previous_inclusive_returns_the_day_itself(self, cal: TradingCalendar) -> None:
        assert cal.previous_session(date(2024, 1, 5), inclusive=True) == date(2024, 1, 5)

    def test_next_session_skips_the_weekend(self, cal: TradingCalendar) -> None:
        assert cal.next_session(date(2024, 1, 5)) == date(2024, 1, 8)

    def test_no_earlier_session_raises(self, cal: TradingCalendar) -> None:
        with pytest.raises(CalendarRangeError, match="No session on or before"):
            cal.previous_session(date(2024, 1, 1))

    def test_no_later_session_raises(self, cal: TradingCalendar) -> None:
        with pytest.raises(CalendarRangeError, match="No session on or after"):
            cal.next_session(date(2024, 1, 9))


class TestShift:
    def test_forward_one_session_is_not_plus_one_day(self, cal: TradingCalendar) -> None:
        """What a signal lag actually means."""
        assert cal.shift(date(2024, 1, 5), 1) == date(2024, 1, 8)

    def test_backward(self, cal: TradingCalendar) -> None:
        assert cal.shift(date(2024, 1, 8), -1) == date(2024, 1, 5)

    def test_zero_is_identity(self, cal: TradingCalendar) -> None:
        assert cal.shift(date(2024, 1, 3), 0) == date(2024, 1, 3)

    def test_shifting_from_a_non_session_is_an_error(self, cal: TradingCalendar) -> None:
        with pytest.raises(CalendarRangeError, match="not a trading session"):
            cal.shift(date(2024, 1, 4), 1)

    def test_shifting_past_the_end_is_an_error(self, cal: TradingCalendar) -> None:
        with pytest.raises(CalendarRangeError, match="outside the observed range"):
            cal.shift(date(2024, 1, 9), 5)


class TestRanges:
    def test_sessions_between_is_inclusive(self, cal: TradingCalendar) -> None:
        got = cal.sessions_between(date(2024, 1, 2), date(2024, 1, 5))
        assert got == (date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 5))

    def test_session_count(self, cal: TradingCalendar) -> None:
        assert cal.session_count(date(2024, 1, 1), date(2024, 1, 9)) == 6

    def test_reversed_range_is_an_error(self, cal: TradingCalendar) -> None:
        with pytest.raises(ValueError, match="precedes start"):
            cal.sessions_between(date(2024, 1, 9), date(2024, 1, 1))

    def test_missing_weekdays_finds_the_holiday(self, cal: TradingCalendar) -> None:
        """A calendar reporting no missing weekdays was built from a weekday rule."""
        assert cal.missing_weekdays() == (date(2024, 1, 4),)
