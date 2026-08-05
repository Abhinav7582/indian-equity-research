"""CSV loading: tolerant about formatting, strict about anything that corrupts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from indian_equity_research.data.csv_series import CsvSeriesError, load_price_series


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


class TestFormatTolerance:
    @pytest.mark.parametrize(
        "raw_date",
        ["01-Jan-2021", "01 Jan 2021", "01-01-2021", "01/01/2021", "2021-01-01"],
    )
    def test_accepts_known_date_formats(self, tmp_path: Path, raw_date: str) -> None:
        path = write(tmp_path, "s.csv", f"Date,Close\n{raw_date},100.5\n")
        assert load_price_series(path, "S").dates == (date(2021, 1, 1),)

    def test_strips_thousands_separators(self, tmp_path: Path) -> None:
        path = write(tmp_path, "s.csv", 'Date,Close\n01-Jan-2021,"24,850.75"\n')
        assert load_price_series(path, "S").closes == (24850.75,)

    @pytest.mark.parametrize(
        "column", ["Close", "Closing Value", "Total Returns Index", "Index Value"]
    )
    def test_detects_alternative_value_columns(self, tmp_path: Path, column: str) -> None:
        path = write(tmp_path, "s.csv", f"Date,{column}\n01-Jan-2021,100\n")
        assert load_price_series(path, "S").closes == (100.0,)

    def test_handles_a_utf8_bom(self, tmp_path: Path) -> None:
        path = tmp_path / "s.csv"
        path.write_text("Date,Close\n01-Jan-2021,100\n", encoding="utf-8-sig")
        assert len(load_price_series(path, "S")) == 1

    def test_sorts_rows_by_date(self, tmp_path: Path) -> None:
        path = write(
            tmp_path,
            "s.csv",
            "Date,Close\n03-Jan-2021,102\n01-Jan-2021,100\n02-Jan-2021,101\n",
        )
        assert load_price_series(path, "S").closes == (100.0, 101.0, 102.0)

    def test_ignores_blank_trailing_rows(self, tmp_path: Path) -> None:
        path = write(tmp_path, "s.csv", "Date,Close\n01-Jan-2021,100\n,\n")
        assert len(load_price_series(path, "S")) == 1

    def test_explicit_column_names_override_detection(self, tmp_path: Path) -> None:
        path = write(tmp_path, "s.csv", "When,Level\n01-Jan-2021,100\n")
        s = load_price_series(path, "S", date_column="When", value_column="Level")
        assert s.closes == (100.0,)


class TestStrictness:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(CsvSeriesError, match="no such file"):
            load_price_series(tmp_path / "absent.csv", "S")

    def test_empty_file(self, tmp_path: Path) -> None:
        with pytest.raises(CsvSeriesError, match="no header row"):
            load_price_series(write(tmp_path, "s.csv", ""), "S")

    def test_header_only(self, tmp_path: Path) -> None:
        with pytest.raises(CsvSeriesError, match="no usable rows"):
            load_price_series(write(tmp_path, "s.csv", "Date,Close\n"), "S")

    def test_unknown_date_column(self, tmp_path: Path) -> None:
        with pytest.raises(CsvSeriesError, match="No date column"):
            load_price_series(write(tmp_path, "s.csv", "Foo,Close\n1,2\n"), "S")

    def test_unknown_value_column(self, tmp_path: Path) -> None:
        with pytest.raises(CsvSeriesError, match="No value column"):
            load_price_series(write(tmp_path, "s.csv", "Date,Bar\n01-Jan-2021,2\n"), "S")

    def test_unparseable_date_names_the_line(self, tmp_path: Path) -> None:
        path = write(tmp_path, "s.csv", "Date,Close\n01-Jan-2021,100\nJan 1 2021,101\n")
        with pytest.raises(CsvSeriesError, match="line 3"):
            load_price_series(path, "S")

    def test_non_numeric_value_names_the_line(self, tmp_path: Path) -> None:
        path = write(tmp_path, "s.csv", "Date,Close\n01-Jan-2021,abc\n")
        with pytest.raises(CsvSeriesError, match="line 2"):
            load_price_series(path, "S")

    def test_duplicate_dates_rejected(self, tmp_path: Path) -> None:
        """Silently keeping one of two values for a date would corrupt returns."""
        path = write(tmp_path, "s.csv", "Date,Close\n01-Jan-2021,100\n01-Jan-2021,101\n")
        with pytest.raises(CsvSeriesError, match="duplicate date"):
            load_price_series(path, "S")

    def test_non_positive_value_rejected(self, tmp_path: Path) -> None:
        path = write(tmp_path, "s.csv", "Date,Close\n01-Jan-2021,0\n")
        with pytest.raises(CsvSeriesError, match="invalid series"):
            load_price_series(path, "S")
