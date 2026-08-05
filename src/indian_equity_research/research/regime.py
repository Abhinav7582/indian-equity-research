"""The H4 market-regime rule, exactly as declared in Amendment A2.

    RISK-OFF when the Nifty 100 closes below its 200-day simple moving average
    AND India VIX closes above its trailing three-year 80th percentile.
    Otherwise RISK-ON.

Two properties are enforced by construction and asserted by tests:

**Causality.** The state on date *T* uses only observations up to and including
*T*. Appending future data can never alter a previously computed state.

**No silent defaults.** Before either rolling window is full the state is
``UNKNOWN``, never ``RISK_ON``. Defaulting during warm-up would quietly assert
a market view for the first three years of any sample.

Acting on a state is a separate concern with its own lag; see
:func:`lag_states`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import pairwise

from indian_equity_research.research.series import (
    PriceSeries,
    align,
    rolling_mean,
    rolling_quantile,
)

__all__ = ["Regime", "RegimeConfig", "RegimeSeries", "compute_regime", "lag_states"]

#: Trading days in three calendar years, at roughly 252 sessions per year.
TRADING_DAYS_PER_YEAR = 252


class Regime(StrEnum):
    """Market state under the Amendment A2 rule."""

    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    #: Insufficient history for at least one input. Never treated as a view.
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RegimeConfig:
    """Parameters of the A2 rule.

    These are the declared values. They are exposed as fields so that
    sensitivity can be *reported*, not so that they can be tuned: Amendment A2
    fixes them, and changing them for a headline result would require a further
    dated amendment.

    Attributes:
        sma_window: Trend lookback in trading days.
        vix_quantile: Percentile of trailing India VIX above which volatility
            counts as elevated.
        vix_window: Trailing window for the VIX percentile, in trading days.
    """

    sma_window: int = 200
    vix_quantile: float = 0.80
    vix_window: int = 3 * TRADING_DAYS_PER_YEAR

    def __post_init__(self) -> None:
        """Reject parameters outside the ranges the rule is defined for."""
        if self.sma_window <= 1:
            message = f"sma_window must exceed 1, got {self.sma_window}."
            raise ValueError(message)
        if not 0.0 < self.vix_quantile < 1.0:
            message = f"vix_quantile must be strictly within (0, 1), got {self.vix_quantile}."
            raise ValueError(message)
        if self.vix_window <= 1:
            message = f"vix_window must exceed 1, got {self.vix_window}."
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class RegimeSeries:
    """Computed regime states with the inputs that produced them.

    Attributes:
        dates: Observation dates, aligned across both inputs.
        states: Regime state per date.
        market_close: Market index close per date.
        market_sma: Trend average per date, ``None`` during warm-up.
        vix_close: India VIX close per date.
        vix_threshold: Trailing percentile per date, ``None`` during warm-up.
        config: Parameters used.
    """

    dates: tuple[date, ...]
    states: tuple[Regime, ...]
    market_close: tuple[float, ...]
    market_sma: tuple[float | None, ...]
    vix_close: tuple[float, ...]
    vix_threshold: tuple[float | None, ...]
    config: RegimeConfig

    def __len__(self) -> int:
        """Return the number of dated states."""
        return len(self.dates)

    def as_mapping(self) -> dict[date, Regime]:
        """Return ``{date: state}``."""
        return dict(zip(self.dates, self.states, strict=True))

    def switch_count(self) -> int:
        """Count transitions between RISK_ON and RISK_OFF.

        Transitions into or out of ``UNKNOWN`` are not switches: the warm-up
        boundary is an artefact of sample length, not a market event.

        Returns:
            The number of genuine state changes.
        """
        known = [s for s in self.states if s is not Regime.UNKNOWN]
        return sum(1 for a, b in pairwise(known) if a is not b)

    def switches_per_year(self) -> float:
        """Average switches per year over the dated (non-warm-up) span.

        Returns:
            Switches per year, or ``0.0`` if the span is too short to annualise.
        """
        known_dates = [
            d for d, s in zip(self.dates, self.states, strict=True) if s is not Regime.UNKNOWN
        ]
        if len(known_dates) < 2:
            return 0.0
        years = (known_dates[-1] - known_dates[0]).days / 365.25
        return self.switch_count() / years if years > 0 else 0.0

    def fraction_risk_off(self) -> float:
        """Share of dated observations spent in RISK_OFF.

        Returns:
            A value in ``[0, 1]``, or ``0.0`` if no state is known.
        """
        known = [s for s in self.states if s is not Regime.UNKNOWN]
        if not known:
            return 0.0
        return sum(1 for s in known if s is Regime.RISK_OFF) / len(known)


def compute_regime(
    market: PriceSeries,
    vix: PriceSeries,
    config: RegimeConfig | None = None,
) -> RegimeSeries:
    """Compute the A2 regime state for every common date.

    Args:
        market: Broad-market **price return** index. A total-return index is
            wrong here: reinvested dividends make the level drift upward
            relative to its own moving average, biasing the trend signal.
        vix: India VIX daily closes.
        config: Rule parameters. Defaults to the values declared in A2.

    Returns:
        A :class:`RegimeSeries` covering the dates common to both inputs.

    Raises:
        ValueError: If the two series share no dates.
    """
    cfg = config or RegimeConfig()
    dates, (market_close, vix_close) = align(market, vix)

    sma = rolling_mean(market_close, cfg.sma_window)
    threshold = rolling_quantile(vix_close, cfg.vix_window, cfg.vix_quantile)

    states: list[Regime] = []
    for close, avg, vix_value, limit in zip(market_close, sma, vix_close, threshold, strict=True):
        if avg is None or limit is None:
            states.append(Regime.UNKNOWN)
            continue
        # Both conditions required. Declared in A2: fewer false alarms, at the
        # cost of being slow to de-risk.
        below_trend = close < avg
        elevated_vol = vix_value > limit
        states.append(Regime.RISK_OFF if (below_trend and elevated_vol) else Regime.RISK_ON)

    return RegimeSeries(
        dates=dates,
        states=tuple(states),
        market_close=market_close,
        market_sma=tuple(sma),
        vix_close=vix_close,
        vix_threshold=tuple(threshold),
        config=cfg,
    )


def lag_states(states: tuple[Regime, ...], lag: int = 1) -> tuple[Regime, ...]:
    """Shift states forward so a signal is acted on after it is observed.

    A regime computed from the close of day *T* cannot be traded until day
    *T+1* at the earliest. Amendment A2 requires this lag explicitly.

    Args:
        states: States in chronological order.
        lag: Number of periods to delay. Must not be negative.

    Returns:
        States shifted forward by ``lag``, padded at the front with
        ``UNKNOWN`` so that no position is implied before a signal existed.

    Raises:
        ValueError: If ``lag`` is negative.
    """
    if lag < 0:
        message = f"lag must not be negative, got {lag}."
        raise ValueError(message)
    if lag == 0:
        return states
    return (Regime.UNKNOWN,) * lag + states[:-lag]
