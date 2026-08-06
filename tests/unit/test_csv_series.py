"""CSV loading: tolerant about formatting, strict about anything that corrupts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from indian_equity_research.data.csv_series import (
    CsvSeriesError,
    load_price_series,
    load_price_series_glob,
)


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


class TestGlobMerge:
    """Year-by-year downloads must merge safely."""

    def test_merges_several_files_in_date_order(self, tmp_path: Path) -> None:
        write(tmp_path, "x_2020.csv", "Date,Close\n01-Jan-2020,100\n02-Jan-2020,101\n")
        write(tmp_path, "x_2021.csv", "Date,Close\n01-Jan-2021,110\n")
        s = load_price_series_glob(tmp_path, "x_*.csv", "X")
        assert len(s) == 3
        assert s.closes == (100.0, 101.0, 110.0)

    def test_tolerates_overlapping_ranges_that_agree(self, tmp_path: Path) -> None:
        write(tmp_path, "x_a.csv", "Date,Close\n01-Jan-2020,100\n02-Jan-2020,101\n")
        write(tmp_path, "x_b.csv", "Date,Close\n02-Jan-2020,101\n03-Jan-2020,102\n")
        assert len(load_price_series_glob(tmp_path, "x_*.csv", "X")) == 3

    def test_rejects_overlapping_ranges_that_disagree(self, tmp_path: Path) -> None:
        """Two files claiming different closes for one date is a real error."""
        write(tmp_path, "x_a.csv", "Date,Close\n02-Jan-2020,101\n")
        write(tmp_path, "x_b.csv", "Date,Close\n02-Jan-2020,999\n")
        with pytest.raises(CsvSeriesError, match="conflicting values"):
            load_price_series_glob(tmp_path, "x_*.csv", "X")

    def test_conflict_message_names_both_files(self, tmp_path: Path) -> None:
        write(tmp_path, "x_a.csv", "Date,Close\n02-Jan-2020,101\n")
        write(tmp_path, "x_b.csv", "Date,Close\n02-Jan-2020,999\n")
        with pytest.raises(CsvSeriesError) as exc:
            load_price_series_glob(tmp_path, "x_*.csv", "X")
        assert "x_a.csv" in str(exc.value)
        assert "x_b.csv" in str(exc.value)

    def test_single_file_still_works(self, tmp_path: Path) -> None:
        write(tmp_path, "x.csv", "Date,Close\n01-Jan-2020,100\n")
        assert len(load_price_series_glob(tmp_path, "x*.csv", "X")) == 1

    def test_no_match_names_the_pattern(self, tmp_path: Path) -> None:
        with pytest.raises(CsvSeriesError, match="no files matching"):
            load_price_series_glob(tmp_path, "absent*.csv", "X")


class TestRealNseIndicesFormats:
    """Samples of the shapes niftyindices.com actually exports.

    Kept as regression tests so a future refactor of the loader cannot
    silently stop reading the files this project depends on.
    """

    def test_hybrid_index_with_placeholder_ohl(self, tmp_path: Path) -> None:
        """Multi-asset indices publish only a close; OHL come through as '-'."""
        path = write(
            tmp_path,
            "blend.csv",
            "Index Name,Index Date,Open Index Value,High Index Value,"
            "Low Index Value,Closing Index Value\n"
            "NIFTY200 MOMENTUM 30 PLUS 8-13 YR G-SEC 75:25,31 Dec 2021,-,-,-,5789.57\n"
            "NIFTY200 MOMENTUM 30 PLUS 8-13 YR G-SEC 75:25,30 Dec 2021,-,-,-,5743.48\n",
        )
        s = load_price_series(path, "Blend")
        assert len(s) == 2
        assert s.closes == (5743.48, 5789.57)

    def test_equity_index_with_separators_and_extra_columns(self, tmp_path: Path) -> None:
        path = write(
            tmp_path,
            "n100.csv",
            "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
            "Closing Index Value,Points Change,Change(%),P/E,P/B,Div Yield\n"
            'NIFTY 100,01-Jan-2021,"13,981.95","14,049.85","13,951.70","14,018.50",'
            "36.55,0.26,33.42,3.85,1.05\n",
        )
        assert load_price_series(path, "N100").closes == (14018.50,)

    def test_rows_exported_newest_first_are_reordered(self, tmp_path: Path) -> None:
        """The site lists most recent first; the series must still be ascending."""
        path = write(
            tmp_path,
            "x.csv",
            "Index Date,Closing Index Value\n31 Dec 2021,300\n30 Dec 2021,200\n29 Dec 2021,100\n",
        )
        s = load_price_series(path, "X")
        assert s.closes == (100.0, 200.0, 300.0)
        assert s.dates[0] < s.dates[-1]

    def test_finds_files_in_subdirectories(self, tmp_path: Path) -> None:
        """Downloads are often grouped one folder per series."""
        (tmp_path / "series_a").mkdir()
        write(tmp_path / "series_a", "x_2020.csv", "Date,Close\n01-Jan-2020,100\n")
        write(tmp_path / "series_a", "x_2021.csv", "Date,Close\n01-Jan-2021,110\n")
        assert len(load_price_series_glob(tmp_path, "x_*.csv", "X")) == 2

    def test_does_not_cross_match_similar_prefixes(self, tmp_path: Path) -> None:
        """`..._tri*` must not pick up `..._gsec_7525*` from a sibling folder."""
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        write(tmp_path / "a", "mom30_tri_2020.csv", "Date,Close\n01-Jan-2020,100\n")
        write(tmp_path / "b", "mom30_gsec_7525_2020.csv", "Date,Close\n01-Jan-2020,999\n")
        s = load_price_series_glob(tmp_path, "mom30_tri*.csv", "TRI")
        assert s.closes == (100.0,)
