#!/usr/bin/env python3
"""Reconstruct point-in-time Nifty 100 membership and report how clean it is.

Usage
-----
    uv run python scripts/build_membership.py
    uv run python scripts/build_membership.py --write data/reference/nifty100_membership.csv

Reads every press release in ``data/raw/circulars``, the hand-read register, and
the most recent archived constituent list, then rolls the roster backwards to
the start of the price archive.

Why the output is not committed by default
------------------------------------------
``docs/data_sources.md`` records that NSE prohibits redistribution of its data
outside a licensing agreement. A reconstructed membership table is still NSE's
data. The **method** is committed; the table is produced locally by whoever has
the licence to hold it. ``--write`` is therefore opt-in and the default target
is git-ignored.

Why this spends no trial budget
-------------------------------
No returns are read. This is a reconstruction of a published fact, and its
output is the same whatever the market did.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.backtest.prices import CASH_EQUITY_SERIES
from indian_equity_research.market.identity import canonical_symbols, group_members
from indian_equity_research.market.index_changes import (
    IndexChange,
    IndexChangeError,
    drop_deferred,
    load_manual_register,
    parse_release,
    read_release_pdf,
)
from indian_equity_research.market.membership import MembershipHistory, roll_back

CIRCULARS = Path("data/raw/circulars")
BHAVCOPY = Path("data/raw/bhavcopy")
ROSTERS = Path("data/raw/archive/nse_nifty100_constituents")
INDEX_NAME = "Nifty 100"
ARCHIVE_START = date(2015, 1, 1)


def isins_by_symbol() -> dict[str, set[str]]:
    """Every cash-equity ticker in the archive and the ISINs it traded under.

    Reads the whole bhavcopy archive, which takes a couple of minutes. It is
    the only source that links a ticker to a security across a rename, because
    it is the only one recording both on the same row on the same day.

    **Cash equity only.** The debt series reuse short codes across bond issues,
    so including them chains unrelated issuers through the ISIN graph. Left
    unfiltered this merged IBULHSGFIN, CHOLAFIN and some two hundred bond lines
    into a single "security", silently.
    """
    out: dict[str, set[str]] = {}
    files = sorted(BHAVCOPY.glob("*.zip"))
    for index, path in enumerate(files, start=1):
        with zipfile.ZipFile(path) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8", "replace")
        reader = csv.DictReader(io.StringIO(text))
        legacy = "PREVCLOSE" in {c.strip().upper() for c in (reader.fieldnames or [])}
        symbol_key = "SYMBOL" if legacy else "TCKRSYMB"
        series_key = "SERIES" if legacy else "SCTYSRS"
        for row in reader:
            upper = {k.strip().upper(): (v.strip() if v else "") for k, v in row.items() if k}
            if upper.get(series_key, "").upper() not in CASH_EQUITY_SERIES:
                continue
            symbol = upper.get(symbol_key, "")
            isin = upper.get("ISIN", "").upper()
            if symbol and isin:
                out.setdefault(symbol, set()).add(isin)
        if index % 500 == 0:
            print(f"  indexed {index}/{len(files)} sessions", file=sys.stderr)
    return out


def parsed_changes() -> tuple[list[IndexChange], int, int]:
    """Every Nifty 100 change from the releases plus the hand-read register."""
    changes: list[IndexChange] = []
    unreadable = 0
    for path in sorted(CIRCULARS.glob("*.pdf")):
        try:
            text = read_release_pdf(path)
        except Exception:  # noqa: BLE001 - a scan with no text layer, handled by hand
            unreadable += 1
            continue
        try:
            changes.append(parse_release(text, INDEX_NAME, source=path.name))
        except IndexChangeError:
            continue
    kept = [c for c in drop_deferred(changes) if c.included or c.excluded]
    register = load_manual_register()
    hand = [c for c in register.changes if c.included or c.excluded]
    return kept + hand, len(hand), unreadable


def report(history: MembershipHistory, canonical: dict[str, str]) -> None:
    """Print the reconstruction and everything wrong with it."""
    print(f"\n{history.describe()}\n")

    if history.unapplied:
        print("CHANGES THAT COULD NOT BE APPLIED")
        print("  Each means the roster and the release disagree. Do not proceed.")
        for problem in history.unapplied:
            print(f"    {problem.describe()}")
        print()

    if history.size_deviations:
        groups = group_members(canonical)
        print(f"PERIODS NOT AT {history.declared_size} MEMBERS")
        for deviation in history.size_deviations:
            print(f"    {deviation.effective_from}  {deviation.size} members")

        # Which securities account for the excess? Intersect every oversized
        # snapshot and subtract the union of every correctly sized one. A
        # security that is in all of the former and none of the latter is
        # present exactly when the count is wrong -- which is the only kind of
        # answer worth printing. Differencing against one arbitrary snapshot
        # instead returns every name that ever changed, which is noise.
        oversized = [s for s in history.snapshots if s.size > history.declared_size]
        correct = [s for s in history.snapshots if s.size == history.declared_size]
        if oversized and correct:
            always_extra = set(oversized[0].members)
            for snapshot in oversized[1:]:
                always_extra &= snapshot.members
            for snapshot in correct:
                always_extra -= snapshot.members
            print("\n  Present in every oversized period and in none of the correct ones:")
            for representative in sorted(always_extra) or [
                "(none -- the excess is not one security)"
            ]:
                tickers = ", ".join(groups.get(representative, (representative,)))
                print(f"    {representative}  (tickers: {tickers})")
        print()

    print("SNAPSHOTS")
    for snapshot in history.snapshots:
        print(f"    {snapshot.effective_from}  {snapshot.size}")


def main() -> int:
    """Build the reconstruction, report it, optionally write it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", type=Path, default=None, help="write the table to this path")
    parser.add_argument("--stop-at", default=ARCHIVE_START.isoformat())
    args = parser.parse_args()

    rosters = sorted(ROSTERS.glob("*.csv"))
    if not rosters:
        print(f"no archived constituent list in {ROSTERS}")
        return 1
    roster_path = rosters[-1]
    roster_date = date.fromisoformat(roster_path.stem.split("_")[-1])
    with roster_path.open(encoding="utf-8") as handle:
        roster = [row["Symbol"].strip().upper() for row in csv.DictReader(handle)]
    print(f"roster {roster_path.name}: {len(roster)} symbols as at {roster_date}")

    changes, hand_read, unreadable = parsed_changes()
    print(
        f"{len(changes)} changes ({len(changes) - hand_read} parsed from releases, "
        f"{hand_read} hand-read); {unreadable} releases have no text layer"
    )
    future = [c for c in changes if c.effective_from > roster_date]
    for change in future:
        print(f"  announced but not yet effective, not undone: {change.describe()}")

    print("indexing the bhavcopy archive for symbol identity...")
    canonical = canonical_symbols(isins_by_symbol())

    history = roll_back(
        roster,
        roster_date,
        changes,
        canonical=canonical,
        stop_at=date.fromisoformat(args.stop_at),
    )
    report(history, canonical)

    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        with args.write.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["effective_from", "size", "members"])
            for snapshot in history.snapshots:
                writer.writerow(
                    [snapshot.effective_from, snapshot.size, " ".join(sorted(snapshot.members))]
                )
        print(f"\nwritten to {args.write}")

    return 0 if history.clean else 2


if __name__ == "__main__":
    raise SystemExit(main())
