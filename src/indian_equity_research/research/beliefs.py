"""Testing a claim about market state against the archive before acting on it.

Amendment A13 governs this module. The rules it imposes are not stylistic; two
of them are enforced here by raising rather than returning, because the failure
they prevent is a *plausible number* rather than a crash.

What this answers, and what it does not
---------------------------------------
Given a claim of the form *"X has outperformed Y over horizon H"*, this reports
every historical instance of that comparison and locates the present one within
it. It answers **"is this unusual?"**

It does not answer **"will it continue?"** — and A13 forbids reading it as
though it did. Nothing here returns an allocation, a weight, a target or a rupee
amount, and nothing here should be extended to.

Why this exists at all
----------------------
A confident belief that the market was "at one of its lowest points" was checked
against 23 years and came back at the **97th percentile** — off by roughly ninety
percentiles, and already attached to a decision. The cost of checking is one
function call. The cost of not checking was very nearly real money.

Two guards that raise
---------------------
:class:`ComparatorTooShort` — a comparator that does not span the requested
window would silently answer a 21-year question from 11 years of data. That is
the same class of defect as the ten found in Phase 4, all of which produced
confident wrong numbers rather than errors.

:class:`WindowsNotIndependent` — the second-window confirmation A13 requires is
worthless if the two windows overlap, because overlapping windows share the very
observations whose independence is being claimed.

On overlapping windows
----------------------
:attr:`BeliefCheck.observations` counts rolling windows, which for daily data
massively overstates the evidence: 5,060 daily one-year windows over 21 years
contain roughly **21** independent observations, not 5,060. Adjacent windows
share 364 of their 365 days. :attr:`BeliefCheck.independent_observations` is
reported alongside for exactly that reason, and every percentile in this module
should be read against the smaller number.
"""

from __future__ import annotations

import csv
import statistics
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# A calendar year of a rolling window, in days. Used only to translate a horizon
# expressed in months into a lookback; the actual endpoints are always real
# sessions found in the series.
DAYS_PER_MONTH = 30.44

# How much shorter than nominal a window may be and still count. A one-year
# window landing on a long holiday weekend is legitimate; one landing 40 days
# short is a data gap wearing a window's clothes.
WINDOW_TOLERANCE = 0.93


class BeliefError(RuntimeError):
    """A belief check could not be performed honestly."""


class ComparatorTooShort(BeliefError):  # noqa: N818 - it is a shortfall, not an error about one
    """The comparator series does not span the window the claim is about.

    Raised rather than truncating. A13 rule 5: answering a 21-year claim from 11
    years of comparator data and reporting it as 21 years is indistinguishable,
    in the output, from having had the data.
    """


class WindowsNotIndependent(BeliefError):  # noqa: N818 - it is a property, not an error about one
    """A confirmation window overlaps the window it is meant to confirm.

    A13 rule 3 requires the second window to be non-overlapping. Two windows
    sharing observations cannot corroborate each other — the shared data would
    agree with itself.
    """


@dataclass(frozen=True)
class Series:
    """One named index level series, and the sessions it actually has.

    Attributes:
        name: How the series is identified in output. Must be the index's real
            name; a mislabelled comparator is undetectable downstream.
        levels: ``{session: level}``. Total-return levels, not price levels —
            comparing a price index against a total-return one silently
            attributes the dividend yield to whichever side is the TRI.
    """

    name: str
    levels: Mapping[date, float]

    @property
    def sessions(self) -> list[date]:
        """Every session present, ascending."""
        return sorted(self.levels)

    @property
    def first(self) -> date:
        """Earliest session."""
        return min(self.levels)

    @property
    def last(self) -> date:
        """Latest session."""
        return max(self.levels)

    def on_or_before(self, when: date) -> date | None:
        """The latest session at or before ``when``, or ``None`` if none exists.

        Used rather than exact-date lookup because a window endpoint computed
        from a horizon will usually land on a weekend or a holiday.
        """
        sessions = self.sessions
        position = bisect_right(sessions, when)
        return sessions[position - 1] if position else None

    def describe(self) -> str:
        """One line for a result header."""
        return f"{self.name}: {len(self.levels)} sessions, {self.first} to {self.last}"


@dataclass(frozen=True)
class Window:
    """One historical instance of the comparison, and what it returned.

    Attributes:
        start: Session the window opens on.
        end: Session the window closes on.
        subject_return: Total return of the subject series across the window.
        comparator_return: Total return of the comparator across the same
            sessions — the same two dates, never a nearby pair.
    """

    start: date
    end: date
    subject_return: float
    comparator_return: float

    @property
    def relative(self) -> float:
        """Subject minus comparator, in simple return terms.

        A difference of simple returns rather than a ratio of growth factors,
        because the claim being tested is habitually phrased as "beat it by 2%"
        and that is what a reader will compare against.
        """
        return self.subject_return - self.comparator_return


@dataclass(frozen=True)
class BeliefCheck:
    """The distribution a claim lives in, and where the present sits in it.

    Deliberately contains no verdict field. A13 rule 1: this describes, it does
    not recommend, and a boolean called something like ``supported`` would be
    read as advice however it were documented.
    """

    claim: str
    subject: str
    comparator: str
    horizon_months: int
    windows: tuple[Window, ...]
    first_session: date
    last_session: date

    @property
    def observations(self) -> int:
        """Rolling windows measured. Overstates the evidence — see below."""
        return len(self.windows)

    @property
    def independent_observations(self) -> float:
        """Non-overlapping windows the span could hold.

        The honest denominator. Adjacent daily windows share all but one day of
        their data, so :attr:`observations` counts the same evidence hundreds of
        times over. Every percentile here should be read against this number.
        """
        span_days = (self.last_session - self.first_session).days
        return span_days / (self.horizon_months * DAYS_PER_MONTH)

    @property
    def relatives(self) -> list[float]:
        """Every window's relative return, ascending."""
        return sorted(window.relative for window in self.windows)

    @property
    def latest(self) -> Window:
        """The most recent window — the one the claim is usually about."""
        return max(self.windows, key=lambda window: window.end)

    @property
    def percentile(self) -> float:
        """Where the latest window sits, 0 to 100.

        The fraction of historical windows the present one equals or exceeds.
        A high number means today is unusual **by historical standards**, and
        says nothing whatever about tomorrow.
        """
        values = self.relatives
        below = sum(1 for value in values if value <= self.latest.relative)
        return 100.0 * below / len(values)

    @property
    def hit_rate(self) -> float:
        """Fraction of windows in which the subject beat the comparator."""
        return sum(1 for value in self.relatives if value > 0) / len(self.relatives)

    @property
    def mean_win(self) -> float:
        """Average margin in windows the subject won. Zero if it never won."""
        wins = [value for value in self.relatives if value > 0]
        return statistics.fmean(wins) if wins else 0.0

    @property
    def mean_loss(self) -> float:
        """Average margin in windows the subject lost. Zero if it never lost.

        Reported beside :attr:`mean_win` because a hit rate alone hides
        asymmetry: winning 53% of the time while losing more per loss than is
        gained per win is a different proposition from winning 53% evenly.
        """
        losses = [value for value in self.relatives if value <= 0]
        return statistics.fmean(losses) if losses else 0.0

    def quantile(self, fraction: float) -> float:
        """The relative return at ``fraction`` of the distribution, 0 to 1."""
        values = self.relatives
        index = min(len(values) - 1, max(0, int(fraction * len(values))))
        return values[index]

    def describe(self) -> str:
        """One line stating the finding without interpreting it."""
        return (
            f"{self.subject} vs {self.comparator}, {self.horizon_months}m: "
            f"latest {self.latest.relative:+.1%} at the {self.percentile:.0f}th "
            f"percentile of {self.observations} windows "
            f"(~{self.independent_observations:.0f} independent)"
        )


def load_index_series(directory: Path, name: str | None = None) -> Series:
    """Read one NSE Total Returns Index folder of yearly CSVs.

    Args:
        directory: Folder of ``*_YYYY.csv`` files in NSE's TRI export format.
        name: Override for the series name. Defaults to the ``IndexName``
            column, which is the index's own published name.

    Returns:
        The series.

    Raises:
        BeliefError: if the folder is empty, if no rows parse, or if the files
            disagree about which index they describe. The last case means two
            indices have been mixed into one folder, which would produce a
            level series that jumps between two unrelated scales and a return
            distribution built from the jumps.
    """
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise BeliefError(
            f"no CSV files in {directory}. A belief cannot be checked against a "
            f"series that is not there."
        )

    levels: dict[date, float] = {}
    names: set[str] = set()
    for path in files:
        with path.open(encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                raw_date = (row.get("Date") or "").strip()
                raw_value = (row.get("Total Returns Index") or "").strip()
                if not raw_date or not raw_value:
                    continue
                if index_name := (row.get("IndexName") or "").strip():
                    names.add(index_name)
                parsed = datetime.strptime(raw_date, "%d %b %Y").replace(tzinfo=UTC)
                levels[parsed.date()] = float(raw_value.replace(",", ""))

    if not levels:
        raise BeliefError(
            f"no usable rows in {directory}. NSE serves price-return data from a "
            f"different page than total-return data, and only the latter has a "
            f"'Total Returns Index' column — check which section was downloaded."
        )
    if len(names) > 1:
        raise BeliefError(
            f"{directory} contains more than one index: {sorted(names)}. Merging "
            f"them would build a level series that jumps between unrelated scales."
        )
    return Series(name=name or (names.pop() if names else directory.name), levels=levels)


def _windows(
    subject: Series,
    comparator: Series,
    horizon_months: int,
    start: date,
    end: date,
) -> list[Window]:
    """Every rolling window of the horizon whose endpoints both series share.

    Sessions are intersected before anything is measured. Reading each series on
    its own calendar would compare returns over different sets of trading days
    and attribute the difference to the indices.
    """
    lookback = timedelta(days=round(horizon_months * DAYS_PER_MONTH))
    minimum = lookback.days * WINDOW_TOLERANCE
    shared = sorted(set(subject.levels) & set(comparator.levels))

    out: list[Window] = []
    for close in shared:
        if close < start or close > end:
            continue
        opened = subject.on_or_before(close - lookback)
        if opened is None or opened not in comparator.levels:
            continue
        if (close - opened).days < minimum:
            continue
        out.append(
            Window(
                start=opened,
                end=close,
                subject_return=subject.levels[close] / subject.levels[opened] - 1.0,
                comparator_return=(comparator.levels[close] / comparator.levels[opened] - 1.0),
            )
        )
    return out


def check_belief(
    claim: str,
    subject: Series,
    comparator: Series,
    horizon_months: int = 12,
    start: date | None = None,
    end: date | None = None,
) -> BeliefCheck:
    """Locate a claim about relative performance within its own history.

    Args:
        claim: The belief in the words it was said in. Recorded verbatim so the
            log shows what was actually asked, not a tidied version of it.
        subject: The series the claim is about.
        comparator: What it is claimed to have beaten.
        horizon_months: Horizon of the claim. Twelve for "over the past year".
        start: Earliest window close to measure. Defaults to the earliest both
            series can support.
        end: Latest window close. Defaults to the latest they share.

    Returns:
        The distribution, and where the present window sits in it.

    Raises:
        ComparatorTooShort: if the comparator begins after the subject, by more
            than one horizon. A13 rule 5 — refuse rather than truncate.
        BeliefError: if the horizon is not positive, or if no window survives.
    """
    if horizon_months <= 0:
        raise BeliefError(f"horizon_months must be positive, got {horizon_months}")

    lookback = timedelta(days=round(horizon_months * DAYS_PER_MONTH))
    if comparator.first > subject.first + lookback:
        shortfall = (comparator.first - subject.first).days / 365.25
        raise ComparatorTooShort(
            f"{comparator.name} begins {comparator.first}, {shortfall:.1f} years "
            f"after {subject.name} begins {subject.first}. Measuring the claim "
            f"anyway would answer it from the shorter history while reporting "
            f"the longer one. Extend {comparator.name}, or state the shortened "
            f"window explicitly by passing start=."
        )

    lower = start or max(subject.first, comparator.first) + lookback
    upper = end or min(subject.last, comparator.last)
    windows = _windows(subject, comparator, horizon_months, lower, upper)
    if not windows:
        raise BeliefError(
            f"no {horizon_months}-month window between {lower} and {upper} exists "
            f"in both series. Check the horizon against the overlap: "
            f"{subject.describe()}; {comparator.describe()}."
        )

    return BeliefCheck(
        claim=claim,
        subject=subject.name,
        comparator=comparator.name,
        horizon_months=horizon_months,
        windows=tuple(windows),
        first_session=min(window.start for window in windows),
        last_session=max(window.end for window in windows),
    )


def confirm_on_second_window(
    first: BeliefCheck,
    subject: Series,
    comparator: Series,
    start: date,
    end: date,
) -> BeliefCheck:
    """Re-run a check on a window that shares no data with the first.

    A13 rule 3. An encouraging result must survive a period it was not measured
    on before it may inform a decision — a run concentrated in recent months
    dominates every rolling window containing it, and overlapping windows cannot
    reveal that because they all contain it.

    Args:
        first: The check being confirmed.
        subject: Same series as the first check.
        comparator: Same comparator as the first check.
        start: Earliest window *close* in the confirmation.
        end: Latest window close.

    Returns:
        A second check, over the confirmation window only.

    Raises:
        WindowsNotIndependent: if the two checks read any session in common.
        BeliefError: if the confirmation uses a different pair of series.
    """
    if subject.name != first.subject or comparator.name != first.comparator:
        raise BeliefError(
            f"confirmation must use the same pair: {first.subject} vs "
            f"{first.comparator}, not {subject.name} vs {comparator.name}. "
            f"Changing the series makes this a new claim, not a confirmation."
        )

    # The confirmation reads back one full horizon before its first window
    # closes, so its data span begins at ``start - lookback`` and NOT at
    # ``start``. Comparing the two ``start`` dates instead would pass a
    # confirmation window that begins the day after the first check ends while
    # its opening window quietly reaches a whole year back into it.
    lookback = timedelta(days=round(first.horizon_months * DAYS_PER_MONTH))
    reads_from = start - lookback
    if reads_from <= first.last_session and end >= first.first_session:
        raise WindowsNotIndependent(
            f"the confirmation reads from {reads_from} (one {first.horizon_months}-month "
            f"horizon before {start}) to {end}, overlapping the first check's "
            f"{first.first_session} to {first.last_session}. Windows that share "
            f"observations cannot confirm each other — the shared data would only "
            f"be agreeing with itself. Start the confirmation on or after "
            f"{first.last_session + lookback + timedelta(days=1)}."
        )

    return check_belief(
        claim=f"{first.claim} [confirmation window {start} to {end}]",
        subject=subject,
        comparator=comparator,
        horizon_months=first.horizon_months,
        start=start,
        end=end,
    )
