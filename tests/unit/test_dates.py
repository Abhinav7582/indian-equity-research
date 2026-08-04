"""Generic date utilities.

These helpers deliberately know nothing about exchange holidays. The tests
assert weekday behaviour only, and one test documents that limitation so that
nobody later mistakes these functions for a trading calendar.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from indian_equity_research.constants import INDIA_TZ
from indian_equity_research.utils.dates import (
    ensure_utc,
    is_weekend,
    next_weekday,
    now_ist,
    parse_iso_date,
    previous_weekday,
    to_ist,
    today_ist,
    weekday_range,
)

# 2024-04-01 was a Monday; 2024-04-06 a Saturday; 2024-04-07 a Sunday.
MONDAY = date(2024, 4, 1)
FRIDAY = date(2024, 4, 5)
SATURDAY = date(2024, 4, 6)
SUNDAY = date(2024, 4, 7)
NEXT_MONDAY = date(2024, 4, 8)


class TestWeekend:
    @pytest.mark.parametrize("day", [SATURDAY, SUNDAY])
    def test_weekend_days(self, day: date) -> None:
        assert is_weekend(day)

    @pytest.mark.parametrize("day", [MONDAY, FRIDAY])
    def test_weekdays(self, day: date) -> None:
        assert not is_weekend(day)


class TestPreviousWeekday:
    def test_from_sunday(self) -> None:
        assert previous_weekday(SUNDAY) == FRIDAY

    def test_from_monday_steps_back_to_friday(self) -> None:
        assert previous_weekday(NEXT_MONDAY) == FRIDAY

    def test_inclusive_returns_same_weekday(self) -> None:
        assert previous_weekday(FRIDAY, inclusive=True) == FRIDAY

    def test_inclusive_still_skips_a_weekend_day(self) -> None:
        assert previous_weekday(SATURDAY, inclusive=True) == FRIDAY


class TestNextWeekday:
    def test_from_friday(self) -> None:
        assert next_weekday(FRIDAY) == NEXT_MONDAY

    def test_from_saturday(self) -> None:
        assert next_weekday(SATURDAY) == NEXT_MONDAY

    def test_inclusive_returns_same_weekday(self) -> None:
        assert next_weekday(MONDAY, inclusive=True) == MONDAY


class TestWeekdayRange:
    def test_excludes_weekend_days(self) -> None:
        days = list(weekday_range(MONDAY, NEXT_MONDAY))
        assert SATURDAY not in days
        assert SUNDAY not in days

    def test_is_inclusive_of_both_endpoints(self) -> None:
        days = list(weekday_range(MONDAY, FRIDAY))
        assert days[0] == MONDAY
        assert days[-1] == FRIDAY
        assert len(days) == 5

    def test_single_weekday(self) -> None:
        assert list(weekday_range(MONDAY, MONDAY)) == [MONDAY]

    def test_single_weekend_day_yields_nothing(self) -> None:
        assert list(weekday_range(SATURDAY, SATURDAY)) == []

    def test_reversed_range_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="precedes start"):
            list(weekday_range(FRIDAY, MONDAY))

    def test_does_not_know_about_exchange_holidays(self) -> None:
        """Documents a limitation: a weekday is not necessarily a trading day.

        26 January 2024 (Republic Day) is a market holiday but a Friday. These
        helpers correctly report it as a weekday. Trading-calendar awareness
        arrives with the data-ingestion phase.
        """
        republic_day = date(2024, 1, 26)
        assert not is_weekend(republic_day)
        assert republic_day in list(weekday_range(republic_day, republic_day))


class TestTimezones:
    def test_ensure_utc_converts(self) -> None:
        ist_noon = datetime(2024, 4, 1, 12, 0, tzinfo=INDIA_TZ)
        converted = ensure_utc(ist_noon)
        assert converted.tzinfo is UTC
        assert converted.hour == 6
        assert converted.minute == 30

    def test_ensure_utc_rejects_naive(self) -> None:
        with pytest.raises(ValueError, match="Naive datetime"):
            ensure_utc(datetime(2024, 4, 1, 12, 0))  # noqa: DTZ001

    def test_to_ist_converts(self) -> None:
        utc_midnight = datetime(2024, 4, 1, 0, 0, tzinfo=UTC)
        converted = to_ist(utc_midnight)
        assert converted.hour == 5
        assert converted.minute == 30

    def test_to_ist_rejects_naive(self) -> None:
        with pytest.raises(ValueError, match="Naive datetime"):
            to_ist(datetime(2024, 4, 1, 12, 0))  # noqa: DTZ001

    def test_round_trip_preserves_the_instant(self) -> None:
        original = datetime(2024, 4, 1, 9, 15, tzinfo=INDIA_TZ)
        assert to_ist(ensure_utc(original)) == original

    def test_now_ist_is_aware_and_in_ist(self) -> None:
        moment = now_ist()
        assert moment.tzinfo is not None
        assert moment.utcoffset() == timedelta(hours=5, minutes=30)

    def test_today_ist_uses_ist_not_the_host_timezone(self) -> None:
        """A UTC host late in the day must not report yesterday's IST date."""
        assert today_ist() == datetime.now(tz=ZoneInfo("Asia/Kolkata")).date()


class TestParseIsoDate:
    def test_parses_a_valid_date(self) -> None:
        assert parse_iso_date("2024-04-01") == MONDAY

    def test_tolerates_surrounding_whitespace(self) -> None:
        assert parse_iso_date("  2024-04-01 ") == MONDAY

    @pytest.mark.parametrize("bad", ["01-04-2024", "2024/04/01", "not-a-date", "", "2024-13-01"])
    def test_rejects_invalid_input(self, bad: str) -> None:
        with pytest.raises(ValueError, match="ISO-8601"):
            parse_iso_date(bad)

    def test_error_names_the_offending_value(self) -> None:
        with pytest.raises(ValueError, match="01-04-2024"):
            parse_iso_date("01-04-2024")
