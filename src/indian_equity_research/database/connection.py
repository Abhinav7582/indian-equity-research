"""Engine and session construction.

Engines are created explicitly and owned by the caller. There is no module
level engine singleton: a hidden global connection pool is difficult to close
deterministically and makes tests order-dependent.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from indian_equity_research.config import Settings
from indian_equity_research.exceptions import DatabaseConnectionError
from indian_equity_research.logging_config import get_logger, redact_secrets

__all__ = [
    "create_database_engine",
    "create_session_factory",
    "dispose_engine",
    "session_scope",
]

logger = get_logger(__name__)


def create_database_engine(settings: Settings, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine from validated settings.

    ``pool_pre_ping`` is enabled so that a connection dropped by the server
    (or by a container restart) is detected and replaced rather than surfacing
    as a confusing error at query time.

    Args:
        settings: Validated application settings.
        echo: Whether SQLAlchemy should log every statement. Off by default.

    Returns:
        A configured engine. No connection is opened until first use.

    Raises:
        DatabaseConnectionError: If the URL or pool arguments are invalid. The
            message never contains the password.
    """
    url = settings.database_url
    try:
        engine = create_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            pool_timeout=settings.database_pool_timeout_seconds,
            connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
        )
    except (ArgumentError, SQLAlchemyError) as exc:
        message = f"Could not configure the database engine: {redact_secrets(str(exc))}"
        raise DatabaseConnectionError(message) from exc

    logger.debug("Database engine created for %s", settings.database_url_safe)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine.

    Args:
        engine: The engine sessions should use.

    Returns:
        A ``sessionmaker`` producing sessions with autoflush disabled, so that
        writes happen only where the code says they do.
    """
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on any exception, and always closes the
    session.

    Args:
        factory: The session factory to draw a session from.

    Yields:
        An open session.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine(engine: Engine) -> None:
    """Close every pooled connection held by the engine.

    Args:
        engine: The engine to dispose. Safe to call more than once.
    """
    engine.dispose()
    logger.debug("Database engine disposed.")
