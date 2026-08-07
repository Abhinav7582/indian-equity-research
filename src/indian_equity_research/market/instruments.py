"""Instrument identity over time: symbol history built from dated snapshots.

The problem
-----------
Historical Indian market files are keyed on **ticker symbol**. Symbols are not
stable identifiers: they change on restructuring, and they are **reused** after
a delisting. Joining on symbol will eventually attribute one company's price
history to a different company, and it will do so silently.

The fix is to key on ISIN and keep a record of which symbol belonged to which
ISIN on which date. That record is built from daily snapshots of NSE's
``EQUITY_L.csv``.

The honest limitation
---------------------
A snapshot archive can only describe dates it has observed. It says nothing
about 2011. For historical bhavcopy this leaves three cases, and
:class:`Resolution` reports which one applies rather than papering over them:

* ``OBSERVED``  - the mapping was seen in a snapshot covering that date.
* ``ASSUMED_STABLE`` - the symbol maps to exactly one ISIN across every
  snapshot held, and is assumed to have been stable earlier too. Usually right;
  **wrong precisely for the symbols that changed or were reused**, which are
  the cases that matter.
* ``AMBIGUOUS`` / ``UNKNOWN`` - refuse to answer.

Post-July-2024 bhavcopy carries ISIN directly and needs none of this. The gap
is the pre-2024 history, and it cannot be closed by archiving forward. Closing
it properly needs a vendor with point-in-time security master history.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from indian_equity_research.exceptions import IndianEquityResearchError

__all__ = [
    "InstrumentRecord",
    "InstrumentSnapshot",
    "Resolution",
    "ResolutionBasis",
    "SymbolHistory",
    "SymbolSpan",
    "load_snapshot",
    "load_snapshots",
]

#: ISIN: 2-letter country code, 9 alphanumerics, 1 check digit.
_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")

#: Series that settle normally. BE and BZ are trade-to-trade: compulsory
#: delivery, no intraday netting, and BZ additionally signals surveillance.
NORMAL_SERIES = frozenset({"EQ"})
TRADE_TO_TRADE_SERIES = frozenset({"BE", "BZ"})

_DATE_FORMATS = ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d %b %Y")


class InstrumentError(IndianEquityResearchError):
    """An instrument snapshot could not be read or was internally inconsistent."""


class ResolutionBasis(StrEnum):
    """How confident a symbol-to-ISIN resolution is."""

    OBSERVED = "OBSERVED"
    ASSUMED_STABLE = "ASSUMED_STABLE"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Resolution:
    """Outcome of resolving a symbol to an ISIN on a date.

    Attributes:
        symbol: The symbol asked about.
        as_of: The date asked about.
        isin: The resolved ISIN, or ``None`` when not resolvable.
        basis: How the answer was reached.
        detail: Explanation, populated for ambiguous and unknown outcomes.
    """

    symbol: str
    as_of: date
    isin: str | None
    basis: ResolutionBasis
    detail: str = ""

    @property
    def is_reliable(self) -> bool:
        """Whether the mapping was actually observed for that date.

        ``ASSUMED_STABLE`` is deliberately excluded. It is usually correct and
        wrong exactly where the risk lives, so callers building a research
        dataset should treat it as a warning, not a fact.
        """
        return self.basis is ResolutionBasis.OBSERVED


@dataclass(frozen=True, slots=True)
class InstrumentRecord:
    """One security as listed in a snapshot.

    Attributes:
        isin: Stable identifier. The only safe join key.
        symbol: Ticker as of the snapshot date.
        name: Company name.
        series: NSE series, e.g. ``EQ``, ``BE``, ``BZ``.
        listing_date: Date of listing, when parseable.
        face_value: Face value per share, when parseable.
    """

    isin: str
    symbol: str
    name: str
    series: str
    listing_date: date | None = None
    face_value: float | None = None

    @property
    def is_normal_series(self) -> bool:
        """Whether the security settles normally rather than trade-to-trade."""
        return self.series in NORMAL_SERIES

    @property
    def is_trade_to_trade(self) -> bool:
        """Whether the security is in a compulsory-delivery series."""
        return self.series in TRADE_TO_TRADE_SERIES


@dataclass(frozen=True, slots=True)
class InstrumentSnapshot:
    """Every security listed on one date.

    Attributes:
        as_of: Date the snapshot was captured.
        records: Securities, keyed by ISIN.
    """

    as_of: date
    records: dict[str, InstrumentRecord]

    def __len__(self) -> int:
        """Return the number of securities in the snapshot."""
        return len(self.records)

    def by_symbol(self) -> dict[str, InstrumentRecord]:
        """Return the securities keyed by symbol.

        Returns:
            A symbol-to-record mapping. Within a single snapshot a symbol may
            legitimately appear in more than one series (for example ``EQ`` and
            ``BE``); the normally-settling row wins.
        """
        out: dict[str, InstrumentRecord] = {}
        for record in self.records.values():
            existing = out.get(record.symbol)
            if existing is None or (record.is_normal_series and not existing.is_normal_series):
                out[record.symbol] = record
        return out


@dataclass(frozen=True, slots=True)
class SymbolSpan:
    """A period over which a symbol was observed to belong to an ISIN.

    Attributes:
        symbol: The ticker.
        isin: The security it identified.
        first_seen: Earliest snapshot showing this pairing.
        last_seen: Latest snapshot showing it.
        series_seen: Every series observed for the pairing.
    """

    symbol: str
    isin: str
    first_seen: date
    last_seen: date
    series_seen: frozenset[str]

    def covers(self, day: date) -> bool:
        """Whether the pairing was observed on or around ``day``."""
        return self.first_seen <= day <= self.last_seen


def _parse_date(raw: str) -> date | None:
    """Parse a listing date, returning ``None`` when it is absent or odd.

    Args:
        raw: Raw cell contents.

    Returns:
        The parsed date, or ``None``.
    """
    text = raw.strip()
    if not text or text == "-":
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 - calendar date
        except ValueError:
            continue
    return None


def _resolve_column(header: list[str], *candidates: str) -> str | None:
    """Find a column by normalised name.

    NSE ships this file with leading spaces in most headers
    (``" ISIN NUMBER"``), so matching must ignore surrounding whitespace.

    Args:
        header: Column names as they appear.
        *candidates: Acceptable names, upper-case and stripped.

    Returns:
        The matching header, or ``None``.
    """
    lookup = {name.strip().upper(): name for name in header}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def _snapshot_date_from_filename(path: Path) -> date:
    """Extract the capture date from an archived filename.

    Args:
        path: File named ``<source>_YYYY-MM-DD.csv``.

    Returns:
        The capture date.

    Raises:
        InstrumentError: If no ``YYYY-MM-DD`` is present in the name.
    """
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    if not match:
        message = f"{path.name}: expected a YYYY-MM-DD date in the filename."
        raise InstrumentError(message)
    return date.fromisoformat(match.group(1))


def load_snapshot(path: Path, as_of: date | None = None) -> InstrumentSnapshot:
    """Read one archived ``EQUITY_L.csv``.

    Args:
        path: Path to the snapshot.
        as_of: Capture date. Inferred from the filename when omitted.

    Returns:
        The parsed snapshot.

    Raises:
        InstrumentError: If the file is missing, lacks required columns, or
            contains no usable rows.
    """
    if not path.is_file():
        message = f"No such instrument snapshot: {path}"
        raise InstrumentError(message)
    captured = as_of or _snapshot_date_from_filename(path)

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        if not header:
            message = f"{path.name}: no header row."
            raise InstrumentError(message)

        isin_key = _resolve_column(header, "ISIN NUMBER", "ISIN CODE", "ISIN")
        symbol_key = _resolve_column(header, "SYMBOL")
        if not isin_key or not symbol_key:
            message = f"{path.name}: needs SYMBOL and ISIN columns; found {header}."
            raise InstrumentError(message)
        name_key = _resolve_column(header, "NAME OF COMPANY", "COMPANY NAME", "NAME")
        series_key = _resolve_column(header, "SERIES")
        listed_key = _resolve_column(header, "DATE OF LISTING", "LISTING DATE")
        face_key = _resolve_column(header, "FACE VALUE")

        records: dict[str, InstrumentRecord] = {}
        for line, row in enumerate(reader, start=2):
            isin = (row.get(isin_key) or "").strip().upper()
            symbol = (row.get(symbol_key) or "").strip().upper()
            if not isin or not symbol:
                continue
            if not _ISIN_RE.match(isin):
                message = f"{path.name} line {line}: {isin!r} is not a valid ISIN."
                raise InstrumentError(message)
            series = (row.get(series_key) or "").strip().upper() if series_key else ""
            face_raw = (row.get(face_key) or "").strip() if face_key else ""
            try:
                face = float(face_raw.replace(",", "")) if face_raw else None
            except ValueError:
                face = None
            # A security may appear once per series. Keep the normal one.
            existing = records.get(isin)
            candidate = InstrumentRecord(
                isin=isin,
                symbol=symbol,
                name=(row.get(name_key) or "").strip() if name_key else "",
                series=series,
                listing_date=_parse_date(row.get(listed_key) or "") if listed_key else None,
                face_value=face,
            )
            if existing is None or (candidate.is_normal_series and not existing.is_normal_series):
                records[isin] = candidate

    if not records:
        message = f"{path.name}: contained no usable rows."
        raise InstrumentError(message)
    return InstrumentSnapshot(as_of=captured, records=records)


def load_snapshots(
    directory: Path, pattern: str = "nse_equity_master_*.csv"
) -> list[InstrumentSnapshot]:
    """Load every archived snapshot under a directory, oldest first.

    Args:
        directory: Archive root; subdirectories are searched.
        pattern: Filename glob.

    Returns:
        Snapshots sorted by capture date.

    Raises:
        InstrumentError: If nothing matches.
    """
    paths = sorted(directory.rglob(pattern))
    if not paths:
        message = (
            f"No instrument snapshots matching {pattern!r} under {directory}. "
            f"Run: python -m indian_equity_research archive"
        )
        raise InstrumentError(message)
    return sorted((load_snapshot(p) for p in paths), key=lambda s: s.as_of)


@dataclass(frozen=True, slots=True)
class SymbolHistory:
    """Symbol-to-ISIN mappings observed across a series of snapshots.

    Attributes:
        spans: Every observed pairing.
        observed_from: Earliest snapshot date.
        observed_to: Latest snapshot date.
    """

    spans: tuple[SymbolSpan, ...]
    observed_from: date
    observed_to: date

    @classmethod
    def from_snapshots(cls, snapshots: Iterable[InstrumentSnapshot]) -> SymbolHistory:
        """Build a history from dated snapshots.

        Args:
            snapshots: Snapshots in any order.

        Returns:
            The assembled history.

        Raises:
            InstrumentError: If no snapshots are supplied.
        """
        ordered = sorted(snapshots, key=lambda s: s.as_of)
        if not ordered:
            message = "SymbolHistory needs at least one snapshot."
            raise InstrumentError(message)

        first: dict[tuple[str, str], date] = {}
        last: dict[tuple[str, str], date] = {}
        series: dict[tuple[str, str], set[str]] = {}
        for snapshot in ordered:
            for record in snapshot.records.values():
                key = (record.symbol, record.isin)
                first.setdefault(key, snapshot.as_of)
                last[key] = snapshot.as_of
                series.setdefault(key, set()).add(record.series)

        spans = tuple(
            SymbolSpan(
                symbol=symbol,
                isin=isin,
                first_seen=first[(symbol, isin)],
                last_seen=last[(symbol, isin)],
                series_seen=frozenset(series[(symbol, isin)]),
            )
            for symbol, isin in sorted(first)
        )
        return cls(spans=spans, observed_from=ordered[0].as_of, observed_to=ordered[-1].as_of)

    def resolve(self, symbol: str, as_of: date) -> Resolution:
        """Resolve a symbol to an ISIN as at a date.

        Args:
            symbol: Ticker, case-insensitive.
            as_of: Date the symbol was recorded against.

        Returns:
            A :class:`Resolution` stating both the answer and how sure it is.
            Callers must check :attr:`Resolution.basis` rather than assuming
            a non-``None`` ISIN is trustworthy.
        """
        key = symbol.strip().upper()
        candidates = [s for s in self.spans if s.symbol == key]

        if not candidates:
            return Resolution(
                key,
                as_of,
                None,
                ResolutionBasis.UNKNOWN,
                f"{key} appears in no snapshot between {self.observed_from} and "
                f"{self.observed_to}. It may have delisted before archiving began.",
            )

        covering = [s for s in candidates if s.covers(as_of)]
        if len(covering) == 1:
            return Resolution(key, as_of, covering[0].isin, ResolutionBasis.OBSERVED)
        if len(covering) > 1:
            return Resolution(
                key,
                as_of,
                None,
                ResolutionBasis.AMBIGUOUS,
                f"{key} maps to {len(covering)} ISINs on {as_of}: "
                f"{sorted(s.isin for s in covering)}.",
            )

        distinct = {s.isin for s in candidates}
        if len(distinct) == 1:
            return Resolution(
                key,
                as_of,
                next(iter(distinct)),
                ResolutionBasis.ASSUMED_STABLE,
                f"{as_of} predates the archive (starts {self.observed_from}); "
                f"{key} maps to one ISIN in every snapshot held, so stability is "
                f"assumed. Wrong if the symbol was reused or changed earlier.",
            )
        return Resolution(
            key,
            as_of,
            None,
            ResolutionBasis.AMBIGUOUS,
            f"{key} maps to {len(distinct)} different ISINs across the archive: "
            f"{sorted(distinct)}. Cannot resolve for {as_of}.",
        )

    def symbols_with_multiple_isins(self) -> dict[str, list[str]]:
        """Return symbols seen against more than one ISIN.

        These are the reuses and restructurings - the cases where a
        symbol-keyed join silently attributes one company's data to another.

        Returns:
            A symbol-to-ISINs mapping, only for symbols with more than one.
        """
        seen: dict[str, set[str]] = {}
        for span in self.spans:
            seen.setdefault(span.symbol, set()).add(span.isin)
        return {sym: sorted(isins) for sym, isins in sorted(seen.items()) if len(isins) > 1}

    def isins_with_multiple_symbols(self) -> dict[str, list[str]]:
        """Return ISINs seen under more than one symbol - i.e. renames.

        Returns:
            An ISIN-to-symbols mapping, only where more than one symbol was seen.
        """
        seen: dict[str, set[str]] = {}
        for span in self.spans:
            seen.setdefault(span.isin, set()).add(span.symbol)
        return {isin: sorted(syms) for isin, syms in sorted(seen.items()) if len(syms) > 1}
