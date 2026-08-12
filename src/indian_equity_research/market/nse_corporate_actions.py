"""Parse NSE's corporate-actions feed into documented :class:`CorporateAction`.

Why a documented feed is required
---------------------------------
The adjustment engine can infer a multiplier from an unexplained price move.
That is unsafe here, and the archive says so plainly. Every line below is a real
single-day move in a liquid NSE security, checked against the downloaded feed:

    RELIANCE    2024-10-28  x0.5000   documented 1:1 bonus     -- adjust
    BAJFINANCE  2016-09-08  x0.2000   documented 1:5 split     -- adjust
    IRCTC       2021-10-28  x0.2000   documented 1:5 split     -- adjust
    YESBANK     2017-09-21  x0.2000   documented 1:5 split     -- adjust

    ADANIENT    2015-06-03  x0.1723   NO documented action     -- do NOT adjust
    DHFL        2018-09-21  x0.5742   NO documented action     -- do NOT adjust
    IRB         2023-02-22  x0.1145   NO documented action     -- do NOT adjust

The two groups are indistinguishable by ratio. ``YESBANK`` at exactly x0.2 is a
genuine 1:5 split; ``ADANIENT`` at x0.1723 is the 2015 demerger fallout and
``DHFL`` at x0.5742 is the IL&FS-contagion crash. An inference rule keyed on
"looks like a clean ratio" adjusts the first three correctly and leaves the last
three alone only by luck -- and a rule keyed on magnitude erases real crashes,
which is the worse direction: it turns a near-total loss into a non-event.

A note on how this list was built. An earlier draft of this docstring asserted
that ``YESBANK x0.2005`` was a genuine collapse. It is not -- it is the 2017
split, and the claim came from a scan whose printed dates had the year sliced
off, so a 2017 corporate action was read as the March 2020 crash. The argument
survived; the example was wrong. Every row above now carries its date and was
re-checked against the feed rather than recalled.

So: adjustments come from documents. Inference is reserved for cases a human has
looked at and signed off.

The feed
--------
``https://www.nseindia.com/api/corporates-corporateActions`` returns JSON, one
object per action, with a free-text ``subject`` carrying the substance:

    "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 5/- Per Share"
    "Bonus 1:1"
    "Interim Dividend - Rs 5 Per Share"
    "Demerger"

The ratio has to be read out of that prose. Every phrasing this module does not
recognise becomes :attr:`ActionType.OTHER` with no multiplier, which the
adjustment engine then leaves alone -- the safe direction. What it must never do
is guess a ratio from a subject it did not understand.

Sign conventions, stated once
-----------------------------
:attr:`CorporateAction.price_multiplier` is ``ratio_from / ratio_to`` and means
the expected ``close / previous_close``.

* **Face-value split** from ``old`` to ``new``: the share count rises by
  ``old / new``, so the price falls to ``new / old``. Hence ``ratio_from=new``,
  ``ratio_to=old``. A 10 to 5 split gives 0.5.
* **Bonus ``a:b``**: ``a`` new shares for every ``b`` held, so the count rises
  to ``(a + b) / b`` and the price falls to ``b / (a + b)``. Hence
  ``ratio_from=b``, ``ratio_to=a+b``. A 1:1 bonus gives 0.5; a 1:2 bonus gives
  0.667, which is the origin of every ``x0.6667`` in the price archive.

Getting either backwards produces a multiplier that is plausible, wrong, and
undetectable downstream -- so both are pinned by tests against real subjects.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from typing import Any, Final

from indian_equity_research.market.corporate_actions import ActionType, CorporateAction

__all__ = [
    "CorporateActionParseError",
    "ParsedSubject",
    "load_actions_json",
    "parse_action_record",
    "parse_subject",
]

_MONTHS: Final = frozenset(
    {
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    }
)

# "From Rs 10/- Per Share To Rs 5/- Per Share", and the several ways NSE has
# punctuated it. Decimals are real: face values of 2.50 and 0.50 both occur.
_FACE_SPLIT_RE: Final = re.compile(
    r"from\s*(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*/?-?\s*(?:per\s+share)?\s*"
    r"to\s*(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_BONUS_RATIO_RE: Final = re.compile(r"(\d+)\s*[:\-/]\s*(\d+)")
_AMOUNT_RE: Final = re.compile(
    r"(?:rs\.?|inr|re\.?)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:per\s+share)",
    re.IGNORECASE,
)

# Order matters: "Bonus" appears inside subjects that are primarily something
# else, and a demerger subject can mention a ratio that is not a price ratio.
_SPLIT_WORDS: Final = ("face value split", "sub-division", "subdivision", "stock split")
_CONSOLIDATION_WORDS: Final = ("consolidation", "face value consolidation", "reverse split")
_DEMERGER_WORDS: Final = ("demerger", "scheme of arrangement", "spin off", "spin-off")
_RIGHTS_WORDS: Final = ("rights",)
_DIVIDEND_WORDS: Final = ("dividend",)
_BONUS_WORDS: Final = ("bonus",)


class CorporateActionParseError(ValueError):
    """Raised when a feed record cannot be read without guessing."""


class ParsedSubject:
    """What a ``subject`` line was understood to mean.

    A plain object rather than a dataclass so the invariant below can be stated
    in one place: an action either carries a complete ratio or carries none.
    """

    __slots__ = ("action_type", "amount", "ratio_from", "ratio_to")

    def __init__(
        self,
        action_type: ActionType,
        ratio_from: int | None = None,
        ratio_to: int | None = None,
        amount: float | None = None,
    ) -> None:
        """Store the reading, refusing a half-formed ratio."""
        if (ratio_from is None) != (ratio_to is None):
            raise CorporateActionParseError(
                f"half a ratio is not a ratio: from={ratio_from}, to={ratio_to}"
            )
        self.action_type = action_type
        self.ratio_from = ratio_from
        self.ratio_to = ratio_to
        self.amount = amount

    def __eq__(self, other: object) -> bool:
        """Value equality, so tests can compare readings directly."""
        if not isinstance(other, ParsedSubject):
            return NotImplemented
        return (
            self.action_type == other.action_type
            and self.ratio_from == other.ratio_from
            and self.ratio_to == other.ratio_to
            and self.amount == other.amount
        )

    def __repr__(self) -> str:
        """Readable in a test failure, which is the only place this is seen."""
        return (
            f"ParsedSubject({self.action_type}, ratio_from={self.ratio_from}, "
            f"ratio_to={self.ratio_to}, amount={self.amount})"
        )


def _as_ratio(numerator: float, denominator: float) -> tuple[int, int]:
    """Scale a possibly-decimal ratio to whole numbers.

    Face values of 2.50 and 0.50 both occur, so ``5 / 2.5`` must not be
    truncated to ``5 / 2``.
    """
    scale = 1
    while (numerator * scale) % 1 or (denominator * scale) % 1:
        scale *= 10
        if scale > 10_000:  # pragma: no cover - no real face value needs this
            break
    return round(numerator * scale), round(denominator * scale)


def parse_subject(subject: str) -> ParsedSubject:
    """Read one NSE ``subject`` line.

    Args:
        subject: The free-text description from the feed.

    Returns:
        The reading. Unrecognised subjects come back as
        :attr:`ActionType.OTHER` with no ratio, which the adjustment engine
        treats as "no price adjustment" -- the safe direction.
    """
    text = " ".join(subject.split()).strip()
    lowered = text.lower()

    if any(word in lowered for word in _SPLIT_WORDS) or ("split" in lowered and "from" in lowered):
        match = _FACE_SPLIT_RE.search(text)
        if match:
            old, new = float(match.group(1)), float(match.group(2))
            if new > 0 and old > 0:
                # Price falls to new/old. NSE occasionally writes a
                # consolidation using the same "From ... To ..." wording, so
                # the direction is taken from the numbers, not the noun.
                numerator, denominator = _as_ratio(new, old)
                kind = ActionType.CONSOLIDATION if new > old else ActionType.SPLIT
                return ParsedSubject(kind, numerator, denominator)
        return ParsedSubject(ActionType.SPLIT)

    if any(word in lowered for word in _CONSOLIDATION_WORDS):
        match = _FACE_SPLIT_RE.search(text)
        if match:
            old, new = float(match.group(1)), float(match.group(2))
            if new > 0 and old > 0:
                numerator, denominator = _as_ratio(new, old)
                return ParsedSubject(ActionType.CONSOLIDATION, numerator, denominator)
        return ParsedSubject(ActionType.CONSOLIDATION)

    # Demerger before bonus: a demerger subject can mention a share-exchange
    # ratio, which is not a price ratio and must not be used as one. The value
    # of the demerged entity is unknown from this feed.
    if any(word in lowered for word in _DEMERGER_WORDS):
        return ParsedSubject(ActionType.DEMERGER)

    if any(word in lowered for word in _BONUS_WORDS):
        match = _BONUS_RATIO_RE.search(text)
        if match:
            new_shares, held = int(match.group(1)), int(match.group(2))
            if held > 0 and new_shares > 0:
                return ParsedSubject(ActionType.BONUS, held, new_shares + held)
        return ParsedSubject(ActionType.BONUS)

    if any(word in lowered for word in _RIGHTS_WORDS):
        # A rights issue does change the price basis, but correctly only with
        # the subscription price and the ex-rights value. Neither is in this
        # feed, so no ratio is claimed.
        return ParsedSubject(ActionType.RIGHTS)

    if any(word in lowered for word in _DIVIDEND_WORDS):
        match = _AMOUNT_RE.search(text)
        amount = None
        if match:
            amount = float(match.group(1) or match.group(2))
        return ParsedSubject(ActionType.DIVIDEND, amount=amount)

    return ParsedSubject(ActionType.OTHER)


def _parse_ex_date(raw: str) -> date:
    """Read NSE's ``06-Jan-2020`` form.

    Raises:
        CorporateActionParseError: on anything else. The ex-date places the
            adjustment; a date read wrongly moves a split by days and corrupts
            every return that spans it.
    """
    cleaned = raw.strip()
    parts = cleaned.split("-")
    if len(parts) != 3 or parts[1][:3].title() not in _MONTHS:
        raise CorporateActionParseError(
            f"{raw!r} is not an ex-date in NSE's DD-Mon-YYYY form (e.g. 06-Jan-2020)"
        )
    try:
        return datetime.strptime(cleaned, "%d-%b-%Y").replace(tzinfo=UTC).date()
    except ValueError as exc:
        raise CorporateActionParseError(f"could not read ex-date {raw!r}: {exc}") from exc


def parse_action_record(record: dict[str, Any], *, source: str = "") -> CorporateAction | None:
    """Convert one feed object into a :class:`CorporateAction`.

    Args:
        record: One object from the API response.
        source: Lineage string carried onto the action.

    Returns:
        The action, or ``None`` for rows that cannot affect a cash-equity
        price series: non-``EQ`` series (government securities dominate the
        feed by count), and rows with no usable ex-date such as book-closure
        notices.

    Raises:
        CorporateActionParseError: if an ``EQ`` row is present but malformed.
            Skipping it silently would drop a real adjustment.
    """
    series = str(record.get("series", "")).strip().upper()
    if series != "EQ":
        return None

    raw_date = str(record.get("exDate", "")).strip()
    if not raw_date or raw_date == "-":
        return None

    isin = str(record.get("isin", "")).strip().upper()
    symbol = str(record.get("symbol", "")).strip().upper()
    if not isin:
        raise CorporateActionParseError(
            f"EQ record for {symbol or '<no symbol>'} on {raw_date} has no ISIN. The "
            f"archive is keyed by ISIN because symbols are reassigned after a "
            f"delisting, so a record without one cannot be attached to a price series."
        )

    subject = str(record.get("subject", ""))
    parsed = parse_subject(subject)
    return CorporateAction(
        isin=isin,
        ex_date=_parse_ex_date(raw_date),
        action_type=parsed.action_type,
        ratio_from=parsed.ratio_from,
        ratio_to=parsed.ratio_to,
        amount=parsed.amount,
        source=f"{source}:{symbol}:{subject.strip()}" if source else subject.strip(),
    )


def load_actions_json(payload: str | bytes, *, source: str = "") -> list[CorporateAction]:
    """Parse a saved API response into actions.

    Args:
        payload: The JSON body, exactly as downloaded.
        source: Lineage string, usually the filename.

    Returns:
        Every ``EQ`` action in the response, ascending by ex-date.

    Raises:
        CorporateActionParseError: if the payload is not a JSON array of
            objects, or if any ``EQ`` row is malformed.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CorporateActionParseError(
            f"{source or 'payload'} is not valid JSON: {exc}. NSE returns an HTML "
            f"challenge page instead of JSON when a request arrives without the "
            f"cookies a browser would have sent."
        ) from exc

    if not isinstance(data, list):
        raise CorporateActionParseError(
            f"{source or 'payload'} is a {type(data).__name__}, expected a JSON array"
        )

    actions: list[CorporateAction] = []
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise CorporateActionParseError(
                f"{source or 'payload'} item {index} is a {type(record).__name__}, "
                f"expected an object"
            )
        action = parse_action_record(record, source=source)
        if action is not None:
            actions.append(action)
    return sorted(actions, key=lambda a: (a.ex_date, a.isin))
