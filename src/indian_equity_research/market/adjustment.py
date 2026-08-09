"""Back-adjust prices for corporate actions, with provenance and sensitivity.

Two things make this module different from a naive adjuster.

**Provenance.** Every applied factor records where it came from. A documented
action from an exchange file is not the same claim as a ratio the validator
inferred from a suspicious price move, and downstream code must be able to
tell them apart - and to re-run with inferred adjustments excluded. If a
result flips when inferred adjustments are removed, that is a finding.

**Sensitivity rather than assumption.** What a holder recovered when a
security delisted is not in the price data. Rather than pick the answer, this
computes outcomes under every policy and reports the spread. The pre-committed
rule is: **report both, act on the conservative one.** A strategy that only
works under the optimistic assumption does not work.

The arithmetic
--------------
A back-adjusted price is the raw price multiplied by every action multiplier
with an ex-date *after* it::

    adjusted(d) = raw(d) * product{ m_a : ex_date(a) > d }

So a 2-for-1 split (m = 0.5) halves every price before the ex-date, making the
series continuous. The cumulative factor rises toward 1.0 at the latest date,
which is what :func:`validate_adjustment_factors` checks for.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from indian_equity_research.market.corporate_actions import (
    AnomalyClass,
    CorporateAction,
    ValidationReport,
)
from indian_equity_research.market.delisting import (
    ClassificationConfig,
    DelistingOutcome,
    DelistingRecord,
    TerminalReturnPolicy,
    classify_delisting,
)
from indian_equity_research.research.series import PriceSeries

__all__ = [
    "Adjustment",
    "AdjustmentSource",
    "TerminalSensitivity",
    "adjustments_from_actions",
    "adjustments_from_report",
    "apply_adjustments",
    "cumulative_factors",
    "terminal_return",
    "terminal_sensitivity",
]


class AdjustmentSource(StrEnum):
    """Where an adjustment factor came from."""

    #: An exchange-published corporate action. Trustworthy.
    DOCUMENTED = "DOCUMENTED"
    #: A ratio inferred from an otherwise unexplained price move. Usually
    #: right, and wrong exactly where a genuine crash looked like a split.
    INFERRED = "INFERRED"


@dataclass(frozen=True, slots=True)
class Adjustment:
    """One price multiplier to apply from an ex-date.

    Attributes:
        ex_date: First session on the new basis.
        multiplier: Expected ``close / previous_close`` across the ex-date.
            A 2-for-1 split is ``0.5``.
        source: Whether this is documented or inferred.
        detail: Human-readable justification.
    """

    ex_date: date
    multiplier: float
    source: AdjustmentSource
    detail: str = ""

    def __post_init__(self) -> None:
        """Reject a multiplier that cannot describe a corporate action."""
        if self.multiplier <= 0:
            message = f"{self.ex_date}: multiplier {self.multiplier} must be positive."
            raise ValueError(message)


def adjustments_from_actions(actions: Iterable[CorporateAction]) -> list[Adjustment]:
    """Convert documented corporate actions into adjustments.

    Actions without a ratio - cash dividends, for instance - produce no price
    adjustment here. Dividend adjustment is a separate decision with its own
    conventions and is deliberately not folded in.

    Args:
        actions: Documented actions.

    Returns:
        Adjustments in ex-date order.
    """
    out = [
        Adjustment(
            ex_date=action.ex_date,
            multiplier=multiplier,
            source=AdjustmentSource.DOCUMENTED,
            detail=f"{action.action_type.value} {action.ratio_from}:{action.ratio_to}",
        )
        for action in actions
        if (multiplier := action.price_multiplier) is not None
    ]
    return sorted(out, key=lambda a: a.ex_date)


def adjustments_from_report(report: ValidationReport) -> list[Adjustment]:
    """Convert suspected unadjusted actions into inferred adjustments.

    Only anomalies the validator matched to a plausible action ratio are
    used. ``UNEXPLAINED`` moves are never converted: assuming an unexplained
    50% fall was a split would erase a genuine collapse.

    Args:
        report: A validation report for one security.

    Returns:
        Adjustments in ex-date order, all marked ``INFERRED``.
    """
    out = [
        Adjustment(
            ex_date=anomaly.when,
            multiplier=anomaly.inferred_multiplier,
            source=AdjustmentSource.INFERRED,
            detail=anomaly.detail,
        )
        for anomaly in report.anomalies
        if anomaly.classification is AnomalyClass.SUSPECTED_UNADJUSTED_ACTION
        and anomaly.inferred_multiplier is not None
    ]
    return sorted(out, key=lambda a: a.ex_date)


def cumulative_factors(
    dates: Iterable[date], adjustments: Iterable[Adjustment]
) -> list[tuple[date, float]]:
    """Compute the cumulative back-adjustment factor for each date.

    Args:
        dates: Session dates, ascending.
        adjustments: Adjustments to apply.

    Returns:
        ``(date, factor)`` pairs. The factor is the product of every
        multiplier with a later ex-date, so it rises toward 1.0 at the end of
        the series.
    """
    ordered = sorted(adjustments, key=lambda a: a.ex_date)
    out: list[tuple[date, float]] = []
    for when in dates:
        factor = 1.0
        for adjustment in ordered:
            if adjustment.ex_date > when:
                factor *= adjustment.multiplier
        out.append((when, factor))
    return out


def apply_adjustments(
    series: PriceSeries,
    adjustments: Iterable[Adjustment],
    *,
    include_inferred: bool = True,
    name_suffix: str = " (adjusted)",
) -> PriceSeries:
    """Return a back-adjusted copy of a price series.

    Args:
        series: Raw closes.
        adjustments: Adjustments to apply.
        include_inferred: When ``False``, only documented adjustments are
            applied. Re-running with this off is how a result is tested for
            dependence on inferred data.
        name_suffix: Appended to the series name.

    Returns:
        A new series with prices before each ex-date rescaled.
    """
    selected = [
        a for a in adjustments if include_inferred or a.source is AdjustmentSource.DOCUMENTED
    ]
    factors = dict(cumulative_factors(series.dates, selected))
    return PriceSeries(
        name=series.name + name_suffix,
        dates=series.dates,
        closes=tuple(close * factors[when] for when, close in series),
    )


def terminal_return(
    record: DelistingRecord,
    policy: TerminalReturnPolicy,
    classification: ClassificationConfig | None = None,
) -> float | None:
    """Return the assumed terminal value per share on delisting.

    Args:
        record: The delisting record, whose last close is the only price
            evidence available.
        policy: Which assumption to apply.
        classification: Thresholds used when ``policy`` is ``CLASSIFIED``.

    Returns:
        The last observed close under ``LAST_PRICE``, ``0.0`` under
        ``TOTAL_LOSS``, or ``None`` when the policy refuses to assume - in
        which case the caller must exclude the security or supply a documented
        recovery value.
    """
    if policy is TerminalReturnPolicy.LAST_PRICE:
        return record.last_close
    if policy is TerminalReturnPolicy.TOTAL_LOSS:
        return 0.0
    if policy is TerminalReturnPolicy.CLASSIFIED:
        outcome = classify_delisting(record, classification)
        if outcome is DelistingOutcome.LIKELY_ACQUISITION:
            return record.last_close
        if outcome is DelistingOutcome.LIKELY_COLLAPSE:
            return 0.0
        return None
    return None


@dataclass(frozen=True, slots=True)
class TerminalSensitivity:
    """How much the delisting assumption could move a result.

    Two bands are reported and both matter:

    * the **outer bound**, from assuming every delisting recovered its last
      close down to assuming none did. This is the honest full range and it is
      never discarded;
    * the **classified band**, which resolves the confidently-readable tails
      and leaves only the uncertain middle floating.

    If a conclusion holds across the outer bound, the delisting assumption is
    not load-bearing and can be ignored. If it holds only inside the
    classified band, it depends on the classification being right - which is
    an inference from price data, not a fact.

    Attributes:
        securities: Delistings considered.
        likely_acquisition: Read as acquisitions.
        likely_collapse: Read as collapses.
        uncertain: Not separable from prices.
        value_at_last_price: Total last-close value across all delistings.
        value_uncertain: Last-close value of the uncertain middle alone.
        collapse_threshold: Threshold used for the collapse test.
    """

    securities: int
    likely_acquisition: int
    likely_collapse: int
    uncertain: int
    value_at_last_price: float
    value_uncertain: float
    collapse_threshold: float

    @property
    def value_at_total_loss(self) -> float:
        """Terminal value assuming nothing was recovered. Zero by definition."""
        return 0.0

    @property
    def outer_band(self) -> float:
        """Width of the unavoidable uncertainty, before classification."""
        return self.value_at_last_price

    @property
    def classified_band(self) -> float:
        """Width remaining once the confident tails are resolved."""
        return self.value_uncertain

    @property
    def band_narrowing(self) -> float:
        """Fraction of the uncertainty the classification removes."""
        if self.value_at_last_price <= 0:
            return 0.0
        return 1.0 - (self.value_uncertain / self.value_at_last_price)

    @property
    def uncertain_fraction(self) -> float:
        """Share of delistings that remain unclassifiable."""
        return self.uncertain / self.securities if self.securities else 0.0

    def summary(self) -> str:
        """Return a two-line description of the sensitivity."""
        return (
            f"{self.securities:,} delistings: {self.likely_acquisition:,} likely "
            f"acquisitions, {self.likely_collapse:,} likely collapses, "
            f"{self.uncertain:,} uncertain ({self.uncertain_fraction:.0%}).\n"
            f"  Uncertainty band {self.outer_band:,.0f} -> {self.classified_band:,.0f} "
            f"after classification ({self.band_narrowing:.0%} narrower)."
        )


def terminal_sensitivity(
    records: Iterable[DelistingRecord],
    *,
    classification: ClassificationConfig | None = None,
) -> TerminalSensitivity:
    """Measure how much the delisting assumption could matter.

    Args:
        records: Delisting records.
        classification: Thresholds for the three-way read.

    Returns:
        The measured sensitivity, with both the outer bound and the narrowed
        band.
    """
    cfg = classification or ClassificationConfig()
    entries = list(records)
    counts = dict.fromkeys(DelistingOutcome, 0)
    uncertain_value = 0.0
    for record in entries:
        outcome = classify_delisting(record, cfg)
        counts[outcome] += 1
        if outcome is DelistingOutcome.UNCERTAIN:
            uncertain_value += record.last_close
    return TerminalSensitivity(
        securities=len(entries),
        likely_acquisition=counts[DelistingOutcome.LIKELY_ACQUISITION],
        likely_collapse=counts[DelistingOutcome.LIKELY_COLLAPSE],
        uncertain=counts[DelistingOutcome.UNCERTAIN],
        value_at_last_price=sum(r.last_close for r in entries),
        value_uncertain=uncertain_value,
        collapse_threshold=cfg.collapse_peak_threshold,
    )
