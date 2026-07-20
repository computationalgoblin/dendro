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
from typing import Any

from packages.domain.candidate_issue import Issue, Candidate, StructuredIssue
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.narrative_framework import NarrativeFramework
from packages.domain.project_chronology import ProjectChronology
from packages.domain.chronology_walk import ChronologyWalkReport, ChronologyWalkSession
from packages.domain.narrative_memory import NarrativeMemory
from packages.domain.structured_reference import StructuredReference
from packages.domain.temporal_models import TimelineEvent
from packages.domain.writing_models import WritingUnit
from packages.domain.campaign_models import Campaign, PlayerCharacterProfile, CampaignClock
from packages.domain.secrets_models import Secreto, Pista
from packages.domain.faction_models import Faction, Front
from packages.domain.session_models import Session
from packages.domain.custom_types import (
    CustomEntityType,
    CustomFieldDefinition,
    CustomRelationType,
)
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_domain import NarrativeDomain
from packages.domain.world_layer import WorldLayer
from packages.domain.creative_config import CreativeProjectConfig
from packages.domain.relation import NarrativeRelation
from packages.domain.source_history import HistoryEntry, Source
from packages.domain.watering import WateringDiagnostic


class ProjectType:
    """Project type constants (B31-T03)."""
    CAMPANA = "campana"
    NOVELA = "novela"
    OTRO = "otro"


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
    world_layers: list[WorldLayer] = field(default_factory=list)

    # ── Writing units (Bloque 19) ──
    writing_units: list[WritingUnit] = field(default_factory=list)

    # ── Campaign collections (Bloque 20) ──
    campaigns: list[Campaign] = field(default_factory=list)
    player_character_profiles: list[PlayerCharacterProfile] = field(default_factory=list)
    campaign_clocks: list[CampaignClock] = field(default_factory=list)

    # ── Secrets and clues (Bloque 21) ──
    secrets: list[Secreto] = field(default_factory=list)
    clues: list[Pista] = field(default_factory=list)

    # ── Factions and fronts (Bloque 22) ──
    factions: list[Faction] = field(default_factory=list)
    fronts: list[Front] = field(default_factory=list)

    # ── Sessions (Bloque 23) ──
    sessions: list[Session] = field(default_factory=list)

    # ── Saved graph views (Bloque 28) ──
    saved_graph_views: list[dict] = field(default_factory=list)

    # ── Causal milestones (Bloque 41) ──
    causal_milestones: list[CausalMilestone] = field(default_factory=list)

    # Project chronology (H01-H02)
    project_chronology: ProjectChronology = field(default_factory=ProjectChronology)

    # ── Modo Creación Cronológica (CRON) ──
    chronology_walk_sessions: list[ChronologyWalkSession] = field(default_factory=list)
    chronology_walk_reports: list[ChronologyWalkReport] = field(default_factory=list)

    # ── Memoria narrativa viva (BETA2-MEM) ──
    # Estado editorial DERIVADO del canon (resúmenes, contradicciones, huecos,
    # causalidad) por nivel: proyecto/entidad/relación/hito/anillo/rama + contexto.
    # No es canon: la IA nunca lo convierte en canon. Ver docs/contracts/memoria_narrativa.md.
    narrative_memories: list[NarrativeMemory] = field(default_factory=list)

    # ── @menciones estructuradas (BETA2-MEM-03) ──
    # Referencias resueltas (sidecar) derivadas de las @menciones que el usuario
    # escribe en campos de prosa: puntero estable (target_kind, target_id) por id,
    # resistente a renombrado. Alimenta backlinks/impacto/RAG. No es canon.
    structured_references: list[StructuredReference] = field(default_factory=list)

    # ── Jardín narrativo: riego de entidades (BETA2-FOCO) ──
    # Historial de diagnósticos IA por entidad. El "secado" vive a nivel de
    # proyecto (no como campo de entidad) para que los formularios, que
    # reescriben el payload completo de la entidad, no puedan pisarlo.
    watering_diagnostics: list[WateringDiagnostic] = field(default_factory=list)
    watering_paused_entity_ids: list[str] = field(default_factory=list)

    # ── Project type & creative config (B31-T03) ──
    project_type: str = "otro"  # campana, novela, otro
    # PA02: worldbuilding deja de ser opcional — siempre activo. Se conserva el
    # campo (persistencia/compat) pero se fuerza a True al crear y al cargar.
    worldbuilding_active: bool = True
    creative_config: CreativeProjectConfig = field(default_factory=CreativeProjectConfig)

    def touch(self) -> None:
        """Mark the project as updated (bump updated_at).

        BETA1-L01: también incrementa una revisión interna que invalida los
        índices derivados (id→entidad, id→relación, adyacencia). Todas las
        mutaciones de las colecciones pasan por ``touch()``, así que el índice
        se reconstruye perezosamente solo cuando algo cambió.
        """
        self.updated_at = _now_utc()
        self._index_revision = getattr(self, "_index_revision", 0) + 1

    # ------------------------------------------------------------------
    # Índices derivados (BETA1-L01) — caché de SOLO LECTURA, no es una segunda
    # fuente de verdad: las listas ``entities``/``relations`` siguen mandando.
    # Convierten búsquedas O(N) repetidas (get_by_id, vecindario) en O(1).
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        """Construye/revalida los índices si la revisión o el tamaño cambió.

        La revisión (vía ``touch()``) cubre cualquier mutación normal; el respaldo
        por longitud captura un add/remove que excepcionalmente no llamara a
        ``touch()``. Coste O(N) solo cuando hay cambios; gratis entre lecturas."""
        rev = getattr(self, "_index_revision", 0)
        sizes = (len(self.entities), len(self.relations))
        if (
            getattr(self, "_entity_index", None) is not None
            and getattr(self, "_index_built_rev", None) == rev
            and getattr(self, "_index_built_sizes", None) == sizes
        ):
            return
        entity_index: dict[str, NarrativeEntity] = {}
        for entity in self.entities:
            entity_index[entity.id] = entity
        relation_index: dict[str, NarrativeRelation] = {}
        adjacency: dict[str, list[NarrativeRelation]] = {}
        for relation in self.relations:
            relation_index[relation.id] = relation
            adjacency.setdefault(relation.source_id, []).append(relation)
            if relation.target_id != relation.source_id:
                adjacency.setdefault(relation.target_id, []).append(relation)
        self._entity_index = entity_index
        self._relation_index = relation_index
        self._adjacency_index = adjacency
        self._index_built_rev = rev
        self._index_built_sizes = sizes

    def entity_by_id(self, entity_id: str) -> NarrativeEntity | None:
        """Entidad por id en O(1), o ``None`` si no existe."""
        self._ensure_indexes()
        return self._entity_index.get(entity_id)

    def relation_by_id(self, relation_id: str) -> NarrativeRelation | None:
        """Relación por id en O(1), o ``None`` si no existe."""
        self._ensure_indexes()
        return self._relation_index.get(relation_id)

    def relations_for(self, entity_id: str) -> list[NarrativeRelation]:
        """Relaciones donde la entidad participa (origen o destino), en O(1).

        Devuelve una lista nueva (el llamante puede filtrarla sin alterar el
        índice). El orden preserva el de ``relations``."""
        self._ensure_indexes()
        return list(self._adjacency_index.get(entity_id, ()))

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
            # ── Writing units (Bloque 19) ──
            "writing_units": [wu.to_dict() for wu in self.writing_units],
            # ── Campaign collections (Bloque 20) ──
            "campaigns": [c.to_dict() for c in self.campaigns],
            "player_character_profiles": [p.to_dict() for p in self.player_character_profiles],
            "campaign_clocks": [c.to_dict() for c in self.campaign_clocks],
            # ── Secrets and clues (Bloque 21) ──
            "secrets": [s.to_dict() for s in self.secrets],
            "clues": [c.to_dict() for c in self.clues],
            # ── Factions and fronts (Bloque 22) ──
            "factions": [f.to_dict() for f in self.factions],
            "fronts": [f.to_dict() for f in self.fronts],
            # ── Sessions (Bloque 23) ──
            "sessions": [s.to_dict() for s in self.sessions],
            # ── Saved graph views (Bloque 28) ──
            "saved_graph_views": [dict(v) for v in self.saved_graph_views],
            # ── Causal milestones (Bloque 41) ──
            "causal_milestones": [h.to_dict() for h in self.causal_milestones],
            "project_chronology": self.project_chronology.to_dict(),
            "chronology_walk_sessions": [s.to_dict() for s in self.chronology_walk_sessions],
            "chronology_walk_reports": [r.to_dict() for r in self.chronology_walk_reports],
            # ── Memoria narrativa viva (BETA2-MEM) ──
            "narrative_memories": [m.to_dict() for m in self.narrative_memories],
            # ── @menciones estructuradas (BETA2-MEM-03) ──
            "structured_references": [r.to_dict() for r in self.structured_references],
            # ── Jardín narrativo: riego (BETA2-FOCO) ──
            "watering_diagnostics": [d.to_dict() for d in self.watering_diagnostics],
            "watering_paused_entity_ids": list(self.watering_paused_entity_ids),
            # ── Project type & creative config (B31-T03) ──
            "project_type": self.project_type,
            "worldbuilding_active": self.worldbuilding_active,
            "creative_config": self.creative_config.to_dict(),
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
            # Nota: "import_baskets" (subsistema de importación, retirado) ya no se
            # deserializa. Un valor residual en project.json de proyectos antiguos se
            # ignora sin error (lectura selectiva) y se descarta al reguardar.
            # ── Writing units (Bloque 19) ──
            **(
                {"writing_units": [
                    WritingUnit.from_dict(wu)
                    for wu in data.get("writing_units", [])
                    if isinstance(wu, dict)
                ]}
                if "writing_units" in data else {}
            ),
            # ── Campaign collections (Bloque 20) ──
            **(
                {"campaigns": [
                    Campaign.from_dict(c)
                    for c in data.get("campaigns", [])
                    if isinstance(c, dict)
                ]}
                if "campaigns" in data else {}
            ),
            **(
                {"player_character_profiles": [
                    PlayerCharacterProfile.from_dict(p)
                    for p in data.get("player_character_profiles", [])
                    if isinstance(p, dict)
                ]}
                if "player_character_profiles" in data else {}
            ),
            **(
                {"campaign_clocks": [
                    CampaignClock.from_dict(c)
                    for c in data.get("campaign_clocks", [])
                    if isinstance(c, dict)
                ]}
                if "campaign_clocks" in data else {}
            ),
            # ── Secrets and clues (Bloque 21) ──
            **(
                {"secrets": [
                    Secreto.from_dict(s)
                    for s in data.get("secrets", [])
                    if isinstance(s, dict)
                ]}
                if "secrets" in data else {}
            ),
            **(
                {"clues": [
                    Pista.from_dict(c)
                    for c in data.get("clues", [])
                    if isinstance(c, dict)
                ]}
                if "clues" in data else {}
            ),
            # ── Factions and fronts (Bloque 22) ──
            **(
                {"factions": [Faction.from_dict(f) for f in data.get("factions", []) if isinstance(f, dict)]}
                if "factions" in data else {}
            ),
            **(
                {"fronts": [Front.from_dict(f) for f in data.get("fronts", []) if isinstance(f, dict)]}
                if "fronts" in data else {}
            ),
            # ── Sessions (Bloque 23) ──
            **(
                {"sessions": [Session.from_dict(s) for s in data.get("sessions", []) if isinstance(s, dict)]}
                if "sessions" in data else {}
            ),
            # ── Saved graph views (Bloque 28) ──
            **(
                {"saved_graph_views": [dict(v) for v in data.get("saved_graph_views", []) if isinstance(v, dict)]}
                if "saved_graph_views" in data else {}
            ),
            # ── Causal milestones (Bloque 41) ──
            **(
                {"causal_milestones": [
                    CausalMilestone.from_dict(h)
                    for h in data.get("causal_milestones", [])
                    if isinstance(h, dict)
                ]}
                if "causal_milestones" in data else {}
            ),
            **(
                {"project_chronology": ProjectChronology.from_dict(
                    data.get("project_chronology", {})
                )}
                if "project_chronology" in data else {}
            ),
            # ── Modo Creación Cronológica (CRON) ──
            **(
                {"chronology_walk_sessions": [
                    ChronologyWalkSession.from_dict(s)
                    for s in data.get("chronology_walk_sessions", [])
                    if isinstance(s, dict)
                ]}
                if "chronology_walk_sessions" in data else {}
            ),
            **(
                {"chronology_walk_reports": [
                    ChronologyWalkReport.from_dict(r)
                    for r in data.get("chronology_walk_reports", [])
                    if isinstance(r, dict)
                ]}
                if "chronology_walk_reports" in data else {}
            ),
            # ── Memoria narrativa viva (BETA2-MEM) ──
            **(
                {"narrative_memories": [
                    NarrativeMemory.from_dict(m)
                    for m in data.get("narrative_memories", [])
                    if isinstance(m, dict)
                ]}
                if "narrative_memories" in data else {}
            ),
            # ── @menciones estructuradas (BETA2-MEM-03) ──
            **(
                {"structured_references": [
                    StructuredReference.from_dict(r)
                    for r in data.get("structured_references", [])
                    if isinstance(r, dict)
                ]}
                if "structured_references" in data else {}
            ),
            # ── Jardín narrativo: riego (BETA2-FOCO) ──
            **(
                {"watering_diagnostics": [
                    WateringDiagnostic.from_dict(d)
                    for d in data.get("watering_diagnostics", [])
                    if isinstance(d, dict)
                ]}
                if "watering_diagnostics" in data else {}
            ),
            **(
                {"watering_paused_entity_ids": _parse_str_list(data["watering_paused_entity_ids"])}
                if "watering_paused_entity_ids" in data else {}
            ),
            # ── Project type & creative config (B31-T03) ──
            project_type=data.get("project_type", "otro"),
            # PA02: worldbuilding siempre activo (incluido al cargar proyectos viejos).
            worldbuilding_active=True,
            creative_config=CreativeProjectConfig.from_dict(data.get("creative_config", {})),
        )

# ── Helpers ──

def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []
