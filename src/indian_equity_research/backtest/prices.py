"""Build back-adjusted OHLC bars for the backtest engine.

This is the bridge Phase 3b was missing. The adjustment engine
(``market/adjustment.py``) worked on a single close series; the backtest engine
consumes ``{symbol: {date: Bar}}`` with four prices per session. Nothing joined
them, so every backtest so far has run on **raw** prices: a 10-for-1 split
appeared as a 90 per cent loss.

Two rules, both load-bearing
----------------------------
**Adjust all four prices by the same factor.** A ratio adjustment rescales the
security, not one field of it. Adjusting close alone would leave
``high < close`` on split days and quietly corrupt any signal built on ranges.

**Refuse to serve prices while the audit is incomplete.** :func:`build_bars`
loads the verdict register and raises if any large move is still unclassified.
That guard is the only thing making the audit worth having: without it, an
unresolved row silently becomes "no adjustment", which is a decision nobody
made. See ``data/reference/adjustment_audit.md`` and Amendment A5 clause 4.

Where the adjustments come from
-------------------------------
Two sources, merged:

1. **The NSE corporate-actions feed**, parsed by
   ``market/nse_corporate_actions.py``. Splits, bonuses and consolidations that
   carry a ratio.
2. **The verdict register**, for moves the feed did not explain and a human
   adjudicated. Six of 67 turned out to be real actions the feed had missed --
   all of them recoverable only through company renames (CADILAHC to
   ZYDUSLIFE, TIDEWATER to VEEDOL, INFIBEAM to CCAVENUE, MCDOWELL-N to
   UNITDSPR), plus an abbreviated subject and a rights issue.

Both are ``DOCUMENTED``. Nothing here infers a multiplier from a price move,
because the two are indistinguishable: YESBANK at exactly x0.2 was a real 1:5
split, and ADANIENT at x0.1723 was not.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import Final

from indian_equity_research.backtest.engine import Bar
from indian_equity_research.market.adjustment import (
    Adjustment,
    AdjustmentSource,
    cumulative_factors,
)
from indian_equity_research.market.adjustment_verdicts import load_verdicts
from indian_equity_research.market.nse_corporate_actions import load_actions_json

__all__ = [
    "RESIDUAL_MOVE_THRESHOLD",
    "BarBuildError",
    "PriceHistory",
    "ResidualMove",
    "adjust_bars",
    "build_bars",
    "documented_adjustments",
    "residual_moves",
]

# A daily move beyond this, surviving adjustment, is treated as suspicious.
# Real single-day falls of this size happen -- DHFL lost 42.6% in one session
# and Jet Airways 40.8% -- so this cannot simply raise. It reports.
RESIDUAL_MOVE_THRESHOLD: Final = 0.35

BHAVCOPY_DIR: Final = Path("data/raw/bhavcopy")
ACTIONS_DIR: Final = Path("data/raw/corporate_actions")


class BarBuildError(RuntimeError):
    """Raised when bars cannot be built without hiding a decision."""


@dataclass(frozen=True, slots=True)
class ResidualMove:
    """A large move that survived adjustment, and therefore needs explaining."""

    symbol: str
    when: date
    multiplier: float

    def describe(self) -> str:
        """One line a human can check against the corporate-action record."""
        return f"{self.when} {self.symbol} x{self.multiplier:.4f}"


@dataclass(frozen=True, slots=True)
class PriceHistory:
    """Adjusted bars, and an account of what was done to them."""

    bars: dict[str, dict[date, Bar]]
    sessions: tuple[date, ...]
    adjustments_applied: int
    securities_adjusted: int
    from_feed: int
    from_register: int
    residuals: tuple[ResidualMove, ...] = ()

    def describe(self) -> str:
        """One line, carrying the provenance with it."""
        warning = f", {len(self.residuals)} UNEXPLAINED large moves" if self.residuals else ""
        return (
            f"{len(self.bars)} securities, {len(self.sessions)} sessions, "
            f"{self.adjustments_applied} adjustments on {self.securities_adjusted} "
            f"securities ({self.from_feed} from the NSE feed, "
            f"{self.from_register} hand-verified){warning}"
        )


def residual_moves(
    bars: dict[str, dict[date, Bar]], threshold: float = RESIDUAL_MOVE_THRESHOLD
) -> list[ResidualMove]:
    """Find daily moves that survived adjustment.

    Why this exists, and why it is not optional
    -------------------------------------------
    The hand audit was scoped to liquid names -- turnover of at least ₹20
    crore -- because 1,868 raw candidates were mostly sub-rupee penny stocks.
    That scoping was reasonable and it leaves a hole: a genuine split in a
    thinly traded security was never examined and is still unadjusted.

    TIDEWATER is the worked example. It split on 2021-10-18 on ₹4.03 crore of
    turnover, below the audit threshold, and its corporate actions sit in the
    NSE feed under the post-rename symbol VEEDOL. Two independent reasons the
    adjustment was missed -- and one check that catches both.

    A residual is **not proof of an error**. DHFL fell 42.6% in a session and
    Jet Airways 40.8%; both are real. This reports so a human can look, rather
    than adjusting on suspicion, which is the failure mode the whole audit
    exists to avoid.
    """
    out: list[ResidualMove] = []
    for symbol, series in bars.items():
        ordered = sorted(series)
        # pairwise, not zip(x, x[1:]). Ruff has now caught this pattern twice in
        # this repository and it has been written by hand four times besides.
        for earlier, later in pairwise(ordered):
            previous = series[earlier].close
            if previous <= 0:
                continue
            multiplier = series[later].close / previous
            if abs(multiplier - 1.0) > threshold:
                out.append(ResidualMove(symbol=symbol, when=later, multiplier=multiplier))
    return sorted(out, key=lambda r: (r.when, r.symbol))


def documented_adjustments(
    *,
    actions_dir: Path | None = None,
    require_complete_audit: bool = True,
) -> tuple[dict[str, list[Adjustment]], int, int]:
    """Collect every documented adjustment, keyed by symbol.

    Args:
        actions_dir: Where the downloaded feed lives.
        require_complete_audit: When True, refuse if any audited move is still
            unclassified.

    Returns:
        ``(by_symbol, from_feed, from_register)``.

    Raises:
        BarBuildError: if the feed is missing, or the audit is incomplete.
    """
    source = actions_dir or ACTIONS_DIR
    files = sorted(source.glob("*.json"))
    if not files:
        raise BarBuildError(
            f"no corporate actions in {source}. Run "
            f"`uv run python scripts/fetch_corporate_actions.py --fetch` first. "
            f"Building bars without them would treat every split as a price collapse."
        )

    by_symbol: dict[str, list[Adjustment]] = defaultdict(list)
    seen: set[tuple[str, date, float]] = set()
    from_feed = 0
    for path in files:
        for action in load_actions_json(path.read_bytes(), source=path.name):
            multiplier = action.price_multiplier
            if multiplier is None:
                continue
            symbol = action.source.split(":")[1] if ":" in action.source else ""
            if not symbol:
                continue
            # The same action appears in both the quarterly sweep and the
            # per-symbol history. Applying it twice would square the multiplier.
            key = (symbol, action.ex_date, round(multiplier, 6))
            if key in seen:
                continue
            seen.add(key)
            by_symbol[symbol].append(
                Adjustment(
                    ex_date=action.ex_date,
                    multiplier=multiplier,
                    source=AdjustmentSource.DOCUMENTED,
                    detail=f"NSE feed: {action.action_type.value}",
                )
            )
            from_feed += 1

    register = load_verdicts()
    if require_complete_audit and not register.complete:
        outstanding = ", ".join(f"{d} {s}" for d, s in register.outstanding[:5])
        raise BarBuildError(
            f"{len(register.outstanding)} large price move(s) are still unclassified "
            f"in {register.source_path} (e.g. {outstanding}). Every one is either a "
            f"corporate action that must be adjusted or a real move that must not be. "
            f"Serving prices now would silently choose 'no adjustment' for all of "
            f"them -- a decision nobody made."
        )

    from_register = 0
    for verdict in register.verdicts:
        if not verdict.adjusts or verdict.multiplier is None:
            continue
        key = (verdict.symbol, verdict.when, round(verdict.multiplier, 6))
        if key in seen:
            continue
        seen.add(key)
        by_symbol[verdict.symbol].append(
            Adjustment(
                ex_date=verdict.when,
                multiplier=verdict.multiplier,
                source=AdjustmentSource.DOCUMENTED,
                detail=f"hand-verified: {verdict.note[:60]}",
            )
        )
        from_register += 1

    return dict(by_symbol), from_feed, from_register


def adjust_bars(bars: dict[date, Bar], adjustments: list[Adjustment]) -> dict[date, Bar]:
    """Back-adjust one security's bars.

    Every price before an ex-date is multiplied by the product of all later
    multipliers, so the most recent bar is unchanged and history is expressed
    on today's share basis.

    All four prices take the same factor. Scaling close alone would leave
    ``high < close`` on split days.
    """
    if not adjustments:
        return bars
    ordered = sorted(bars)
    factors = dict(cumulative_factors(ordered, adjustments))
    return {
        when: Bar(
            date=when,
            open=bar.open * factors[when],
            high=bar.high * factors[when],
            low=bar.low * factors[when],
            close=bar.close * factors[when],
        )
        for when, bar in bars.items()
    }


def _read_session(path: Path) -> list[tuple[str, float, float, float, float]]:
    """Pull EQ rows from one bhavcopy file, in either published format."""
    with zipfile.ZipFile(path) as archive:
        text = archive.read(archive.namelist()[0]).decode("utf-8", "replace")
    reader = csv.DictReader(io.StringIO(text))
    legacy = "PREVCLOSE" in {c.strip().upper() for c in (reader.fieldnames or [])}
    keys = (
        ("SYMBOL", "OPEN", "HIGH", "LOW", "CLOSE")
        if legacy
        else ("TCKRSYMB", "OPNPRIC", "HGHPRIC", "LWPRIC", "CLSPRIC")
    )
    series_key = "SERIES" if legacy else "SCTYSRS"
    out: list[tuple[str, float, float, float, float]] = []
    for row in reader:
        upper = {k.strip().upper(): (v.strip() if v else "") for k, v in row.items() if k}
        if upper.get(series_key) != "EQ":
            continue
        try:
            open_, high, low, close = (float(upper[k]) for k in keys[1:])
        except (KeyError, ValueError):
            continue
        if min(open_, high, low, close) <= 0 or low > high:
            continue
        out.append((upper.get(keys[0], ""), open_, high, low, close))
    return out


def build_bars(
    *,
    symbols: set[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    bhavcopy_dir: Path | None = None,
    actions_dir: Path | None = None,
    require_complete_audit: bool = True,
    strict: bool = False,
) -> PriceHistory:
    """Load bhavcopy and return back-adjusted bars ready for the engine.

    Args:
        symbols: Restrict to these. ``None`` loads everything, which is slow
            and rarely wanted.
        start: First session, inclusive.
        end: Last session, inclusive.
        bhavcopy_dir: Where the archive lives.
        actions_dir: Where the corporate-actions feed lives.
        require_complete_audit: Refuse while any audited move is unclassified.
        strict: Refuse if any large move survives adjustment. Off by default
            because genuine crashes of that size exist; **on** is correct for a
            run whose result will be entered in the trial register.

    Returns:
        Adjusted bars plus a record of what was applied.

    Raises:
        BarBuildError: if no sessions are found, the audit is incomplete, or
            ``strict`` and a large move survived adjustment.
    """
    by_symbol, from_feed, from_register = documented_adjustments(
        actions_dir=actions_dir, require_complete_audit=require_complete_audit
    )

    source = bhavcopy_dir or BHAVCOPY_DIR
    raw: dict[str, dict[date, Bar]] = defaultdict(dict)
    sessions: list[date] = []
    for path in sorted(source.glob("*.zip")):
        try:
            when = date.fromisoformat(path.stem.split("_")[-1].replace(".csv", ""))
        except ValueError:  # pragma: no cover - filenames are generated by us
            continue
        if (start and when < start) or (end and when > end):
            continue
        sessions.append(when)
        for symbol, open_, high, low, close in _read_session(path):
            if symbols is not None and symbol not in symbols:
                continue
            raw[symbol][when] = Bar(date=when, open=open_, high=high, low=low, close=close)

    if not sessions:
        raise BarBuildError(
            f"no bhavcopy sessions found in {source} for the requested range ({start} to {end})"
        )

    adjusted: dict[str, dict[date, Bar]] = {}
    applied = 0
    touched = 0
    for symbol, bars in raw.items():
        relevant = [a for a in by_symbol.get(symbol, []) if min(bars) <= a.ex_date <= max(bars)]
        adjusted[symbol] = adjust_bars(bars, relevant)
        if relevant:
            applied += len(relevant)
            touched += 1

    residuals = residual_moves(adjusted)
    if strict and residuals:
        listed = "; ".join(r.describe() for r in residuals[:6])
        raise BarBuildError(
            f"{len(residuals)} large move(s) survived adjustment, e.g. {listed}. "
            f"Each is either an unadjusted corporate action or a real collapse, and "
            f"the two are indistinguishable from the price alone. Resolve them before "
            f"entering a result in the trial register, or pass strict=False to "
            f"proceed with the residuals recorded on the result."
        )

    return PriceHistory(
        bars=adjusted,
        sessions=tuple(sorted(set(sessions))),
        adjustments_applied=applied,
        securities_adjusted=touched,
        from_feed=from_feed,
        from_register=from_register,
        residuals=tuple(residuals),
    )
