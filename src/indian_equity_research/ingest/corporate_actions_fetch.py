"""Plan and fetch NSE's corporate-actions feed.

The endpoint takes a date range and returns JSON:

    https://www.nseindia.com/api/corporates-corporateActions
        ?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY

Quarterly windows, not yearly
-----------------------------
A quarter returns roughly 55 KB and a few hundred rows. NSE has never
documented a row cap, which is precisely the reason not to ask for a year: an
undocumented cap does not announce itself. It returns a short response that
looks exactly like a quiet period, and the actions past the limit are simply
absent from the archive with nothing to indicate they were ever expected.

Quarterly windows for 2015-2026 come to about 47 requests. At the usual delay
that is a couple of minutes, which is not worth trading for a risk that cannot
be detected after the fact.

The cookie requirement
----------------------
``nseindia.com`` rejects requests that arrive without the cookies a browser
would have obtained from the site first. The failure is not an HTTP error: the
server returns **200 with an HTML challenge page**, which JSON parsing then
rejects halfway through a run. :func:`~indian_equity_research.market.
nse_corporate_actions.load_actions_json` names that case explicitly rather than
surfacing a bare decoder error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

__all__ = [
    "CORPORATE_ACTIONS_URL",
    "FetchWindow",
    "plan_windows",
    "window_filename",
    "window_url",
]

CORPORATE_ACTIONS_URL: Final = "https://www.nseindia.com/api/corporates-corporateActions"

# NSE writes dates DD-MM-YYYY in the query and DD-Mon-YYYY in the response.
# They are different formats in the same API; both are handled where they occur.
_QUERY_DATE: Final = "%d-%m-%Y"


@dataclass(frozen=True, slots=True)
class FetchWindow:
    """One quarter to request."""

    start: date
    end: date

    def __post_init__(self) -> None:
        """Reject a window that cannot describe a real range."""
        if self.end < self.start:
            raise ValueError(f"window ends {self.end} before it starts {self.start}")

    @property
    def label(self) -> str:
        """``2020Q1`` style label, used in filenames."""
        return f"{self.start.year}Q{(self.start.month - 1) // 3 + 1}"


def _quarter_end(year: int, quarter: int) -> date:
    """Last day of a quarter."""
    month = quarter * 3
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def plan_windows(start: date, end: date) -> list[FetchWindow]:
    """Quarterly windows covering ``[start, end]``.

    The first and last are clipped to the requested bounds, so a range that
    begins mid-quarter does not silently pull in earlier actions.

    Args:
        start: First date wanted.
        end: Last date wanted.

    Returns:
        Windows in chronological order.

    Raises:
        ValueError: if ``end`` precedes ``start``.
    """
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")

    windows: list[FetchWindow] = []
    year, quarter = start.year, (start.month - 1) // 3 + 1
    while True:
        q_start = date(year, (quarter - 1) * 3 + 1, 1)
        q_end = _quarter_end(year, quarter)
        if q_start > end:
            break
        windows.append(FetchWindow(max(q_start, start), min(q_end, end)))
        quarter += 1
        if quarter > 4:
            quarter, year = 1, year + 1
    return windows


def window_url(window: FetchWindow) -> str:
    """Request URL for one window."""
    return (
        f"{CORPORATE_ACTIONS_URL}?index=equities"
        f"&from_date={window.start.strftime(_QUERY_DATE)}"
        f"&to_date={window.end.strftime(_QUERY_DATE)}"
    )


def window_filename(window: FetchWindow) -> str:
    """Filename to save a window under.

    Carries the exact dates, not just the quarter label, so a clipped first or
    last window is distinguishable from a full one on disk.
    """
    return f"ca_{window.label}_{window.start.isoformat()}_{window.end.isoformat()}.json"
