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

from packages.domain.candidate_issue import Issue, Candidate, StructuredIssue
from packages.domain.narrative_framework import NarrativeFramework
from packages.domain.temporal_models import TimelineEvent
from packages.domain.import_models import ImportBasket
from packages.domain.custom_types import (
    CustomEntityType,
    CustomFieldDefinition,
    CustomRelationType,
)
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_domain import NarrativeDomain
from packages.domain.world_layer import WorldLayer, default_world_layers
from packages.domain.advanced_config import AdvancedProjectConfig
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
from packages.domain.relation import NarrativeRelation
from packages.domain.source_history import HistoryEntry, Source

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
    sources: list[Source] = field(default_factory=list)
    history: list[HistoryEntry] = field(default_factory=list)
    issues: list[StructuredIssue] = field(default_factory=list)
    narrative_frameworks: list[NarrativeFramework] = field(default_factory=list)
    framework_templates: list[NarrativeFramework] = field(default_factory=list)
    timeline_events: list[TimelineEvent] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)

    # Custom types and taxonomies (Bloque 8)
    custom_entity_types: list[CustomEntityType] = field(default_factory=list)
    custom_field_definitions: list[CustomFieldDefinition] = field(default_factory=list)
    custom_relation_types: list[CustomRelationType] = field(default_factory=list)

    # ── Domains, layers & advanced config (Bloque 10) ──
    domains: list[str] = field(default_factory=lambda: [
        NarrativeDomain.MUNDO.value,
        NarrativeDomain.HISTORIA.value,
        NarrativeDomain.CAMPANA.value,
        NarrativeDomain.COMPARTIDO.value,
        NarrativeDomain.SIN_ASIGNAR.value,
    ])
    world_layers: list[WorldLayer] = field(default_factory=default_world_layers)
    advanced_config: AdvancedProjectConfig = field(default_factory=AdvancedProjectConfig)

    # ── Import baskets (Bloque 17) ──
    import_baskets: list[ImportBasket] = field(default_factory=list)

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
            "sources": [s.to_dict() for s in self.sources],
            "history": [h.to_dict() for h in self.history],
            "issues": [i.to_dict() for i in self.issues],
            "structured_issues": [i.to_dict() for i in self.issues],
            "narrative_frameworks": [f.to_dict() for f in self.narrative_frameworks],
            "framework_templates": [f.to_dict() for f in self.framework_templates],
            "timeline_events": [e.to_dict() for e in self.timeline_events],
            "candidates": [c.to_dict() for c in self.candidates],
            # Custom types (Bloque 8)
            "custom_entity_types": [ct.to_dict() for ct in self.custom_entity_types],
            "custom_field_definitions": [
                fd.to_dict() for fd in self.custom_field_definitions
            ],
            "custom_relation_types": [
                crt.to_dict() for crt in self.custom_relation_types
            ],
            # Domains, layers & advanced config (Bloque 10)
            "domains": list(self.domains),
            "world_layers": [wl.to_dict() for wl in self.world_layers],
            "advanced_config": self.advanced_config.to_dict(),
            # ── Import baskets (Bloque 17) ──
            "import_baskets": [b.to_dict() for b in self.import_baskets],
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
            sources=[Source.from_dict(s) for s in data.get("sources", []) if isinstance(s, dict)],
            history=[HistoryEntry.from_dict(h) for h in data.get("history", []) if isinstance(h, dict)],
            issues=[
                StructuredIssue.from_dict(i)
                for i in data.get("structured_issues", data.get("issues", []))
                if isinstance(i, dict)
            ],
            narrative_frameworks=[
                NarrativeFramework.from_dict(f)
                for f in data.get("narrative_frameworks", [])
                if isinstance(f, dict)
            ],
            framework_templates=[
                NarrativeFramework.from_dict(f)
                for f in data.get("framework_templates", [])
                if isinstance(f, dict)
            ],
            timeline_events=[
                TimelineEvent.from_dict(e)
                for e in data.get("timeline_events", [])
                if isinstance(e, dict)
            ],
            candidates=[Candidate.from_dict(c) for c in data.get("candidates", []) if isinstance(c, dict)],
            # Custom types (Bloque 8)
            custom_entity_types=[
                CustomEntityType.from_dict(ct)
                for ct in data.get("custom_entity_types", [])
                if isinstance(ct, dict)
            ],
            custom_field_definitions=[
                CustomFieldDefinition.from_dict(fd)
                for fd in data.get("custom_field_definitions", [])
                if isinstance(fd, dict)
            ],
            custom_relation_types=[
                CustomRelationType.from_dict(crt)
                for crt in data.get("custom_relation_types", [])
                if isinstance(crt, dict)
            ],
            # Domains, layers & advanced config (Bloque 10)
            **(
                {"domains": _parse_str_list(data["domains"])}
                if "domains" in data else {}
            ),
            **(
                {"world_layers": [
                    WorldLayer.from_dict(wl)
                    for wl in data.get("world_layers", [])
                    if isinstance(wl, dict)
                ]}
                if "world_layers" in data else {}
            ),
            **(
                {"advanced_config": AdvancedProjectConfig.from_dict(
                    data.get("advanced_config", {})
                )}
                if "advanced_config" in data else {}
            ),
            # ── Import baskets (Bloque 17) ──
            **(
                {"import_baskets": [
                    ImportBasket.from_dict(b)
                    for b in data.get("import_baskets", [])
                    if isinstance(b, dict)
                ]}
                if "import_baskets" in data else {}
            ),
        )

# ── Helpers ──

def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []

