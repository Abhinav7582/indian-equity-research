"""Tests for press-release collection.

The listing fixture is taken from the real ``/media`` page, in the exact form
``web_fetch`` returned it, so the extractor is tested against what the site
actually serves rather than an idealised version of it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from indian_equity_research.ingest.circulars_fetch import (
    BASE_URL,
    CircularFetchConfig,
    SweepWindow,
    extract_release_links,
    fetch_releases,
    is_possibly_relevant,
    looks_like_a_release,
    plan_sweep,
    release_url,
    semi_annual_windows,
)
from indian_equity_research.ingest.fetcher import FetchResult

# Verbatim from the rendered /media listing.
LISTING = """
- August 10, 2026     [Replacements in indices w.e.f. September 30, 2026](https://www.niftyindices.com/Press_Release/ind_prs10082026.pdf)
- August 10, 2026     [Exclusion from Nifty SME Emerge index w.e.f. August 12, 2026](https://www.niftyindices.com/Press_Release/ind_prs10082026_1.pdf)
- August 10, 2026     [Replacements in indices w.e.f. August 31, 2026](https://www.niftyindices.com/Press_Release/ind_prs10082026_3.pdf)
- August 06, 2026     [Changes in Nifty Fixed Income indices w.e.f. August 11 2026](https://www.niftyindices.com/Press_Release/ind_prs06082026.pdf)
- August 06, 2026     [NSE Indices launches Nifty India Defence Equal Weight Index](https://www.niftyindices.com/Press_Release/ind_prs06082026_1.pdf)
- July 28, 2026     [Corporate Action Adjustment for Inox Green Energy Ltd. in Nifty Indices](https://www.niftyindices.com/Press_Release/ind_prs28072026_1.pdf)
"""

HTML_LISTING = (
    '<li><span>Sep 18, 2015</span>'
    '<a href="/Press_Release/ind_prs18092015.pdf">Change in Indices w.e.f October 19, 2015</a>'
    "</li>"
)


# --------------------------------------------------------------------------
# Extracting links from a saved listing
# --------------------------------------------------------------------------


def test_every_release_link_is_found() -> None:
    links = extract_release_links(LISTING)
    assert [link.filename for link in links] == [
        "ind_prs10082026.pdf",
        "ind_prs10082026_1.pdf",
        "ind_prs10082026_3.pdf",
        "ind_prs06082026.pdf",
        "ind_prs06082026_1.pdf",
        "ind_prs28072026_1.pdf",
    ]


def test_titles_are_captured_alongside_the_link() -> None:
    links = extract_release_links(LISTING)
    assert links[0].title.startswith("Replacements in indices")
    assert "Fixed Income" in links[3].title


def test_relative_hrefs_in_saved_html_are_found() -> None:
    """A browser 'Save Page As' can rewrite absolute URLs to relative ones."""
    links = extract_release_links(HTML_LISTING)
    assert len(links) == 1
    assert links[0].filename == "ind_prs18092015.pdf"
    assert links[0].title == "Change in Indices w.e.f October 19, 2015"


def test_duplicates_are_collapsed() -> None:
    """The live page repeats its list twice in the markup."""
    assert len(extract_release_links(LISTING + LISTING)) == 6


def test_the_date_is_recovered_from_the_filename() -> None:
    links = extract_release_links(LISTING)
    assert links[0].date_from_filename == dt.date(2026, 8, 10)
    assert links[-1].date_from_filename == dt.date(2026, 7, 28)


def test_a_malformed_filename_gives_no_date_rather_than_raising() -> None:
    from indian_equity_research.ingest.circulars_fetch import ReleaseLink

    assert ReleaseLink(filename="ind_prs99999999.pdf").date_from_filename is None


def test_url_is_reconstructed_correctly() -> None:
    links = extract_release_links(LISTING)
    assert links[0].url == f"{BASE_URL}/ind_prs10082026.pdf"


# --------------------------------------------------------------------------
# Relevance filtering, which must err toward keeping things
# --------------------------------------------------------------------------


def test_equity_replacements_are_kept() -> None:
    assert is_possibly_relevant("Replacements in indices w.e.f. September 30, 2026")
    assert is_possibly_relevant("Change in Indices w.e.f October 19, 2015")
    assert is_possibly_relevant("Change in CNX Alpha, CNX High Beta w.e.f October 19, 2015")


def test_clearly_unrelated_releases_are_dropped() -> None:
    assert not is_possibly_relevant("Changes in Nifty Fixed Income indices w.e.f. August 11 2026")
    assert not is_possibly_relevant("NSE Indices launches Nifty India Defence Equal Weight Index")
    assert not is_possibly_relevant("Maturity of Nifty Fixed Income index w.e.f. September 02")


def test_an_unknown_title_is_kept() -> None:
    """The asymmetry that matters.

    A wrongly kept release costs one HTTP request and then fails to parse
    loudly. A wrongly skipped one leaves a hole in the membership history that
    surfaces months later as a failed reconstruction.
    """
    assert is_possibly_relevant("")
    assert is_possibly_relevant("Some heading nobody anticipated")


def test_corporate_action_releases_are_kept() -> None:
    """These change index composition even though they are not reviews."""
    assert is_possibly_relevant(
        "Corporate Action Adjustment for Inox Green Energy Services Ltd. in Nifty Indices"
    )


# --------------------------------------------------------------------------
# The sweep
# --------------------------------------------------------------------------


def test_release_url_formats_the_date_correctly() -> None:
    assert release_url(dt.date(2025, 8, 22)) == f"{BASE_URL}/ind_prs22082025.pdf"
    assert release_url(dt.date(2015, 2, 4)) == f"{BASE_URL}/ind_prs04022015.pdf"
    assert release_url(dt.date(2025, 8, 22), 1) == f"{BASE_URL}/ind_prs22082025_1.pdf"


def test_the_url_pattern_matches_releases_confirmed_to_exist() -> None:
    """Anchored to files fetched successfully during development."""
    assert release_url(dt.date(2025, 8, 22)).endswith("ind_prs22082025.pdf")
    assert release_url(dt.date(2015, 8, 24)).endswith("ind_prs24082015.pdf")
    assert release_url(dt.date(2024, 2, 28)).endswith("ind_prs28022024.pdf")


def test_windows_skip_weekends() -> None:
    window = SweepWindow(dt.date(2025, 8, 22), dt.date(2025, 8, 26))  # Fri..Tue
    assert list(window.dates()) == [
        dt.date(2025, 8, 22),
        dt.date(2025, 8, 25),
        dt.date(2025, 8, 26),
    ]


def test_a_backwards_window_is_refused() -> None:
    with pytest.raises(ValueError, match="precedes start"):
        SweepWindow(dt.date(2025, 8, 26), dt.date(2025, 8, 22))


def test_semi_annual_windows_cover_both_reviews_each_year() -> None:
    windows = semi_annual_windows(2015, 2026)
    assert len(windows) == 24
    assert all(w.start.month in (2, 8) for w in windows)


def test_the_confirmed_announcement_dates_fall_inside_the_windows() -> None:
    """The windows are only useful if they contain the reviews we know about."""
    known = [
        dt.date(2015, 8, 24),
        dt.date(2022, 2, 24),
        dt.date(2024, 2, 28),
        dt.date(2024, 8, 23),
        dt.date(2025, 8, 22),
        dt.date(2026, 8, 10),
    ]
    windows = semi_annual_windows(2015, 2026)
    for day in known:
        assert any(w.start <= day <= w.end for w in windows), f"{day} falls outside every window"


def test_sweep_size_is_modest() -> None:
    """Keep the request count small.

    A full brute force over twelve years is roughly 4,300 requests, almost all
    404s. Planning suffixes up front tripled it to ~1,300. Planning base URLs
    only, and following suffixes solely on dates that hit, brings it under 500
    -- about fifteen minutes at the 2-second default.
    """
    urls = plan_sweep(semi_annual_windows(2015, 2026))
    assert 300 < len(urls) < 600, f"sweep is {len(urls)} requests"
    assert len(urls) * 2 / 60 < 20


def test_files_already_held_are_not_requested_again() -> None:
    windows = [SweepWindow(dt.date(2025, 8, 22), dt.date(2025, 8, 22))]
    assert plan_sweep(windows) == [release_url(dt.date(2025, 8, 22))]
    assert plan_sweep(windows, already_have={"ind_prs22082025.pdf"}) == []


def test_the_plan_holds_no_suffixed_urls() -> None:
    """Suffixes are followed at fetch time, not planned."""
    urls = plan_sweep(semi_annual_windows(2025, 2025))
    assert not any("_1.pdf" in u or "_2.pdf" in u for u in urls)


def test_suffixes_are_followed_only_after_a_hit(tmp_path: Path) -> None:
    """The whole point of the adaptive sweep.

    A date with a release gets its variants chased; a date without one costs
    exactly one request.
    """
    hit = release_url(dt.date(2025, 8, 22))
    miss = release_url(dt.date(2025, 8, 21))
    available = {hit, hit.replace(".pdf", "_1.pdf"), hit.replace(".pdf", "_2.pdf")}
    fetcher = StubFetcher(available)

    written, _ = fetch_releases(
        [miss, hit], fetcher, CircularFetchConfig(destination=tmp_path, enabled=True)
    )
    assert sorted(p.name for p in written) == [
        "ind_prs22082025.pdf",
        "ind_prs22082025_1.pdf",
        "ind_prs22082025_2.pdf",
    ]
    # miss: 1 request. hit: base + _1 + _2 + the _3 that stops the chain.
    assert len(fetcher.requested) == 5


def test_a_variant_beyond_the_fixed_old_limit_is_still_found(tmp_path: Path) -> None:
    """Real listings carry an ``_3``; a hardcoded max of 2 would have lost it."""
    hit = release_url(dt.date(2026, 8, 10))
    available = {hit} | {hit.replace(".pdf", f"_{i}.pdf") for i in (1, 2, 3)}
    fetcher = StubFetcher(available)
    written, _ = fetch_releases(
        [hit], fetcher, CircularFetchConfig(destination=tmp_path, enabled=True)
    )
    assert len(written) == 4


def test_suffix_following_cannot_loop_forever(tmp_path: Path) -> None:
    class AlwaysYes:
        def fetch(self, url: str) -> FetchResult:
            return FetchResult(url=url, content=b"%PDF-1.7" + b"0" * 5_000, status=200)

    written, _ = fetch_releases(
        [release_url(dt.date(2025, 8, 22))],
        AlwaysYes(),
        CircularFetchConfig(destination=tmp_path, enabled=True),
        suffix_limit=4,
    )
    assert len(written) == 5  # base + _1.._4


# --------------------------------------------------------------------------
# Recognising a real PDF from a 404 page
# --------------------------------------------------------------------------


def test_a_real_pdf_is_accepted() -> None:
    result = FetchResult(url="x", content=b"%PDF-1.7" + b"0" * 5_000, status=200)
    assert looks_like_a_release(result)


def test_an_html_error_page_returned_with_status_200_is_rejected() -> None:
    """Reject an HTML error page served with status 200.

    NSE does this for some missing files. Trusting the status code alone would
    save thousands of junk files that all look like successful downloads.
    """
    result = FetchResult(url="x", content=b"<html><body>Not found</body></html>" * 200, status=200)
    assert not looks_like_a_release(result)


def test_a_truncated_pdf_is_rejected() -> None:
    result = FetchResult(url="x", content=b"%PDF-1.7 tiny", status=200)
    assert not looks_like_a_release(result)


def test_a_non_200_is_rejected() -> None:
    result = FetchResult(url="x", content=b"%PDF-1.7" + b"0" * 5_000, status=404)
    assert not looks_like_a_release(result)


# --------------------------------------------------------------------------
# Downloading
# --------------------------------------------------------------------------


class StubFetcher:
    """Serves a PDF for known URLs and raises for everything else."""

    def __init__(self, available: set[str]) -> None:
        """Record which URLs will succeed."""
        self.available = available
        self.requested: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.requested.append(url)
        if url not in self.available:
            raise RuntimeError("404")
        return FetchResult(url=url, content=b"%PDF-1.7" + b"0" * 5_000, status=200)


def test_nothing_is_written_unless_explicitly_enabled(tmp_path: Path) -> None:
    """Dry run is the default, so a plan can always be inspected first."""
    urls = [release_url(dt.date(2025, 8, 22))]
    fetcher = StubFetcher(set(urls))
    written, missing = fetch_releases(urls, fetcher, CircularFetchConfig(destination=tmp_path))
    assert written == []
    assert missing == urls
    assert fetcher.requested == [], "a dry run must not touch the network"


def test_enabled_run_writes_only_real_releases(tmp_path: Path) -> None:
    good = release_url(dt.date(2025, 8, 22))
    bad = release_url(dt.date(2025, 8, 21))
    fetcher = StubFetcher({good})
    written, missing = fetch_releases(
        [good, bad], fetcher, CircularFetchConfig(destination=tmp_path, enabled=True)
    )
    assert [p.name for p in written] == ["ind_prs22082025.pdf"]
    assert (tmp_path / "ind_prs22082025.pdf").read_bytes().startswith(b"%PDF")
    # The bad date, plus the _1 probe that ended the suffix chain on the good one.
    assert bad in missing
    assert good.replace(".pdf", "_1.pdf") in missing


def test_existing_files_are_not_refetched(tmp_path: Path) -> None:
    """A held file is never re-downloaded, and is never overwritten.

    It still counts as a hit for suffix-following, so re-running a sweep picks
    up variants NSE published after the first pass.
    """
    url = release_url(dt.date(2025, 8, 22))
    (tmp_path / "ind_prs22082025.pdf").write_bytes(b"%PDF already here")
    fetcher = StubFetcher({url})
    written, _ = fetch_releases(
        [url], fetcher, CircularFetchConfig(destination=tmp_path, enabled=True)
    )
    assert written == []
    assert url not in fetcher.requested, "a held file was requested again"
    assert (tmp_path / "ind_prs22082025.pdf").read_bytes() == b"%PDF already here"
    assert fetcher.requested == [url.replace(".pdf", "_1.pdf")]


def test_the_delay_floor_cannot_be_undercut() -> None:
    assert CircularFetchConfig(delay_seconds=0.0).delay_seconds == 1.0
    assert CircularFetchConfig(delay_seconds=5.0).delay_seconds == 5.0
