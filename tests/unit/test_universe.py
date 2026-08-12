"""Tests for the A5 proxy universe.

The property that matters most is the reconstitution lag: membership effective
on a date must be computable from data that existed before it. A universe
selected using prices from the day it starts trading is look-ahead wearing the
costume of index construction, and it is invisible in the output.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.universe import (
    SCAFFOLDING_HEADER,
    UniverseError,
    UniverseSpec,
    build_universe_schedule,
    members_on,
    rebalance_dates,
    turnover_floor_for,
)
from indian_equity_research.market.bhavcopy import BhavRecord


def make_records(
    isin_turnovers: dict[str, float],
    start: dt.date,
    n_sessions: int,
    *,
    series: str = "EQ",
) -> list[BhavRecord]:
    """Records with constant per-ISIN turnover, so ranking is deterministic."""
    out = []
    day = start
    made = 0
    while made < n_sessions:
        if day.weekday() < 5:
            for isin, turnover in isin_turnovers.items():
                out.append(
                    BhavRecord(
                        trade_date=day,
                        isin=isin,
                        symbol=isin[-4:],
                        series=series,
                        open=100.0,
                        high=101.0,
                        low=99.0,
                        close=100.0,
                        previous_close=100.0,
                        volume=1000,
                        turnover=turnover,
                        trades=10,
                    )
                )
            made += 1
        day += dt.timedelta(days=1)
    return out


SMALL_SPEC = UniverseSpec(ranking_window=5, size=3, reconstitution_lag=2, minimum_history=5)


# --------------------------------------------------------------------------
# The declared parameters must be what the amendment says
# --------------------------------------------------------------------------


def test_defaults_are_amendment_a5_verbatim() -> None:
    spec = UniverseSpec()
    assert spec.ranking_window == 126
    assert spec.size == 100
    assert spec.reconstitution_lag == 5
    assert spec.minimum_history == 126
    assert spec.eligible_series == frozenset({"EQ"})
    assert spec.is_amendment_a5_default()


def test_a_tuned_spec_is_flagged_as_no_longer_the_declared_one() -> None:
    """Detect a tuned spec.

    A tuned universe must not be passable off as the pre-registered one.
    """
    assert not UniverseSpec(size=50).is_amendment_a5_default()
    assert not UniverseSpec(ranking_window=60).is_amendment_a5_default()


def test_invalid_specs_are_refused() -> None:
    with pytest.raises(UniverseError, match="ranking_window"):
        UniverseSpec(ranking_window=0)
    with pytest.raises(UniverseError, match="size"):
        UniverseSpec(size=0)
    with pytest.raises(UniverseError, match="eligible_series"):
        UniverseSpec(eligible_series=frozenset())


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------


def test_members_are_the_highest_turnover_names() -> None:
    turnovers = {f"INE{i:04d}": float(i * 1000) for i in range(1, 11)}
    records = make_records(turnovers, dt.date(2023, 1, 2), 200)
    snapshots = build_universe_schedule(records, spec=SMALL_SPEC)
    assert snapshots
    top = snapshots[0].members
    assert top == ("INE0010", "INE0009", "INE0008")


def test_ties_resolve_deterministically() -> None:
    """Identical turnover must not produce order that depends on dict iteration."""
    turnovers = {f"INE{i:04d}": 5000.0 for i in range(1, 8)}
    records = make_records(turnovers, dt.date(2023, 1, 2), 200)
    a = build_universe_schedule(records, spec=SMALL_SPEC)[0].members
    b = build_universe_schedule(list(reversed(records)), spec=SMALL_SPEC)[0].members
    assert a == b


def test_only_eligible_series_are_considered() -> None:
    """BE and BZ are trade-to-trade: different liquidity, different costs."""
    eq = make_records({"INE0001": 1000.0}, dt.date(2023, 1, 2), 200)
    be = make_records({"INE9999": 99_999_999.0}, dt.date(2023, 1, 2), 200, series="BE")
    snapshots = build_universe_schedule(eq + be, spec=SMALL_SPEC)
    assert "INE9999" not in snapshots[0].members, "a trade-to-trade name entered the universe"
    assert "INE0001" in snapshots[0].members


def test_all_ineligible_series_raises_rather_than_returning_empty() -> None:
    be = make_records({"INE9999": 1000.0}, dt.date(2023, 1, 2), 200, series="BE")
    with pytest.raises(UniverseError, match="no records in series"):
        build_universe_schedule(be, spec=SMALL_SPEC)


def test_short_history_names_are_excluded_and_counted() -> None:
    long_history = make_records({"INE0001": 5000.0}, dt.date(2023, 1, 2), 200)
    late = make_records({"INE0002": 999_999.0}, dt.date(2023, 9, 1), 40)
    snapshots = build_universe_schedule(long_history + late, spec=SMALL_SPEC)
    first = snapshots[0]
    assert "INE0002" not in first.members
    assert first.excluded_insufficient_history >= 1


# --------------------------------------------------------------------------
# The reconstitution lag: the anti-look-ahead property
# --------------------------------------------------------------------------


def test_ranking_window_ends_strictly_before_the_effective_date() -> None:
    """The core guarantee of this module."""
    turnovers = {f"INE{i:04d}": float(i * 1000) for i in range(1, 6)}
    records = make_records(turnovers, dt.date(2023, 1, 2), 300)
    for snapshot in build_universe_schedule(records, spec=SMALL_SPEC):
        assert snapshot.ranking_window_end < snapshot.effective_from, (
            f"window ended {snapshot.ranking_window_end} but membership took effect "
            f"{snapshot.effective_from}: the universe was chosen using data from "
            f"the period it was already trading in"
        )


def test_turnover_after_the_window_cannot_change_membership() -> None:
    """Ignore turnover that arrives after the ranking window closes.

    A name that explodes in turnover after the window must not be admitted by
    that explosion. If it is, the lag is not being applied.
    """
    base = {f"INE{i:04d}": float(i * 100) for i in range(1, 6)}
    quiet = make_records(base, dt.date(2023, 1, 2), 300)

    # Derive the boundary from the snapshot rather than guessing a date. An
    # earlier version of this test hardcoded one that fell *inside* the ranking
    # window, so it failed for the right reason and proved nothing.
    reference = build_universe_schedule(quiet, spec=SMALL_SPEC)[0]
    spike_from = reference.ranking_window_end + dt.timedelta(days=1)
    assert spike_from <= reference.effective_from, "test fixture does not exercise the lag"

    loud = []
    for record in quiet:
        turnover = record.turnover
        if record.isin == "INE0001" and record.trade_date >= spike_from:
            turnover = 10_000_000.0
        loud.append(
            BhavRecord(
                trade_date=record.trade_date,
                isin=record.isin,
                symbol=record.symbol,
                series=record.series,
                open=record.open,
                high=record.high,
                low=record.low,
                close=record.close,
                previous_close=record.previous_close,
                volume=record.volume,
                turnover=turnover,
                trades=record.trades,
            )
        )

    quiet_first = build_universe_schedule(quiet, spec=SMALL_SPEC)[0]
    loud_first = build_universe_schedule(loud, spec=SMALL_SPEC)[0]
    assert quiet_first.effective_from == loud_first.effective_from
    assert quiet_first.members == loud_first.members


# --------------------------------------------------------------------------
# Rebalance schedule
# --------------------------------------------------------------------------


def test_rebalances_are_first_session_of_april_and_october() -> None:
    sessions = [dt.date(2023, 1, 1) + dt.timedelta(days=i) for i in range(800)]
    dates = rebalance_dates(sessions)
    assert all(d.month in (4, 10) for d in dates)
    assert all(d.day == 1 for d in dates)
    assert dates == sorted(dates)
    assert len(dates) == 4


def test_rebalance_picks_the_first_available_session_not_the_first_of_month() -> None:
    """If the 1st is a holiday, the universe must turn over on the next session."""
    sessions = [dt.date(2023, 4, 5), dt.date(2023, 4, 6), dt.date(2023, 10, 9)]
    assert rebalance_dates(sessions) == [dt.date(2023, 4, 5), dt.date(2023, 10, 9)]


def test_empty_sessions_gives_no_rebalances() -> None:
    assert rebalance_dates([]) == []


def test_insufficient_history_raises_with_a_useful_message() -> None:
    records = make_records({"INE0001": 1000.0}, dt.date(2023, 3, 20), 12)
    with pytest.raises(UniverseError, match="sessions of preceding"):
        build_universe_schedule(records, spec=UniverseSpec(ranking_window=126, minimum_history=126))


# --------------------------------------------------------------------------
# Lookups and reporting
# --------------------------------------------------------------------------


def test_members_on_uses_the_latest_snapshot_not_the_nearest() -> None:
    turnovers = {f"INE{i:04d}": float(i * 1000) for i in range(1, 6)}
    records = make_records(turnovers, dt.date(2023, 1, 2), 400)
    snapshots = build_universe_schedule(records, spec=SMALL_SPEC)
    assert len(snapshots) >= 2
    mid = snapshots[1].effective_from + dt.timedelta(days=10)
    assert members_on(snapshots, mid) == snapshots[1].members


def test_members_on_before_the_first_snapshot_is_empty_not_guessed() -> None:
    turnovers = {f"INE{i:04d}": float(i * 1000) for i in range(1, 6)}
    records = make_records(turnovers, dt.date(2023, 1, 2), 300)
    snapshots = build_universe_schedule(records, spec=SMALL_SPEC)
    assert members_on(snapshots, dt.date(2020, 1, 1)) == ()


def test_describe_always_carries_the_scaffolding_warning() -> None:
    """Carry the scaffolding warning on every description.

    A5 requires it to travel with the output, so a snapshot cannot be quoted
    without it.
    """
    turnovers = {f"INE{i:04d}": float(i * 1000) for i in range(1, 6)}
    records = make_records(turnovers, dt.date(2023, 1, 2), 300)
    snapshot = build_universe_schedule(records, spec=SMALL_SPEC)[0]
    assert SCAFFOLDING_HEADER in snapshot.describe()
    assert "NOT EVIDENCE" in snapshot.describe()


def test_turnover_floor_reports_the_thin_end_of_the_universe() -> None:
    turnovers = {f"INE{i:04d}": float(i * 1000) for i in range(1, 11)}
    records = make_records(turnovers, dt.date(2023, 1, 2), 300)
    wide = UniverseSpec(ranking_window=5, size=10, reconstitution_lag=2, minimum_history=5)
    snapshot = build_universe_schedule(records, spec=wide)[0]
    assert turnover_floor_for(snapshot, percentile=0.0) == 1000.0
    assert turnover_floor_for(snapshot, percentile=1.0) == 10000.0
    with pytest.raises(UniverseError, match="percentile"):
        turnover_floor_for(snapshot, percentile=1.5)
