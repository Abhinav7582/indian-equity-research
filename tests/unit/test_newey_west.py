"""Tests for the HAC mean test.

The test that justifies the correction is
:func:`test_positive_autocorrelation_shrinks_the_t_statistic`. Without it, H1
and H2 would reject on a t-statistic that positive autocorrelation had inflated
-- the direction that manufactures significance.
"""

from __future__ import annotations

import random

import pytest

from indian_equity_research.backtest.gates import (
    GateError,
    newey_west_lag,
    newey_west_mean_test,
)


def ar1(n: int, phi: float, mean: float, *, seed: int = 7) -> list[float]:
    """An AR(1) series with a known mean and autocorrelation ``phi``."""
    rng = random.Random(seed)
    out: list[float] = []
    value = 0.0
    for _ in range(n):
        value = phi * value + rng.gauss(0.0, 1.0)
        out.append(mean + value)
    return out


def test_positive_autocorrelation_shrinks_the_t_statistic() -> None:
    """The whole reason the correction exists.

    A momentum book holds many of the same names month to month, so consecutive
    returns share exposure and repeat themselves. The ordinary standard error
    assumes they do not, comes out too small, and the t-statistic too large.

    On a strongly autocorrelated series the naive t must exceed the corrected
    one substantially.
    """
    series = ar1(400, phi=0.7, mean=0.35)
    result = newey_west_mean_test(series)

    assert abs(result.naive_t_statistic) > abs(result.t_statistic)
    assert result.inflation > 1.5


def test_an_independent_series_is_barely_adjusted() -> None:
    """The correction must not penalise a series that does not need it.

    With no autocorrelation the HAC and ordinary errors should agree closely;
    a large adjustment here would mean the estimator was adding noise.
    """
    series = ar1(400, phi=0.0, mean=0.2)
    result = newey_west_mean_test(series)
    assert result.inflation == pytest.approx(1.0, abs=0.25)


def test_negative_autocorrelation_can_widen_the_t_statistic() -> None:
    """The adjustment runs both ways, and is not a safety margin.

    A mean-reverting series repeats itself less than independence assumes, so
    the honest standard error is *smaller*. Treating Newey-West as a haircut
    would be wrong in this direction, and would hide a real effect.
    """
    series = ar1(400, phi=-0.6, mean=0.3)
    result = newey_west_mean_test(series)
    assert abs(result.t_statistic) > abs(result.naive_t_statistic)


def test_the_mean_is_unchanged_by_the_correction() -> None:
    """Newey-West adjusts the standard error, never the estimate."""
    series = ar1(120, phi=0.5, mean=1.25)
    result = newey_west_mean_test(series)
    assert result.mean == pytest.approx(sum(series) / len(series))


def test_order_matters() -> None:
    """Shuffling destroys exactly what this measures.

    If the statistic were invariant to order it would not be measuring
    autocorrelation at all -- which is a way this could look implemented and
    do nothing.
    """
    series = ar1(300, phi=0.8, mean=0.4)
    shuffled = list(series)
    random.Random(1).shuffle(shuffled)
    assert newey_west_mean_test(series).t_statistic != pytest.approx(
        newey_west_mean_test(shuffled).t_statistic
    )


def test_the_lag_comes_from_a_published_rule() -> None:
    """Newey & West (1994), ``floor(4 (T/100)^(2/9))``.

    Chosen by rule rather than by hand: picking the lag that made a t look best
    would be a trial per lag, and an undisclosed one.
    """
    assert newey_west_lag(100) == 4
    assert newey_west_lag(84) == 3
    assert newey_west_lag(1) == 0
    assert newey_west_lag(3) >= 1


def test_a_constant_series_is_refused() -> None:
    """A constant has no standard error, and is not evidence."""
    with pytest.raises(GateError, match="not evidence"):
        newey_west_mean_test([0.4] * 50)


def test_too_few_observations_is_refused() -> None:
    with pytest.raises(GateError, match="at least 3"):
        newey_west_mean_test([0.1, 0.2])


def test_a_zero_mean_series_gives_a_zero_t() -> None:
    """The null must be reachable, or the test cannot fail."""
    series = [1.0, -1.0] * 60
    result = newey_west_mean_test(series)
    assert result.mean == pytest.approx(0.0)
    assert result.t_statistic == pytest.approx(0.0)
