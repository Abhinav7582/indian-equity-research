"""Proxy universe construction — SCAFFOLDING, NOT EVIDENCE (Amendment A5).

Read this before using anything here
------------------------------------
This module builds a **liquidity-ranked proxy** for the Nifty 100. It is not
the Nifty 100 and must never be presented as it. Under Amendment A5, dated
2026-08-10:

* No result produced on this universe may enter the trial register.
* No result produced on this universe may be cited for or against H1, H2, H3,
  H5 or H6.
* It exists solely to exercise the engine — to verify that costs are charged,
  execution lags correctly, and leakage is detectable.

**The tilt, stated plainly.** NSE selects the Nifty 100 on full market
capitalisation from the Nifty 500 universe, applying liquidity as a filter.
This ranks on turnover alone. Turnover and market capitalisation correlate but
are not the same thing: this proxy will admit small, heavily traded,
often speculative names the real index excludes, and drop large quietly-held
ones it includes. That difference tilts toward exactly the kind of stock that
produces flattering momentum backtests, which is why A5 forbids drawing
conclusions from it.

Parameters below are transcribed from A5 and must not be tuned. Changing any of
them requires a further dated amendment.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Final

from indian_equity_research.market.bhavcopy import BhavRecord
from indian_equity_research.market.instruments import NORMAL_SERIES

__all__ = [
    "SCAFFOLDING_HEADER",
    "UniverseError",
    "UniverseSnapshot",
    "UniverseSpec",
    "build_universe_schedule",
    "members_on",
    "rebalance_dates",
    "turnover_floor_for",
]

SCAFFOLDING_HEADER: Final = "SCAFFOLDING — NOT EVIDENCE (Amendment A5)"

# --- Amendment A5 parameters. Transcribed, not chosen. ---
RANKING_WINDOW_SESSIONS: Final = 126
UNIVERSE_SIZE: Final = 100
RECONSTITUTION_LAG_SESSIONS: Final = 5
MINIMUM_HISTORY_SESSIONS: Final = 126
REBALANCE_MONTHS: Final = (4, 10)


class UniverseError(ValueError):
    """Raised when a universe cannot be built honestly from the data given."""


@dataclass(frozen=True, slots=True)
class UniverseSpec:
    """The declared construction rule. Defaults are Amendment A5 verbatim."""

    ranking_window: int = RANKING_WINDOW_SESSIONS
    size: int = UNIVERSE_SIZE
    reconstitution_lag: int = RECONSTITUTION_LAG_SESSIONS
    minimum_history: int = MINIMUM_HISTORY_SESSIONS
    eligible_series: frozenset[str] = NORMAL_SERIES

    def __post_init__(self) -> None:
        """Reject specs that could not describe a real universe."""
        if self.ranking_window < 1:
            raise UniverseError(f"ranking_window must be positive, got {self.ranking_window}")
        if self.size < 1:
            raise UniverseError(f"size must be positive, got {self.size}")
        if self.reconstitution_lag < 0:
            raise UniverseError("reconstitution_lag must not be negative")
        if self.minimum_history < 1:
            raise UniverseError(f"minimum_history must be positive, got {self.minimum_history}")
        if not self.eligible_series:
            raise UniverseError("eligible_series must not be empty")

    def is_amendment_a5_default(self) -> bool:
        """True only if every parameter still matches the declared amendment.

        Anything else is a different universe and needs its own amendment.
        """
        return (
            self.ranking_window == RANKING_WINDOW_SESSIONS
            and self.size == UNIVERSE_SIZE
            and self.reconstitution_lag == RECONSTITUTION_LAG_SESSIONS
            and self.minimum_history == MINIMUM_HISTORY_SESSIONS
            and self.eligible_series == NORMAL_SERIES
        )


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    """Membership effective from a date, and the evidence behind it."""

    effective_from: date
    ranking_window_end: date
    members: tuple[str, ...]
    median_turnover: dict[str, float]
    candidates_considered: int
    excluded_insufficient_history: int

    @property
    def size(self) -> int:
        """Number of members actually selected."""
        return len(self.members)

    def describe(self) -> str:
        """One line, carrying the scaffolding warning with it."""
        return (
            f"[{SCAFFOLDING_HEADER}] {self.effective_from}: {self.size} members "
            f"from {self.candidates_considered} candidates ranked to "
            f"{self.ranking_window_end} "
            f"({self.excluded_insufficient_history} excluded for short history)"
        )


def rebalance_dates(sessions: list[date]) -> list[date]:
    """First session of April and October within ``sessions``.

    Mirrors NSE's semi-annual cadence, as fixed by Amendment A5.
    """
    if not sessions:
        return []
    ordered = sorted(set(sessions))
    seen: set[tuple[int, int]] = set()
    out: list[date] = []
    for day in ordered:
        if day.month in REBALANCE_MONTHS and (day.year, day.month) not in seen:
            seen.add((day.year, day.month))
            out.append(day)
    return out


def build_universe_schedule(
    records: list[BhavRecord],
    *,
    spec: UniverseSpec | None = None,
) -> list[UniverseSnapshot]:
    """Build the full sequence of universe snapshots from bhavcopy records.

    The ranking window for a snapshot effective on date *D* ends
    ``reconstitution_lag`` sessions **before** *D*, so membership is computable
    from data that existed before it was acted on. Without that gap the
    universe would be selected using prices from the day it starts trading,
    which is look-ahead dressed up as index construction.

    Args:
        records: Cash-equity rows. Only ``spec.eligible_series`` are considered.
        spec: Construction rule. Defaults to Amendment A5.

    Returns:
        One snapshot per rebalance date, ascending.

    Raises:
        UniverseError: if no eligible records exist, or no rebalance date has
            enough preceding history to rank on.
    """
    cfg = spec or UniverseSpec()
    eligible = [r for r in records if r.series in cfg.eligible_series]
    if not eligible:
        raise UniverseError(
            f"no records in series {sorted(cfg.eligible_series)}; "
            f"saw {sorted({r.series for r in records})[:8]}"
        )

    by_session: dict[date, list[BhavRecord]] = defaultdict(list)
    for record in eligible:
        by_session[record.trade_date].append(record)
    sessions = sorted(by_session)

    turnover: dict[str, dict[date, float]] = defaultdict(dict)
    for day, rows in by_session.items():
        for row in rows:
            turnover[row.isin][day] = row.turnover

    snapshots: list[UniverseSnapshot] = []
    for effective in rebalance_dates(sessions):
        index = sessions.index(effective)
        window_end_index = index - cfg.reconstitution_lag
        if window_end_index < cfg.ranking_window:
            # Not enough history yet. Skipping is correct; ranking on a partial
            # window would silently favour whatever happened to be listed.
            continue
        window = sessions[max(0, window_end_index - cfg.ranking_window) : window_end_index]
        if not window:
            continue
        window_set = set(window)

        ranked: list[tuple[float, str]] = []
        short_history = 0
        for isin, days in turnover.items():
            observed = [v for d, v in days.items() if d in window_set]
            if len(observed) < cfg.minimum_history:
                short_history += 1
                continue
            ranked.append((statistics.median(observed), isin))

        if not ranked:
            continue
        # Sort by turnover descending, then ISIN, so ties resolve
        # deterministically rather than by dictionary ordering.
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))
        chosen = ranked[: cfg.size]
        snapshots.append(
            UniverseSnapshot(
                effective_from=effective,
                ranking_window_end=window[-1],
                members=tuple(isin for _, isin in chosen),
                median_turnover={isin: value for value, isin in chosen},
                candidates_considered=len(ranked),
                excluded_insufficient_history=short_history,
            )
        )

    if not snapshots:
        span = f"{sessions[0]} .. {sessions[-1]}" if sessions else "none"
        raise UniverseError(
            f"no rebalance date had {cfg.ranking_window} sessions of preceding "
            f"history plus a {cfg.reconstitution_lag}-session lag. "
            f"Sessions available: {len(sessions)} ({span})."
        )
    return snapshots


def members_on(snapshots: list[UniverseSnapshot], when: date) -> tuple[str, ...]:
    """Membership in force on ``when``.

    Uses the latest snapshot effective on or before that date. Returns empty
    before the first snapshot rather than guessing.
    """
    applicable = [s for s in snapshots if s.effective_from <= when]
    if not applicable:
        return ()
    return max(applicable, key=lambda s: s.effective_from).members


def turnover_floor_for(snapshot: UniverseSnapshot, *, percentile: float = 0.10) -> float:
    """Median turnover at a given percentile of the snapshot's members.

    Useful for sanity-checking that the thinnest members of the universe are
    actually tradeable at the intended position size. A universe whose bottom
    decile trades a few lakh a day cannot absorb real orders, and a backtest
    that ignores that is describing a market that does not exist.
    """
    if not 0.0 <= percentile <= 1.0:
        raise UniverseError(f"percentile must be between 0 and 1, got {percentile}")
    values = sorted(snapshot.median_turnover.values())
    if not values:
        raise UniverseError("snapshot has no members")
    position = min(int(len(values) * percentile), len(values) - 1)
    return values[position]
