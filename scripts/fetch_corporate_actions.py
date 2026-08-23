#!/usr/bin/env python3
"""Download NSE's corporate-actions feed, one quarter at a time.

Usage
-----
    uv run python scripts/fetch_corporate_actions.py --plan
    uv run python scripts/fetch_corporate_actions.py --fetch --limit 2
    uv run python scripts/fetch_corporate_actions.py --fetch

``--plan`` downloads nothing. ``--limit`` stops after N windows so the first
run can be inspected before committing to all 47.

Why this is a script and not a library function
-----------------------------------------------
``nseindia.com`` refuses requests that arrive without the cookies a browser
would have picked up from the site first, and the refusal is **HTTP 200 with an
HTML challenge page** rather than an error status. So the fetch needs a cookie
jar and a warm-up request, which is session state that has no business inside
the parsing modules. Keeping it here means ``market/`` and ``ingest/`` stay
importable, testable and offline.

Nothing here is imported by ``src/``. It writes files and prints; that is all.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from indian_equity_research.ingest.corporate_actions_fetch import (
    CORPORATE_ACTIONS_URL,
    plan_windows,
    window_filename,
    window_url,
)
from indian_equity_research.market.nse_corporate_actions import (
    CorporateActionParseError,
    load_actions_json,
)

HOME = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
OUT = Path("data/raw/corporate_actions")

# A browser User-Agent is required, not optional: NSE serves the challenge page
# to anything that looks automated. This is stated plainly rather than hidden,
# because pretending to be a browser is a choice worth being aware of. The
# requests remain low-volume, rate-limited and read-only.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": HOME,
}


def opener() -> urllib.request.OpenerDirector:
    """An opener with a cookie jar, warmed up against the site."""
    jar = http.cookiejar.CookieJar()
    built = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    built.addheaders = list(HEADERS.items())
    try:
        built.open(HOME, timeout=30).read()
    except urllib.error.URLError as exc:
        print(f"could not reach {HOME}: {exc}")
        print("Check your connection. Nothing has been downloaded.")
        raise SystemExit(1) from exc
    return built


def fetch_symbols(symbols: list[str], *, delay: float) -> int:
    """Download the complete action history for named symbols.

    Why this exists
    ---------------
    The date-ranged sweep misses actions for companies that were later renamed
    or delisted. Twenty-nine bonuses and splits were absent from a full
    2015-2026 quarterly download but present when the same securities were
    queried by symbol -- the per-symbol endpoint returns history back to about
    2008 and does not appear to apply the same filtering.

    A gap that only affects renamed and delisted companies is the worst kind:
    those are exactly the securities a survivorship-free universe must contain.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    client = opener()
    saved = 0
    for index, symbol in enumerate(symbols, start=1):
        target = OUT / f"ca_symbol_{symbol.upper()}.json"
        if target.exists():
            print(f"  [{index}/{len(symbols)}] {symbol}: already present")
            continue
        # quote(), not raw interpolation. "M&MFIN" contains an ampersand,
        # which starts a new query parameter -- the request silently becomes a
        # query for "M" and returns an empty array that looks exactly like a
        # company with no corporate actions.
        url = (
            f"{CORPORATE_ACTIONS_URL}?index=equities"
            f"&symbol={urllib.parse.quote(symbol.upper(), safe='')}"
        )
        try:
            with client.open(url, timeout=60) as response:
                body = response.read()
        except urllib.error.URLError as exc:
            print(f"  {symbol}: request failed ({exc}). Stopping.")
            return 1
        try:
            actions = load_actions_json(body, source=target.name)
        except CorporateActionParseError as exc:
            print(f"  {symbol}: {exc}")
            return 1
        target.write_bytes(body)
        saved += 1
        note = "" if actions else "   <-- EMPTY: symbol probably renamed or delisted"
        print(f"  [{index}/{len(symbols)}] {symbol}: {len(actions)} equity actions{note}")
        time.sleep(delay)
    print(f"\nsaved {saved} symbol histories to {OUT}")
    return 0


def main() -> int:
    """Plan or run the download."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", default="2015-01-01")
    parser.add_argument("--to", dest="end", default=datetime.now(tz=UTC).date().isoformat())
    parser.add_argument("--plan", action="store_true", help="show the plan, download nothing")
    parser.add_argument("--fetch", action="store_true", help="actually download")
    parser.add_argument("--limit", type=int, default=0, help="stop after N windows")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between requests")
    parser.add_argument(
        "--symbols",
        nargs="+",
        metavar="SYM",
        help=(
            "fetch the FULL history for these symbols instead of a date range. "
            "The per-symbol endpoint returns everything back to ~2008, where the "
            "date-ranged one silently omits renamed and delisted companies."
        ),
    )
    args = parser.parse_args()

    if args.symbols:
        return fetch_symbols(args.symbols, delay=args.delay)

    windows = plan_windows(date.fromisoformat(args.start), date.fromisoformat(args.end))
    if args.limit:
        windows = windows[: args.limit]

    if args.plan or not args.fetch:
        print(f"{len(windows)} quarterly windows, {args.start} to {args.end}")
        for window in windows[:3]:
            print(f"  {window.label}  {window.start} .. {window.end}")
        print(f"  ... {len(windows) - 3} more" if len(windows) > 3 else "")
        print(
            f"\nEstimated time at {args.delay}s delay: "
            f"{len(windows) * (args.delay + 1) / 60:.0f} minutes"
        )
        print("Nothing downloaded. Re-run with --fetch.")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    client = opener()
    saved = skipped = 0
    total_actions = 0

    for index, window in enumerate(windows, start=1):
        target = OUT / window_filename(window)
        if target.exists():
            skipped += 1
            continue
        try:
            with client.open(window_url(window), timeout=60) as response:
                body = response.read()
        except urllib.error.URLError as exc:
            print(f"  {window.label}: request failed ({exc}). Stopping.")
            print("  Downloaded files are kept; re-run to resume where it left off.")
            return 1

        try:
            actions = load_actions_json(body, source=target.name)
        except CorporateActionParseError as exc:
            print(f"  {window.label}: {exc}")
            print("  Stopping rather than saving a file that is not the feed.")
            return 1

        target.write_bytes(body)
        saved += 1
        total_actions += len(actions)
        print(f"  [{index}/{len(windows)}] {window.label}: {len(actions)} equity actions")
        time.sleep(args.delay)

    print(f"\nsaved {saved}, already present {skipped}, {total_actions} equity actions")
    print(f"files in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
