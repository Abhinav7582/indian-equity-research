"""End-to-end H4 experiment over synthetic CSVs.

Proves the whole pipeline runs and scores correctly before any real data is
downloaded. The synthetic market is built so the regime rule has something to
react to; the point is that the machinery works, not that the numbers mean
anything.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from indian_equity_research.research.h4_experiment import (
    H4Inputs,
    load_inputs,
    run_experiment,
)
from indian_equity_research.research.regime import RegimeConfig
from indian_equity_research.research.series import PriceSeries

START = date(2015, 1, 1)
DAYS = 900
SMALL_CONFIG = RegimeConfig(sma_window=20, vix_quantile=0.8, vix_window=60)


def synthetic() -> tuple[list[date], list[float], list[float], list[float]]:
    """A rising market with two drawdowns, and VIX spiking during each."""
    dates = [START + timedelta(days=i) for i in range(DAYS)]
    market: list[float] = []
    vix: list[float] = []
    level = 1000.0
    for i in range(DAYS):
        in_crash = 300 <= i < 400 or 650 <= i < 720
        level *= 0.995 if in_crash else 1.0012
        market.append(level)
        vix.append(35.0 if in_crash else 13.0)
    strategy = [m * 1.5 for m in market]
    return dates, strategy, market, vix


def build_inputs() -> H4Inputs:
    dates, strategy, market, vix = synthetic()
    return H4Inputs(
        strategy=PriceSeries("STRAT", tuple(dates), tuple(strategy)),
        market=PriceSeries("MKT", tuple(dates), tuple(market)),
        vix=PriceSeries("VIX", tuple(dates), tuple(vix)),
    )


class TestRunExperiment:
    def test_produces_a_regime_and_at_least_one_window(self) -> None:
        regime, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        assert len(regime) > 0
        assert windows

    def test_detects_risk_off_during_the_synthetic_crashes(self) -> None:
        regime, _ = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        assert 0.0 < regime.fraction_risk_off() < 1.0

    def test_every_criterion_is_present(self) -> None:
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        names = {c.name for c in windows[0].criteria}
        assert names == {
            "drawdown reduction",
            "CAGR sacrifice",
            "switching frequency",
            "multiple episodes",
            "beats static blend",
        }

    def test_overlay_reduces_drawdown_on_this_synthetic_market(self) -> None:
        """Not evidence about H4 - only that the comparison is wired correctly."""
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        assert windows[0].overlaid.max_drawdown < windows[0].baseline.max_drawdown

    def test_reports_costs_and_tax_separately(self) -> None:
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        assert windows[0].total_costs > 0
        assert windows[0].total_tax >= 0

    def test_supported_flag_reflects_every_criterion(self) -> None:
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        w = windows[0]
        assert w.supported == all(c.passed for c in w.criteria)

    def test_derived_measures_are_consistent(self) -> None:
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        w = windows[0]
        expected = (w.baseline.max_drawdown - w.overlaid.max_drawdown) / w.baseline.max_drawdown
        assert w.drawdown_reduction == pytest.approx(expected)
        assert w.cagr_sacrifice == pytest.approx(w.baseline.cagr - w.overlaid.cagr)


class TestLoadInputs:
    def _write(self, directory: Path) -> None:
        dates, strategy, market, vix = synthetic()
        for filename, values in (
            ("nifty200_momentum30_tri.csv", strategy),
            ("nifty100_pr.csv", market),
            ("india_vix.csv", vix),
        ):
            rows = "\n".join(
                f"{d.strftime('%d-%b-%Y')},{v:.4f}" for d, v in zip(dates, values, strict=True)
            )
            (directory / filename).write_text(f"Date,Close\n{rows}\n", encoding="utf-8")

    def test_loads_the_three_required_series(self, tmp_path: Path) -> None:
        self._write(tmp_path)
        inputs = load_inputs(tmp_path)
        assert len(inputs.strategy) == DAYS
        assert len(inputs.market) == DAYS
        assert len(inputs.vix) == DAYS
        assert inputs.cash is None

    def test_cash_series_is_optional(self, tmp_path: Path) -> None:
        self._write(tmp_path)
        assert load_inputs(tmp_path).cash is None

    def test_end_to_end_from_files(self, tmp_path: Path) -> None:
        self._write(tmp_path)
        regime, windows = run_experiment(load_inputs(tmp_path), regime_config=SMALL_CONFIG)
        assert len(regime) == DAYS
        assert windows


class TestStaticBlendCriterion:
    """A2 criterion 5: the overlay must beat doing nothing clever."""

    def test_unscored_without_the_blend_series(self) -> None:
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        blend = next(c for c in windows[0].criteria if c.name == "beats static blend")
        assert blend.evaluated is False
        assert "not supplied" in blend.observed

    def test_missing_blend_makes_the_window_incomplete(self) -> None:
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        assert windows[0].fully_evaluated is False

    def test_an_unscored_criterion_is_never_a_pass(self) -> None:
        """The failure mode this guards: silently treating absent data as success."""
        _, windows = run_experiment(build_inputs(), regime_config=SMALL_CONFIG)
        assert windows[0].supported is False

    def test_scored_when_the_blend_is_supplied(self) -> None:
        base = build_inputs()
        # A blend that is far smoother than the strategy: the overlay should lose.
        smooth = PriceSeries(
            "BLEND",
            base.strategy.dates,
            tuple(1000.0 * (1.0004**i) for i in range(len(base.strategy))),
        )
        inputs = H4Inputs(strategy=base.strategy, market=base.market, vix=base.vix, blend=smooth)
        _, windows = run_experiment(inputs, regime_config=SMALL_CONFIG)
        blend = next(c for c in windows[0].criteria if c.name == "beats static blend")
        assert blend.evaluated is True
        assert blend.passed is False  # a monotonic blend has no drawdown to beat
        assert windows[0].fully_evaluated is True

    def test_overlay_wins_against_a_volatile_blend(self) -> None:
        base = build_inputs()
        _, _, market, _ = synthetic()
        # A "blend" that is actually worse than the strategy.
        volatile = PriceSeries(
            "BLEND",
            base.strategy.dates,
            tuple(m * (0.5 if 300 <= i < 400 else 1.0) for i, m in enumerate(market)),
        )
        inputs = H4Inputs(strategy=base.strategy, market=base.market, vix=base.vix, blend=volatile)
        _, windows = run_experiment(inputs, regime_config=SMALL_CONFIG)
        blend = next(c for c in windows[0].criteria if c.name == "beats static blend")
        assert blend.passed is True
