"""Foundational enumerations.

These describe the *shape* of the system (environments, storage layers,
connection modes), not financial data. Instrument- and market-level
vocabulary arrives with the data-ingestion phase.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["DataLayer", "Environment", "Exchange", "LogLevel", "SslMode"]


class Environment(StrEnum):
    """Deployment environment the application is running in."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        """Whether this environment must enforce production safety rules."""
        return self is Environment.PRODUCTION


class LogLevel(StrEnum):
    """Supported logging verbosity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DataLayer(StrEnum):
    """Layers of the data lake.

    ``RAW`` is immutable: bytes are written exactly as received from the
    source and never edited in place. Every later layer is a reproducible
    function of ``RAW`` plus versioned transformation code.
    """

    RAW = "raw"
    INTERIM = "interim"
    PROCESSED = "processed"
    REFERENCE = "reference"


class Exchange(StrEnum):
    """Indian cash-equity exchanges this project will eventually read from.

    Declared here so identifiers are consistent from the first commit. No
    exchange connectivity exists in this phase.
    """

    NSE = "NSE"
    BSE = "BSE"


class SslMode(StrEnum):
    """PostgreSQL ``sslmode`` values (libpq semantics)."""

    DISABLE = "disable"
    ALLOW = "allow"
    PREFER = "prefer"
    REQUIRE = "require"
    VERIFY_CA = "verify-ca"
    VERIFY_FULL = "verify-full"
