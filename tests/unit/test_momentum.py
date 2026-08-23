"""Tests for the 12-1 momentum signal.

The tests that justify the module are
:func:`test_the_most_recent_month_is_excluded` -- without which this is a
different signal from the one H1 registered -- and
:func:`test_a_non_member_is_never_ranked`, which is where survivorship bias
would re-enter after being removed everywhere else.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.engine import Bar, LookAheadError, PriceView
from indian_equity_research.research.momentum import (
    FORMATION_SESSIONS,
    SKIP_SESSIONS,
    rank_by_momentum,
    select_top,
)

START = dt.date(2018, 1, 1)
NEEDED = FORMATION_SESSIONS + SKIP_SESSIONS


def sessions(n: int) -> list[dt.date]:
    return [START + dt.timedelta(days=i) for i in range(n)]


def series(closes: list[float], days: list[dt.date]) -> dict[dt.date, Bar]:
    return {
        when: Bar(date=when, open=c, high=c * 1.01, low=c * 0.99, close=c)
        for when, c in zip(days, closes, strict=True)
    }


def flat_then(n: int, base: float, changes: dict[int, float]) -> list[float]:
    """A constant price with multiplicative steps applied from given indices."""
    out = []
    level = base
    for i in range(n):
        level *= changes.get(i, 1.0)
        out.append(level)
    return out


def view_of(data: dict[str, dict[dt.date, Bar]], days: list[dt.date]) -> PriceView:
    return PriceView(data, days, days[-1])


def test_the_most_recent_month_is_excluded() -> None:
    """The '-1' in 12-1, and the reason it is not a tuning parameter.

    Short-horizon reversal runs opposite to momentum. RISER doubles inside the
    formation window and gives it all back in the skipped month; SPIKER does
    nothing until the skipped month and then doubles.

    12-1 must rank RISER first. A 12-0 signal would rank SPIKER first, and would
    be measuring reversal while calling it momentum.
    """
    days = sessions(NEEDED)
    riser = flat_then(NEEDED, 100.0, {1: 2.0, NEEDED - SKIP_SESSIONS: 0.5})
    spiker = flat_then(NEEDED, 100.0, {NEEDED - SKIP_SESSIONS: 2.0})
    data = {"RISER": series(riser, days), "SPIKER": series(spiker, days)}

    ranking = rank_by_momentum(view_of(data, days), {"RISER", "SPIKER"})

    assert [s.symbol for s in ranking.scores] == ["RISER", "SPIKER"]
    assert ranking.scores[0].score == pytest.approx(1.0)
    assert ranking.scores[1].score == pytest.approx(0.0)


def test_a_non_member_is_never_ranked() -> None:
    """Where survivorship bias would come back in.

    Every other guard in the project keeps departed companies in the data. This
    is the one that stops a company being *bought* on a date it was not in the
    index -- which is the same error wearing the opposite mask.
    """
    days = sessions(NEEDED)
    data = {
        "MEMBER": series(flat_then(NEEDED, 100.0, {1: 1.5}), days),
        "OUTSIDER": series(flat_then(NEEDED, 100.0, {1: 9.0}), days),
    }
    ranking = rank_by_momentum(view_of(data, days), {"MEMBER"})

    assert [s.symbol for s in ranking.scores] == ["MEMBER"]
    assert ranking.excluded_not_a_member == 1


def test_a_short_history_is_excluded_and_counted() -> None:
    """An eight-month return is not a twelve-month return.

    Scoring both together ranks the measurement period rather than the
    momentum, and the newest listings would dominate whichever direction the
    market moved.
    """
    days = sessions(NEEDED)
    short_days = days[-50:]
    data = {
        "LONG": series(flat_then(NEEDED, 100.0, {1: 1.2}), days),
        "SHORT": series(flat_then(50, 100.0, {1: 5.0}), short_days),
    }
    ranking = rank_by_momentum(view_of(data, days), {"LONG", "SHORT"})

    assert [s.symbol for s in ranking.scores] == ["LONG"]
    assert ranking.excluded_short_history == 1


def test_a_security_that_did_not_trade_is_not_ranked() -> None:
    """Ranked but untradeable is a portfolio nobody could have held.

    A name suspended on the decision date cannot be bought at the next open.
    """
    days = sessions(NEEDED)
    full = series(flat_then(NEEDED, 100.0, {1: 1.2}), days)
    halted = dict(full)
    del halted[days[-1]]
    data = {"TRADING": full, "HALTED": halted}

    ranking = rank_by_momentum(view_of(data, days), {"TRADING", "HALTED"})

    assert [s.symbol for s in ranking.scores] == ["TRADING"]
    assert ranking.excluded_no_bar == 1


def test_the_signal_cannot_read_past_the_decision_date() -> None:
    """Structural, not conventional.

    The view refuses future dates itself, so a look-ahead is an exception rather
    than a quietly better result.
    """
    days = sessions(NEEDED + 5)
    data = {"X": series(flat_then(NEEDED + 5, 100.0, {1: 1.2}), days)}
    view = PriceView(data, days, days[NEEDED - 1])

    rank_by_momentum(view, {"X"})  # does not raise
    with pytest.raises(LookAheadError):
        view.bar("X", days[NEEDED])


def test_a_zero_skip_is_refused() -> None:
    """12-0 is a different signal from the one H1 registered."""
    days = sessions(NEEDED)
    data = {"X": series(flat_then(NEEDED, 100.0, {}), days)}
    with pytest.raises(ValueError, match="different signal"):
        rank_by_momentum(view_of(data, days), {"X"}, skip=0)


def test_ties_break_on_symbol_so_the_result_is_reproducible() -> None:
    """Two runs over the same data must select the same names."""
    days = sessions(NEEDED)
    identical = flat_then(NEEDED, 100.0, {1: 1.5})
    data = {name: series(identical, days) for name in ("CCC", "AAA", "BBB")}
    ranking = rank_by_momentum(view_of(data, days), set(data))
    assert [s.symbol for s in ranking.scores] == ["AAA", "BBB", "CCC"]


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_the_top_decile_is_equal_weighted() -> None:
    days = sessions(NEEDED)
    data = {
        f"S{i:02d}": series(flat_then(NEEDED, 100.0, {1: 1.0 + i / 100}), days) for i in range(20)
    }
    ranking = rank_by_momentum(view_of(data, days), set(data))
    weights = select_top(ranking, 10)

    assert len(weights) == 10
    assert set(weights) == {f"S{i:02d}" for i in range(10, 20)}
    assert all(w == pytest.approx(0.1) for w in weights.values())
    assert sum(weights.values()) == pytest.approx(1.0)


def test_a_thin_universe_leaves_the_remainder_in_cash() -> None:
    """Weights stay at 1/holdings when fewer names qualify.

    Re-weighting to fill the book would raise concentration on exactly the dates
    when the universe was thin, and would report the returns of a more
    aggressive portfolio than Amendment A9 declared.
    """
    days = sessions(NEEDED)
    data = {f"S{i}": series(flat_then(NEEDED, 100.0, {1: 1.1}), days) for i in range(3)}
    ranking = rank_by_momentum(view_of(data, days), set(data))
    weights = select_top(ranking, 10)

    assert len(weights) == 3
    assert all(w == pytest.approx(0.1) for w in weights.values())
    assert sum(weights.values()) == pytest.approx(0.3)


def test_zero_holdings_is_refused() -> None:
    days = sessions(NEEDED)
    data = {"X": series(flat_then(NEEDED, 100.0, {}), days)}
    ranking = rank_by_momentum(view_of(data, days), {"X"})
    with pytest.raises(ValueError, match="must be positive"):
        select_top(ranking, 0)
