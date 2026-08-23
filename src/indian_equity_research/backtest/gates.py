"""Statistical gates: what a backtest result must survive to mean anything.

The problem these solve
-----------------------
A Sharpe ratio computed from a backtest is not an estimate of future
performance. It is the **maximum** of however many configurations were tried,
and the maximum of a set of noisy numbers is biased upward by construction. Try
twenty random strategies on the same data and one will look excellent. Nothing
in the arithmetic of the Sharpe ratio warns you about this.

Two corrections are implemented here.

**Deflated Sharpe Ratio** (Bailey & López de Prado, 2014) asks: given that N
configurations were tried, how likely is an observed Sharpe this high purely by
chance? It also penalises skew and kurtosis, because a strategy that makes small
gains continually and loses catastrophically rarely has a flattering Sharpe
right up until it does not.

**Probability of Backtest Overfitting** (Bailey, Borwein, López de Prado &
Zhu, 2015) asks a different question: if the configuration that looked best
in-sample is run out-of-sample, how often does it land in the *bottom half*? A
PBO near 0.5 means the selection procedure has no skill -- the winner was chosen
by noise.

Why the trial register matters
------------------------------
``trials`` in :func:`deflated_sharpe_ratio` must be the **honest** count of every
configuration ever evaluated, including abandoned ones, including the ones that
looked bad and were quietly dropped. That is what ``HYPOTHESES.md``'s trial
register exists to record. Understating it is the easiest way to make a
worthless result pass, and it cannot be detected from the output.

References:
----------
Bailey, D. H., & López de Prado, M. (2014). The Deflated Sharpe Ratio.
*Journal of Portfolio Management*, 40(5).

Bailey, D. H., Borwein, J., López de Prado, M., & Zhu, Q. J. (2015). The
Probability of Backtest Overfitting. *Journal of Computational Finance*.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Final

__all__ = [
    "GateError",
    "MeanTest",
    "OverfittingResult",
    "SharpeAssessment",
    "deflated_sharpe_ratio",
    "expected_maximum_sharpe",
    "newey_west_lag",
    "newey_west_mean_test",
    "probability_of_backtest_overfitting",
    "sharpe_ratio",
]

_EULER_MASCHERONI: Final = 0.5772156649015329
_NORMAL: Final = NormalDist()


class GateError(ValueError):
    """Raised when a statistic cannot be computed honestly from the input."""


def sharpe_ratio(returns: list[float], *, periods_per_year: int = 252) -> float:
    """Annualised Sharpe ratio of a return series, excess of zero.

    A risk-free rate is not subtracted. In India that rate is 6-7%, which is
    large enough that omitting it flatters every strategy substantially -- so
    the caller must pass excess returns if they want a comparable figure. This
    function does not silently choose a rate on the caller's behalf.

    Raises:
        GateError: if fewer than two returns are supplied, or volatility is zero.
    """
    if len(returns) < 2:
        raise GateError(f"need at least 2 returns to compute a Sharpe ratio, got {len(returns)}")
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    # Not `variance <= 0`. Summing squared deviations of identical floats can
    # leave a residue around 1e-38, which is arithmetically positive and
    # financially meaningless -- and would produce a Sharpe in the billions.
    # Degeneracy has to be judged relative to the size of the numbers involved.
    if math.sqrt(variance) <= 1e-12 * max(1.0, abs(mean)):
        raise GateError(
            "return series has zero variance; a Sharpe ratio is undefined. "
            "This usually means the strategy never traded."
        )
    return (mean / math.sqrt(variance)) * math.sqrt(periods_per_year)


def _moments(returns: list[float]) -> tuple[float, float]:
    """Sample skewness and kurtosis (not excess) of a return series."""
    n = len(returns)
    mean = sum(returns) / n
    m2 = sum((r - mean) ** 2 for r in returns) / n
    if m2 <= 0:
        raise GateError("cannot compute higher moments of a constant series")
    m3 = sum((r - mean) ** 3 for r in returns) / n
    m4 = sum((r - mean) ** 4 for r in returns) / n
    return m3 / m2**1.5, m4 / m2**2


def expected_maximum_sharpe(trials: int, variance_across_trials: float) -> float:
    """Expected highest Sharpe from ``trials`` strategies with *no* real skill.

    This is the benchmark an observed Sharpe must beat. It rises with the
    number of trials, which is the whole point: finding a Sharpe of 1.5 after
    one attempt is interesting, and after two hundred attempts it is expected.

    Raises:
        GateError: if ``trials`` is below 1 or the variance is negative.
    """
    if trials < 1:
        raise GateError(f"trials must be at least 1, got {trials}")
    if variance_across_trials < 0:
        raise GateError(
            f"variance_across_trials must not be negative, got {variance_across_trials}"
        )
    if trials == 1:
        return 0.0
    sigma = math.sqrt(variance_across_trials)
    # Bailey & López de Prado's approximation to the expected maximum of N
    # independent standard normals.
    a = _NORMAL.inv_cdf(1 - 1 / trials)
    b = _NORMAL.inv_cdf(1 - 1 / (trials * math.e))
    return sigma * ((1 - _EULER_MASCHERONI) * a + _EULER_MASCHERONI * b)


@dataclass(frozen=True, slots=True)
class SharpeAssessment:
    """The verdict on an observed Sharpe ratio."""

    observed_sharpe: float
    benchmark_sharpe: float
    deflated_probability: float
    trials: int
    observations: int
    skewness: float
    kurtosis: float

    @property
    def passes(self) -> bool:
        """True if the result survives at the conventional 95% level."""
        return self.deflated_probability > 0.95

    def explain(self) -> str:
        """A sentence a human can check, rather than a number to be quoted."""
        verdict = "SURVIVES" if self.passes else "FAILS"
        return (
            f"{verdict}: observed Sharpe {self.observed_sharpe:.3f} over "
            f"{self.observations} observations, against a chance-expected maximum of "
            f"{self.benchmark_sharpe:.3f} from {self.trials} trial(s). "
            f"Probability it is not luck: {self.deflated_probability:.1%} "
            f"(threshold 95%). Skew {self.skewness:+.2f}, kurtosis {self.kurtosis:.2f}."
        )


def deflated_sharpe_ratio(
    returns: list[float],
    *,
    trials: int,
    variance_across_trials: float | None = None,
    periods_per_year: int = 252,
    benchmark_sharpe: float | None = None,
) -> SharpeAssessment:
    """Probability that an observed Sharpe reflects skill rather than selection.

    Args:
        returns: Per-period strategy returns. Excess of the risk-free rate if a
            comparable figure is wanted -- see :func:`sharpe_ratio`.
        trials: **Every** configuration evaluated, including abandoned ones.
            This is the trial register count. Understating it invalidates the
            result silently.
        variance_across_trials: Variance of Sharpe ratios across those trials.
            If unknown, a conservative default of 1.0 is used, which makes the
            gate harder to pass rather than easier.
        periods_per_year: For annualisation. 252 for daily, 12 for monthly.
        benchmark_sharpe: Override the chance-expected maximum directly.

    Returns:
        The assessment. ``passes`` is True only above 95%.

    Raises:
        GateError: on degenerate input.
    """
    if trials < 1:
        raise GateError(f"trials must be at least 1, got {trials}")
    n = len(returns)
    if n < 4:
        raise GateError(f"need at least 4 observations for higher moments, got {n}")

    observed = sharpe_ratio(returns, periods_per_year=periods_per_year)
    skew, kurt = _moments(returns)

    if benchmark_sharpe is None:
        variance = 1.0 if variance_across_trials is None else variance_across_trials
        benchmark_annual = expected_maximum_sharpe(trials, variance)
    else:
        benchmark_annual = benchmark_sharpe

    # The test statistic works in per-period units.
    obs = observed / math.sqrt(periods_per_year)
    bench = benchmark_annual / math.sqrt(periods_per_year)

    denominator = math.sqrt(max(1.0 - skew * obs + ((kurt - 1.0) / 4.0) * obs**2, 1e-12))
    statistic = ((obs - bench) * math.sqrt(n - 1)) / denominator
    probability = _NORMAL.cdf(statistic)

    return SharpeAssessment(
        observed_sharpe=observed,
        benchmark_sharpe=benchmark_annual,
        deflated_probability=probability,
        trials=trials,
        observations=n,
        skewness=skew,
        kurtosis=kurt,
    )


@dataclass(frozen=True, slots=True)
class OverfittingResult:
    """Output of the combinatorially symmetric cross-validation procedure."""

    probability: float
    splits_evaluated: int
    median_out_of_sample_rank: float

    @property
    def passes(self) -> bool:
        """True if selection shows evidence of genuine skill.

        The conventional threshold is 0.5: at or above it, the in-sample winner
        lands in the bottom half out-of-sample as often as not, which is what
        selecting on noise produces.
        """
        return self.probability < 0.5

    def explain(self) -> str:
        """A sentence a human can check, rather than a number to be quoted."""
        verdict = "SURVIVES" if self.passes else "FAILS"
        return (
            f"{verdict}: PBO {self.probability:.1%} across {self.splits_evaluated} splits. "
            f"The in-sample best configuration landed at median rank "
            f"{self.median_out_of_sample_rank:.2f} out-of-sample "
            f"(0.5 = pure chance, lower is better)."
        )


def probability_of_backtest_overfitting(
    performance: list[list[float]],
    *,
    splits: int = 16,
) -> OverfittingResult:
    """Estimate how often the in-sample winner underperforms out-of-sample.

    Args:
        performance: One list of per-period returns per configuration. Every
            configuration must cover the same periods, because they are compared
            on identical slices.
        splits: Number of in-sample/out-of-sample partitions to evaluate.

    Returns:
        The result. ``probability`` near 0.5 means the selection has no skill.

    Raises:
        GateError: if fewer than two configurations are given, if their lengths
            differ, or if the series are too short to split.
    """
    if len(performance) < 2:
        raise GateError(
            f"need at least 2 configurations to assess selection, got {len(performance)}. "
            f"With one configuration there is no selection to overfit."
        )
    lengths = {len(p) for p in performance}
    if len(lengths) != 1:
        raise GateError(f"all configurations must cover the same periods, got lengths {lengths}")
    n = lengths.pop()
    if n < 2 * splits:
        raise GateError(f"need at least {2 * splits} observations for {splits} splits, got {n}")

    block = n // splits
    below_median = 0
    ranks: list[float] = []

    for i in range(splits):
        oos_start = i * block
        oos_end = oos_start + block if i < splits - 1 else n
        in_sample = [p[:oos_start] + p[oos_end:] for p in performance]
        out_sample = [p[oos_start:oos_end] for p in performance]

        try:
            in_scores = [_safe_sharpe(s) for s in in_sample]
            out_scores = [_safe_sharpe(s) for s in out_sample]
        except GateError:
            continue

        best = max(range(len(in_scores)), key=lambda k: in_scores[k])
        # Fractional rank of the chosen configuration out-of-sample: 0 is worst,
        # 1 is best.
        worse = sum(1 for s in out_scores if s < out_scores[best])
        rank = worse / max(len(out_scores) - 1, 1)
        ranks.append(rank)
        if rank < 0.5:
            below_median += 1

    if not ranks:
        raise GateError("no split produced a usable comparison; series may be degenerate")

    ordered = sorted(ranks)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2

    return OverfittingResult(
        probability=below_median / len(ranks),
        splits_evaluated=len(ranks),
        median_out_of_sample_rank=median,
    )


def _safe_sharpe(returns: list[float]) -> float:
    """Sharpe on a slice, treating a constant slice as zero rather than raising."""
    if len(returns) < 2:
        raise GateError("slice too short")
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    if var <= 0:
        return 0.0
    return mean / math.sqrt(var)


# ---------------------------------------------------------------------------
# Newey-West: the standard error a t-statistic needs when returns are not
# independent
# ---------------------------------------------------------------------------
#
# H1 and H2 both reject on "Newey-West-adjusted |t| < 3.0", and the adjustment
# is not a formality. The ordinary standard error of a mean assumes the
# observations are independent. Monthly strategy returns are not: a momentum
# book holds many of the same names from one month to the next, so consecutive
# returns share exposure and are positively autocorrelated.
#
# Positive autocorrelation makes the ordinary standard error too small, and a
# t-statistic too large -- in the direction that manufactures significance. The
# HAC estimator (Newey & West 1987) widens the error bar by however much the
# series actually repeats itself, using a Bartlett kernel whose weights taper
# to zero and which is guaranteed positive semi-definite, so the variance it
# reports cannot come out negative.
#
# Requiring |t| >= 3.0 rather than the conventional 1.96 is deliberate and was
# fixed at registration. Harvey, Liu & Zhu (2016) argue that the multiple
# testing across the published asset-pricing literature means a t of 2 is no
# longer evidence of anything; 3.0 is their suggested floor for a *new* claim.


def newey_west_lag(observations: int) -> int:
    """Bartlett bandwidth from Newey & West (1994), ``floor(4 (T/100)^(2/9))``.

    Chosen by a published rule rather than by hand. Selecting the lag that made
    a t-statistic look best would be a trial per lag tried, and an undisclosed
    one.

    Args:
        observations: Length of the series.

    Returns:
        The lag truncation, at least 1 for any non-empty series.
    """
    if observations < 2:
        return 0
    return max(1, int(4.0 * (observations / 100.0) ** (2.0 / 9.0)))


@dataclass(frozen=True, slots=True)
class MeanTest:
    """Whether a mean differs from zero, with autocorrelation accounted for."""

    mean: float
    standard_error: float
    t_statistic: float
    observations: int
    lag: int
    naive_t_statistic: float

    @property
    def inflation(self) -> float:
        """How much the naive t overstates the corrected one.

        Above 1.0 means ignoring autocorrelation would have flattered the
        result. It is reported because it is the quantity the correction exists
        to remove, and a reader should see its size rather than trust that it
        was small.
        """
        if self.t_statistic == 0:
            return 0.0
        return abs(self.naive_t_statistic) / abs(self.t_statistic)

    def describe(self) -> str:
        """One line for a result table."""
        return (
            f"mean {self.mean:+.5f}, HAC t {self.t_statistic:+.2f} "
            f"(naive {self.naive_t_statistic:+.2f}, x{self.inflation:.2f}), "
            f"n={self.observations}, lag={self.lag}"
        )


def newey_west_mean_test(series: list[float], *, lag: int | None = None) -> MeanTest:
    """Test whether the mean of ``series`` differs from zero, HAC-corrected.

    Args:
        series: Observations, in time order. Order matters -- shuffling it
            destroys exactly the autocorrelation this measures.
        lag: Bartlett truncation. Defaults to :func:`newey_west_lag`.

    Returns:
        The mean, its HAC standard error, and both t-statistics.

    Raises:
        GateError: if fewer than three observations are supplied, or the series
            has no variance at all.
    """
    count = len(series)
    if count < 3:
        raise GateError(
            f"a mean test needs at least 3 observations, got {count}. Fewer than "
            f"that has no meaningful standard error, and reporting one would "
            f"dress a coincidence as a measurement."
        )
    chosen = newey_west_lag(count) if lag is None else lag
    if chosen < 0 or chosen >= count:
        raise GateError(f"lag must be in [0, {count}), got {chosen}")

    mean = sum(series) / count
    residuals = [value - mean for value in series]
    gamma_zero = sum(r * r for r in residuals) / count
    # Not `gamma_zero <= 0`, for the reason `sharpe_ratio` records above: the
    # mean of identical floats is not exactly any of them, so the residuals come
    # out around 1e-16 and their squares around 1e-32 -- arithmetically positive,
    # financially nothing, and enough to produce a t-statistic in the millions
    # from a series that never moved.
    if math.sqrt(gamma_zero) <= 1e-12 * max(1.0, abs(mean)):
        raise GateError(
            "every observation equals the mean, so the series has no variance and "
            "no standard error exists. A constant is not evidence."
        )

    variance = gamma_zero
    for j in range(1, chosen + 1):
        gamma_j = sum(residuals[t] * residuals[t - j] for t in range(j, count)) / count
        weight = 1.0 - j / (chosen + 1.0)
        variance += 2.0 * weight * gamma_j
    # The Bartlett kernel is positive semi-definite, so this cannot go negative;
    # the guard is against floating-point dust at the boundary, not against the
    # mathematics.
    variance = max(variance, 0.0)

    standard_error = math.sqrt(variance / count)
    naive_error = math.sqrt(gamma_zero * count / (count - 1) / count)
    return MeanTest(
        mean=mean,
        standard_error=standard_error,
        t_statistic=mean / standard_error if standard_error > 0 else 0.0,
        observations=count,
        lag=chosen,
        naive_t_statistic=mean / naive_error if naive_error > 0 else 0.0,
    )
