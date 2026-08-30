"""Current allocation against the declared target, and what closing it costs.

Phase 5 component 2. The target is a policy the owner declares in
``configs/target_allocation.yaml``; this module measures against it and prices
the correction. It does not choose the target, and there is nothing here that
could be extended to.

Why a band rule at all
----------------------
Gold reached 25% of this balance sheet **by appreciation rather than by
decision**. Nobody chose it; it simply grew while everything else did not, and
the position that resulted was never compared against anything. A band rule
answers that without needing a view on gold, on equities, or on what happens
next: it says only *"this is further from the declared policy than the policy
permits"*, and the arithmetic is the same in every market.

Two bands, and why both
-----------------------
A holding is drifted when it breaches **either** an absolute band (percentage
points) or a relative one (a share of the target weight). Each fails alone:

* Five percentage points is meaningless on a 3% target. The holding would have
  to nearly triple before anything registered.
* Twenty-five percent relative is far too loose on a 45% target. It would permit
  an eleven-point swing in the largest position in the book.

Taking whichever is tighter puts small positions under the relative band and
large ones under the absolute band, which is the correct way round.

The part most rebalancing tools leave out
------------------------------------------
**A rebalance that costs more than it is worth is not a rebalance.** Every trade
pays charges, and a sale pays capital gains tax on top — which on a short-term
lot is twenty per cent of the gain and dwarfs every charge in the schedule.
:class:`DriftReport` therefore reports the friction on each correcting trade
beside the trade itself, and flags the ones whose cost exceeds the declared
budget. It still does not tell anyone what to do.

What is deliberately absent
---------------------------
No field here names an action, and none should be added. The module reports a
gap, the rupees that would close it, and what closing it costs. Whether to close
it is a decision, and the decision belongs to the person whose money it is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from indian_equity_research.backtest.costs import Side, charges_for

__all__ = [
    "Band",
    "BucketDrift",
    "DriftError",
    "DriftReport",
    "TargetPolicy",
    "load_policy",
    "measure_drift",
]

# A total that misses 100 by more than this is a mistake rather than rounding.
# Four buckets each given to one decimal place cannot drift further than 0.4.
TOTAL_TOLERANCE_PP = 0.5


class DriftError(ValueError):
    """The drift could not be measured against a policy that means anything."""


@dataclass(frozen=True, slots=True)
class Band:
    """How far a holding may stray before it counts as drifted.

    Attributes:
        absolute_pp: Percentage points either side of target.
        relative_pct: Percent of the target weight, either side.
    """

    absolute_pp: float
    relative_pct: float

    def width_for(self, target_pct: float) -> float:
        """The binding half-width at this target, in percentage points.

        The tighter of the two. At a 3% target the relative band binds at
        0.75pp; at a 45% target the absolute band binds at 5pp. Neither alone
        governs the whole book sensibly.
        """
        return min(self.absolute_pp, target_pct * self.relative_pct / 100.0)


@dataclass(frozen=True, slots=True)
class TargetPolicy:
    """The declared allocation, as committed.

    Attributes:
        version: Policy version, so a report can name what it measured against.
        declared_on: When these weights were decided.
        targets: ``{bucket: target percent}``.
        band: The band rule.
        min_trade_rupees: Trades below this are reported as too small to make.
        max_cost_fraction: Friction above this share of the amount moved is
            flagged as costing more than the correction is worth.
    """

    version: int
    declared_on: date
    targets: dict[str, float]
    band: Band
    min_trade_rupees: float
    max_cost_fraction: float

    def describe(self) -> str:
        """One line naming the policy a report was measured against."""
        return (
            f"policy v{self.version} declared {self.declared_on}, "
            f"{len(self.targets)} buckets, bands +/-{self.band.absolute_pp:g}pp "
            f"or {self.band.relative_pct:g}% relative, whichever is tighter"
        )


@dataclass(frozen=True, slots=True)
class BucketDrift:
    """One bucket: where it is, where policy says it should be, and the gap.

    Attributes:
        name: Bucket name, matching the policy exactly.
        value: Current rupee value.
        total: Portfolio total, for converting to a weight.
        target_pct: Declared target.
        band_pp: The binding half-width at this target.
        trade_charges: Modelled charges on the correcting trade, or ``None``
            when no trade is needed.
    """

    name: str
    value: float
    total: float
    target_pct: float
    band_pp: float
    trade_charges: float | None

    @property
    def current_pct(self) -> float:
        """Current weight, in percent."""
        return 100.0 * self.value / self.total if self.total > 0 else 0.0

    @property
    def gap_pp(self) -> float:
        """Current minus target, in percentage points. Positive is overweight."""
        return self.current_pct - self.target_pct

    @property
    def is_drifted(self) -> bool:
        """Whether the gap breaches the binding band."""
        return abs(self.gap_pp) > self.band_pp

    @property
    def trade_rupees(self) -> float:
        """Rupees that would move this bucket to target. Negative is a sale.

        Computed against the *current* total. Correcting one bucket changes
        every other bucket's weight, so a set of these trades executed together
        will not land exactly on target — which is why they are reported as the
        gap to target rather than as a plan.
        """
        return self.total * (self.target_pct - self.current_pct) / 100.0

    @property
    def cost_fraction(self) -> float:
        """Modelled friction as a share of the amount moved."""
        if self.trade_charges is None or self.trade_rupees == 0:
            return 0.0
        return self.trade_charges / abs(self.trade_rupees)

    def describe(self) -> str:
        """One line for a report table."""
        flag = "DRIFTED" if self.is_drifted else "within band"
        return (
            f"{self.name}: {self.current_pct:.1f}% against {self.target_pct:.1f}% "
            f"({self.gap_pp:+.1f}pp, band +/-{self.band_pp:.2f}pp) - {flag}"
        )


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Every bucket measured against the policy on one date."""

    policy: TargetPolicy
    on: date
    buckets: tuple[BucketDrift, ...]

    @property
    def total(self) -> float:
        """Portfolio total across every bucket."""
        return sum(bucket.value for bucket in self.buckets)

    @property
    def drifted(self) -> tuple[BucketDrift, ...]:
        """Buckets outside their band, worst first."""
        return tuple(
            sorted(
                (bucket for bucket in self.buckets if bucket.is_drifted),
                key=lambda bucket: abs(bucket.gap_pp),
                reverse=True,
            )
        )

    @property
    def worth_making(self) -> tuple[BucketDrift, ...]:
        """Drifted buckets whose correcting trade clears both economic tests.

        Large enough to be worth an order, and cheap enough that the friction
        does not exceed the declared budget. A drifted bucket that fails either
        is still reported as drifted — it is simply one where the arithmetic
        says a trade is not the way to fix it.
        """
        return tuple(
            bucket
            for bucket in self.drifted
            if abs(bucket.trade_rupees) >= self.policy.min_trade_rupees
            and bucket.cost_fraction <= self.policy.max_cost_fraction
        )

    @property
    def total_turnover(self) -> float:
        """Rupees that would change hands correcting every drifted bucket."""
        return sum(abs(bucket.trade_rupees) for bucket in self.drifted)

    def describe(self) -> str:
        """One line summarising the state against the policy."""
        if not self.drifted:
            return f"{self.on}: every bucket within band against {self.policy.describe()}"
        return (
            f"{self.on}: {len(self.drifted)} of {len(self.buckets)} buckets drifted, "
            f"{self.total_turnover:,.0f} to correct"
        )


def load_policy(path: Path) -> TargetPolicy:
    """Read and validate the declared target allocation.

    Args:
        path: Path to ``target_allocation.yaml``.

    Returns:
        The policy.

    Raises:
        DriftError: if the file is missing, if any target is unset, if the
            targets do not total 100, if a weight is negative, or if
            ``declared_on`` is absent. Every one of these would otherwise
            produce a drift report against a policy nobody chose — which looks
            exactly like a drift report against one somebody did.
    """
    if not path.exists():
        raise DriftError(
            f"no target allocation at {path}. Phase 5 measures against a declared "
            f"policy; without one there is no drift to report, only a description "
            f"of wherever the portfolio already is."
        )

    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    buckets = raw.get("buckets") or []
    if not buckets:
        raise DriftError(f"{path} declares no buckets.")

    unset = [b.get("name", "?") for b in buckets if b.get("target_pct") is None]
    if unset:
        raise DriftError(
            f"{path} is still a template: {', '.join(unset)} have no target. "
            f"The monitor refuses a template so it cannot become a default "
            f"nobody chose. Set every target_pct, and make them total 100."
        )

    targets: dict[str, float] = {}
    for entry in buckets:
        name = str(entry["name"])
        weight = float(entry["target_pct"])
        if weight < 0:
            raise DriftError(f"{name} has a negative target of {weight}.")
        if name in targets:
            raise DriftError(f"{path} declares {name} twice. One of the two would silently win.")
        targets[name] = weight

    total = sum(targets.values())
    if abs(total - 100.0) > TOTAL_TOLERANCE_PP:
        raise DriftError(
            f"targets in {path} total {total:.1f}%, not 100%. Every weight in a "
            f"drift report is a share of the whole, so a total that is not 100 "
            f"makes each one wrong by a factor nobody would see."
        )

    declared = raw.get("declared_on")
    if not declared:
        raise DriftError(
            f"{path} has no declared_on date. A policy without a date cannot be "
            f"distinguished from one written after seeing the drift."
        )

    band_cfg = raw.get("bands") or {}
    econ = raw.get("economics") or {}
    return TargetPolicy(
        version=int(raw.get("version", 0)),
        declared_on=declared if isinstance(declared, date) else date.fromisoformat(declared),
        targets=targets,
        band=Band(
            absolute_pp=float(band_cfg.get("absolute_pp", 5.0)),
            relative_pct=float(band_cfg.get("relative_pct", 25.0)),
        ),
        min_trade_rupees=float(econ.get("min_trade_rupees", 0.0)),
        max_cost_fraction=float(econ.get("max_cost_fraction", 1.0)),
    )


def measure_drift(
    policy: TargetPolicy,
    holdings: dict[str, float],
    on: date,
) -> DriftReport:
    """Measure current holdings against the declared policy.

    Args:
        policy: The declared target.
        holdings: ``{bucket: current rupee value}``. Supplied by the caller and
            never read from the portfolio file.
        on: Date of the measurement, used to select the charge schedule.

    Returns:
        The report.

    Raises:
        DriftError: if a holding names a bucket the policy does not declare, if
            a declared bucket is missing from the holdings, or if the total is
            not positive. A silent name mismatch would put real money into a
            bucket with a 0% target while the real bucket read as empty, and
            both halves of that error look plausible in the output.
    """
    unknown = set(holdings) - set(policy.targets)
    if unknown:
        raise DriftError(
            f"holdings name buckets the policy does not declare: {sorted(unknown)}. "
            f"Declared: {sorted(policy.targets)}. A typo here would create a "
            f"bucket at 0% target and leave the real one reading empty."
        )
    missing = set(policy.targets) - set(holdings)
    if missing:
        raise DriftError(
            f"the policy declares buckets with no holding supplied: {sorted(missing)}. "
            f"Pass 0 explicitly if a bucket is genuinely empty, so that an "
            f"omission cannot be mistaken for a zero."
        )

    total = sum(holdings.values())
    if total <= 0:
        raise DriftError(f"holdings total {total}, so no weight can be computed.")

    buckets: list[BucketDrift] = []
    for name, target in policy.targets.items():
        value = holdings[name]
        current_pct = 100.0 * value / total
        trade = total * (target - current_pct) / 100.0
        charges = None
        if abs(trade) > 0:
            side = Side.BUY if trade > 0 else Side.SELL
            charges = charges_for(abs(trade), side, on).total
        buckets.append(
            BucketDrift(
                name=name,
                value=value,
                total=total,
                target_pct=target,
                band_pp=policy.band.width_for(target),
                trade_charges=charges,
            )
        )

    return DriftReport(policy=policy, on=on, buckets=tuple(buckets))
