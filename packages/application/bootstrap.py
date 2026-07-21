"""
Application bootstrap — single entry point for base service initialization.

Provides ``initialize()`` which loads config, sets up logging, creates the
ProjectStore, and returns an ``AppContext`` with initialized services.

Usage::

    from packages.application.bootstrap import initialize

    result = initialize()
    if result.is_ok():
        ctx = result.unwrap()
        logger = ctx.logger
        store = ctx.project_store
    else:
        print(f"Startup failed: {result.unwrap_error()}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from packages.application.repository_port import ProjectRepository, default_repository
from packages.domain.config import AppConfig, load_settings
from packages.domain.logging import configure_logging, get_logger
from packages.domain.result import Error, Ok, Result


@dataclass
class AppContext:
    """Initialized application services container.

    Returned by :func:`initialize` on success. Provides access to all
    base services that are ready at startup.

    Attributes:
        config: The resolved application configuration.
        logger: A root-level logger already configured.
        project_store: Ready-to-use ProjectStore for persistence operations.
    """

    config: AppConfig
    logger: logging.Logger
    project_store: ProjectRepository = field(default_factory=default_repository)

    @property
    def data_dir(self) -> Path:
        """Shortcut to the configured data directory."""
        return Path(self.config.data_dir)


def initialize(
    config_overrides: dict | None = None,
) -> Result[AppContext, str]:
    """Initialize all base application services.

    Call this once at application startup. It:

    1. Loads application configuration (defaults + overrides + env vars).
    2. Configures the logging system.
    3. Ensures the data directory exists.
    4. Creates a ready-to-use :class:`ProjectStore`.

    Args:
        config_overrides: Optional dict of fields to override on AppConfig.
            Same shape as :func:`domain.config.load_settings`.

    Returns:
        ``Ok(AppContext)`` on success, ``Error(str)`` on failure with a
        human-readable message describing what went wrong.
    """
    try:
        # 1. Load application configuration
        config = load_settings(config_overrides)

        # 2. Configure logging globally
        configure_logging(config)
        logger = get_logger("narrative-architect", config)
        logger.info("Application starting", extra={"version": config.app_version})

        # 3. Ensure data directory exists
        data_dir = Path(config.data_dir)
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return Error(
                f"Cannot create data directory '{data_dir}': {e}"
            )

        # 4. Create ProjectStore (vía la raíz de composición del puerto,
        #    DC-AUDIT-03: application no importa persistence estáticamente)
        project_store = default_repository()

        context = AppContext(
            config=config,
            logger=logger,
            project_store=project_store,
        )

        logger.info(
            "Application initialized",
            extra={
                "data_dir": str(data_dir),
                "debug": config.debug,
            },
        )
        return Ok(context)

    except Exception as e:
        return Error(f"Application initialization failed: {e}")


__all__ = [
    "AppContext",
    "initialize",
]
