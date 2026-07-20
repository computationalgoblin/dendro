"""Tests for domain configuration module."""

import dataclasses
from pathlib import Path

from packages.domain.config import (
    AppConfig,
    LoggingConfig,
    get_settings,
    load_settings,
    reset_settings,
)


class TestLoggingConfig:
    """Test LoggingConfig defaults and overrides."""

    def test_default_level(self):
        config = LoggingConfig()
        assert config.level == "INFO"

    def test_default_structured(self):
        config = LoggingConfig()
        assert config.structured is True

    def test_default_output_file_none(self):
        config = LoggingConfig()
        assert config.output_file is None

    def test_custom_level(self):
        config = LoggingConfig(level="DEBUG")
        assert config.level == "DEBUG"

    def test_custom_output_file(self):
        config = LoggingConfig(output_file="/tmp/test.log")
        assert config.output_file == "/tmp/test.log"


class TestAppConfig:
    """Test AppConfig defaults and construction."""

    def test_default_app_name(self):
        config = AppConfig()
        assert config.app_name == "narrative-architect"

    def test_default_version(self):
        config = AppConfig()
        assert config.app_version == "0.9.0b1"

    def test_default_debug(self):
        config = AppConfig()
        assert config.debug is False

    def test_default_logging_config(self):
        config = AppConfig()
        assert isinstance(config.logging, LoggingConfig)
        assert config.logging.level == "INFO"

    def test_default_data_dir(self):
        config = AppConfig()
        expected = str(Path.home() / ".narrative-architect")
        assert config.data_dir == expected


class TestLoadSettings:
    """Test load_settings function."""

    def test_default_settings(self):
        config = load_settings()
        assert isinstance(config, AppConfig)
        assert config.app_name == "narrative-architect"
        assert config.debug is False

    def test_override_debug(self):
        config = load_settings({"debug": True})
        assert config.debug is True

    def test_override_app_name(self):
        config = load_settings({"app_name": "test-app"})
        assert config.app_name == "test-app"

    def test_override_logging_level(self):
        config = load_settings({"logging": {"level": "DEBUG"}})
        assert config.logging.level == "DEBUG"

    def test_override_logging_format(self):
        custom_format = "%(message)s"
        config = load_settings({"logging": {"format": custom_format}})
        assert config.logging.format == custom_format

    def test_override_multiple_fields(self):
        config = load_settings({
            "debug": True,
            "app_name": "test",
            "logging": {"level": "DEBUG", "output_file": "/tmp/test.log"},
        })
        assert config.debug is True
        assert config.app_name == "test"
        assert config.logging.level == "DEBUG"
        assert config.logging.output_file == "/tmp/test.log"

    def test_reset_settings(self):
        reset_settings()
        config = get_settings()
        assert isinstance(config, AppConfig)
        assert config.debug is False


class TestAppConfigImmutability:
    """Test that AppConfig is frozen/immutable."""

    def test_cannot_modify_app_name(self):
        config = AppConfig()
        try:
            config.app_name = "new-name"
            assert False, "Should have raised FrozenInstanceError"
        except (dataclasses.FrozenInstanceError, AttributeError):
            pass

    def test_cannot_modify_logging_level_directly(self):
        config = AppConfig()
        try:
            config.logging.level = "DEBUG"
            assert False, "Should have raised FrozenInstanceError"
        except (dataclasses.FrozenInstanceError, AttributeError):
            pass

    def test_dataclass_replace_works(self):
        config = AppConfig()
        new_config = dataclasses.replace(config, debug=True)
        assert new_config.debug is True
        assert config.debug is False  # original unchanged
