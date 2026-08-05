"""Read a dated value series from a manually downloaded CSV.

Indian index and volatility CSVs vary in shape between sources and over time:
date formats differ, value columns are named differently, and numbers often
carry thousands separators. This loader is tolerant about those surface
details and strict about everything that could corrupt a result.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from indian_equity_research.exceptions import IndianEquityResearchError
from indian_equity_research.research.series import PriceSeries

__all__ = ["CsvSeriesError", "load_price_series", "load_price_series_glob"]

#: Date layouts seen in NSE and NSE Indices exports.
_DATE_FORMATS = (
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%b-%y",
)

#: Column names that have carried the closing value, lower-cased.
_VALUE_COLUMN_CANDIDATES = (
    "close",
    "closing value",
    "total returns index",
    "index value",
    "value",
    "close price",
    "closing index value",
)

_DATE_COLUMN_CANDIDATES = ("date", "index date", "hist_date", "timestamp")


class CsvSeriesError(IndianEquityResearchError):
    """A CSV could not be read into a valid series."""


def _parse_date(raw: str) -> datetime:
    """Parse a date string using the known Indian export formats.

    Args:
        raw: The raw cell contents.

    Returns:
        The parsed datetime.

    Raises:
        CsvSeriesError: If no known format matches.
    """
    text = raw.strip().strip('"')
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)  # noqa: DTZ007 - calendar date, no timezone
        except ValueError:
            continue
    message = f"Unrecognised date {text!r}. Known formats: {', '.join(_DATE_FORMATS)}."
    raise CsvSeriesError(message)


def _parse_value(raw: str) -> float:
    """Parse a numeric cell, tolerating thousands separators and quoting.

    Args:
        raw: The raw cell contents.

    Returns:
        The parsed value.

    Raises:
        CsvSeriesError: If the cell is not numeric.
    """
    text = raw.strip().strip('"').replace(",", "")
    if not text or text == "-":
        message = "Empty or placeholder numeric cell."
        raise CsvSeriesError(message)
    try:
        return float(text)
    except ValueError as exc:
        message = f"Non-numeric value {raw!r}."
        raise CsvSeriesError(message) from exc


def _resolve_column(header: list[str], candidates: tuple[str, ...], role: str) -> str:
    """Find the column matching one of the candidate names.

    Args:
        header: Column names from the CSV.
        candidates: Acceptable names, lower-cased.
        role: Human-readable role, used in the error message.

    Returns:
        The matching column name as it appears in the header.

    Raises:
        CsvSeriesError: If no candidate matches.
    """
    lowered = {name.strip().lower(): name for name in header}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    message = (
        f"No {role} column found. Looked for {list(candidates)}; "
        f"the file has {header}. Pass the column name explicitly."
    )
    raise CsvSeriesError(message)


def load_price_series(
    path: Path,
    name: str,
    *,
    date_column: str | None = None,
    value_column: str | None = None,
) -> PriceSeries:
    """Load a dated value series from a CSV file.

    Args:
        path: Path to the CSV.
        name: Identifier for the resulting series.
        date_column: Explicit date column name. Auto-detected when omitted.
        value_column: Explicit value column name. Auto-detected when omitted.

    Returns:
        A validated, date-ordered :class:`PriceSeries`.

    Raises:
        CsvSeriesError: If the file is missing, empty, malformed, or contains
            duplicate dates. The message names the file and the offending row.
    """
    if not path.is_file():
        message = f"{name}: no such file: {path}"
        raise CsvSeriesError(message)

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        if not header:
            message = f"{name}: {path.name} has no header row."
            raise CsvSeriesError(message)

        date_key = date_column or _resolve_column(list(header), _DATE_COLUMN_CANDIDATES, "date")
        value_key = value_column or _resolve_column(list(header), _VALUE_COLUMN_CANDIDATES, "value")

        observations: dict[object, float] = {}
        for line_number, row in enumerate(reader, start=2):
            raw_date = row.get(date_key)
            raw_value = row.get(value_key)
            if raw_date is None or raw_value is None:
                continue
            if not raw_date.strip():
                continue
            try:
                when = _parse_date(raw_date).date()
                value = _parse_value(raw_value)
            except CsvSeriesError as exc:
                message = f"{name}: {path.name} line {line_number}: {exc}"
                raise CsvSeriesError(message) from exc
            if when in observations:
                message = f"{name}: {path.name} line {line_number}: duplicate date {when}."
                raise CsvSeriesError(message)
            observations[when] = value

    if not observations:
        message = f"{name}: {path.name} contained no usable rows."
        raise CsvSeriesError(message)

    try:
        return PriceSeries.from_mapping(name, observations)  # type: ignore[arg-type]
    except ValueError as exc:
        message = f"{name}: {path.name} produced an invalid series: {exc}"
        raise CsvSeriesError(message) from exc


def load_price_series_glob(
    directory: Path,
    pattern: str,
    name: str,
    *,
    date_column: str | None = None,
    value_column: str | None = None,
) -> PriceSeries:
    """Load and merge every CSV matching a glob into one series.

    Index providers cap a single download to a limited date range, so a long
    history arrives as one file per year. This merges them.

    Overlapping ranges are expected and tolerated **only when they agree**: a
    date appearing in two files with the same value is a harmless overlap, a
    date appearing with two different values means one of the files is wrong
    and is rejected rather than silently resolved.

    Args:
        directory: Directory to search.
        pattern: Glob pattern, e.g. ``"nifty100_pr*.csv"``.
        name: Identifier for the merged series.
        date_column: Explicit date column. Auto-detected when omitted.
        value_column: Explicit value column. Auto-detected when omitted.

    Returns:
        The merged, date-ordered series.

    Raises:
        CsvSeriesError: If nothing matches, or two files disagree on a date.
    """
    paths = sorted(directory.glob(pattern))
    if not paths:
        message = (
            f"{name}: no files matching {pattern!r} in {directory}. "
            f"Download the CSV and save it there."
        )
        raise CsvSeriesError(message)

    merged: dict[object, float] = {}
    origin: dict[object, str] = {}
    for path in paths:
        part = load_price_series(path, name, date_column=date_column, value_column=value_column)
        for when, value in part:
            if when in merged and abs(merged[when] - value) > 1e-6:
                message = (
                    f"{name}: conflicting values for {when}: "
                    f"{merged[when]} in {origin[when]} but {value} in {path.name}. "
                    f"One of these files is wrong; remove it and re-download."
                )
                raise CsvSeriesError(message)
            merged[when] = value
            origin.setdefault(when, path.name)

    try:
        return PriceSeries.from_mapping(name, merged)  # type: ignore[arg-type]
    except ValueError as exc:
        message = f"{name}: merged {len(paths)} file(s) into an invalid series: {exc}"
        raise CsvSeriesError(message) from exc
