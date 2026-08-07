"""Instrument identity and symbol history."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from indian_equity_research.market.instruments import (
    InstrumentError,
    InstrumentSnapshot,
    ResolutionBasis,
    SymbolHistory,
    load_snapshot,
    load_snapshots,
)

HEADER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE,"
    " MARKET LOT, ISIN NUMBER, FACE VALUE\n"
)
ROW_A = "AAA,Alpha Ltd,EQ,06-OCT-2008,5,1,INE111A01011,5\n"
ROW_B = "BBB,Beta Ltd,EQ,03-MAY-1995,10,1,INE222B01012,10\n"


def write(dir_: Path, name: str, body: str) -> Path:
    p = dir_ / name
    p.write_text(HEADER + body, encoding="utf-8")
    return p


class TestLoadSnapshot:
    def test_parses_the_real_nse_header_with_leading_spaces(self, tmp_path: Path) -> None:
        """NSE ships ' SERIES', ' ISIN NUMBER' etc. with leading spaces."""
        snap = load_snapshot(write(tmp_path, "nse_equity_master_2026-08-07.csv", ROW_A))
        record = snap.records["INE111A01011"]
        assert record.symbol == "AAA"
        assert record.series == "EQ"
        assert record.listing_date == date(2008, 10, 6)
        assert record.face_value == 5.0

    def test_infers_the_capture_date_from_the_filename(self, tmp_path: Path) -> None:
        snap = load_snapshot(write(tmp_path, "nse_equity_master_2026-08-07.csv", ROW_A))
        assert snap.as_of == date(2026, 8, 7)

    def test_filename_without_a_date_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(InstrumentError, match="YYYY-MM-DD"):
            load_snapshot(write(tmp_path, "equity.csv", ROW_A))

    def test_invalid_isin_is_rejected(self, tmp_path: Path) -> None:
        bad = "AAA,Alpha Ltd,EQ,06-OCT-2008,5,1,NOTANISIN,5\n"
        with pytest.raises(InstrumentError, match="not a valid ISIN"):
            load_snapshot(write(tmp_path, "nse_equity_master_2026-08-07.csv", bad))

    def test_missing_columns_are_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "nse_equity_master_2026-08-07.csv"
        p.write_text("FOO,BAR\n1,2\n", encoding="utf-8")
        with pytest.raises(InstrumentError, match="needs SYMBOL and ISIN"):
            load_snapshot(p)

    def test_normal_series_wins_over_trade_to_trade(self, tmp_path: Path) -> None:
        """A security can appear once per series; EQ is the tradeable one."""
        rows = (
            "AAA,Alpha Ltd,BE,06-OCT-2008,5,1,INE111A01011,5\n"
            "AAA,Alpha Ltd,EQ,06-OCT-2008,5,1,INE111A01011,5\n"
        )
        snap = load_snapshot(write(tmp_path, "nse_equity_master_2026-08-07.csv", rows))
        assert snap.records["INE111A01011"].series == "EQ"

    def test_series_classification(self, tmp_path: Path) -> None:
        rows = ROW_A + "CCC,Gamma Ltd,BZ,01-JAN-2010,10,1,INE333C01013,10\n"
        snap = load_snapshot(write(tmp_path, "nse_equity_master_2026-08-07.csv", rows))
        assert snap.records["INE111A01011"].is_normal_series
        assert snap.records["INE333C01013"].is_trade_to_trade

    def test_load_snapshots_sorts_by_date(self, tmp_path: Path) -> None:
        write(tmp_path, "nse_equity_master_2026-08-07.csv", ROW_A)
        write(tmp_path, "nse_equity_master_2026-08-05.csv", ROW_A)
        snaps = load_snapshots(tmp_path)
        assert [s.as_of for s in snaps] == [date(2026, 8, 5), date(2026, 8, 7)]

    def test_no_snapshots_names_the_command_to_run(self, tmp_path: Path) -> None:
        with pytest.raises(InstrumentError, match="archive"):
            load_snapshots(tmp_path)


def snapshot(as_of: date, pairs: list[tuple[str, str]]) -> InstrumentSnapshot:
    from indian_equity_research.market.instruments import InstrumentRecord

    return InstrumentSnapshot(
        as_of=as_of,
        records={
            isin: InstrumentRecord(isin=isin, symbol=sym, name="", series="EQ")
            for sym, isin in pairs
        },
    )


class TestSymbolHistory:
    def test_observed_mapping_is_reliable(self) -> None:
        h = SymbolHistory.from_snapshots([snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")])])
        r = h.resolve("AAA", date(2026, 8, 1))
        assert r.isin == "INE111A01011"
        assert r.basis is ResolutionBasis.OBSERVED
        assert r.is_reliable

    def test_symbol_lookup_is_case_insensitive(self) -> None:
        h = SymbolHistory.from_snapshots([snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")])])
        assert h.resolve("aaa", date(2026, 8, 1)).isin == "INE111A01011"

    def test_unknown_symbol_is_refused_not_guessed(self) -> None:
        h = SymbolHistory.from_snapshots([snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")])])
        r = h.resolve("ZZZ", date(2026, 8, 1))
        assert r.isin is None
        assert r.basis is ResolutionBasis.UNKNOWN
        assert "delisted before archiving began" in r.detail

    def test_date_before_the_archive_is_assumed_not_observed(self) -> None:
        """The honest limitation: a snapshot archive says nothing about 2011."""
        h = SymbolHistory.from_snapshots([snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")])])
        r = h.resolve("AAA", date(2011, 5, 2))
        assert r.isin == "INE111A01011"
        assert r.basis is ResolutionBasis.ASSUMED_STABLE
        assert r.is_reliable is False
        assert "predates the archive" in r.detail

    def test_a_reused_symbol_is_refused(self) -> None:
        """The corruption this whole module exists to prevent."""
        h = SymbolHistory.from_snapshots(
            [
                snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")]),
                snapshot(date(2026, 8, 5), [("AAA", "INE999Z01019")]),
            ]
        )
        r = h.resolve("AAA", date(2011, 5, 2))
        assert r.isin is None
        assert r.basis is ResolutionBasis.AMBIGUOUS
        assert "2 different ISINs" in r.detail

    def test_a_reused_symbol_still_resolves_where_observed(self) -> None:
        h = SymbolHistory.from_snapshots(
            [
                snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")]),
                snapshot(date(2026, 8, 5), [("AAA", "INE999Z01019")]),
            ]
        )
        assert h.resolve("AAA", date(2026, 8, 1)).isin == "INE111A01011"
        assert h.resolve("AAA", date(2026, 8, 5)).isin == "INE999Z01019"

    def test_detects_symbol_reuse(self) -> None:
        h = SymbolHistory.from_snapshots(
            [
                snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")]),
                snapshot(date(2026, 8, 5), [("AAA", "INE999Z01019")]),
            ]
        )
        assert h.symbols_with_multiple_isins() == {"AAA": ["INE111A01011", "INE999Z01019"]}

    def test_detects_a_rename(self) -> None:
        h = SymbolHistory.from_snapshots(
            [
                snapshot(date(2026, 8, 1), [("OLDNAME", "INE111A01011")]),
                snapshot(date(2026, 8, 5), [("NEWNAME", "INE111A01011")]),
            ]
        )
        assert h.isins_with_multiple_symbols() == {"INE111A01011": ["NEWNAME", "OLDNAME"]}

    def test_records_the_observed_window(self) -> None:
        h = SymbolHistory.from_snapshots(
            [
                snapshot(date(2026, 8, 1), [("AAA", "INE111A01011")]),
                snapshot(date(2026, 8, 5), [("AAA", "INE111A01011")]),
            ]
        )
        assert h.observed_from == date(2026, 8, 1)
        assert h.observed_to == date(2026, 8, 5)

    def test_empty_input_is_rejected(self) -> None:
        with pytest.raises(InstrumentError, match="at least one snapshot"):
            SymbolHistory.from_snapshots([])
