"""Trading calendar built from observed sessions, not from a holiday list.

A published holiday list is a secondary source: it can be stale, it omits
unscheduled closures, and it says nothing about special sessions. A date on
which the exchange actually published prices is ground truth.

So the calendar is constructed from dates seen in real market data - index
series today, bhavcopy once that lands - and it refuses to answer questions
outside the range it has observed rather than extrapolating.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from indian_equity_research.exceptions import IndianEquityResearchError

__all__ = ["CalendarRangeError", "TradingCalendar"]


class CalendarRangeError(IndianEquityResearchError):
    """A calendar question was asked about a date it has not observed."""


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    """Sessions the exchange actually held, in ascending order.

    Attributes:
        sessions: Observed trading dates, sorted and unique.
    """

    sessions: tuple[date, ...]

    def __post_init__(self) -> None:
        """Reject an empty or unsorted session list."""
        if not self.sessions:
            message = "A trading calendar needs at least one observed session."
            raise ValueError(message)
        if any(b <= a for a, b in pairwise(self.sessions)):
            message = "Sessions must be strictly increasing with no duplicates."
            raise ValueError(message)

    def __len__(self) -> int:
        """Return the number of observed sessions."""
        return len(self.sessions)

    @classmethod
    def from_dates(cls, dates: Iterable[date]) -> TradingCalendar:
        """Build a calendar from any iterable of observed dates.

        Args:
            dates: Dates on which the market traded. Duplicates and disorder
                are tolerated; the result is sorted and deduplicated.

        Returns:
            A calendar covering exactly those dates.

        Raises:
            ValueError: If no dates are supplied.
        """
        return cls(sessions=tuple(sorted(set(dates))))

    @property
    def first(self) -> date:
        """Earliest observed session."""
        return self.sessions[0]

    @property
    def last(self) -> date:
        """Latest observed session."""
        return self.sessions[-1]

    def covers(self, day: date) -> bool:
        """Whether ``day`` lies inside the observed range.

        Args:
            day: Date to test.

        Returns:
            ``True`` if the calendar can speak about this date at all.
        """
        return self.first <= day <= self.last

    def is_session(self, day: date) -> bool:
        """Whether the market traded on ``day``.

        Args:
            day: Date to test.

        Returns:
            ``True`` if a session was observed on that date.

        Raises:
            CalendarRangeError: If ``day`` is outside the observed range.
                Answering ``False`` would be indistinguishable from a genuine
                holiday, which is exactly the confusion this class exists to
                remove.
        """
        self._require_covered(day, "is_session")
        index = bisect_left(self.sessions, day)
        return index < len(self.sessions) and self.sessions[index] == day

    def previous_session(self, day: date, *, inclusive: bool = False) -> date:
        """Return the latest session on or before ``day``.

        Args:
            day: Reference date.
            inclusive: Whether ``day`` itself may be returned when it is a
                session.

        Returns:
            The preceding session date.

        Raises:
            CalendarRangeError: If no session exists at or before ``day``
                within the observed range.
        """
        index = bisect_right(self.sessions, day) if inclusive else bisect_left(self.sessions, day)
        if index == 0:
            message = (
                f"No session on or before {day.isoformat()}; the calendar starts "
                f"{self.first.isoformat()}."
            )
            raise CalendarRangeError(message)
        return self.sessions[index - 1]

    def next_session(self, day: date, *, inclusive: bool = False) -> date:
        """Return the earliest session on or after ``day``.

        Args:
            day: Reference date.
            inclusive: Whether ``day`` itself may be returned when it is a
                session.

        Returns:
            The following session date.

        Raises:
            CalendarRangeError: If no session exists at or after ``day``
                within the observed range.
        """
        index = bisect_left(self.sessions, day) if inclusive else bisect_right(self.sessions, day)
        if index >= len(self.sessions):
            message = (
                f"No session on or after {day.isoformat()}; the calendar ends "
                f"{self.last.isoformat()}."
            )
            raise CalendarRangeError(message)
        return self.sessions[index]

    def shift(self, day: date, sessions: int) -> date:
        """Move forward or backward a number of sessions.

        This is what a signal lag actually means: ``shift(decision_date, 1)``
        is the next date on which an order could trade, which is not
        ``decision_date + 1 day``.

        Args:
            day: Starting date. Must itself be a session.
            sessions: Number of sessions to move. Negative moves backwards.

        Returns:
            The resulting session date.

        Raises:
            CalendarRangeError: If ``day`` is not a session, or the shift lands
                outside the observed range.
        """
        self._require_covered(day, "shift")
        index = bisect_left(self.sessions, day)
        if index >= len(self.sessions) or self.sessions[index] != day:
            message = f"{day.isoformat()} is not a trading session."
            raise CalendarRangeError(message)
        target = index + sessions
        if not 0 <= target < len(self.sessions):
            message = (
                f"Shifting {sessions:+d} sessions from {day.isoformat()} falls outside "
                f"the observed range {self.first.isoformat()}..{self.last.isoformat()}."
            )
            raise CalendarRangeError(message)
        return self.sessions[target]

    def sessions_between(self, start: date, end: date) -> tuple[date, ...]:
        """Return every session in ``[start, end]``.

        Args:
            start: First date to consider, inclusive.
            end: Last date to consider, inclusive.

        Returns:
            Sessions in ascending order; empty if none fall in the range.

        Raises:
            ValueError: If ``end`` precedes ``start``.
        """
        if end < start:
            message = f"end ({end.isoformat()}) precedes start ({start.isoformat()})."
            raise ValueError(message)
        lo = bisect_left(self.sessions, start)
        hi = bisect_right(self.sessions, end)
        return self.sessions[lo:hi]

    def session_count(self, start: date, end: date) -> int:
        """Count sessions in ``[start, end]``.

        Args:
            start: First date, inclusive.
            end: Last date, inclusive.

        Returns:
            The number of sessions in range.
        """
        return len(self.sessions_between(start, end))

    def missing_weekdays(self) -> tuple[date, ...]:
        """Return weekdays inside the observed range that were **not** sessions.

        These are exchange holidays and unscheduled closures. Useful as a
        sanity check: a calendar that reports almost none has probably been
        built from a weekday rule rather than from observed data.

        Returns:
            Non-session weekdays, ascending.
        """
        held = set(self.sessions)
        out: list[date] = []
        day = self.first
        while day <= self.last:
            if day.weekday() < 5 and day not in held:
                out.append(day)
            day += timedelta(days=1)
        return tuple(out)

    def _require_covered(self, day: date, operation: str) -> None:
        """Raise if ``day`` lies outside the observed range.

        Args:
            day: Date being queried.
            operation: Name of the calling operation, for the message.

        Raises:
            CalendarRangeError: If the date is out of range.
        """
        if not self.covers(day):
            message = (
                f"{operation}({day.isoformat()}) is outside the observed calendar "
                f"{self.first.isoformat()}..{self.last.isoformat()}. Extend the "
                f"calendar rather than assuming a holiday."
            )
            raise CalendarRangeError(message)
