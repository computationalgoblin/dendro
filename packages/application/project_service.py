"""
Project service — application-layer lifecycle for projects.

Provides ``ProjectService``, a stateful service that manages the active
project and orchestrates domain + persistence operations: create, open,
save, save_as, close, validate, and configuration access.

Usage::

    from pathlib import Path
    from packages.application.project_service import ProjectService

    svc = ProjectService()
    result = svc.create(name="My World")
    if result.is_ok():
        svc.save(Path("my-world.json"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.application.repository_port import (
    ProjectRepository,
    current_schema_version,
    default_repository,
)
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result


def _file_fingerprint(path: Path) -> tuple[int, int] | None:
    """Huella barata de un fichero: (mtime en ns, tamaño).

    BETA-AUDIT-12. No se hashea el contenido a propósito: un proyecto grande son
    megas y esto corre en cada guardado, incluido el autoguardado diferido. Con
    mtime+tamaño basta para detectar que ALGUIEN MÁS escribió; los falsos negativos
    (misma marca de tiempo y mismo tamaño exacto) son irrelevantes en la práctica.
    """
    try:
        estado = Path(path).stat()
    except OSError:
        return None
    return (estado.st_mtime_ns, estado.st_size)


@dataclass
class ProjectService:
    """Stateful service for project lifecycle management.

    Maintains an ``active_project`` reference that ``close()``, ``save()``
    and ``save_as()`` operate on when no explicit project is passed.

    Attributes:
        store: Repositorio de proyectos (``ProjectRepository``) usado para
            las operaciones de persistencia.
        active_project: The currently open project, or ``None``.
    """

    store: ProjectRepository = field(default_factory=default_repository)
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
        # BETA-AUDIT-12: se recuerda de qué fichero venimos y cómo estaba.
        self._loaded_path = Path(path)
        self._loaded_fingerprint = _file_fingerprint(path)
        return Ok(result.value)

    def set_last_worked_entity(self, entity_id: str) -> Result[None, str]:
        """BETA2-FOCO: recuerda la última entidad trabajada (Foco la centra al abrir).

        Vive en ``Project.metadata["last_worked_entity_id"]``: viaja con el
        archivo del proyecto y se persiste con cualquier guardado normal. No
        marca el proyecto como editado (sin ``touch``): centrar una entidad no
        es un cambio de contenido. Cadena vacía limpia la marca.
        """
        if self.active_project is None:
            return Error("No active project")
        project = self.active_project
        cleaned = (entity_id or "").strip()
        if not cleaned:
            project.metadata.pop("last_worked_entity_id", None)
            return Ok(None)
        if project.entity_by_id(cleaned) is None:
            return Error(f"Entidad no encontrada: {cleaned}")
        project.metadata["last_worked_entity_id"] = cleaned
        return Ok(None)

    def get_last_worked_entity(self) -> Result[str, str]:
        """Id de la última entidad trabajada, o "" si no hay o ya no existe."""
        if self.active_project is None:
            return Error("No active project")
        value = self.active_project.metadata.get("last_worked_entity_id", "")
        if value and self.active_project.entity_by_id(value) is None:
            return Ok("")
        return Ok(value)

    def save(self, path: Path) -> Result[None, str]:
        """Persist the active project to disk.

        Args:
            path: Output file path.

        Returns:
            ``Ok(None)`` on success, ``Error(str)`` on failure.
        """
        if self.active_project is None:
            return Error("No active project to save")

        # BETA-AUDIT-12: nadie comprobaba si el fichero había cambiado por debajo.
        # Con el proyecto en una carpeta sincronizada (OneDrive, Drive, Dropbox) o
        # abierto dos veces, el último en guardar se llevaba por delante el trabajo
        # del otro en silencio — agravado porque el proyecto es un JSON monolítico
        # que se reescribe entero.
        conflicto = self._detect_external_change(path)
        if conflicto is not None:
            respaldo = self._write_conflict_copy(path)
            detalle = f" Tu trabajo se ha guardado en «{respaldo.name}»." if respaldo else ""
            return Error(
                "El fichero del proyecto ha cambiado fuera de Dendro desde que lo "
                f"abriste ({conflicto}). No se ha sobrescrito para no perder esos "
                f"cambios.{detalle}"
            )

        resultado = self.store.save(self.active_project, path)
        if not isinstance(resultado, Error):
            # Tras un guardado correcto la huella se refresca: si no, el SEGUNDO
            # autoguardado seguido se detectaría a sí mismo como conflicto.
            self._loaded_fingerprint = _file_fingerprint(path)
            self._loaded_path = Path(path)
        return resultado

    def _detect_external_change(self, path: Path) -> str | None:
        """Devuelve una descripción del conflicto, o ``None`` si se puede guardar.

        Solo vigila la ruta de la que se cargó: un ``save_as`` a otro sitio nunca
        puede dar falso positivo.
        """
        destino = Path(path)
        origen = getattr(self, "_loaded_path", None)
        huella = getattr(self, "_loaded_fingerprint", None)
        if huella is None or origen is None or destino != origen:
            return None
        if not destino.exists():
            return None  # lo borraron: guardar lo recrea, no hay nada que pisar
        actual = _file_fingerprint(destino)
        if actual == huella:
            return None
        return "otra copia de Dendro o una carpeta sincronizada lo reescribió"

    def _write_conflict_copy(self, path: Path) -> Path | None:
        """Vuelca lo que hay en memoria a un fichero aparte para no perderlo."""
        destino = Path(path)
        marca = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        alterno = destino.with_name(f"{destino.stem}-conflicto-{marca}{destino.suffix}")
        resultado = self.store.save(self.active_project, alterno)
        return alterno if not isinstance(resultado, Error) else None

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
        # BETA-AUDIT-12: sin huella no hay vigilancia de conflicto sobre un fichero
        # que ya no tenemos abierto.
        self._loaded_path = None
        self._loaded_fingerprint = None
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
            La ``CURRENT_SCHEMA_VERSION`` de persistencia, resuelta vía el
            puerto de repositorio (application no importa persistence).
        """
        return current_schema_version()

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
