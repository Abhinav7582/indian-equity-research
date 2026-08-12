"""Self-deception tests: proof that the engine can be caught lying.

A backtest engine is a machine for producing encouraging numbers. Left
untested, the encouraging numbers arrive whether or not the engine is correct,
and there is no external referee. These tests are the referee.

Each one asserts a property that would be **violated by a specific, plausible
bug** -- not that the engine produces a nice result, but that it produces the
uniquely correct one, to the rupee where that is possible.

The four failures being guarded against:

1. **Look-ahead.** The strategy sees data it could not have had.
2. **Missing costs.** Charges are modelled but not actually deducted.
3. **Execution timing.** Orders fill on the bar the decision was made from.
4. **Arithmetic.** The accounting simply does not add up.

If any test here fails, no result from this engine means anything.
"""

from __future__ import annotations

import datetime as dt
import random

import pytest

from indian_equity_research.backtest.costs import Side, charges_for
from indian_equity_research.backtest.engine import (
    Bar,
    EngineConfig,
    LookAheadError,
    PriceView,
    run_backtest,
)

START = dt.date(2024, 1, 1)


def sessions(n: int) -> list[dt.date]:
    """``n`` consecutive weekday-ish dates. Calendar realism is not the point."""
    return [START + dt.timedelta(days=i) for i in range(n)]


def flat_series(symbol: str, days: list[dt.date], price: float) -> dict[str, dict[dt.date, Bar]]:
    """Build a security whose price never moves.

    Any change in equity is then unambiguously caused by the engine.
    """
    return {symbol: {d: Bar(d, price, price, price, price) for d in days}}


def trending(
    symbol: str, days: list[dt.date], start: float, daily: float
) -> dict[str, dict[dt.date, Bar]]:
    bars: dict[dt.date, Bar] = {}
    price = start
    for d in days:
        bars[d] = Bar(d, price, price * 1.01, price * 0.99, price * (1 + daily))
        price *= 1 + daily
    return {symbol: bars}


# ==========================================================================
# 1. LOOK-AHEAD MUST BE IMPOSSIBLE, NOT MERELY DISCOURAGED
# ==========================================================================


def test_asking_for_tomorrow_raises() -> None:
    """Enforce the core guarantee.

    A strategy that reaches forward gets an exception, not a number.
    """
    days = sessions(10)
    data = flat_series("ACME", days, 100.0)
    view = PriceView(data, days, days[4])

    assert view.bar("ACME", days[4]) is not None  # today is fine
    assert view.bar("ACME", days[3]) is not None  # yesterday is fine
    with pytest.raises(LookAheadError, match="did not exist yet"):
        view.bar("ACME", days[5])


def test_history_never_leaks_past_the_decision_date() -> None:
    days = sessions(50)
    data = flat_series("ACME", days, 100.0)
    view = PriceView(data, days, days[20])
    hist = view.history("ACME", lookback=1000)
    assert len(hist) == 21
    assert max(b.date for b in hist) == days[20]


def test_a_cheating_strategy_is_stopped_at_the_boundary() -> None:
    """Propagate the error rather than swallowing it.

    Swallowing it would leave a plausible-looking equity curve behind.
    """
    days = sessions(10)
    data = flat_series("ACME", days, 100.0)

    def cheat(view: PriceView) -> dict[str, float]:
        view.bar("ACME", view.as_of + dt.timedelta(days=1))  # peek at tomorrow
        return {"ACME": 1.0}

    with pytest.raises(LookAheadError):
        run_backtest(data, days, cheat)


def test_leaked_signal_produces_an_absurd_result() -> None:
    """The positive control.

    If perfect foresight does NOT produce a spectacular return, the engine is
    failing to act on signals at all -- and would equally fail to act on a real
    one. A test suite that only checks that cheating is blocked cannot
    distinguish a safe engine from a broken one.

    This strategy is handed the raw data deliberately, bypassing PriceView.
    """
    days = sessions(120)
    rng = random.Random(11)
    bars = {}
    price = 100.0
    for d in days:
        move = rng.choice([-0.03, 0.03])
        nxt = price * (1 + move)
        bars[d] = Bar(d, price, max(price, nxt) * 1.001, min(price, nxt) * 0.999, nxt)
        price = nxt
    data = {"ACME": bars}
    ordered = sorted(bars)

    def oracle(view: PriceView) -> dict[str, float]:
        i = ordered.index(view.as_of)
        if i + 2 >= len(ordered):
            return {}
        today_open = bars[ordered[i + 1]].open
        tomorrow_open = bars[ordered[i + 2]].open
        return {"ACME": 1.0} if tomorrow_open > today_open else {}

    cheating = run_backtest(data, days, oracle, config=EngineConfig(initial_capital=1_000_000.0))
    honest = run_backtest(
        data, days, lambda _view: {"ACME": 1.0}, config=EngineConfig(initial_capital=1_000_000.0)
    )
    assert cheating.final_equity > honest.final_equity * 1.5, (
        "perfect foresight barely beat buy-and-hold: the engine is not acting on signals"
    )


# ==========================================================================
# 2. COSTS MUST ACTUALLY BE DEDUCTED
# ==========================================================================


def test_a_pointless_round_trip_loses_exactly_the_charges() -> None:
    """The rupee-exact test.

    Prices never move. One buy, one sell. Final equity must equal the initial
    capital minus precisely the charges the cost model says were incurred --
    not approximately, not within a percent.
    """
    days = sessions(6)
    data = flat_series("ACME", days, 100.0)
    cfg = EngineConfig(initial_capital=100_000.0, minimum_trade_value=0.0)

    def in_then_out(view: PriceView) -> dict[str, float]:
        return {"ACME": 1.0} if view.as_of == days[0] else {}

    result = run_backtest(data, days, in_then_out, config=cfg)

    assert len(result.fills) == 2
    buy, sell = result.fills
    assert buy.side is Side.BUY and sell.side is Side.SELL
    assert buy.quantity == sell.quantity, "sold a different quantity than was bought"

    expected = cfg.initial_capital - buy.charges.total - sell.charges.total
    assert result.final_equity == pytest.approx(expected, abs=0.01)
    assert result.total_charges > 0, "a round trip cost nothing: charges are not being applied"


def test_charges_match_an_independent_calculation() -> None:
    """Cross-check the engine's charges against the cost model called directly.

    Guards against the engine charging the wrong side, date or turnover.
    """
    days = sessions(6)
    data = flat_series("ACME", days, 250.0)
    cfg = EngineConfig(initial_capital=100_000.0, minimum_trade_value=0.0)

    result = run_backtest(
        data, days, lambda view: {"ACME": 1.0} if view.as_of == days[0] else {}, config=cfg
    )
    buy, sell = result.fills
    independent_buy = charges_for(buy.turnover, Side.BUY, buy.date)
    independent_sell = charges_for(sell.turnover, Side.SELL, sell.date)

    assert buy.charges.total == pytest.approx(independent_buy.total, abs=1e-6)
    assert sell.charges.total == pytest.approx(independent_sell.total, abs=1e-6)
    # Stamp duty is buy-only; DP charge is sell-only. Getting these backwards
    # is a classic error that barely changes the total.
    assert buy.charges.stamp_duty > 0 and sell.charges.stamp_duty == 0
    assert sell.charges.dp_charge > 0 and buy.charges.dp_charge == 0


def test_charges_match_absolute_hand_calculated_values() -> None:
    """Anchor the charges to externally-known rupee amounts.

    Regression test, added after mutation testing.
    ``test_charges_match_an_independent_calculation`` compares the engine's
    charges to ``charges_for``. That catches the engine mis-calling the cost
    model -- but it is blind to a bug *inside* the cost model, because both
    sides of the comparison move together. A mutation charging STT on the buy
    leg only passed the entire suite.

    The fix is an assertion that does not consult the code under test at all.
    These figures come from the hand-worked examples in the feasibility
    research, computed before this engine existed.
    """
    when = dt.date(2026, 8, 10)

    buy = charges_for(100_000.0, Side.BUY, when)
    sell = charges_for(100_000.0, Side.SELL, when)

    # STT is 0.1% on BOTH legs for delivery equity. Charging it on one side
    # halves it, which is a plausible bug and a large error.
    assert buy.stt == pytest.approx(100.0, abs=0.01), "STT must be 0.1% on the buy leg"
    assert sell.stt == pytest.approx(100.0, abs=0.01), "STT must be 0.1% on the sell leg too"
    assert buy.stt == pytest.approx(sell.stt, abs=0.01)

    # Stamp duty 0.015%, buy only. DP charge flat, sell only.
    assert buy.stamp_duty == pytest.approx(15.0, abs=0.01)
    assert sell.stamp_duty == 0.0
    assert sell.dp_charge == pytest.approx(20.0, abs=0.01)
    assert buy.dp_charge == 0.0

    # Totals, to the paisa.
    assert buy.total == pytest.approx(142.34, abs=0.01)
    assert sell.total == pytest.approx(150.94, abs=0.01)

    # The Rs 30,000 case worked through in the research document.
    assert charges_for(30_000.0, Side.BUY, when).total == pytest.approx(59.22, abs=0.01)
    assert charges_for(30_000.0, Side.SELL, when).total == pytest.approx(78.32, abs=0.01)


def test_more_churn_costs_strictly_more() -> None:
    """Charge more for more trading.

    A flat market with more round trips must end strictly poorer.
    """
    days = sessions(40)
    data = flat_series("ACME", days, 100.0)
    cfg = EngineConfig(initial_capital=200_000.0, minimum_trade_value=0.0)
    outcomes = []
    ordered = sorted(data["ACME"])
    for period in (20, 8, 2):

        def churn(view: PriceView, p: int = period, o: list[dt.date] = ordered) -> dict[str, float]:
            return {"ACME": 1.0} if (o.index(view.as_of) // p) % 2 == 0 else {}

        r = run_backtest(data, days, churn, config=cfg)
        outcomes.append((len(r.fills), r.final_equity))

    for i in range(len(outcomes) - 1):
        assert outcomes[i][0] < outcomes[i + 1][0], "expected more fills with shorter periods"
        assert outcomes[i][1] > outcomes[i + 1][1], "more trading did not cost more"


def test_holding_nothing_costs_nothing() -> None:
    """Apply the null control: no trades, no charges, capital preserved."""
    days = sessions(30)
    data = flat_series("ACME", days, 100.0)
    cfg = EngineConfig(initial_capital=50_000.0)
    result = run_backtest(data, days, lambda _view: {}, config=cfg)
    assert result.fills == []
    assert result.total_charges == 0.0
    assert result.final_equity == pytest.approx(50_000.0, abs=1e-9)


# ==========================================================================
# 3. EXECUTION MUST LAG THE DECISION
# ==========================================================================


def test_fill_happens_at_the_next_open_not_todays_close() -> None:
    """Constructed so all three candidate prices differ sharply.

    Day 0 closes at 100. Day 1 **opens at 150 and closes at 300**. A strategy
    deciding from day 0's close must pay 150 -- not 100 (filling on the bar it
    decided from) and not 300 (filling at the next close, which is a whole
    session of hindsight). Three distinct numbers, so the assertion can tell
    all three cases apart.
    """
    days = sessions(4)
    bars = {
        days[0]: Bar(days[0], 100.0, 100.0, 100.0, 100.0),
        days[1]: Bar(days[1], 150.0, 300.0, 150.0, 300.0),
        days[2]: Bar(days[2], 300.0, 300.0, 300.0, 300.0),
        days[3]: Bar(days[3], 300.0, 300.0, 300.0, 300.0),
    }
    data = {"GAP": bars}
    result = run_backtest(
        data,
        days,
        lambda _view: {"GAP": 1.0},
        config=EngineConfig(initial_capital=150_000.0, minimum_trade_value=0.0),
    )
    assert result.fills, "no fill occurred"
    first = result.fills[0]
    assert first.date == days[1], (
        f"filled on {first.date}, expected {days[1]}: a decision taken from the "
        f"close of {days[0]} cannot transact on {days[0]}"
    )
    assert first.price == 150.0, (
        f"filled at {first.price}, expected 150.0 (the next open). "
        f"100.0 would mean filling on the bar the decision was made from; "
        f"300.0 would mean filling at the next close. Both are look-ahead, "
        f"and both are profitable, which is why they survive unnoticed."
    )


def test_the_final_session_cannot_trade() -> None:
    """Refuse to fill a decision made on the final session.

    There is no next open, so filling it at the last close is look-ahead.
    """
    days = sessions(5)
    data = flat_series("ACME", days, 100.0)
    result = run_backtest(
        data,
        days,
        lambda _view: {"ACME": 1.0},
        config=EngineConfig(initial_capital=100_000.0, minimum_trade_value=0.0),
    )
    assert all(f.date != days[-1] for f in result.fills)


# ==========================================================================
# 4. THE ARITHMETIC MUST RECONCILE
# ==========================================================================


def test_hand_calculated_five_day_run_reconciles_to_the_rupee() -> None:
    """Worked out by hand, independently of the engine.

    Capital 100,000. ACME opens at 200. The naive answer is 500 shares, and it
    is wrong: 500 x 200 is the entire 100,000, leaving nothing for the charges.
    A real account cannot do that. The engine must trim to **499 shares**
    (99,800 turnover), leaving 200 minus charges in cash.

    That off-by-one is the whole value of hand-checking. An engine that
    silently bought 500 would be running a small overdraft on every entry, and
    would report a slightly better return than any real account could achieve
    -- invisible in aggregate, and wrong in the flattering direction.

    Sell 499 at 220 on day 3 = 109,780 turnover.
    """
    days = sessions(5)
    bars = {
        days[0]: Bar(days[0], 200.0, 200.0, 200.0, 200.0),
        days[1]: Bar(days[1], 200.0, 200.0, 200.0, 200.0),
        days[2]: Bar(days[2], 220.0, 220.0, 220.0, 220.0),
        days[3]: Bar(days[3], 220.0, 220.0, 220.0, 220.0),
        days[4]: Bar(days[4], 220.0, 220.0, 220.0, 220.0),
    }
    data = {"ACME": bars}
    cfg = EngineConfig(initial_capital=100_000.0, minimum_trade_value=0.0)

    def strat(view: PriceView) -> dict[str, float]:
        return {"ACME": 1.0} if view.as_of == days[0] else {}

    result = run_backtest(data, days, strat, config=cfg)

    buy, sell = result.fills
    assert buy.date == days[1] and buy.quantity == 499 and buy.price == 200.0
    assert sell.date == days[2] and sell.quantity == 499 and sell.price == 220.0
    assert buy.turnover == pytest.approx(99_800.0)
    assert sell.turnover == pytest.approx(109_780.0)

    buy_charges = charges_for(99_800.0, Side.BUY, days[1]).total
    sell_charges = charges_for(109_780.0, Side.SELL, days[2]).total
    expected = 100_000.0 - 99_800.0 - buy_charges + 109_780.0 - sell_charges

    assert result.final_equity == pytest.approx(expected, abs=0.01)
    # Gross gain on the shares actually held is 499 x 20 = 9,980. Net must be
    # exactly that, less both legs of charges. Not approximately.
    assert result.final_equity - 100_000.0 == pytest.approx(
        9_980.0 - buy_charges - sell_charges, abs=0.01
    )
    # And the engine must never have overdrawn on the way through.
    assert min(result.cash) >= -0.01


def test_equity_equals_cash_plus_positions_every_single_day() -> None:
    """Hold the accounting identity every day.

    If it breaks, money is being created or destroyed in the fill path.
    """
    days = sessions(60)
    rng = random.Random(3)
    data = {}
    for sym in ("AAA", "BBB", "CCC"):
        price = rng.uniform(50, 500)
        bars = {}
        for d in days:
            nxt = price * (1 + rng.gauss(0, 0.02))
            bars[d] = Bar(d, price, max(price, nxt) * 1.01, min(price, nxt) * 0.99, nxt)
            price = nxt
        data[sym] = bars

    def rotate(view: PriceView) -> dict[str, float]:
        i = days.index(view.as_of)
        picks = [("AAA", "BBB"), ("BBB", "CCC"), ("CCC", "AAA")][i % 3]
        return {picks[0]: 0.5, picks[1]: 0.5}

    result = run_backtest(data, days, rotate, config=EngineConfig(initial_capital=500_000.0))

    assert len(result.equity) == len(days)
    assert all(e > 0 for e in result.equity), "equity went non-positive without leverage"
    for i, (eq, csh) in enumerate(zip(result.equity, result.cash, strict=True)):
        assert csh >= -0.01, f"cash went negative on {days[i]}: that is undeclared leverage"
        assert eq >= csh - 0.01


def test_charges_by_component_sums_to_total_charges() -> None:
    days = sessions(30)
    data = flat_series("ACME", days, 100.0)
    ordered = sorted(data["ACME"])
    result = run_backtest(
        data,
        days,
        lambda view: {"ACME": 1.0} if ordered.index(view.as_of) % 4 < 2 else {},
        config=EngineConfig(initial_capital=100_000.0, minimum_trade_value=0.0),
    )
    assert result.fills
    assert sum(result.charges_by_component().values()) == pytest.approx(
        result.total_charges, abs=1e-6
    )


# ==========================================================================
# 5. CONSTRAINTS DECLARED IN THE CHARTER MUST BE ENFORCED
# ==========================================================================


def test_a_hole_in_the_session_calendar_is_refused() -> None:
    """Regression test, from a real defect in this project's own archive.

    2025 was entirely absent from the bhavcopy directory. The engine ran
    happily across the 366-day hole, held positions through it, and booked the
    whole year as one session's return -- which annualisation then treated as a
    single day. Measured Sharpe went from 0.817 to 0.961 on missing files
    alone. The equity curve looked completely ordinary.
    """
    days = [START + dt.timedelta(days=i) for i in range(5)]
    days += [START + dt.timedelta(days=400 + i) for i in range(5)]
    data = {"ACME": {d: Bar(d, 100.0, 100.0, 100.0, 100.0) for d in days}}

    with pytest.raises(ValueError, match="gap"):
        run_backtest(data, days, lambda _view: {"ACME": 1.0})


def test_a_genuine_closure_can_be_allowed_explicitly() -> None:
    """Allow a genuine closure to be waived explicitly.

    The guard must be overridable or it would block legitimate work, but only
    deliberately, never by default.
    """
    days = [START + dt.timedelta(days=i) for i in range(5)]
    days += [START + dt.timedelta(days=400 + i) for i in range(5)]
    data = {"ACME": {d: Bar(d, 100.0, 100.0, 100.0, 100.0) for d in days}}

    result = run_backtest(
        data,
        days,
        lambda _view: {"ACME": 1.0},
        config=EngineConfig(initial_capital=100_000.0, max_session_gap_days=None),
    )
    assert len(result.equity) == len(days)


def test_ordinary_weekends_and_holidays_do_not_trip_the_guard() -> None:
    """A ten-day default must tolerate a long weekend plus a festival."""
    days = [START + dt.timedelta(days=i) for i in range(20)]
    days = [d for d in days if d.weekday() < 5]
    days = [d for d in days if d != days[6]]  # drop a holiday mid-run
    data = {"ACME": {d: Bar(d, 100.0, 100.0, 100.0, 100.0) for d in days}}
    result = run_backtest(
        data, days, lambda _view: {"ACME": 1.0}, config=EngineConfig(initial_capital=100_000.0)
    )
    assert len(result.equity) == len(days)


def test_leverage_is_refused() -> None:
    days = sessions(5)
    data = flat_series("ACME", days, 100.0)
    with pytest.raises(ValueError, match="no leverage"):
        run_backtest(data, days, lambda _view: {"ACME": 1.6})


def test_shorting_is_refused() -> None:
    days = sessions(5)
    data = {**flat_series("ACME", days, 100.0), **flat_series("BETA", days, 100.0)}
    with pytest.raises(ValueError, match="no shorting"):
        run_backtest(data, days, lambda _view: {"ACME": 1.0, "BETA": -0.5})


def test_buy_and_hold_tracks_the_price_almost_exactly() -> None:
    """Anchor on buy-and-hold: one buy, then nothing.

    The book must track the security's return, short only the entry charges
    and the cash left by whole-share rounding.
    """
    days = sessions(100)
    data = trending("ACME", days, 100.0, 0.002)
    cfg = EngineConfig(initial_capital=500_000.0)
    result = run_backtest(data, days, lambda _view: {"ACME": 1.0}, config=cfg)

    bars = data["ACME"]
    entry = bars[days[1]].open
    exit_price = bars[days[-1]].close
    gross = exit_price / entry - 1
    net = result.final_equity / cfg.initial_capital - 1

    assert net < gross, "net return matched gross: charges vanished"
    assert net > gross - 0.01, f"net {net:.4%} vs gross {gross:.4%}: drag is implausibly large"
    assert len([f for f in result.fills if f.side is Side.SELL]) == 0
