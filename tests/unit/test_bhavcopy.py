"""Bhavcopy parsing across the July 2024 format change.

The important test in this file is
``TestFormatBoundary::test_both_layouts_produce_identical_records`` - the same
session expressed in both layouts must normalise to byte-identical records.
Without that, the changeover becomes a silent discontinuity in every price
series that spans it.
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from indian_equity_research.market.bhavcopy import (
    UDIFF_EFFECTIVE_FROM,
    BhavcopyError,
    BhavFormat,
    BhavRecord,
    detect_format,
    parse_bhavcopy,
    read_bhavcopy_file,
    series_by_isin,
    series_for_isin,
)

LEGACY_HEADER = (
    "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,"
    "TIMESTAMP,TOTALTRADES,ISIN,\n"
)
LEGACY_ROWS = (
    "RELIANCE,EQ,2900.00,2950.00,2880.00,2940.00,2941.00,2895.00,"
    "5000000,14700000000.00,05-JUL-2024,120000,INE002A01018,\n"
    "TCS,EQ,3900.00,3950.00,3880.00,3910.00,3911.00,3905.00,"
    "1000000,3910000000.00,05-JUL-2024,60000,INE467B01029,\n"
    "SOMEBOND,N1,100.00,100.00,100.00,100.00,100.00,100.00,"
    "10,1000.00,05-JUL-2024,2,INE999X01011,\n"
)

UDIFF_HEADER = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,"
    "FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,"
    "LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,"
    "TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
)
UDIFF_ROWS = (
    "2024-07-05,2024-07-05,CM,NSE,STK,2885,INE002A01018,RELIANCE,EQ,,,,,RELIANCE,"
    "2900.00,2950.00,2880.00,2940.00,2941.00,2895.00,,,,,5000000,14700000000.00,"
    "120000,F1,1,,,,,\n"
    "2024-07-05,2024-07-05,CM,NSE,STK,11536,INE467B01029,TCS,EQ,,,,,TCS,"
    "3900.00,3950.00,3880.00,3910.00,3911.00,3905.00,,,,,1000000,3910000000.00,"
    "60000,F1,1,,,,,\n"
    "2024-07-05,2024-07-05,FO,NSE,IDF,1,INE000000000,NIFTY,XX,2024-07-25,,,,NIFTY,"
    "24000,24100,23900,24050,24050,23990,,,,,1,1,1,F1,50,,,,,\n"
)


class TestFormatDetection:
    def test_detects_legacy(self) -> None:
        assert detect_format(LEGACY_HEADER.strip().split(",")) is BhavFormat.LEGACY

    def test_detects_udiff(self) -> None:
        assert detect_format(UDIFF_HEADER.strip().split(",")) is BhavFormat.UDIFF

    def test_detection_is_by_content_not_filename(self) -> None:
        """A republished or renamed file must still be read correctly."""
        records = parse_bhavcopy(UDIFF_HEADER + UDIFF_ROWS)
        assert records[0].trade_date == date(2024, 7, 5)

    def test_unknown_header_is_rejected(self) -> None:
        with pytest.raises(BhavcopyError, match="neither the legacy nor the UDiFF"):
            detect_format(["FOO", "BAR"])


class TestLegacyParsing:
    def test_parses_cash_equities(self) -> None:
        records = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)
        assert [r.symbol for r in records] == ["RELIANCE", "TCS"]

    def test_excludes_non_equity_series(self) -> None:
        """N1 is a debt series and must not enter a price table."""
        records = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)
        assert all(r.series in {"EQ", "BE", "BZ"} for r in records)

    def test_field_mapping(self) -> None:
        record = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)[0]
        assert record.isin == "INE002A01018"
        assert record.trade_date == date(2024, 7, 5)
        assert record.open == 2900.0
        assert record.close == 2940.0
        assert record.previous_close == 2895.0
        assert record.volume == 5_000_000
        assert record.trades == 120_000

    def test_trailing_comma_in_the_header_is_tolerated(self) -> None:
        assert len(parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)) == 2


class TestUdiffParsing:
    def test_parses_cash_equities(self) -> None:
        records = parse_bhavcopy(UDIFF_HEADER + UDIFF_ROWS)
        assert [r.symbol for r in records] == ["RELIANCE", "TCS"]

    def test_excludes_other_segments(self) -> None:
        """UDiFF covers every segment; derivatives must be filtered out."""
        records = parse_bhavcopy(UDIFF_HEADER + UDIFF_ROWS)
        assert all(r.isin.startswith("INE") for r in records)
        assert "NIFTY" not in [r.symbol for r in records]

    def test_field_mapping(self) -> None:
        record = parse_bhavcopy(UDIFF_HEADER + UDIFF_ROWS)[0]
        assert record.isin == "INE002A01018"
        assert record.trade_date == date(2024, 7, 5)
        assert record.close == 2940.0
        assert record.previous_close == 2895.0
        assert record.volume == 5_000_000


class TestFormatBoundary:
    """The changeover must not become a discontinuity in any price series."""

    def test_both_layouts_produce_identical_records(self) -> None:
        legacy = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)
        udiff = parse_bhavcopy(UDIFF_HEADER + UDIFF_ROWS)
        assert legacy == udiff

    def test_closes_match_across_the_boundary(self) -> None:
        legacy = {r.isin: r.close for r in parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)}
        udiff = {r.isin: r.close for r in parse_bhavcopy(UDIFF_HEADER + UDIFF_ROWS)}
        assert legacy == udiff

    def test_the_changeover_date_is_recorded(self) -> None:
        assert date(2024, 7, 8) == UDIFF_EFFECTIVE_FROM


class TestRecordChecks:
    def test_daily_return_from_published_previous_close(self) -> None:
        record = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)[0]
        assert record.daily_return == pytest.approx((2940.0 / 2895.0) - 1.0)

    def test_daily_return_is_none_without_a_previous_close(self) -> None:
        rows = LEGACY_ROWS.replace(",2895.00,", ",0.00,")
        assert parse_bhavcopy(LEGACY_HEADER + rows)[0].daily_return is None

    def test_ohlc_consistency(self) -> None:
        assert parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)[0].is_consistent

    def test_incoherent_ohlc_is_detected(self) -> None:
        rows = LEGACY_ROWS.replace("2900.00,2950.00,2880.00", "2900.00,2850.00,2880.00")
        assert parse_bhavcopy(LEGACY_HEADER + rows)[0].is_consistent is False


class TestFileReading:
    def test_reads_a_plain_csv(self, tmp_path: Path) -> None:
        p = tmp_path / "cm05JUL2024bhav.csv"
        p.write_text(LEGACY_HEADER + LEGACY_ROWS, encoding="utf-8")
        assert len(read_bhavcopy_file(p)) == 2

    def test_reads_a_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "cm05JUL2024bhav.csv.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("cm05JUL2024bhav.csv", LEGACY_HEADER + LEGACY_ROWS)
        assert len(read_bhavcopy_file(p)) == 2

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(BhavcopyError, match="No such bhavcopy"):
            read_bhavcopy_file(tmp_path / "absent.csv")

    def test_zip_with_no_csv(self, tmp_path: Path) -> None:
        p = tmp_path / "x.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("readme.txt", "nothing here")
        with pytest.raises(BhavcopyError, match="no CSV"):
            read_bhavcopy_file(p)

    def test_zip_with_several_csvs_is_refused(self, tmp_path: Path) -> None:
        """Guessing which one to use would be a silent data choice."""
        p = tmp_path / "x.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("a.csv", LEGACY_HEADER + LEGACY_ROWS)
            z.writestr("b.csv", LEGACY_HEADER + LEGACY_ROWS)
        with pytest.raises(BhavcopyError, match="expected one"):
            read_bhavcopy_file(p)

    def test_corrupt_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "x.zip"
        p.write_bytes(b"not a zip")
        with pytest.raises(BhavcopyError, match="not a valid zip"):
            read_bhavcopy_file(p)

    def test_error_message_names_the_file(self, tmp_path: Path) -> None:
        p = tmp_path / "broken.csv"
        p.write_text("FOO,BAR\n1,2\n", encoding="utf-8")
        with pytest.raises(BhavcopyError, match=r"broken\.csv"):
            read_bhavcopy_file(p)


class TestSeriesForIsin:
    def test_builds_a_date_ordered_series(self) -> None:
        day1 = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)
        day2 = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS.replace("05-JUL-2024", "08-JUL-2024"))
        s = series_for_isin(day1 + day2, "INE002A01018")
        assert len(s) == 2
        assert s.dates == (date(2024, 7, 5), date(2024, 7, 8))

    def test_unknown_isin_is_an_error(self) -> None:
        records = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)
        with pytest.raises(BhavcopyError, match="appears in none"):
            series_for_isin(records, "INE000000000")

    def test_conflicting_closes_on_one_date_are_refused(self) -> None:
        """Two series rows for one security would make the history ambiguous."""
        rows = LEGACY_ROWS + (
            "RELIANCE,BE,2900.00,2950.00,2880.00,9999.00,2941.00,2895.00,"
            "10,1000.00,05-JUL-2024,2,INE002A01018,\n"
        )
        records = parse_bhavcopy(LEGACY_HEADER + rows)
        with pytest.raises(BhavcopyError, match="two different closes"):
            series_for_isin(records, "INE002A01018")


class TestEmptyAndMalformed:
    def test_no_header(self) -> None:
        with pytest.raises(BhavcopyError, match="no header row"):
            parse_bhavcopy("")

    def test_no_cash_equity_rows(self) -> None:
        rows = (
            "SOMEBOND,N1,100.00,100.00,100.00,100.00,100.00,100.00,"
            "10,1000.00,05-JUL-2024,2,INE999X01011,\n"
        )
        with pytest.raises(BhavcopyError, match="no cash-equity rows"):
            parse_bhavcopy(LEGACY_HEADER + rows)

    def test_bad_isin_rows_are_skipped_not_fatal(self) -> None:
        rows = LEGACY_ROWS + ("JUNK,EQ,1,1,1,1,1,1,1,1.00,05-JUL-2024,1,NOTANISIN,\n")
        assert len(parse_bhavcopy(LEGACY_HEADER + rows)) == 2

    def test_non_numeric_price_names_the_column(self) -> None:
        rows = LEGACY_ROWS.replace("2900.00,2950.00", "abc,2950.00")
        with pytest.raises(BhavcopyError, match="OPEN"):
            parse_bhavcopy(LEGACY_HEADER + rows)


class TestSeriesByIsin:
    """Single-pass series construction.

    Regression: the CLI originally called ``series_for_isin`` once per
    security, which rescans every record each time. On eleven years of Indian
    equities that is ~3.9 million rows times ~3,000 securities and the loop
    never finishes.
    """

    def _two_days(self) -> list[BhavRecord]:
        day1 = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS)
        day2 = parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS.replace("05-JUL-2024", "08-JUL-2024"))
        return day1 + day2

    def test_builds_every_series_in_one_pass(self) -> None:
        series, problems = series_by_isin(self._two_days())
        assert set(series) == {"INE002A01018", "INE467B01029"}
        assert problems == []

    def test_matches_the_single_security_builder(self) -> None:
        records = self._two_days()
        bulk, _ = series_by_isin(records)
        one = series_for_isin(records, "INE002A01018")
        assert bulk["INE002A01018"].dates == one.dates
        assert bulk["INE002A01018"].closes == one.closes

    def test_omits_securities_with_too_few_observations(self) -> None:
        series, _ = series_by_isin(parse_bhavcopy(LEGACY_HEADER + LEGACY_ROWS))
        assert series == {}

    def test_conflicting_closes_are_reported_not_raised(self) -> None:
        """One bad security must not abort the whole load."""
        rows = LEGACY_ROWS + (
            "RELIANCE,BE,2900.00,2950.00,2880.00,9999.00,2941.00,2895.00,"
            "10,1000.00,05-JUL-2024,2,INE002A01018,\n"
        )
        records = parse_bhavcopy(LEGACY_HEADER + rows) + parse_bhavcopy(
            LEGACY_HEADER + LEGACY_ROWS.replace("05-JUL-2024", "08-JUL-2024")
        )
        series, problems = series_by_isin(records)
        assert "INE002A01018" not in series
        assert any("two different closes" in p for p in problems)
        assert "INE467B01029" in series  # the healthy one survives


class TestDateFormatVariants:
    """NSE has not been consistent about the date format in legacy files."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("05-JUL-2024", date(2024, 7, 5)),
            ("13-Jul-20", date(2020, 7, 13)),
            ("2024-07-05", date(2024, 7, 5)),
        ],
    )
    def test_accepts_known_variants(self, raw: str, expected: date) -> None:
        rows = LEGACY_ROWS.replace("05-JUL-2024", raw)
        assert parse_bhavcopy(LEGACY_HEADER + rows)[0].trade_date == expected

    def test_two_digit_year_regression(self) -> None:
        """The 2020-07-13 file used '13-Jul-20' and failed the whole load."""
        rows = LEGACY_ROWS.replace("05-JUL-2024", "13-Jul-20")
        records = parse_bhavcopy(LEGACY_HEADER + rows)
        assert records[0].trade_date == date(2020, 7, 13)
