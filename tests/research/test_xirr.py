"""Tests for the money-weighted return solver.

The cases below are hand-checkable. Where a case is not obvious by inspection,
the expected value is justified in a comment rather than copied from the
function's own output -- a test that asserts what the code already does proves
only that the code is deterministic.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.research.xirr import (
    CashFlow,
    XirrError,
    npv,
    xirr,
)


def d(iso: str) -> dt.date:
    return dt.date.fromisoformat(iso)


# --------------------------------------------------------------------------
# Known answers
# --------------------------------------------------------------------------


def test_doubling_in_exactly_one_year_is_100_percent() -> None:
    """Pay 100 today, receive 200 in 365 days: +100% by definition."""
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2024-12-31"), 200.0)]
    assert xirr(flows) == pytest.approx(1.0, abs=1e-6)


def test_flat_value_after_one_year_is_zero() -> None:
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2024-12-31"), 100.0)]
    assert xirr(flows) == pytest.approx(0.0, abs=1e-9)


def test_halving_in_one_year_is_minus_fifty_percent() -> None:
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2024-12-31"), 50.0)]
    assert xirr(flows) == pytest.approx(-0.5, abs=1e-6)


def test_doubling_over_two_years_is_root_two_minus_one() -> None:
    """Compound 2x over 2 years: sqrt(2) - 1 = 41.42%, not 50%."""
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2025-12-31"), 200.0)]
    assert xirr(flows) == pytest.approx(2**0.5 - 1, abs=1e-4)


def test_half_year_doubling_annualises_to_three_hundred_percent() -> None:
    """Compound 2x in half a year: 2^2 - 1 = 300% annualised."""
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2024-07-01"), 200.0)]
    assert xirr(flows) == pytest.approx(3.0, rel=1e-2)


def test_total_loss_approaches_minus_one_hundred_percent() -> None:
    """Represent a near-wipeout rather than rejecting it.

    Regression test. The first version of the bracketing search expanded the
    negative side by doubling (-0.05, -0.1, ... -0.8) and then stopped, because
    the next step would have fallen below -100%. It could therefore never reach
    the true root here, around -99.999%, and raised "could not bracket a root"
    on a perfectly ordinary total loss.
    """
    flows = [CashFlow(d("2024-01-01"), -100_000.0), CashFlow(d("2024-12-31"), 1.0)]
    assert xirr(flows) < -0.99


def test_severe_but_not_total_loss_is_bracketed() -> None:
    """Bracket -90%, which the old doubling search skipped."""
    flows = [CashFlow(d("2024-01-01"), -10_000.0), CashFlow(d("2024-12-31"), 1_000.0)]
    assert xirr(flows) == pytest.approx(-0.9, abs=1e-5)


def test_very_large_positive_rate_is_bracketed() -> None:
    """Bracket a 50x gain in one year, which is 4,900%."""
    flows = [CashFlow(d("2024-01-01"), -1_000.0), CashFlow(d("2024-12-31"), 50_000.0)]
    assert xirr(flows) == pytest.approx(49.0, rel=1e-3)


def test_lakh_scale_flows_still_converge() -> None:
    """Guard the scale-aware tolerance.

    An absolute 1e-10 NPV target is not reachable in float64 at this size.
    """
    flows = [
        CashFlow(d("2021-09-20"), -1_300_000.0),
        CashFlow(d("2026-08-10"), 1_555_570.0),
    ]
    rate = xirr(flows)
    scale = sum(abs(f.amount) for f in flows)
    assert npv(rate, flows) == pytest.approx(0.0, abs=1e-9 * scale)
    assert 0.03 < rate < 0.05


# --------------------------------------------------------------------------
# Properties that must hold
# --------------------------------------------------------------------------


def test_npv_at_the_solved_rate_is_zero() -> None:
    """Check the defining property of an internal rate of return."""
    flows = [
        CashFlow(d("2022-01-10"), -25_000.0),
        CashFlow(d("2022-06-15"), -15_000.0),
        CashFlow(d("2023-03-01"), 5_000.0),
        CashFlow(d("2024-02-20"), -8_000.0),
        CashFlow(d("2025-08-10"), 52_000.0),
    ]
    rate = xirr(flows)
    # Tolerance is relative to the size of the flows: an absolute rupee
    # tolerance is not meaningful across portfolios of different magnitudes.
    scale = sum(abs(f.amount) for f in flows)
    assert npv(rate, flows) == pytest.approx(0.0, abs=1e-9 * scale)


def test_scaling_all_flows_leaves_the_rate_unchanged() -> None:
    """Confirm a rate is a ratio: doubling every rupee must not move it."""
    base = [
        CashFlow(d("2021-04-01"), -10_000.0),
        CashFlow(d("2022-04-01"), -10_000.0),
        CashFlow(d("2026-08-10"), 31_000.0),
    ]
    scaled = [CashFlow(f.date, f.amount * 1_000) for f in base]
    assert xirr(base) == pytest.approx(xirr(scaled), abs=1e-9)


def test_order_of_input_does_not_matter() -> None:
    flows = [
        CashFlow(d("2024-03-01"), -5_000.0),
        CashFlow(d("2023-01-01"), -10_000.0),
        CashFlow(d("2026-01-01"), 20_000.0),
    ]
    assert xirr(flows) == pytest.approx(xirr(list(reversed(flows))), abs=1e-12)


def test_monthly_sip_into_a_flat_market_returns_about_zero() -> None:
    """A flat market earns nothing.

    36 monthly payments of 1,000 closing at exactly 36,000 means nothing was
    earned, regardless of when the money arrived.
    """
    flows = [CashFlow(d("2021-01-01") + dt.timedelta(days=30 * i), -1_000.0) for i in range(36)]
    flows.append(CashFlow(d("2021-01-01") + dt.timedelta(days=30 * 36), 36_000.0))
    assert xirr(flows) == pytest.approx(0.0, abs=1e-6)


def test_later_contributions_earn_less_so_lift_the_rate_less() -> None:
    """Later money must imply a higher rate.

    Same total paid in and same closing value, but money arriving later had
    less time to work, so the implied annual rate must be higher.
    """
    early = [
        CashFlow(d("2020-01-01"), -50_000.0),
        CashFlow(d("2020-02-01"), -50_000.0),
        CashFlow(d("2026-01-01"), 200_000.0),
    ]
    late = [
        CashFlow(d("2020-01-01"), -50_000.0),
        CashFlow(d("2025-02-01"), -50_000.0),
        CashFlow(d("2026-01-01"), 200_000.0),
    ]
    assert xirr(late) > xirr(early)


# --------------------------------------------------------------------------
# Failure modes -- these must raise, never return a plausible-looking number
# --------------------------------------------------------------------------


def test_all_negative_flows_raise() -> None:
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2025-01-01"), -100.0)]
    with pytest.raises(XirrError, match="both positive and negative"):
        xirr(flows)


def test_all_positive_flows_raise() -> None:
    flows = [CashFlow(d("2024-01-01"), 100.0), CashFlow(d("2025-01-01"), 100.0)]
    with pytest.raises(XirrError, match="both positive and negative"):
        xirr(flows)


def test_single_flow_raises() -> None:
    with pytest.raises(XirrError, match="at least two"):
        xirr([CashFlow(d("2024-01-01"), -100.0)])


def test_empty_raises() -> None:
    with pytest.raises(XirrError, match="at least two"):
        xirr([])


def test_same_day_flows_raise() -> None:
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2024-01-01"), 150.0)]
    with pytest.raises(XirrError, match="same date"):
        xirr(flows)


def test_nan_amount_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="NaN"):
        CashFlow(d("2024-01-01"), float("nan"))


def test_non_date_rejected_at_construction() -> None:
    with pytest.raises(TypeError, match=r"datetime\.date"):
        CashFlow("2024-01-01", -100.0)  # type: ignore[arg-type]


def test_npv_rejects_impossible_rate() -> None:
    flows = [CashFlow(d("2024-01-01"), -100.0), CashFlow(d("2025-01-01"), 150.0)]
    with pytest.raises(XirrError, match="non-positive discount factor"):
        npv(-1.5, flows)


def test_npv_rejects_empty() -> None:
    with pytest.raises(XirrError, match="no cash flows"):
        npv(0.1, [])
