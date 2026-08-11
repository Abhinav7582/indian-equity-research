"""Collect NSE Indices press releases without doing it by hand.

The problem
-----------
NSE Indices lists press releases at https://www.niftyindices.com/media, but the
year filter is applied **in the browser**, not in the URL. Fetching
``/media?year=2015`` returns exactly the same page as ``/media``: the current
ten months or so. Plain HTTP therefore cannot reach older years, and roughly
twelve years of releases are needed.

Two routes are provided, and they are complementary rather than alternatives.

**Route 1 — parse a saved listing.** Select a year in the browser, save the page
(*Save Page As → Webpage, HTML Only*), and :func:`extract_release_links` pulls
every release URL, date and title out of it. One save per year, then everything
downstream is automatic. This is the reliable route because the listing is
authoritative: nothing is guessed.

**Route 2 — sweep candidate dates.** Release URLs are deterministic
(``ind_prsDDMMYYYY.pdf``), and semi-annual reviews are announced in predictable
windows. :func:`plan_sweep` generates candidates for those windows only, so a
run is a few hundred polite requests rather than the ~4,300 a full brute force
would need.

Route 2 will miss interim changes — demergers, mergers, suspensions — because
those fall on unpredictable dates. That is a real limitation and not a
recoverable one by sweeping alone. It is survivable because
``reconstruct_membership`` refuses to return a membership that is not exactly
100, so a missing release announces itself as an error naming the period.
Sweep, reconstruct, read the failure, then sweep that window narrowly.

Manners
-------
Default delay is 2 seconds and the floor is 1. A 404 costs NSE almost nothing,
but several thousand of them in quick succession is rude, which is why the
sweep is windowed rather than exhaustive.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from indian_equity_research.ingest.fetcher import Fetcher, FetchResult

__all__ = [
    "CircularFetchConfig",
    "ReleaseLink",
    "SweepWindow",
    "extract_release_links",
    "is_possibly_relevant",
    "plan_sweep",
    "release_url",
]

BASE_URL: Final = "https://www.niftyindices.com/Press_Release"
LISTING_URL: Final = "https://www.niftyindices.com/media"

# Announcement windows for the semi-annual reviews, as (month, day) inclusive
# ranges, sized around the announcement dates actually observed: 24 Aug 2015,
# 24 Feb 2022, 28 Feb 2024, 23 Aug 2024, 22 Aug 2025, 10 Aug 2026.
#
# Deliberately narrow. Every date in a window costs three requests that will
# almost all be 404s, and widening by a week adds roughly 180 of them across
# twelve years. The windows only need to catch the semi-annual reviews --
# interim changes fall on unpredictable dates and are found by reconstructing
# membership and reading where it breaks, not by sweeping wider.
SEMI_ANNUAL_WINDOWS: Final = (
    ((2, 15), (3, 5)),
    ((8, 5), (9, 5)),
)

_HREF_RE: Final = re.compile(
    r"(?:https?://(?:www\.)?niftyindices\.com)?/Press_Release/(ind_prs[0-9]{8}(?:_\d+)?\.pdf)",
    re.IGNORECASE,
)
_FILENAME_DATE_RE: Final = re.compile(r"ind_prs(\d{2})(\d{2})(\d{4})")

# Titles that cannot possibly change Nifty 100 membership. Filtering these out
# is a convenience, never a correctness guarantee -- when in doubt the release
# is kept, because a wrongly skipped release is invisible and a wrongly kept
# one merely fails to parse.
_IRRELEVANT_MARKERS: Final = (
    "fixed income",
    "g-sec",
    "gsec",
    "sdl",
    "corporate bond",
    "money market",
    "t-bill",
    "municipal",
    "target maturity",
    "sme emerge",
    "maturity of nifty",
    "launches",
    "riskometer",
    "consultation",
)

_RELEVANT_MARKERS: Final = (
    "replacement",
    "change in indices",
    "change in nifty",
    "change in cnx",
    "inclusion",
    "exclusion",
    "corporate action",
    "index maintenance",
    "reconstitution",
)


@dataclass(frozen=True, slots=True)
class ReleaseLink:
    """One press release found on a listing page."""

    filename: str
    title: str = ""
    announced_on: date | None = None

    @property
    def url(self) -> str:
        """Absolute URL of the release PDF."""
        return f"{BASE_URL}/{self.filename}"

    @property
    def date_from_filename(self) -> date | None:
        """Announcement date decoded from the filename, if it parses."""
        match = _FILENAME_DATE_RE.match(self.filename)
        if not match:
            return None
        day, month, year = (int(g) for g in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None


def release_url(when: date, suffix: int | None = None) -> str:
    """URL for a release announced on ``when``.

    Several releases can share a date; NSE distinguishes them with ``_1``,
    ``_2`` and so on. ``suffix=None`` gives the unsuffixed first one.
    """
    stem = f"ind_prs{when.day:02d}{when.month:02d}{when.year:04d}"
    if suffix is not None:
        stem = f"{stem}_{suffix}"
    return f"{BASE_URL}/{stem}.pdf"


def extract_release_links(html: str) -> list[ReleaseLink]:
    """Pull every press-release link out of a saved listing page.

    Works on raw HTML and on the markdown-ish text some tools produce, because
    it matches the href itself rather than the surrounding markup. Duplicates
    are removed, order of first appearance is kept.

    Args:
        html: Contents of a saved ``/media`` page.

    Returns:
        Links found, newest first as the page presents them.
    """
    seen: set[str] = set()
    links: list[ReleaseLink] = []
    for line in html.splitlines():
        for match in _HREF_RE.finditer(line):
            filename = match.group(1)
            if filename in seen:
                continue
            seen.add(filename)
            links.append(ReleaseLink(filename=filename, title=_title_near(line)))
    return links


def _title_near(line: str) -> str:
    """Best-effort title from the same line as the link.

    Listings render as ``[Replacements in indices w.e.f. ...](url)`` in
    markdown or ``<a href="url">Replacements in indices</a>`` in HTML. Both put
    the title beside the href, so a line-local search is enough. An empty title
    is not an error: it only means the relevance filter cannot help.
    """
    bracketed = re.search(r"\[([^\]]{4,200})\]\(", line)
    if bracketed:
        return bracketed.group(1).strip()
    tagged = re.search(r">([^<>]{4,200})</a>", line)
    if tagged:
        return tagged.group(1).strip()
    return ""


def is_possibly_relevant(title: str) -> bool:
    """Whether a release might change equity index membership.

    Deliberately generous. An unknown or empty title returns True, because
    downloading a release that turns out to be irrelevant costs one request,
    while skipping one that mattered leaves a silent hole in the membership
    history that only surfaces much later as a failed reconstruction.
    """
    if not title.strip():
        return True
    lowered = title.lower()
    if any(marker in lowered for marker in _RELEVANT_MARKERS):
        # An explicit equity-change marker wins even if a noisy word is present,
        # except for the fixed-income families, which never touch the Nifty 100.
        return not ("fixed income" in lowered or "g-sec" in lowered)
    return not any(marker in lowered for marker in _IRRELEVANT_MARKERS)


@dataclass(frozen=True, slots=True)
class SweepWindow:
    """A date range to try candidate URLs in."""

    start: date
    end: date
    label: str = ""

    def __post_init__(self) -> None:
        """Reject windows that cannot be swept."""
        if self.end < self.start:
            raise ValueError(f"window end {self.end} precedes start {self.start}")

    def dates(self) -> Iterator[date]:
        """Every weekday in the window. NSE does not publish at weekends."""
        current = self.start
        while current <= self.end:
            if current.weekday() < 5:
                yield current
            current += timedelta(days=1)


def semi_annual_windows(first_year: int, last_year: int) -> list[SweepWindow]:
    """Announcement windows for the semi-annual reviews across a span of years."""
    windows: list[SweepWindow] = []
    for year in range(first_year, last_year + 1):
        for (start_month, start_day), (end_month, end_day) in SEMI_ANNUAL_WINDOWS:
            windows.append(
                SweepWindow(
                    start=date(year, start_month, start_day),
                    end=date(year, end_month, end_day),
                    label=f"{year}-{start_month:02d} review",
                )
            )
    return windows


def plan_sweep(
    windows: list[SweepWindow],
    *,
    already_have: set[str] | None = None,
) -> list[str]:
    """Base candidate URLs — one per date, no suffixes.

    Same-day variants (``_1``, ``_2``, …) are **not** planned here. They are
    followed at fetch time, and only for dates that actually produced a
    release. Planning them up front would triple the request count to chase
    variants that exist on maybe twenty days out of four hundred, and would
    still miss the ``_3`` and ``_4`` that busy days occasionally carry.

    Args:
        windows: Ranges to try.
        already_have: Filenames already downloaded, skipped rather than
            re-requested.

    Returns:
        URLs in chronological order.
    """
    have = already_have or set()
    urls: list[str] = []
    for window in windows:
        for day in window.dates():
            url = release_url(day)
            if url.rsplit("/", 1)[-1] in have:
                continue
            urls.append(url)
    return urls


@dataclass
class CircularFetchConfig:
    """Parameters for a download run."""

    destination: Path = field(default_factory=lambda: Path("data/raw/circulars"))
    delay_seconds: float = 2.0
    enabled: bool = False
    minimum_bytes: int = 2_000

    def __post_init__(self) -> None:
        """Enforce the politeness floor."""
        self.delay_seconds = max(self.delay_seconds, 1.0)
        if self.minimum_bytes < 0:
            raise ValueError("minimum_bytes must not be negative")


def looks_like_a_release(result: FetchResult, *, minimum_bytes: int = 2_000) -> bool:
    """Whether a response is a real PDF rather than a 404 page.

    NSE returns an HTML error page with status 200 for some missing files, so
    the status code alone is not enough.
    """
    if result.status != 200:
        return False
    if len(result.content) < minimum_bytes:
        return False
    return result.content.startswith(b"%PDF")


def fetch_releases(
    urls: list[str],
    fetcher: Fetcher,
    config: CircularFetchConfig,
    *,
    follow_suffixes: bool = True,
    suffix_limit: int = 9,
) -> tuple[list[Path], list[str]]:
    """Download ``urls`` that look like real releases.

    Nothing is written unless ``config.enabled`` is true, so a dry run is the
    default and a plan can always be inspected first.

    Args:
        urls: Base candidates, typically from :func:`plan_sweep`.
        fetcher: How to retrieve them.
        config: Destination, delay and enablement.
        follow_suffixes: After a hit, try ``_1``, ``_2`` … until one misses.
            This is where same-day variants are found, and it costs requests
            only on dates that already produced something.
        suffix_limit: Safety stop, so a server returning a valid PDF for every
            suffix cannot cause an unbounded loop.

    Returns:
        ``(written, missing)`` -- paths saved, and URLs that returned nothing
        usable. A long ``missing`` list is normal when sweeping: most candidate
        dates simply have no release.
    """
    written: list[Path] = []
    missing: list[str] = []
    if not config.enabled:
        return written, urls

    config.destination.mkdir(parents=True, exist_ok=True)
    for url in urls:
        saved = _try_one(url, fetcher, config, written, missing)
        if not (saved and follow_suffixes):
            continue
        for suffix in range(1, suffix_limit + 1):
            variant = url.replace(".pdf", f"_{suffix}.pdf")
            if not _try_one(variant, fetcher, config, written, missing):
                break
    return written, missing


def _try_one(
    url: str,
    fetcher: Fetcher,
    config: CircularFetchConfig,
    written: list[Path],
    missing: list[str],
) -> bool:
    """Fetch one URL. Returns True if a real release was saved or already held."""
    filename = url.rsplit("/", 1)[-1]
    target = config.destination / filename
    if target.exists():
        return True
    try:
        result = fetcher.fetch(url)
    except Exception:  # noqa: BLE001 - a missing candidate is normal when sweeping
        missing.append(url)
        return False
    if not looks_like_a_release(result, minimum_bytes=config.minimum_bytes):
        missing.append(url)
        return False
    target.write_bytes(result.content)
    written.append(target)
    return True
