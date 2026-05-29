"""
Project service — application-layer lifecycle for projects.

Provides ``ProjectService``, a stateful service that manages the active
project and orchestrates domain + persistence operations: create, open,
save, save_as, close, validate, and configuration access.

Usage::

    from pathlib import Path
    from packages.persistence.store import ProjectStore
    from packages.application.project_service import ProjectService

    svc = ProjectService(ProjectStore())
    result = svc.create(name="My World")
    if result.is_ok():
        svc.save(Path("my-world.json"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result
from packages.persistence.schema import CURRENT_SCHEMA_VERSION
from packages.persistence.store import ProjectStore


@dataclass
class ProjectService:
    """Stateful service for project lifecycle management.

    Maintains an ``active_project`` reference that ``close()``, ``save()``
    and ``save_as()`` operate on when no explicit project is passed.

    Attributes:
        store: The ``ProjectStore`` used for persistence operations.
        active_project: The currently open project, or ``None``.
    """

    store: ProjectStore = field(default_factory=ProjectStore)
    active_project: Project | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create(
        self,
        name: str = "",
        config_overrides: dict | None = None,
    ) -> Result[Project, str]:
        """Create a new project with sensible defaults.

        The new project becomes the active project.

        Args:
            name: Project name (empty string by default).
            config_overrides: Optional dict of dotted-path keys to values
                applied after default project creation (e.g.
                ``{"general.theme": "cyberpunk"}``).

        Returns:
            ``Ok(Project)`` on success, ``Error(str)`` if overrides fail.
        """
        project = Project(name=name)

        if config_overrides:
            for path, value in config_overrides.items():
                result = self._set_config(project, path, value)
                if isinstance(result, Error):
                    return Error(
                        f"Failed to apply config override '{path}': "
                        f"{result.error}"
                    )

        self.active_project = project
        return Ok(project)

    def open(self, path: Path) -> Result[Project, str]:
        """Open a project from a file.

        The loaded project becomes the active project.

        Args:
            path: Path to the project JSON file.

        Returns:
            ``Ok(Project)`` on success, ``Error(str)`` on failure
            (file not found, corrupt, version mismatch, etc.).
        """
        result = self.store.load(path)
        if isinstance(result, Error):
            return Error(result.error)

        self.active_project = result.value
        return Ok(result.value)

    def save(self, path: Path) -> Result[None, str]:
        """Persist the active project to disk.

        Args:
            path: Output file path.

        Returns:
            ``Ok(None)`` on success, ``Error(str)`` on failure.
        """
        if self.active_project is None:
            return Error("No active project to save")
        return self.store.save(self.active_project, path)

    def save_as(self, path: Path) -> Result[None, str]:
        """Persist the active project to a new path.

        The active project remains unchanged; only the file path differs.

        Args:
            path: New output file path.

        Returns:
            ``Ok(None)`` on success, ``Error(str)`` on failure.
        """
        return self.save(path)

    def close(self) -> Result[None, str]:
        """Close the active project.

        Idempotent — safe to call when no project is active.

        Returns:
            ``Ok(None)`` always.
        """
        self.active_project = None
        return Ok(None)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, project: Project | None = None) -> Result[list[str], str]:
        """Validate a project's required fields.

        Checks basic integrity — name, dates, types. Does NOT perform
        semantic validation (that is the domain model's responsibility
        in future blocks).

        Args:
            project: The project to validate. Defaults to active project.

        Returns:
            ``Ok(list[str])`` with an empty list if valid, or a list of
            issue descriptions. ``Error(str)`` if no project is available.
        """
        target = project if project is not None else self.active_project
        if target is None:
            return Error("No project to validate")

        issues: list[str] = []

        if not target.name.strip():
            issues.append("Project name is empty")

        if not target.id:
            issues.append("Project id is empty")

        if target.created_at is None:
            issues.append("Project created_at is missing")

        if target.updated_at is None:
            issues.append("Project updated_at is missing")

        return Ok(issues)

    # ------------------------------------------------------------------
    # Configuration access
    # ------------------------------------------------------------------

    def get_config(
        self,
        config_path: str,
        project: Project | None = None,
    ) -> Result[Any, str]:
        """Read a configuration value by dotted path.

        Examples::

            svc.get_config("primary_language")       # -> "es"
            svc.get_config("general.theme")           # -> ""
            svc.get_config("ai.enabled")              # -> False
            svc.get_config("project_metadata.author") # -> ""

        Args:
            config_path: Dotted path to the configuration field.
            project: The project to read from. Defaults to active project.

        Returns:
            ``Ok(value)`` on success, ``Error(str)`` if the path is
            invalid or no project is available.
        """
        target = project if project is not None else self.active_project
        if target is None:
            return Error("No project available to read configuration")

        return self._get_config(target, config_path)

    def update_config(
        self,
        config_path: str,
        value: Any,
        project: Project | None = None,
        path: Path | None = None,
    ) -> Result[None, str]:
        """Update a configuration value by dotted path and optionally persist.

        Args:
            config_path: Dotted path to the configuration field.
            value: New value to set.
            project: The project to modify. Defaults to active project.
            path: If provided, persist the project after modification.

        Returns:
            ``Ok(None)`` on success, ``Error(str)`` on failure.
        """
        target = project if project is not None else self.active_project
        if target is None:
            return Error("No project available to update configuration")

        result = self._set_config(target, config_path, value)
        if isinstance(result, Error):
            return Error(result.error)

        target.touch()

        if path is not None:
            save_result = self.store.save(target, path)
            if isinstance(save_result, Error):
                return Error(save_result.error)

        return Ok(None)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def get_schema_version(self) -> int:
        """Return the current schema version used by new projects.

        Returns:
            ``CURRENT_SCHEMA_VERSION`` (currently 2).
        """
        return CURRENT_SCHEMA_VERSION

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_config(project: Project, config_path: str) -> Result[Any, str]:
        """Walk a dotted path to read a value from a Project.

        Handles top-level attributes (``name``, ``primary_language``)
        and nested config dataclass attributes (``general.theme``,
        ``ai.enabled``).
        """
        parts = config_path.split(".")
        current: Any = project

        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return Error(
                    f"Configuration path '{config_path}' not found "
                    f"(missing '{part}' in '{type(current).__name__}')"
                )

        return Ok(current)

    @staticmethod
    def _set_config(
        project: Project, config_path: str, value: Any
    ) -> Result[None, str]:
        """Walk a dotted path to set a value on a Project.

        Handles top-level attributes and nested config dataclass
        attributes.
        """
        parts = config_path.split(".")
        if not parts:
            return Error("Empty configuration path")

        # Walk to the parent object
        current: Any = project
        for part in parts[:-1]:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return Error(
                    f"Cannot set '{config_path}': "
                    f"'{part}' not found in '{type(current).__name__}'"
                )

        # Set the final attribute
        final = parts[-1]
        if hasattr(current, final):
            setattr(current, final, value)
        else:
            return Error(
                f"Cannot set '{config_path}': "
                f"'{final}' not found in '{type(current).__name__}'"
            )

        return Ok(None)


__all__ = ["ProjectService"]
