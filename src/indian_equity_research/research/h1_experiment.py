"""H1 — is there cross-sectional momentum structure in the Nifty 100 at all?

H2 asked whether one portfolio could capture the effect and answered no. H1
asks the prior question: **is the effect there.** They are different claims and
can disagree in both directions — a real effect can be untradeable at ₹3L, and
a portfolio can win for reasons unrelated to the signal.

As registered on 2026-08-04: deciles formed on 12-1 momentum within the
point-in-time Nifty 100 exhibit a monotonic relationship with forward one-month
excess returns, decile 10 outperforming decile 1.

Gross, deliberately
-------------------
H1 is a statement about cross-sectional structure and nothing else. No
brokerage, no STT, no DP charge, no tax. That is not an oversight to be
corrected later — a costed H1 would answer H2's question, and H2 has already
been answered.

What "excess" means here, and why it barely matters
----------------------------------------------------
Forward returns are reported net of the Nifty 100 TRI return over the same
interval. For the **decile means** this matters and is what makes them
comparable across periods.

For the **rank IC and the decile 10 minus decile 1 spread it changes nothing**:
subtracting one number from every observation in a cross-section leaves every
rank untouched, and leaves any difference of two means untouched. Both are
computed on excess returns anyway, so the reported figures match the registered
definition exactly rather than relying on that equivalence.

Securities that stop trading mid-interval
------------------------------------------
A name can be suspended, delisted or acquired between one rebalance and the
next. Its forward return is measured to the **last close available inside the
interval**, and the count of such cases is reported.

Dropping them instead would be survivorship bias in its purest form — it
removes exactly the securities that failed, which are disproportionately the
low-momentum ones, and would flatter decile 1 and therefore the decile 10 minus
decile 1 spread. The chosen treatment errs the other way only if a security
kept falling after its last print, which is the safe direction for H1's claim.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Final

from indian_equity_research.backtest.engine import Bar, PriceView
from indian_equity_research.backtest.gates import MeanTest, newey_west_mean_test
from indian_equity_research.market.membership import MembershipHistory, members_on
from indian_equity_research.research.momentum import (
    FORMATION_SESSIONS,
    SKIP_SESSIONS,
    rank_by_momentum,
)
from indian_equity_research.research.rank_stats import RankStatsError, deciles, spearman

__all__ = [
    "DECILES",
    "HOLDOUT_START",
    "SUB_PERIODS",
    "H1Config",
    "H1Result",
    "RebalanceObservation",
    "run_h1",
]

#: As registered. Deciles, not quintiles.
DECILES: Final = 10

#: Non-overlapping sub-periods the D10-D1 spread must be positive in at least
#: three of. Fixed at registration.
SUB_PERIODS: Final = 5

#: The declared holdout, shared with H2.
HOLDOUT_START: Final = date(2022, 1, 1)

_WARMUP_SESSIONS: Final = FORMATION_SESSIONS + SKIP_SESSIONS


@dataclass(frozen=True, slots=True)
class H1Config:
    """The registered specification, printable alongside the result."""

    start: date = date(2015, 1, 1)
    end: date = date(2021, 12, 31)
    buckets: int = DECILES
    sub_periods: int = SUB_PERIODS

    def describe(self) -> str:
        """One line identifying the configuration for the trial register."""
        return (
            f"H1: 12-1 momentum, {self.buckets} deciles, monthly, {self.start} to {self.end}, gross"
        )


@dataclass(frozen=True, slots=True)
class RebalanceObservation:
    """One rebalance date: its IC, its decile means, and what was excluded."""

    when: date
    information_coefficient: float
    decile_excess: tuple[float, ...]
    ranked: int
    incomplete_forward: int

    @property
    def top_minus_bottom(self) -> float:
        """Decile 10 mean excess return less decile 1's."""
        return self.decile_excess[-1] - self.decile_excess[0]


@dataclass(frozen=True, slots=True)
class H1Result:
    """Everything H1's rejection criteria need."""

    config: H1Config
    observations: tuple[RebalanceObservation, ...]
    ic_test: MeanTest
    decile_mean_excess: tuple[float, ...]
    monotonicity: float
    sub_period_spreads: tuple[tuple[date, date, float], ...]
    incomplete_forward: int

    @property
    def mean_ic(self) -> float:
        """The primary metric."""
        return self.ic_test.mean

    @property
    def top_minus_bottom(self) -> float:
        """Decile 10 less decile 1, averaged across rebalances."""
        return self.decile_mean_excess[-1] - self.decile_mean_excess[0]

    @property
    def positive_sub_periods(self) -> int:
        """Sub-periods in which the spread was positive."""
        return sum(1 for _, _, spread in self.sub_period_spreads if spread > 0)


def _forward_excess(
    bars: Mapping[str, Mapping[date, Bar]],
    symbol: str,
    start: date,
    end: date,
    benchmark_return: float,
) -> tuple[float, bool] | None:
    """Return over ``start``..``end`` less the benchmark, and whether it is partial.

    Returns ``None`` when the security had no price at ``start`` at all, which
    means it was never buyable and so belongs in no decile.
    """
    series = bars.get(symbol)
    if not series:
        return None
    opening = series.get(start)
    if opening is None or opening.close <= 0:
        return None
    closing = series.get(end)
    partial = closing is None
    if closing is None:
        # Last print inside the interval. See the module docstring: dropping
        # these removes exactly the securities that failed.
        available = [d for d in series if start < d <= end]
        if not available:
            return None
        closing = series[max(available)]
    return (closing.close / opening.close - 1.0) - benchmark_return, partial


def run_h1(
    bars: Mapping[str, Mapping[date, Bar]],
    sessions: Sequence[date],
    history: MembershipHistory,
    tri: Mapping[date, float],
    rebalances: Sequence[date],
    *,
    config: H1Config | None = None,
) -> H1Result:
    """Measure cross-sectional momentum structure over the development window.

    Args:
        bars: Back-adjusted OHLC keyed by the security's canonical symbol.
        sessions: Every session available, ascending.
        history: Point-in-time index membership.
        tri: Nifty 100 Total Return Index levels, for the excess return.
        rebalances: Decision dates, ascending. The last one has no forward
            interval and is dropped.
        config: The registered specification.

    Returns:
        The result, with every figure a rejection criterion needs.

    Raises:
        ValueError: if fewer than three usable rebalance dates remain, which is
            too few for any of the statistics to mean anything.
    """
    cfg = config or H1Config()
    ordered = [d for d in sorted(sessions) if cfg.start <= d <= cfg.end]
    usable = [d for d in sorted(rebalances) if cfg.start <= d <= cfg.end]

    observations: list[RebalanceObservation] = []
    incomplete_total = 0
    last_tri: float | None = None
    tri_on: dict[date, float] = {}
    for when in ordered:
        level = tri.get(when, last_tri)
        if level is not None:
            tri_on[when] = level
            last_tri = level

    for decision, following in pairwise(usable):
        start_level = tri_on.get(decision)
        end_level = tri_on.get(following)
        if start_level is None or end_level is None or start_level <= 0:
            continue
        benchmark = end_level / start_level - 1.0

        view = PriceView(bars, ordered, decision)
        ranking = rank_by_momentum(view, members_on(history, decision))

        scored: list[tuple[str, float]] = []
        forward: dict[str, float] = {}
        partials = 0
        for score in ranking.scores:
            outcome = _forward_excess(bars, score.symbol, decision, following, benchmark)
            if outcome is None:
                continue
            value, partial = outcome
            partials += int(partial)
            scored.append((score.symbol, score.score))
            forward[score.symbol] = value

        if len(scored) < cfg.buckets:
            continue
        incomplete_total += partials

        try:
            coefficient = spearman(
                [s for _, s in scored], [forward[symbol] for symbol, _ in scored]
            )
        except RankStatsError:
            continue

        buckets = deciles(scored, buckets=cfg.buckets)
        means = tuple(
            sum(forward[symbol] for symbol in bucket.symbols) / bucket.size for bucket in buckets
        )
        observations.append(
            RebalanceObservation(
                when=decision,
                information_coefficient=coefficient,
                decile_excess=means,
                ranked=len(scored),
                incomplete_forward=partials,
            )
        )

    if len(observations) < 3:
        raise ValueError(
            f"{len(observations)} usable rebalance dates; H1 needs at least 3 for any "
            f"of its statistics to mean anything. Widen the window."
        )

    decile_means = tuple(
        sum(o.decile_excess[i] for o in observations) / len(observations)
        for i in range(cfg.buckets)
    )
    # Monotonicity is the rank correlation between decile *index* and decile
    # mean return: does the ordering hold across all ten, not just the ends. A
    # large 10-minus-1 spread with a scrambled middle is a two-point result
    # dressed as a ten-point one.
    monotonicity = spearman(list(range(1, cfg.buckets + 1)), list(decile_means))

    return H1Result(
        config=cfg,
        observations=tuple(observations),
        ic_test=newey_west_mean_test([o.information_coefficient for o in observations]),
        decile_mean_excess=decile_means,
        monotonicity=monotonicity,
        sub_period_spreads=_sub_period_spreads(observations, cfg.sub_periods),
        incomplete_forward=incomplete_total,
    )


def _sub_period_spreads(
    observations: Sequence[RebalanceObservation], count: int
) -> tuple[tuple[date, date, float], ...]:
    """Split the observations into ``count`` equal, non-overlapping blocks.

    Equal by **number of rebalances**, not by calendar length, so each block
    carries the same statistical weight. Splitting by calendar would give the
    2020 block fewer observations than the 2017 block if a year had fewer
    rebalances, and the criterion counts blocks rather than months.
    """
    total = len(observations)
    if total < count:
        return ()
    base, remainder = divmod(total, count)
    out: list[tuple[date, date, float]] = []
    cursor = 0
    for block in range(count):
        size = base + (1 if block < remainder else 0)
        chunk = observations[cursor : cursor + size]
        cursor += size
        if not chunk:
            continue
        spread = sum(o.top_minus_bottom for o in chunk) / len(chunk)
        out.append((chunk[0].when, chunk[-1].when, spread))
    return tuple(out)
