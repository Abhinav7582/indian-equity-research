"""Build back-adjusted OHLC bars for the backtest engine.

This is the bridge Phase 3b was missing. The adjustment engine
(``market/adjustment.py``) worked on a single close series; the backtest engine
consumes ``{symbol: {date: Bar}}`` with four prices per session. Nothing joined
them, so every backtest so far has run on **raw** prices: a 10-for-1 split
appeared as a 90 per cent loss.

Four rules, all load-bearing
----------------------------
**Adjust all four prices by the same factor.** A ratio adjustment rescales the
security, not one field of it. Adjusting close alone would leave
``high < close`` on split days and quietly corrupt any signal built on ranges.

**Refuse to serve prices while the audit is incomplete.** :func:`build_bars`
loads the verdict register and raises if any large move is still unclassified.
That guard is the only thing making the audit worth having: without it, an
unresolved row silently becomes "no adjustment", which is a decision nobody
made. See ``data/reference/adjustment_audit.md`` and Amendment A5 clause 4.

**Keep the surveillance series.** A security under surveillance moves from
``EQ`` to ``BE`` or ``BZ`` -- trade-for-trade settlement -- and returns later.
It is the same share on the same ISIN; only the settlement rule differs. An
earlier version of this module filtered on ``SERIES == "EQ"``, which deleted
those sessions outright and silently welded the last pre-surveillance bar onto
the first bar after the security came back. See :data:`CASH_EQUITY_SERIES`.

**Route actions by ISIN, not by symbol.** NSE's feed reports the security's
**current** symbol on every historical row, so a 2015 action for CADILAHC comes
back labelled ZYDUSLIFE -- a symbol that did not exist until 2022 and matches no
bar in 2015. Keying adjustments by symbol dropped 61 of 841 documented ratios,
every one of them silently. See :func:`route_adjustments`.

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
    "CASH_EQUITY_SERIES",
    "RESIDUAL_MOVE_THRESHOLD",
    "BarBuildError",
    "FeedAdjustment",
    "PriceHistory",
    "ResidualMove",
    "SupersededAction",
    "SymbolSpan",
    "adjust_bars",
    "build_bars",
    "documented_adjustments",
    "residual_moves",
    "route_adjustments",
]

# NSE settlement series carrying the ordinary equity share.
#
# ``EQ`` is normal rolling settlement. ``BE`` and ``BZ`` are trade-for-trade:
# the same share, the same ISIN, compulsory delivery, no intraday netting. A
# security is moved there under surveillance and moved back when the reason
# lapses, which for a mid-cap can be months.
#
# Excluding them is not a conservative choice, it is a corrupting one. The bars
# do not become missing data -- they become *absent*, and the sessions on either
# side of the hole become adjacent, so a return is computed across a gap that no
# holder ever experienced. TIDEWATER spent 2021-07-15 to 2021-10-14 on ``BE``,
# and dropping it turned a documented x0.2 action plus a real 43 per cent
# decline into a single fabricated -89 per cent day.
#
# ``SM`` and ``ST`` (the SME platform) are deliberately **not** here. That is a
# separate board with its own listing rules, and no Nifty 100 constituent trades
# on it. ``GB``/``GS``/``TB`` are government securities and ``N1``-``NE`` debt.
CASH_EQUITY_SERIES: Final = frozenset({"EQ", "BE", "BZ"})

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
class FeedAdjustment:
    """One documented adjustment, still carrying the labels the feed gave it.

    The feed's ``symbol`` is the security's name **today**, not on the ex-date,
    so it cannot be used as a key. It is kept only as a fallback for records
    with no usable ISIN, and as the thing a human recognises in a report.
    """

    symbol: str
    isin: str
    adjustment: Adjustment
    hand_verified: bool = False


@dataclass(frozen=True, slots=True)
class SupersededAction:
    """A feed action displaced by a hand-verified verdict for the same day.

    Recorded rather than discarded, because a material disagreement means the
    feed's subject line was read incompletely, and that is a parser defect worth
    seeing. TIDEWATER 2016-03-16 is the type case: the subject was
    ``Bonus 1:1/Face Value Split ... Rs 10 to Rs 5``, two actions in one string.
    The parser took x0.5; the truth is x0.25; the observed move was x0.2426.
    """

    symbol: str
    when: date
    feed_multiplier: float
    verified_multiplier: float

    @property
    def material(self) -> bool:
        """Whether the two accounts of the day disagree enough to matter."""
        return abs(self.feed_multiplier - self.verified_multiplier) > 0.10 * max(
            self.feed_multiplier, self.verified_multiplier
        )

    def describe(self) -> str:
        """One line for a report."""
        flag = "  <-- DISAGREE" if self.material else ""
        return (
            f"{self.when} {self.symbol} feed x{self.feed_multiplier:.4f} "
            f"superseded by verified x{self.verified_multiplier:.4f}{flag}"
        )


@dataclass(frozen=True, slots=True)
class SymbolSpan:
    """When a ticker was observed trading, under which ISINs."""

    first: date
    last: date
    isins: frozenset[str]

    def covers(self, when: date) -> bool:
        """Whether the ticker was live on this date."""
        return self.first <= when <= self.last


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
    unrouted: tuple[FeedAdjustment, ...] = ()
    superseded: tuple[SupersededAction, ...] = ()

    def describe(self) -> str:
        """One line, carrying the provenance with it."""
        warning = f", {len(self.residuals)} UNEXPLAINED large moves" if self.residuals else ""
        lost = f", {len(self.unrouted)} adjustments matched no loaded bar" if self.unrouted else ""
        return (
            f"{len(self.bars)} securities, {len(self.sessions)} sessions, "
            f"{self.adjustments_applied} adjustments on {self.securities_adjusted} "
            f"securities ({self.from_feed} from the NSE feed, "
            f"{self.from_register} hand-verified){lost}{warning}"
        )


def residual_moves(
    bars: dict[str, dict[date, Bar]], threshold: float = RESIDUAL_MOVE_THRESHOLD
) -> list[ResidualMove]:
    """Find daily moves that survived adjustment.

    Why this exists, and why it is not optional
    -------------------------------------------
    Every other check in this project examines an **input**: is the feed
    complete, is the register marked, does the ratio parse. This one examines
    the **output**, and so it catches causes nobody thought to look for.

    TIDEWATER is the worked example, and it is worth stating exactly because
    the first diagnosis of it was wrong. The reported residual was
    ``2021-10-18 x0.1123``, and it was read as a missed split in a thinly
    traded name. It was not. TIDEWATER traded every session throughout; it was
    moved to the surveillance series ``BE`` on 2021-07-15 and returned to
    ``EQ`` on 2021-10-18. The loader filtered on ``EQ``, so three months of
    bars were dropped, and 2021-07-14 was welded onto 2021-10-18 across a
    documented x0.2 corporate action *and* a real 43 per cent decline.

    Neither the corporate-action feed nor the verdict register could have
    revealed that. Only the output could. The lesson is the general one: an
    output check finds defects an input check cannot enumerate, which is
    precisely why it must not be optional.

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
) -> tuple[list[FeedAdjustment], int, int]:
    """Collect every documented adjustment, with the labels it arrived under.

    Deliberately returns a flat list rather than a symbol-keyed mapping. The
    feed's symbol is not a key -- see :func:`route_adjustments` -- and returning
    a dict keyed by it would make the wrong thing the easy thing.

    Args:
        actions_dir: Where the downloaded feed lives.
        require_complete_audit: When True, refuse if any audited move is still
            unclassified.

    Returns:
        ``(adjustments, from_feed, from_register)``.

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

    collected: list[FeedAdjustment] = []
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
            collected.append(
                FeedAdjustment(
                    symbol=symbol,
                    isin=action.isin.strip().upper(),
                    adjustment=Adjustment(
                        ex_date=action.ex_date,
                        multiplier=multiplier,
                        source=AdjustmentSource.DOCUMENTED,
                        detail=f"NSE feed: {action.action_type.value}",
                    ),
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
        # No ISIN, and none is wanted. Register symbols were read off the
        # bhavcopy archive itself, so they are already the name the security
        # traded under on that date -- the one thing the feed cannot tell us.
        collected.append(
            FeedAdjustment(
                symbol=verdict.symbol,
                isin="",
                adjustment=Adjustment(
                    ex_date=verdict.when,
                    multiplier=verdict.multiplier,
                    source=AdjustmentSource.DOCUMENTED,
                    detail=f"hand-verified: {verdict.note[:60]}",
                ),
                hand_verified=True,
            )
        )
        from_register += 1

    return collected, from_feed, from_register


def route_adjustments(
    adjustments: list[FeedAdjustment], spans: dict[str, SymbolSpan]
) -> tuple[dict[str, list[Adjustment]], list[FeedAdjustment], list[SupersededAction]]:
    """Attach each adjustment to the ticker that was actually trading on its ex-date.

    The problem
    -----------
    NSE's corporate-actions API reports each security's **current** symbol on
    every row, however old. A 1:5 split with an ex-date of 2015-10-06 comes back
    labelled ``ZYDUSLIFE``, a name that did not exist until 2022; the bars for
    that day are filed under ``CADILAHC``. Keyed by symbol, the adjustment lands
    on an empty bucket and does nothing -- no error, no warning, just a split
    left in the price series as a 80 per cent fall.

    Measured against the 2015-2026 archive, 61 of 841 documented ratios (7.2%)
    were misrouted this way, including MOTHERSUMI's three bonuses, MCDOWELL-N,
    MINDAIND and PHILIPCARB.

    The resolution
    --------------
    Bhavcopy carries an ``ISIN`` column, so the archive can answer the question
    the feed cannot: which ticker held this ISIN on this date. Symbol match is
    kept as a fallback because the ISIN itself changes across a split -- the two
    keys fail in opposite directions, which is why the audit uses their union.

    Ambiguity is reported, never resolved by preference. Two live tickers on one
    ISIN means something is wrong with an assumption, and picking one would hide
    it.

    An adjustment for a security that was simply **not loaded** -- because
    ``symbols`` restricted the run, or the date range excluded it -- is not
    unrouted. It is irrelevant, and reporting it would bury the real cases under
    hundreds of lines of noise. ``unrouted`` means the security *is* here and the
    adjustment still could not be placed, which always deserves a look.

    Args:
        adjustments: Documented adjustments as collected.
        spans: Ticker to when it traded and under which ISINs, from the bars.

    Precedence on a shared date
    ---------------------------
    Two feed rows on one day compound: VEEDOL's 2021-07-26 bonus 1:1 and its
    5-to-2 split are separate actions and the price took both, x0.5 * x0.4.

    A hand-verified verdict is different. It is one person's account of what
    that whole day's move was, checked against the move itself, so it
    **replaces** the feed's account of that day rather than stacking on top of
    it. Stacking is how a x0.25 split became x0.125 and a real 76 per cent fall
    turned into a fictitious 94 per cent gain.

    Args:
        adjustments: Documented adjustments as collected.
        spans: Ticker to when it traded and under which ISINs, from the bars.

    Returns:
        ``(by_symbol, unrouted, superseded)``. Anything in ``unrouted`` was
        **not applied**.
    """
    by_isin: dict[str, set[str]] = defaultdict(set)
    for symbol, span in spans.items():
        for isin in span.isins:
            by_isin[isin].add(symbol)

    landed: dict[str, list[FeedAdjustment]] = defaultdict(list)
    unrouted: list[FeedAdjustment] = []
    for entry in adjustments:
        when = entry.adjustment.ex_date
        known = set(by_isin.get(entry.isin, ()))
        if entry.symbol in spans:
            known.add(entry.symbol)
        if not known:
            continue  # security not in this run at all
        live = {symbol for symbol in known if spans[symbol].covers(when)}
        if len(live) == 1:
            landed[live.pop()].append(entry)
        else:
            unrouted.append(entry)

    routed: dict[str, list[Adjustment]] = {}
    superseded: list[SupersededAction] = []
    for symbol, entries in landed.items():
        by_date: dict[date, list[FeedAdjustment]] = defaultdict(list)
        for entry in entries:
            by_date[entry.adjustment.ex_date].append(entry)
        keep: list[Adjustment] = []
        for when, same_day in by_date.items():
            verified = [e for e in same_day if e.hand_verified]
            if not verified:
                keep.extend(e.adjustment for e in same_day)
                continue
            feed_product = 1.0
            for entry in same_day:
                if not entry.hand_verified:
                    feed_product *= entry.adjustment.multiplier
            verified_product = 1.0
            for entry in verified:
                verified_product *= entry.adjustment.multiplier
            if len(same_day) > len(verified):
                superseded.append(
                    SupersededAction(
                        symbol=symbol,
                        when=when,
                        feed_multiplier=feed_product,
                        verified_multiplier=verified_product,
                    )
                )
            keep.extend(e.adjustment for e in verified)
        routed[symbol] = sorted(keep, key=lambda a: a.ex_date)
    return routed, unrouted, superseded


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


def _read_session(
    path: Path, series: frozenset[str] = CASH_EQUITY_SERIES
) -> list[tuple[str, str, float, float, float, float]]:
    """Pull cash-equity rows from one bhavcopy file, in either published format.

    Returns ``(symbol, isin, open, high, low, close)`` per row. The ISIN is
    carried because it is the only stable identity in the file: symbols are
    reused and renamed, and the corporate-actions feed knows nothing about
    which name applied on which date.
    """
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
    out: list[tuple[str, str, float, float, float, float]] = []
    for row in reader:
        upper = {k.strip().upper(): (v.strip() if v else "") for k, v in row.items() if k}
        if upper.get(series_key, "").upper() not in series:
            continue
        try:
            open_, high, low, close = (float(upper[k]) for k in keys[1:])
        except (KeyError, ValueError):
            continue
        if min(open_, high, low, close) <= 0 or low > high:
            continue
        out.append((upper.get(keys[0], ""), upper.get("ISIN", "").upper(), open_, high, low, close))
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
    collected, from_feed, from_register = documented_adjustments(
        actions_dir=actions_dir, require_complete_audit=require_complete_audit
    )

    source = bhavcopy_dir or BHAVCOPY_DIR
    raw: dict[str, dict[date, Bar]] = defaultdict(dict)
    isins: dict[str, set[str]] = defaultdict(set)
    sessions: list[date] = []
    for path in sorted(source.glob("*.zip")):
        try:
            when = date.fromisoformat(path.stem.split("_")[-1].replace(".csv", ""))
        except ValueError:  # pragma: no cover - filenames are generated by us
            continue
        if (start and when < start) or (end and when > end):
            continue
        sessions.append(when)
        for symbol, isin, open_, high, low, close in _read_session(path):
            if symbols is not None and symbol not in symbols:
                continue
            raw[symbol][when] = Bar(date=when, open=open_, high=high, low=low, close=close)
            if isin:
                isins[symbol].add(isin)

    if not sessions:
        raise BarBuildError(
            f"no bhavcopy sessions found in {source} for the requested range ({start} to {end})"
        )

    spans = {
        symbol: SymbolSpan(first=min(bars), last=max(bars), isins=frozenset(isins.get(symbol, ())))
        for symbol, bars in raw.items()
    }
    by_symbol, unrouted, superseded = route_adjustments(collected, spans)

    adjusted: dict[str, dict[date, Bar]] = {}
    applied = 0
    touched = 0
    for symbol, bars in raw.items():
        relevant = by_symbol.get(symbol, [])
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
        unrouted=tuple(unrouted),
        superseded=tuple(superseded),
    )
