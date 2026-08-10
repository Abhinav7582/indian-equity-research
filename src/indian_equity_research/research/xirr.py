"""Money-weighted return (XIRR) for irregular cash flows.

Why this exists
---------------
Time-weighted return answers "how did the strategy perform?".  Money-weighted
return answers "how did *this investor's money* perform?".  They differ whenever
capital is added or removed, which for a real portfolio is always.

A backtest reports time-weighted returns because it assumes a single lump sum.
A live portfolio funded by monthly contributions has a different experience: a
strategy can have an excellent time-weighted record while the investor's actual
money, arriving mostly near the top, earns far less.  Reporting only the
time-weighted number is one of the more comfortable ways to mislead yourself.

Conventions
-----------
Cash flows are signed **from the investor's point of view**:

* negative -- money leaving the investor (a purchase, a contribution)
* positive -- money returning to the investor (a sale, a dividend, and the
  closing market value, which is treated as a final notional withdrawal)

Solver
------
Newton-Raphson is the usual choice and is fast, but it can diverge on the
irregular sign patterns real portfolios produce.  This module brackets the root
first and finishes with bisection, which cannot diverge.  Slower, and it does
not matter: a portfolio has thousands of cash flows, not billions.

Every failure raises.  A wrong rate returned silently is worse than no rate.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

__all__ = [
    "CashFlow",
    "XirrError",
    "npv",
    "xirr",
]

DAYS_PER_YEAR: Final = 365.0

# A rate below -100% would mean losing more than everything, which the
# discounting formula cannot represent: (1 + r) must stay positive.
_MIN_RATE: Final = -0.999999999999
_MAX_RATE: Final = 1e6
# Relative, not absolute. An absolute rupee tolerance is meaningless when the
# flows may be hundreds or millions of rupees: 1e-10 is unreachable in float64
# for lakh-sized flows, and far looser than necessary for small ones.
_NPV_RELATIVE_TOLERANCE: Final = 1e-12
_RATE_TOLERANCE: Final = 1e-12
_MAX_ITERATIONS: Final = 400


class XirrError(ValueError):
    """Raised when no money-weighted rate can be determined."""


@dataclass(frozen=True, slots=True)
class CashFlow:
    """A single dated cash flow, signed from the investor's point of view."""

    date: dt.date
    amount: float

    def __post_init__(self) -> None:
        """Reject values that would silently corrupt a rate calculation."""
        if not isinstance(self.date, dt.date):
            raise TypeError(f"date must be a datetime.date, got {type(self.date)!r}")
        if self.amount != self.amount:  # NaN
            raise ValueError("amount must not be NaN")


def npv(rate: float, flows: Sequence[CashFlow], *, base: dt.date | None = None) -> float:
    """Net present value of ``flows`` discounted at ``rate`` (annual, decimal).

    ``base`` defaults to the earliest cash flow date.
    """
    if not flows:
        raise XirrError("no cash flows supplied")
    if rate <= _MIN_RATE:
        raise XirrError(f"rate {rate} implies a non-positive discount factor")

    origin = base if base is not None else min(f.date for f in flows)
    total = 0.0
    for flow in flows:
        years = (flow.date - origin).days / DAYS_PER_YEAR
        total += flow.amount / (1.0 + rate) ** years
    return total


def xirr(flows: Iterable[CashFlow]) -> float:
    """Annualised money-weighted return implied by ``flows``.

    Returns a decimal rate: ``0.1242`` means 12.42% per annum.

    Raises:
        XirrError: if there are fewer than two flows, if all flows share one
            sign (no rate can make them balance), if every flow falls on the
            same date, or if no root can be bracketed.
    """
    ordered = sorted(flows, key=lambda f: f.date)
    if len(ordered) < 2:
        raise XirrError("at least two cash flows are required")

    if not (any(f.amount > 0 for f in ordered) and any(f.amount < 0 for f in ordered)):
        raise XirrError(
            "cash flows must contain both positive and negative amounts; "
            "a series that only ever pays in, or only ever pays out, has no rate of return"
        )

    origin = ordered[0].date
    if all(f.date == origin for f in ordered):
        raise XirrError("all cash flows fall on the same date; no time has elapsed")

    def f(rate: float) -> float:
        return npv(rate, ordered, base=origin)

    # Scale the NPV tolerance to the size of the cash flows, so that "close
    # enough to zero" means the same thing for a 10,000 portfolio and a
    # 10,000,000 one.
    scale = sum(abs(flow.amount) for flow in ordered)
    npv_tolerance = max(_NPV_RELATIVE_TOLERANCE * scale, 1e-9)

    lo, hi = _bracket(f)
    if lo == hi:
        return lo

    f_lo = f(lo)
    for _ in range(_MAX_ITERATIONS):
        mid = (lo + hi) / 2.0
        f_mid = f(mid)
        if abs(f_mid) < npv_tolerance or (hi - lo) < _RATE_TOLERANCE * max(1.0, abs(mid)):
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    raise XirrError(
        f"bisection did not converge within {_MAX_ITERATIONS} iterations "
        f"(final bracket [{lo}, {hi}])"
    )


def _bracket(f) -> tuple[float, float]:  # type: ignore[no-untyped-def]
    """Find two rates whose NPVs have opposite signs.

    Expands outward from 0% rather than assuming a plausible range. A portfolio
    that lost 95% of its value in three months has a real, very negative rate,
    and refusing to represent it would be its own kind of dishonesty.

    The two directions need different search patterns, which is easy to get
    wrong. Upward the domain is unbounded, so doubling works. Downward the
    domain is bounded at -100%, and doubling stops dead at -80% -- it can never
    reach a rate like -99.999%, which is exactly what a near-total loss implies.
    Below -80% the search therefore closes on -1 geometrically instead.
    """
    candidates = [0.0]

    step = 0.05
    while step <= _MAX_RATE:
        candidates.append(step)
        step *= 2.0

    step = 0.05
    while step < 0.8:
        candidates.append(-step)
        step *= 2.0

    gap = 0.2
    while True:
        rate = -(1.0 - gap)
        if rate <= _MIN_RATE:
            break
        candidates.append(rate)
        gap /= 10.0

    previous: tuple[float, float] | None = None
    for rate in sorted(candidates):
        if rate <= _MIN_RATE:
            continue
        try:
            value = f(rate)
        except (OverflowError, ZeroDivisionError, XirrError):
            continue
        if value == 0.0:
            return rate, rate
        if previous is not None and (previous[1] > 0) != (value > 0):
            return previous[0], rate
        previous = (rate, value)

    raise XirrError(
        "could not bracket a root: the net present value never changes sign. "
        "This usually means the cash flows are degenerate (for example a tiny "
        "closing value against very large contributions)."
    )
