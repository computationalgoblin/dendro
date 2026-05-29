"""
Advanced config service — application-layer management of project configuration.

Provides ``AdvancedConfigService``, a stateful service for reading and
updating ``AdvancedProjectConfig`` on the active project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.domain.advanced_config import (
    CONFIG_ARRAY_PATHS,
    CONFIG_PATH_WHITELIST,
    AdvancedProjectConfig,
)
from packages.domain.result import Error, Ok, Result


@dataclass
class AdvancedConfigService:
    """Read and update advanced project configuration (§10.4).

    All paths are validated against ``CONFIG_PATH_WHITELIST``.
    Array paths are validated as ``list[str]``.
    """

    project_service: Any  # ProjectService

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_project(self):
        ps = self.project_service
        if ps.active_project is None:
            return Error("No active project")
        return Ok(ps.active_project)

    def _validate_path(self, path: str) -> str | None:
        """Return error message if *path* is invalid, or None."""
        if path not in CONFIG_PATH_WHITELIST:
            return (
                f"Invalid config path '{path}'. "
                f"Valid paths: {', '.join(sorted(CONFIG_PATH_WHITELIST))}"
            )
        return None

    def _validate_value(self, path: str, value: Any) -> str | None:
        """Return error message if *value* type is invalid for *path*."""
        if path in CONFIG_ARRAY_PATHS:
            if not isinstance(value, list):
                return f"'{path}' must be a list, got {type(value).__name__}"
            for i, v in enumerate(value):
                if not isinstance(v, str):
                    return f"'{path}[{i}]' must be a string, got {type(v).__name__}"
        return None

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_config(self) -> Result[AdvancedProjectConfig, str]:
        """Return the current advanced project configuration."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok(proj.value.advanced_config)

    def get_value(self, path: str) -> Result[Any, str]:
        """Return the value at a single config path."""
        err = self._validate_path(path)
        if err:
            return Error(err)
        cfg = self.get_config()
        if isinstance(cfg, Error):
            return Error(cfg.error)
        return Ok(getattr(cfg.value, path))

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def set_value(self, path: str, value: Any) -> Result[None, str]:
        """Set a single config value by path."""
        err = self._validate_path(path)
        if err:
            return Error(err)

        err = self._validate_value(path, value)
        if err:
            return Error(err)

        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        setattr(proj.value.advanced_config, path, value)
        proj.value.touch()
        return Ok(None)

    def update_config(
        self, **kwargs: Any,
    ) -> Result[AdvancedProjectConfig, str]:
        """Update multiple config fields at once."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for path, value in kwargs.items():
            err = self._validate_path(path)
            if err:
                return Error(err)
            err = self._validate_value(path, value)
            if err:
                return Error(err)
            setattr(proj.value.advanced_config, path, value)

        proj.value.touch()
        return Ok(proj.value.advanced_config)
