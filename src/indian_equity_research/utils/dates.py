"""Generic date and time helpers.

Scope note
----------
These helpers know about calendar weekends and Indian Standard Time. They do
**not** know about exchange holidays, settlement cycles or trading sessions.
A weekday is not necessarily a trading day.

The NSE/BSE trading calendar is sourced data, not a hardcoded list, and
belongs to the data-ingestion phase. Nothing here should be mistaken for a
trading calendar.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

from indian_equity_research.constants import INDIA_TZ

__all__ = [
    "SATURDAY",
    "SUNDAY",
    "ensure_utc",
    "is_weekend",
    "next_weekday",
    "now_ist",
    "parse_iso_date",
    "previous_weekday",
    "to_ist",
    "today_ist",
    "weekday_range",
]

SATURDAY = 5
SUNDAY = 6


def now_ist() -> datetime:
    """Return the current time as a timezone-aware IST datetime."""
    return datetime.now(tz=INDIA_TZ)


def today_ist() -> date:
    """Return today's date in Indian Standard Time.

    Using IST rather than the host timezone avoids an off-by-one-day defect
    when the machine runs in UTC and the local time is past 18:30 UTC.
    """
    return now_ist().date()


def ensure_utc(moment: datetime) -> datetime:
    """Convert an aware datetime to UTC, rejecting naive input.

    Args:
        moment: A timezone-aware datetime.

    Returns:
        The same instant expressed in UTC.

    Raises:
        ValueError: If ``moment`` has no timezone. Naive datetimes are
            ambiguous and are treated as a defect rather than assumed to be
            local time.
    """
    if moment.tzinfo is None:
        message = "Naive datetime rejected: attach a timezone before converting."
        raise ValueError(message)
    return moment.astimezone(UTC)


def to_ist(moment: datetime) -> datetime:
    """Convert an aware datetime to Indian Standard Time.

    Args:
        moment: A timezone-aware datetime.

    Returns:
        The same instant expressed in IST.

    Raises:
        ValueError: If ``moment`` has no timezone.
    """
    if moment.tzinfo is None:
        message = "Naive datetime rejected: attach a timezone before converting."
        raise ValueError(message)
    return moment.astimezone(INDIA_TZ)


def is_weekend(day: date) -> bool:
    """Return whether the given date falls on a Saturday or Sunday.

    Args:
        day: The date to test.

    Returns:
        ``True`` for Saturday and Sunday.
    """
    return day.weekday() in (SATURDAY, SUNDAY)


def previous_weekday(day: date, *, inclusive: bool = False) -> date:
    """Return the nearest weekday on or before ``day``.

    Args:
        day: Reference date.
        inclusive: If ``True`` and ``day`` is already a weekday, return it
            unchanged. Otherwise always step back at least one day.

    Returns:
        A date that is not a Saturday or Sunday.
    """
    candidate = day if inclusive else day - timedelta(days=1)
    while is_weekend(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_weekday(day: date, *, inclusive: bool = False) -> date:
    """Return the nearest weekday on or after ``day``.

    Args:
        day: Reference date.
        inclusive: If ``True`` and ``day`` is already a weekday, return it
            unchanged. Otherwise always step forward at least one day.

    Returns:
        A date that is not a Saturday or Sunday.
    """
    candidate = day if inclusive else day + timedelta(days=1)
    while is_weekend(candidate):
        candidate += timedelta(days=1)
    return candidate


def weekday_range(start: date, end: date) -> Iterator[date]:
    """Yield every weekday from ``start`` to ``end`` inclusive.

    Args:
        start: First date to consider.
        end: Last date to consider.

    Yields:
        Each date in the range that is not a Saturday or Sunday.

    Raises:
        ValueError: If ``end`` precedes ``start``.
    """
    if end < start:
        message = f"end ({end.isoformat()}) precedes start ({start.isoformat()})."
        raise ValueError(message)
    current = start
    while current <= end:
        if not is_weekend(current):
            yield current
        current += timedelta(days=1)


def parse_iso_date(value: str) -> date:
    """Parse a ``YYYY-MM-DD`` string into a date.

    Args:
        value: An ISO-8601 calendar date.

    Returns:
        The parsed date.

    Raises:
        ValueError: If the string is not a valid ISO-8601 date. The message
            names the offending input so failures are diagnosable.
    """
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        message = f"Expected an ISO-8601 date such as 2024-04-01, got {value!r}."
        raise ValueError(message) from exc
