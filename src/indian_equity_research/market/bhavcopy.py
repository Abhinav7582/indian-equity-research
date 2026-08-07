"""NSE bhavcopy parsing across the July 2024 format change.

NSE discontinued the legacy daily bhavcopy with effect from **8 July 2024**,
replacing it with the CM-UDiFF Common Bhavcopy Final (NSE Circular 62424,
12 June 2024). Any ingest covering more than the last two years therefore has
to read two entirely different layouts.

The approach here:

* **Detect by header, not by date.** A date rule breaks on a file that was
  republished, back-filled or renamed. The header is what the file actually
  is.
* **Normalise immediately.** Both parsers emit :class:`BhavRecord`; the raw
  shapes never travel further than this module.
* **Key on ISIN.** Both formats carry it, which is fortunate - it means
  historical rows can be joined without depending on the symbol history and
  its ``ASSUMED_STABLE`` caveat.
* **Cash equities only.** Indices, derivatives and other segments are filtered
  out here rather than being allowed to leak into a price table.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from indian_equity_research.exceptions import IndianEquityResearchError
from indian_equity_research.research.series import PriceSeries

__all__ = [
    "BhavFormat",
    "BhavRecord",
    "BhavcopyError",
    "BhavcopyLoadReport",
    "detect_format",
    "load_bhavcopy_directory",
    "parse_bhavcopy",
    "read_bhavcopy_file",
    "series_by_isin",
    "series_for_isin",
]

#: Date the legacy format was discontinued. Recorded for documentation and
#: boundary testing; parsing never depends on it.
UDIFF_EFFECTIVE_FROM = date(2024, 7, 8)

#: NSE series that are cash equities. EQ settles normally; BE and BZ are
#: trade-to-trade. Everything else (debt, ETFs, warrants) is excluded.
CASH_EQUITY_SERIES = frozenset({"EQ", "BE", "BZ"})

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


class BhavcopyError(IndianEquityResearchError):
    """A bhavcopy file could not be read or was not the expected shape."""


class BhavFormat(StrEnum):
    """Which layout a file uses."""

    LEGACY = "LEGACY"
    UDIFF = "UDIFF"


@dataclass(frozen=True, slots=True)
class BhavRecord:
    """One security's trading for one session, normalised across formats.

    Attributes:
        trade_date: Session date.
        isin: Stable identifier. The join key.
        symbol: Ticker on that date - useful for building symbol history.
        series: NSE series, e.g. ``EQ``.
        open: Opening price.
        high: Session high.
        low: Session low.
        close: Closing price.
        previous_close: Prior session's close, as published.
        volume: Shares traded.
        turnover: Value traded in rupees.
        trades: Number of trades, when published.
    """

    trade_date: date
    isin: str
    symbol: str
    series: str
    open: float
    high: float
    low: float
    close: float
    previous_close: float
    volume: int
    turnover: float
    trades: int | None = None

    @property
    def daily_return(self) -> float | None:
        """Return implied by the published previous close.

        Returns:
            The simple return, or ``None`` when the previous close is unusable.
            Note this is **unadjusted**: on an ex-date it reflects the
            corporate action, which is exactly what the validator looks for.
        """
        if self.previous_close <= 0:
            return None
        return (self.close / self.previous_close) - 1.0

    @property
    def is_consistent(self) -> bool:
        """Whether the OHLC values are internally coherent."""
        return (
            self.low <= self.open <= self.high
            and self.low <= self.close <= self.high
            and self.low > 0
        )


def _clean(value: str | None) -> str:
    """Strip whitespace and quoting from a raw cell."""
    return (value or "").strip().strip('"')


def _number(value: str | None, *, field: str, line: int) -> float:
    """Parse a numeric cell, tolerating thousands separators.

    Args:
        value: Raw cell.
        field: Column name, for the error message.
        line: Line number, for the error message.

    Returns:
        The parsed value.

    Raises:
        BhavcopyError: If the cell is not numeric.
    """
    text = _clean(value).replace(",", "")
    if not text or text == "-":
        return 0.0
    try:
        return float(text)
    except ValueError as exc:
        message = f"line {line}: {field}={value!r} is not numeric."
        raise BhavcopyError(message) from exc


def _parse_date(value: str | None, *, line: int) -> date:
    """Parse a session date in either format's convention.

    Args:
        value: Raw cell, e.g. ``08-JUL-2024`` or ``2024-07-08``.
        line: Line number, for the error message.

    Returns:
        The parsed date.

    Raises:
        BhavcopyError: If no known layout matches.
    """
    text = _clean(value)
    # NSE has published a two-digit year on at least one day (13-Jul-20 in
    # the 2020-07-13 legacy file), so %y must be tried as well.
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%y", "%d-%B-%Y"):
        try:
            return datetime.strptime(text, fmt).date()  # noqa: DTZ007 - calendar date
        except ValueError:
            continue
    message = f"line {line}: {value!r} is not a recognised date."
    raise BhavcopyError(message)


def detect_format(header: list[str]) -> BhavFormat:
    """Identify the layout from the header row.

    Detection is by content rather than by filename or date, so a republished
    or renamed file is still read correctly.

    Args:
        header: Column names as they appear in the file.

    Returns:
        The detected format.

    Raises:
        BhavcopyError: If the header matches neither layout.
    """
    names = {name.strip().upper() for name in header if name}
    if {"TCKRSYMB", "TRADDT", "CLSPRIC"} <= names:
        return BhavFormat.UDIFF
    if {"SYMBOL", "SERIES", "CLOSE", "TIMESTAMP"} <= names:
        return BhavFormat.LEGACY
    message = (
        "Header matches neither the legacy nor the UDiFF bhavcopy layout. "
        f"Columns found: {sorted(names)}"
    )
    raise BhavcopyError(message)


def _parse_legacy(reader: csv.DictReader[str]) -> Iterator[BhavRecord]:
    """Parse rows from the pre-July-2024 layout.

    Args:
        reader: A reader positioned after the header.

    Yields:
        One record per cash-equity row.
    """
    for line, row in enumerate(reader, start=2):
        series = _clean(row.get("SERIES")).upper()
        if series not in CASH_EQUITY_SERIES:
            continue
        isin = _clean(row.get("ISIN")).upper()
        if not _ISIN_RE.match(isin):
            continue
        yield BhavRecord(
            trade_date=_parse_date(row.get("TIMESTAMP"), line=line),
            isin=isin,
            symbol=_clean(row.get("SYMBOL")).upper(),
            series=series,
            open=_number(row.get("OPEN"), field="OPEN", line=line),
            high=_number(row.get("HIGH"), field="HIGH", line=line),
            low=_number(row.get("LOW"), field="LOW", line=line),
            close=_number(row.get("CLOSE"), field="CLOSE", line=line),
            previous_close=_number(row.get("PREVCLOSE"), field="PREVCLOSE", line=line),
            volume=int(_number(row.get("TOTTRDQTY"), field="TOTTRDQTY", line=line)),
            turnover=_number(row.get("TOTTRDVAL"), field="TOTTRDVAL", line=line),
            trades=int(_number(row.get("TOTALTRADES"), field="TOTALTRADES", line=line)) or None,
        )


def _parse_udiff(reader: csv.DictReader[str]) -> Iterator[BhavRecord]:
    """Parse rows from the post-July-2024 UDiFF layout.

    The UDiFF file covers every segment, so cash equities must be selected
    rather than assumed.

    Args:
        reader: A reader positioned after the header.

    Yields:
        One record per cash-equity row.
    """
    for line, row in enumerate(reader, start=2):
        if _clean(row.get("Sgmt")).upper() not in {"CM", ""}:
            continue
        instrument = _clean(row.get("FinInstrmTp")).upper()
        if instrument and instrument not in {"STK", "EQ"}:
            continue
        series = _clean(row.get("SctySrs")).upper()
        if series not in CASH_EQUITY_SERIES:
            continue
        isin = _clean(row.get("ISIN")).upper()
        if not _ISIN_RE.match(isin):
            continue
        yield BhavRecord(
            trade_date=_parse_date(row.get("TradDt"), line=line),
            isin=isin,
            symbol=_clean(row.get("TckrSymb")).upper(),
            series=series,
            open=_number(row.get("OpnPric"), field="OpnPric", line=line),
            high=_number(row.get("HghPric"), field="HghPric", line=line),
            low=_number(row.get("LwPric"), field="LwPric", line=line),
            close=_number(row.get("ClsPric"), field="ClsPric", line=line),
            previous_close=_number(row.get("PrvsClsgPric"), field="PrvsClsgPric", line=line),
            volume=int(_number(row.get("TtlTradgVol"), field="TtlTradgVol", line=line)),
            turnover=_number(row.get("TtlTrfVal"), field="TtlTrfVal", line=line),
            trades=int(_number(row.get("TtlNbOfTxsExctd"), field="TtlNbOfTxsExctd", line=line))
            or None,
        )


def parse_bhavcopy(text: str) -> list[BhavRecord]:
    """Parse bhavcopy CSV content in either layout.

    Args:
        text: Full CSV content.

    Returns:
        Cash-equity records, in file order.

    Raises:
        BhavcopyError: If the content is empty or the layout is unrecognised.
    """
    handle = io.StringIO(text)
    reader = csv.DictReader(handle)
    header = list(reader.fieldnames or [])
    if not header:
        message = "Bhavcopy content has no header row."
        raise BhavcopyError(message)

    layout = detect_format(header)
    records = list(_parse_legacy(reader) if layout is BhavFormat.LEGACY else _parse_udiff(reader))
    if not records:
        message = f"{layout.value} bhavcopy contained no cash-equity rows."
        raise BhavcopyError(message)
    return records


def read_bhavcopy_file(path: Path) -> list[BhavRecord]:
    """Read a bhavcopy from a ``.csv`` or ``.zip`` file.

    NSE publishes these zipped, and the archive normally holds a single CSV.

    Args:
        path: Path to the file.

    Returns:
        Cash-equity records.

    Raises:
        BhavcopyError: If the file is missing, unreadable, or contains no CSV.
    """
    if not path.is_file():
        message = f"No such bhavcopy: {path}"
        raise BhavcopyError(message)

    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                if not members:
                    message = f"{path.name}: zip contains no CSV ({archive.namelist()})."
                    raise BhavcopyError(message)
                if len(members) > 1:
                    message = (
                        f"{path.name}: zip contains {len(members)} CSVs; expected one. "
                        f"Extract it and pass the intended file explicitly."
                    )
                    raise BhavcopyError(message)
                raw = archive.read(members[0])
        except zipfile.BadZipFile as exc:
            message = f"{path.name} is not a valid zip archive."
            raise BhavcopyError(message) from exc
    else:
        raw = path.read_bytes()

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    try:
        return parse_bhavcopy(text)
    except BhavcopyError as exc:
        message = f"{path.name}: {exc}"
        raise BhavcopyError(message) from exc


def series_for_isin(records: list[BhavRecord], isin: str, name: str = "") -> PriceSeries:
    """Build a close-price series for one security from many sessions.

    Args:
        records: Records spanning any number of sessions.
        isin: Security to extract.
        name: Series name for reporting. Defaults to the ISIN.

    Returns:
        A date-ordered :class:`PriceSeries` of closes.

    Raises:
        BhavcopyError: If the ISIN appears in no record, or appears twice on
            one date - which means two series rows were not filtered and the
            price history would be ambiguous.
    """
    wanted = isin.strip().upper()
    by_date: dict[date, float] = {}
    for record in records:
        if record.isin != wanted:
            continue
        if record.trade_date in by_date and by_date[record.trade_date] != record.close:
            message = (
                f"{wanted} has two different closes on {record.trade_date}: "
                f"{by_date[record.trade_date]} and {record.close}. "
                f"Two series rows were not filtered."
            )
            raise BhavcopyError(message)
        by_date[record.trade_date] = record.close

    if not by_date:
        message = f"{wanted} appears in none of the {len(records):,} records supplied."
        raise BhavcopyError(message)
    return PriceSeries.from_mapping(name or wanted, by_date)


@dataclass(frozen=True, slots=True)
class BhavcopyLoadReport:
    """Outcome of reading a directory of bhavcopy files.

    Attributes:
        files_read: Files parsed successfully.
        records: Total cash-equity rows across all files.
        sessions: Distinct session dates seen.
        securities: Distinct ISINs seen.
        failures: ``(filename, reason)`` for files that could not be read.
    """

    files_read: int
    records: int
    sessions: tuple[date, ...]
    securities: int
    failures: tuple[tuple[str, str], ...] = ()

    def summary(self) -> str:
        """Return a one-line description of what was loaded."""
        if not self.files_read:
            return "No bhavcopy files read."
        span = f"{self.sessions[0]} .. {self.sessions[-1]}" if self.sessions else "-"
        failed = f", {len(self.failures)} failed" if self.failures else ""
        return (
            f"{self.files_read:,} files, {self.records:,} rows, "
            f"{len(self.sessions):,} sessions ({span}), "
            f"{self.securities:,} securities{failed}"
        )


def load_bhavcopy_directory(
    directory: Path, pattern: str = "*.zip"
) -> tuple[list[BhavRecord], BhavcopyLoadReport]:
    """Read every bhavcopy file under a directory.

    A file that cannot be parsed is recorded as a failure rather than aborting
    the load: one corrupt download out of several thousand should not prevent
    the rest being used, but it must remain visible.

    Args:
        directory: Directory to search, including subdirectories.
        pattern: Filename glob. Use ``"*.csv"`` for extracted files.

    Returns:
        Every record found, and a report describing the load.

    Raises:
        BhavcopyError: If the directory does not exist.
    """
    if not directory.is_dir():
        message = f"No such bhavcopy directory: {directory}"
        raise BhavcopyError(message)

    records: list[BhavRecord] = []
    failures: list[tuple[str, str]] = []
    read = 0
    for path in sorted(directory.rglob(pattern)):
        try:
            records.extend(read_bhavcopy_file(path))
        except BhavcopyError as exc:
            failures.append((path.name, str(exc)))
            continue
        read += 1

    sessions = tuple(sorted({r.trade_date for r in records}))
    report = BhavcopyLoadReport(
        files_read=read,
        records=len(records),
        sessions=sessions,
        securities=len({r.isin for r in records}),
        failures=tuple(failures),
    )
    return records, report


def series_by_isin(
    records: list[BhavRecord], *, min_observations: int = 2
) -> tuple[dict[str, PriceSeries], list[str]]:
    """Build a close-price series for every security in one pass.

    :func:`series_for_isin` scans the whole record list for each security it is
    asked about. Called once that is fine; called for every security it is
    quadratic - on eleven years of Indian equities that is roughly 3.9 million
    rows times 3,000 securities, and the loop never finishes. This groups the
    records once instead.

    Args:
        records: Records spanning any number of sessions.
        min_observations: Securities with fewer closes than this are omitted;
            a one-day series supports no return at all.

    Returns:
        A mapping of ISIN to price series, and a list of problems for
        securities that could not be assembled - typically two series rows
        publishing different closes for one date.
    """
    grouped: dict[str, dict[date, float]] = {}
    problems: list[str] = []
    conflicted: set[str] = set()

    for record in records:
        by_date = grouped.setdefault(record.isin, {})
        previous = by_date.get(record.trade_date)
        if previous is not None and previous != record.close:
            if record.isin not in conflicted:
                conflicted.add(record.isin)
                problems.append(
                    f"{record.isin}: two different closes on {record.trade_date} "
                    f"({previous} and {record.close}); two series rows were not filtered."
                )
            continue
        by_date[record.trade_date] = record.close

    series: dict[str, PriceSeries] = {}
    for isin, by_date in grouped.items():
        if isin in conflicted or len(by_date) < min_observations:
            continue
        series[isin] = PriceSeries.from_mapping(isin, by_date)
    return series, problems
