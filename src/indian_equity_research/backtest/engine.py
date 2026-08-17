"""Event-driven daily backtest engine.

Design position
---------------
The purpose of this engine is not to produce good-looking results. It is to
produce results that would be *wrong in a detectable way* if the code were
wrong. Three properties are therefore enforced structurally rather than by
convention, because conventions are what fail silently:

**1. The future is unreachable, not merely unused.**
A strategy never receives the price series. It receives a :class:`PriceView`
pinned to a decision date, which raises :class:`LookAheadError` if asked about
any later date. A leak becomes an exception at the moment it is attempted,
rather than a good Sharpe ratio six months later.

**2. Signals and fills are separated in time by construction.**
A signal computed from the close of day *t* fills at the **open of day t+1**.
There is no code path that fills at the close of the decision day, so
"accidentally trading on the bar you decided from" is not a bug that can be
introduced by a careless edit -- the required price is not in scope.

**3. Costs are charged per order, from the dated schedule.**
Not modelled as a spread, not netted, not approximated as a round-trip
percentage. Every order is priced through
:func:`~indian_equity_research.backtest.costs.charges_for` at the schedule in
force on the fill date, because that is where the Indian charge structure
actually bites: STT on both legs, stamp duty on buys only, and a flat DP charge
per scrip sold that makes small positions disproportionately expensive.

What this engine deliberately does not do
-----------------------------------------
No shorting, no leverage, no intraday, no derivatives. Fills are assumed to
occur at the open in full, with no market impact and no partial fills. For a
retail book inside the Nifty 100 that is defensible; it would not be for a
large one, and it is recorded here so the assumption is visible rather than
implied.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Final

from indian_equity_research.backtest.costs import ChargeBreakdown, CostSchedule, Side, charges_for

__all__ = [
    "BacktestResult",
    "Bar",
    "EngineConfig",
    "Fill",
    "LookAheadError",
    "PriceView",
    "Strategy",
    "run_backtest",
]

_EPSILON: Final = 1e-9


class LookAheadError(LookupError):
    """Raised when a strategy asks for data it could not have had.

    This is deliberately an error rather than a silent ``None``. A strategy
    that reaches into the future is not a strategy with a small defect; it is
    not a strategy at all, and every number downstream of it is void.
    """


@dataclass(frozen=True, slots=True)
class Bar:
    """One security on one session."""

    date: dt.date
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        """Reject bars that cannot represent a real session."""
        for name in ("open", "high", "low", "close"):
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")
        if self.low > self.high:
            raise ValueError(f"low {self.low} exceeds high {self.high} on {self.date}")


@dataclass(frozen=True, slots=True)
class Fill:
    """An executed order, with its charges."""

    date: dt.date
    symbol: str
    side: Side
    quantity: int
    price: float
    charges: ChargeBreakdown

    @property
    def turnover(self) -> float:
        """Order value in rupees, before charges."""
        return self.quantity * self.price

    @property
    def cash_delta(self) -> float:
        """Signed effect on cash, charges included."""
        if self.side is Side.BUY:
            return -(self.turnover + self.charges.total)
        return self.turnover - self.charges.total


class PriceView:
    """A window onto market data that ends at ``as_of``.

    Every accessor refuses dates after ``as_of``. This is the single mechanism
    preventing look-ahead, so it is intentionally strict: there is no lenient
    mode and no override parameter.
    """

    __slots__ = ("_data", "_sessions", "as_of")

    def __init__(
        self,
        data: Mapping[str, Mapping[dt.date, Bar]],
        sessions: Sequence[dt.date],
        as_of: dt.date,
    ) -> None:
        """Pin a view of ``data`` to the session ``as_of``."""
        self._data = data
        self._sessions = sessions
        self.as_of = as_of

    def symbols(self) -> tuple[str, ...]:
        """Symbols with at least one bar on or before ``as_of``."""
        return tuple(
            sorted(s for s, bars in self._data.items() if any(d <= self.as_of for d in bars))
        )

    def bar(self, symbol: str, when: dt.date) -> Bar | None:
        """The bar for ``symbol`` on ``when``, or ``None`` if it did not trade.

        Raises:
            LookAheadError: if ``when`` is after ``as_of``.
        """
        if when > self.as_of:
            raise LookAheadError(
                f"asked for {symbol} on {when} while standing on {self.as_of}. "
                f"That data did not exist yet."
            )
        return self._data.get(symbol, {}).get(when)

    def close(self, symbol: str) -> float | None:
        """Closing price on ``as_of``, or ``None`` if it did not trade."""
        bar = self.bar(symbol, self.as_of)
        return bar.close if bar else None

    def history(self, symbol: str, lookback: int) -> tuple[Bar, ...]:
        """The most recent ``lookback`` bars up to and including ``as_of``.

        Returns fewer than ``lookback`` bars if the security has less history.
        Never returns anything dated after ``as_of``.
        """
        if lookback <= 0:
            raise ValueError(f"lookback must be positive, got {lookback}")
        bars = self._data.get(symbol, {})
        available = [bars[d] for d in sorted(bars) if d <= self.as_of]
        return tuple(available[-lookback:])


# A strategy maps a pinned view of the past onto target portfolio weights.
# Weights are fractions of total portfolio value; they must be non-negative and
# must not sum above 1.0. Anything omitted is treated as a target of zero.
Strategy = Callable[[PriceView], Mapping[str, float]]


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Fixed parameters of a run."""

    initial_capital: float = 300_000.0
    allow_fractional_shares: bool = False
    schedule: CostSchedule | None = None
    # Trades below this rupee value are skipped. A flat DP charge makes tiny
    # rebalancing trades value-destroying, and executing them anyway would
    # understate the drag a real book suffers from constant small adjustments.
    minimum_trade_value: float = 1_000.0
    # Largest permitted gap between consecutive sessions. Anything longer is
    # almost always missing data rather than a genuine market closure -- the
    # longest real NSE closure in modern history is a handful of days. Set to
    # None only when a gap is known to be genuine, and say why at the call site.
    max_session_gap_days: int | None = 10
    # Sell orders the engine assumes each exit takes. The DP charge is levied
    # **per sell order**, not per position -- verified against a real contract
    # note where one security sold in two orders was charged twice
    # (docs/cost_model_validation.md).
    #
    # The default of 1 is the OPTIMISTIC case: every exit fills in a single
    # order. Real execution splits when liquidity requires it, and each slice
    # costs another Rs 23.60. This is exposed and reported rather than assumed
    # silently, because at Rs 3,000 positions it is the difference between a
    # 0.79% and a 1.18% cost of one full turnover.
    sell_orders_per_exit: float = 1.0

    def __post_init__(self) -> None:
        """Reject configurations that cannot describe a real portfolio."""
        if self.sell_orders_per_exit < 1.0:
            raise ValueError(
                f"sell_orders_per_exit must be at least 1, got {self.sell_orders_per_exit}. "
                f"An exit takes at least one order; a value below 1 would model a "
                f"position leaving the book without being sold."
            )
        if self.initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {self.initial_capital}")
        if self.minimum_trade_value < 0:
            raise ValueError("minimum_trade_value must not be negative")
        if self.max_session_gap_days is not None and self.max_session_gap_days < 1:
            raise ValueError(
                f"max_session_gap_days must be positive or None, got {self.max_session_gap_days}"
            )


@dataclass
class BacktestResult:
    """Everything a run produced, including what it cost."""

    dates: list[dt.date] = field(default_factory=list)
    equity: list[float] = field(default_factory=list)
    cash: list[float] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    config: EngineConfig = field(default_factory=EngineConfig)

    @property
    def final_equity(self) -> float:
        """Portfolio value on the last session."""
        return self.equity[-1] if self.equity else self.config.initial_capital

    @property
    def total_charges(self) -> float:
        """Every charge paid across every fill."""
        return sum(f.charges.total for f in self.fills)

    @property
    def total_turnover(self) -> float:
        """Gross value traded across every fill."""
        return sum(f.turnover for f in self.fills)

    def charges_by_component(self) -> dict[str, float]:
        """Charges summed by component, so the drag can be attributed."""
        totals: dict[str, float] = {}
        for fill in self.fills:
            for name, value in fill.charges.itemised().items():
                totals[name] = totals.get(name, 0.0) + value
        return totals


def run_backtest(
    data: Mapping[str, Mapping[dt.date, Bar]],
    sessions: Sequence[dt.date],
    strategy: Strategy,
    *,
    config: EngineConfig | None = None,
    rebalance_on: Callable[[dt.date], bool] | None = None,
) -> BacktestResult:
    """Run ``strategy`` over ``sessions``.

    On each session the strategy sees a :class:`PriceView` pinned to that date
    and returns target weights. Resulting orders fill at the **open of the next
    session**. The final session can therefore produce no fills, which is
    correct: there is no next open to trade at.

    Args:
        data: ``{symbol: {date: Bar}}``. Missing dates mean the security did
            not trade, not that its price was unchanged.
        sessions: Trading dates, ascending. Must be sorted and unique.
        strategy: Called once per session on which ``rebalance_on`` is true.
        config: Engine parameters.
        rebalance_on: Predicate selecting decision dates. Defaults to every
            session.

    Returns:
        The result, including every fill and every charge.

    Raises:
        ValueError: if ``sessions`` is empty, unsorted or contains duplicates.
        LookAheadError: propagated if the strategy reaches into the future.
    """
    cfg = config or EngineConfig()
    if not sessions:
        raise ValueError("sessions must not be empty")
    if list(sessions) != sorted(set(sessions)):
        raise ValueError("sessions must be sorted ascending and free of duplicates")
    _check_session_continuity(sessions, cfg.max_session_gap_days)

    decide = rebalance_on or (lambda _: True)
    cash = cfg.initial_capital
    holdings: dict[str, int] = {}
    result = BacktestResult(config=cfg)
    # None means "no decision is outstanding". An *empty dict* means "the
    # strategy decided to hold nothing", which is a real instruction to sell
    # everything. Conflating the two -- by testing `if pending:` -- would make
    # a strategy that goes to cash silently stay invested forever, and would
    # report buy-and-hold returns for a market-timing rule. Caught by
    # test_a_pointless_round_trip_loses_exactly_the_charges.
    pending: dict[str, float] | None = None

    for index, today in enumerate(sessions):
        # --- 1. Execute what yesterday decided, at today's open -------------
        if pending is not None:
            cash = _execute(pending, holdings, cash, data, today, cfg, result)
            pending = None

        # --- 2. Mark to market on today's close -----------------------------
        equity = cash + _position_value(holdings, data, today)
        result.dates.append(today)
        result.equity.append(equity)
        result.cash.append(cash)

        # --- 3. Decide, using only what today's close made available --------
        is_last = index == len(sessions) - 1
        if is_last or not decide(today):
            continue
        view = PriceView(data, sessions, today)
        targets = strategy(view)
        _validate_targets(targets, today)
        pending = dict(targets)

    return result


def _check_session_continuity(sessions: Sequence[dt.date], limit: int | None) -> None:
    """Refuse to run across a hole in the session calendar.

    Missing data does not announce itself. A year absent from the archive looks
    exactly like one very eventful trading day: the engine holds positions
    across it, marks them at the last available close, and then books the whole
    period's move as a single-session return.

    That single return is then annualised as if it spanned one day, which
    inflates every risk statistic downstream. Measured on this project's own
    data, a 366-day gap raised the Sharpe ratio from 0.817 to 0.961 -- an 18%
    improvement produced entirely by absent files.

    Nothing about the resulting equity curve looks wrong, which is why this has
    to be a hard failure rather than a warning.
    """
    if limit is None or len(sessions) < 2:
        return
    # itertools.pairwise, not zip(sessions, sessions[1:], strict=True).
    # The strict form raises on every input, because the two sequences differ
    # in length by one by construction. This is the third time that exact
    # mistake has been made in this repository -- see market/calendar.py and
    # research/series.py -- which is why it is written down here.
    gaps = [(a, b, (b - a).days) for a, b in pairwise(sessions) if (b - a).days > limit]
    if not gaps:
        return
    worst = max(gaps, key=lambda g: g[2])
    raise ValueError(
        f"session calendar has {len(gaps)} gap(s) longer than {limit} days; "
        f"the largest is {worst[2]} days ({worst[0]} to {worst[1]}). "
        f"This is almost certainly missing data, and running across it would "
        f"annualise that whole period as a single session. Fill the gap, or "
        f"pass max_session_gap_days=None if the closure is genuine."
    )


def _validate_targets(targets: Mapping[str, float], when: dt.date) -> None:
    """Reject weights that imply shorting or leverage."""
    for symbol, weight in targets.items():
        if weight < 0:
            raise ValueError(f"negative target weight {weight} for {symbol} on {when}: no shorting")
    total = sum(targets.values())
    if total > 1.0 + _EPSILON:
        raise ValueError(f"target weights sum to {total:.6f} on {when}: no leverage")


def _position_value(
    holdings: Mapping[str, int], data: Mapping[str, Mapping[dt.date, Bar]], when: dt.date
) -> float:
    """Mark holdings at ``when``'s close, carrying the last close forward.

    A security that did not trade is not worth zero. The most recent close is
    the honest estimate, and it is what a broker statement would show.
    """
    total = 0.0
    for symbol, quantity in holdings.items():
        if quantity == 0:
            continue
        bars = data.get(symbol, {})
        candidates = [d for d in bars if d <= when]
        if not candidates:
            continue
        total += quantity * bars[max(candidates)].close
    return total


def _execute(
    targets: Mapping[str, float],
    holdings: dict[str, int],
    cash: float,
    data: Mapping[str, Mapping[dt.date, Bar]],
    when: dt.date,
    cfg: EngineConfig,
    result: BacktestResult,
) -> float:
    """Trade toward ``targets`` at ``when``'s open. Returns updated cash."""
    opens: dict[str, float] = {}
    for symbol in set(targets) | set(holdings):
        bar = data.get(symbol, {}).get(when)
        if bar is not None:
            opens[symbol] = bar.open

    equity = cash + _position_value(holdings, data, when)

    desired: dict[str, int] = {}
    for symbol, price in opens.items():
        weight = targets.get(symbol, 0.0)
        raw = (equity * weight) / price
        desired[symbol] = int(raw) if not cfg.allow_fractional_shares else raw  # type: ignore[assignment]

    # Sell first: a real account cannot spend proceeds it has not received,
    # and settlement aside, ordering sells before buys is the conservative
    # assumption. Doing it the other way round would quietly assume credit.
    for symbol in sorted(opens):
        delta = desired.get(symbol, 0) - holdings.get(symbol, 0)
        if delta < 0:
            cash = _fill(
                symbol, Side.SELL, -delta, opens[symbol], when, cfg, holdings, cash, result
            )
    for symbol in sorted(opens):
        delta = desired.get(symbol, 0) - holdings.get(symbol, 0)
        if delta > 0:
            cash = _fill(symbol, Side.BUY, delta, opens[symbol], when, cfg, holdings, cash, result)
    return cash


def _fill(
    symbol: str,
    side: Side,
    quantity: float,
    price: float,
    when: dt.date,
    cfg: EngineConfig,
    holdings: dict[str, int],
    cash: float,
    result: BacktestResult,
) -> float:
    """Record one order if it is worth doing, and return updated cash."""
    turnover = quantity * price
    if quantity <= 0 or turnover < cfg.minimum_trade_value:
        return cash

    charges = charges_for(
        turnover, side, when, schedule=cfg.schedule, sell_orders=cfg.sell_orders_per_exit
    )
    if side is Side.BUY and turnover + charges.total > cash + _EPSILON:
        # Trim to what the cash will actually bear, charges included, rather
        # than allowing an overdraft the constraint forbids.
        affordable = int((cash - charges.total) / price)
        if affordable <= 0:
            return cash
        quantity = affordable
        turnover = quantity * price
        if turnover < cfg.minimum_trade_value:
            return cash
        charges = charges_for(
            turnover, side, when, schedule=cfg.schedule, sell_orders=cfg.sell_orders_per_exit
        )

    fill = Fill(when, symbol, side, int(quantity), price, charges)
    result.fills.append(fill)
    holdings[symbol] = holdings.get(symbol, 0) + (
        int(quantity) if side is Side.BUY else -int(quantity)
    )
    return cash + fill.cash_delta
