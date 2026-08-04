"""Shared pytest fixtures.

Two rules govern every test in this suite:

1. **No network access.** Nothing here contacts an exchange, a broker or any
   external service. The only socket a test may open is to a local
   PostgreSQL instance, and only in the integration suite.
2. **No dependence on a developer's ``.env``.** Settings are always built with
   ``_env_file=None`` and an explicitly controlled environment, so results do
   not change between machines.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from indian_equity_research.config import Settings, load_settings, reset_settings_cache
from indian_equity_research.database.health import check_database_health

#: Environment variables that must not leak from the developer's shell into a test.
_MANAGED_ENV_VARS = (
    "APP_ENV",
    "LOG_LEVEL",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_SSL_MODE",
)


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove managed variables and clear the settings cache around each test."""
    for name in _MANAGED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    reset_settings_cache()
    yield
    reset_settings_cache()


SettingsFactory = Callable[..., Settings]


@pytest.fixture
def make_settings() -> SettingsFactory:
    """Return a factory building :class:`Settings` without reading ``.env``."""

    def _factory(**overrides: Any) -> Settings:
        overrides.setdefault("_env_file", None)
        return load_settings(**overrides)

    return _factory


@pytest.fixture
def postgres_settings(make_settings: SettingsFactory) -> Settings:
    """Settings pointing at a local PostgreSQL, skipping if it is unreachable.

    Connection details come from the ambient environment when present so the
    same test runs against the ``docker compose`` service and against CI.
    """
    settings = make_settings(
        database_host=os.environ.get("TEST_DATABASE_HOST", "localhost"),
        database_port=int(os.environ.get("TEST_DATABASE_PORT", "5432")),
        database_name=os.environ.get("TEST_DATABASE_NAME", "equity_research"),
        database_user=os.environ.get("TEST_DATABASE_USER", "equity_user"),
        database_password=os.environ.get("TEST_DATABASE_PASSWORD", "equity_password"),
        database_ssl_mode="disable",
        database_connect_timeout_seconds=2,
    )
    health = check_database_health(settings)
    if not health.is_healthy:
        pytest.skip(f"PostgreSQL unavailable at {health.target}: {health.error}")
    return settings


@pytest.fixture
def unreachable_settings(make_settings: SettingsFactory) -> Settings:
    """Settings pointing at a closed local port, for failure-path tests.

    Port 1 on the loopback interface refuses connections immediately, so the
    failure path is exercised without a timeout and without leaving the host.
    """
    return make_settings(
        database_host="127.0.0.1",
        database_port=1,
        database_name="does_not_exist",
        database_user="nobody",
        database_password="unused",
        database_ssl_mode="disable",
        database_connect_timeout_seconds=1,
    )
