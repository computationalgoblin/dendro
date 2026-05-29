"""
Local project store with atomic save, load with validation, and backup management.

Uses Result type from domain for safe error handling.
JSON format with schema versioning.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Error, Ok, Result
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v1_to_v2,
    _apply_migration_v2_to_v3,
    _apply_migration_v3_to_v4,
    _apply_migration_v4_to_v5,
    _apply_migration_v5_to_v6,
    detect_schema_version,
    validate_project_structure,
    validate_schema_version,
)

BACKUP_SUFFIX = ".bak"
TEMP_SUFFIX = ".tmp"
MAX_BACKUPS = 3


# ---------------------------------------------------------------------------
# Low-level I/O helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Result[dict[str, Any], str]:
    """Read and parse a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Ok(dict) on success, Error(message) on failure.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Error(f"Project file not found: {path}")
    except PermissionError:
        return Error(f"Permission denied reading: {path}")
    except OSError as e:
        return Error(f"I/O error reading {path}: {e}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return Error(
            f"Project file is corrupt or invalid JSON: {path}\n"
            f"  JSON error: {e.msg} at line {e.lineno}, column {e.colno}"
        )

    if not isinstance(data, dict):
        return Error(f"Project file is not a JSON object: {path}")

    return Ok(data)


def _write_json_atomic(data: dict[str, Any], path: Path) -> Result[None, str]:
    """Write JSON data to a file atomically.

    Writes to a temporary file first, fsyncs, then renames to target.
    This prevents partial writes from corrupting the project file.

    Args:
        data: Data to serialize as JSON.
        path: Final output path.

    Returns:
        Ok(None) on success, Error(message) on failure.
    """
    tmp_path = path.with_suffix(path.suffix + TEMP_SUFFIX)

    try:
        serialized = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        tmp_path.write_text(serialized, encoding="utf-8")

        # On Unix: fsync the file, then the directory
        try:
            fd = os.open(tmp_path, os.O_RDONLY)
            os.fsync(fd)
            os.close(fd)
        except OSError:
            pass  # best-effort fsync

        # Atomic rename (POSIX guarantees this on same filesystem)
        tmp_path.rename(path)

        # fsync parent directory to ensure metadata is flushed
        try:
            fd = os.open(str(path.parent), os.O_RDONLY)
            os.fsync(fd)
            os.close(fd)
        except OSError:
            pass  # best-effort directory sync

    except OSError as e:
        return Error(f"I/O error writing project file: {e}")
    except (TypeError, ValueError) as e:
        return Error(f"Serialization error: {e}")

    return Ok(None)


# ---------------------------------------------------------------------------
# Backup management
# ---------------------------------------------------------------------------


def _rotate_backups(path: Path) -> None:
    """Rotate backup files, keeping the most recent MAX_BACKUPS.

    Args:
        path: Primary project file path.
    """
    # Find existing backups
    existing: list[tuple[int, Path]] = []
    for p in path.parent.glob(f"{path.name}{BACKUP_SUFFIX}*"):
        try:
            # Parse backup index: .bak.1, .bak.2, etc.
            suffix = p.suffixes
            if len(suffix) >= 2 and suffix[-2] == BACKUP_SUFFIX:
                idx = int(suffix[-1].lstrip("."))
                existing.append((idx, p))
        except (ValueError, IndexError):
            pass

    # Sort by index descending and remove excess
    existing.sort(key=lambda x: x[0], reverse=True)
    for idx, p in existing[MAX_BACKUPS - 1:]:
        p.unlink(missing_ok=True)


def _create_backup(path: Path) -> None:
    """Create a numbered backup of an existing file.

    Args:
        path: Existing file to back up.
    """
    if not path.exists():
        return

    # Find next backup index
    idx = 1
    base = str(path)
    while Path(f"{base}{BACKUP_SUFFIX}.{idx}").exists():
        idx += 1

    backup_path = Path(f"{base}{BACKUP_SUFFIX}.{idx}")
    shutil.copy2(path, backup_path)
    _rotate_backups(path)


# ---------------------------------------------------------------------------
# Convenience: data-level I/O (no Project model dependency)
# ---------------------------------------------------------------------------


def save_project_data(
    data: dict[str, Any],
    path: Path,
    schema_version: int = CURRENT_SCHEMA_VERSION,
) -> Result[None, str]:
    """Save project data to a file atomically with schema version.

    Args:
        data: Project data dictionary (without schema_version).
        path: Output file path.
        schema_version: Schema version to embed.

    Returns:
        Ok(None) on success, Error(message) on failure.
    """
    # Embed schema version
    payload = dict(data)
    payload["schema_version"] = schema_version

    # Create parent directory if needed
    path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing file
    _create_backup(path)

    # Atomic write
    return _write_json_atomic(payload, path)


def load_project_data(path: Path) -> Result[dict[str, Any], str]:
    """Load and validate project data from a file.

    Performs:
    1. File existence check
    2. JSON parse
    3. Schema version detection and validation
    4. Schema migration (v1 → v2) if needed
    5. Structural validation

    Args:
        path: Path to the project file.

    Returns:
        Ok(dict) on success, Error(message) on failure.
    """
    # Step 1-2: Read and parse
    result = _read_json(path)
    if isinstance(result, Error):
        return Error(result.error)

    data = result.value

    # Step 3: Detect and validate schema version
    version = detect_schema_version(data)
    validation_error = validate_schema_version(version)
    if validation_error is not None:
        return Error(validation_error)

    # Step 4: Migrate if needed
    if version == 1:
        data = _apply_migration_v1_to_v2(data)
        data["schema_version"] = 2
        version = 2

    if version == 2:
        data = _apply_migration_v2_to_v3(data)
        data["schema_version"] = 3
        version = 3

    if version == 3:
        data = _apply_migration_v3_to_v4(data)
        data["schema_version"] = 4
        version = 4

    if version == 4:
        data = _apply_migration_v4_to_v5(data)
        data["schema_version"] = 5
        version = 5

    if version == 5:
        data = _apply_migration_v5_to_v6(data)
        data["schema_version"] = CURRENT_SCHEMA_VERSION

    # Step 5: Structural validation
    structure_error = validate_project_structure(data)
    if structure_error is not None:
        return Error(structure_error)

    return Ok(data)


# ---------------------------------------------------------------------------
# High-level ProjectStore
# ---------------------------------------------------------------------------


class ProjectStore:
    """High-level store that works with Project domain objects.

    Handles serialization, deserialization, and file I/O.
    Manages backup rotation automatically.

    Usage:
        store = ProjectStore()
        result = store.save(project, Path("mi-proyecto.json"))
        result = store.load(Path("mi-proyecto.json"))
    """

    def save(self, project: Project, path: Path) -> Result[None, str]:
        """Save a Project to a file.

        Args:
            project: The project to save.
            path: Output file path.

        Returns:
            Ok(None) on success, Error(message) on failure.
        """
        data = project.to_dict()
        return save_project_data(data, path)

    def load(self, path: Path) -> Result[Project, str]:
        """Load a Project from a file.

        Args:
            path: Path to the project file.

        Returns:
            Ok(Project) on success, Error(message) on failure.
        """
        result = load_project_data(path)
        if isinstance(result, Error):
            return Error(result.error)

        data = result.value

        # Deserialize to Project
        try:
            project = Project.from_dict(data)
        except KeyError as e:
            return Error(f"Project file is missing required field: {e}")
        except ValueError as e:
            return Error(f"Project file has invalid data: {e}")

        return Ok(project)

    def exists(self, path: Path) -> bool:
        """Check if a project file exists.

        Args:
            path: Path to check.

        Returns:
            True if the file exists.
        """
        return path.is_file()

    def get_backup_paths(self, path: Path) -> list[Path]:
        """Get paths to backup files for a project.

        Args:
            path: Primary project file path.

        Returns:
            List of backup paths, sorted newest-first.
        """
        backups: list[tuple[int, Path]] = []
        for p in path.parent.glob(f"{path.name}{BACKUP_SUFFIX}*"):
            try:
                suffix = p.suffixes
                if len(suffix) >= 2 and suffix[-2] == BACKUP_SUFFIX:
                    idx = int(suffix[-1].lstrip("."))
                    backups.append((idx, p))
            except (ValueError, IndexError):
                pass
        backups.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in backups]

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    def add_entity(
        self, project: Project, entity: NarrativeEntity, path: Path
    ) -> Result[None, str]:
        """Add an entity to the project and persist.

        Args:
            project: The project to add to.
            entity: The entity to add.
            path: File path to persist to.

        Returns:
            Ok(None) on success, Error on failure.
        """
        project.entities.append(entity)
        return self.save(project, path)

    def update_entity(
        self, project: Project, entity: NarrativeEntity, path: Path
    ) -> Result[None, str]:
        """Replace an entity by id and persist.

        Args:
            project: The project containing the entity.
            entity: The updated entity (matched by id).
            path: File path to persist to.

        Returns:
            Ok(None) on success, Error if entity not found.
        """
        for i, existing in enumerate(project.entities):
            if existing.id == entity.id:
                project.entities[i] = entity
                return self.save(project, path)
        return Error(f"Entity with id '{entity.id}' not found in project")

    def archive_entity(
        self, project: Project, entity_id: str, path: Path
    ) -> Result[None, str]:
        """Soft-delete an entity by setting canon_state=ARCHIVED.

        The entity remains in the list for traceability.

        Args:
            project: The project containing the entity.
            entity_id: The entity to archive.
            path: File path to persist to.

        Returns:
            Ok(None) on success, Error if entity not found.
        """
        from packages.domain.entity import CanonState

        for entity in project.entities:
            if entity.id == entity_id:
                entity.canon_state = CanonState.ARCHIVADO
                entity.touch()
                return self.save(project, path)
        return Error(f"Entity with id '{entity_id}' not found in project")

    def restore_entity(
        self, project: Project, entity_id: str, path: Path
    ) -> Result[None, str]:
        """Restore an archived entity to BORRADOR state.

        Args:
            project: The project containing the entity.
            entity_id: The entity to restore.
            path: File path to persist to.

        Returns:
            Ok(None) on success, Error if entity not found or not archived.
        """
        from packages.domain.entity import CanonState

        for entity in project.entities:
            if entity.id == entity_id:
                if entity.canon_state != CanonState.ARCHIVADO:
                    return Error(
                        f"Entity '{entity_id}' is not archived "
                        f"(current state: {entity.canon_state.value})"
                    )
                entity.canon_state = CanonState.BORRADOR
                entity.touch()
                return self.save(project, path)
        return Error(f"Entity with id '{entity_id}' not found in project")

    def find_entity(
        self, project: Project, entity_id: str
    ) -> Result[NarrativeEntity, str]:
        """Find an entity by id in the project.

        Args:
            project: The project to search.
            entity_id: The entity id to find.

        Returns:
            Ok(NarrativeEntity) on success, Error if not found.
        """
        for entity in project.entities:
            if entity.id == entity_id:
                return Ok(entity)
        return Error(f"Entity with id '{entity_id}' not found in project")

    # ------------------------------------------------------------------
    # Relation operations
    # ------------------------------------------------------------------

    def add_relation(
        self, project: Project, relation: NarrativeRelation
    ) -> None:
        """Add a relation to project.relations in memory. No implicit save."""
        project.relations.append(relation)

    def update_relation(
        self, project: Project, relation: NarrativeRelation
    ) -> Result[None, str]:
        """Replace a relation by id in project.relations."""
        for i, existing in enumerate(project.relations):
            if existing.id == relation.id:
                project.relations[i] = relation
                return Ok(None)
        return Error(f"Relation with id '{relation.id}' not found in project")

    def archive_relation(
        self, project: Project, relation_id: str
    ) -> Result[None, str]:
        """Soft-delete a relation by setting canon_state=ARCHIVADO."""
        from packages.domain.entity import CanonState

        for rel in project.relations:
            if rel.id == relation_id:
                rel.canon_state = CanonState.ARCHIVADO
                rel.touch()
                return Ok(None)
        return Error(f"Relation with id '{relation_id}' not found in project")

    def restore_relation(
        self, project: Project, relation_id: str
    ) -> Result[None, str]:
        """Restore an archived relation to BORRADOR state."""
        from packages.domain.entity import CanonState

        for rel in project.relations:
            if rel.id == relation_id:
                if rel.canon_state != CanonState.ARCHIVADO:
                    return Error(
                        f"Relation '{relation_id}' is not archived "
                        f"(current: {rel.canon_state.value})"
                    )
                rel.canon_state = CanonState.BORRADOR
                rel.touch()
                return Ok(None)
        return Error(f"Relation with id '{relation_id}' not found in project")

    def find_relation(
        self, project: Project, relation_id: str
    ) -> Result[NarrativeRelation, str]:
        """Find a relation by id."""
        for rel in project.relations:
            if rel.id == relation_id:
                return Ok(rel)
        return Error(f"Relation with id '{relation_id}' not found in project")

    def find_relations_by_entity(
        self, project: Project, entity_id: str
    ) -> list[NarrativeRelation]:
        """Return all relations where entity_id is source or target."""
        return [
            r for r in project.relations
            if r.source_id == entity_id or r.target_id == entity_id
        ]

    def validate_relations_integrity(
        self, project: Project
    ) -> Result[None, str]:
        """Validate referential integrity of all relations.

        Checks that every source_id and target_id references an
        existing entity in project.entities.  This is the persistence
        layer's safety barrier — the application layer (B04-T03)
        validates at create/update time as well.
        """
        entity_ids = {e.id for e in project.entities}
        for i, rel in enumerate(project.relations):
            if rel.source_id and rel.source_id not in entity_ids:
                return Error(
                    f"Relation at index {i} (id='{rel.id}'): "
                    f"source entity '{rel.source_id}' not found"
                )
            if rel.target_id and rel.target_id not in entity_ids:
                return Error(
                    f"Relation at index {i} (id='{rel.id}'): "
                    f"target entity '{rel.target_id}' not found"
                )
        return Ok(None)
