"""The H4 experiment: score the regime overlay against Amendment A2.

Given four locally stored index series, this module produces a verdict on each
A2 criterion. It computes; it does not decide. Whether H4 stands is determined
by the criteria that were written down before any of this data existed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from indian_equity_research.data.csv_series import load_price_series
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
    "WindowResult",
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
    """

    strategy: PriceSeries
    market: PriceSeries
    vix: PriceSeries
    cash: PriceSeries | None = None


@dataclass(frozen=True, slots=True)
class Criterion:
    """One A2 pass/fail test.

    Attributes:
        name: Short identifier.
        passed: Whether the criterion is satisfied.
        observed: The measured value, formatted.
        required: The declared threshold, formatted.
        note: Optional clarification.
    """

    name: str
    passed: bool
    observed: str
    required: str
    note: str = ""


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
    def supported(self) -> bool:
        """Whether every criterion passed for this window."""
        return all(c.passed for c in self.criteria)

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


def load_inputs(directory: Path) -> H4Inputs:
    """Load the four series from a directory of manually downloaded CSVs.

    Expected filenames, all lower case:

    * ``nifty200_momentum30_tri.csv``
    * ``nifty100_pr.csv``
    * ``india_vix.csv``
    * ``nifty_1d_rate.csv`` (optional; cash earns 0% without it)

    Args:
        directory: Directory containing the CSVs.

    Returns:
        The loaded inputs.

    Raises:
        CsvSeriesError: If a required file is missing or malformed.
    """
    cash_path = directory / "nifty_1d_rate.csv"
    return H4Inputs(
        strategy=load_price_series(
            directory / "nifty200_momentum30_tri.csv", "Nifty200 Momentum 30 TRI"
        ),
        market=load_price_series(directory / "nifty100_pr.csv", "Nifty 100 PR"),
        vix=load_price_series(directory / "india_vix.csv", "India VIX"),
        cash=load_price_series(cash_path, "Nifty 1D Rate") if cash_path.is_file() else None,
    )


def evaluate_window(
    label: str,
    description: str,
    dates: list[date],
    strategy_closes: list[float],
    states: list[Regime],
    cash_returns: list[float] | None,
    config: OverlayConfig,
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
    if inputs.cash is not None:
        series_to_align.append(inputs.cash)

    aligned = align(*series_to_align)
    dates = list(aligned[0])
    strategy_closes = list(aligned[1][0])
    cash_levels = list(aligned[1][2]) if inputs.cash is not None else None

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
            )
        )

    return regime, windows
