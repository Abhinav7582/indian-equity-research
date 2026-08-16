"""Read the human verdicts recorded in the adjustment audit register.

The register lists large price moves that no documented corporate action
explains. A person marks each one, and this module turns those marks into
something the adjustment engine can act on.

The asymmetry that governs the defaults
---------------------------------------
The two mistakes are not equally bad, and the difference decides how strict
this module is in each direction.

* **A real action marked ``crash``** leaves a fake fall in the price series.
  The strategy looks *worse* than it was. Conservative, visible, recoverable.
* **A real crash marked ``action``** adjusts the fall away. The strategy looks
  *better* than it was, and nothing downstream can tell -- the series is smooth
  and plausible, and the loss simply never happened.

So ``crash`` is accepted on its own. ``action`` must carry a multiplier, and
that multiplier is checked against the move it claims to explain: a verdict of
"1:5 split" against an observed x0.68 is rejected, because one of the two is
wrong and guessing which would defeat the point of asking a human.

Unmarked rows
-------------
An unmarked row is not "no adjustment". It is "nobody has looked", and
:func:`load_verdicts` reports it as outstanding so the caller can refuse to run
until it is resolved. Treating unmarked as clean would quietly reintroduce every
error the register exists to catch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

__all__ = [
    "VERDICT_REGISTER_PATH",
    "AdjustmentVerdict",
    "VerdictError",
    "VerdictRegister",
    "load_verdicts",
]

VERDICT_REGISTER_PATH: Final = Path("data/reference/adjustment_audit.md")

CRASH: Final = "crash"
ACTION: Final = "action"
DATA: Final = "data"
_VALID: Final = frozenset({CRASH, ACTION, DATA})

# How far the stated multiplier may sit from the observed move. A corporate
# action lands on its exact ratio only if the stock did not otherwise move that
# day, which never happens; 10% absorbs an ordinary session comfortably while
# still rejecting a ratio that belongs to a different action entirely.
_MULTIPLIER_TOLERANCE: Final = 0.10

_MULTIPLIER_RE: Final = re.compile(r"(?:x\s*)?(\d+(?:\.\d+)?)", re.IGNORECASE)


class VerdictError(ValueError):
    """Raised when a register row cannot be read without guessing."""


@dataclass(frozen=True, slots=True)
class AdjustmentVerdict:
    """One human decision about one large move."""

    when: date
    symbol: str
    observed: float
    verdict: str
    multiplier: float | None = None
    note: str = ""

    @property
    def adjusts(self) -> bool:
        """Whether this verdict changes the price series."""
        return self.verdict == ACTION

    def describe(self) -> str:
        """One line a human can check against the register."""
        applied = f" -> apply x{self.multiplier}" if self.multiplier else ""
        return f"{self.when} {self.symbol} observed x{self.observed:.4f} = {self.verdict}{applied}"


@dataclass(frozen=True, slots=True)
class VerdictRegister:
    """Everything the register says, including what it does not say."""

    verdicts: tuple[AdjustmentVerdict, ...]
    outstanding: tuple[tuple[date, str], ...]
    source_path: Path

    @property
    def complete(self) -> bool:
        """True only when every row has been marked."""
        return not self.outstanding

    def describe(self) -> str:
        """One line summarising progress."""
        adjusting = sum(1 for v in self.verdicts if v.adjusts)
        return (
            f"{self.source_path}: {len(self.verdicts)} marked "
            f"({adjusting} apply an adjustment), {len(self.outstanding)} outstanding"
        )


def _parse_multiplier(cell: str) -> float | None:
    """Read ``x0.5`` or ``0.5`` from a verdict note."""
    match = _MULTIPLIER_RE.search(cell)
    if not match:
        return None
    value = float(match.group(1))
    return value if value > 0 else None


def load_verdicts(path: Path | None = None) -> VerdictRegister:
    """Read the audit register.

    Args:
        path: The register. Defaults to :data:`VERDICT_REGISTER_PATH`.

    Returns:
        The parsed register, including rows still unmarked.

    Raises:
        VerdictError: if the file is missing, or a row is marked in a way that
            cannot be acted on.
    """
    target = path or VERDICT_REGISTER_PATH
    if not target.exists():
        raise VerdictError(
            f"{target} does not exist. Generate it with "
            f"`uv run python scripts/audit_adjustments.py`, then mark each row."
        )

    verdicts: list[AdjustmentVerdict] = []
    outstanding: list[tuple[date, str]] = []

    for number, raw in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("| 2"):  # data rows begin with a date
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7:
            raise VerdictError(f"line {number}: {len(cells)} columns, expected at least 7")

        try:
            when = datetime.strptime(cells[0], "%Y-%m-%d").replace(tzinfo=UTC).date()
        except ValueError as exc:
            raise VerdictError(f"line {number}: {cells[0]!r} is not a date") from exc
        symbol = cells[1]
        try:
            observed = float(cells[2])
        except ValueError as exc:
            raise VerdictError(f"line {number}: {cells[2]!r} is not a multiplier") from exc

        marked = cells[6].strip().lower()
        if not marked:
            outstanding.append((when, symbol))
            continue

        word = marked.split()[0].strip(":,")
        if word not in _VALID:
            raise VerdictError(
                f"line {number}: verdict {cells[6]!r} for {symbol} on {when} is not one of "
                f"{sorted(_VALID)}. Leave it blank rather than inventing a category -- a "
                f"blank row is reported as outstanding, which is the honest state."
            )

        multiplier = _parse_multiplier(marked[len(word) :]) if word == ACTION else None
        if word == ACTION:
            if multiplier is None:
                raise VerdictError(
                    f"line {number}: {symbol} on {when} is marked '{ACTION}' with no "
                    f"multiplier. Write e.g. 'action x0.2'. An adjustment without a "
                    f"ratio cannot be applied, and this is the direction that hides "
                    f"its own errors -- an adjusted-away crash leaves no trace."
                )
            if abs(multiplier - observed) > _MULTIPLIER_TOLERANCE * max(multiplier, observed):
                raise VerdictError(
                    f"line {number}: {symbol} on {when} moved x{observed:.4f} but is "
                    f"marked as an action of x{multiplier}. Those disagree by more than "
                    f"{_MULTIPLIER_TOLERANCE:.0%}, so one of them is wrong."
                )

        verdicts.append(
            AdjustmentVerdict(
                when=when,
                symbol=symbol,
                observed=observed,
                verdict=word,
                multiplier=multiplier,
                note=cells[6],
            )
        )

    return VerdictRegister(
        verdicts=tuple(sorted(verdicts, key=lambda v: (v.when, v.symbol))),
        outstanding=tuple(sorted(outstanding)),
        source_path=target,
    )
