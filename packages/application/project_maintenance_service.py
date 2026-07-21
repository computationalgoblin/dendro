"""Application-level project maintenance orchestration for B29."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packages.application.repository_port import ProjectRepository, default_repository
from packages.domain.result import Result


@dataclass
class ProjectMaintenanceService:
    """Safe maintenance facade over persistence backup/restore operations."""

    store: ProjectRepository = field(default_factory=default_repository)

    def create_backup(self, project_path: Path | str) -> Result[Path, str]:
        """Create a validated backup of a project file."""
        return self.store.create_backup(Path(project_path))

    def restore_backup(self, project_path: Path | str, backup_path: Path | str) -> Result[Path, str]:
        """Restore a validated backup after preserving the current file."""
        return self.store.restore_backup(Path(project_path), Path(backup_path))

    def list_backups(self, project_path: Path | str) -> list[Path]:
        """List project backups newest-first."""
        return self.store.get_backup_paths(Path(project_path))

    def backup_metadata(self, project_path: Path | str) -> list[dict[str, Any]]:
        """Return parseable metadata for backups without loading project contents."""
        rows: list[dict[str, Any]] = []
        for path in self.list_backups(project_path):
            try:
                stat = path.stat()
            except OSError:
                continue
            rows.append({
                "path": str(path),
                "bytes": stat.st_size,
                "mtime": stat.st_mtime,
            })
        return rows


__all__ = ["ProjectMaintenanceService"]
