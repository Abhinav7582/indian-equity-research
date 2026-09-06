"""Tests for routing new money instead of rebalancing by selling.

The one that matters most is
:func:`test_the_shortfall_is_measured_against_the_post_contribution_total`.
Measuring against the pre-contribution total under-fills every bucket by a
little, every month, and the output looks entirely correct while doing it.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.drift import (
    Band,
    DriftError,
    DriftReport,
    TargetPolicy,
    measure_drift,
    route_contribution,
)

ON = dt.date(2026, 9, 6)


def policy(targets: dict[str, float] | None = None) -> TargetPolicy:
    return TargetPolicy(
        version=1,
        declared_on=dt.date(2026, 8, 31),
        targets=targets or {"Equity": 40.0, "Gold": 10.0, "Debt": 50.0},
        band=Band(absolute_pp=5.0, relative_pct=25.0),
        min_trade_rupees=25_000.0,
        max_cost_fraction=0.02,
    )


def report(holdings: dict[str, float]) -> DriftReport:
    return measure_drift(policy(), holdings, ON)


# ---------------------------------------------------------------------------
# The arithmetic that is easy to get subtly wrong
# ---------------------------------------------------------------------------


def test_the_shortfall_is_measured_against_the_post_contribution_total() -> None:
    """A bucket at 20% of 100 needs more than 5 to reach 25% of 105.

    Routing against the *pre*-contribution total under-fills every bucket by a
    little every month, and nothing in the output looks wrong while it happens.
    Here: Equity is 30,000 of 100,000 against a 40% target. Adding 20,000 makes
    the total 120,000, so the target is 48,000 and the true shortfall is 18,000
    — not the 10,000 a pre-contribution measurement would report.
    """
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 20_000.0)
    equity = next(s for s in plan.shares if s.name == "Equity")
    assert equity.gap_rupees_before == pytest.approx(18_000.0)


def test_a_contribution_reduces_total_deviation_from_target() -> None:
    """The whole book moves closer, which is not the same as every bucket doing so.

    A contribution smaller than the total shortfall **cannot** improve every
    bucket at once. Overweight Gold can only be corrected by dilution, and
    dilution comes out of everyone's share of a fixed pot — so a bucket sitting
    exactly at target can end slightly below it. Asserting per-bucket
    improvement is asking for something arithmetically impossible; total
    deviation is the property that actually holds.
    """
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 20_000.0)
    before = sum(abs(s.before_pct - s.target_pct) for s in plan.shares)
    after = sum(abs(s.after_pct - s.target_pct) for s in plan.shares)
    assert after < before


def test_a_bucket_exactly_at_target_still_has_a_shortfall() -> None:
    """Counter-intuitive, and the reason the post-contribution total is used.

    Debt is 50,000 of 100,000 against a 50% target — exactly on it. Add 20,000
    and the total becomes 120,000, so holding 50% now needs 60,000. Standing
    still requires 10,000 of new money; getting none would drop it to 41.7%.
    """
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 20_000.0)
    debt = next(s for s in plan.shares if s.name == "Debt")
    assert debt.before_pct == pytest.approx(50.0)
    assert debt.gap_rupees_before == pytest.approx(10_000.0)
    assert debt.amount > 0


def test_the_whole_contribution_is_allocated() -> None:
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 20_000.0)
    assert sum(s.amount for s in plan.shares) == pytest.approx(20_000.0)


def test_an_overweight_bucket_receives_nothing() -> None:
    """Money never goes to a bucket already above target — that is the point."""
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 5_000.0)
    gold = next(s for s in plan.shares if s.name == "Gold")
    assert gold.amount == 0.0
    assert gold.after_pct < gold.before_pct  # diluted by everyone else's growth


def test_gaps_close_at_the_same_rate_rather_than_one_at_a_time() -> None:
    """Proportional routing, not worst-gap-first.

    Predictable month to month: a small change in relative weight must not
    swing the entire contribution from one bucket to another.
    """
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 10_000.0)
    receiving = [s for s in plan.shares if s.amount > 0]
    assert len(receiving) >= 2
    closed = {round(s.closes, 9) for s in receiving}
    assert len(closed) == 1


def test_a_contribution_larger_than_every_gap_spreads_the_rest_by_target() -> None:
    """Overshooting one bucket to fill another would be worse than not routing."""
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 10_000_000.0)
    for share in plan.shares:
        assert share.after_pct == pytest.approx(share.target_pct, abs=0.2)


def test_with_nothing_underweight_the_split_holds_the_allocation_still() -> None:
    r = report({"Equity": 40_000.0, "Gold": 10_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 20_000.0)
    for share in plan.shares:
        assert share.after_pct == pytest.approx(share.target_pct)


def test_a_zero_contribution_allocates_nothing() -> None:
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 0.0)
    assert plan.receiving == ()
    assert sum(s.amount for s in plan.shares) == 0.0


def test_a_negative_contribution_is_refused() -> None:
    """This routes money in. A withdrawal would need selling, which it never does."""
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    with pytest.raises(DriftError, match="does not model a withdrawal"):
        route_contribution(r, -1_000.0)


# ---------------------------------------------------------------------------
# What it tells the owner
# ---------------------------------------------------------------------------


def test_months_to_target_scales_with_the_contribution() -> None:
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 5_000.0)
    equity = next(s for s in plan.shares if s.name == "Equity")
    assert equity.months_to_target(5_000.0) == pytest.approx(2 * equity.months_to_target(10_000.0))


def test_an_overweight_bucket_needs_no_months_and_closes_nothing() -> None:
    """An overweight bucket has no shortfall, so neither figure applies to it.

    Note this is *overweight*, not *at target*: a bucket exactly at target has
    a positive shortfall against the grown total, per the test above.
    """
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 1_000.0)
    gold = next(s for s in plan.shares if s.name == "Gold")
    assert gold.gap_rupees_before == 0.0
    assert gold.months_to_target(1_000.0) == 0.0
    assert gold.closes == 0.0


def test_no_output_names_an_action() -> None:
    """It states where money would go. It does not say to send it."""
    r = report({"Equity": 30_000.0, "Gold": 20_000.0, "Debt": 50_000.0})
    plan = route_contribution(r, 10_000.0)
    forbidden = {"recommendation", "verdict", "advice", "should_invest", "action"}
    assert not forbidden & set(dir(plan))
    assert not forbidden & set(dir(plan.shares[0]))
