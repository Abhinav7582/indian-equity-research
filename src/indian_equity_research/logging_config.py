"""Structured logging configuration.

Log records carry a timestamp, level, logger name and message. A redaction
filter is installed on the project's handler so that a credential which
reaches a log call by accident is masked before it is written.

The filter is a safety net, not a licence to log secrets. Never pass a
password, token or full database URL to a log call.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Final, TextIO

from indian_equity_research.domain.enums import LogLevel

__all__ = [
    "LOG_DATE_FORMAT",
    "LOG_FORMAT",
    "configure_logging",
    "get_logger",
    "redact_secrets",
]

LOG_FORMAT: Final = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: Final = "%Y-%m-%dT%H:%M:%S%z"

_HANDLER_NAME: Final = "indian-equity-research-console"
_REDACTED: Final = "***REDACTED***"

# Matches the password segment of a URL such as
# postgresql+psycopg://user:s3cr3t@host:5432/db  ->  postgresql+psycopg://user:***@host...
_URL_CREDENTIAL_RE: Final = re.compile(r"(?P<prefix>://[^:/?#\s]+:)(?P<secret>[^@\s]+)(?P<at>@)")

# Matches key=value / key: value pairs whose key names a secret.
_KEYED_SECRET_RE: Final = re.compile(
    r"(?P<key>(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?token)"
    r"\s*[=:]\s*)(?P<secret>[^\s,;'\"}\])]+)",
    re.IGNORECASE,
)


def redact_secrets(message: str) -> str:
    """Mask credentials embedded in a string.

    Handles the two shapes that leak in practice: the password segment of a
    connection URL, and ``key=value`` pairs whose key names a secret.

    Args:
        message: Text that may contain a credential.

    Returns:
        The text with any detected credential replaced by a fixed marker.

    Examples:
        >>> redact_secrets("postgresql://alice:hunter2@db:5432/x")
        'postgresql://alice:***REDACTED***@db:5432/x'
        >>> redact_secrets("password=hunter2")
        'password=***REDACTED***'
    """
    redacted = _URL_CREDENTIAL_RE.sub(rf"\g<prefix>{_REDACTED}\g<at>", message)
    return _KEYED_SECRET_RE.sub(rf"\g<key>{_REDACTED}", redacted)


class SecretRedactingFilter(logging.Filter):
    """Logging filter that redacts credentials from the formatted message."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record in place and always allow it through.

        Args:
            record: The record about to be emitted.

        Returns:
            Always ``True``; this filter censors rather than drops.
        """
        record.msg = redact_secrets(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_secrets(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(redact_secrets(str(a)) for a in record.args)
        return True


def configure_logging(
    level: LogLevel | str = LogLevel.INFO,
    *,
    stream: TextIO | None = None,
) -> None:
    """Install the project's console handler on the root logger.

    Calling this repeatedly is safe: the previously installed handler is
    replaced rather than duplicated, so log lines are never emitted twice.

    Args:
        level: Minimum level to emit.
        stream: Destination stream. Defaults to ``sys.stderr`` so that machine
            readable CLI output on stdout stays clean.
    """
    resolved_level = LogLevel(str(level).upper())
    root = logging.getLogger()

    for existing in [h for h in root.handlers if h.name == _HANDLER_NAME]:
        root.removeHandler(existing)
        existing.close()

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.name = _HANDLER_NAME
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    handler.addFilter(SecretRedactingFilter())

    root.addHandler(handler)
    root.setLevel(resolved_level.value)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A standard library logger.
    """
    return logging.getLogger(name)
