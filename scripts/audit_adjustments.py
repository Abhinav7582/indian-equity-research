#!/usr/bin/env python3
"""Classify every large price move as documented action, market-wide, or open.

Usage
-----
    uv run python scripts/audit_adjustments.py
    uv run python scripts/audit_adjustments.py --min-turnover 20 --min-price 50

Writes ``data/reference/adjustment_audit.md`` -- a triage register listing the
moves that no downloaded corporate action explains and that the market does not
account for either.

What this does not do
---------------------
It does not adjust anything, and it does not decide anything. Every unexplained
move lands in the register for a human to classify as **crash** or **missing
action**, because the two are indistinguishable by ratio:

    YESBANK    2017-09-21  x0.2000   documented 1:5 split
    ADANIENT   2015-06-03  x0.1723   no documented action

Auto-adjusting anything that "looks like a clean ratio" would silently erase
real crashes, which is the worse of the two failure directions: a missed split
leaves a visible one-day outlier, while a wrongly-adjusted crash disappears
completely and makes the strategy look better than it was.

The liquidity filter, and why it is not a shortcut
--------------------------------------------------
Restricting to liquid, non-penny names cuts 1,868 events to a few hundred. That
is legitimate *only* because the Nifty 100 cannot contain the excluded names --
VISESHINFO alone contributes 265 events at sub-rupee prices where one paisa is
a large percentage. The filter is recorded in the register header so a later
reader knows exactly what was not examined.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import io
import sys
import zipfile
from collections import defaultdict, deque
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.market.corporate_actions import (
    ValidationConfig,
    match_plausible_action,
)
from indian_equity_research.market.nse_corporate_actions import load_actions_json

BHAV = Path("data/raw/bhavcopy")
ACTIONS = Path("data/raw/corporate_actions")
INDEX = Path("data/raw/indices/nifty100")
OUT = Path("data/reference/adjustment_audit.md")
CRORE = 1_00_00_000


def read_bhav_row(row: dict[str, str], legacy: bool) -> tuple[str, str, float, float, float] | None:
    """Pull the five fields we need from either bhavcopy format."""
    upper = {k.strip().upper(): (v.strip() if v else "") for k, v in row.items() if k}
    if legacy:
        if upper.get("SERIES") != "EQ":
            return None
        keys = ("SYMBOL", "ISIN", "CLOSE", "PREVCLOSE", "TOTTRDVAL")
    else:
        if upper.get("SCTYSRS") != "EQ":
            return None
        keys = ("TCKRSYMB", "ISIN", "CLSPRIC", "PRVSCLSGPRIC", "TTLTRFVAL")
    try:
        return (
            upper.get(keys[0], ""),
            upper.get(keys[1], ""),
            float(upper[keys[2]]),
            float(upper[keys[3]]),
            float(upper[keys[4]]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def market_returns() -> dict[dt.date, float]:
    """Daily Nifty 100 returns, for attributing market-wide moves."""
    closes: dict[dt.date, float] = {}
    for path in sorted(INDEX.glob("*.csv")):
        with path.open(encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                cells = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                raw_date = cells.get("date") or cells.get("index date") or ""
                close = cells.get("close") or cells.get("closing index value") or ""
                for fmt in ("%d-%b-%Y", "%d %b %Y", "%Y-%m-%d"):
                    try:
                        when = dt.datetime.strptime(raw_date, fmt).replace(tzinfo=dt.UTC).date()
                    except ValueError:
                        continue
                    with contextlib.suppress(ValueError):
                        closes[when] = float(close.replace(",", ""))
                    break
    ordered = sorted(closes)
    # pairwise, not zip(x, x[1:]). Ruff flagged this one; the same mistake has
    # been made by hand four times in this repository.
    return {
        later: closes[later] / closes[earlier] - 1.0
        for earlier, later in pairwise(ordered)
        if closes[earlier]
    }


def main() -> int:
    """Run the audit and write the register."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-price", type=float, default=50.0)
    parser.add_argument("--min-turnover", type=float, default=20.0, help="in crore")
    args = parser.parse_args()
    cfg = ValidationConfig()

    documented: dict[tuple[str, dt.date], float] = {}
    action_files = sorted(ACTIONS.glob("*.json"))
    if not action_files:
        print(f"no corporate actions in {ACTIONS}.")
        print("Run: uv run python scripts/fetch_corporate_actions.py --fetch")
        return 1
    for path in action_files:
        for action in load_actions_json(path.read_bytes(), source=path.name):
            if action.price_multiplier is not None:
                symbol = action.source.split(":")[1] if ":" in action.source else ""
                documented[(symbol, action.ex_date)] = action.price_multiplier
    print(f"documented price-changing actions: {len(documented):,}")

    index = market_returns()
    print(f"market return days: {len(index):,}")

    # A security's first session has no meaningful previous close: for an IPO
    # the bhavcopy carries the issue price there, so the listing move is real by
    # construction and is not an adjustment. Excluded rather than left for a
    # human, because there is nothing to decide.
    seen: set[str] = set()
    listings = 0
    # Trailing turnover per symbol, for the second signal. A split leaves the
    # value traded roughly unchanged -- the same money buys more, cheaper
    # shares. A crash does not: it brings panic volume, and turnover jumps.
    # The two signals are independent, which is the whole point: a move that
    # matches a clean ratio AND trades normally is very likely an action, and
    # one that matches no ratio AND trades 5x is very likely a crash.
    history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=20))

    explained: list[tuple[dt.date, str, float]] = []
    by_market: list[tuple[dt.date, str, float]] = []
    open_moves: list[tuple[dt.date, str, str, float, float, float, str, str]] = []

    files = sorted(BHAV.glob("*.zip"))
    for number, path in enumerate(files, start=1):
        if number % 500 == 0:
            print(f"  {number}/{len(files)} sessions")
        when = dt.date.fromisoformat(path.stem.split("_")[-1].replace(".csv", ""))
        with zipfile.ZipFile(path) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8", "replace")
        reader = csv.DictReader(io.StringIO(text))
        legacy = "PREVCLOSE" in {c.strip().upper() for c in (reader.fieldnames or [])}
        for row in reader:
            parsed = read_bhav_row(row, legacy)
            if parsed is None:
                continue
            symbol, isin, close, previous, turnover = parsed
            first_session = symbol not in seen
            seen.add(symbol)
            trailing = list(history[symbol])
            history[symbol].append(turnover)
            if previous < args.min_price or turnover < args.min_turnover * CRORE:
                continue
            if previous <= 0:
                continue
            multiplier = close / previous
            if abs(multiplier - 1.0) <= cfg.outlier_threshold:
                continue
            if first_session:
                listings += 1
                continue

            window = range(-cfg.action_window_days, cfg.action_window_days + 1)
            if any((symbol, when + dt.timedelta(days=d)) in documented for d in window):
                explained.append((when, symbol, multiplier))
                continue
            move = index.get(when)
            if (
                move is not None
                and abs(move) >= cfg.market_extreme_threshold
                and (move < 0) == (multiplier < 1.0)
            ):
                by_market.append((when, symbol, multiplier))
                continue
            typical = sorted(trailing)[len(trailing) // 2] if trailing else 0.0
            turnover_x = turnover / typical if typical > 0 else 0.0
            fit = match_plausible_action(multiplier, cfg.ratio_tolerance)
            ratio_note = fit[1] if fit else "no clean ratio"
            if fit and 0 < turnover_x < 3.0:
                hint = "likely action"
            elif not fit and turnover_x >= 3.0:
                hint = "likely crash"
            else:
                hint = "unclear"
            open_moves.append(
                (when, symbol, isin, multiplier, turnover / CRORE, turnover_x, ratio_note, hint)
            )

    total = len(explained) + len(by_market) + len(open_moves) + listings
    print(f"\nlarge moves examined      : {total:,}")
    print(f"  explained by an action  : {len(explained):,}")
    print(f"  explained by the market : {len(by_market):,}")
    print(f"  listing days (excluded) : {listings:,}")
    print(f"  OPEN, need a human      : {len(open_moves):,}")
    for label in ("likely action", "likely crash", "unclear"):
        count = sum(1 for row in open_moves if row[7] == label)
        print(f"      {label:<14} : {count:,}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Adjustment audit — open items",
        "",
        f"Generated {dt.datetime.now(tz=dt.UTC).date()} by `scripts/audit_adjustments.py`.",
        "",
        "Each row is a large single-day move that **no downloaded corporate action",
        "explains** and that the market does not account for. Classify each as:",
        "",
        "* `crash` — a genuine price move. **Do not adjust.**",
        "* `action` — a real corporate action missing from the NSE feed. Record the",
        "  multiplier and it will be applied.",
        "* `data` — a bhavcopy defect, e.g. a stale previous close.",
        "",
        "The **hint** column is a suggestion from two independent signals and is",
        "not a decision. `ratio fit` asks whether the move matches a multiplier a",
        "real corporate action produces; `turnover x20d` compares the day's value",
        "traded against that security's own 20-session median. A split leaves",
        "turnover roughly unchanged — the same money buys more, cheaper shares —",
        "while a crash brings panic volume. Agreement between the two is",
        "informative; disagreement is marked `unclear` and needs reading.",
        "",
        "An unclassified row blocks the security from the backtest. That is",
        "deliberate: a wrongly-adjusted crash vanishes from the record entirely,",
        "while a missing adjustment leaves a visible outlier.",
        "",
        "## Scope examined",
        "",
        "| Filter | Value |",
        "|---|---|",
        f"| Minimum previous close | Rs {args.min_price:,.0f} |",
        f"| Minimum turnover on the day | Rs {args.min_turnover:,.0f} crore |",
        f"| Outlier threshold | {cfg.outlier_threshold:.0%} |",
        f"| Action match window | +/-{cfg.action_window_days} days |",
        "",
        f"Moves examined {total:,}; explained by an action {len(explained):,}; "
        f"explained by the market {len(by_market):,}; listing days excluded "
        f"{listings:,}; **open {len(open_moves):,}**.",
        "",
        "## Register",
        "",
        "| date | symbol | multiplier | turnover x20d | ratio fit | hint | verdict |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for when, symbol, _isin, multiplier, _tv, turnover_x, ratio_note, hint in sorted(open_moves):
        lines.append(
            f"| {when} | {symbol} | {multiplier:.4f} | {turnover_x:.1f}x | "
            f"{ratio_note} | {hint} |  |"
        )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nregister written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
