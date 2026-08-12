"""Tests for the hand-verified index-change register.

The register exists because a minority of NSE releases are scans. Its whole
value is that a human read them, so every test here is about refusing input
that would let an *unread* release pass as a read one.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from indian_equity_research.market.index_changes import (
    IndexChangeError,
    load_manual_register,
)

HEADER = (
    "| source | index | effective_from | excluded | included | evidence |\n"
    "|---|---|---|---|---|---|\n"
)


def write(tmp_path: Path, body: str, *, preamble: str = "") -> Path:
    path = tmp_path / "index_changes_manual.md"
    path.write_text(preamble + HEADER + body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


def test_a_change_row_becomes_an_index_change(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "| ind_prs23082021.pdf | Nifty 100 | 2021-09-30 "
        "| ABBOTINDIA, MRF | SAIL, PIIND | p5, read by eye |\n",
    )
    register = load_manual_register(path)
    assert len(register.changes) == 1
    change = register.changes[0]
    assert change.effective_from == dt.date(2021, 9, 30)
    assert change.excluded == ("ABBOTINDIA", "MRF")
    assert change.included == ("SAIL", "PIIND")
    assert change.source == "ind_prs23082021.pdf"
    assert change.net_size_change == 0


def test_prose_around_the_table_is_ignored(tmp_path: Path) -> None:
    """The file is written for a human first; it carries notes and headings."""
    path = write(
        tmp_path,
        "| a.pdf | Nifty 100 | no change | | | bond index only |\n\n"
        "## Notes\n\nThe effective date is as printed. See page 5.\n",
        preamble="# Hand-verified index changes\n\nRead by: someone, 2026-08-12.\n\n",
    )
    register = load_manual_register(path)
    assert register.changes == ()
    assert register.no_change == (("a.pdf", "bond index only"),)


def test_no_change_is_recorded_separately_from_absence(tmp_path: Path) -> None:
    """A release read and dismissed is not the same as one never opened.

    This is the distinction the whole file exists to preserve.
    """
    path = write(
        tmp_path,
        "| read.pdf | Nifty 100 | no change | | | CPSE index only |\n"
        "| changed.pdf | Nifty 100 | 2018-09-28 | WIPRO | SAIL | p2 |\n",
    )
    register = load_manual_register(path)
    assert [s for s, _ in register.no_change] == ["read.pdf"]
    assert [c.source for c in register.changes] == ["changed.pdf"]
    assert "1 hand-read change" in register.describe()


def test_changes_come_back_in_date_order(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "| b.pdf | Nifty 100 | 2021-09-30 | MRF | SAIL | p5 |\n"
        "| a.pdf | Nifty 100 | 2018-09-28 | WIPRO | PIIND | p2 |\n",
    )
    assert [c.source for c in load_manual_register(path).changes] == ["a.pdf", "b.pdf"]


def test_rows_can_be_filtered_by_index(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "| a.pdf | Nifty 100 | 2021-09-30 | MRF | SAIL | p5 |\n"
        "| a.pdf | Nifty 500 | 2021-09-30 | WIPRO | PIIND | p9 |\n",
    )
    register = load_manual_register(path, index_name="Nifty 100")
    assert [c.index_name for c in register.changes] == ["Nifty 100"]


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_missing_register_is_refused_not_treated_as_empty(tmp_path: Path) -> None:
    """The failure that matters most.

    Returning an empty register would mean every scanned release silently
    reports "no changes" -- the exact outcome `read_release_pdf` refuses.
    """
    with pytest.raises(IndexChangeError, match="does not exist"):
        load_manual_register(tmp_path / "absent.md")


def test_the_filename_date_cannot_be_used_by_accident(tmp_path: Path) -> None:
    path = write(tmp_path, "| a.pdf | Nifty 100 | 23-08-2021 | MRF | SAIL | p5 |\n")
    with pytest.raises(IndexChangeError, match="YYYY-MM-DD"):
        load_manual_register(path)


def test_no_change_with_symbols_is_a_contradiction(tmp_path: Path) -> None:
    path = write(tmp_path, "| a.pdf | Nifty 100 | no change | MRF | SAIL | p5 |\n")
    with pytest.raises(IndexChangeError, match="lists symbols"):
        load_manual_register(path)


def test_a_date_with_no_symbols_is_refused(tmp_path: Path) -> None:
    """Ambiguous: did the reader find nothing, or stop halfway?"""
    path = write(tmp_path, "| a.pdf | Nifty 100 | 2021-09-30 | | | p5 |\n")
    with pytest.raises(IndexChangeError, match="no symbols"):
        load_manual_register(path)


def test_a_company_name_in_a_symbol_column_is_refused(tmp_path: Path) -> None:
    """OCR yields company names readily and symbols poorly."""
    path = write(tmp_path, "| a.pdf | Nifty 100 | 2021-09-30 | Abbott India Ltd. | SAIL | p5 |\n")
    with pytest.raises(IndexChangeError, match="does not look"):
        load_manual_register(path)


def test_missing_evidence_is_refused(tmp_path: Path) -> None:
    """An unattributed reading cannot be re-checked, so it is not accepted."""
    path = write(tmp_path, "| a.pdf | Nifty 100 | 2021-09-30 | MRF | SAIL |  |\n")
    with pytest.raises(IndexChangeError, match="'evidence' column is empty"):
        load_manual_register(path)


def test_a_release_recorded_twice_is_refused(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "| a.pdf | Nifty 100 | 2021-09-30 | MRF | SAIL | first read |\n"
        "| a.pdf | Nifty 100 | no change | | | second read |\n",
    )
    with pytest.raises(IndexChangeError, match="recorded twice"):
        load_manual_register(path)


def test_the_same_release_may_cover_two_indices(tmp_path: Path) -> None:
    """Duplicate detection is per (source, index), not per source."""
    path = write(
        tmp_path,
        "| a.pdf | Nifty 100 | 2021-09-30 | MRF | SAIL | p5 |\n"
        "| a.pdf | Nifty 500 | 2021-09-30 | WIPRO | PIIND | p9 |\n",
    )
    assert len(load_manual_register(path).changes) == 2


def test_a_symbol_listed_twice_is_refused(tmp_path: Path) -> None:
    path = write(tmp_path, "| a.pdf | Nifty 100 | 2021-09-30 | MRF, MRF | SAIL, PIIND | p5 |\n")
    with pytest.raises(IndexChangeError, match="listed twice"):
        load_manual_register(path)


def test_a_symbol_on_both_sides_is_refused(tmp_path: Path) -> None:
    """Delegated to IndexChange, but pinned here because it survives a typo."""
    path = write(tmp_path, "| a.pdf | Nifty 100 | 2021-09-30 | MRF, SAIL | SAIL | p5 |\n")
    with pytest.raises(IndexChangeError, match="both excluded and included"):
        load_manual_register(path)


def test_a_stray_pipe_is_reported_with_its_line_number(tmp_path: Path) -> None:
    path = write(tmp_path, "| a.pdf | Nifty 100 | 2021-09-30 | MRF | SAIL | p5 | extra |\n")
    with pytest.raises(IndexChangeError, match="line 3: 7 columns, expected 6"):
        load_manual_register(path)
