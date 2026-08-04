"""Database plumbing.

Phase 1 provides the declarative base, engine/session construction and a
health check. It defines **no tables**: instruments, prices, corporate
actions and universes are designed in the data-modelling phase, once the
point-in-time requirements are fixed.
"""

from indian_equity_research.database.base import Base, metadata
from indian_equity_research.database.connection import (
    create_database_engine,
    create_session_factory,
    dispose_engine,
    session_scope,
)
from indian_equity_research.database.health import DatabaseHealth, check_database_health

__all__ = [
    "Base",
    "DatabaseHealth",
    "check_database_health",
    "create_database_engine",
    "create_session_factory",
    "dispose_engine",
    "metadata",
    "session_scope",
]
