"""Assembling reference data from whatever is on disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from indian_equity_research.data.csv_series import CsvSeriesError
from indian_equity_research.market.reference import (
    build_reference,
    calendar_from_index_series,
)

# Mon-Wed and Fri of the first week of Jan 2024. Thursday 4th is a holiday.
INDEX_CSV = (
    "Date,Close\n"
    "01-Jan-2024,100\n02-Jan-2024,101\n03-Jan-2024,102\n05-Jan-2024,103\n08-Jan-2024,104\n"
)
EQUITY_CSV = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE,"
    " MARKET LOT, ISIN NUMBER, FACE VALUE\n"
    "AAA,Alpha Ltd,EQ,06-OCT-2008,5,1,INE111A01011,5\n"
    "BBB,Beta Ltd,BE,03-MAY-1995,10,1,INE222B01012,10\n"
)


def make_indices(root: Path) -> Path:
    d = root / "indices"
    d.mkdir(parents=True, exist_ok=True)
    (d / "nifty100_pr_2024.csv").write_text(INDEX_CSV, encoding="utf-8")
    return d


def make_archive(root: Path) -> Path:
    d = root / "archive" / "nse_equity_master"
    d.mkdir(parents=True, exist_ok=True)
    (d / "nse_equity_master_2026-08-07.csv").write_text(EQUITY_CSV, encoding="utf-8")
    return root / "archive"


class TestCalendarFromIndexSeries:
    def test_derives_sessions_from_observed_dates(self, tmp_path: Path) -> None:
        cal, source = calendar_from_index_series(make_indices(tmp_path))
        assert len(cal) == 5
        assert source == "Nifty 100 PR"

    def test_finds_the_midweek_holiday(self, tmp_path: Path) -> None:
        """The whole reason the calendar is observed rather than computed."""
        cal, _ = calendar_from_index_series(make_indices(tmp_path))
        from datetime import date

        assert cal.missing_weekdays() == (date(2024, 1, 4),)

    def test_falls_back_to_another_series(self, tmp_path: Path) -> None:
        d = tmp_path / "indices"
        d.mkdir(parents=True)
        (d / "india_vix_2024.csv").write_text(INDEX_CSV, encoding="utf-8")
        _, source = calendar_from_index_series(d)
        assert source == "India VIX"

    def test_no_series_at_all_is_an_error(self, tmp_path: Path) -> None:
        (tmp_path / "indices").mkdir()
        with pytest.raises(CsvSeriesError, match="No index series available"):
            calendar_from_index_series(tmp_path / "indices")


class TestBuildReference:
    def test_both_pieces_present(self, tmp_path: Path) -> None:
        make_indices(tmp_path)
        make_archive(tmp_path)
        ref = build_reference(tmp_path)
        assert ref.is_complete
        assert ref.calendar is not None
        assert ref.symbols is not None
        assert ref.latest_snapshot is not None

    def test_missing_calendar_is_reported_not_faked(self, tmp_path: Path) -> None:
        """A missing calendar must never degrade into a weekday rule."""
        make_archive(tmp_path)
        ref = build_reference(tmp_path)
        assert ref.calendar is None
        assert ref.calendar_problem
        assert ref.is_complete is False

    def test_missing_instruments_is_reported(self, tmp_path: Path) -> None:
        make_indices(tmp_path)
        ref = build_reference(tmp_path)
        assert ref.symbols is None
        assert "archive" in ref.instrument_problem
        assert ref.is_complete is False

    def test_nothing_present_reports_both(self, tmp_path: Path) -> None:
        ref = build_reference(tmp_path)
        assert ref.calendar_problem
        assert ref.instrument_problem
        assert ref.is_complete is False

    def test_trade_to_trade_series_is_visible(self, tmp_path: Path) -> None:
        make_indices(tmp_path)
        make_archive(tmp_path)
        ref = build_reference(tmp_path)
        assert ref.latest_snapshot is not None
        t2t = [r for r in ref.latest_snapshot.records.values() if r.is_trade_to_trade]
        assert [r.symbol for r in t2t] == ["BBB"]
