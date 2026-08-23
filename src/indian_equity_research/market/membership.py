"""Reconstruct point-in-time Nifty 100 membership by rolling today's roster back.

Why backwards
-------------
NSE publishes the constituent list **as it is now**, and press releases for
every change. It does not publish the list as it stood in 2015. Rolling forward
would need a 2015 starting roster that does not exist; rolling backward needs
only today's roster, which does.

Undoing a change is the exact inverse of applying it: the members immediately
before a reconstitution are the members after it, minus everything included,
plus everything excluded.

Why this is not merely convenient
---------------------------------
A universe built from **today's** constituents and then held fixed is
survivorship bias in its purest form: every company that failed out of the index
is missing, and every company that succeeded into it is present from the start.
That single error has flattered more backtests than any other. This module
exists so that the universe on any date is the universe as it was on that date,
and so that the securities that left are still there when the backtest walks
past them.

Three things that make the reconstruction checkable
---------------------------------------------------
**Identity, not tickers.** A 2015 release names ``MCDOWELL-N``; today's roster
says ``UNITDSPR``. Undoing by ticker fails, and fails quietly -- the name is
simply not found and the roster drifts. Symbols are resolved to a security
through :mod:`indian_equity_research.market.identity` first.

**Every undo is verified.** To undo an inclusion the name must currently be a
member, and to undo an exclusion it must currently not be. A violation means the
roster and the change register disagree, which is a finding and is reported;
it is never smoothed over.

**Size is reported, not assumed.** A hundred-member index should have a hundred
members. When it does not, the deviation is carried on the result rather than
corrected, because the correction would be a guess. The 2015-2026
reconstruction runs at 101 in two windows, both bracketed by matched
``TATAMTRDVR`` events -- NSE treated Tata Motors' differential-voting share as a
constituent in its own right, and ran the Nifty 50 at 51 members for the same
reason.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from indian_equity_research.market.index_changes import IndexChange

__all__ = [
    "MembershipError",
    "MembershipHistory",
    "MembershipSnapshot",
    "SizeDeviation",
    "UnappliedChange",
    "members_on",
    "roll_back",
]


class MembershipError(ValueError):
    """Raised when a membership history cannot be built without guessing."""


@dataclass(frozen=True, slots=True)
class MembershipSnapshot:
    """Who was in the index from ``effective_from`` until the next snapshot."""

    effective_from: date
    members: frozenset[str]

    @property
    def size(self) -> int:
        """Constituent count."""
        return len(self.members)


@dataclass(frozen=True, slots=True)
class UnappliedChange:
    """A change the roster could not absorb, and exactly what disagreed."""

    effective_from: date
    source: str
    included_but_absent: tuple[str, ...]
    excluded_but_present: tuple[str, ...]

    def describe(self) -> str:
        """One line a human can check against the release."""
        parts = []
        if self.included_but_absent:
            parts.append(f"included but absent: {', '.join(self.included_but_absent)}")
        if self.excluded_but_present:
            parts.append(f"excluded but present: {', '.join(self.excluded_but_present)}")
        return f"{self.effective_from} {self.source}: {'; '.join(parts)}"


@dataclass(frozen=True, slots=True)
class SizeDeviation:
    """A period during which the reconstruction did not hold the declared size."""

    effective_from: date
    size: int


@dataclass(frozen=True, slots=True)
class MembershipHistory:
    """The reconstruction, and every way it failed to be clean."""

    snapshots: tuple[MembershipSnapshot, ...]
    unapplied: tuple[UnappliedChange, ...]
    size_deviations: tuple[SizeDeviation, ...]
    roster_date: date
    declared_size: int

    @property
    def clean(self) -> bool:
        """True only when every change was absorbed and the size never moved."""
        return not self.unapplied and not self.size_deviations

    def describe(self) -> str:
        """One line, carrying the caveats with it."""
        first = self.snapshots[0].effective_from if self.snapshots else self.roster_date
        problems = ""
        if self.unapplied:
            problems += f", {len(self.unapplied)} change(s) UNAPPLIED"
        if self.size_deviations:
            sizes = sorted({d.size for d in self.size_deviations})
            problems += f", size {sizes} in {len(self.size_deviations)} snapshot(s)"
        return (
            f"{len(self.snapshots)} snapshots, {first} to {self.roster_date}, "
            f"declared size {self.declared_size}{problems}"
        )


def roll_back(
    roster: Iterable[str],
    roster_date: date,
    changes: Sequence[IndexChange],
    *,
    canonical: Mapping[str, str] | None = None,
    stop_at: date | None = None,
    declared_size: int = 100,
) -> MembershipHistory:
    """Reconstruct membership backwards from a known roster.

    Changes with an effective date **after** ``roster_date`` are ignored rather
    than undone. A reconstitution announced in August and effective in September
    has not happened yet as far as an August roster is concerned, and undoing it
    would remove five names that were never there and restore five that never
    left.

    Args:
        roster: Constituents as at ``roster_date``.
        roster_date: When that roster was published.
        changes: Every parsed change for this index, in any order.
        canonical: Symbol to representative, from
            :func:`~indian_equity_research.market.identity.canonical_symbols`.
            Omitting it compares raw tickers, which will silently fail on every
            rename -- supply it unless the test data has none.
        stop_at: Stop rolling back once a change on or before this date has been
            undone. Usually the first date in the price archive; there is no
            point reconstructing membership for years with no bars.
        declared_size: The index's fixed size, for the deviation report.

    Returns:
        The history, including changes that could not be applied and any period
        whose size differs from ``declared_size``.

    Raises:
        MembershipError: if ``roster`` is empty.
    """
    resolve = (lambda symbol: canonical.get(symbol, symbol)) if canonical else (lambda s: s)

    members = {resolve(symbol.strip().upper()) for symbol in roster if symbol.strip()}
    if not members:
        raise MembershipError(
            f"the roster for {roster_date} is empty. Rolling back from nothing "
            f"would produce a history of empty universes rather than an error."
        )

    applicable = sorted(
        (c for c in changes if c.effective_from <= roster_date),
        key=lambda c: c.effective_from,
        reverse=True,
    )

    # Each iteration emits the membership in force **from** this change's date,
    # then undoes it to obtain the membership in force before it. Emitting after
    # the undo instead would label every snapshot with the date of the change
    # that ended it rather than the one that began it -- an off-by-one interval
    # that puts the wrong constituents in the universe on every rebalance date.
    snapshots: list[MembershipSnapshot] = []
    unapplied: list[UnappliedChange] = []
    for change in applicable:
        snapshots.append(
            MembershipSnapshot(effective_from=change.effective_from, members=frozenset(members))
        )
        included = {resolve(s) for s in change.included}
        excluded = {resolve(s) for s in change.excluded}
        absent = tuple(sorted(s for s in change.included if resolve(s) not in members))
        present = tuple(sorted(s for s in change.excluded if resolve(s) in members))
        if absent or present:
            unapplied.append(
                UnappliedChange(
                    effective_from=change.effective_from,
                    source=change.source,
                    included_but_absent=absent,
                    excluded_but_present=present,
                )
            )
        members = (members - included) | excluded
        if stop_at is not None and change.effective_from <= stop_at:
            break

    # The membership left in ``members`` predates the earliest change undone,
    # and nothing in the inputs says when it began. It is therefore not emitted:
    # ``members_on`` raises for those dates rather than serving a roster whose
    # start is unknown. Roll back further if a backtest needs to reach them.
    if not snapshots:
        snapshots.append(MembershipSnapshot(effective_from=roster_date, members=frozenset(members)))

    ordered = tuple(sorted(snapshots, key=lambda s: s.effective_from))
    deviations = tuple(
        SizeDeviation(effective_from=s.effective_from, size=s.size)
        for s in ordered
        if s.size != declared_size
    )
    return MembershipHistory(
        snapshots=ordered,
        unapplied=tuple(sorted(unapplied, key=lambda u: u.effective_from)),
        size_deviations=deviations,
        roster_date=roster_date,
        declared_size=declared_size,
    )


def members_on(history: MembershipHistory, when: date) -> frozenset[str]:
    """Membership in force on ``when``.

    Args:
        history: A reconstruction from :func:`roll_back`.
        when: The date asked about.

    Returns:
        The members of the latest snapshot effective on or before ``when``.

    Raises:
        MembershipError: if ``when`` precedes the earliest snapshot. Returning
            an empty set would look like an index with no members, and a
            backtest would read that as a legitimate instruction to hold
            nothing rather than as the absence of data.
    """
    if not history.snapshots:
        raise MembershipError("this history has no snapshots")
    starts = [s.effective_from for s in history.snapshots]
    index = bisect_right(starts, when) - 1
    if index < 0:
        raise MembershipError(
            f"membership on {when} is not reconstructed: the earliest snapshot "
            f"begins {starts[0]}. Roll back further, or start the backtest later."
        )
    return history.snapshots[index].members
