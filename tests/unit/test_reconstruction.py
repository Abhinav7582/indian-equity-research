"""Tests for assembling a point-in-time index universe.

The test that matters most is :func:`test_the_series_definitions_agree`. The
rest guard the ways a universe could be built from nothing and look fine.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pytest

from indian_equity_research.backtest import prices
from indian_equity_research.market import reconstruction
from indian_equity_research.market.reconstruction import (
    NIFTY_100,
    NIFTY_200,
    NIFTY_200_UNION,
    IndexSpec,
    ReconstructionError,
    UnionIndexSpec,
    index_changes_for,
    load_roster,
)


def test_the_series_definitions_agree() -> None:
    """``market`` and ``backtest`` must filter bhavcopy the same way.

    ``market.reconstruction`` duplicates the constant rather than importing it,
    because ``market`` must not depend on ``backtest``. That duplication is only
    safe if a divergence fails a test — otherwise the universe could be built
    from one set of bars while the backtest reads another, and the two would
    disagree about which securities existed on which days.
    """
    assert reconstruction.CASH_EQUITY_SERIES == prices.CASH_EQUITY_SERIES


def test_the_declared_index_sizes_are_what_their_names_say() -> None:
    """A transposed size would move the deviation report, not the universe.

    The reconstruction would still be correct and the report would quietly stop
    flagging anything, which is the worst combination.
    """
    assert NIFTY_100.declared_size == 100
    assert NIFTY_200.declared_size == 200
    assert NIFTY_100.roster_dir != NIFTY_200.roster_dir


def write_roster(directory: Path, when: str, symbols: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"nse_test_constituents_{when}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Company Name", "Industry", "Symbol", "Series", "ISIN Code"])
        for symbol in symbols:
            writer.writerow([f"{symbol} Ltd.", "Test", symbol, "EQ", f"INE{symbol}"])


def test_the_most_recent_roster_wins(tmp_path: Path) -> None:
    """Rolling back from a stale roster undoes changes already reflected in it."""
    write_roster(tmp_path, "2020-01-01", ["OLD"])
    write_roster(tmp_path, "2026-08-21", ["NEW", "ALSO"])
    symbols, as_at = load_roster(tmp_path)
    assert as_at == dt.date(2026, 8, 21)
    assert symbols == ["NEW", "ALSO"]


def test_a_missing_roster_is_refused(tmp_path: Path) -> None:
    """Without a starting point there is nothing to roll backwards.

    Proceeding would silently produce an empty universe, which a backtest reads
    as a legitimate instruction to hold nothing.
    """
    with pytest.raises(ReconstructionError, match="starting point"):
        load_roster(tmp_path / "nothing-here")


def test_a_roster_filename_without_a_date_is_refused(tmp_path: Path) -> None:
    """The roster date decides which changes are already reflected in it.

    Guessing it would undo reconstitutions that have not happened yet — the
    2026-09-30 reconstitution is already published and must not be undone
    against an August roster.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "constituents.csv").write_text("Symbol\nAAA\n", encoding="utf-8")
    with pytest.raises(ReconstructionError, match="have not happened yet"):
        load_roster(tmp_path)


def test_an_empty_roster_file_is_refused(tmp_path: Path) -> None:
    write_roster(tmp_path, "2026-08-21", [])
    with pytest.raises(ReconstructionError, match="no Symbol column or no rows"):
        load_roster(tmp_path)


def test_no_changes_found_is_refused_rather_than_returned(tmp_path: Path) -> None:
    """A universe with no changes is today's constituents held fixed.

    That is survivorship bias in its purest form, and it is what a misspelled
    index name would silently produce.
    """
    spec = IndexSpec(name="Nifty 999", roster_dir=tmp_path, declared_size=10)
    write_roster(tmp_path, "2026-08-21", ["AAA", "BBB"])
    empty = tmp_path / "no-releases"
    empty.mkdir()
    with pytest.raises(ReconstructionError, match="survivorship bias"):
        reconstruction.reconstruct(spec, stop_at=dt.date(2015, 1, 1), circulars=empty)


def test_an_index_name_is_matched_exactly(tmp_path: Path) -> None:
    """Nifty 200 and Nifty 200 Momentum 30 are different indices.

    Their sections sit in the same documents, so a prefix match would merge two
    unrelated reconstitution histories into one.
    """
    empty = tmp_path / "releases"
    empty.mkdir()
    changes, parsed, hand = index_changes_for("Nifty 200", circulars=empty)
    assert changes == [] and parsed == 0 and hand == 0


# ---------------------------------------------------------------------------
# The union reconstruction
# ---------------------------------------------------------------------------


def test_a_union_needs_at_least_two_parts() -> None:
    spec = UnionIndexSpec(name="Solo", parts=(NIFTY_100,), declared_size=100)
    with pytest.raises(ReconstructionError, match="at least two parts"):
        reconstruction.reconstruct_union(spec, stop_at=dt.date(2015, 1, 1))


def test_the_union_spec_names_its_parts() -> None:
    """The description has to say how the index was built.

    A Nifty 200 reconstructed as a union and one parsed from Nifty 200 sections
    are different objects with different failure modes, and a report that calls
    both "Nifty 200" hides which one produced a number.
    """
    described = NIFTY_200_UNION.describe()
    assert "Nifty 100" in described
    assert "Nifty Midcap 100" in described
    assert NIFTY_200_UNION.declared_size == 200


def test_the_union_sizes_add_up_to_the_declared_total() -> None:
    """200 = 100 + 100, and the check that the union must total 200 depends on it."""
    assert sum(part.declared_size for part in NIFTY_200_UNION.parts) == (
        NIFTY_200_UNION.declared_size
    )


def test_the_parts_have_distinct_rosters() -> None:
    """Two parts pointing at one roster would union a set with itself.

    The result would be 100 members where 200 were declared, and the size
    deviation report would be the only thing that noticed.
    """
    directories = {part.roster_dir for part in NIFTY_200_UNION.parts}
    assert len(directories) == len(NIFTY_200_UNION.parts)
