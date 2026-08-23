"""Tests for the adjusted-bar bridge.

The test that justifies the module is
:func:`test_a_split_stops_looking_like_a_ninety_percent_loss`. Everything else
guards the ways this could silently do nothing.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.engine import Bar
from indian_equity_research.backtest.prices import (
    CASH_EQUITY_SERIES,
    FeedAdjustment,
    SymbolSpan,
    adjust_bars,
    residual_moves,
    route_adjustments,
)
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

    Worth recording what it actually found, because the first reading of it was
    wrong. The residual was ``2021-10-18 x0.1123`` and was taken for a missed
    split in a thinly traded name. It was not: TIDEWATER traded every session,
    but on the surveillance series ``BE`` from 2021-07-15, and the loader kept
    only ``EQ``. Three months of bars were dropped, welding 2021-07-14 onto
    2021-10-18 across a documented x0.2 action and a real 43 per cent fall.

    No input check could have caught that -- the feed was complete and the
    register was fully marked. Only the output was wrong. That is the argument
    for this function.
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


# ---------------------------------------------------------------------------
# Routing: the feed labels every historical row with today's symbol
# ---------------------------------------------------------------------------


def feed(symbol: str, isin: str, ex_date: dt.date, multiplier: float) -> FeedAdjustment:
    return FeedAdjustment(symbol=symbol, isin=isin, adjustment=split(ex_date, multiplier))


def verified(symbol: str, ex_date: dt.date, multiplier: float) -> FeedAdjustment:
    return FeedAdjustment(
        symbol=symbol, isin="", adjustment=split(ex_date, multiplier), hand_verified=True
    )


CADILA = SymbolSpan(
    first=dt.date(2015, 1, 1), last=dt.date(2022, 3, 4), isins=frozenset({"INE010B01027"})
)
ZYDUS = SymbolSpan(
    first=dt.date(2022, 3, 7), last=dt.date(2026, 8, 5), isins=frozenset({"INE010B01027"})
)


def test_an_action_reaches_the_name_the_security_traded_under() -> None:
    """The 7.2% of documented ratios that symbol-keying threw away.

    NSE reports the **current** symbol on every historical row, so Cadila's
    2015 split comes back labelled ZYDUSLIFE -- a name that first traded in
    2022. Keyed by symbol it lands nowhere and does nothing, with no error.
    """
    entry = feed("ZYDUSLIFE", "INE010B01027", dt.date(2015, 10, 6), 0.2)
    routed, unrouted, _ = route_adjustments([entry], {"CADILAHC": CADILA, "ZYDUSLIFE": ZYDUS})

    assert unrouted == []
    assert "ZYDUSLIFE" not in routed, "the 2022 name did not exist on the 2015 ex-date"
    assert [a.multiplier for a in routed["CADILAHC"]] == [0.2]


def test_a_security_outside_the_run_is_not_reported_as_unrouted() -> None:
    """Absent is not the same as unplaceable.

    A run restricted to twenty names must not report the other eight hundred
    adjustments as problems, or the real ones become unfindable.
    """
    entry = feed("RELIANCE", "INE002A01018", dt.date(2024, 10, 28), 0.5)
    routed, unrouted, _ = route_adjustments([entry], {"CADILAHC": CADILA})
    assert routed == {} and unrouted == []


def test_an_ambiguous_isin_is_reported_rather_than_guessed() -> None:
    """Two live tickers on one ISIN means an assumption is wrong.

    Picking one would apply an adjustment to a security that may not have had
    it, and the choice would be invisible afterwards.
    """
    overlap = SymbolSpan(
        first=dt.date(2015, 1, 1), last=dt.date(2026, 1, 1), isins=frozenset({"INE010B01027"})
    )
    entry = feed("ZYDUSLIFE", "INE010B01027", dt.date(2015, 10, 6), 0.2)
    routed, unrouted, _ = route_adjustments([entry], {"CADILAHC": CADILA, "OTHER": overlap})
    assert routed == {}
    assert [u.symbol for u in unrouted] == ["ZYDUSLIFE"]


def test_two_feed_actions_on_one_day_compound() -> None:
    """VEEDOL, 2021-07-26: a 1:1 bonus and a 5-to-2 split, both real, x0.5 * x0.4."""
    when = dt.date(2021, 7, 26)
    spans = {"TIDEWATER": SymbolSpan(dt.date(2015, 1, 1), dt.date(2024, 10, 8), frozenset({"I1"}))}
    entries = [feed("VEEDOL", "I1", when, 0.5), feed("VEEDOL", "I1", when, 0.4)]
    routed, _, superseded = route_adjustments(entries, spans)
    product = 1.0
    for adjustment in routed["TIDEWATER"]:
        product *= adjustment.multiplier
    assert product == pytest.approx(0.2)
    assert superseded == []


def test_a_verified_verdict_replaces_the_feed_rather_than_stacking() -> None:
    """The double-adjustment that fixing the routing bug exposed.

    The six hand-verified entries were recovered by a person *because* the feed
    rows were misrouted. Once routing worked, both landed on the same day: a
    x0.25 split became x0.125, turning a real 76 per cent fall into a
    fictitious 94 per cent gain. A verdict is one account of a whole day's
    move, so it supersedes; it does not compound.
    """
    when = dt.date(2016, 3, 16)
    spans = {"TIDEWATER": SymbolSpan(dt.date(2015, 1, 1), dt.date(2024, 10, 8), frozenset({"I1"}))}
    entries = [feed("VEEDOL", "I1", when, 0.25), verified("TIDEWATER", when, 0.25)]
    routed, _, superseded = route_adjustments(entries, spans)

    assert [a.multiplier for a in routed["TIDEWATER"]] == [0.25]
    assert len(superseded) == 1
    assert not superseded[0].material, "these two agree; only disagreement is a finding"


def test_a_superseded_action_that_disagrees_is_flagged() -> None:
    """Disagreement means the feed subject was read incompletely.

    Silently preferring the verdict would hide the parser defect that made the
    verdict necessary.
    """
    when = dt.date(2016, 3, 16)
    spans = {"TIDEWATER": SymbolSpan(dt.date(2015, 1, 1), dt.date(2024, 10, 8), frozenset({"I1"}))}
    entries = [feed("VEEDOL", "I1", when, 0.5), verified("TIDEWATER", when, 0.25)]
    _, _, superseded = route_adjustments(entries, spans)
    assert superseded[0].material
    assert "DISAGREE" in superseded[0].describe()


# ---------------------------------------------------------------------------
# The settlement series
# ---------------------------------------------------------------------------


def test_the_surveillance_series_are_kept() -> None:
    """BE and BZ are the same share under a stricter settlement rule.

    Dropping them does not produce missing data. It produces *absent* data, and
    the sessions either side become adjacent, so a return gets computed across
    a gap no holder ever experienced.
    """
    assert {"EQ", "BE", "BZ"} <= CASH_EQUITY_SERIES


def test_the_sme_and_debt_series_are_excluded() -> None:
    """A separate board and a different instrument, not a settlement variant."""
    assert not CASH_EQUITY_SERIES & {"SM", "ST", "GB", "GS", "TB", "N1", "NE"}
