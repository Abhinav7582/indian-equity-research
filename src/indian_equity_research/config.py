"""Typed application settings.

Configuration is layered, lowest precedence first:

1. ``configs/base.yaml``           - non-sensitive defaults for all environments
2. ``configs/<APP_ENV>.yaml``      - non-sensitive per-environment overrides
3. ``.env``                        - local developer values (git-ignored)
4. Process environment variables   - highest precedence

Secrets live only in layers 3 and 4. YAML files must never contain a
credential; this is enforced by convention and documented in
``docs/data_principles.md``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from sqlalchemy import URL

from indian_equity_research.constants import CONFIG_DIR, PROJECT_ROOT
from indian_equity_research.domain.enums import Environment, LogLevel, SslMode
from indian_equity_research.exceptions import ConfigurationError

__all__ = [
    "Settings",
    "YamlSettingsSource",
    "get_settings",
    "load_settings",
    "reset_settings_cache",
]

#: Placeholder shipped in ``.env.example``. Never valid in production.
_PLACEHOLDER_PASSWORD = "replace_me"


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Settings source that merges ``base.yaml`` with an environment overlay.

    ``APP_ENV`` is read directly from the process environment because the
    overlay filename depends on it, and the settings object does not exist yet
    when sources are constructed.
    """

    def __init__(self, settings_cls: type[BaseSettings], config_dir: Path) -> None:
        """Load and merge the YAML layers.

        Args:
            settings_cls: The settings class being populated.
            config_dir: Directory holding the YAML configuration files.
        """
        super().__init__(settings_cls)
        self._config_dir = config_dir
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        env_name = os.environ.get("APP_ENV", Environment.DEVELOPMENT.value).strip().lower()
        merged: dict[str, Any] = {}
        for filename in ("base.yaml", f"{env_name}.yaml"):
            path = self._config_dir / filename
            if not path.is_file():
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                message = f"Configuration file '{filename}' is not valid YAML: {exc}"
                raise ConfigurationError(message) from exc
            except OSError as exc:
                message = f"Configuration file '{filename}' could not be read: {exc}"
                raise ConfigurationError(message) from exc
            if raw is None:
                continue
            if not isinstance(raw, dict):
                message = f"Configuration file '{filename}' must contain a top-level mapping."
                raise ConfigurationError(message)
            merged.update(raw)
        return merged

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:  # noqa: ARG002
        """Return the YAML value for a single field.

        Args:
            field: Pydantic field metadata (unused; lookup is by name).
            field_name: Name of the field being resolved.

        Returns:
            A ``(value, key, is_complex)`` triple as required by
            ``pydantic-settings``.
        """
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        """Return every value supplied by the YAML layers."""
        return dict(self._data)


class Settings(BaseSettings):
    """Application settings, validated at construction time."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # ----------------------------- application -----------------------------
    app_env: Environment = Environment.DEVELOPMENT
    app_name: str = "indian-equity-research"
    log_level: LogLevel = LogLevel.INFO

    # ------------------------------- storage -------------------------------
    data_root: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    interim_dir: Path = Path("data/interim")
    processed_dir: Path = Path("data/processed")
    reference_dir: Path = Path("data/reference")

    # ------------------------------ database -------------------------------
    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "equity_research"
    database_user: str = "equity_user"
    database_password: SecretStr | None = None
    database_ssl_mode: SslMode = SslMode.PREFER
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=300)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=120)

    @field_validator(
        "data_root", "raw_dir", "interim_dir", "processed_dir", "reference_dir", mode="after"
    )
    @classmethod
    def _resolve_against_project_root(cls, value: Path) -> Path:
        """Resolve relative data paths against the project root, not the CWD."""
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @model_validator(mode="after")
    def _reject_unsafe_production_config(self) -> Settings:
        """Refuse to run in production without a real database password."""
        if not self.app_env.is_production:
            return self
        secret = self.database_password.get_secret_value() if self.database_password else ""
        if not secret.strip():
            message = (
                "DATABASE_PASSWORD must be set when APP_ENV=production. "
                "No production default is provided by design."
            )
            raise ValueError(message)
        if secret == _PLACEHOLDER_PASSWORD:
            message = (
                "DATABASE_PASSWORD is still the placeholder from .env.example. "
                "Set a real value before running in production."
            )
            raise ValueError(message)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order the configuration sources, highest precedence first."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlSettingsSource(settings_cls, CONFIG_DIR),
            file_secret_settings,
        )

    # ------------------------------ derived --------------------------------
    @property
    def database_url(self) -> URL:
        """Build the SQLAlchemy PostgreSQL URL.

        ``URL.create`` is used rather than string formatting so that special
        characters in the password are escaped correctly, and so that the
        password is masked when the URL is rendered.

        Returns:
            A SQLAlchemy :class:`~sqlalchemy.URL` for the ``psycopg`` driver.
        """
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value() if self.database_password else None,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"sslmode": self.database_ssl_mode.value},
        )

    @property
    def database_url_safe(self) -> str:
        """Return the database URL with the password masked, safe to log."""
        return self.database_url.render_as_string(hide_password=True)

    @property
    def data_directories(self) -> tuple[Path, ...]:
        """Return every directory the data lake expects to exist."""
        return (
            self.data_root,
            self.raw_dir,
            self.interim_dir,
            self.processed_dir,
            self.reference_dir,
        )

    def missing_data_directories(self) -> tuple[Path, ...]:
        """Return the configured data directories that do not yet exist."""
        return tuple(path for path in self.data_directories if not path.is_dir())


def load_settings(**overrides: Any) -> Settings:
    """Construct :class:`Settings`, converting validation errors into our own.

    Args:
        **overrides: Values passed straight to the settings constructor,
            taking precedence over every other source. Used by tests.

    Returns:
        A validated settings object.

    Raises:
        ConfigurationError: If any value is missing or invalid. The message
            lists the offending fields and never includes secret values.
    """
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        message = f"Invalid configuration ({exc.error_count()} problem(s)) -> {problems}"
        raise ConfigurationError(message) from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Cached so that configuration is parsed and validated once. Tests that
    change the environment must call :func:`reset_settings_cache` afterwards.

    Returns:
        The validated settings object.

    Raises:
        ConfigurationError: If configuration is missing or invalid.
    """
    return load_settings()


def reset_settings_cache() -> None:
    """Clear the cached settings so the next call re-reads the environment."""
    get_settings.cache_clear()
