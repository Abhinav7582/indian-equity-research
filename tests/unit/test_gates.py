"""Tests for the statistical gates.

The gates exist to reject flattering results. So the tests that matter most are
the ones proving they actually reject: a pure-noise strategy dressed up with
enough trials must fail, and a selection procedure with no skill must show a
PBO near one half.
"""

from __future__ import annotations

import math
import random

import pytest

from indian_equity_research.backtest.gates import (
    GateError,
    deflated_sharpe_ratio,
    expected_maximum_sharpe,
    probability_of_backtest_overfitting,
    sharpe_ratio,
)


def noise(n: int, seed: int, mu: float = 0.0, sigma: float = 0.01) -> list[float]:
    rng = random.Random(seed)
    return [rng.gauss(mu, sigma) for _ in range(n)]


# --------------------------------------------------------------------------
# Sharpe ratio
# --------------------------------------------------------------------------


def test_sharpe_of_a_known_series() -> None:
    """Mean 0.001, sd 0.01 daily => 0.1 per period => 0.1 * sqrt(252) annual."""
    returns = [0.001 + 0.01 * v for v in (1, -1) * 126]
    s = sharpe_ratio(returns)
    assert s == pytest.approx(0.1 * math.sqrt(252), rel=0.02)


def test_sharpe_scales_with_the_annualisation_factor() -> None:
    r = noise(500, seed=1, mu=0.0005)
    daily = sharpe_ratio(r, periods_per_year=252)
    monthly = sharpe_ratio(r, periods_per_year=12)
    assert daily == pytest.approx(monthly * math.sqrt(252 / 12), rel=1e-9)


def test_zero_variance_raises_rather_than_returning_infinity() -> None:
    with pytest.raises(GateError, match="zero variance"):
        sharpe_ratio([0.001] * 50)


def test_too_few_returns_raises() -> None:
    with pytest.raises(GateError, match="at least 2"):
        sharpe_ratio([0.01])


# --------------------------------------------------------------------------
# Expected maximum Sharpe: the multiple-testing benchmark
# --------------------------------------------------------------------------


def test_one_trial_has_no_selection_bias() -> None:
    assert expected_maximum_sharpe(1, 1.0) == 0.0


def test_benchmark_rises_with_the_number_of_trials() -> None:
    """The core property. Trying more configurations raises the bar."""
    values = [expected_maximum_sharpe(n, 1.0) for n in (2, 5, 20, 100, 1000)]
    assert values == sorted(values)
    assert values[0] > 0
    assert values[-1] > values[0] * 2


def test_benchmark_scales_with_dispersion() -> None:
    assert expected_maximum_sharpe(50, 4.0) == pytest.approx(
        2 * expected_maximum_sharpe(50, 1.0), rel=1e-9
    )


def test_invalid_trial_counts_raise() -> None:
    with pytest.raises(GateError, match="at least 1"):
        expected_maximum_sharpe(0, 1.0)


# --------------------------------------------------------------------------
# Deflated Sharpe: the gate must actually reject
# --------------------------------------------------------------------------


def test_pure_noise_after_many_trials_is_rejected() -> None:
    """The test that justifies the module.

    A strategy with no edge, selected as the best of 200 attempts, must not
    pass. If it does, the gate is decoration.
    """
    result = deflated_sharpe_ratio(noise(1000, seed=7), trials=200)
    assert not result.passes
    assert "FAILS" in result.explain()


def test_the_same_result_looks_better_when_trials_are_understated() -> None:
    """Demonstrates why the trial register must be honest.

    Identical returns, different declared trial counts. Understating trials is
    undetectable from the output, which is exactly why it is governed by
    HYPOTHESES.md rather than by this code.
    """
    returns = noise(2000, seed=3, mu=0.0009)
    honest = deflated_sharpe_ratio(returns, trials=500)
    understated = deflated_sharpe_ratio(returns, trials=1)
    assert understated.deflated_probability > honest.deflated_probability
    assert understated.benchmark_sharpe < honest.benchmark_sharpe


def test_a_genuinely_strong_result_survives_a_single_trial() -> None:
    """The gate must not reject everything, or it would be useless."""
    result = deflated_sharpe_ratio(noise(2000, seed=5, mu=0.0012), trials=1)
    assert result.passes
    assert "SURVIVES" in result.explain()


def test_more_trials_monotonically_reduce_the_probability() -> None:
    returns = noise(1500, seed=11, mu=0.0008)
    probs = [deflated_sharpe_ratio(returns, trials=t).deflated_probability for t in (1, 10, 100)]
    assert probs == sorted(probs, reverse=True)


def test_negative_skew_is_penalised() -> None:
    """Penalise negative skew.

    A strategy that grinds out gains and loses badly must score worse than a
    symmetric one with the same mean and variance. This is the profile of
    selling insurance: excellent right up until it is not.
    """
    rng = random.Random(21)
    symmetric = [rng.gauss(0.0008, 0.01) for _ in range(1500)]
    skewed = list(symmetric)
    # Move mass from many small gains into a few large losses, holding the sum
    # approximately constant.
    for i in range(0, 1500, 150):
        skewed[i] -= 0.09
    for i in range(1500):
        skewed[i] += 0.09 * 10 / 1500

    a = deflated_sharpe_ratio(symmetric, trials=1)
    b = deflated_sharpe_ratio(skewed, trials=1)
    assert b.skewness < a.skewness
    assert b.deflated_probability < a.deflated_probability


def test_degenerate_inputs_raise() -> None:
    with pytest.raises(GateError, match="at least 4 observations"):
        deflated_sharpe_ratio([0.01, 0.02], trials=1)
    with pytest.raises(GateError, match="at least 1"):
        deflated_sharpe_ratio(noise(100, seed=1), trials=0)


# --------------------------------------------------------------------------
# Probability of backtest overfitting
# --------------------------------------------------------------------------


def test_selecting_among_pure_noise_gives_pbo_near_one_half() -> None:
    """The defining case.

    Twenty configurations, none with any edge. Whichever looks best in-sample
    should land in the bottom half out-of-sample roughly half the time. A PBO
    far from 0.5 here would mean the procedure itself is broken.
    """
    configs = [noise(1200, seed=100 + i) for i in range(20)]
    result = probability_of_backtest_overfitting(configs, splits=12)
    assert 0.25 < result.probability < 0.75
    assert result.splits_evaluated > 0


def test_a_genuinely_superior_configuration_is_detected() -> None:
    """Detect a genuinely superior configuration.

    One configuration has a real edge; the procedure should find it
    consistently, giving a low PBO.
    """
    configs = [noise(1200, seed=200 + i) for i in range(9)]
    configs.append(noise(1200, seed=999, mu=0.0025))
    result = probability_of_backtest_overfitting(configs, splits=12)
    assert result.probability < 0.25
    assert result.passes
    assert "SURVIVES" in result.explain()


def test_one_configuration_cannot_be_assessed() -> None:
    with pytest.raises(GateError, match="at least 2 configurations"):
        probability_of_backtest_overfitting([noise(500, seed=1)])


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(GateError, match="same periods"):
        probability_of_backtest_overfitting([noise(500, seed=1), noise(400, seed=2)])


def test_too_short_for_the_requested_splits_raises() -> None:
    with pytest.raises(GateError, match="at least"):
        probability_of_backtest_overfitting([noise(10, seed=1), noise(10, seed=2)], splits=16)
