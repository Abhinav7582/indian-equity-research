"""The H4 experiment: score the regime overlay against Amendment A2.

Given four locally stored index series, this module produces a verdict on each
A2 criterion. It computes; it does not decide. Whether H4 stands is determined
by the criteria that were written down before any of this data existed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from indian_equity_research.data.csv_series import load_price_series_glob
from indian_equity_research.research.metrics import (
    PerformanceSummary,
    drawdown_episodes,
    summarise,
)
from indian_equity_research.research.overlay import (
    OverlayConfig,
    OverlayResult,
    apply_overlay,
    buy_and_hold,
)
from indian_equity_research.research.regime import (
    Regime,
    RegimeConfig,
    RegimeSeries,
    compute_regime,
    lag_states,
)
from indian_equity_research.research.series import PriceSeries, align, simple_returns

__all__ = [
    "Criterion",
    "H4Inputs",
    "SeriesReport",
    "WindowResult",
    "describe_inputs",
    "evaluate_window",
    "load_inputs",
    "run_experiment",
]

#: Amendment A2 thresholds. Changing any of these requires a further amendment.
MIN_RELATIVE_DRAWDOWN_REDUCTION = 0.20
MAX_CAGR_SACRIFICE = 0.02
MAX_SWITCHES_PER_YEAR = 8.0
MIN_DISTINCT_EPISODES = 2

#: Index launch date. Everything earlier is back-tested, not live.
MOMENTUM_INDEX_LAUNCH = date(2020, 8, 25)


@dataclass(frozen=True, slots=True)
class H4Inputs:
    """The four series the experiment consumes.

    Attributes:
        strategy: Nifty200 Momentum 30 total return index.
        market: Nifty 100 price return index, input to the trend condition.
        vix: India VIX daily closes.
        cash: Overnight rate index used while in cash. Optional.
        blend: Nifty200 Momentum 30 Plus 8-13yr G-Sec 75:25. The static
            alternative the overlay must beat under A2. Optional only in the
            sense that the code runs without it; A2 requires it before H4 can
            be declared supported.
    """

    strategy: PriceSeries
    market: PriceSeries
    vix: PriceSeries
    cash: PriceSeries | None = None
    blend: PriceSeries | None = None


@dataclass(frozen=True, slots=True)
class Criterion:
    """One A2 pass/fail test.

    Attributes:
        name: Short identifier.
        passed: Whether the criterion is satisfied. Meaningless when
            ``evaluated`` is ``False``.
        observed: The measured value, formatted.
        required: The declared threshold, formatted.
        note: Optional clarification.
        evaluated: ``False`` when the data needed to score this criterion was
            not supplied. An unevaluated criterion is **not** a pass; the
            overall verdict is incomplete until every criterion has been
            scored.
    """

    name: str
    passed: bool
    observed: str
    required: str
    note: str = ""
    evaluated: bool = True


@dataclass(frozen=True, slots=True)
class WindowResult:
    """Scored outcome for one evaluation window.

    Attributes:
        label: Window identifier, ``"W1"`` or ``"W2"``.
        description: Human-readable span description.
        overlaid: Summary of the overlaid strategy, post tax and costs.
        baseline: Summary of the unoverlaid buy-and-hold comparator.
        criteria: Each A2 criterion with its outcome.
        switches_per_year: Realised switching frequency.
        distinct_episodes: Material drawdown episodes in the baseline.
        total_costs: Explicit transaction costs paid by the overlay.
        total_tax: Capital gains tax paid by the overlay.
    """

    label: str
    description: str
    overlaid: PerformanceSummary
    baseline: PerformanceSummary
    criteria: tuple[Criterion, ...]
    switches_per_year: float
    distinct_episodes: int
    total_costs: float
    total_tax: float

    @property
    def fully_evaluated(self) -> bool:
        """Whether every criterion had the data needed to score it."""
        return all(c.evaluated for c in self.criteria)

    @property
    def supported(self) -> bool:
        """Whether every criterion was scored and passed.

        An unscored criterion cannot count as a pass. H4 is supported only
        when the full A2 set has been evaluated.
        """
        return self.fully_evaluated and all(c.passed for c in self.criteria)

    @property
    def drawdown_reduction(self) -> float:
        """Relative reduction in maximum drawdown versus the baseline."""
        if self.baseline.max_drawdown <= 0:
            return 0.0
        return (
            self.baseline.max_drawdown - self.overlaid.max_drawdown
        ) / self.baseline.max_drawdown

    @property
    def cagr_sacrifice(self) -> float:
        """Annualised CAGR given up by the overlay. Negative means it gained."""
        return self.baseline.cagr - self.overlaid.cagr


@dataclass(frozen=True, slots=True)
class SeriesReport:
    """What was actually loaded, and whether it looks like the right thing.

    Downloading the wrong series is the most likely mistake in this workflow -
    price return instead of total return, the wrong index, or a truncated date
    range. Those errors do not raise; they quietly produce a plausible-looking
    number. These checks surface them before any result is printed.

    Attributes:
        name: Series identifier.
        observations: Number of rows loaded.
        first: Earliest date.
        last: Latest date.
        warnings: Human-readable concerns, empty when nothing looks wrong.
    """

    name: str
    observations: int
    first: date
    last: date
    warnings: tuple[str, ...] = ()


#: Below this many observations a three-year rolling window cannot warm up.
_MIN_USEFUL_OBSERVATIONS = 250
#: India VIX has historically traded roughly between 8 and 90.
_VIX_PLAUSIBLE_LOW = 5.0
_VIX_PLAUSIBLE_HIGH = 150.0


def _check_series(series: PriceSeries, *, is_vix: bool = False) -> SeriesReport:
    """Sanity-check one loaded series.

    Args:
        series: The loaded series.
        is_vix: Apply volatility-index range checks when ``True``.

    Returns:
        A report including any warnings.
    """
    warnings: list[str] = []
    if len(series) < _MIN_USEFUL_OBSERVATIONS:
        warnings.append(
            f"only {len(series)} observations - too short for a 3-year rolling window; "
            "download a longer date range"
        )
    span_years = (series.dates[-1] - series.dates[0]).days / 365.25
    if span_years > 0 and len(series) / span_years < 150:
        warnings.append(
            f"~{len(series) / span_years:.0f} observations per year - expected ~250 for "
            "daily data; the file may be weekly or monthly"
        )
    if is_vix:
        lo, hi = min(series.closes), max(series.closes)
        if lo < _VIX_PLAUSIBLE_LOW or hi > _VIX_PLAUSIBLE_HIGH:
            warnings.append(
                f"values range {lo:.1f}-{hi:.1f}, outside the plausible India VIX band "
                f"({_VIX_PLAUSIBLE_LOW:.0f}-{_VIX_PLAUSIBLE_HIGH:.0f}) - is this really VIX?"
            )
    return SeriesReport(
        name=series.name,
        observations=len(series),
        first=series.dates[0],
        last=series.dates[-1],
        warnings=tuple(warnings),
    )


def describe_inputs(inputs: H4Inputs) -> list[SeriesReport]:
    """Report coverage and plausibility for every loaded series.

    Args:
        inputs: The loaded series.

    Returns:
        One report per series that was supplied.
    """
    reports = [
        _check_series(inputs.strategy),
        _check_series(inputs.market),
        _check_series(inputs.vix, is_vix=True),
    ]
    if inputs.blend is not None:
        reports.append(_check_series(inputs.blend))
    if inputs.cash is not None:
        reports.append(_check_series(inputs.cash))

    # A total-return index must outgrow its own price-return counterpart over a
    # long span. If the momentum series has not, it is probably the PR variant.
    strategy_growth = inputs.strategy.closes[-1] / inputs.strategy.closes[0]
    market_growth = inputs.market.closes[-1] / inputs.market.closes[0]
    span = (inputs.strategy.dates[-1] - inputs.strategy.dates[0]).days / 365.25
    if span > 5 and strategy_growth <= market_growth:
        reports[0] = SeriesReport(
            reports[0].name,
            reports[0].observations,
            reports[0].first,
            reports[0].last,
            (
                *reports[0].warnings,
                "grew no faster than the Nifty 100 price index over "
                f"{span:.0f} years - check this is the TOTAL RETURN series, not price return",
            ),
        )
    return reports


def load_inputs(directory: Path) -> H4Inputs:
    """Load the four series from a directory of manually downloaded CSVs.

    Files are matched by a recursive glob, so a history downloaded one year at
    a time can be dropped in as ``nifty100_pr_2015.csv``,
    ``nifty100_pr_2016.csv`` and so on, either loose in the directory or
    grouped into one subfolder per series. Expected patterns, all lower case:

    * ``nifty200_momentum30_tri*.csv``
    * ``nifty100_pr*.csv``
    * ``india_vix*.csv``
    * ``nifty200_momentum30_gsec_7525*.csv`` (the static blend A2 compares
      against; without it the fifth criterion cannot be scored and H4 cannot
      be declared supported)
    * ``nifty_1d_rate*.csv`` (optional; cash earns 0% without it)

    Args:
        directory: Directory containing the CSVs.

    Returns:
        The loaded inputs.

    Raises:
        CsvSeriesError: If a required file is missing or malformed.
    """
    has_cash = any(directory.rglob("nifty_1d_rate*.csv"))
    has_blend = any(directory.rglob("nifty200_momentum30_gsec_7525*.csv"))
    return H4Inputs(
        strategy=load_price_series_glob(
            directory, "nifty200_momentum30_tri*.csv", "Nifty200 Momentum 30 TRI"
        ),
        market=load_price_series_glob(directory, "nifty100_pr*.csv", "Nifty 100 PR"),
        vix=load_price_series_glob(directory, "india_vix*.csv", "India VIX"),
        cash=(
            load_price_series_glob(directory, "nifty_1d_rate*.csv", "Nifty 1D Rate")
            if has_cash
            else None
        ),
        blend=(
            load_price_series_glob(
                directory, "nifty200_momentum30_gsec_7525*.csv", "Momentum 30 + G-Sec 75:25"
            )
            if has_blend
            else None
        ),
    )


def evaluate_window(
    label: str,
    description: str,
    dates: list[date],
    strategy_closes: list[float],
    states: list[Regime],
    cash_returns: list[float] | None,
    config: OverlayConfig,
    blend_closes: list[float] | None = None,
) -> WindowResult:
    """Score one evaluation window against the A2 criteria.

    Args:
        label: Window identifier.
        description: Human-readable span description.
        dates: Evaluation dates.
        strategy_closes: Strategy index closes, parallel to ``dates``.
        states: Lagged regime states, parallel to ``dates``.
        cash_returns: Cash returns while de-risked, length ``len(dates) - 1``.
        config: Cost and tax parameters.
        blend_closes: Closes of the static momentum/G-Sec blend, parallel to
            ``dates``. When omitted the fifth A2 criterion is reported as not
            evaluated.

    Returns:
        The scored window.
    """
    overlaid: OverlayResult = apply_overlay(
        dates, strategy_closes, states, cash_returns=cash_returns, config=config
    )
    baseline: OverlayResult = buy_and_hold(dates, strategy_closes, config)

    overlaid_summary = summarise(
        "overlaid", overlaid.dates, overlaid.post_tax_curve, overlaid.returns()
    )
    baseline_summary = summarise(
        "buy-and-hold", baseline.dates, baseline.post_tax_curve, baseline.returns()
    )

    years = max((dates[-1] - dates[0]).days / 365.25, 1e-9)
    switches_per_year = overlaid.switch_count / years
    episodes = drawdown_episodes(baseline.dates, baseline.post_tax_curve)

    reduction = (
        (baseline_summary.max_drawdown - overlaid_summary.max_drawdown)
        / baseline_summary.max_drawdown
        if baseline_summary.max_drawdown > 0
        else 0.0
    )
    sacrifice = baseline_summary.cagr - overlaid_summary.cagr

    criteria = (
        Criterion(
            "drawdown reduction",
            reduction >= MIN_RELATIVE_DRAWDOWN_REDUCTION,
            f"{reduction:+.1%}",
            f">= {MIN_RELATIVE_DRAWDOWN_REDUCTION:.0%} relative",
        ),
        Criterion(
            "CAGR sacrifice",
            sacrifice <= MAX_CAGR_SACRIFICE,
            f"{sacrifice:+.2%} p.a.",
            f"<= {MAX_CAGR_SACRIFICE:.0%} p.a.",
        ),
        Criterion(
            "switching frequency",
            switches_per_year <= MAX_SWITCHES_PER_YEAR,
            f"{switches_per_year:.1f}/yr",
            f"<= {MAX_SWITCHES_PER_YEAR:.0f}/yr",
        ),
        Criterion(
            "multiple episodes",
            len(episodes) >= MIN_DISTINCT_EPISODES,
            f"{len(episodes)} episodes",
            f">= {MIN_DISTINCT_EPISODES}",
            note="benefit must not rest on a single historical episode",
        ),
        _score_static_blend(dates, blend_closes, overlaid_summary, config),
    )

    return WindowResult(
        label=label,
        description=description,
        overlaid=overlaid_summary,
        baseline=baseline_summary,
        criteria=criteria,
        switches_per_year=switches_per_year,
        distinct_episodes=len(episodes),
        total_costs=overlaid.total_costs,
        total_tax=overlaid.total_tax,
    )


def _score_static_blend(
    dates: list[date],
    blend_closes: list[float] | None,
    overlaid: PerformanceSummary,
    config: OverlayConfig,
) -> Criterion:
    """Score the overlay against NSE's static momentum/G-Sec blend.

    Amendment A2 rejects H4 if a static blend matches or exceeds the overlay's
    drawdown benefit, because such a blend needs no machinery, incurs no
    switching cost and triggers no tax event. A dynamic rule has to beat doing
    nothing clever, not merely beat doing nothing.

    Args:
        dates: Evaluation dates.
        blend_closes: Blend index closes, parallel to ``dates``.
        overlaid: Summary of the overlaid strategy.
        config: Cost parameters, used for the blend's single entry cost.

    Returns:
        The scored criterion, marked unevaluated when the blend is absent.
    """
    if blend_closes is None:
        return Criterion(
            "beats static blend",
            passed=False,
            observed="not supplied",
            required="overlay drawdown < blend drawdown",
            note="A2 requires this; add nifty200_momentum30_gsec_7525.csv",
            evaluated=False,
        )
    blend = buy_and_hold(dates, blend_closes, config)
    blend_summary = summarise("static blend", blend.dates, blend.post_tax_curve, blend.returns())
    beats = overlaid.max_drawdown < blend_summary.max_drawdown
    return Criterion(
        "beats static blend",
        passed=beats,
        observed=(
            f"{overlaid.max_drawdown:.1%} vs {blend_summary.max_drawdown:.1%} "
            f"(CAGR {overlaid.cagr:+.1%} vs {blend_summary.cagr:+.1%})"
        ),
        required="overlay drawdown < blend drawdown",
        note="a static 75:25 blend needs no switching, no tax, no machinery",
    )


def run_experiment(
    inputs: H4Inputs,
    *,
    regime_config: RegimeConfig | None = None,
    overlay_config: OverlayConfig | None = None,
) -> tuple[RegimeSeries, list[WindowResult]]:
    """Run the full H4 experiment over both A2 evaluation windows.

    Args:
        inputs: The four loaded series.
        regime_config: Rule parameters. Defaults to the A2 values.
        overlay_config: Cost and tax parameters. Defaults to the A2 values.

    Returns:
        The computed regime series, and one :class:`WindowResult` per window.

    Raises:
        ValueError: If the series do not overlap sufficiently.
    """
    reg_cfg = regime_config or RegimeConfig()
    ovl_cfg = overlay_config or OverlayConfig()

    regime = compute_regime(inputs.market, inputs.vix, reg_cfg)
    lagged = lag_states(regime.states, lag=1)

    regime_as_series = PriceSeries("regime-dates", regime.dates, tuple(1.0 for _ in regime.dates))
    series_to_align: list[PriceSeries] = [inputs.strategy, regime_as_series]
    cash_index = blend_index = None
    if inputs.cash is not None:
        cash_index = len(series_to_align)
        series_to_align.append(inputs.cash)
    if inputs.blend is not None:
        blend_index = len(series_to_align)
        series_to_align.append(inputs.blend)

    aligned = align(*series_to_align)
    dates = list(aligned[0])
    strategy_closes = list(aligned[1][0])
    cash_levels = list(aligned[1][cash_index]) if cash_index is not None else None
    blend_levels = list(aligned[1][blend_index]) if blend_index is not None else None

    state_by_date = dict(zip(regime.dates, lagged, strict=True))
    states = [state_by_date[d] for d in dates]
    cash_returns = simple_returns(cash_levels) if cash_levels else None

    windows: list[WindowResult] = []
    tradable = [i for i, s in enumerate(states) if s is not Regime.UNKNOWN]
    if tradable:
        first = tradable[0]
        windows.append(
            evaluate_window(
                "W1",
                f"full available history ({dates[first]} to {dates[-1]}) "
                "- contains a back-tested segment",
                dates[first:],
                strategy_closes[first:],
                states[first:],
                cash_returns[first:] if cash_returns else None,
                ovl_cfg,
                blend_levels[first:] if blend_levels else None,
            )
        )

    live = [i for i, d in enumerate(dates) if d >= MOMENTUM_INDEX_LAUNCH]
    if live and states[live[0]] is not Regime.UNKNOWN and len(live) > 2:
        start = live[0]
        windows.append(
            evaluate_window(
                "W2",
                f"live only ({dates[start]} to {dates[-1]}) - index launched "
                f"{MOMENTUM_INDEX_LAUNCH}; this window governs",
                dates[start:],
                strategy_closes[start:],
                states[start:],
                cash_returns[start:] if cash_returns else None,
                ovl_cfg,
                blend_levels[start:] if blend_levels else None,
            )
        )

    return regime, windows
