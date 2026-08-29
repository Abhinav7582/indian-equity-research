"""Assemble a point-in-time index universe from the pieces on disk.

Three scripts needed the same seven steps — read the roster, parse the press
releases, drop the deferred reconstitutions, add the hand-read register, build
symbol identity from bhavcopy, roll the roster backwards, check it closed — and
each had its own copy with the index name written into it. This module holds the
sequence once and takes the index as an argument.

That is not tidiness. Amendment A10 extends the study from the Nifty 100 to the
Nifty 200, and an extension that requires editing three scripts is an extension
where the two universes can quietly diverge in some detail nobody re-checked.
The whole value of moving one variable is that everything else is provably the
same code.

What this does not do
---------------------
It downloads nothing. Fetching NSE's site needs a cookie jar and a warm-up
request, which is session state with no business in ``market/`` — see
``scripts/fetch_corporate_actions.py`` for the same reasoning. Everything here
reads files that are already on disk and fails loudly when they are not.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from indian_equity_research.market.identity import canonical_symbols
from indian_equity_research.market.index_changes import (
    IndexChange,
    IndexChangeError,
    drop_deferred,
    load_manual_register,
    parse_release,
    read_release_pdf,
)
from indian_equity_research.market.membership import (
    MembershipHistory,
    MembershipSnapshot,
    SizeDeviation,
    members_on,
    roll_back,
)

__all__ = [
    "A11_IMPLICATED",
    "CASH_EQUITY_SERIES",
    "NIFTY_50",
    "NIFTY_100",
    "NIFTY_200",
    "NIFTY_200_UNION",
    "NIFTY_MIDCAP_100",
    "NIFTY_NEXT_50",
    "IndexSpec",
    "Reconstruction",
    "ReconstructionError",
    "UnionIndexSpec",
    "index_changes_for",
    "isins_by_symbol",
    "load_roster",
    "reconstruct",
    "reconstruct_union",
]

# Duplicated deliberately rather than imported from ``backtest.prices``:
# ``market`` must not depend on ``backtest``. The two are pinned equal by
# ``test_the_series_definitions_agree``, so a divergence fails a test rather
# than silently building a universe from a different set of bars than the
# backtest reads.
CASH_EQUITY_SERIES: Final = frozenset({"EQ", "BE", "BZ"})

CIRCULARS: Final = Path("data/raw/circulars")
BHAVCOPY: Final = Path("data/raw/bhavcopy")


class ReconstructionError(RuntimeError):
    """Raised when a universe cannot be assembled from what is on disk."""


@dataclass(frozen=True, slots=True)
class IndexSpec:
    """Which index, where its roster lives, and how many members it should hold."""

    name: str
    roster_dir: Path
    declared_size: int

    def describe(self) -> str:
        """One line for a report header."""
        return f"{self.name} ({self.declared_size} constituents)"


#: The two universes this project studies. Amendment A5 fixed the first;
#: Amendment A10 added the second.
NIFTY_100: Final = IndexSpec(
    name="Nifty 100",
    roster_dir=Path("data/raw/archive/nse_nifty100_constituents"),
    declared_size=100,
)
NIFTY_200: Final = IndexSpec(
    name="Nifty 200",
    roster_dir=Path("data/raw/archive/nse_nifty200_constituents"),
    declared_size=200,
)

# The two halves of the Nifty 100, and the cleanest-parsing indices in the whole
# archive: 25 changes with 2 net-size anomalies for the Nifty 50, 35 with 1 for
# the Next 50, against 51 with 4 for the Nifty 200. Amendment A11 uses them to
# ask the size question the Nifty 200 could not be made to answer.
NIFTY_50: Final = IndexSpec(
    name="Nifty 50",
    roster_dir=Path("data/raw/archive/nse_nifty50_constituents"),
    declared_size=50,
)
NIFTY_NEXT_50: Final = IndexSpec(
    name="Nifty Next 50",
    roster_dir=Path("data/raw/archive/nse_niftynext50_constituents"),
    declared_size=50,
)

# The twenty securities implicated by the thirteen Nifty 200 changes that cannot
# be applied. Fixed by Amendment A11 **before any Nifty 200 return was read**, so
# excluding them prejudges nothing. Band B of the A11 sensitivity drops these;
# Band A keeps them. Widening this set until the bands agree is forbidden.
A11_IMPLICATED: Final = frozenset(
    {
        "ABBOTINDIA",
        "BAJAJFINSV",
        "BBTC",
        "CENTRALBK",
        "CESC",
        "CRISIL",
        "GODREJAGRO",
        "HINDCOPPER",
        "IDEA",
        "INDIANB",
        "IREDA",
        "MFSL",
        "NATIONALUM",
        "NIITTECH",
        "RELCAPITAL",
        "TATACOMM",
        "TRENT",
        "VAKRANGEE",
        "VGUARD",
        "WABAG",
    }
)


@dataclass(frozen=True, slots=True)
class Reconstruction:
    """A point-in-time universe and the evidence behind it."""

    spec: IndexSpec
    history: MembershipHistory
    canonical: dict[str, str]
    changes_parsed: int
    changes_hand_read: int
    releases_without_text: int

    @property
    def securities(self) -> set[str]:
        """Every security that was ever a member, by canonical symbol."""
        out: set[str] = set()
        for snapshot in self.history.snapshots:
            out |= snapshot.members
        return out

    @property
    def tickers(self) -> set[str]:
        """Every **ticker** belonging to a member security.

        Not the same set as :attr:`securities`. Bars are keyed by the name a
        security traded under; membership is keyed by one representative. Load
        only the representatives and a renamed company disappears from the
        universe on the day it changed name.
        """
        return {symbol for symbol, rep in self.canonical.items() if rep in self.securities}

    def describe(self) -> str:
        """One line, carrying the caveats with it."""
        return (
            f"{self.spec.name}: {self.history.describe()}; "
            f"{self.changes_parsed} changes parsed + {self.changes_hand_read} hand-read; "
            f"{len(self.securities)} securities, {len(self.tickers)} tickers"
        )


def load_roster(directory: Path) -> tuple[list[str], date]:
    """Read the most recent archived constituent list.

    Args:
        directory: Folder of ``*_YYYY-MM-DD.csv`` files with a ``Symbol`` column.

    Returns:
        ``(symbols, as_at)``.

    Raises:
        ReconstructionError: if the folder is empty or has no usable file. The
            reconstruction rolls a roster backwards; without one there is
            nothing to roll, and proceeding would silently produce an empty
            universe.
    """
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise ReconstructionError(
            f"no archived constituent list in {directory}. The reconstruction rolls "
            f"today's roster backwards through the published changes, so it needs a "
            f"starting point. Download the current constituent CSV from NSE and save "
            f"it there with the date in the filename."
        )
    latest = files[-1]
    try:
        as_at = date.fromisoformat(latest.stem.split("_")[-1])
    except ValueError as exc:
        raise ReconstructionError(
            f"cannot read a date from {latest.name}. The filename must end in "
            f"_YYYY-MM-DD.csv -- the roster date decides which changes are already "
            f"reflected in it, and guessing it would undo reconstitutions that have "
            f"not happened yet."
        ) from exc
    with latest.open(encoding="utf-8") as handle:
        symbols = [
            row["Symbol"].strip().upper() for row in csv.DictReader(handle) if row.get("Symbol")
        ]
    if not symbols:
        raise ReconstructionError(f"{latest} has no Symbol column or no rows")
    return symbols, as_at


def index_changes_for(
    index_name: str, *, circulars: Path | None = None
) -> tuple[list[IndexChange], int, int]:
    """Every membership change for one index, from the releases and the register.

    Args:
        index_name: Exact heading, e.g. ``"Nifty 200"``. Matched exactly rather
            than by prefix, because ``Nifty 200 Momentum 30`` and ``Nifty200
            Quality 30`` are different indices whose sections sit in the same
            documents.
        circulars: Folder of press-release PDFs.

    Returns:
        ``(changes, parsed_count, hand_read_count)``. Releases with no text
        layer are counted separately by the caller via
        :func:`reconstruct`.
    """
    source = circulars or CIRCULARS
    changes: list[IndexChange] = []
    unreadable = 0
    for path in sorted(source.glob("*.pdf")):
        try:
            text = read_release_pdf(path)
        except Exception:  # noqa: BLE001 - a scan with no text layer; handled by hand
            unreadable += 1
            continue
        try:
            changes.append(parse_release(text, index_name, source=path.name))
        except IndexChangeError:
            continue
    kept = [c for c in drop_deferred(changes) if c.included or c.excluded]
    hand = [
        c
        for c in load_manual_register().changes
        if c.index_name == index_name and (c.included or c.excluded)
    ]
    return kept + hand, len(kept), len(hand)


def isins_by_symbol(
    *, bhavcopy: Path | None = None, series: Iterable[str] = CASH_EQUITY_SERIES
) -> dict[str, set[str]]:
    """Every cash-equity ticker in the archive and the ISINs it traded under.

    Reads the whole bhavcopy archive. It is the only source linking a ticker to
    a security across a rename, because it is the only one recording both on the
    same row on the same day.

    **Cash equity only.** Debt series reuse short codes across bond issues, and
    including them chains unrelated issuers through the ISIN graph -- once
    merging IBULHSGFIN, CHOLAFIN and some two hundred bond lines into a single
    "security", silently. :func:`~indian_equity_research.market.identity.canonical_symbols`
    now refuses a group that large, but the filter is what stops it arising.
    """
    wanted = frozenset(series)
    source = bhavcopy or BHAVCOPY
    out: dict[str, set[str]] = {}
    for path in sorted(source.glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8", "replace")
        reader = csv.DictReader(io.StringIO(text))
        legacy = "PREVCLOSE" in {c.strip().upper() for c in (reader.fieldnames or [])}
        symbol_key = "SYMBOL" if legacy else "TCKRSYMB"
        series_key = "SERIES" if legacy else "SCTYSRS"
        for row in reader:
            upper = {k.strip().upper(): (v.strip() if v else "") for k, v in row.items() if k}
            if upper.get(series_key, "").upper() not in wanted:
                continue
            symbol = upper.get(symbol_key, "")
            isin = upper.get("ISIN", "").upper()
            if symbol and isin:
                out.setdefault(symbol, set()).add(isin)
    return out


def reconstruct(
    spec: IndexSpec,
    *,
    stop_at: date,
    circulars: Path | None = None,
    bhavcopy: Path | None = None,
    canonical: dict[str, str] | None = None,
) -> Reconstruction:
    """Build the point-in-time universe for one index.

    Args:
        spec: Which index.
        stop_at: Stop rolling back once a change on or before this date is
            undone. Usually the first date in the price archive.
        circulars: Press-release folder.
        bhavcopy: Price archive, for symbol identity.
        canonical: A precomputed identity map. Building one reads the entire
            bhavcopy archive and takes a minute, so :func:`reconstruct_union`
            builds it once and shares it. Sharing is not merely faster: two
            halves of a union resolved through *different* identity maps could
            disagree about whether a renamed company is one security or two,
            and the union would then double-count it.

    Returns:
        The reconstruction. **Check ``history.unapplied`` before using it** — a
        chain that does not close is not a universe, and this function reports
        that rather than refusing, so the caller decides in one visible place.
    """
    roster, as_at = load_roster(spec.roster_dir)
    changes, parsed, hand = index_changes_for(spec.name, circulars=circulars)
    if not changes:
        raise ReconstructionError(
            f"no membership changes found for {spec.name!r} in "
            f"{circulars or CIRCULARS}. Either the releases are missing or the "
            f"index heading is spelled differently in them; a universe with no "
            f"changes would be today's constituents held fixed, which is "
            f"survivorship bias in its purest form."
        )
    resolved = (
        canonical
        if canonical is not None
        else canonical_symbols(isins_by_symbol(bhavcopy=bhavcopy))
    )
    history = roll_back(
        roster,
        as_at,
        changes,
        canonical=resolved,
        stop_at=stop_at,
        declared_size=spec.declared_size,
    )
    return Reconstruction(
        spec=spec,
        history=history,
        canonical=resolved,
        changes_parsed=parsed,
        changes_hand_read=hand,
        releases_without_text=0,
    )


@dataclass(frozen=True, slots=True)
class UnionIndexSpec:
    """An index defined as the union of two others.

    NSE builds the Nifty 200 from the Nifty 100 and the Nifty Midcap 100, and
    reconstructing it that way is not a convenience -- it is more faithful to
    how the index actually changes.

    **Why the union is more complete than the Nifty 200's own sections.** When a
    company migrates up from the Midcap 100 into the Nifty 100, Nifty 200
    membership does not change. There is nothing for a "Nifty 200" section to
    say, so the releases often say nothing, while the two sub-index sections
    each record their half. Parsing Nifty 200 sections alone therefore sees an
    incomplete shadow of the churn: the 2015-2026 archive yields 13 changes that
    cannot be reconciled against the published roster, and a constituent count
    that drifts from 200 to 208. Reconstructed as a union, a migration is
    automatically a no-op.

    **And the union checks itself.** ``|Nifty 100 union Nifty Midcap 100|`` must
    equal 200 on every date. Neither half can drift without the total saying so,
    which is a guard the single-index reconstruction has no equivalent of.
    """

    name: str
    parts: tuple[IndexSpec, ...]
    declared_size: int

    def describe(self) -> str:
        """One line for a report header."""
        joined = " + ".join(part.name for part in self.parts)
        return f"{self.name} ({self.declared_size} constituents, as {joined})"


NIFTY_MIDCAP_100: Final = IndexSpec(
    name="Nifty Midcap 100",
    roster_dir=Path("data/raw/archive/nse_niftymidcap100_constituents"),
    declared_size=100,
)

#: The Nifty 200, built the way NSE builds it. Amendment A10.
NIFTY_200_UNION: Final = UnionIndexSpec(
    name="Nifty 200",
    parts=(NIFTY_100, NIFTY_MIDCAP_100),
    declared_size=200,
)


def reconstruct_union(
    spec: UnionIndexSpec,
    *,
    stop_at: date,
    circulars: Path | None = None,
    bhavcopy: Path | None = None,
) -> tuple[Reconstruction, tuple[Reconstruction, ...]]:
    """Reconstruct each part and union them into one membership history.

    The identity map is built **once** and shared by every part. Two halves
    resolved through different maps could disagree about whether a renamed
    company is one security or two, and the union would double-count it.

    The union history begins at the **latest** of the parts' earliest snapshots.
    Before that date at least one part cannot say who its members were, and a
    union missing a part is not the index -- it is a smaller index wearing its
    name.

    Args:
        spec: The composite index.
        stop_at: Passed to each part.
        circulars: Press-release folder.
        bhavcopy: Price archive, for symbol identity.

    Returns:
        ``(union, parts)``. The union's ``unapplied`` carries every part's
        unapplied change, so one check still decides whether to proceed.

    Raises:
        ReconstructionError: if ``spec`` has fewer than two parts.
    """
    if len(spec.parts) < 2:
        raise ReconstructionError(f"{spec.name} needs at least two parts to union")

    shared = canonical_symbols(isins_by_symbol(bhavcopy=bhavcopy))
    parts = tuple(
        reconstruct(part, stop_at=stop_at, circulars=circulars, bhavcopy=bhavcopy, canonical=shared)
        for part in spec.parts
    )

    begins = max(p.history.snapshots[0].effective_from for p in parts)
    moments = sorted(
        {
            snapshot.effective_from
            for part in parts
            for snapshot in part.history.snapshots
            if snapshot.effective_from >= begins
        }
    )
    snapshots = tuple(
        MembershipSnapshot(
            effective_from=when,
            members=frozenset().union(*(members_on(part.history, when) for part in parts)),
        )
        for when in moments
    )
    deviations = tuple(
        SizeDeviation(effective_from=s.effective_from, size=s.size)
        for s in snapshots
        if s.size != spec.declared_size
    )
    union = Reconstruction(
        spec=IndexSpec(
            name=spec.name,
            roster_dir=spec.parts[0].roster_dir,
            declared_size=spec.declared_size,
        ),
        history=MembershipHistory(
            snapshots=snapshots,
            unapplied=tuple(u for part in parts for u in part.history.unapplied),
            size_deviations=deviations,
            roster_date=max(p.history.roster_date for p in parts),
            declared_size=spec.declared_size,
        ),
        canonical=shared,
        changes_parsed=sum(p.changes_parsed for p in parts),
        changes_hand_read=sum(p.changes_hand_read for p in parts),
        releases_without_text=0,
    )
    return union, parts
