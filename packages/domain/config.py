"""
Application configuration module.

Provides typed configuration using dataclasses with sensible defaults.
The configuration can be loaded from environment variables or a config file
in the future, but currently uses hardcoded defaults that work out of the box.

All settings are defined in the domain layer so they are accessible to
all layers without dependency inversion.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class LoggingConfig:
    """Configuration for the logging subsystem."""

    level: str = "INFO"
    """Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL."""

    format: str = "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s"
    """Log format string. Uses Python's %-formatting."""

    date_format: str = "%Y-%m-%d %H:%M:%S"
    """Date format for timestamps in log messages."""

    output_file: str | None = None
    """Optional path to a log file. If None, logs go to stderr."""

    structured: bool = True
    """If True, adds structured context (module, function, line) to each message."""


@dataclasses.dataclass(frozen=True)
class AppConfig:
    """Global application configuration.

    This is the top-level configuration object. All subsystems get their
    config from here. In the future, this could be loaded from JSON/YAML
    or environment variables; currently uses sensible defaults.
    """

    app_name: str = "narrative-architect"
    """Application name, used in logging and metadata."""

    app_version: str = "0.9.0b1"
    """Current application version (semver)."""

    debug: bool = False
    """If True, enables debug-level logging and verbose error messages."""

    logging: LoggingConfig = dataclasses.field(default_factory=LoggingConfig)
    """Logging subsystem configuration."""

    data_dir: str = str(Path.home() / ".narrative-architect")
    """Directory where application data (projects, config, logs) is stored."""


# Module-level singleton for global access
_settings: AppConfig | None = None


def get_settings() -> AppConfig:
    """Get the current application settings singleton.

    Returns the global AppConfig instance, creating it with defaults
    if it hasn't been initialized yet.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def load_settings(overrides: dict | None = None) -> AppConfig:
    """Load application settings from defaults and optional overrides.

    Args:
        overrides: Optional dict of fields to override on AppConfig.
            Nested dicts are supported for nested configs (e.g.,
            {"logging": {"level": "DEBUG"}}).

    Returns:
        An AppConfig instance with merged settings.

    Example:
        config = load_settings({"debug": True, "logging": {"level": "DEBUG"}})
    """
    config = AppConfig()

    if overrides:
        return _merge_config(config, overrides)

    # Check environment variables
    env_debug = os.environ.get("NA_DEBUG", "").lower()
    if env_debug in ("1", "true", "yes"):
        config = dataclasses.replace(config, debug=True)

    env_log_level = os.environ.get("NA_LOG_LEVEL", "")
    if env_log_level:
        config = dataclasses.replace(
            config,
            logging=dataclasses.replace(
                config.logging, level=env_log_level.upper()
            ),
        )

    return config


def _merge_config(config: AppConfig, overrides: dict) -> AppConfig:
    """Merge a nested dict of overrides into an AppConfig."""
    merged = config

    if "debug" in overrides:
        merged = dataclasses.replace(merged, debug=bool(overrides["debug"]))

    if "app_name" in overrides:
        merged = dataclasses.replace(merged, app_name=str(overrides["app_name"]))

    if "app_version" in overrides:
        merged = dataclasses.replace(merged, app_version=str(overrides["app_version"]))

    if "data_dir" in overrides:
        merged = dataclasses.replace(merged, data_dir=str(overrides["data_dir"]))

    if "logging" in overrides and isinstance(overrides["logging"], dict):
        log_overrides = overrides["logging"]
        log_config = merged.logging
        for field_name in ("level", "format", "date_format", "output_file", "structured"):
            if field_name in log_overrides:
                log_config = dataclasses.replace(
                    log_config, **{field_name: log_overrides[field_name]}
                )
        merged = dataclasses.replace(merged, logging=log_config)

    return merged


def reset_settings() -> None:
    """Reset the settings singleton. Useful for testing."""
    global _settings
    _settings = None


__all__ = [
    "AppConfig",
    "LoggingConfig",
    "get_settings",
    "load_settings",
    "reset_settings",
]
