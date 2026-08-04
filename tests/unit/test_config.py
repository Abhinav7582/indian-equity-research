"""Configuration loading, validation and secret hygiene."""

from __future__ import annotations

import json

import pytest

from indian_equity_research.config import Settings, get_settings, reset_settings_cache
from indian_equity_research.constants import PROJECT_ROOT
from indian_equity_research.domain.enums import Environment, LogLevel, SslMode
from indian_equity_research.exceptions import ConfigurationError
from tests.conftest import SettingsFactory

SECRET = "sup3r-s3cret-value"


class TestValidLoading:
    def test_defaults_load_without_error(self, make_settings: SettingsFactory) -> None:
        settings = make_settings()
        assert settings.app_name == "indian-equity-research"
        assert isinstance(settings.log_level, LogLevel)

    def test_app_env_comes_from_environment(
        self, monkeypatch: pytest.MonkeyPatch, make_settings: SettingsFactory
    ) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        assert make_settings().app_env is Environment.DEVELOPMENT

    def test_environment_variable_overrides_yaml(
        self, monkeypatch: pytest.MonkeyPatch, make_settings: SettingsFactory
    ) -> None:
        # configs/test.yaml sets log_level: WARNING; the environment must win.
        monkeypatch.setenv("LOG_LEVEL", "ERROR")
        assert make_settings().log_level is LogLevel.ERROR

    def test_yaml_layer_is_actually_applied(self, make_settings: SettingsFactory) -> None:
        # configs/test.yaml sets database_pool_size: 1, overriding the base value of 5.
        assert make_settings().database_pool_size == 1

    def test_relative_data_paths_resolve_against_project_root(
        self, make_settings: SettingsFactory
    ) -> None:
        settings = make_settings()
        assert settings.raw_dir.is_absolute()
        assert settings.raw_dir == (PROJECT_ROOT / "data" / "raw").resolve()

    def test_data_directories_exist_in_the_repository(self, make_settings: SettingsFactory) -> None:
        assert make_settings().missing_data_directories() == ()

    def test_get_settings_is_cached(self) -> None:
        reset_settings_cache()
        first = get_settings()
        assert get_settings() is first
        reset_settings_cache()
        assert get_settings() is not first


class TestInvalidConfiguration:
    def test_unknown_log_level_is_rejected(self, make_settings: SettingsFactory) -> None:
        with pytest.raises(ConfigurationError, match="log_level"):
            make_settings(log_level="CHATTY")

    def test_port_out_of_range_is_rejected(self, make_settings: SettingsFactory) -> None:
        with pytest.raises(ConfigurationError, match="database_port"):
            make_settings(database_port=70_000)

    def test_error_message_names_every_offending_field(
        self, make_settings: SettingsFactory
    ) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            make_settings(database_port=0, log_level="NOISY")
        message = str(exc_info.value)
        assert "database_port" in message
        assert "log_level" in message


class TestProductionSafety:
    def test_production_requires_a_password(self, make_settings: SettingsFactory) -> None:
        with pytest.raises(ConfigurationError, match="DATABASE_PASSWORD must be set"):
            make_settings(app_env="production", database_password=None)

    def test_production_rejects_a_blank_password(self, make_settings: SettingsFactory) -> None:
        with pytest.raises(ConfigurationError, match="DATABASE_PASSWORD must be set"):
            make_settings(app_env="production", database_password="   ")

    def test_production_rejects_the_example_placeholder(
        self, make_settings: SettingsFactory
    ) -> None:
        with pytest.raises(ConfigurationError, match="placeholder"):
            make_settings(app_env="production", database_password="replace_me")

    def test_production_accepts_a_real_password(self, make_settings: SettingsFactory) -> None:
        settings = make_settings(app_env="production", database_password=SECRET)
        assert settings.app_env.is_production

    def test_development_does_not_require_a_password(self, make_settings: SettingsFactory) -> None:
        settings = make_settings(app_env="development", database_password=None)
        assert settings.database_password is None


class TestSecretHygiene:
    """The secret must not appear in any representation of the settings."""

    @pytest.fixture
    def settings(self, make_settings: SettingsFactory) -> Settings:
        return make_settings(database_password=SECRET)

    def test_secret_absent_from_repr(self, settings: Settings) -> None:
        assert SECRET not in repr(settings)

    def test_secret_absent_from_str(self, settings: Settings) -> None:
        assert SECRET not in str(settings)

    def test_secret_absent_from_model_dump_json(self, settings: Settings) -> None:
        assert SECRET not in settings.model_dump_json()

    def test_secret_absent_from_stringified_model_dump(self, settings: Settings) -> None:
        assert SECRET not in str(settings.model_dump())

    def test_secret_absent_from_safe_url(self, settings: Settings) -> None:
        assert SECRET not in settings.database_url_safe

    def test_secret_absent_from_json_serialisable_dump(self, settings: Settings) -> None:
        payload = json.loads(settings.model_dump_json())
        assert SECRET not in json.dumps(payload)

    def test_secret_is_still_retrievable_deliberately(self, settings: Settings) -> None:
        # Explicit retrieval must work; accidental disclosure must not.
        assert settings.database_password is not None
        assert settings.database_password.get_secret_value() == SECRET


class TestDatabaseUrl:
    def test_url_components(self, make_settings: SettingsFactory) -> None:
        settings = make_settings(
            database_host="db.internal",
            database_port=6543,
            database_name="research",
            database_user="analyst",
            database_password=SECRET,
            database_ssl_mode="require",
        )
        url = settings.database_url
        assert url.drivername == "postgresql+psycopg"
        assert url.username == "analyst"
        assert url.host == "db.internal"
        assert url.port == 6543
        assert url.database == "research"
        assert url.query["sslmode"] == SslMode.REQUIRE.value
        assert url.password == SECRET

    def test_password_with_special_characters_is_escaped(
        self, make_settings: SettingsFactory
    ) -> None:
        awkward = "p@ss:w/ord?#&"
        settings = make_settings(database_password=awkward)
        # The password survives a round trip through the URL object intact,
        # which string formatting would not guarantee.
        assert settings.database_url.password == awkward
        assert awkward not in settings.database_url_safe

    def test_safe_url_masks_the_password_but_keeps_the_target(
        self, make_settings: SettingsFactory
    ) -> None:
        settings = make_settings(database_host="db.internal", database_password=SECRET)
        safe = settings.database_url_safe
        assert SECRET not in safe
        assert "db.internal" in safe
        assert "***" in safe

    def test_url_without_a_password(self, make_settings: SettingsFactory) -> None:
        settings = make_settings(database_password=None)
        assert settings.database_url.password is None
