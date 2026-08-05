"""Aligned daily price series and the rolling statistics H4 needs.

Implemented with the standard library only. The dataset is roughly 4,500 daily
observations across four series; a dataframe dependency would buy nothing and
would make the look-ahead properties harder to verify by reading the code.

Every rolling statistic here is **causal**: the value at index ``i`` uses only
observations at indices ``<= i``. Tests assert this directly rather than
trusting the implementation.
"""

from __future__ import annotations

from bisect import bisect_left, insort
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise

__all__ = [
    "PriceSeries",
    "align",
    "rolling_mean",
    "rolling_quantile",
    "simple_returns",
]


@dataclass(frozen=True, slots=True)
class PriceSeries:
    """An immutable, date-ordered series of daily closes.

    Attributes:
        name: Human-readable identifier, used in reports and error messages.
        dates: Strictly increasing observation dates.
        closes: Closing values, parallel to ``dates``.
    """

    name: str
    dates: tuple[date, ...]
    closes: tuple[float, ...]

    def __post_init__(self) -> None:
        """Validate the invariants the rest of the module relies on."""
        if len(self.dates) != len(self.closes):
            message = f"{self.name}: {len(self.dates)} dates but {len(self.closes)} closes."
            raise ValueError(message)
        if any(b <= a for a, b in pairwise(self.dates)):
            message = f"{self.name}: dates must be strictly increasing with no duplicates."
            raise ValueError(message)
        if any(c <= 0 for c in self.closes):
            message = f"{self.name}: closes must be positive."
            raise ValueError(message)

    def __len__(self) -> int:
        """Return the number of observations."""
        return len(self.dates)

    def __iter__(self) -> Iterator[tuple[date, float]]:
        """Iterate as ``(date, close)`` pairs."""
        return zip(self.dates, self.closes, strict=True)

    @classmethod
    def from_mapping(cls, name: str, data: Mapping[date, float]) -> PriceSeries:
        """Build a series from a date-to-close mapping, sorting by date.

        Args:
            name: Series identifier.
            data: Closes keyed by observation date.

        Returns:
            A validated, date-ordered series.
        """
        ordered = sorted(data.items())
        return cls(
            name=name,
            dates=tuple(d for d, _ in ordered),
            closes=tuple(float(c) for _, c in ordered),
        )

    def as_mapping(self) -> dict[date, float]:
        """Return the series as a plain ``{date: close}`` dictionary."""
        return dict(zip(self.dates, self.closes, strict=True))

    def slice_from(self, start: date) -> PriceSeries:
        """Return the sub-series on or after ``start``.

        Args:
            start: First date to retain.

        Returns:
            A new series containing only observations on or after ``start``.
        """
        kept = [(d, c) for d, c in self if d >= start]
        return PriceSeries(
            name=self.name,
            dates=tuple(d for d, _ in kept),
            closes=tuple(c for _, c in kept),
        )


def align(*series: PriceSeries) -> tuple[tuple[date, ...], tuple[tuple[float, ...], ...]]:
    """Restrict several series to their common dates.

    Indices published by different sources have different holiday handling and
    occasional gaps. Comparing them on anything other than their intersection
    silently invents observations.

    Args:
        *series: Two or more series to align.

    Returns:
        A ``(dates, values)`` pair where ``values[i]`` corresponds to
        ``series[i]`` restricted to the common dates.

    Raises:
        ValueError: If fewer than two series are given, or the intersection is
            empty.
    """
    if len(series) < 2:
        message = "align() needs at least two series."
        raise ValueError(message)

    common = set(series[0].dates)
    for other in series[1:]:
        common &= set(other.dates)
    if not common:
        names = ", ".join(s.name for s in series)
        message = f"No overlapping dates between: {names}."
        raise ValueError(message)

    dates = tuple(sorted(common))
    values = tuple(tuple(s.as_mapping()[d] for d in dates) for s in series)
    return dates, values


def rolling_mean(values: Sequence[float], window: int) -> list[float | None]:
    """Causal simple moving average.

    Args:
        values: Observations in chronological order.
        window: Number of observations in the average.

    Returns:
        A list the same length as ``values``. Entries before the window is full
        are ``None`` rather than a partial average — a 200-day average computed
        from 30 observations is not a 200-day average, and defaulting it would
        silently change the regime during the warm-up period.

    Raises:
        ValueError: If ``window`` is not positive.
    """
    if window <= 0:
        message = f"window must be positive, got {window}."
        raise ValueError(message)

    out: list[float | None] = []
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= window:
            running -= values[i - window]
        out.append(running / window if i >= window - 1 else None)
    return out


def rolling_quantile(values: Sequence[float], window: int, quantile: float) -> list[float | None]:
    """Causal rolling quantile using linear interpolation between order statistics.

    Args:
        values: Observations in chronological order.
        window: Number of trailing observations, inclusive of the current one.
        quantile: Target quantile in ``[0, 1]``.

    Returns:
        A list the same length as ``values``, with ``None`` until the window is
        full.

    Raises:
        ValueError: If ``window`` is not positive or ``quantile`` is outside
            ``[0, 1]``.
    """
    if window <= 0:
        message = f"window must be positive, got {window}."
        raise ValueError(message)
    if not 0.0 <= quantile <= 1.0:
        message = f"quantile must be in [0, 1], got {quantile}."
        raise ValueError(message)

    out: list[float | None] = []
    ordered: list[float] = []
    for i, value in enumerate(values):
        insort(ordered, value)
        if i >= window:
            stale = values[i - window]
            ordered.pop(bisect_left(ordered, stale))
        if i < window - 1:
            out.append(None)
            continue
        position = quantile * (len(ordered) - 1)
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        weight = position - low
        out.append(ordered[low] * (1 - weight) + ordered[high] * weight)
    return out


def simple_returns(values: Sequence[float]) -> list[float]:
    """Period-over-period simple returns.

    Args:
        values: Levels in chronological order.

    Returns:
        A list of length ``len(values) - 1``; ``out[i]`` is the return from
        ``values[i]`` to ``values[i + 1]``.
    """
    return [(b / a) - 1.0 for a, b in pairwise(values)]
