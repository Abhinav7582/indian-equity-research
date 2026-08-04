"""Database health check against a real PostgreSQL instance.

These tests are skipped automatically when PostgreSQL is not reachable, so
``pytest`` still succeeds on a machine without Docker. Start the service with::

    make db-up

Run them explicitly with::

    make test-integration
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from indian_equity_research.config import Settings
from indian_equity_research.database.connection import (
    create_database_engine,
    create_session_factory,
    dispose_engine,
    session_scope,
)
from indian_equity_research.database.health import check_database_health

pytestmark = pytest.mark.integration


class TestHealthCheckSuccessPath:
    def test_reports_healthy(self, postgres_settings: Settings) -> None:
        health = check_database_health(postgres_settings)
        assert health.is_healthy is True
        assert health.error is None

    def test_reports_the_server_version(self, postgres_settings: Settings) -> None:
        health = check_database_health(postgres_settings)
        assert health.server_version
        assert health.server_version[0].isdigit()

    def test_reports_a_plausible_latency(self, postgres_settings: Settings) -> None:
        health = check_database_health(postgres_settings)
        assert health.latency_ms is not None
        assert 0 <= health.latency_ms < 10_000

    def test_description_starts_with_ok(self, postgres_settings: Settings) -> None:
        assert check_database_health(postgres_settings).describe().startswith("OK")

    def test_reuses_a_supplied_engine(self, postgres_settings: Settings) -> None:
        engine = create_database_engine(postgres_settings)
        try:
            assert check_database_health(postgres_settings, engine=engine).is_healthy
            # The caller-owned engine must survive the check.
            with engine.connect() as connection:
                assert connection.execute(text("SELECT 1")).scalar_one() == 1
        finally:
            dispose_engine(engine)


class TestSessionScope:
    def test_yields_a_usable_session(self, postgres_settings: Settings) -> None:
        engine = create_database_engine(postgres_settings)
        try:
            factory = create_session_factory(engine)
            with session_scope(factory) as session:
                assert session.execute(text("SELECT 42")).scalar_one() == 42
        finally:
            dispose_engine(engine)

    def test_rolls_back_and_re_raises_on_error(self, postgres_settings: Settings) -> None:
        engine = create_database_engine(postgres_settings)
        try:
            factory = create_session_factory(engine)
            with pytest.raises(Exception, match="syntax error"), session_scope(factory) as session:
                session.execute(text("SELECT FROM WHERE"))
        finally:
            dispose_engine(engine)


class TestSchemaState:
    def test_no_application_tables_exist_yet(self, postgres_settings: Settings) -> None:
        """Phase 1 creates no tables. A populated schema means scope creep."""
        engine = create_database_engine(postgres_settings)
        try:
            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ).fetchall()
            assert rows == []
        finally:
            dispose_engine(engine)
