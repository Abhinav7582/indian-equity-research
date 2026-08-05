"""Apply the H4 regime overlay, charging every cost Amendment A2 requires.

A regime overlay is not free, and the costs are asymmetric in a way that is
easy to miss:

* **Transaction costs** on each switch, in and out.
* **Tax.** Every RISK-OFF exit *realises* gains. At holding periods under
  twelve months that is 20% STCG, and the exit also resets the holding-period
  clock. The buy-and-hold comparator realises nothing and defers its tax
  indefinitely. This asymmetry is usually the overlay's largest cost and it is
  modelled explicitly here rather than mentioned in a footnote.
* **Signal lag.** A regime observed at the close of day *T* is acted on at
  *T+1* at the earliest.

Amendment A2 also restricts evaluation to rebalance dates, so a mid-month
regime change is not acted on until the next rebalance. That is deliberate and
conservative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise

from indian_equity_research.research.regime import Regime

__all__ = [
    "OverlayConfig",
    "OverlayResult",
    "SwitchEvent",
    "apply_overlay",
    "buy_and_hold",
    "month_start_rebalance_dates",
]

#: Indian financial year starts in April.
_FY_START_MONTH = 4


@dataclass(frozen=True, slots=True)
class OverlayConfig:
    """Cost and tax parameters, as declared in Amendment A2.

    Attributes:
        initial_capital: Starting capital in rupees.
        round_trip_cost: Total explicit cost of a buy plus a sell, as a
            fraction of turnover. Charged as half on each leg.
        stcg_rate: Short-term capital gains rate for holdings under a year.
        ltcg_rate: Long-term capital gains rate.
        ltcg_exemption_per_year: Annual LTCG exemption in rupees.
        long_term_days: Holding period at which gains become long-term.
        signal_lag_days: Rebalance periods between observing a regime and
            acting on it.
    """

    initial_capital: float = 300_000.0
    round_trip_cost: float = 0.0055
    stcg_rate: float = 0.20
    ltcg_rate: float = 0.125
    ltcg_exemption_per_year: float = 125_000.0
    long_term_days: int = 365
    signal_lag_days: int = 1

    def __post_init__(self) -> None:
        """Reject parameters outside their meaningful ranges."""
        if self.initial_capital <= 0:
            message = f"initial_capital must be positive, got {self.initial_capital}."
            raise ValueError(message)
        if not 0.0 <= self.round_trip_cost < 1.0:
            message = f"round_trip_cost must be in [0, 1), got {self.round_trip_cost}."
            raise ValueError(message)
        for name, rate in (("stcg_rate", self.stcg_rate), ("ltcg_rate", self.ltcg_rate)):
            if not 0.0 <= rate < 1.0:
                message = f"{name} must be in [0, 1), got {rate}."
                raise ValueError(message)

    @property
    def one_way_cost(self) -> float:
        """Explicit cost of a single buy or sell, as a fraction of turnover."""
        return self.round_trip_cost / 2.0


@dataclass(frozen=True, slots=True)
class SwitchEvent:
    """A single entry into or exit from the market.

    Attributes:
        when: Date of the transaction.
        action: ``"EXIT"`` or ``"ENTER"``.
        value: Portfolio value transacted, before costs.
        cost: Explicit transaction cost paid.
        realised_gain: Gain realised on an exit; zero on an entry.
        tax_paid: Capital gains tax paid on an exit; zero on an entry.
        holding_days: Days held before an exit; zero on an entry.
    """

    when: date
    action: str
    value: float
    cost: float
    realised_gain: float = 0.0
    tax_paid: float = 0.0
    holding_days: int = 0


@dataclass(slots=True)
class OverlayResult:
    """Outcome of applying the overlay.

    Attributes:
        dates: Evaluation dates.
        pre_tax_curve: Equity after transaction costs, before tax.
        post_tax_curve: Equity after transaction costs and realised tax.
        switches: Every transaction, in order.
        total_costs: Sum of explicit transaction costs.
        total_tax: Sum of capital gains tax paid.
    """

    dates: list[date] = field(default_factory=list)
    pre_tax_curve: list[float] = field(default_factory=list)
    post_tax_curve: list[float] = field(default_factory=list)
    switches: list[SwitchEvent] = field(default_factory=list)
    total_costs: float = 0.0
    total_tax: float = 0.0

    @property
    def switch_count(self) -> int:
        """Number of transactions. One full cycle out and back is two."""
        return len(self.switches)

    @property
    def cycle_count(self) -> int:
        """Number of complete exit-and-re-enter cycles."""
        return sum(1 for s in self.switches if s.action == "EXIT")

    def returns(self, *, post_tax: bool = True) -> list[float]:
        """Periodic returns of the chosen curve.

        Args:
            post_tax: Use the post-tax curve when ``True``.

        Returns:
            Simple returns, of length ``len(dates) - 1``.
        """
        curve = self.post_tax_curve if post_tax else self.pre_tax_curve
        return [(b / a) - 1.0 for a, b in pairwise(curve)]


def month_start_rebalance_dates(dates: list[date]) -> set[date]:
    """Select the first available trading date in each calendar month.

    Args:
        dates: Trading dates in chronological order.

    Returns:
        The subset that begins a new month.
    """
    chosen: set[date] = set()
    seen: set[tuple[int, int]] = set()
    for d in dates:
        key = (d.year, d.month)
        if key not in seen:
            seen.add(key)
            chosen.add(d)
    return chosen


def _financial_year(when: date) -> int:
    """Return the Indian financial year a date falls in, labelled by start year."""
    return when.year if when.month >= _FY_START_MONTH else when.year - 1


def _tax_on_gain(
    gain: float,
    holding_days: int,
    financial_year: int,
    exemption_used: dict[int, float],
    config: OverlayConfig,
) -> float:
    """Compute capital gains tax, applying the annual LTCG exemption.

    Losses attract no tax and are not carried forward here; the experiment does
    not model set-off, which would flatter the overlay.

    Args:
        gain: Realised gain in rupees. Non-positive gains return zero tax.
        holding_days: Days the position was held.
        financial_year: Indian FY the realisation falls in.
        exemption_used: Mutable record of LTCG exemption consumed per FY.
        config: Cost and tax parameters.

    Returns:
        Tax payable in rupees.
    """
    if gain <= 0:
        return 0.0
    if holding_days < config.long_term_days:
        return gain * config.stcg_rate
    already_used = exemption_used.get(financial_year, 0.0)
    remaining = max(0.0, config.ltcg_exemption_per_year - already_used)
    shielded = min(gain, remaining)
    exemption_used[financial_year] = already_used + shielded
    return (gain - shielded) * config.ltcg_rate


def buy_and_hold(
    dates: list[date], closes: list[float], config: OverlayConfig | None = None
) -> OverlayResult:
    """The unoverlaid comparator: buy once, hold, realise nothing.

    Tax is deliberately zero. A buy-and-hold investor defers capital gains
    indefinitely, and pretending otherwise would understate the overlay's tax
    disadvantage.

    Args:
        dates: Evaluation dates.
        closes: Index closes, parallel to ``dates``.
        config: Cost parameters. One entry cost is charged.

    Returns:
        The comparator result.

    Raises:
        ValueError: If the inputs are empty or of differing length.
    """
    cfg = config or OverlayConfig()
    _validate(dates, closes)

    entry_cost = cfg.initial_capital * cfg.one_way_cost
    units = (cfg.initial_capital - entry_cost) / closes[0]
    curve = [units * c for c in closes]
    return OverlayResult(
        dates=list(dates),
        pre_tax_curve=curve,
        post_tax_curve=list(curve),
        switches=[SwitchEvent(dates[0], "ENTER", cfg.initial_capital, entry_cost)],
        total_costs=entry_cost,
        total_tax=0.0,
    )


def apply_overlay(
    dates: list[date],
    closes: list[float],
    states: list[Regime],
    *,
    cash_returns: list[float] | None = None,
    rebalance_dates: set[date] | None = None,
    config: OverlayConfig | None = None,
) -> OverlayResult:
    """Run the regime overlay over an index return stream.

    Args:
        dates: Evaluation dates in chronological order.
        closes: Index closes, parallel to ``dates``.
        states: Regime state per date. **Must already be lagged**; this
            function does not shift them, so the caller decides the lag and it
            is visible at the call site.
        cash_returns: Return earned while in cash, per period, of length
            ``len(dates) - 1``. Defaults to zero, which understates the
            overlay's benefit — the safe direction to be wrong in.
        rebalance_dates: Dates on which the regime may be acted upon. Defaults
            to the first trading day of each month.
        config: Cost and tax parameters.

    Returns:
        The overlaid result, with every transaction recorded.

    Raises:
        ValueError: If inputs are empty or inconsistent in length.
    """
    cfg = config or OverlayConfig()
    _validate(dates, closes)
    if len(states) != len(dates):
        message = f"states ({len(states)}) must match dates ({len(dates)})."
        raise ValueError(message)
    if cash_returns is not None and len(cash_returns) != len(dates) - 1:
        message = (
            f"cash_returns ({len(cash_returns)}) must have length len(dates) - 1 "
            f"({len(dates) - 1})."
        )
        raise ValueError(message)

    rebalances = (
        rebalance_dates if rebalance_dates is not None else month_start_rebalance_dates(dates)
    )
    exemption_used: dict[int, float] = {}
    result = OverlayResult()

    invested = False
    units = 0.0
    cash = cfg.initial_capital
    cost_basis = 0.0
    entry_date = dates[0]
    tax_paid_to_date = 0.0

    for i, (when, close) in enumerate(zip(dates, closes, strict=True)):
        # 1. Accrue cash return for the period just elapsed.
        if i > 0 and not invested and cash_returns is not None:
            cash *= 1.0 + cash_returns[i - 1]

        # 2. Act on the regime, but only on a rebalance date.
        if when in rebalances:
            desired_invested = states[i] is Regime.RISK_ON
            if desired_invested and not invested:
                cost = cash * cfg.one_way_cost
                deployed = cash - cost
                units = deployed / close
                cost_basis = deployed
                cash = 0.0
                invested = True
                entry_date = when
                result.total_costs += cost
                result.switches.append(SwitchEvent(when, "ENTER", deployed + cost, cost))
            elif not desired_invested and invested:
                gross = units * close
                cost = gross * cfg.one_way_cost
                proceeds = gross - cost
                gain = proceeds - cost_basis
                holding_days = (when - entry_date).days
                tax = _tax_on_gain(gain, holding_days, _financial_year(when), exemption_used, cfg)
                cash = proceeds - tax
                units = 0.0
                invested = False
                result.total_costs += cost
                result.total_tax += tax
                tax_paid_to_date += tax
                result.switches.append(
                    SwitchEvent(when, "EXIT", gross, cost, gain, tax, holding_days)
                )

        # 3. Mark to market.
        value = units * close if invested else cash
        result.dates.append(when)
        result.post_tax_curve.append(value)
        # Pre-tax curve adds back every rupee of tax paid so far, isolating the
        # tax drag from the transaction-cost drag.
        result.pre_tax_curve.append(value + tax_paid_to_date)

    return result


def _validate(dates: list[date], closes: list[float]) -> None:
    """Check that dated series are non-empty and aligned.

    Args:
        dates: Evaluation dates.
        closes: Values parallel to ``dates``.

    Raises:
        ValueError: If empty or of differing length.
    """
    if not dates or not closes:
        message = "dates and closes must not be empty."
        raise ValueError(message)
    if len(dates) != len(closes):
        message = f"dates ({len(dates)}) and closes ({len(closes)}) must be the same length."
        raise ValueError(message)
