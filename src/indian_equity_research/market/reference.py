"""Assemble reference data from whatever is on disk.

Reference data arrives from two independent places and neither is guaranteed
to be present:

* the **trading calendar** is derived from index series in
  ``data/raw/indices`` - every date on which an index printed a close is a
  date on which the market traded;
* the **instrument master** comes from archived ``EQUITY_L.csv`` snapshots in
  ``data/raw/archive``.

Each piece is optional and reported as absent rather than faked. A missing
calendar must never silently degrade into a weekday rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from indian_equity_research.data.csv_series import CsvSeriesError, load_price_series_glob
from indian_equity_research.market.calendar import TradingCalendar
from indian_equity_research.market.instruments import (
    InstrumentError,
    InstrumentSnapshot,
    SymbolHistory,
    load_snapshots,
)

__all__ = ["ReferenceData", "build_reference", "calendar_from_index_series"]

#: Index series preferred for deriving the calendar, best first. A broad index
#: trades on every session; a narrow or newer one may not.
_CALENDAR_SOURCES = (
    ("nifty100_pr*.csv", "Nifty 100 PR"),
    ("nifty200_momentum30_tri*.csv", "Nifty200 Momentum 30 TRI"),
    ("india_vix*.csv", "India VIX"),
)


def calendar_from_index_series(indices_dir: Path) -> tuple[TradingCalendar, str]:
    """Derive a trading calendar from whichever index series is available.

    Args:
        indices_dir: Directory holding downloaded index CSVs.

    Returns:
        The calendar and the name of the series it came from.

    Raises:
        CsvSeriesError: If no usable index series is present.
    """
    problems: list[str] = []
    for pattern, label in _CALENDAR_SOURCES:
        try:
            series = load_price_series_glob(indices_dir, pattern, label)
        except CsvSeriesError as exc:
            problems.append(f"{label}: {exc}")
            continue
        return TradingCalendar.from_dates(series.dates), label
    message = "No index series available to derive a calendar from. " + " | ".join(problems)
    raise CsvSeriesError(message)


@dataclass(frozen=True, slots=True)
class ReferenceData:
    """Whatever reference data could be assembled.

    Attributes:
        calendar: Observed trading sessions, or ``None`` if unavailable.
        calendar_source: Series the calendar was derived from.
        calendar_problem: Why the calendar is missing, when it is.
        symbols: Symbol history, or ``None`` if no snapshots are archived.
        latest_snapshot: Most recent instrument snapshot.
        instrument_problem: Why instruments are missing, when they are.
    """

    calendar: TradingCalendar | None = None
    calendar_source: str = ""
    calendar_problem: str = ""
    symbols: SymbolHistory | None = None
    latest_snapshot: InstrumentSnapshot | None = None
    instrument_problem: str = ""

    @property
    def is_complete(self) -> bool:
        """Whether both the calendar and the instrument master are available."""
        return self.calendar is not None and self.symbols is not None


def build_reference(data_root: Path) -> ReferenceData:
    """Assemble reference data, reporting rather than raising on absence.

    Args:
        data_root: The ``data/raw`` directory.

    Returns:
        A :class:`ReferenceData` with each piece either populated or
        accompanied by an explanation of why it is missing.
    """
    calendar: TradingCalendar | None = None
    source = ""
    calendar_problem = ""
    try:
        calendar, source = calendar_from_index_series(data_root / "indices")
    except CsvSeriesError as exc:
        calendar_problem = str(exc)

    symbols: SymbolHistory | None = None
    latest: InstrumentSnapshot | None = None
    instrument_problem = ""
    try:
        snapshots = load_snapshots(data_root / "archive")
        symbols = SymbolHistory.from_snapshots(snapshots)
        latest = snapshots[-1]
    except InstrumentError as exc:
        instrument_problem = str(exc)

    return ReferenceData(
        calendar=calendar,
        calendar_source=source,
        calendar_problem=calendar_problem,
        symbols=symbols,
        latest_snapshot=latest,
        instrument_problem=instrument_problem,
    )
