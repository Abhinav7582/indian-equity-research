"""Tests for belief checking.

The two that matter most are :func:`test_a_short_comparator_is_refused` and
:func:`test_a_confirmation_reaching_back_into_the_first_window_is_refused`.
Both guard against a *plausible number* rather than a crash, which is the
failure mode every defect found in Phase 4 shared.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pytest

from indian_equity_research.research.beliefs import (
    BeliefError,
    ComparatorTooShort,
    Series,
    WindowsNotIndependent,
    check_belief,
    confirm_on_second_window,
    load_index_series,
)

START = dt.date(2005, 1, 3)


def daily(first: dt.date, days: int, per_day: float, base: float = 1000.0) -> dict[dt.date, float]:
    """A series compounding at a fixed daily rate, one point per calendar day."""
    return {first + dt.timedelta(days=i): base * (1 + per_day) ** i for i in range(days)}


def series(name: str, per_day: float, days: int = 4000, first: dt.date = START) -> Series:
    return Series(name=name, levels=daily(first, days, per_day))


# ---------------------------------------------------------------------------
# The guards that raise
# ---------------------------------------------------------------------------


def test_a_short_comparator_is_refused() -> None:
    """A 21-year claim must not be answered from 11 years of comparator data.

    This is the defect A13 rule 5 exists for, and it is invisible in the output:
    the check would return a full distribution, a percentile and a hit rate, all
    correctly computed over a window nobody asked about.
    """
    subject = series("Subject", 0.0004)
    late = Series(
        name="Comparator",
        levels=daily(START + dt.timedelta(days=2000), 2000, 0.0003),
    )
    with pytest.raises(ComparatorTooShort, match="answer it from the shorter history"):
        check_belief("anything", subject, late)


def test_a_comparator_shorter_by_less_than_one_horizon_is_allowed() -> None:
    """The guard must not fire on a series that merely starts a few days later.

    Refusing every imperfect overlap would make the checker unusable, and the
    first horizon of windows is unmeasurable regardless of which series is
    shorter.
    """
    subject = series("Subject", 0.0004)
    slightly_late = Series(
        name="Comparator", levels=daily(START + dt.timedelta(days=30), 3900, 0.0003)
    )
    result = check_belief("fine", subject, slightly_late, horizon_months=12)
    assert result.observations > 0


def test_a_confirmation_must_use_the_same_pair() -> None:
    """Swapping a series turns a confirmation into a different question."""
    subject, comparator = series("Subject", 0.0004), series("Comparator", 0.0003)
    first = check_belief("claim", subject, comparator)
    with pytest.raises(BeliefError, match="new claim, not a confirmation"):
        confirm_on_second_window(
            first,
            series("Something Else", 0.0004),
            comparator,
            dt.date(2014, 1, 1),
            dt.date(2015, 1, 1),
        )


def test_a_confirmation_reaching_back_into_the_first_window_is_refused() -> None:
    """A confirmation starting one day later still reads a year of shared data.

    This is the subtle case. The naive check — comparing the two start dates —
    passes it, because the confirmation's *first window close* is after the
    first check ends. But that window **opens** twelve months earlier, inside
    the period being confirmed. The two checks would share a year of
    observations while reporting themselves as independent.
    """
    subject, comparator = series("Subject", 0.0004), series("Comparator", 0.0003)
    first = check_belief("claim", subject, comparator, horizon_months=12)
    just_after = first.last_session + dt.timedelta(days=1)
    with pytest.raises(WindowsNotIndependent, match="agreeing with itself"):
        confirm_on_second_window(
            first, subject, comparator, just_after, just_after + dt.timedelta(days=200)
        )


def test_a_genuinely_separated_confirmation_is_allowed() -> None:
    """Non-overlapping windows are what rule 3 asks for, and must work."""
    subject, comparator = (
        series("Subject", 0.0004, days=6000),
        series("Comparator", 0.0003, days=6000),
    )
    first = check_belief("claim", subject, comparator, horizon_months=12, end=dt.date(2012, 1, 1))
    second = confirm_on_second_window(
        first, subject, comparator, dt.date(2014, 1, 1), dt.date(2016, 1, 1)
    )
    assert second.observations > 0
    assert second.first_session > first.last_session


def test_a_non_positive_horizon_is_refused() -> None:
    subject, comparator = series("Subject", 0.0004), series("Comparator", 0.0003)
    with pytest.raises(BeliefError, match="must be positive"):
        check_belief("claim", subject, comparator, horizon_months=0)


# ---------------------------------------------------------------------------
# The statistics
# ---------------------------------------------------------------------------


def test_a_series_that_always_wins_reports_a_hit_rate_of_one() -> None:
    """A subject compounding faster every single day must never lose a window."""
    result = check_belief("always", series("Subject", 0.0004), series("Comparator", 0.0002))
    assert result.hit_rate == 1.0
    assert result.mean_win > 0
    assert result.mean_loss == 0.0


def test_the_independent_count_is_far_below_the_window_count() -> None:
    """Overlapping windows must not be presented as independent evidence.

    Ten years of daily one-year windows is about 2,500 windows and about ten
    genuinely independent observations. Reporting the first number as the sample
    size is how a noisy result acquires a decisive-looking denominator.
    """
    result = check_belief(
        "claim", series("Subject", 0.0004), series("Comparator", 0.0003), horizon_months=12
    )
    assert result.observations > 2000
    assert result.independent_observations < 15
    assert result.independent_observations > 8


def accelerating(first: dt.date, days: int, base_rate: float, accel: float) -> dict[dt.date, float]:
    """A series whose daily growth rate rises, so later windows return more."""
    levels, level = {}, 1000.0
    for i in range(days):
        levels[first + dt.timedelta(days=i)] = level
        level *= 1 + base_rate + accel * i
    return levels


def test_a_gap_that_is_widening_puts_today_at_the_top() -> None:
    """If the subject's edge grows window on window, today must be the extreme.

    The anchor for the percentile: a series built so that now is the most
    unusual point it has ever been must come back at 100.
    """
    subject = Series("Subject", accelerating(START, 3000, 0.0001, 2e-7))
    result = check_belief("widening", subject, series("Comparator", 0.0001, days=3000))
    assert result.percentile == pytest.approx(100.0)


def test_two_steady_compounders_have_no_distribution_to_sit_in() -> None:
    """Fixed growth rates give an identical relative return in *every* window.

    Worth pinning down because it is counter-intuitive and it caught this
    project's own test author: the level gap between two fixed compounders
    widens without limit, but the gap *measured over a fixed-length window* is
    the same every time. A percentile is only meaningful where the distribution
    has spread, and here it has none — so the spread, not the percentile, is
    what a reader must check first.
    """
    result = check_belief("steady", series("Subject", 0.0005), series("Comparator", 0.0001))
    assert result.quantile(0.05) == pytest.approx(result.quantile(0.95), abs=5e-4)


def test_windows_are_measured_on_sessions_both_series_share() -> None:
    """A session missing from one series must not be read from the other.

    Otherwise the two sides are measured over different sets of trading days and
    the difference is attributed to the indices rather than to the calendar.
    """
    subject = series("Subject", 0.0004, days=2000)
    thinned = {
        day: level
        for day, level in series("Comparator", 0.0003, days=2000).levels.items()
        if day.weekday() != 2
    }
    result = check_belief("claim", subject, Series("Comparator", thinned))
    assert all(window.end.weekday() != 2 for window in result.windows)
    assert all(window.start.weekday() != 2 for window in result.windows)


def test_relative_return_is_the_difference_of_simple_returns() -> None:
    """A claim of "beat it by 2%" means the difference, and the code must too."""
    subject = Series("Subject", {dt.date(2020, 1, 1): 100.0, dt.date(2021, 1, 1): 120.0})
    comparator = Series("Comparator", {dt.date(2020, 1, 1): 50.0, dt.date(2021, 1, 1): 55.0})
    result = check_belief("claim", subject, comparator, horizon_months=12)
    assert result.latest.relative == pytest.approx(0.20 - 0.10)


def test_the_result_carries_no_verdict_field() -> None:
    """A13 rule 1: this describes, it does not recommend.

    A boolean named ``supported`` or a field naming a weight would be read as
    advice no matter how it were documented, so the guard is that no such field
    exists to be read.
    """
    result = check_belief("claim", series("Subject", 0.0004), series("Comparator", 0.0003))
    forbidden = {"supported", "verdict", "recommendation", "allocation", "weight", "target"}
    assert not forbidden & set(dir(result))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def write_tri(directory: Path, index: str, rows: list[tuple[str, str]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{index.lower().replace(' ', '')}_{rows[0][0][-4:]}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["IndexName", "Date", "Total Returns Index"])
        for when, value in rows:
            writer.writerow([index, when, value])


def test_two_indices_in_one_folder_are_refused(tmp_path: Path) -> None:
    """Mixed indices would build a level series that jumps between scales.

    Every jump would then be read as a return, and the distribution would be
    made of the jumps rather than of the market.
    """
    write_tri(tmp_path, "NIFTY MIDCAP 150", [("01 Jan 2020", "100")])
    write_tri(tmp_path / "x", "NIFTY SMALLCAP 250", [("02 Jan 2020", "200")])
    for path in (tmp_path / "x").glob("*.csv"):
        path.rename(tmp_path / path.name)
    with pytest.raises(BeliefError, match="more than one index"):
        load_index_series(tmp_path)


def test_a_price_return_download_is_refused(tmp_path: Path) -> None:
    """NSE serves price returns from a different page, without the TRI column.

    Downloading the wrong section is a mistake this project has already made
    once, and the resulting file parses to zero usable rows rather than failing
    loudly on its own.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    with (tmp_path / "wrong_2020.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Index Name", "Date", "Open", "High", "Low", "Close"])
        writer.writerow(["NIFTY MIDCAP 150", "01 Jan 2020", "1", "2", "3", "4"])
    with pytest.raises(BeliefError, match="Total Returns Index"):
        load_index_series(tmp_path)


def test_an_empty_folder_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BeliefError, match="not there"):
        load_index_series(tmp_path / "nothing")
