"""Delisting register derived from the bhavcopy record itself.

No exchange publishes a clean historical delisting file. But the bhavcopy is
ground truth about what traded: a security that appears every session for
years and then never appears again has, in effect, left the market. Deriving
the register from observed data avoids depending on a list that does not
exist.

Why this matters more than it sounds
------------------------------------
Of the 3,905 securities in eleven years of NSE data, roughly 1,500 are not in
today's instrument master. They are disproportionately the ones with violent
price histories - collapses, frauds, suspensions. A universe built from
today's listings silently deletes every one of them, and with them every
disaster a strategy would have had to survive.

The terminal return problem
---------------------------
What a holder actually recovered on delisting is **not** in the price data. A
compulsory delisting after a fraud finding usually returns nothing; a
voluntary delisting via buyback returns the offer price. This module refuses
to guess: it records the last observed price and a
:class:`TerminalReturnPolicy`, and the backtest decides. Assuming the last
traded price was recoverable is the optimistic error, and it is the one that
flatters results.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from indian_equity_research.market.bhavcopy import BhavRecord

__all__ = [
    "DelistingRecord",
    "DelistingRegister",
    "TerminalReturnPolicy",
    "build_delisting_register",
]

#: A security absent for at least this long, with the market still trading, is
#: treated as gone rather than merely suspended. Indian suspensions frequently
#: run for months, so a short window would misclassify them.
DEFAULT_ABSENCE_DAYS = 180


class TerminalReturnPolicy(StrEnum):
    """How a backtest should treat the final holding.

    Attributes are policies, not observations: none of this is recoverable
    from price data alone.
    """

    #: Assume the position was liquidated at the last observed close. The
    #: optimistic assumption, and usually wrong for a collapse.
    LAST_PRICE = "LAST_PRICE"
    #: Assume a total loss. Appropriate for compulsory delistings and fraud.
    TOTAL_LOSS = "TOTAL_LOSS"
    #: Refuse to assume. The backtest must exclude the security or supply a
    #: documented recovery value.
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DelistingRecord:
    """One security that stopped trading.

    Attributes:
        isin: Security.
        last_symbol: Ticker as at the final session.
        first_seen: Earliest session observed.
        last_seen: Final session observed.
        last_close: Close on the final session.
        sessions_observed: Number of sessions the security traded.
        absent_days: Calendar days between the final session and the end of
            the dataset.
        still_listed: Whether the security is in the current instrument
            master. A security absent from the data but present in the master
            is suspended, not delisted.
        policy: Recommended terminal-return treatment.
    """

    isin: str
    last_symbol: str
    first_seen: date
    last_seen: date
    last_close: float
    sessions_observed: int
    absent_days: int
    still_listed: bool
    policy: TerminalReturnPolicy = TerminalReturnPolicy.UNKNOWN

    @property
    def is_suspended_not_delisted(self) -> bool:
        """Whether the security stopped trading but remains listed."""
        return self.still_listed


@dataclass(frozen=True, slots=True)
class DelistingRegister:
    """Every security that stopped trading, with what is and is not known.

    Attributes:
        records: Delisting records, keyed by ISIN.
        dataset_end: Final session in the source data.
        absence_days: Threshold used.
    """

    records: dict[str, DelistingRecord]
    dataset_end: date
    absence_days: int

    def __len__(self) -> int:
        """Return the number of securities that stopped trading."""
        return len(self.records)

    @property
    def delisted(self) -> list[DelistingRecord]:
        """Securities absent from the data **and** from today's master."""
        return [r for r in self.records.values() if not r.still_listed]

    @property
    def suspended(self) -> list[DelistingRecord]:
        """Securities absent from the data but still listed today."""
        return [r for r in self.records.values() if r.still_listed]

    def summary(self) -> str:
        """Return a one-line description of the register."""
        return (
            f"{len(self.delisted):,} delisted, {len(self.suspended):,} suspended-but-listed, "
            f"threshold {self.absence_days} days, dataset ends {self.dataset_end}"
        )


def build_delisting_register(
    records: Iterable[BhavRecord],
    currently_listed: set[str] | None = None,
    *,
    absence_days: int = DEFAULT_ABSENCE_DAYS,
    policy: TerminalReturnPolicy = TerminalReturnPolicy.UNKNOWN,
) -> DelistingRegister:
    """Derive a delisting register from observed trading.

    Args:
        records: Bhavcopy records spanning the full history.
        currently_listed: ISINs in today's instrument master. When supplied,
            a security missing from the data but present here is classified as
            suspended rather than delisted - a distinction that matters,
            because a suspension can end.
        absence_days: Days of absence before a security counts as gone.
        policy: Terminal-return treatment recorded against each entry. The
            default refuses to assume anything.

    Returns:
        The register.

    Raises:
        ValueError: If no records are supplied.
    """
    last_seen: dict[str, date] = {}
    first_seen: dict[str, date] = {}
    last_close: dict[str, float] = {}
    last_symbol: dict[str, str] = {}
    sessions: dict[str, int] = {}

    dataset_end: date | None = None
    for record in records:
        isin = record.isin
        sessions[isin] = sessions.get(isin, 0) + 1
        if isin not in first_seen or record.trade_date < first_seen[isin]:
            first_seen[isin] = record.trade_date
        if isin not in last_seen or record.trade_date > last_seen[isin]:
            last_seen[isin] = record.trade_date
            last_close[isin] = record.close
            last_symbol[isin] = record.symbol
        if dataset_end is None or record.trade_date > dataset_end:
            dataset_end = record.trade_date

    if dataset_end is None:
        message = "Cannot build a delisting register from no records."
        raise ValueError(message)

    cutoff = dataset_end - timedelta(days=absence_days)
    listed = currently_listed or set()
    out: dict[str, DelistingRecord] = {}
    for isin, final in last_seen.items():
        if final > cutoff:
            continue
        out[isin] = DelistingRecord(
            isin=isin,
            last_symbol=last_symbol[isin],
            first_seen=first_seen[isin],
            last_seen=final,
            last_close=last_close[isin],
            sessions_observed=sessions[isin],
            absent_days=(dataset_end - final).days,
            still_listed=isin in listed,
            policy=policy,
        )
    return DelistingRegister(records=out, dataset_end=dataset_end, absence_days=absence_days)
