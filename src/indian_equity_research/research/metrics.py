"""Performance and drawdown metrics for the H4 evaluation.

Only the metrics Amendment A2 actually scores on are implemented. Adding
metrics that no criterion depends on invites picking the flattering one after
the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

__all__ = [
    "DrawdownEpisode",
    "PerformanceSummary",
    "annualised_volatility",
    "cagr",
    "drawdown_episodes",
    "equity_curve",
    "max_drawdown",
    "summarise",
]

TRADING_DAYS_PER_YEAR = 252
#: Episodes shallower than this are ordinary noise, not distinct events. Used
#: only for the A2 criterion "benefit present in more than one episode".
MATERIAL_DRAWDOWN = 0.10


@dataclass(frozen=True, slots=True)
class DrawdownEpisode:
    """A peak-to-trough-to-recovery drawdown.

    Attributes:
        peak_date: Date of the high-water mark that began the decline.
        trough_date: Date of the lowest point.
        recovery_date: Date the previous peak was regained, or ``None`` if it
            never was within the sample.
        depth: Maximum decline as a positive fraction (0.25 means a 25% decline).
    """

    peak_date: date
    trough_date: date
    recovery_date: date | None
    depth: float

    @property
    def recovered(self) -> bool:
        """Whether the previous peak was regained within the sample."""
        return self.recovery_date is not None


@dataclass(frozen=True, slots=True)
class PerformanceSummary:
    """Metrics scored by the A2 pass/fail criteria.

    Attributes:
        label: Identifier for reporting, e.g. ``"overlaid"``.
        start: First date in the evaluated span.
        end: Last date in the evaluated span.
        years: Span length in years.
        final_value: Terminal equity.
        total_return: Cumulative return as a fraction.
        cagr: Compound annual growth rate.
        max_drawdown: Deepest peak-to-trough decline, positive fraction.
        volatility: Annualised standard deviation of periodic returns.
        calmar: CAGR divided by max drawdown.
        material_episodes: Count of drawdowns at least ``MATERIAL_DRAWDOWN`` deep.
    """

    label: str
    start: date
    end: date
    years: float
    final_value: float
    total_return: float
    cagr: float
    max_drawdown: float
    volatility: float
    calmar: float
    material_episodes: int


def equity_curve(returns: list[float], initial: float = 1.0) -> list[float]:
    """Compound a return stream into an equity curve.

    Args:
        returns: Periodic simple returns.
        initial: Starting capital.

    Returns:
        A curve of length ``len(returns) + 1``; the first entry is ``initial``.
    """
    curve = [initial]
    for r in returns:
        curve.append(curve[-1] * (1.0 + r))
    return curve


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Compound annual growth rate.

    Args:
        start_value: Beginning equity. Must be positive.
        end_value: Ending equity.
        years: Elapsed years. Must be positive.

    Returns:
        The annualised growth rate. Returns ``-1.0`` for a total loss.

    Raises:
        ValueError: If ``start_value`` or ``years`` is not positive.
    """
    if start_value <= 0:
        message = f"start_value must be positive, got {start_value}."
        raise ValueError(message)
    if years <= 0:
        message = f"years must be positive, got {years}."
        raise ValueError(message)
    if end_value <= 0:
        return -1.0
    return float((end_value / start_value) ** (1.0 / years)) - 1.0


def max_drawdown(curve: list[float]) -> float:
    """Deepest peak-to-trough decline in an equity curve.

    Args:
        curve: Equity values in chronological order.

    Returns:
        The decline as a positive fraction; ``0.0`` for a curve that never
        falls below a prior peak.
    """
    if not curve:
        return 0.0
    peak = curve[0]
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        worst = max(worst, (peak - value) / peak)
    return worst


def drawdown_episodes(
    dates: list[date], curve: list[float], minimum_depth: float = MATERIAL_DRAWDOWN
) -> list[DrawdownEpisode]:
    """Identify distinct drawdowns at least ``minimum_depth`` deep.

    Amendment A2 rejects H4 if the drawdown benefit comes from a single
    historical episode, so episodes must be separable rather than aggregated
    into one worst-case number.

    Args:
        dates: Dates parallel to ``curve``.
        curve: Equity values in chronological order.
        minimum_depth: Minimum depth, as a positive fraction, for an episode to
            count as material.

    Returns:
        Episodes in chronological order.

    Raises:
        ValueError: If ``dates`` and ``curve`` differ in length.
    """
    if len(dates) != len(curve):
        message = f"dates ({len(dates)}) and curve ({len(curve)}) must be the same length."
        raise ValueError(message)
    if not curve:
        return []

    episodes: list[DrawdownEpisode] = []
    peak_value = curve[0]
    peak_index = 0
    trough_value = curve[0]
    trough_index = 0
    in_drawdown = False

    for i, value in enumerate(curve):
        if value >= peak_value:
            if in_drawdown:
                depth = (peak_value - trough_value) / peak_value
                if depth >= minimum_depth:
                    episodes.append(
                        DrawdownEpisode(
                            peak_date=dates[peak_index],
                            trough_date=dates[trough_index],
                            recovery_date=dates[i],
                            depth=depth,
                        )
                    )
                in_drawdown = False
            peak_value = value
            peak_index = i
            trough_value = value
            trough_index = i
        else:
            in_drawdown = True
            if value < trough_value:
                trough_value = value
                trough_index = i

    # A drawdown still open at the end of the sample is real and must be
    # reported; dropping it would flatter the result.
    if in_drawdown:
        depth = (peak_value - trough_value) / peak_value
        if depth >= minimum_depth:
            episodes.append(
                DrawdownEpisode(
                    peak_date=dates[peak_index],
                    trough_date=dates[trough_index],
                    recovery_date=None,
                    depth=depth,
                )
            )
    return episodes


def annualised_volatility(
    returns: list[float], periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    """Annualised standard deviation of periodic returns.

    Args:
        returns: Periodic simple returns.
        periods_per_year: Observations per year for scaling.

    Returns:
        Annualised volatility, or ``0.0`` for fewer than two observations.
    """
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return sqrt(variance) * sqrt(periods_per_year)


def summarise(
    label: str,
    dates: list[date],
    curve: list[float],
    returns: list[float],
) -> PerformanceSummary:
    """Compute every metric the A2 criteria score on.

    Args:
        label: Identifier for reporting.
        dates: Dates parallel to ``curve``.
        curve: Equity values in chronological order.
        returns: Periodic returns, of length ``len(curve) - 1``.

    Returns:
        A populated :class:`PerformanceSummary`.

    Raises:
        ValueError: If the inputs are empty or inconsistent in length.
    """
    if not curve or not dates:
        message = f"{label}: cannot summarise an empty curve."
        raise ValueError(message)
    if len(dates) != len(curve):
        message = f"{label}: dates ({len(dates)}) and curve ({len(curve)}) differ."
        raise ValueError(message)

    years = (dates[-1] - dates[0]).days / 365.25
    drawdown = max_drawdown(curve)
    growth = cagr(curve[0], curve[-1], years) if years > 0 else 0.0
    return PerformanceSummary(
        label=label,
        start=dates[0],
        end=dates[-1],
        years=years,
        final_value=curve[-1],
        total_return=(curve[-1] / curve[0]) - 1.0,
        cagr=growth,
        max_drawdown=drawdown,
        volatility=annualised_volatility(returns),
        calmar=(growth / drawdown) if drawdown > 0 else float("inf"),
        material_episodes=len(drawdown_episodes(dates, curve)),
    )
