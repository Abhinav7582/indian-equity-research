"""Database health check.

Used by ``python -m indian_equity_research db-health`` and by the integration
test suite. The check is read-only: it opens a connection, runs ``SELECT 1``
and reads the server version. It creates nothing and writes nothing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from indian_equity_research.config import Settings
from indian_equity_research.database.connection import create_database_engine, dispose_engine
from indian_equity_research.logging_config import get_logger, redact_secrets

__all__ = ["DatabaseHealth", "check_database_health"]

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    """Outcome of a database health check.

    Attributes:
        is_healthy: Whether the database answered a trivial query.
        target: Connection target with the password masked, safe to display.
        latency_ms: Round-trip time in milliseconds, when the check succeeded.
        server_version: PostgreSQL version string, when the check succeeded.
        error: Redacted failure reason, when the check failed.
    """

    is_healthy: bool
    target: str
    latency_ms: float | None = None
    server_version: str | None = None
    error: str | None = None

    def describe(self) -> str:
        """Return a single human-readable line summarising the result."""
        if self.is_healthy:
            latency = f"{self.latency_ms:.1f} ms" if self.latency_ms is not None else "unknown"
            return f"OK  {self.target}  (server={self.server_version}, latency={latency})"
        return f"FAIL  {self.target}  ({self.error})"


def check_database_health(
    settings: Settings,
    *,
    engine: Engine | None = None,
) -> DatabaseHealth:
    """Check that PostgreSQL is reachable and answering queries.

    This function does not raise on connection failure: an unreachable
    database is an expected condition that callers report rather than crash
    on. Programming errors still propagate.

    Args:
        settings: Validated application settings.
        engine: An existing engine to reuse. When omitted, a temporary engine
            is created and disposed before returning.

    Returns:
        A :class:`DatabaseHealth` describing the outcome. Any error message is
        passed through credential redaction before being stored.
    """
    target = settings.database_url_safe
    owns_engine = engine is None
    active_engine = engine if engine is not None else create_database_engine(settings)

    try:
        started = time.perf_counter()
        with active_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            version = connection.execute(text("SHOW server_version")).scalar_one()
        latency_ms = (time.perf_counter() - started) * 1000
    except SQLAlchemyError as exc:
        reason = redact_secrets(str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc))
        logger.warning("Database health check failed for %s: %s", target, reason)
        return DatabaseHealth(is_healthy=False, target=target, error=reason)
    finally:
        if owns_engine:
            dispose_engine(active_engine)

    logger.info("Database health check succeeded for %s", target)
    return DatabaseHealth(
        is_healthy=True,
        target=target,
        latency_ms=latency_ms,
        server_version=str(version),
    )
