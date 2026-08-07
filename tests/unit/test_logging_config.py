"""Structured logging and credential redaction."""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest

from indian_equity_research.domain.enums import LogLevel
from indian_equity_research.logging_config import (
    configure_logging,
    get_logger,
    redact_secrets,
)

SECRET = "hunter2-very-secret"


class TestRedactSecrets:
    def test_redacts_a_url_password(self) -> None:
        result = redact_secrets(f"postgresql+psycopg://analyst:{SECRET}@db.internal:5432/research")
        assert SECRET not in result
        assert "analyst" in result
        assert "db.internal" in result

    @pytest.mark.parametrize(
        "template",
        [
            "password={secret}",
            "PASSWORD: {secret}",
            "api_key={secret}",
            "access-token: {secret}",
            "secret={secret}",
        ],
    )
    def test_redacts_keyed_secrets(self, template: str) -> None:
        assert SECRET not in redact_secrets(template.format(secret=SECRET))

    def test_leaves_ordinary_text_untouched(self) -> None:
        message = "Loaded 250 rows for NSE bhavcopy 2024-04-01"
        assert redact_secrets(message) == message

    def test_is_idempotent(self) -> None:
        once = redact_secrets(f"password={SECRET}")
        assert redact_secrets(once) == once


class TestConfigureLogging:
    @pytest.fixture(autouse=True)
    def _restore_root_logger(self) -> Iterator[None]:
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        original_level = root.level
        yield
        root.handlers = original_handlers
        root.setLevel(original_level)

    def test_emits_timestamp_level_name_and_message(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("ingest finished")
        line = stream.getvalue().strip()
        parts = [part.strip() for part in line.split("|")]
        assert len(parts) == 4
        assert parts[0].startswith("20")  # ISO-8601 timestamp
        assert parts[1] == "INFO"
        assert parts[2] == "indian_equity_research.test"
        assert parts[3] == "ingest finished"

    def test_is_idempotent_and_does_not_duplicate_lines(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        configure_logging(LogLevel.INFO, stream=stream)
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("only once")
        assert stream.getvalue().count("only once") == 1

    def test_respects_the_configured_level(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.WARNING, stream=stream)
        logger = get_logger("indian_equity_research.test")
        logger.debug("suppressed")
        logger.warning("emitted")
        output = stream.getvalue()
        assert "suppressed" not in output
        assert "emitted" in output

    def test_accepts_a_plain_string_level(self) -> None:
        stream = io.StringIO()
        configure_logging("debug", stream=stream)
        get_logger("indian_equity_research.test").debug("visible")
        assert "visible" in stream.getvalue()

    def test_redacts_a_secret_that_reaches_a_log_call(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info(
            "connecting to postgresql://analyst:%s@db:5432/research", SECRET
        )
        assert SECRET not in stream.getvalue()

    def test_redacts_secrets_passed_as_arguments(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("detail: %s", f"password={SECRET}")
        assert SECRET not in stream.getvalue()


class TestFormatSpecifiers:
    """Regression: the redaction filter must not break numeric formatting.

    The original filter coerced every argument with ``str()``, so a `%d`
    given an int received `'42'` and raised TypeError inside the handler.
    Python's logging swallows that into a stderr traceback, so the program
    keeps running while the log line is lost - a failure mode that is easy to
    miss and unpleasant to debug. Found in Phase 2a, fixed here.
    """

    @pytest.fixture(autouse=True)
    def _restore_root_logger(self) -> Iterator[None]:
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        original_level = root.level
        yield
        root.handlers = original_handlers
        root.setLevel(original_level)

    def test_integer_format_specifier(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("Archived %s (%d bytes)", "asm", 169183)
        assert "Archived asm (169183 bytes)" in stream.getvalue()

    def test_float_format_specifier(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("latency %.2f ms", 12.3456)
        assert "latency 12.35 ms" in stream.getvalue()

    def test_mixed_types_with_a_secret_present(self) -> None:
        """Strings still get redacted; numbers pass through untouched."""
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info(
            "%s wrote %d bytes", f"password={SECRET}", 42
        )
        output = stream.getvalue()
        assert SECRET not in output
        assert "wrote 42 bytes" in output

    def test_dict_style_args_preserve_numbers(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info(
            "%(name)s took %(ms)d ms", {"name": "ingest", "ms": 250}
        )
        assert "ingest took 250 ms" in stream.getvalue()

    def test_no_handler_errors_are_raised(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A broken filter shows up as a stderr traceback, not an exception."""
        logging.raiseExceptions = True
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("n=%d pct=%.1f%%", 5, 99.5)
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err
        assert "n=5 pct=99.5%" in stream.getvalue()


class TestNonStringArguments:
    """Regression: the filter once coerced every argument with ``str()``.

    That silently broke numeric format specifiers. It surfaced in Phase 2a as
    ``TypeError: %d format: a real number is required, not str`` on a log call
    the archiver made *after* successfully saving a file - so the data was
    fine and only the log record blew up, which is the kind of defect that
    survives a long time unnoticed.
    """

    @pytest.fixture(autouse=True)
    def _restore_root_logger(self) -> Iterator[None]:
        root = logging.getLogger()
        handlers, level = list(root.handlers), root.level
        yield
        root.handlers, root.level = handlers, level

    def test_integer_format_specifier_survives(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("Archived %s (%d bytes)", "master", 169183)
        assert "Archived master (169183 bytes)" in stream.getvalue()

    def test_float_format_specifier_survives(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("took %.2f ms", 12.3456)
        assert "took 12.35 ms" in stream.getvalue()

    def test_dict_style_arguments_keep_their_types(self) -> None:
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("%(n)d rows", {"n": 42})
        assert "42 rows" in stream.getvalue()

    def test_string_arguments_are_still_redacted(self) -> None:
        """The fix must not weaken the guarantee it was protecting."""
        stream = io.StringIO()
        configure_logging(LogLevel.INFO, stream=stream)
        get_logger("indian_equity_research.test").info("%s at %d", f"password={SECRET}", 5432)
        output = stream.getvalue()
        assert SECRET not in output
        assert "5432" in output
