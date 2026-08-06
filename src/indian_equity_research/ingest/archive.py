"""Append-only daily archive of sources that overwrite themselves.

Design rules, all of which exist because this data cannot be re-acquired:

* **Append-only.** A file already captured for a date is never re-fetched and
  never overwritten. Re-running the archiver twice in a day is a no-op.
* **Verbatim.** Bytes are stored exactly as received. No parsing, no cleaning,
  no normalisation. Interpretation happens downstream, where it can change
  without losing the original.
* **Refuse suspicious payloads.** An endpoint that has moved often answers with
  an HTML error page and status 200. Saving that would poison the archive
  silently, so it is rejected unless the source declares ``expect_html``.
* **Recorded provenance.** Each capture appends a manifest line with the URL,
  timestamp, byte count and SHA-256, so the archive can be audited later.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from indian_equity_research.constants import INDIA_TZ
from indian_equity_research.ingest.fetcher import Fetcher, FetchError, FetchResult
from indian_equity_research.ingest.sources import ArchiveSource
from indian_equity_research.logging_config import get_logger

__all__ = ["ArchiveOutcome", "ArchiveResult", "DailyArchiver"]

logger = get_logger(__name__)

MANIFEST_FILENAME = "manifest.jsonl"
#: Below this a "CSV" is almost certainly an error message, not data.
MIN_PLAUSIBLE_BYTES = 64


class ArchiveOutcome:
    """Outcome labels for a single source on a single day."""

    SAVED = "SAVED"
    ALREADY_HELD = "ALREADY_HELD"
    SKIPPED_DISABLED = "SKIPPED_DISABLED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    """What happened for one source.

    Attributes:
        source: Source name.
        outcome: One of the :class:`ArchiveOutcome` labels.
        path: Where the bytes were written, when they were.
        bytes_written: Size of the captured payload.
        detail: Human-readable explanation for failures and rejections.
    """

    source: str
    outcome: str
    path: Path | None = None
    bytes_written: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        """Whether the day's capture for this source is secured."""
        return self.outcome in (ArchiveOutcome.SAVED, ArchiveOutcome.ALREADY_HELD)


@dataclass(frozen=True, slots=True)
class DailyArchiver:
    """Captures each enabled source once per day into a dated archive.

    Attributes:
        root: Archive root, normally ``data/raw/archive``.
        fetcher: How bytes are retrieved.
    """

    root: Path
    fetcher: Fetcher

    def archive_all(
        self,
        sources: list[ArchiveSource],
        when: date | None = None,
        *,
        dry_run: bool = False,
    ) -> list[ArchiveResult]:
        """Capture every enabled source for a given date.

        Args:
            sources: The registry.
            when: Capture date. Defaults to today in IST, because an exchange
                day is an IST day and a UTC host would otherwise mislabel
                anything captured after 18:30 UTC.
            dry_run: Report what would happen without fetching or writing.

        Returns:
            One result per source, in registry order.
        """
        capture_date = when or datetime.now(tz=INDIA_TZ).date()
        return [self.archive_one(s, capture_date, dry_run=dry_run) for s in sources]

    def archive_one(
        self, source: ArchiveSource, when: date, *, dry_run: bool = False
    ) -> ArchiveResult:
        """Capture a single source for a single date.

        Args:
            source: The source to capture.
            when: Capture date.
            dry_run: Report the intended action without fetching or writing.

        Returns:
            The outcome.
        """
        if not source.enabled:
            return ArchiveResult(
                source.name,
                ArchiveOutcome.SKIPPED_DISABLED,
                detail="not yet verified; enable it in configs/archive_sources.yaml",
            )

        target = self.root / source.name / source.filename_for(when)
        if target.exists():
            return ArchiveResult(
                source.name,
                ArchiveOutcome.ALREADY_HELD,
                path=target,
                bytes_written=target.stat().st_size,
            )
        if dry_run:
            return ArchiveResult(source.name, ArchiveOutcome.SAVED, path=target, detail="dry run")

        try:
            result = self.fetcher.fetch(source.url)
        except FetchError as exc:
            logger.warning("Archive fetch failed for %s: %s", source.name, exc)
            return ArchiveResult(source.name, ArchiveOutcome.FAILED, detail=str(exc))

        rejection = self._reject_reason(result, source)
        if rejection:
            logger.warning("Rejected payload for %s: %s", source.name, rejection)
            return ArchiveResult(source.name, ArchiveOutcome.REJECTED, detail=rejection)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.content)
        self._append_manifest(source, target, result.content, when)
        logger.info("Archived %s (%d bytes)", source.name, len(result.content))
        return ArchiveResult(
            source.name, ArchiveOutcome.SAVED, path=target, bytes_written=len(result.content)
        )

    @staticmethod
    def _reject_reason(result: FetchResult, source: ArchiveSource) -> str:
        """Return why a payload should not be archived, or an empty string.

        Args:
            result: The fetch result.
            source: The source it came from.

        Returns:
            A reason, or ``""`` when the payload looks usable.
        """
        if len(result.content) < MIN_PLAUSIBLE_BYTES:
            return f"only {len(result.content)} bytes - too small to be real data"
        if result.looks_like_html() and not source.expect_html:
            return "response looks like an HTML page, not data - the URL has probably moved"
        return ""

    def _append_manifest(
        self, source: ArchiveSource, path: Path, content: bytes, when: date
    ) -> None:
        """Record provenance for a capture.

        Args:
            source: The source captured.
            path: Where it was written.
            content: The bytes written.
            when: Capture date.
        """
        entry = {
            "source": source.name,
            "url": source.url,
            "capture_date": when.isoformat(),
            "captured_at": datetime.now(tz=INDIA_TZ).isoformat(),
            "file": str(path.relative_to(self.root)),
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        manifest = self.root / MANIFEST_FILENAME
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
