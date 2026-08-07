"""Prospective archiver: append-only capture of sources that overwrite daily.

Every test runs offline against ``FakeFetcher``. Nothing here touches a
network, which is the same discipline applied to the broker layer.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from indian_equity_research.exceptions import ConfigurationError
from indian_equity_research.ingest.archive import (
    ArchiveOutcome,
    DailyArchiver,
)
from indian_equity_research.ingest.fetcher import FakeFetcher, FetchResult
from indian_equity_research.ingest.sources import ArchiveSource, load_sources

WHEN = date(2026, 8, 6)
URL = "https://example.test/asm.csv"
GOOD = b"SYMBOL,SERIES,STAGE\nRELIANCE,EQ,1\nTCS,EQ,2\n" + b"x" * 64


def source(**kw: object) -> ArchiveSource:
    defaults: dict[str, object] = {
        "name": "asm",
        "url": URL,
        "description": "test source",
        "enabled": True,
    }
    defaults.update(kw)
    return ArchiveSource(**defaults)  # type: ignore[arg-type]


class TestCapture:
    def test_saves_bytes_verbatim(self, tmp_path: Path) -> None:
        fetcher = FakeFetcher(responses={URL: GOOD})
        result = DailyArchiver(tmp_path, fetcher).archive_one(source(), WHEN)
        assert result.outcome == ArchiveOutcome.SAVED
        assert result.path is not None
        assert result.path.read_bytes() == GOOD

    def test_filename_carries_the_capture_date(self, tmp_path: Path) -> None:
        fetcher = FakeFetcher(responses={URL: GOOD})
        result = DailyArchiver(tmp_path, fetcher).archive_one(source(), WHEN)
        assert result.path is not None
        assert result.path.name == "asm_2026-08-06.csv"

    def test_never_refetches_what_it_already_holds(self, tmp_path: Path) -> None:
        """Re-running the archiver twice in a day must be a no-op."""
        fetcher = FakeFetcher(responses={URL: GOOD})
        archiver = DailyArchiver(tmp_path, fetcher)
        archiver.archive_one(source(), WHEN)
        second = archiver.archive_one(source(), WHEN)
        assert second.outcome == ArchiveOutcome.ALREADY_HELD
        assert fetcher.requested == [URL]  # exactly one request, not two

    def test_existing_capture_is_never_overwritten(self, tmp_path: Path) -> None:
        archiver = DailyArchiver(tmp_path, FakeFetcher(responses={URL: GOOD}))
        archiver.archive_one(source(), WHEN)
        path = tmp_path / "asm" / "asm_2026-08-06.csv"
        archiver2 = DailyArchiver(tmp_path, FakeFetcher(responses={URL: b"DIFFERENT" * 20}))
        archiver2.archive_one(source(), WHEN)
        assert path.read_bytes() == GOOD

    def test_different_days_are_separate_captures(self, tmp_path: Path) -> None:
        fetcher = FakeFetcher(responses={URL: GOOD})
        archiver = DailyArchiver(tmp_path, fetcher)
        archiver.archive_one(source(), date(2026, 8, 6))
        archiver.archive_one(source(), date(2026, 8, 7))
        assert len(list((tmp_path / "asm").glob("*.csv"))) == 2


class TestRejection:
    def test_rejects_an_html_error_page(self, tmp_path: Path) -> None:
        """An endpoint that has moved often answers 200 with a friendly page."""
        html = b"<!DOCTYPE html><html><body>Page not found</body></html>" + b" " * 64
        result = DailyArchiver(tmp_path, FakeFetcher(responses={URL: html})).archive_one(
            source(), WHEN
        )
        assert result.outcome == ArchiveOutcome.REJECTED
        assert "HTML" in result.detail or "html" in result.detail

    def test_rejects_a_suspiciously_small_payload(self, tmp_path: Path) -> None:
        result = DailyArchiver(tmp_path, FakeFetcher(responses={URL: b"error"})).archive_one(
            source(), WHEN
        )
        assert result.outcome == ArchiveOutcome.REJECTED
        assert "too small" in result.detail

    def test_allows_html_when_the_source_declares_it(self, tmp_path: Path) -> None:
        html = b"<html><body>" + b"data" * 40 + b"</body></html>"
        result = DailyArchiver(tmp_path, FakeFetcher(responses={URL: html})).archive_one(
            source(expect_html=True), WHEN
        )
        assert result.outcome == ArchiveOutcome.SAVED

    def test_rejected_payloads_are_not_written(self, tmp_path: Path) -> None:
        DailyArchiver(tmp_path, FakeFetcher(responses={URL: b"tiny"})).archive_one(source(), WHEN)
        assert not (tmp_path / "asm").exists()

    def test_fetch_failure_is_reported_not_raised(self, tmp_path: Path) -> None:
        result = DailyArchiver(tmp_path, FakeFetcher(failures={URL})).archive_one(source(), WHEN)
        assert result.outcome == ArchiveOutcome.FAILED
        assert result.ok is False


class TestDisabledAndDryRun:
    def test_disabled_sources_are_not_fetched(self, tmp_path: Path) -> None:
        fetcher = FakeFetcher(responses={URL: GOOD})
        result = DailyArchiver(tmp_path, fetcher).archive_one(source(enabled=False), WHEN)
        assert result.outcome == ArchiveOutcome.SKIPPED_DISABLED
        assert fetcher.requested == []

    def test_dry_run_neither_fetches_nor_writes(self, tmp_path: Path) -> None:
        fetcher = FakeFetcher(responses={URL: GOOD})
        result = DailyArchiver(tmp_path, fetcher).archive_one(source(), WHEN, dry_run=True)
        assert result.detail == "dry run"
        assert fetcher.requested == []
        assert not (tmp_path / "asm").exists()


class TestManifest:
    def test_records_provenance_for_each_capture(self, tmp_path: Path) -> None:
        DailyArchiver(tmp_path, FakeFetcher(responses={URL: GOOD})).archive_one(source(), WHEN)
        lines = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
        entry = json.loads(lines[0])
        assert entry["source"] == "asm"
        assert entry["url"] == URL
        assert entry["capture_date"] == "2026-08-06"
        assert entry["bytes"] == len(GOOD)
        assert len(entry["sha256"]) == 64

    def test_manifest_is_append_only(self, tmp_path: Path) -> None:
        archiver = DailyArchiver(tmp_path, FakeFetcher(responses={URL: GOOD}))
        archiver.archive_one(source(), date(2026, 8, 6))
        archiver.archive_one(source(), date(2026, 8, 7))
        lines = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2


class TestArchiveAll:
    def test_one_result_per_source_in_order(self, tmp_path: Path) -> None:
        a = source(name="a", url="https://x.test/a.csv")
        b = source(name="b", url="https://x.test/b.csv", enabled=False)
        fetcher = FakeFetcher(responses={"https://x.test/a.csv": GOOD})
        results = DailyArchiver(tmp_path, fetcher).archive_all([a, b], WHEN)
        assert [r.source for r in results] == ["a", "b"]
        assert results[0].outcome == ArchiveOutcome.SAVED
        assert results[1].outcome == ArchiveOutcome.SKIPPED_DISABLED


class TestSourceRegistry:
    def test_loads_the_shipped_registry(self) -> None:
        from indian_equity_research.constants import CONFIG_DIR

        sources = load_sources(CONFIG_DIR / "archive_sources.yaml")
        assert len(sources) >= 4
        # Automated sources are fetched from `url`; manual ones send a human
        # to `manual_url`. Either way, somewhere over HTTPS.
        assert all((s.manual_url if s.manual else s.url).startswith("https://") for s in sources)

    def test_every_registered_source_is_well_formed(self) -> None:
        """Structural invariants only.

        ``archive_sources.yaml`` is edited by the operator as endpoints are
        verified, so asserting that everything is disabled would fail the
        moment the archiver is actually put to use. What must hold regardless
        is that every entry is complete and points somewhere over HTTPS -
        `url` for an automated source, `manual_url` for one captured by hand.
        """
        from indian_equity_research.constants import CONFIG_DIR

        for source in load_sources(CONFIG_DIR / "archive_sources.yaml"):
            assert source.name
            assert source.description
            assert source.extension
            target = source.manual_url if source.manual else source.url
            assert target.startswith("https://"), f"{source.name} has no https target"

    def test_new_sources_default_to_disabled(self, tmp_path: Path) -> None:
        """A source added without an explicit flag must not start fetching."""
        p = tmp_path / "s.yaml"
        p.write_text(
            "sources:\n  - {name: x, url: 'https://x.test/a.csv', description: d}\n",
            encoding="utf-8",
        )
        assert load_sources(p)[0].enabled is False

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="not found"):
            load_sources(tmp_path / "absent.yaml")

    def test_missing_required_field(self, tmp_path: Path) -> None:
        p = tmp_path / "s.yaml"
        p.write_text("sources:\n  - name: x\n    url: https://x.test\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="description"):
            load_sources(p)

    def test_duplicate_names_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "s.yaml"
        p.write_text(
            "sources:\n"
            "  - {name: x, url: 'https://a.test', description: a}\n"
            "  - {name: x, url: 'https://b.test', description: b}\n",
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError, match="duplicate"):
            load_sources(p)

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "s.yaml"
        p.write_text("sources: [unclosed\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="not valid YAML"):
            load_sources(p)


class TestFetchResult:
    @pytest.mark.parametrize("body", [b"<!DOCTYPE html><html>", b"<html><head>", b"  <HTML>"])
    def test_detects_html_bodies(self, body: bytes) -> None:
        assert FetchResult(URL, body).looks_like_html()

    def test_csv_is_not_html(self) -> None:
        assert not FetchResult(URL, b"SYMBOL,SERIES\nX,EQ").looks_like_html()

    def test_detects_html_content_type(self) -> None:
        assert FetchResult(URL, b"data", content_type="text/html; charset=utf-8").looks_like_html()
