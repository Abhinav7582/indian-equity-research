"""Backfill historical bhavcopy files.

Unlike the daily archiver, this data **can** be re-acquired later - which is
why it was built second. But it is one published file per trading day, roughly
5,600 files for 23 years, so there is no realistic manual path.

The same discipline as the archiver applies, for the same reasons set out in
``docs/data_sources.md``:

* one request per file, never repeated - an already-downloaded date is skipped
  without a network call, so a run is resumable and re-running is nearly free;
* a generous delay between requests, configurable upward, never downward past
  a floor;
* URLs come from configuration, because NSE changes them and a stale URL
  hard-coded in Python is a silent failure;
* nothing is enabled until it has been verified reachable.

This is not legal advice. If you ever intend to publish, share or charge for
anything derived from this data, obtain a written licence first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from indian_equity_research.ingest.fetcher import Fetcher, FetchError
from indian_equity_research.logging_config import get_logger
from indian_equity_research.market.bhavcopy import UDIFF_EFFECTIVE_FROM, BhavFormat

__all__ = [
    "BhavcopyFetchConfig",
    "BhavcopyFetchPlan",
    "BhavcopyFetchResult",
    "BhavcopyFetcher",
    "FetchOutcome",
    "plan_downloads",
]

logger = get_logger(__name__)

#: Never poll faster than this, whatever the caller passes.
MIN_DELAY_SECONDS = 1.0
#: Below this a "zip" is an error page, not data.
MIN_PLAUSIBLE_BYTES = 512

_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


class FetchOutcome:
    """Outcome labels for one date."""

    DOWNLOADED = "DOWNLOADED"
    ALREADY_HELD = "ALREADY_HELD"
    NOT_A_SESSION = "NOT_A_SESSION"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class BhavcopyFetchConfig:
    """Where files come from and how politely.

    Attributes:
        legacy_url_template: Template for dates before the UDiFF changeover.
            Placeholders: ``{yyyy}``, ``{mon}``, ``{dd}``.
        udiff_url_template: Template from the changeover onward. Placeholder:
            ``{yyyymmdd}``.
        delay_seconds: Minimum pause between requests, floored at
            :data:`MIN_DELAY_SECONDS`.
        enabled: Whether downloading may proceed. Off until the URLs have been
            verified with ``fetch-bhavcopy --check``.
    """

    legacy_url_template: str = (
        "https://nsearchives.nseindia.com/content/historical/EQUITIES/"
        "{yyyy}/{mon}/cm{dd}{mon}{yyyy}bhav.csv.zip"
    )
    udiff_url_template: str = (
        "https://nsearchives.nseindia.com/content/cm/"
        "BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
    )
    delay_seconds: float = 2.0
    enabled: bool = False

    @property
    def effective_delay(self) -> float:
        """The delay actually used, never below the floor."""
        return max(self.delay_seconds, MIN_DELAY_SECONDS)

    def format_for(self, when: date) -> BhavFormat:
        """Return the layout published for a date.

        Args:
            when: Session date.

        Returns:
            The expected format.
        """
        return BhavFormat.UDIFF if when >= UDIFF_EFFECTIVE_FROM else BhavFormat.LEGACY

    def url_for(self, when: date) -> str:
        """Build the published URL for a session date.

        Args:
            when: Session date.

        Returns:
            The URL to request.
        """
        if self.format_for(when) is BhavFormat.UDIFF:
            return self.udiff_url_template.format(yyyymmdd=when.strftime("%Y%m%d"))
        return self.legacy_url_template.format(
            yyyy=when.year, mon=_MONTHS[when.month - 1], dd=f"{when.day:02d}"
        )

    def filename_for(self, when: date) -> str:
        """Return the local filename for a session date.

        The layout is encoded in the name so a directory can be read back
        without re-deriving it from the date.

        Args:
            when: Session date.

        Returns:
            A filename such as ``bhav_LEGACY_2024-07-05.csv.zip``.
        """
        return f"bhav_{self.format_for(when).value}_{when.isoformat()}.csv.zip"


@dataclass(frozen=True, slots=True)
class BhavcopyFetchResult:
    """What happened for one date.

    Attributes:
        when: Session date.
        outcome: One of the :class:`FetchOutcome` labels.
        path: Where the file was written, when it was.
        bytes_written: Size of the payload.
        detail: Explanation for failures and rejections.
    """

    when: date
    outcome: str
    path: Path | None = None
    bytes_written: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        """Whether the date's file is now held locally."""
        return self.outcome in (FetchOutcome.DOWNLOADED, FetchOutcome.ALREADY_HELD)


@dataclass(frozen=True, slots=True)
class BhavcopyFetchPlan:
    """What a run would do, before it does it.

    Attributes:
        wanted: Dates in scope.
        already_held: Dates already on disk.
        to_download: Dates that would be requested.
        config: Configuration used.
    """

    wanted: tuple[date, ...]
    already_held: tuple[date, ...]
    to_download: tuple[date, ...]
    config: BhavcopyFetchConfig

    @property
    def estimated_minutes(self) -> float:
        """Rough wall-clock estimate for the download, in minutes."""
        return len(self.to_download) * self.config.effective_delay / 60.0

    def describe(self) -> str:
        """Return a one-line summary of the plan."""
        return (
            f"{len(self.wanted):,} dates in scope, {len(self.already_held):,} already held, "
            f"{len(self.to_download):,} to download "
            f"(~{self.estimated_minutes:.0f} min at {self.config.effective_delay:.0f}s each)"
        )


def plan_downloads(
    start: date,
    end: date,
    destination: Path,
    config: BhavcopyFetchConfig,
    sessions: set[date] | None = None,
) -> BhavcopyFetchPlan:
    """Work out what a run would fetch, without fetching anything.

    Args:
        start: First date, inclusive.
        end: Last date, inclusive.
        destination: Directory files are stored in.
        config: Fetch configuration.
        sessions: Known trading sessions. When supplied, non-sessions are
            skipped entirely - which typically removes a third of the requests
            and every guaranteed 404.

    Returns:
        The plan.

    Raises:
        ValueError: If ``end`` precedes ``start``.
    """
    if end < start:
        message = f"end ({end.isoformat()}) precedes start ({start.isoformat()})."
        raise ValueError(message)

    wanted: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5 and (sessions is None or day in sessions):
            wanted.append(day)
        day += timedelta(days=1)

    held = [d for d in wanted if (destination / config.filename_for(d)).exists()]
    held_set = set(held)
    return BhavcopyFetchPlan(
        wanted=tuple(wanted),
        already_held=tuple(held),
        to_download=tuple(d for d in wanted if d not in held_set),
        config=config,
    )


@dataclass(frozen=True, slots=True)
class BhavcopyFetcher:
    """Downloads published bhavcopy files into a local directory.

    Attributes:
        destination: Where files are written.
        fetcher: How bytes are retrieved.
        config: URLs and politeness settings.
    """

    destination: Path
    fetcher: Fetcher
    config: BhavcopyFetchConfig

    def fetch_one(self, when: date) -> BhavcopyFetchResult:
        """Download a single session's file if it is not already held.

        Args:
            when: Session date.

        Returns:
            The outcome. A missing file for a non-session is reported as
            ``NOT_A_SESSION`` rather than a failure, because a 404 on a market
            holiday is the expected answer.
        """
        target = self.destination / self.config.filename_for(when)
        if target.exists():
            return BhavcopyFetchResult(
                when, FetchOutcome.ALREADY_HELD, target, target.stat().st_size
            )

        url = self.config.url_for(when)
        try:
            result = self.fetcher.fetch(url)
        except FetchError as exc:
            outcome = FetchOutcome.NOT_A_SESSION if "404" in str(exc) else FetchOutcome.FAILED
            return BhavcopyFetchResult(when, outcome, detail=str(exc))

        if len(result.content) < MIN_PLAUSIBLE_BYTES:
            return BhavcopyFetchResult(
                when,
                FetchOutcome.REJECTED,
                detail=f"only {len(result.content)} bytes - not a real archive",
            )
        if result.looks_like_html():
            return BhavcopyFetchResult(
                when,
                FetchOutcome.REJECTED,
                detail="response is an HTML page, not a zip - the URL has moved",
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.content)
        logger.info("Downloaded bhavcopy for %s (%d bytes)", when.isoformat(), len(result.content))
        return BhavcopyFetchResult(when, FetchOutcome.DOWNLOADED, target, len(result.content))

    def fetch_range(
        self, plan: BhavcopyFetchPlan, *, limit: int | None = None
    ) -> list[BhavcopyFetchResult]:
        """Download every date a plan says is missing.

        Args:
            plan: A plan from :func:`plan_downloads`.
            limit: Stop after this many downloads. Useful for a first cautious
                run against a freshly verified URL.

        Returns:
            One result per date attempted.
        """
        if not self.config.enabled:
            return [
                BhavcopyFetchResult(
                    d,
                    FetchOutcome.FAILED,
                    detail="downloading is disabled; verify the URLs first",
                )
                for d in plan.to_download[:1]
            ]
        results: list[BhavcopyFetchResult] = []
        for when in plan.to_download:
            if limit is not None and len(results) >= limit:
                break
            results.append(self.fetch_one(when))
        return results
