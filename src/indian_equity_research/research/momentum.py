"""12-1 momentum, as registered in H1 and specified for H2 by Amendment A9.

The signal is the total return over the trailing twelve months **excluding the
most recent month**. Both halves of that sentence are load-bearing.

Why twelve months
-----------------
It is the horizon at which momentum has survived replication (Hou-Xue-Zhang
2020, where most anomalies did not). Nothing here searched for a better one, and
searching would be a trial per window tried.

Why the most recent month is skipped
------------------------------------
Short-horizon reversal runs the other way. A stock that jumped last month tends
to give some of it back, so including that month mixes two effects with opposite
signs and dilutes the measurement of either. The skip is not a tuning parameter;
it is what makes the quantity 12-1 momentum rather than 12-0.

The look-ahead surface, and why it is narrower than it looks
------------------------------------------------------------
A ranking signal has exactly two ways to see the future, and both are cheap to
close:

1. **Reading a bar dated after the decision.** Closed structurally: this module
   takes a :class:`~indian_equity_research.backtest.engine.PriceView`, which
   refuses any date after the session it is pinned to. There is no lenient mode
   and no bypass, so a violation is an exception rather than a silent gain.
2. **Ranking a security that was not investable.** Subtler and more damaging.
   Deciding on a name that had not yet listed, had already left the index, or
   did not trade that day produces a portfolio nobody could have held. Closed by
   requiring the caller to pass the point-in-time membership and by dropping any
   name without a bar on the decision date.

What this refuses to do
-----------------------
It never interpolates a missing price, and it never scores a security with an
incomplete window. A security with eight months of history has an eight-month
return, and comparing that against a twelve-month return ranks the measurement
period rather than the momentum. Short histories are excluded and counted, so
the exclusion is visible in the result rather than inferred from a gap.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Final

from indian_equity_research.backtest.engine import PriceView

__all__ = [
    "FORMATION_SESSIONS",
    "MINIMUM_HISTORY_SESSIONS",
    "SKIP_SESSIONS",
    "MomentumRanking",
    "MomentumScore",
    "rank_by_momentum",
    "select_top",
]

# Sessions in the formation window. NSE trades about 250 sessions a year; 252 is
# the convention and the exact figure does not matter provided it is fixed
# before any result is seen, which it is.
FORMATION_SESSIONS: Final = 252

# The skipped month. Twenty-one sessions is one trading month.
SKIP_SESSIONS: Final = 21

# A security must have at least the full window to be scored at all.
MINIMUM_HISTORY_SESSIONS: Final = FORMATION_SESSIONS


@dataclass(frozen=True, slots=True)
class MomentumScore:
    """One security's 12-1 momentum on one decision date."""

    symbol: str
    score: float
    start_close: float
    end_close: float

    def describe(self) -> str:
        """One line a human can re-derive from two prices."""
        return f"{self.symbol}: {self.start_close:.2f} -> {self.end_close:.2f} = {self.score:+.2%}"


@dataclass(frozen=True, slots=True)
class MomentumRanking:
    """Scored securities, and an account of everything left out.

    The exclusions are part of the result rather than a side effect. A ranking
    of forty names drawn from a hundred-name index means sixty were dropped, and
    a reader cannot judge the ranking without knowing why.
    """

    as_of: date
    scores: tuple[MomentumScore, ...]
    excluded_not_a_member: int
    excluded_short_history: int
    excluded_no_bar: int

    @property
    def considered(self) -> int:
        """Securities that reached the ranking."""
        return len(self.scores)

    def describe(self) -> str:
        """One line, carrying the exclusions with it."""
        return (
            f"{self.as_of}: {self.considered} ranked "
            f"({self.excluded_not_a_member} not members, "
            f"{self.excluded_short_history} short history, "
            f"{self.excluded_no_bar} did not trade)"
        )


def rank_by_momentum(
    view: PriceView,
    members: Iterable[str],
    *,
    formation: int = FORMATION_SESSIONS,
    skip: int = SKIP_SESSIONS,
) -> MomentumRanking:
    """Score index members by 12-1 momentum, highest first.

    The window ends ``skip`` sessions before the decision date and begins
    ``formation`` sessions before that. Both endpoints are taken from bars the
    view will serve, so neither can be dated after the decision.

    Args:
        view: Pinned to the decision session. Refuses future dates itself.
        members: Point-in-time index membership on the decision date. Passing
            today's constituents here would reintroduce survivorship bias at the
            one place it is hardest to see.
        formation: Sessions in the formation window.
        skip: Sessions skipped immediately before the decision date.

    Returns:
        Scores in descending order, ties broken by symbol so the result is
        reproducible, plus the exclusion counts.

    Raises:
        ValueError: if ``formation`` or ``skip`` is not positive.
    """
    if formation < 1:
        raise ValueError(f"formation must be positive, got {formation}")
    if skip < 1:
        raise ValueError(
            f"skip must be positive, got {skip}. A skip of zero is 12-0 momentum, "
            f"which mixes in short-horizon reversal and is a different signal from "
            f"the one H1 registered."
        )

    eligible = set(members)
    scores: list[MomentumScore] = []
    short_history = 0
    no_bar = 0
    needed = formation + skip

    for symbol in sorted(eligible):
        # Tradeability first, history second, and the order matters for the
        # *reason* rather than the outcome. A name that did not trade on the
        # decision date is one bar short of the window, so checking length first
        # reports it as short history -- a true statement about the data and a
        # false one about the cause. The exclusion counts are only worth having
        # if each one means what it says.
        if view.bar(symbol, view.as_of) is None:
            no_bar += 1
            continue
        # The whole window in one call, so every bar comes through the guard.
        window = view.history(symbol, needed)
        if len(window) < needed:
            short_history += 1
            continue
        start = window[0]
        end = window[-1 - skip]
        if start.close <= 0:
            no_bar += 1
            continue
        scores.append(
            MomentumScore(
                symbol=symbol,
                score=end.close / start.close - 1.0,
                start_close=start.close,
                end_close=end.close,
            )
        )

    available = set(view.symbols())
    return MomentumRanking(
        as_of=view.as_of,
        scores=tuple(sorted(scores, key=lambda s: (-s.score, s.symbol))),
        excluded_not_a_member=len(available - eligible),
        excluded_short_history=short_history,
        excluded_no_bar=no_bar,
    )


def select_top(ranking: MomentumRanking, holdings: int) -> dict[str, float]:
    """Equal-weight the top ``holdings`` names.

    Returns fewer than ``holdings`` positions when the ranking is short, and
    weights them at ``1 / holdings`` rather than ``1 / len(selected)``. The
    remainder stays in cash.

    That choice is deliberate and it is the conservative one. Re-weighting to
    fill the book would quietly increase concentration on exactly the dates when
    the universe was thin -- early in the archive, and around delistings -- and
    would report the returns of a more aggressive portfolio than the one
    Amendment A9 declared.

    Args:
        ranking: Output of :func:`rank_by_momentum`.
        holdings: Declared breadth. A9 fixes this at 10 for H2.

    Returns:
        ``{symbol: weight}``, suitable as engine target weights.

    Raises:
        ValueError: if ``holdings`` is not positive.
    """
    if holdings < 1:
        raise ValueError(f"holdings must be positive, got {holdings}")
    weight = 1.0 / holdings
    return {score.symbol: weight for score in ranking.scores[:holdings]}
