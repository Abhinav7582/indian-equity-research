"""Historical bhavcopy backfill.

Every test runs offline against ``FakeFetcher``.
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from indian_equity_research.ingest.bhavcopy_fetch import (
    MIN_DELAY_SECONDS,
    BhavcopyFetchConfig,
    BhavcopyFetcher,
    FetchOutcome,
    plan_downloads,
)
from indian_equity_research.ingest.fetcher import FakeFetcher
from indian_equity_research.market.bhavcopy import BhavFormat

LEGACY_DAY = date(2024, 7, 5)  # Friday, before the changeover
UDIFF_DAY = date(2024, 7, 8)  # Monday, the changeover date
PAYLOAD = b"PK\x03\x04" + b"x" * 2048


def zip_bytes() -> bytes:
    import io as _io

    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.csv", "SYMBOL,SERIES\nX,EQ\n" + "pad," * 200)
    return buf.getvalue()


class TestUrlConstruction:
    def test_legacy_url_shape(self) -> None:
        url = BhavcopyFetchConfig().url_for(LEGACY_DAY)
        assert url.endswith("/2024/JUL/cm05JUL2024bhav.csv.zip")

    def test_udiff_url_shape(self) -> None:
        url = BhavcopyFetchConfig().url_for(UDIFF_DAY)
        assert url.endswith("BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip")

    def test_format_switches_on_the_changeover_date(self) -> None:
        cfg = BhavcopyFetchConfig()
        assert cfg.format_for(date(2024, 7, 5)) is BhavFormat.LEGACY
        assert cfg.format_for(date(2024, 7, 8)) is BhavFormat.UDIFF

    def test_filename_encodes_the_layout(self) -> None:
        """So a directory can be read back without re-deriving it from dates."""
        cfg = BhavcopyFetchConfig()
        assert cfg.filename_for(LEGACY_DAY) == "bhav_LEGACY_2024-07-05.csv.zip"
        assert cfg.filename_for(UDIFF_DAY) == "bhav_UDIFF_2024-07-08.csv.zip"

    def test_urls_are_configurable(self) -> None:
        cfg = BhavcopyFetchConfig(legacy_url_template="https://x.test/{yyyy}-{mon}-{dd}.zip")
        assert cfg.url_for(LEGACY_DAY) == "https://x.test/2024-JUL-05.zip"


class TestPoliteness:
    def test_delay_has_a_floor(self) -> None:
        """A caller cannot configure a hammering rate."""
        assert BhavcopyFetchConfig(delay_seconds=0.0).effective_delay == MIN_DELAY_SECONDS

    def test_delay_can_be_raised(self) -> None:
        assert BhavcopyFetchConfig(delay_seconds=10.0).effective_delay == 10.0

    def test_downloading_is_disabled_by_default(self) -> None:
        assert BhavcopyFetchConfig().enabled is False


class TestPlanning:
    def test_excludes_weekends(self, tmp_path: Path) -> None:
        plan = plan_downloads(date(2024, 7, 5), date(2024, 7, 8), tmp_path, BhavcopyFetchConfig())
        assert plan.wanted == (date(2024, 7, 5), date(2024, 7, 8))

    def test_known_sessions_remove_guaranteed_404s(self, tmp_path: Path) -> None:
        """A holiday request is a 404 by construction; skip it."""
        sessions = {date(2024, 7, 5)}
        plan = plan_downloads(
            date(2024, 7, 5), date(2024, 7, 8), tmp_path, BhavcopyFetchConfig(), sessions
        )
        assert plan.wanted == (date(2024, 7, 5),)

    def test_already_held_files_are_not_re_requested(self, tmp_path: Path) -> None:
        cfg = BhavcopyFetchConfig()
        (tmp_path / cfg.filename_for(LEGACY_DAY)).write_bytes(PAYLOAD)
        plan = plan_downloads(LEGACY_DAY, UDIFF_DAY, tmp_path, cfg)
        assert plan.already_held == (LEGACY_DAY,)
        assert plan.to_download == (UDIFF_DAY,)

    def test_estimates_wall_clock(self, tmp_path: Path) -> None:
        plan = plan_downloads(
            date(2024, 1, 1), date(2024, 12, 31), tmp_path, BhavcopyFetchConfig(delay_seconds=2.0)
        )
        assert 5 < plan.estimated_minutes < 15

    def test_reversed_range_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="precedes start"):
            plan_downloads(UDIFF_DAY, LEGACY_DAY, tmp_path, BhavcopyFetchConfig())

    def test_describe_is_informative(self, tmp_path: Path) -> None:
        plan = plan_downloads(LEGACY_DAY, UDIFF_DAY, tmp_path, BhavcopyFetchConfig())
        assert "to download" in plan.describe()


class TestFetching:
    def _fetcher(
        self, tmp_path: Path, responses: dict[str, bytes], **kw: object
    ) -> BhavcopyFetcher:
        cfg = BhavcopyFetchConfig(enabled=True, **kw)  # type: ignore[arg-type]
        return BhavcopyFetcher(tmp_path, FakeFetcher(responses=responses), cfg)

    def test_downloads_and_writes(self, tmp_path: Path) -> None:
        cfg = BhavcopyFetchConfig(enabled=True)
        f = BhavcopyFetcher(
            tmp_path, FakeFetcher(responses={cfg.url_for(LEGACY_DAY): zip_bytes()}), cfg
        )
        result = f.fetch_one(LEGACY_DAY)
        assert result.outcome == FetchOutcome.DOWNLOADED
        assert result.path is not None
        assert result.path.exists()

    def test_existing_file_is_not_re_requested(self, tmp_path: Path) -> None:
        cfg = BhavcopyFetchConfig(enabled=True)
        (tmp_path / cfg.filename_for(LEGACY_DAY)).write_bytes(PAYLOAD)
        fake = FakeFetcher(responses={})
        result = BhavcopyFetcher(tmp_path, fake, cfg).fetch_one(LEGACY_DAY)
        assert result.outcome == FetchOutcome.ALREADY_HELD
        assert fake.requested == []

    def test_a_404_is_reported_as_a_non_session_not_a_failure(self, tmp_path: Path) -> None:
        """A market holiday returns 404. That is the expected answer."""
        cfg = BhavcopyFetchConfig(enabled=True)
        f = BhavcopyFetcher(tmp_path, FakeFetcher(responses={}), cfg)
        assert f.fetch_one(LEGACY_DAY).outcome == FetchOutcome.NOT_A_SESSION

    def test_a_tiny_payload_is_rejected(self, tmp_path: Path) -> None:
        cfg = BhavcopyFetchConfig(enabled=True)
        f = BhavcopyFetcher(
            tmp_path, FakeFetcher(responses={cfg.url_for(LEGACY_DAY): b"nope"}), cfg
        )
        result = f.fetch_one(LEGACY_DAY)
        assert result.outcome == FetchOutcome.REJECTED
        assert not (tmp_path / cfg.filename_for(LEGACY_DAY)).exists()

    def test_an_html_page_is_rejected(self, tmp_path: Path) -> None:
        cfg = BhavcopyFetchConfig(enabled=True)
        body = b"<!DOCTYPE html><html>" + b" " * 2048
        f = BhavcopyFetcher(tmp_path, FakeFetcher(responses={cfg.url_for(LEGACY_DAY): body}), cfg)
        result = f.fetch_one(LEGACY_DAY)
        assert result.outcome == FetchOutcome.REJECTED
        assert "URL has moved" in result.detail

    def test_disabled_config_downloads_nothing(self, tmp_path: Path) -> None:
        cfg = BhavcopyFetchConfig(enabled=False)
        fake = FakeFetcher(responses={cfg.url_for(LEGACY_DAY): zip_bytes()})
        plan = plan_downloads(LEGACY_DAY, LEGACY_DAY, tmp_path, cfg)
        results = BhavcopyFetcher(tmp_path, fake, cfg).fetch_range(plan)
        assert fake.requested == []
        assert "disabled" in results[0].detail

    def test_limit_caps_a_cautious_first_run(self, tmp_path: Path) -> None:
        cfg = BhavcopyFetchConfig(enabled=True)
        responses = {
            cfg.url_for(d): zip_bytes()
            for d in (date(2024, 7, 1), date(2024, 7, 2), date(2024, 7, 3))
        }
        fake = FakeFetcher(responses=responses)
        plan = plan_downloads(date(2024, 7, 1), date(2024, 7, 3), tmp_path, cfg)
        results = BhavcopyFetcher(tmp_path, fake, cfg).fetch_range(plan, limit=2)
        assert len(results) == 2
