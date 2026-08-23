#!/usr/bin/env python3
"""Reconstruct a point-in-time index universe and report how clean it is.

Usage
-----
    uv run python scripts/build_membership.py
    uv run python scripts/build_membership.py --index "Nifty 200"
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
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.market.identity import group_members
from indian_equity_research.market.reconstruction import (
    NIFTY_100,
    NIFTY_200,
    IndexSpec,
    Reconstruction,
    ReconstructionError,
    reconstruct,
)

ARCHIVE_START = date(2015, 1, 1)
KNOWN: dict[str, IndexSpec] = {spec.name: spec for spec in (NIFTY_100, NIFTY_200)}


def report(built: Reconstruction) -> None:
    """Print the reconstruction and everything wrong with it."""
    history = built.history
    print(f"\n{built.describe()}\n")

    if history.unapplied:
        print("CHANGES THAT COULD NOT BE APPLIED")
        print("  Each means the roster and the release disagree. Do not proceed.")
        for problem in history.unapplied:
            print(f"    {problem.describe()}")
        print()

    if history.size_deviations:
        groups = group_members(built.canonical)
        print(f"PERIODS NOT AT {history.declared_size} MEMBERS")
        for deviation in history.size_deviations:
            print(f"    {deviation.effective_from}  {deviation.size} members")

        # Which securities account for the excess? Intersect every oversized
        # snapshot and subtract the union of every correctly sized one. A
        # security in all of the former and none of the latter is present
        # exactly when the count is wrong -- the only answer worth printing.
        # Differencing against one arbitrary snapshot returns every name that
        # ever changed, which is noise.
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
    parser.add_argument("--index", default=NIFTY_100.name, choices=sorted(KNOWN))
    parser.add_argument("--write", type=Path, default=None, help="write the table to this path")
    parser.add_argument("--stop-at", default=ARCHIVE_START.isoformat())
    args = parser.parse_args()

    spec = KNOWN[args.index]
    print(f"reconstructing {spec.describe()}...")
    print("  (indexing the bhavcopy archive for symbol identity, this takes a minute)")
    try:
        built = reconstruct(spec, stop_at=date.fromisoformat(args.stop_at))
    except ReconstructionError as exc:
        # Expected and actionable -- usually a dataset not yet downloaded. A
        # traceback would bury the line that says what to do about it.
        print(f"\n  CANNOT BUILD THE UNIVERSE\n    {exc}")
        return 1
    report(built)

    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        with args.write.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["effective_from", "size", "members"])
            for snapshot in built.history.snapshots:
                writer.writerow(
                    [snapshot.effective_from, snapshot.size, " ".join(sorted(snapshot.members))]
                )
        print(f"\nwritten to {args.write}")

    return 0 if built.history.clean else 2


if __name__ == "__main__":
    raise SystemExit(main())
