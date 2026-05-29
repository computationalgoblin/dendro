"""
Project domain model.

Provides the base Project dataclass that represents a narrative project.
Extended in B02-T01 with full configuration, language settings, prepared
collections, and structured metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypeVar

from packages.domain.entity import NarrativeEntity
from packages.domain.relation import NarrativeRelation
from packages.domain.project_config import (
    AIConfig,
    ExportConfig,
    GeneralProjectConfig,
    GenreConfig,
    ProjectMetadata,
    RealismConfig,
    ToneConfig,
    VisibilityConfig,
)

_T = TypeVar("_T")


def _now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """Generate a new project ID."""
    return uuid.uuid4().hex[:12]


@dataclass
class Project:
    """A narrative project.

    This is the root entity of the application. Contains identification,
    metadata, configuration, and prepared collections for entities,
    relations, sources, history, and issues.

    Extended in B02-T01 to cover all 20 fields from contrato_fases §2.2.

    Attributes:
        id: Unique project identifier (hex string, 12 chars).
        name: Human-readable project name.
        description: Project description.
        primary_language: Primary language code (default "es").
        secondary_languages: Secondary language codes.
        created_at: Timestamp of project creation (UTC).
        updated_at: Timestamp of last modification (UTC).
        metadata: Flat key-value metadata store (backward compat).
        project_metadata: Structured project metadata.
        general: General project configuration.
        tone: Narrative tone configuration.
        genre: Genre classification.
        realism: Realism and world-building parameters.
        ai: AI assistance configuration (placeholder).
        visibility: Default visibility rules.
        export: Export preferences (placeholder).
        entities: Prepared collection for narrative entities (Bloque 3).
        relations: Prepared collection for semantic relations (Bloque 4).
        sources: Prepared collection for documentary sources (Bloque 5).
        history: Prepared collection for history events (Bloque 6).
        issues: Prepared collection for issues and AI candidates (Bloque 6+).
    """

    # Identification and core fields (Bloque 1)
    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    primary_language: str = "es"
    secondary_languages: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    metadata: dict[str, str] = field(default_factory=dict)

    # Configuration dataclasses
    project_metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    general: GeneralProjectConfig = field(default_factory=GeneralProjectConfig)
    tone: ToneConfig = field(default_factory=ToneConfig)
    genre: GenreConfig = field(default_factory=GenreConfig)
    realism: RealismConfig = field(default_factory=RealismConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    visibility: VisibilityConfig = field(default_factory=VisibilityConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    # Prepared collections (empty, for Bloque 3-6+)
    entities: list[NarrativeEntity] = field(default_factory=list)
    relations: list[NarrativeRelation] = field(default_factory=list)
    sources: list = field(default_factory=list)
    history: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    def touch(self) -> None:
        """Mark the project as updated (bump updated_at)."""
        self.updated_at = _now_utc()

    # ------------------------------------------------------------------
    # Serialization helpers for config dataclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _config_to_dict(config: object) -> dict:
        """Convert a config dataclass to a plain dict.

        Uses __dict__ to avoid importing dataclasses.asdict (stdlib-only).
        Excludes private attributes and nested dataclass instances.
        """
        result: dict = {}
        for key, value in config.__dict__.items():
            if key.startswith("_"):
                continue
            result[key] = value
        return result

    @staticmethod
    def _config_from_dict(cls: type[_T], data: dict) -> _T:
        """Reconstruct a config dataclass from a dict, using defaults
        for missing keys."""
        # Filter to only keys the dataclass actually accepts
        field_names = {f.name for f in getattr(cls, "__dataclass_fields__", {}).values()}
        filtered = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary.

        Returns:
            dict with string timestamps in ISO format, config sections,
            and prepared collections.
        """
        return {
            # Core fields
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "primary_language": self.primary_language,
            "secondary_languages": list(self.secondary_languages),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": dict(self.metadata),
            # Config dataclasses
            "project_metadata": self._config_to_dict(self.project_metadata),
            "general": self._config_to_dict(self.general),
            "tone": self._config_to_dict(self.tone),
            "genre": self._config_to_dict(self.genre),
            "realism": self._config_to_dict(self.realism),
            "ai": self._config_to_dict(self.ai),
            "visibility": self._config_to_dict(self.visibility),
            "export": self._config_to_dict(self.export),
            # Prepared collections
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "sources": list(self.sources),
            "history": list(self.history),
            "issues": list(self.issues),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Project:
        """Deserialize from a dictionary.

        Handles both v1 (minimal) and v2 (extended) data. Missing fields
        receive sensible defaults — no error raised for absent config
        sections or collections.

        Args:
            data: Dictionary with project data.

        Returns:
            New Project instance.

        Raises:
            KeyError: If required fields (id, created_at, updated_at)
                are missing.
            ValueError: If date fields are invalid.
        """
        return cls(
            # Core fields (required: id, created_at, updated_at)
            id=str(data["id"]),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            primary_language=str(data.get("primary_language", "es")),
            secondary_languages=list(data.get("secondary_languages", [])),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=dict(data.get("metadata", {})),
            # Config dataclasses (all optional — defaults apply)
            project_metadata=cls._config_from_dict(
                ProjectMetadata, data.get("project_metadata", {})
            ),
            general=cls._config_from_dict(
                GeneralProjectConfig, data.get("general", {})
            ),
            tone=cls._config_from_dict(
                ToneConfig, data.get("tone", {})
            ),
            genre=cls._config_from_dict(
                GenreConfig, data.get("genre", {})
            ),
            realism=cls._config_from_dict(
                RealismConfig, data.get("realism", {})
            ),
            ai=cls._config_from_dict(
                AIConfig, data.get("ai", {})
            ),
            visibility=cls._config_from_dict(
                VisibilityConfig, data.get("visibility", {})
            ),
            export=cls._config_from_dict(
                ExportConfig, data.get("export", {})
            ),
            # Prepared collections (all optional — empty list defaults)
            entities=[
                NarrativeEntity.from_dict(e)
                for e in data.get("entities", [])
                if isinstance(e, dict)
            ],
            relations=[
                NarrativeRelation.from_dict(r)
                for r in data.get("relations", [])
                if isinstance(r, dict)
            ],
            sources=list(data.get("sources", [])),
            history=list(data.get("history", [])),
            issues=list(data.get("issues", [])),
        )
