"""Amendment A7's breadth budget, as an executable rule.

A7 caps the modelled cost of one full turnover at 1.00% of capital. A number
written only in a markdown file is a suggestion; written here it is a
constraint that fails a test run when it is breached.

Every figure below comes from the cost model validated against real contract
notes (`docs/cost_model_validation.md`), and reads no returns.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.costs import Side, charges_for

AS_OF = dt.date(2026, 8, 18)
BUDGET = 0.01  # Amendment A7
CAP = 300_000.0


def turnover_cost(capital: float, names: int, sell_orders: float = 1.0) -> float:
    """Cost of buying and selling every position once, as a fraction of capital."""
    position = capital / names
    buy = charges_for(position, Side.BUY, AS_OF)
    sell = charges_for(position, Side.SELL, AS_OF, sell_orders=sell_orders)
    return (buy.total + sell.total) * names / capital


@pytest.mark.parametrize(("names", "expected"), [(10, 0.00458), (15, 0.00576), (100, 0.01402)])
def test_the_frontier_is_what_amendment_a7_says_it_is(names: int, expected: float) -> None:
    """Pin the table in HYPOTHESES.md to the cost model that produced it."""
    assert turnover_cost(CAP, names) == pytest.approx(expected, abs=5e-5)


def test_one_hundred_names_at_three_lakh_breaches_the_budget() -> None:
    """The configuration A7 exists to rule out.

    1.402% for one full turnover. At monthly rebalancing that is 16.8% a year
    before a single rupee of alpha.
    """
    assert turnover_cost(CAP, 100) > BUDGET


def test_fifty_names_breaches_the_budget_once_exits_are_split() -> None:
    """0.852% at one order per exit, but 1.638% at three.

    A configuration that passes only under the optimistic execution assumption
    is not passing. This is why A7 requires the assumption to be reported.
    """
    assert turnover_cost(CAP, 50, sell_orders=1.0) < BUDGET
    assert turnover_cost(CAP, 50, sell_orders=3.0) > BUDGET


@pytest.mark.parametrize("names", [10, 15, 20])
def test_only_twenty_or_fewer_names_survive_pessimistic_execution(names: int) -> None:
    """The configurations A7 leaves available under a hostile assumption.

    This bound is tighter than it first appears. At one order per exit the
    budget permits up to 50 names (0.852%); at three it permits **20**. The
    difference is entirely execution, not strategy.
    """
    assert turnover_cost(CAP, names, sell_orders=3.0) < BUDGET


def test_thirty_names_survives_optimistically_and_fails_pessimistically() -> None:
    """The boundary case, and the reason A7 requires the assumption reported.

    0.694% at one order per exit; 1.166% at three. Reporting only the first
    would put a breaching configuration inside the budget on paper.
    """
    assert turnover_cost(CAP, 30, sell_orders=1.0) < BUDGET
    assert turnover_cost(CAP, 30, sell_orders=3.0) > BUDGET


def test_the_statutory_floor_is_the_same_at_every_breadth() -> None:
    """STT, stamp duty and exchange fees are proportional.

    0.222% is the cost no amount of portfolio construction can avoid, and any
    edge must clear it before anything else.
    """
    floors = []
    for names in (10, 50, 100):
        position = CAP / names
        buy = charges_for(position, Side.BUY, AS_OF)
        sell = charges_for(position, Side.SELL, AS_OF)
        fixed = (sell.dp_charge + buy.brokerage + sell.brokerage) * (1 + buy.gst_rate)
        floors.append((buy.total + sell.total - fixed) * names / CAP)
    assert floors[0] == pytest.approx(floors[1], abs=1e-6)
    assert floors[1] == pytest.approx(floors[2], abs=1e-6)
    assert floors[0] == pytest.approx(0.00222, abs=5e-5)


def test_breadth_is_bought_with_capital() -> None:
    """100 names at Rs 20L costs the same as 15 names at Rs 3L.

    The small-account problem is not that wide books are wrong. It is that
    they are unaffordable at this size.
    """
    assert turnover_cost(2_000_000.0, 100) == pytest.approx(turnover_cost(CAP, 15), abs=5e-5)
