"""Rank statistics for cross-sectional studies.

H1's primary metric is a **Spearman rank information coefficient**: the rank
correlation between a signal and the return that followed it, averaged across
rebalance dates. Two things about that choice are worth stating, because both
are the reason H1 and H2 can disagree.

**Rank, not level.** A Pearson correlation on raw returns is dominated by the
largest movers. One security that tripled decides the number, and the question
"do high-momentum names tend to outperform" gets answered by "one of them
did". Ranking removes the magnitudes and keeps the ordering, which is the claim
actually being made.

**Invariant to what does not matter.** Rank correlation is unchanged by any
increasing transform applied to every observation, so subtracting the index
return from every forward return leaves the IC exactly as it was. "Excess"
returns and raw returns give the same IC, and the same decile 10 minus decile 1
spread. This is worth knowing before someone spends an afternoon deciding what
to subtract.

Ties are handled properly
-------------------------
Spearman on tied values requires **average ranks** -- three securities sharing
the 4th, 5th and 6th positions each rank 5.0. Assigning them 4, 5, 6 in
whatever order the input happened to arrive makes the statistic depend on dict
ordering, which is reproducible and meaningless. Momentum scores rarely tie;
forward returns on a halted security do.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "RankStatsError",
    "decile_of",
    "deciles",
    "ranks",
    "spearman",
]


class RankStatsError(ValueError):
    """Raised when a rank statistic cannot be computed honestly."""


def ranks(values: Sequence[float]) -> list[float]:
    """Rank ``values`` ascending, averaging ties.

    Args:
        values: Observations.

    Returns:
        Ranks from 1.0, with tied values sharing their average rank.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2.0 + 1.0
        for index in range(position, end + 1):
            out[order[index]] = average
        position = end + 1
    return out


def spearman(first: Sequence[float], second: Sequence[float]) -> float:
    """Spearman rank correlation between two equal-length series.

    Computed as the Pearson correlation of the average ranks, which is the
    definition that stays correct when ties are present. The shortcut formula
    ``1 - 6*sum(d^2)/(n(n^2-1))`` is only valid without ties and is not used.

    Args:
        first: One series.
        second: The other, same length and aligned element-wise.

    Returns:
        The correlation, in ``[-1, 1]``.

    Raises:
        RankStatsError: if the lengths differ, fewer than three observations
            are given, or either series is constant. A constant has no
            correlation with anything, and returning 0.0 would report "no
            relationship" where the truth is "no measurement".
    """
    if len(first) != len(second):
        raise RankStatsError(f"lengths differ: {len(first)} and {len(second)}")
    count = len(first)
    if count < 3:
        raise RankStatsError(
            f"a rank correlation needs at least 3 observations, got {count}. "
            f"With two, it is always exactly +1 or -1."
        )

    left, right = ranks(first), ranks(second)
    mean_left = sum(left) / count
    mean_right = sum(right) / count
    covariance = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right, strict=True))
    variance_left = sum((a - mean_left) ** 2 for a in left)
    variance_right = sum((b - mean_right) ** 2 for b in right)
    if variance_left <= 0 or variance_right <= 0:
        raise RankStatsError(
            "one of the series is constant, so no rank correlation exists. "
            "Reporting 0.0 would state 'no relationship' where the truth is "
            "'no measurement'."
        )
    return covariance / math.sqrt(variance_left * variance_right)


@dataclass(frozen=True, slots=True)
class Decile:
    """One decile of a cross-section, and what fell into it."""

    index: int
    symbols: tuple[str, ...]

    @property
    def size(self) -> int:
        """How many securities."""
        return len(self.symbols)


def deciles(scored: Sequence[tuple[str, float]], *, buckets: int = 10) -> list[Decile]:
    """Split a scored cross-section into ``buckets``, lowest score first.

    Decile 1 holds the lowest scores and decile ``buckets`` the highest, which
    is the convention H1 is written in ("decile 10 outperforming decile 1").

    Sizes are as equal as the count allows, with the remainder spread across
    the **lowest** buckets rather than concentrated anywhere. A hundred names
    give ten of ten; a hundred and one give eleven in decile 1 and ten
    everywhere else. That happens in this archive: NSE ran the Nifty 100 at 101
    constituents while Tata Motors' differential-voting share was a member in
    its own right.

    Ties are broken by symbol so the split is reproducible across runs.

    Args:
        scored: ``(symbol, score)`` pairs.
        buckets: How many groups.

    Returns:
        Buckets in ascending order of score.

    Raises:
        RankStatsError: if there are fewer securities than buckets, which would
            leave empty deciles whose "mean return" is undefined and would be
            silently reported as zero.
    """
    if buckets < 2:
        raise RankStatsError(f"buckets must be at least 2, got {buckets}")
    if len(scored) < buckets:
        raise RankStatsError(
            f"{len(scored)} securities cannot fill {buckets} deciles. Empty deciles "
            f"have no mean return, and reporting one as zero would place a "
            f"fabricated observation in the middle of the monotonicity test."
        )

    ordered = sorted(scored, key=lambda pair: (pair[1], pair[0]))
    base, remainder = divmod(len(ordered), buckets)
    out: list[Decile] = []
    cursor = 0
    for bucket in range(buckets):
        size = base + (1 if bucket < remainder else 0)
        out.append(
            Decile(index=bucket + 1, symbols=tuple(s for s, _ in ordered[cursor : cursor + size]))
        )
        cursor += size
    return out


def decile_of(symbol: str, buckets: Sequence[Decile]) -> int | None:
    """Which decile a symbol landed in, or ``None`` if it is not present."""
    for bucket in buckets:
        if symbol in bucket.symbols:
            return bucket.index
    return None
