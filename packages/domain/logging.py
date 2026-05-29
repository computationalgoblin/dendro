"""
Structured logging module for narrative-architect.

Provides a logging setup function that creates a standardized logger
with structured format, timestamps, and configurable output.

Uses Python's standard `logging` module with no external dependencies.
All loggers created through this module follow the same format and
conventions defined in the application configuration.
"""

from __future__ import annotations

import logging
import sys

from packages.domain.config import AppConfig

# Module-level cache of configured loggers
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str, config: AppConfig | None = None) -> logging.Logger:
    """Get a configured logger for the given name.

    Creates a new logger if one doesn't exist for this name, or returns
    an existing one. Loggers are configured with the format and level
    from the application configuration.

    Args:
        name: The logger name, typically ``__name__`` of the calling module.
        config: Optional AppConfig. If None, uses get_settings().

    Returns:
        A configured logging.Logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Application started", extra={"version": "1.0"})
    """
    if name in _loggers:
        return _loggers[name]

    if config is None:
        from packages.domain.config import get_settings
        config = get_settings()

    logger = logging.getLogger(name)
    log_config = config.logging

    logger.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))

    # Only add handler if the logger doesn't have one already
    if not logger.handlers:
        handler: logging.Handler
        if log_config.output_file:
            handler = logging.FileHandler(log_config.output_file)
        else:
            handler = logging.StreamHandler(sys.stderr)

        handler.setLevel(logger.level)

        if log_config.structured:
            fmt = logging.Formatter(
                log_config.format or _DEFAULT_STRUCTURED_FORMAT,
                datefmt=log_config.date_format,
            )
        else:
            fmt = logging.Formatter(
                "%(levelname)s: %(message)s",
            )

        handler.setFormatter(fmt)
        logger.addHandler(handler)

        # Prevent propagation to root logger to avoid duplicate messages
        logger.propagate = False

    _loggers[name] = logger
    return logger


_DEFAULT_STRUCTURED_FORMAT = "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s"
"""Default log format used when structured=True and no custom format is given."""


def configure_logging(config: AppConfig | None = None) -> None:
    """Configure the root logger and clear module-level cache.

    Call this once at application startup to set up logging globally.
    Subsequent calls to get_logger() will use the new configuration.

    Args:
        config: AppConfig with logging settings. If None, uses defaults.
    """
    if config is None:
        from packages.domain.config import get_settings
        config = get_settings()

    # Reset module-level cache
    _loggers.clear()

    # Configure root logger
    root_logger = logging.getLogger()
    log_config = config.logging
    root_logger.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))

    # Remove existing handlers from root
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add root handler
    handler: logging.Handler
    if log_config.output_file:
        handler = logging.FileHandler(log_config.output_file)
    else:
        handler = logging.StreamHandler(sys.stderr)

    if log_config.structured:
        fmt = logging.Formatter(
            log_config.format or _DEFAULT_STRUCTURED_FORMAT,
            datefmt=log_config.date_format,
        )
    else:
        fmt = logging.Formatter("%(levelname)s: %(message)s")

    handler.setFormatter(fmt)
    root_logger.addHandler(handler)


def shutdown_logging() -> None:
    """Shut down the logging system and flush all handlers.

    Call this during application shutdown to ensure all log messages
    are written and resources are released.
    """
    _loggers.clear()
    logging.shutdown()


__all__ = [
    "get_logger",
    "configure_logging",
    "shutdown_logging",
]
