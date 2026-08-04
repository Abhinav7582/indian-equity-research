"""Exception hierarchy for the Indian Equity Research System.

A single base class lets callers catch everything this project raises without
resorting to a bare ``except Exception``, which is banned by the project's
coding standards.

None of these exceptions may carry credentials in their message. Where an
underlying library error might contain a connection string, redact it with
:func:`indian_equity_research.logging_config.redact_secrets` before wrapping.
"""

from __future__ import annotations

__all__ = [
    "ConfigurationError",
    "DatabaseConnectionError",
    "IndianEquityResearchError",
]


class IndianEquityResearchError(Exception):
    """Base class for every error raised by this project."""


class ConfigurationError(IndianEquityResearchError):
    """Configuration is missing, malformed or unsafe for the target environment."""


class DatabaseConnectionError(IndianEquityResearchError):
    """The research database could not be reached or could not be configured."""
