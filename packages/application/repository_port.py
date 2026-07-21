"""Puerto de repositorio de proyectos (DC-AUDIT-03).

``ProjectRepository`` es el contrato estructural (``typing.Protocol``) con la
superficie de ``ProjectStore`` que consumen los servicios de application:
guardar/cargar el proyecto y las operaciones de backup. La implementación
concreta sigue en ``packages.persistence.store``; aquí solo se declara la
forma, de modo que application no importa persistence estáticamente.

``default_repository`` es la raíz de composición: construye el ``ProjectStore``
real por import dinámico (cacheado a nivel de módulo, no de instancia — cada
llamada devuelve un store nuevo, igual que el antiguo
``field(default_factory=ProjectStore)``). ``current_schema_version`` expone la
versión de esquema vigente por la misma vía.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from packages.domain.project import Project
    from packages.domain.result import Result


class ProjectRepository(Protocol):
    """Superficie de persistencia usada por los servicios de application.

    La cumple ``packages.persistence.store.ProjectStore`` (guardado atómico
    con backups ``.bak``); los tests pueden aportar dobles con esta forma.
    """

    def save(self, project: Project, path: Path) -> Result[None, str]:
        """Persiste el proyecto en ``path`` de forma atómica."""
        ...

    def load(self, path: Path) -> Result[Project, str]:
        """Carga (y migra si toca) el proyecto guardado en ``path``."""
        ...

    def create_backup(self, path: Path) -> Result[Path, str]:
        """Crea un backup numerado y verificado del fichero de proyecto."""
        ...

    def restore_backup(self, path: Path, backup_path: Path) -> Result[Path, str]:
        """Restaura un backup validado preservando antes el fichero actual."""
        ...

    def get_backup_paths(self, path: Path) -> list[Path]:
        """Rutas de backup existentes para un proyecto, más reciente primero."""
        ...


# ---------------------------------------------------------------------------
# Raíz de composición (resolución dinámica de persistence)
# ---------------------------------------------------------------------------

_store_module: ModuleType | None = None


def _persistence_store_module() -> ModuleType:
    """Import dinámico y cacheado de ``packages.persistence.store``."""
    global _store_module
    if _store_module is None:
        _store_module = importlib.import_module("packages.persistence.store")
    return _store_module


def default_repository() -> ProjectRepository:
    """Construye el ``ProjectStore`` por defecto (una instancia nueva por llamada)."""
    return _persistence_store_module().ProjectStore()


def current_schema_version() -> int:
    """Versión de esquema vigente (``packages.persistence.schema``)."""
    schema = importlib.import_module("packages.persistence.schema")
    return int(schema.CURRENT_SCHEMA_VERSION)


__all__ = ["ProjectRepository", "current_schema_version", "default_repository"]
