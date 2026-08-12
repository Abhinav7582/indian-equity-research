"""Tests for corporate-actions download planning.

Planning is tested rather than fetching: the fetch itself is a socket, and the
part that can be wrong without anyone noticing is the arithmetic that decides
which ranges get requested at all.
"""

from __future__ import annotations

import datetime as dt
from itertools import pairwise

import pytest

from indian_equity_research.ingest.corporate_actions_fetch import (
    FetchWindow,
    plan_windows,
    window_filename,
    window_url,
)


def test_the_full_project_range_is_a_manageable_number_of_requests() -> None:
    windows = plan_windows(dt.date(2015, 1, 1), dt.date(2026, 8, 5))
    assert len(windows) == 47
    assert windows[0].start == dt.date(2015, 1, 1)
    assert windows[-1].end == dt.date(2026, 8, 5)


def test_windows_are_contiguous_and_leave_no_day_uncovered() -> None:
    """A one-day gap between quarters would drop every action on that day.

    Nothing downstream could detect it: the archive would simply not contain
    a split that happened.
    """
    windows = plan_windows(dt.date(2015, 1, 1), dt.date(2026, 12, 31))
    # itertools.pairwise, not zip(w, w[1:], strict=True) -- the strict form
    # raises on every input, because the tail is always one shorter. This is
    # the FOURTH time that exact mistake has been made in this repository
    # (market/calendar.py, research/series.py, backtest/engine.py), and the
    # third of those already carries a comment saying so.
    for earlier, later in pairwise(windows):
        assert later.start == earlier.end + dt.timedelta(days=1)


def test_quarter_ends_are_correct_including_leap_years() -> None:
    windows = plan_windows(dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [w.end for w in windows] == [
        dt.date(2020, 3, 31),
        dt.date(2020, 6, 30),
        dt.date(2020, 9, 30),
        dt.date(2020, 12, 31),
    ]


def test_a_range_starting_mid_quarter_is_clipped() -> None:
    """Otherwise the first request quietly pulls in earlier actions."""
    windows = plan_windows(dt.date(2020, 2, 14), dt.date(2020, 5, 3))
    assert windows[0].start == dt.date(2020, 2, 14)
    assert windows[0].end == dt.date(2020, 3, 31)
    assert windows[-1].end == dt.date(2020, 5, 3)


def test_a_single_day_range_is_one_window() -> None:
    windows = plan_windows(dt.date(2020, 5, 3), dt.date(2020, 5, 3))
    assert len(windows) == 1
    assert windows[0].start == windows[0].end == dt.date(2020, 5, 3)


def test_a_reversed_range_is_refused() -> None:
    with pytest.raises(ValueError, match="precedes start"):
        plan_windows(dt.date(2020, 5, 3), dt.date(2020, 1, 1))
    with pytest.raises(ValueError, match=r"ends .* before it starts"):
        FetchWindow(dt.date(2020, 5, 3), dt.date(2020, 1, 1))


def test_the_url_uses_the_query_date_format_not_the_response_one() -> None:
    """NSE writes DD-MM-YYYY in the query and DD-Mon-YYYY in the response.

    Sending the response format returns an empty array, not an error -- which
    reads as a quarter with no corporate actions.
    """
    url = window_url(FetchWindow(dt.date(2020, 1, 1), dt.date(2020, 3, 31)))
    assert "from_date=01-01-2020" in url
    assert "to_date=31-03-2020" in url
    assert "Jan" not in url


def test_the_filename_distinguishes_a_clipped_window_from_a_full_one() -> None:
    full = window_filename(FetchWindow(dt.date(2020, 1, 1), dt.date(2020, 3, 31)))
    clipped = window_filename(FetchWindow(dt.date(2020, 2, 14), dt.date(2020, 3, 31)))
    assert full != clipped
    assert full == "ca_2020Q1_2020-01-01_2020-03-31.json"
