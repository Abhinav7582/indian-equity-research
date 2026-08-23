"""H2 — does a momentum book beat the Nifty 100 TRI after every cost and tax?

The hypothesis this project exists to answer, run exactly as Amendment A9
declares it: **10 holdings**, the top decile of 12-1 momentum in the
point-in-time Nifty 100, equal weight, rebalanced on the first session of each
month, decided on the previous close and filled at the next open.

What is being compared, and why it is not obvious
--------------------------------------------------
The strategy pays brokerage, STT, stamp duty, exchange and SEBI fees, GST, DP
charges, and capital gains tax at the **short-term** rate on almost every
realised gain, because a monthly rebalance almost never holds anything twelve
months.

The benchmark is the Nifty 100 **Total Return** Index. A price-return
comparison would overstate the strategy by the index's dividend yield, roughly
1.2-1.5% a year in this market, which is larger than many claimed edges.

But the TRI is not itself investable either, so it is reported alongside a
**net benchmark**: the same index less a 0.20% annual expense ratio, which is
what a Nifty 100 index fund actually costs, and less LTCG at 12.5% on the
terminal gain, since a buy-and-hold investor realises once. The strategy must
beat that to be worth running, and beating the raw TRI is not sufficient.

Warm-up, and the year it costs
------------------------------
12-1 momentum needs 273 sessions before the first decision. The archive starts
2015-01-01, so the first tradeable rebalance is in early 2016 and the
development window is shorter than the calendar suggests. That is a property of
the data, not a choice, and the actual first and last session are reported with
every result rather than assumed from the request.

The holdout
-----------
`HYPOTHESES.md` declares 2022-01-01 to 2025-12-31 as a holdout to be touched
**once**. This module will refuse to run across it unless explicitly told to,
and saying so is a deliberate act recorded in the trial register. The archive's
2026 tail is outside the declared holdout and is **not** a second one.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import pairwise
from pathlib import Path
from typing import Final

from indian_equity_research.backtest.engine import (
    BacktestResult,
    Bar,
    EngineConfig,
    PriceView,
    run_backtest,
)
from indian_equity_research.backtest.gates import MeanTest, newey_west_mean_test
from indian_equity_research.backtest.tax import TaxSummary, tax_on_fills
from indian_equity_research.market.membership import MembershipHistory, members_on
from indian_equity_research.research.metrics import PerformanceSummary, max_drawdown, summarise
from indian_equity_research.research.momentum import (
    FORMATION_SESSIONS,
    SKIP_SESSIONS,
    rank_by_momentum,
    select_top,
)

__all__ = [
    "HOLDOUT_END",
    "HOLDOUT_START",
    "INDEX_FUND_EXPENSE_RATIO",
    "H2Config",
    "H2Result",
    "HoldoutBreach",
    "load_tri",
    "month_start_sessions",
    "run_h2",
]

#: The declared holdout, from ``HYPOTHESES.md``. Touched once, at the end.
HOLDOUT_START: Final = date(2022, 1, 1)
HOLDOUT_END: Final = date(2025, 12, 31)

#: What a real Nifty 100 index fund charges. Direct-plan index funds tracking
#: this index sit around 0.20%; the benchmark is not free to hold either.
INDEX_FUND_EXPENSE_RATIO: Final = 0.0020

_WARMUP_SESSIONS: Final = FORMATION_SESSIONS + SKIP_SESSIONS


class HoldoutBreach(RuntimeError):  # noqa: N818 - it is a breach, not an error about one
    """Raised when a run would touch the holdout without saying so."""


@dataclass(frozen=True, slots=True)
class H2Config:
    """Everything A9 fixed, in one object that can be printed with the result."""

    holdings: int = 10
    start: date = date(2015, 1, 1)
    end: date = date(2021, 12, 31)
    initial_capital: float = 300_000.0
    sell_orders_per_exit: float = 1.0
    expense_ratio: float = INDEX_FUND_EXPENSE_RATIO

    def describe(self) -> str:
        """One line that identifies the configuration for the trial register."""
        return (
            f"H2: {self.holdings} holdings, equal weight, monthly, "
            f"{self.start} to {self.end}, capital {self.initial_capital:,.0f}, "
            f"{self.sell_orders_per_exit} sell order(s) per exit"
        )


@dataclass(frozen=True, slots=True)
class H2Result:
    """The result, with every number a rejection criterion needs."""

    config: H2Config
    strategy: PerformanceSummary
    benchmark: PerformanceSummary
    strategy_post_tax_curve: tuple[float, ...]
    benchmark_net_curve: tuple[float, ...]
    dates: tuple[date, ...]
    excess_test: MeanTest
    tax: TaxSummary
    total_charges: float
    total_turnover: float
    rebalances: int
    residual_warnings: tuple[str, ...]

    @property
    def net_cagr(self) -> float:
        """Strategy CAGR after charges and tax."""
        return _cagr(self.strategy_post_tax_curve, self.dates)

    @property
    def benchmark_net_cagr(self) -> float:
        """Benchmark CAGR after expense ratio and terminal LTCG."""
        return _cagr(self.benchmark_net_curve, self.dates)

    @property
    def excess_cagr(self) -> float:
        """Annualised outperformance, both sides net."""
        return self.net_cagr - self.benchmark_net_cagr

    @property
    def strategy_max_drawdown(self) -> float:
        """Worst peak-to-trough on the post-tax curve."""
        return max_drawdown(list(self.strategy_post_tax_curve))

    @property
    def benchmark_max_drawdown(self) -> float:
        """Worst peak-to-trough on the net benchmark."""
        return max_drawdown(list(self.benchmark_net_curve))


def _cagr(curve: Sequence[float], dates: Sequence[date]) -> float:
    """Compound annual growth of a curve, or 0.0 over a degenerate window."""
    if len(curve) < 2 or curve[0] <= 0:
        return 0.0
    years = (dates[-1] - dates[0]).days / 365.25
    if years <= 0:
        return 0.0
    # float() around the power: typeshed types ``float.__pow__`` as returning
    # Any, because a negative base with a fractional exponent yields a complex.
    # The guard above rules that out here, so the cast states what is already
    # true rather than hiding anything.
    return float((curve[-1] / curve[0]) ** (1.0 / years)) - 1.0


def load_tri(directory: Path) -> dict[date, float]:
    """Read the Nifty 100 Total Return Index from NSE's yearly CSVs.

    Args:
        directory: Folder of ``nifty100_tri_YYYY.csv`` files.

    Returns:
        ``{date: level}``.

    Raises:
        FileNotFoundError: if no files are present. A silently empty benchmark
            would make every excess return equal the strategy's own return.
    """
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"no Nifty 100 TRI files in {directory}. H2 is defined against the "
            f"Total Return Index; without it there is nothing to compare to."
        )
    levels: dict[date, float] = {}
    for path in files:
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                raw = (row.get("Date") or "").strip()
                value = (row.get("Total Returns Index") or "").strip()
                if not raw or not value:
                    continue
                parsed = datetime.strptime(raw, "%d %b %Y").replace(tzinfo=UTC)
                levels[parsed.date()] = float(value.replace(",", ""))
    return levels


def month_start_sessions(sessions: Sequence[date]) -> list[date]:
    """The first session of each calendar month present in ``sessions``."""
    seen: set[tuple[int, int]] = set()
    out: list[date] = []
    for when in sorted(sessions):
        key = (when.year, when.month)
        if key not in seen:
            seen.add(key)
            out.append(when)
    return out


def _strategy_for(
    history: MembershipHistory, holdings: int
) -> Callable[[PriceView], Mapping[str, float]]:
    """Build the A9 strategy: rank point-in-time members, take the top decile."""

    def strategy(view: PriceView) -> Mapping[str, float]:
        members = members_on(history, view.as_of)
        ranking = rank_by_momentum(view, members)
        return select_top(ranking, holdings)

    return strategy


def _benchmark_curve(
    levels: Mapping[date, float], dates: Sequence[date], initial: float, expense_ratio: float
) -> list[float]:
    """The TRI rebased to ``initial``, less a daily slice of the expense ratio.

    Forward-filled across sessions the index did not publish, which happens
    where NSE's calendar and the bhavcopy calendar differ by a day. Forward-fill
    is right and back-fill would not be: it carries the last **known** level
    rather than one from the future.
    """
    out: list[float] = []
    last: float | None = None
    base: float | None = None
    for index, when in enumerate(dates):
        level = levels.get(when, last)
        if level is None:
            continue
        last = level
        if base is None:
            base = level
        drag = float((1.0 - expense_ratio) ** (index / 252.0))
        out.append(initial * (level / base) * drag)
    return out


def run_h2(
    bars: Mapping[str, Mapping[date, Bar]],
    sessions: Sequence[date],
    history: MembershipHistory,
    tri: Mapping[date, float],
    *,
    config: H2Config | None = None,
    residual_warnings: Sequence[str] = (),
    allow_holdout: bool = False,
) -> H2Result:
    """Run H2 as declared and return everything its criteria need.

    Args:
        bars: Back-adjusted OHLC, from ``backtest.prices.build_bars``.
        sessions: Every session in the archive, ascending. The backtest starts
            after the 273-session warm-up, not at ``sessions[0]``.
        history: Point-in-time membership.
        tri: Nifty 100 Total Return Index levels.
        config: The A9 specification.
        residual_warnings: Unexplained large moves reported by the price
            builder, carried onto the result so a reader sees them next to the
            number rather than in a different file.
        allow_holdout: Must be ``True`` to run across the declared holdout.

    Returns:
        The result.

    Raises:
        HoldoutBreach: if the window overlaps the holdout and ``allow_holdout``
            is not set.
        ValueError: if the warm-up leaves too few sessions to run.
    """
    cfg = config or H2Config()
    if not allow_holdout and cfg.end >= HOLDOUT_START:
        raise HoldoutBreach(
            f"the requested window ends {cfg.end}, inside the declared holdout "
            f"({HOLDOUT_START} to {HOLDOUT_END}). HYPOTHESES.md says the holdout is "
            f"touched exactly once, at the end, after the specification is final. "
            f"Pass allow_holdout=True only when that moment has arrived, and log it "
            f"in the trial register."
        )

    ordered = [d for d in sorted(sessions) if cfg.start <= d <= cfg.end]
    if len(ordered) <= _WARMUP_SESSIONS + 2:
        raise ValueError(
            f"{len(ordered)} sessions in {cfg.start}..{cfg.end}, but 12-1 momentum "
            f"needs {_WARMUP_SESSIONS} before the first decision. Widen the window."
        )
    tradeable = ordered[_WARMUP_SESSIONS:]
    rebalance_days = set(month_start_sessions(tradeable))

    result = run_backtest(
        bars,
        tradeable,
        _strategy_for(history, cfg.holdings),
        config=EngineConfig(
            initial_capital=cfg.initial_capital,
            sell_orders_per_exit=cfg.sell_orders_per_exit,
        ),
        rebalance_on=lambda when: when in rebalance_days,
    )

    tax = tax_on_fills(result.fills)
    post_tax = _post_tax_curve(result, tax)
    benchmark = _benchmark_curve(tri, result.dates, cfg.initial_capital, cfg.expense_ratio)

    # Compare on identical dates. A benchmark one session shorter would shift
    # every excess return by a day and quietly change the sign of the test.
    span = min(len(post_tax), len(benchmark))
    dates = tuple(result.dates[:span])
    post_tax = post_tax[:span]
    benchmark = benchmark[:span]

    monthly = _monthly_excess(dates, post_tax, benchmark)
    return H2Result(
        config=cfg,
        strategy=summarise("H2 strategy", list(dates), post_tax, _returns(post_tax)),
        benchmark=summarise("Nifty 100 TRI net", list(dates), benchmark, _returns(benchmark)),
        strategy_post_tax_curve=tuple(post_tax),
        benchmark_net_curve=tuple(benchmark),
        dates=dates,
        excess_test=newey_west_mean_test(monthly),
        tax=tax,
        total_charges=result.total_charges,
        total_turnover=result.total_turnover,
        rebalances=len(rebalance_days),
        residual_warnings=tuple(residual_warnings),
    )


def _post_tax_curve(result: BacktestResult, tax: TaxSummary) -> list[float]:
    """Subtract each financial year's tax from the equity curve when it is due.

    Charged on 31 March of the year it accrues rather than smoothed across it.
    Smoothing would understate every drawdown that ends near a year boundary,
    which is exactly where a strategy is most likely to be judged.
    """
    by_year_end: dict[str, float] = {label: year.total_tax for label, year in tax.years.items()}
    paid = 0.0
    out: list[float] = []
    settled: set[str] = set()
    for when, equity in zip(result.dates, result.equity, strict=True):
        for label, amount in by_year_end.items():
            end_year = int(label.split("-")[0]) + 1
            if label not in settled and when >= date(end_year, 3, 31):
                paid += amount
                settled.add(label)
        out.append(equity - paid)
    return out


def _returns(curve: Sequence[float]) -> list[float]:
    """Period returns of a curve."""
    return [curve[i] / curve[i - 1] - 1.0 for i in range(1, len(curve)) if curve[i - 1] > 0]


def _monthly_excess(
    dates: Sequence[date], strategy: Sequence[float], benchmark: Sequence[float]
) -> list[float]:
    """Month-end excess returns, which is what the t-test is defined on.

    Daily excess returns would give twenty times as many observations of the
    same six years and a t-statistic inflated accordingly. The frequency of a
    test must match the frequency of the decision, which A9 fixes as monthly.
    """
    marks = month_start_sessions(dates)
    index = {when: i for i, when in enumerate(dates)}
    points = [index[m] for m in marks if m in index]
    out: list[float] = []
    for earlier, later in pairwise(points):
        if strategy[earlier] <= 0 or benchmark[earlier] <= 0:
            continue
        out.append((strategy[later] / strategy[earlier]) - (benchmark[later] / benchmark[earlier]))
    return out
