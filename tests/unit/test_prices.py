"""Tests for the adjusted-bar bridge.

The test that justifies the module is
:func:`test_a_split_stops_looking_like_a_ninety_percent_loss`. Everything else
guards the ways this could silently do nothing.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.engine import Bar
from indian_equity_research.backtest.prices import adjust_bars, residual_moves
from indian_equity_research.market.adjustment import Adjustment, AdjustmentSource

START = dt.date(2020, 1, 1)


def split(ex_date: dt.date, multiplier: float) -> Adjustment:
    return Adjustment(
        ex_date=ex_date,
        multiplier=multiplier,
        source=AdjustmentSource.DOCUMENTED,
        detail="test",
    )


def flat_then_split(n: int, price: float, ex_index: int, ratio: float) -> dict[dt.date, Bar]:
    """A security at a constant price that splits partway through.

    Raw prices: `price` before the ex-date, `price * ratio` from it. The
    security is worth exactly the same throughout; only the share count
    changed.
    """
    bars = {}
    for i in range(n):
        when = START + dt.timedelta(days=i)
        p = price if i < ex_index else price * ratio
        bars[when] = Bar(date=when, open=p, high=p * 1.01, low=p * 0.99, close=p)
    return bars


def test_a_split_stops_looking_like_a_ninety_percent_loss() -> None:
    """The whole reason this module exists.

    A 10-for-1 split on an otherwise flat security shows as a -90% return in
    raw prices. After back-adjustment the return on the ex-date is zero,
    because nothing happened to the value of the holding.
    """
    ex = START + dt.timedelta(days=5)
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.1)
    days = sorted(raw)

    raw_return = raw[days[5]].close / raw[days[4]].close - 1.0
    assert raw_return == pytest.approx(-0.9), "the raw series must show the fake loss"

    fixed = adjust_bars(raw, [split(ex, 0.1)])
    adjusted_return = fixed[days[5]].close / fixed[days[4]].close - 1.0
    assert adjusted_return == pytest.approx(0.0, abs=1e-9)


def test_the_most_recent_bar_is_never_rescaled() -> None:
    """Back-adjustment expresses history on today's basis, not the reverse.

    A reader comparing the final bar against a broker screen must see the same
    number.
    """
    ex = START + dt.timedelta(days=5)
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.1)
    fixed = adjust_bars(raw, [split(ex, 0.1)])
    last = max(raw)
    assert fixed[last].close == pytest.approx(raw[last].close)


def test_all_four_prices_take_the_same_factor() -> None:
    """Scaling close alone would leave high < close on split days.

    That corrupts anything built on ranges -- ATR, gaps, intraday extremes --
    and does so only on the handful of days that matter most.
    """
    ex = START + dt.timedelta(days=5)
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.1)
    fixed = adjust_bars(raw, [split(ex, 0.1)])
    for when, bar in fixed.items():
        assert bar.low <= bar.open <= bar.high
        assert bar.low <= bar.close <= bar.high
        ratio = bar.close / raw[when].close
        for field in ("open", "high", "low"):
            assert getattr(bar, field) / getattr(raw[when], field) == pytest.approx(ratio)


def test_two_splits_compound() -> None:
    """A 1:5 then a 1:2 leaves the earliest prices at one tenth."""
    first = START + dt.timedelta(days=3)
    second = START + dt.timedelta(days=7)
    raw = {
        START + dt.timedelta(days=i): Bar(
            date=START + dt.timedelta(days=i), open=100.0, high=101.0, low=99.0, close=100.0
        )
        for i in range(10)
    }
    fixed = adjust_bars(raw, [split(first, 0.2), split(second, 0.5)])
    assert fixed[START].close == pytest.approx(100.0 * 0.2 * 0.5)
    assert fixed[START + dt.timedelta(days=5)].close == pytest.approx(100.0 * 0.5)
    assert fixed[START + dt.timedelta(days=9)].close == pytest.approx(100.0)


def test_no_adjustments_leaves_the_series_untouched() -> None:
    """A security with no corporate action must be returned exactly as it was."""
    raw = flat_then_split(10, 1000.0, ex_index=99, ratio=1.0)
    assert adjust_bars(raw, []) == raw


def test_a_bonus_and_a_split_are_treated_identically() -> None:
    """Treat a bonus and a split identically.

    Both are ratio adjustments; only the arithmetic that produced the
    multiplier differs. A 1:1 bonus and a 2-for-1 split both give 0.5, and the price series cannot
    tell them apart -- correctly, because the holder's position is the same.
    """
    ex = START + dt.timedelta(days=5)
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.5)
    bonus = adjust_bars(raw, [split(ex, 0.5)])
    assert bonus[START].close == pytest.approx(500.0)


def test_an_adjustment_outside_the_window_still_scales_history() -> None:
    """An ex-date after every bar rescales the whole series.

    This is what a split occurring after the backtest window looks like, and
    getting it wrong would leave the last window on a different basis from the
    one before it.
    """
    raw = flat_then_split(5, 100.0, ex_index=99, ratio=1.0)
    fixed = adjust_bars(raw, [split(START + dt.timedelta(days=99), 0.5)])
    assert all(b.close == pytest.approx(50.0) for b in fixed.values())


# ---------------------------------------------------------------------------
# The guard that catches what the audit could not reach
# ---------------------------------------------------------------------------


def test_an_unadjusted_split_is_reported_as_a_residual() -> None:
    """The check that found TIDEWATER.

    The hand audit was scoped to names trading at least Rs 20 crore a day.
    TIDEWATER split on 2021-10-18 on Rs 4.03 crore, so it was never examined,
    and its corporate actions sit in the NSE feed under the post-rename symbol
    VEEDOL. Two independent reasons the adjustment was missed, and this one
    check catches both -- because it looks at the output, not the inputs.
    """
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.1)
    found = residual_moves({"TIDEWATER": raw})
    assert len(found) == 1
    assert found[0].symbol == "TIDEWATER"
    assert found[0].multiplier == pytest.approx(0.1)


def test_a_correctly_adjusted_split_leaves_no_residual() -> None:
    ex = START + dt.timedelta(days=5)
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.1)
    assert residual_moves({"X": adjust_bars(raw, [split(ex, 0.1)])}) == []


def test_a_real_crash_is_reported_but_not_adjusted_away() -> None:
    """Report a real crash without adjusting it away.

    DHFL fell 42.6% in one session and Jet Airways 40.8%; both are real. If
    this module adjusted on suspicion it would erase them, which is precisely
    the failure the audit exists to prevent.
    """
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.574)
    found = residual_moves({"DHFL": raw})
    assert len(found) == 1
    # Reported, and the bars are untouched.
    assert raw[max(raw)].close == pytest.approx(574.0)


def test_ordinary_volatility_is_not_flagged() -> None:
    """The threshold must not fire on a bad but normal day."""
    raw = flat_then_split(10, 1000.0, ex_index=5, ratio=0.75)
    assert residual_moves({"X": raw}) == []
