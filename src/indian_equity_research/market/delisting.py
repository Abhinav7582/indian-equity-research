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
    "ClassificationConfig",
    "DelistingOutcome",
    "DelistingRecord",
    "DelistingRegister",
    "TerminalReturnPolicy",
    "build_delisting_register",
    "classify_delisting",
]

#: A security absent for at least this long, with the market still trading, is
#: treated as gone rather than merely suspended. Indian suspensions frequently
#: run for months, so a short window would misclassify them.
DEFAULT_ABSENCE_DAYS = 180

#: Sessions before delisting over which the peak is taken - roughly a year.
DEFAULT_TRAILING_WINDOW = 250
#: Sessions before the end used for the terminal-slide measure - roughly a
#: quarter, short enough to catch a sharp final fall.
DEFAULT_SLIDE_WINDOW = 60


class DelistingOutcome(StrEnum):
    """What a delisting most likely was, judged from the final trajectory.

    The evidence for these labels is weak and one-sided, so they stay
    ``LIKELY_``. Neither histogram of the real data was bimodal: only the
    extremes are separable, and roughly two thirds of delistings fall in
    between and are honestly ``UNCERTAIN``.
    """

    #: Rising into the delisting - the price converging toward an offer.
    LIKELY_ACQUISITION = "LIKELY_ACQUISITION"
    #: Ended far below its own recent peak.
    LIKELY_COLLAPSE = "LIKELY_COLLAPSE"
    #: Not separable from price data. The majority.
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class ClassificationConfig:
    """Thresholds separating the classifiable tails from the ambiguous middle.

    These are **declared, not tuned**. They come from reading the observed
    distribution once - 29% of delistings rose in their final 60 sessions, 8%
    ended below a tenth of their annual peak - and are fixed in Amendment A4.
    Moving them to improve a result would be fitting the delisting assumption
    to the answer.

    Attributes:
        acquisition_slide_threshold: ``terminal_slide`` at or above which a
            delisting is read as an acquisition. A price rising into its final
            session is the signature of converging toward an offer.
        collapse_peak_threshold: ``final_decline`` at or below which a
            delisting is read as a collapse.
    """

    acquisition_slide_threshold: float = 1.05
    collapse_peak_threshold: float = 0.10


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
    #: Use the classification: acquisitions recover the last close, collapses
    #: recover nothing, and the uncertain majority is refused. Narrows the
    #: uncertainty band without pretending the middle is knowable.
    CLASSIFIED = "CLASSIFIED"


@dataclass(frozen=True, slots=True)
class DelistingRecord:
    """One security that stopped trading.

    Attributes:
        isin: Security.
        last_symbol: Ticker as at the final session.
        first_seen: Earliest session observed.
        last_seen: Final session observed.
        first_close: Close on the first session observed.
        last_close: Close on the final session.
        peak_close: Highest close within the trailing window before delisting.
            Comparing the last close to this - rather than to the first close
            - is what distinguishes *how a security ended* from *how it did
            over its life*. A company can triple over eight years and then
            collapse in its final six months; measured against its first
            price those two facts are indistinguishable.
        close_before_end: Close roughly ``slide_window`` sessions before the
            final one, for measuring the terminal slide.
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
    first_close: float
    last_close: float
    peak_close: float
    close_before_end: float
    sessions_observed: int
    absent_days: int
    still_listed: bool
    policy: TerminalReturnPolicy = TerminalReturnPolicy.UNKNOWN

    @property
    def final_decline(self) -> float:
        """Last close as a fraction of the trailing-window peak.

        An acquisition delists near its recent high, often at a premium. A
        collapse delists far below it. This is the discriminating measure;
        :attr:`decline_from_first` is not, because it is confounded by however
        long the security happened to trade.
        """
        if self.peak_close <= 0:
            return 0.0
        return self.last_close / self.peak_close

    @property
    def terminal_slide(self) -> float:
        """Last close as a fraction of the close shortly before the end.

        Captures a sharp final fall that a longer window would dilute.
        """
        if self.close_before_end <= 0:
            return 0.0
        return self.last_close / self.close_before_end

    @property
    def decline_from_first(self) -> float:
        """Fraction of the first observed price still standing at the end.

        ``0.02`` means the security ended at 2% of where it was first seen -
        already worthless before it delisted.
        """
        if self.first_close <= 0:
            return 0.0
        return self.last_close / self.first_close

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
    trailing_window: int = DEFAULT_TRAILING_WINDOW,
    slide_window: int = DEFAULT_SLIDE_WINDOW,
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
        trailing_window: Sessions before delisting over which the peak close
            is taken.
        slide_window: Sessions before the end used for the terminal-slide
            measure.

    Returns:
        The register.

    Raises:
        ValueError: If no records are supplied.
    """
    history: dict[str, list[tuple[date, float, str]]] = {}
    dataset_end: date | None = None
    for record in records:
        history.setdefault(record.isin, []).append((record.trade_date, record.close, record.symbol))
        if dataset_end is None or record.trade_date > dataset_end:
            dataset_end = record.trade_date

    if dataset_end is None:
        message = "Cannot build a delisting register from no records."
        raise ValueError(message)

    cutoff = dataset_end - timedelta(days=absence_days)
    listed = currently_listed or set()
    out: dict[str, DelistingRecord] = {}
    for isin, rows in history.items():
        rows.sort()
        final_date, final_close, final_symbol = rows[-1]
        if final_date > cutoff:
            continue
        trailing = rows[-trailing_window:]
        slide_index = max(0, len(rows) - 1 - slide_window)
        out[isin] = DelistingRecord(
            isin=isin,
            last_symbol=final_symbol,
            first_seen=rows[0][0],
            last_seen=final_date,
            first_close=rows[0][1],
            last_close=final_close,
            peak_close=max(close for _, close, _ in trailing),
            close_before_end=rows[slide_index][1],
            sessions_observed=len(rows),
            absent_days=(dataset_end - final_date).days,
            still_listed=isin in listed,
            policy=policy,
        )
    return DelistingRegister(records=out, dataset_end=dataset_end, absence_days=absence_days)


def classify_delisting(
    record: DelistingRecord, config: ClassificationConfig | None = None
) -> DelistingOutcome:
    """Read a delisting's final trajectory.

    The collapse test runs first. A security can both sit far below its annual
    peak *and* have risen over its final quarter - a dead-cat bounce before
    the end - and that is a collapse, not an acquisition.

    Args:
        record: The delisting record.
        config: Thresholds. Defaults to the values declared in Amendment A4.

    Returns:
        The most likely outcome, or ``UNCERTAIN`` where the price data does
        not separate them.
    """
    cfg = config or ClassificationConfig()
    if record.final_decline <= cfg.collapse_peak_threshold:
        return DelistingOutcome.LIKELY_COLLAPSE
    if record.terminal_slide >= cfg.acquisition_slide_threshold:
        return DelistingOutcome.LIKELY_ACQUISITION
    return DelistingOutcome.UNCERTAIN
