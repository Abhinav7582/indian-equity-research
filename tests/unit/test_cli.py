"""Command-line interface: behaviour and exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from indian_equity_research import __version__
from indian_equity_research.cli import COMMANDS, EXIT_FAILURE, EXIT_OK, build_parser, main


class TestParser:
    def test_requires_a_subcommand(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            build_parser().parse_args([])
        assert exc_info.value.code == 2

    def test_rejects_an_unknown_subcommand(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            build_parser().parse_args(["backtest"])
        assert exc_info.value.code == 2

    def test_exposes_exactly_the_three_read_only_commands(self) -> None:
        """Guards the Phase 1 scope boundary.

        Asserts on the declared command set rather than the help text, because
        the help text deliberately contains the words "place orders" in its
        safety notice.

        The set has grown three times: `h4-regime` in Phase 1.5 (reads local
        CSVs, opens no socket), `archive` in Phase 2a (fetches published
        exchange files, one request per source per day, writing only into the
        git-ignored data directory), and `reference` in Phase 2b (reads local
        data and prints a report).

        Neither can place an order. The invariant this guards is **no broker
        connectivity and no order placement**, not "never add a command" -
        which is why `test_no_broker_dependency_anywhere` below is the real
        boundary and this assertion is the tripwire that forces a reviewer to
        look.

        Later additions, each of which tripped this assertion deliberately:
        `bhavcopy` (Phase 2d, downloads exchange files) and `circulars`
        (Phase 3a, downloads NSE index-change press releases and reads them).
        Both are read-only against public documents and write only into the
        git-ignored data directory.
        """
        assert set(COMMANDS) == {
            "version",
            "config-check",
            "db-health",
            "h4-regime",
            "archive",
            "reference",
            "bhavcopy",
            "circulars",
        }

    def test_every_declared_command_is_registered(self) -> None:
        parser = build_parser()
        for command in COMMANDS:
            assert parser.parse_args([command]).command == command

    def test_h4_command_accepts_a_data_directory(self) -> None:
        args = build_parser().parse_args(["h4-regime", "--data-dir", "/tmp/x"])
        assert args.command == "h4-regime"
        assert str(args.data_dir) == "/tmp/x"

    def test_no_command_can_reach_a_broker(self) -> None:
        """No CLI code path references broker or order-placement machinery."""
        import indian_equity_research.cli as cli_module

        source = Path(cli_module.__file__ or "").read_text(encoding="utf-8").lower()
        for forbidden in ("growwapi", "place_order", "modify_order", "cancel_order"):
            assert forbidden not in source

    def test_no_broker_dependency_anywhere_in_the_package(self) -> None:
        """The real scope boundary: no broker SDK is imported by any module."""
        import indian_equity_research

        package_root = Path(indian_equity_research.__file__ or "").parent
        forbidden = (
            "growwapi",
            "kiteconnect",
            "smartapi",
            "fyers",
            "dhanhq",
            "upstox",
            "ccxt",
            "binance",
        )
        for module in package_root.rglob("*.py"):
            text = module.read_text(encoding="utf-8").lower()
            for name in forbidden:
                assert name not in text, f"{module.name} references {name}"

    def test_bhavcopy_defaults_to_a_dry_run(self) -> None:
        """Downloading must be an explicit choice, never the default."""
        args = build_parser().parse_args(["bhavcopy", "--from", "2024-01-01", "--to", "2024-01-31"])
        assert args.fetch is False

    def test_bhavcopy_flags(self) -> None:
        args = build_parser().parse_args(["bhavcopy", "--check", "--delay", "5", "--limit", "10"])
        assert args.check is True
        assert args.delay == 5.0
        assert args.limit == 10

    def test_archive_command_flags(self) -> None:
        args = build_parser().parse_args(["archive", "--check", "--delay", "5"])
        assert args.command == "archive"
        assert args.check is True
        assert args.delay == 5.0


class TestVersionCommand:
    def test_exits_zero(self) -> None:
        assert main(["version"]) == EXIT_OK

    def test_prints_the_package_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        main(["version"])
        assert capsys.readouterr().out.strip() == __version__


class TestConfigCheckCommand:
    def test_exits_zero_with_valid_configuration(self) -> None:
        assert main(["config-check"]) == EXIT_OK

    def test_output_never_contains_the_password(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        secret = "cli-visible-secret"
        monkeypatch.setenv("DATABASE_PASSWORD", secret)
        assert main(["config-check"]) == EXIT_OK
        captured = capsys.readouterr()
        assert secret not in captured.out
        assert secret not in captured.err
        assert "<set>" in captured.out

    def test_reports_the_key_settings(self, capsys: pytest.CaptureFixture[str]) -> None:
        main(["config-check"])
        out = capsys.readouterr().out
        for key in ("app_env", "database_host", "database_url", "log_level"):
            assert key in out

    def test_exits_non_zero_on_invalid_configuration(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("DATABASE_PORT", "not-a-port")
        assert main(["config-check"]) == EXIT_FAILURE
        assert "Configuration error" in capsys.readouterr().out


class TestDbHealthCommand:
    def test_exits_non_zero_when_the_database_is_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("DATABASE_HOST", "127.0.0.1")
        monkeypatch.setenv("DATABASE_PORT", "1")
        monkeypatch.setenv("DATABASE_SSL_MODE", "disable")
        assert main(["db-health"]) == EXIT_FAILURE
        assert "FAIL" in capsys.readouterr().out

    def test_failure_output_does_not_leak_the_password(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        secret = "db-health-secret"
        monkeypatch.setenv("DATABASE_HOST", "127.0.0.1")
        monkeypatch.setenv("DATABASE_PORT", "1")
        monkeypatch.setenv("DATABASE_SSL_MODE", "disable")
        monkeypatch.setenv("DATABASE_PASSWORD", secret)
        main(["db-health"])
        captured = capsys.readouterr()
        assert secret not in captured.out
        assert secret not in captured.err


class TestCircularsCommand:
    """The circulars command downloads public documents and reads them.

    It writes only into the git-ignored data directory and places no order.
    These tests pin the behaviour that keeps it safe: a dry run by default,
    and clear guidance rather than a stack trace when inputs are absent.

    Every test that touches the filesystem is pointed at an empty temporary
    directory. An earlier version read the real ``data/`` tree and passed only
    because it happened to be empty; the moment real files landed, three tests
    failed for reasons that had nothing to do with the code. A suite whose
    result depends on the developer's local data is not a suite.
    """

    @pytest.fixture(autouse=True)
    def _isolated_data_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Point every setting at an empty tree, never the real one."""
        monkeypatch.setenv("DATA_ROOT", str(tmp_path))
        monkeypatch.setenv("RAW_DIR", str(tmp_path / "raw"))
        monkeypatch.setenv("INTERIM_DIR", str(tmp_path / "interim"))
        monkeypatch.setenv("PROCESSED_DIR", str(tmp_path / "processed"))
        monkeypatch.setenv("REFERENCE_DIR", str(tmp_path / "reference"))

    def test_the_command_is_registered_with_its_flags(self) -> None:
        args = build_parser().parse_args(
            ["circulars", "--sweep", "--first-year", "2020", "--last-year", "2021"]
        )
        assert args.command == "circulars"
        assert args.sweep is True
        assert args.first_year == 2020
        assert args.last_year == 2021
        assert args.fetch is False, "fetching must be opt-in"

    def test_fetch_defaults_to_off(self) -> None:
        """The single most important default here."""
        args = build_parser().parse_args(["circulars", "--sweep"])
        assert args.fetch is False

    def test_no_mode_selected_fails_with_guidance(self, capsys) -> None:  # type: ignore[no-untyped-def]
        assert main(["circulars"]) == EXIT_FAILURE
        out = capsys.readouterr().out
        assert "--from-listings" in out
        assert "--sweep" in out
        assert "--parse" in out

    def test_missing_listings_explains_why_and_how(self, capsys) -> None:  # type: ignore[no-untyped-def]
        assert main(["circulars", "--from-listings"]) == EXIT_FAILURE
        out = capsys.readouterr().out
        assert "Save Page As" in out
        assert "runs in the browser" in out, "the reason must be stated, not just the remedy"

    def test_sweep_dry_run_downloads_nothing_and_succeeds(self, capsys) -> None:  # type: ignore[no-untyped-def]
        assert main(["circulars", "--sweep", "--limit", "3"]) == EXIT_OK
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "nothing downloaded" in out
        assert "ind_prs" in out

    def test_sweep_reports_the_time_cost_before_committing_to_it(self, capsys) -> None:  # type: ignore[no-untyped-def]
        main(["circulars", "--sweep"])
        out = capsys.readouterr().out
        assert "base candidates" in out
        assert "min)" in out, "the user should see the time cost before running it"

    def test_parse_with_nothing_downloaded_fails_cleanly(self, capsys) -> None:  # type: ignore[no-untyped-def]
        assert main(["circulars", "--parse"]) == EXIT_FAILURE
        assert "No release PDFs" in capsys.readouterr().out
