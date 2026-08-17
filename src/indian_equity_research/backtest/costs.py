"""Itemised Indian equity transaction costs.

Every charge is modelled separately rather than as a flat basis-point
assumption, because the shape matters as much as the size. Two features of the
Indian schedule punish small portfolios specifically:

* **STT is charged on both legs** of a delivery trade at 0.1% each, so a round
  trip pays 0.2% in securities transaction tax alone.
* **DP charges are a flat rupee amount per SELL ORDER**, not a percentage. At a
  ₹25,000 order that is 0.09%; at ₹5,000 it is 0.47%. A flat-bps cost model
  hides this entirely, and it is precisely the term that makes a
  many-small-positions strategy unviable.

Rates are versioned by effective date. They change - STT on delivery was
altered in the 2024 budget cycle - and a backtest spanning a rate change that
applies today's schedule throughout is quietly wrong.

This schedule is **Groww-specific**
-----------------------------------
Validated to the paisa against real contract notes for 4 and 11 August 2026,
and reconciled against the funds ledger. See ``docs/cost_model_validation.md``.

Two brokers are not interchangeable here, and the difference is not only the
rate:

===============  ==========================  ==============================
Broker           DP charge                   Charging unit
===============  ==========================  ==============================
Groww            ₹20 + 18% GST = ₹23.60      **per sell order**
Zerodha          ₹13 + 18% GST = ₹15.34      per scrip per day
===============  ==========================  ==============================

The unit matters more than the rate. On 11 August 2026 one security was sold in
two orders and was charged **twice** -- ₹70.80 for two securities, not ₹47.20.
Under Zerodha's rule the same day would have cost ₹30.68.

What this module does NOT charge
--------------------------------
The ledger for the same account also carries margin interest, pledge and DDPI
fees, and a periodic account charge -- none of which appear on a contract note
and none of which are modelled here. That is correct for a pure cash-delivery
strategy and wrong for anything financed. See the validation document.

Sources: Groww published pricing and exchange circulars, retrieved 2026-08-04;
contract notes and funds ledger, 2026-08-18. **Verify before relying on these
for live trading.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

__all__ = [
    "ChargeBreakdown",
    "CostSchedule",
    "Side",
    "charges_for",
    "round_trip_cost",
    "schedule_for",
]


class Side(StrEnum):
    """Which side of a trade."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class CostSchedule:
    """One version of the charge schedule.

    Attributes:
        effective_from: First date this schedule applies.
        label: Human-readable identifier for reporting.
        brokerage_rate: Fraction of turnover.
        brokerage_cap: Maximum brokerage per order, in rupees.
        brokerage_floor: Minimum brokerage per order, in rupees.
        stt_buy: Securities transaction tax on the buy leg.
        stt_sell: Securities transaction tax on the sell leg.
        stamp_duty_buy: Stamp duty, charged on purchases only.
        exchange_txn_rate: Exchange transaction charge.
        sebi_turnover_rate: SEBI turnover fee.
        ipft_rate: Investor protection fund contribution.
        gst_rate: GST, applied to brokerage and the exchange-side fees.
        dp_charge_per_sell_order: Flat depository charge per **sell order**,
            before GST. Not per scrip and not per fill: an order filled in two
            trades is charged once, while a security sold in two orders is
            charged twice. Verified against the 11 August 2026 contract note.
    """

    effective_from: date
    label: str
    brokerage_rate: float = 0.001
    brokerage_cap: float = 20.0
    brokerage_floor: float = 5.0
    stt_buy: float = 0.001
    stt_sell: float = 0.001
    stamp_duty_buy: float = 0.00015
    exchange_txn_rate: float = 0.0000297
    sebi_turnover_rate: float = 0.000001
    ipft_rate: float = 0.000001
    gst_rate: float = 0.18
    dp_charge_per_sell_order: float = 20.0


#: Schedules in effect order. Extend rather than edit: a backtest spanning a
#: rate change must apply the rate that was actually in force.
SCHEDULES: tuple[CostSchedule, ...] = (
    CostSchedule(effective_from=date(2015, 1, 1), label="pre-2024"),
    CostSchedule(effective_from=date(2024, 10, 1), label="current"),
)


def schedule_for(when: date) -> CostSchedule:
    """Return the schedule in force on a date.

    Args:
        when: Trade date.

    Returns:
        The latest schedule effective on or before ``when``.

    Raises:
        ValueError: If the date precedes every known schedule.
    """
    applicable = [s for s in SCHEDULES if s.effective_from <= when]
    if not applicable:
        message = (
            f"No cost schedule covers {when.isoformat()}; the earliest known "
            f"is {SCHEDULES[0].effective_from.isoformat()}."
        )
        raise ValueError(message)
    return max(applicable, key=lambda s: s.effective_from)


@dataclass(frozen=True, slots=True)
class ChargeBreakdown:
    """Every charge on one order, itemised.

    Attributes:
        turnover: Order value in rupees.
        side: Buy or sell.
        brokerage: Broker commission before GST.
        stt: Securities transaction tax.
        stamp_duty: Stamp duty.
        exchange_txn: Exchange transaction charge.
        sebi_fee: SEBI turnover fee.
        ipft: Investor protection fund contribution.
        dp_charge: Depository charge before GST.
        gst: GST on brokerage, exchange, SEBI, IPFT and DP charges.
        gst_rate: Rate applied, retained so the fixed component can be
            reported inclusive of tax.
        schedule_label: Which rate version was applied.
    """

    turnover: float
    side: Side
    brokerage: float
    stt: float
    stamp_duty: float
    exchange_txn: float
    sebi_fee: float
    ipft: float
    dp_charge: float
    gst: float
    gst_rate: float
    schedule_label: str

    @property
    def total(self) -> float:
        """Total cost of the order in rupees."""
        return (
            self.brokerage
            + self.stt
            + self.stamp_duty
            + self.exchange_txn
            + self.sebi_fee
            + self.ipft
            + self.dp_charge
            + self.gst
        )

    @property
    def as_fraction(self) -> float:
        """Total cost as a fraction of turnover."""
        return self.total / self.turnover if self.turnover > 0 else 0.0

    @property
    def fixed_component(self) -> float:
        """Charges that do not scale with order size, inclusive of GST.

        The DP charge is a flat rupee amount per sell order. It is 0.09% of a
        Rs 25,000 position and 0.47% of a Rs 5,000 one - the term that makes a
        many-small-positions strategy unviable, and the one a flat
        basis-point cost model hides completely.
        """
        return self.dp_charge * (1.0 + self.gst_rate)

    def itemised(self) -> dict[str, float]:
        """Return the breakdown as a mapping, for reporting."""
        return {
            "brokerage": self.brokerage,
            "stt": self.stt,
            "stamp_duty": self.stamp_duty,
            "exchange_txn": self.exchange_txn,
            "sebi_fee": self.sebi_fee,
            "ipft": self.ipft,
            "dp_charge": self.dp_charge,
            "gst": self.gst,
        }


def charges_for(
    turnover: float,
    side: Side,
    when: date,
    *,
    schedule: CostSchedule | None = None,
    sell_orders: float = 1.0,
) -> ChargeBreakdown:
    """Compute every charge on a delivery exit or entry.

    Args:
        turnover: Total value in rupees. Must not be negative.
        side: Buy or sell.
        when: Trade date, used to select the rate schedule.
        schedule: Explicit schedule, overriding date-based selection.
        sell_orders: How many sell orders the exit takes. The DP charge is
            levied **per order**, so an exit worked in three slices pays it
            three times. Ignored on the buy side, where no DP charge applies.
            Defaults to 1, which is the optimistic case.

    Returns:
        The itemised breakdown.

    Raises:
        ValueError: If ``turnover`` is negative or ``sell_orders`` is below 1.
    """
    if turnover < 0:
        message = f"turnover must not be negative, got {turnover}."
        raise ValueError(message)
    if sell_orders < 1.0:
        raise ValueError(f"sell_orders must be at least 1, got {sell_orders}")
    if turnover == 0:
        cfg = schedule or schedule_for(when)
        return ChargeBreakdown(0.0, side, 0, 0, 0, 0, 0, 0, 0, 0, cfg.gst_rate, cfg.label)

    cfg = schedule or schedule_for(when)
    # Percentage of turnover, capped for large orders, floored for small ones.
    brokerage = max(min(turnover * cfg.brokerage_rate, cfg.brokerage_cap), cfg.brokerage_floor)

    is_buy = side is Side.BUY
    stt = turnover * (cfg.stt_buy if is_buy else cfg.stt_sell)
    stamp = turnover * cfg.stamp_duty_buy if is_buy else 0.0
    exchange = turnover * cfg.exchange_txn_rate
    sebi = turnover * cfg.sebi_turnover_rate
    ipft = turnover * cfg.ipft_rate
    dp = 0.0 if is_buy else cfg.dp_charge_per_sell_order * sell_orders
    gst = (brokerage + exchange + sebi + ipft + dp) * cfg.gst_rate

    return ChargeBreakdown(
        turnover=turnover,
        side=side,
        brokerage=brokerage,
        stt=stt,
        stamp_duty=stamp,
        exchange_txn=exchange,
        sebi_fee=sebi,
        ipft=ipft,
        dp_charge=dp,
        gst=gst,
        gst_rate=cfg.gst_rate,
        schedule_label=cfg.label,
    )


def round_trip_cost(
    position_value: float, when: date, *, schedule: CostSchedule | None = None
) -> float:
    """Total cost of buying and later selling a position of a given size.

    Args:
        position_value: Position value in rupees, assumed equal on both legs.
        when: Trade date, for rate selection.
        schedule: Explicit schedule.

    Returns:
        Combined buy and sell charges in rupees.
    """
    buy = charges_for(position_value, Side.BUY, when, schedule=schedule)
    sell = charges_for(position_value, Side.SELL, when, schedule=schedule)
    return buy.total + sell.total
