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
