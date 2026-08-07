"""Corporate actions, and validation of price series against them.

**This module is written before the adjustment engine, deliberately.** An
engine built first produces plausible-looking numbers with nothing to check
them against; the errors it makes are invisible and they flatter results. So
the acceptance test comes first and the engine is built to satisfy it.

The rule from ``docs/data_principles.md``:

> Every absolute daily return greater than 25% is explained by a documented
> corporate action or a documented market event. Unexplained outliers block
> the pipeline.

Four classifications, only one of which is a hard failure:

* ``EXPLAINED_BY_ACTION`` - a corporate action has an ex-date on that day.
* ``EXPLAINED_BY_MARKET`` - the market itself moved comparably. A crash is not
  a data error, and detecting it cross-sectionally means no hardcoded list of
  historical events to maintain.
* ``SUSPECTED_UNADJUSTED_ACTION`` - the move is suspiciously close to a simple
  ratio (-50%, -66.7%, -80%, -90%). An unadjusted 1:2 split is exactly -50%,
  and finding these is the single highest-value check here.
* ``UNEXPLAINED`` - blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from itertools import pairwise

from indian_equity_research.research.series import PriceSeries

__all__ = [
    "ActionType",
    "AnomalyClass",
    "CorporateAction",
    "ReturnAnomaly",
    "ValidationConfig",
    "ValidationReport",
    "validate_adjustment_factors",
    "validate_price_series",
]


class ActionType(StrEnum):
    """Kinds of corporate action that change the price basis."""

    SPLIT = "SPLIT"
    BONUS = "BONUS"
    DIVIDEND = "DIVIDEND"
    RIGHTS = "RIGHTS"
    DEMERGER = "DEMERGER"
    CONSOLIDATION = "CONSOLIDATION"
    OTHER = "OTHER"


class AnomalyClass(StrEnum):
    """How a large daily move was accounted for."""

    EXPLAINED_BY_ACTION = "EXPLAINED_BY_ACTION"
    EXPLAINED_BY_MARKET = "EXPLAINED_BY_MARKET"
    SUSPECTED_UNADJUSTED_ACTION = "SUSPECTED_UNADJUSTED_ACTION"
    UNEXPLAINED = "UNEXPLAINED"


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """One documented action.

    Attributes:
        isin: Security affected.
        ex_date: First date the price trades without the entitlement.
        action_type: What happened.
        ratio_from: Old share count in a split or bonus ratio.
        ratio_to: New share count.
        amount: Cash amount for a dividend.
        source: Where the record came from, for lineage.
    """

    isin: str
    ex_date: date
    action_type: ActionType
    ratio_from: int | None = None
    ratio_to: int | None = None
    amount: float | None = None
    source: str = ""

    @property
    def price_multiplier(self) -> float | None:
        """Expected price ratio across the ex-date, ignoring market movement.

        A 1:2 split multiplies share count by 2, so the price should fall to
        one half.

        Returns:
            The expected ``close / previous_close``, or ``None`` when the
            action carries no ratio.
        """
        if self.ratio_from is None or self.ratio_to is None or self.ratio_to == 0:
            return None
        return self.ratio_from / self.ratio_to


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Thresholds for the checks.

    Attributes:
        outlier_threshold: Absolute daily return above which a move is
            examined. 0.25 is the figure fixed in ``data_principles.md``.
        market_explains_ratio: A move is attributed to the market when the
            market moved at least this fraction of it, in the same direction.
        action_window_days: Calendar days either side of an ex-date that count
            as matching, allowing for the ex-date falling on a non-session.
        ratio_tolerance: Relative tolerance when matching a plausible action
            ratio. Wide enough to absorb a normal day's price movement on top
            of the action, narrow enough that the whitelist entries stay
            distinguishable.
        market_moves_inversely: Set for series that move against the market,
            notably a volatility index. Without it the market check can never
            explain a VIX spike, because a spike accompanies a market *fall*
            and the same-direction test fails by construction.
    """

    outlier_threshold: float = 0.25
    market_explains_ratio: float = 0.60
    action_window_days: int = 3
    ratio_tolerance: float = 0.03
    market_moves_inversely: bool = False


@dataclass(frozen=True, slots=True)
class ReturnAnomaly:
    """A large daily move and what accounts for it.

    Attributes:
        isin: Security.
        when: Date of the move.
        daily_return: Simple return on that date.
        previous_close: Close on the prior session.
        close: Close on the date.
        classification: How it was accounted for.
        detail: Explanation.
    """

    isin: str
    when: date
    daily_return: float
    previous_close: float
    close: float
    classification: AnomalyClass
    detail: str = ""

    @property
    def blocks(self) -> bool:
        """Whether this anomaly should stop the pipeline."""
        return self.classification in (
            AnomalyClass.UNEXPLAINED,
            AnomalyClass.SUSPECTED_UNADJUSTED_ACTION,
        )


@dataclass(slots=True)
class ValidationReport:
    """Outcome of validating one price series.

    Attributes:
        isin: Security validated.
        observations: Number of returns examined.
        anomalies: Every large move found, in date order.
        config: Thresholds used.
    """

    isin: str
    observations: int
    anomalies: list[ReturnAnomaly] = field(default_factory=list)
    config: ValidationConfig = field(default_factory=ValidationConfig)

    @property
    def blocking(self) -> list[ReturnAnomaly]:
        """Anomalies that must be resolved before the data may be used."""
        return [a for a in self.anomalies if a.blocks]

    @property
    def passed(self) -> bool:
        """Whether every large move was accounted for."""
        return not self.blocking

    def count_by_class(self) -> dict[str, int]:
        """Return a tally of anomalies by classification."""
        tally: dict[str, int] = {}
        for anomaly in self.anomalies:
            tally[anomaly.classification.value] = tally.get(anomaly.classification.value, 0) + 1
        return tally

    def summary(self) -> str:
        """Return a single line describing the outcome."""
        if not self.anomalies:
            return f"{self.isin}: {self.observations:,} returns, no moves beyond threshold."
        parts = ", ".join(f"{k}={v}" for k, v in sorted(self.count_by_class().items()))
        verdict = "PASS" if self.passed else f"BLOCKED ({len(self.blocking)})"
        return f"{self.isin}: {self.observations:,} returns, {parts} -> {verdict}"


#: Price multipliers produced by corporate actions that actually occur.
#:
#: An earlier version matched *any* fraction with a small denominator. That was
#: far too loose: the Farey sequence of denominators <= 12 contains 46
#: fractions in (0, 1), so a few percent of tolerance covers most of the number
#: line and almost every large move gets excused as a suspected split. A
#: detector that fires constantly is one the operator learns to ignore.
#:
#: Real ratios are a short, sparse list. Multipliers above 0.75 are omitted:
#: they imply a move smaller than the outlier threshold and are never examined.
_PLAUSIBLE_MULTIPLIERS: dict[float, str] = {
    2 / 3: "1-for-2 bonus (3-for-2)",
    1 / 2: "1-for-1 bonus, or a 2-for-1 split",
    2 / 5: "3-for-2 bonus (5-for-2)",
    1 / 3: "2-for-1 bonus, or a 3-for-1 split",
    1 / 4: "4-for-1 split",
    1 / 5: "5-for-1 split",
    1 / 10: "10-for-1 split",
    1 / 20: "20-for-1 split",
    1 / 50: "50-for-1 split",
    1 / 100: "100-for-1 split",
    # Reverse actions: the price multiplies rather than divides.
    2.0: "1-for-2 consolidation",
    5.0: "1-for-5 consolidation",
    10.0: "1-for-10 consolidation",
    20.0: "1-for-20 consolidation",
    100.0: "1-for-100 consolidation",
}


def _match_plausible_action(observed: float, tolerance: float) -> tuple[float, str] | None:
    """Match a price multiplier against ratios corporate actions actually produce.

    Args:
        observed: ``close / previous_close``.
        tolerance: Relative tolerance, e.g. ``0.03`` for 3%. Wide enough to
            absorb a normal day's movement on top of the action, narrow enough
            that the whitelist entries stay distinguishable.

    Returns:
        The matched multiplier and its description, or ``None`` when the move
        corresponds to no plausible action.
    """
    best: tuple[float, str] | None = None
    best_error = tolerance
    for candidate, description in _PLAUSIBLE_MULTIPLIERS.items():
        error = abs(observed - candidate) / candidate
        if error <= best_error:
            best_error = error
            best = (candidate, description)
    return best


def validate_price_series(
    series: PriceSeries,
    *,
    isin: str = "",
    actions: list[CorporateAction] | None = None,
    market: PriceSeries | None = None,
    config: ValidationConfig | None = None,
) -> ValidationReport:
    """Check a price series for unexplained large moves.

    Args:
        series: Adjusted closes for one security.
        isin: Identifier for reporting. Defaults to the series name.
        actions: Documented corporate actions for this security.
        market: A broad index, used to attribute market-wide moves. Without
            it, a genuine crash is reported as unexplained - which is safe but
            noisy.
        config: Thresholds.

    Returns:
        A :class:`ValidationReport`. Callers must check ``passed`` rather than
        assuming absence of exceptions means the data is sound.
    """
    cfg = config or ValidationConfig()
    identifier = isin or series.name
    known = actions or []
    market_returns: dict[date, float] = {}
    if market is not None:
        market_returns = {
            b_date: (b / a) - 1.0 for (a_date, a), (b_date, b) in pairwise(list(market))
        }

    report = ValidationReport(isin=identifier, observations=max(len(series) - 1, 0), config=cfg)

    for (prev_date, prev_close), (when, close) in pairwise(list(series)):
        daily = (close / prev_close) - 1.0
        if abs(daily) <= cfg.outlier_threshold:
            continue

        matched = [a for a in known if abs((a.ex_date - when).days) <= cfg.action_window_days]
        if matched:
            names = ", ".join(sorted({a.action_type.value for a in matched}))
            report.anomalies.append(
                ReturnAnomaly(
                    identifier,
                    when,
                    daily,
                    prev_close,
                    close,
                    AnomalyClass.EXPLAINED_BY_ACTION,
                    f"{names} with ex-date within {cfg.action_window_days} days.",
                )
            )
            continue

        market_move = market_returns.get(when)
        if market_move is not None:
            aligned = (
                market_move * daily < 0 if cfg.market_moves_inversely else market_move * daily > 0
            )
            # An inverse series need not match the market's magnitude: a 6%
            # index fall routinely produces a 60% volatility spike. Only the
            # direction is required.
            big_enough = (
                True
                if cfg.market_moves_inversely
                else abs(market_move) >= abs(daily) * cfg.market_explains_ratio
            )
            if aligned and big_enough:
                report.anomalies.append(
                    ReturnAnomaly(
                        identifier,
                        when,
                        daily,
                        prev_close,
                        close,
                        AnomalyClass.EXPLAINED_BY_MARKET,
                        f"market moved {market_move:+.1%} the same day.",
                    )
                )
                continue

        multiplier = close / prev_close
        match = _match_plausible_action(multiplier, cfg.ratio_tolerance)
        if match is not None:
            candidate, description = match
            report.anomalies.append(
                ReturnAnomaly(
                    identifier,
                    when,
                    daily,
                    prev_close,
                    close,
                    AnomalyClass.SUSPECTED_UNADJUSTED_ACTION,
                    f"price ratio {multiplier:.4f} ~ {candidate:.4f}, consistent with an "
                    f"unadjusted {description}. Previous close {prev_date.isoformat()}.",
                )
            )
            continue

        report.anomalies.append(
            ReturnAnomaly(
                identifier,
                when,
                daily,
                prev_close,
                close,
                AnomalyClass.UNEXPLAINED,
                f"{prev_close:,.2f} -> {close:,.2f} with no matching action and no "
                f"comparable market move.",
            )
        )

    return report


def validate_adjustment_factors(factors: list[tuple[date, float]]) -> list[str]:
    """Check that cumulative adjustment factors are self-consistent.

    Args:
        factors: ``(date, cumulative_factor)`` pairs in chronological order.

    Returns:
        Problems found; empty when the factors are sound.
    """
    problems: list[str] = []
    if not factors:
        return ["No adjustment factors supplied."]

    for when, value in factors:
        if value <= 0:
            problems.append(f"{when.isoformat()}: factor {value} is not positive.")

    for (a_date, a), (b_date, b) in pairwise(factors):
        if b_date <= a_date:
            problems.append(
                f"{b_date.isoformat()} does not follow {a_date.isoformat()}: "
                f"factors must be in chronological order."
            )
        # Cumulative factors accumulate as actions occur; they never unwind.
        if b < a * (1 - 1e-9):
            problems.append(
                f"{b_date.isoformat()}: cumulative factor fell from {a} to {b}. "
                f"Cumulative factors are non-decreasing; a fall means an action "
                f"was applied twice or reversed."
            )
    return problems
