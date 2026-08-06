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

        The set has grown twice: `h4-regime` in Phase 1.5 (reads local CSVs,
        opens no socket) and `archive` in Phase 2a (fetches published exchange
        files, one request per source per day, and writes only into the
        git-ignored data directory).

        Neither can place an order. The invariant this guards is **no broker
        connectivity and no order placement**, not "never add a command" -
        which is why `test_no_broker_dependency_anywhere` below is the real
        boundary and this assertion is the tripwire that forces a reviewer to
        look.
        """
        assert set(COMMANDS) == {
            "version",
            "config-check",
            "db-health",
            "h4-regime",
            "archive",
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
