"""Tests for reconstructing point-in-time index membership.

The test that justifies the module is
:func:`test_a_company_that_left_the_index_is_still_there_before_it_left`. Every
other test guards a way the reconstruction could look right and be wrong.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.market.index_changes import IndexChange
from indian_equity_research.market.membership import (
    MembershipError,
    members_on,
    roll_back,
)

ROSTER_DATE = dt.date(2026, 8, 21)


def change(
    effective: dt.date, out: tuple[str, ...], into: tuple[str, ...], source: str = "test.pdf"
) -> IndexChange:
    return IndexChange(
        index_name="Nifty 100",
        effective_from=effective,
        announced_on=None,
        excluded=out,
        included=into,
        source=source,
    )


def test_a_company_that_left_the_index_is_still_there_before_it_left() -> None:
    """Survivorship bias, prevented.

    A universe taken from today's constituents and held fixed contains every
    company that succeeded into the index and none that failed out of it. Here
    OLD must be a member before the 2020 swap and absent after.

    Two changes, not one, because a snapshot is dated by the change that
    **began** it. The 2016 change is what gives the OLD-era membership a known
    start date; without it the reconstruction cannot say when that membership
    began and refuses to serve it.
    """
    history = roll_back(
        ["NEW", "STAYER"],
        ROSTER_DATE,
        [
            change(dt.date(2016, 4, 1), out=("ANCIENT",), into=("OLD",)),
            change(dt.date(2020, 4, 1), out=("OLD",), into=("NEW",)),
        ],
    )
    before = members_on(history, dt.date(2019, 1, 1))
    after = members_on(history, dt.date(2021, 1, 1))

    assert before == {"OLD", "STAYER"}
    assert after == {"NEW", "STAYER"}


def test_a_change_effective_after_the_roster_date_is_not_undone() -> None:
    """An announcement is not an event.

    NSE announces a reconstitution five weeks before it takes effect. Undoing
    one that has not happened yet removes names that were never there and
    restores names that never left -- ten wrong constituents from one
    off-by-one in the date comparison.
    """
    history = roll_back(
        ["NEW", "STAYER"],
        ROSTER_DATE,
        [
            change(dt.date(2020, 4, 1), out=("OLD",), into=("NEW",)),
            change(dt.date(2026, 9, 30), out=("STAYER",), into=("NOTYET",)),
        ],
        declared_size=2,
    )
    assert members_on(history, ROSTER_DATE) == {"NEW", "STAYER"}
    assert history.clean


def test_a_rename_is_resolved_before_the_change_is_undone() -> None:
    """A 2015 release says MCDOWELL-N; today's roster says UNITDSPR.

    Undone by ticker the name is simply not found, the roster drifts by one,
    and nothing says so.
    """
    canonical = {
        "MCDOWELL-N": "MCDOWELL-N",
        "UNITDSPR": "MCDOWELL-N",
        "OTHER": "OTHER",
        "GONE": "GONE",
        "ANCIENT": "ANCIENT",
    }
    history = roll_back(
        ["UNITDSPR", "OTHER"],
        ROSTER_DATE,
        [
            change(dt.date(2016, 4, 1), out=("ANCIENT",), into=("GONE",)),
            change(dt.date(2020, 4, 1), out=("GONE",), into=("MCDOWELL-N",)),
        ],
        canonical=canonical,
        declared_size=2,
    )
    assert history.clean
    assert members_on(history, dt.date(2019, 1, 1)) == {"GONE", "OTHER"}


def test_a_change_the_roster_cannot_absorb_is_reported() -> None:
    """The roster and the release disagree, and that is a finding.

    Silently ignoring it drifts the constituent count, which is the symptom
    that led to the whole reconstruction being checked in the first place.
    """
    history = roll_back(
        ["A", "B"],
        ROSTER_DATE,
        [change(dt.date(2020, 4, 1), out=("X",), into=("NEVER_LISTED",))],
    )
    assert not history.clean
    assert history.unapplied[0].included_but_absent == ("NEVER_LISTED",)
    assert "included but absent" in history.unapplied[0].describe()


def test_a_size_deviation_is_carried_not_corrected() -> None:
    """The reconstruction reports 101 members; it must not quietly drop one.

    The real 2015-2026 history runs at 101 in two windows because NSE treated
    Tata Motors' differential-voting share as a constituent in its own right --
    it ran the Nifty 50 at 51 members for the same reason. Correcting that to
    100 would have deleted a real constituent to satisfy an assumption.
    """
    history = roll_back(
        ["A", "B", "C"],
        ROSTER_DATE,
        [
            change(dt.date(2016, 4, 1), out=(), into=("DVR",)),
            change(dt.date(2020, 4, 1), out=("DVR",), into=()),
        ],
        declared_size=3,
    )
    assert [d.size for d in history.size_deviations] == [4]
    assert members_on(history, dt.date(2019, 1, 1)) == {"A", "B", "C", "DVR"}
    assert members_on(history, dt.date(2021, 1, 1)) == {"A", "B", "C"}


def test_asking_before_the_reconstruction_starts_raises() -> None:
    """An empty universe is a legitimate instruction to hold nothing.

    Returning one for a date that was never reconstructed would have the
    backtest read absent data as a decision, and report the result of a
    strategy nobody wrote.
    """
    history = roll_back(["A"], ROSTER_DATE, [change(dt.date(2020, 4, 1), (), ())])
    with pytest.raises(MembershipError, match="not reconstructed"):
        members_on(history, dt.date(2000, 1, 1))


def test_an_empty_roster_is_refused() -> None:
    """Rolling back from nothing yields a history of empty universes."""
    with pytest.raises(MembershipError, match="empty"):
        roll_back([], ROSTER_DATE, [])


def test_membership_holds_between_changes() -> None:
    """A snapshot is in force until the next one, not just on its own date."""
    history = roll_back(
        ["C"],
        ROSTER_DATE,
        [
            change(dt.date(2018, 4, 1), out=("A",), into=("B",)),
            change(dt.date(2022, 4, 1), out=("B",), into=("C",)),
        ],
    )
    assert members_on(history, dt.date(2018, 4, 1)) == {"B"}
    assert members_on(history, dt.date(2020, 6, 15)) == {"B"}
    assert members_on(history, dt.date(2022, 4, 1)) == {"C"}
