"""Contextual AI actions for B31-T08.

All actions build context with NarrativeContextBuilder and produce reviewable
candidates/previews. They never mutate canon directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from packages.application.ai_jobs import AIJobService, AIJobType, job_type_for_action
from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider, create_provider
from packages.application.prompt_registry import get_prompt


# BETA1-AI02: the context menu / detail panel are shortcuts into the SAME
# command-bar job pipeline. action_type → AIJobType lives in ai_jobs
# (ACTION_TO_JOB_TYPE / job_type_for_action). Output policy by intent family:
#   - text job types  → inline text (no candidate)
#   - analytical types → report surfaced as a preview (no persisted candidate)
#   - everything else (generative) → staged candidates persisted for review
_TEXT_JOB_TYPES = {AIJobType.IMPROVE_TEXT, AIJobType.GENERATE_TEXT}
_ANALYTICAL_JOB_TYPES = {
    AIJobType.ANALYZE_COHERENCE,
    AIJobType.REVIEW_GRAPH,
    AIJobType.EXPLAIN_FROM_CAUSES,
}


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _context_hash(context: dict[str, Any]) -> str:
    serialized = _json_dumps(context)
    # Deterministic lightweight fingerprint; avoids adding lower-layer forbidden imports.
    acc = 0
    for idx, char in enumerate(serialized, start=1):
        acc = (acc + idx * ord(char)) % 0xFFFFFFFFFFFF
    return f"{acc:012x}{len(serialized) % 0xFFFF:04x}"


def _candidate_type_for(action_type: str, payload: dict[str, Any], fallback: CandidateType = CandidateType.SUGERENCIA_IA) -> str:
    if "relation_type" in payload or {"source_id", "target_id"}.issubset(payload.keys()) or "relations" in action_type:
        return CandidateType.RELACION.value
    if "name" in payload or "entity_type" in payload or "nodes" in action_type:
        return CandidateType.ENTIDAD.value
    if "contrad" in action_type or "detect" in action_type:
        return CandidateType.INCIDENCIA.value
    if "text" in action_type or "description" in payload or "summar" in action_type:
        return CandidateType.CAMBIO.value
    return fallback.value


def _compact_context_summary(context: dict[str, Any]) -> dict[str, Any]:
    project = context.get("project") or {}
    target = context.get("target") or {}
    neighborhood = context.get("neighborhood") or {}
    knowledge = context.get("knowledge") or {}
    return {
        "schema": context.get("schema"),
        "target_type": context.get("target_type"),
        "target_id": context.get("target_id"),
        "audience": context.get("audience"),
        "project_name": project.get("name"),
        "target_name": target.get("name") or target.get("id"),
        "neighbor_relation_count": len(neighborhood.get("relations") or []),
        "neighbor_entity_count": len(neighborhood.get("entities") or []),
        "visible_secret_count": len(knowledge.get("secrets") or []),
        "visible_clue_count": len(knowledge.get("clues") or []),
    }


@dataclass
class AIContextActionResult:
    action_type: str
    target_type: str
    target_id: str | None
    context_hash: str
    raw_text: str
    candidates: list[Candidate]
    previews: list[dict[str, Any]]
    observations: list[str]
    provider: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "context_hash": self.context_hash,
            "raw_text": self.raw_text,
            "candidate_ids": [c.id for c in self.candidates],
            "previews": list(self.previews),
            "observations": list(self.observations),
            "provider": self.provider,
        }



# Prompts migrated to Prompt Registry (B43-T02)
_ENTITY_TEXT_SYSTEM_PROMPT_ES = get_prompt("inline_leaf", lang="es") or ""
_ENTITY_TEXT_SYSTEM_PROMPT_EN = get_prompt("inline_leaf", lang="en") or ""

_RELATION_TEXT_SYSTEM_PROMPT_ES = get_prompt("inline_relation", lang="es") or ""

_RELATION_TEXT_SYSTEM_PROMPT_EN = get_prompt("inline_relation", lang="en") or ""

_COHERENCE_SYSTEM_PROMPT_ES = get_prompt("coherence", lang="es") or ""
_COHERENCE_SYSTEM_PROMPT_EN = get_prompt("coherence", lang="en") or ""

_COHERENCE_REPAIR_SYSTEM_PROMPT_ES = get_prompt("coherence_repair", lang="es") or ""
_COHERENCE_REPAIR_SYSTEM_PROMPT_EN = get_prompt("coherence_repair", lang="en") or ""


def _context_get(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _compact_for_prompt(value: Any, limit: int = 1600) -> str:
    raw = _json_dumps(value) if not isinstance(value, str) else value
    raw = raw.strip()
    return raw if len(raw) <= limit else raw[:limit].rstrip() + "…"


def _legacy_creative(project: dict[str, Any]) -> dict[str, Any]:
    """PA04: vista compat del creative_config nuevo para estos prompts.

    Mapea estilo.estilo_narrativo→narrative_style, reglas.reglas_canon→creative_rules
    y estilo.realismo→realism, para no reescribir cada plantilla bilingüe.
    """
    cc = project.get("creative_config") or {}
    estilo = cc.get("estilo") if isinstance(cc.get("estilo"), dict) else {}
    reglas = cc.get("reglas") if isinstance(cc.get("reglas"), dict) else {}
    return {
        "narrative_style": estilo.get("estilo_narrativo") or "",
        "creative_rules": reglas.get("reglas_canon") or [],
        "realism": estilo.get("realismo") or "",
    }


def _entity_text_user_prompt(context: dict[str, Any], prompt_hint: str, language: str) -> str:
    target = context.get("target") or {}
    project = context.get("project") or {}
    creative = _legacy_creative(project)
    genre = project.get("genre") or {}
    tone = project.get("tone") or {}
    realism = creative["realism"]
    instruction = (prompt_hint or "").strip()
    if language == "en":
        no_instruction = "No extra instruction: improve or complete the existing text coherently."
        return (
            f"Entity name: {target.get('name') or 'Untitled'}\n"
            f"Entity type: {target.get('entity_type') or target.get('type') or 'entity'}\n"
            f"Current brief description:\n{target.get('brief_description') or target.get('description') or '—'}\n\n"
            f"Current body:\n{target.get('extended_description') or target.get('body') or '—'}\n\n"
            f"Notes/context:\n{_compact_for_prompt(target.get('private_notes') or target.get('exportable_notes') or '—', 800)}\n\n"
            f"Project: {project.get('name') or '—'}\n"
            f"Genre: {_compact_for_prompt(genre, 500)}\n"
            f"Tone: {_compact_for_prompt(tone, 500)}\n"
            f"Realism: {_compact_for_prompt(realism, 500)}\n"
            f"Narrative style: {creative.get('narrative_style') or '—'}\n"
            f"Creative rules: {_compact_for_prompt(creative.get('creative_rules') or '—', 800)}\n"
            f"Worldbuilding active: {project.get('worldbuilding_active', False)}\n"
            f"Neighborhood context: {_compact_for_prompt(context.get('neighborhood') or {}, 1200)}\n"
            f"Causal layer context: {_compact_for_prompt(context.get('causal_context') or {}, 1600)}\n\n"
            f"User instruction: {instruction or no_instruction}"
        )
    no_instruction = "Sin instrucción extra: mejora o completa el texto existente con coherencia."
    return (
        f"Nombre de la entidad: {target.get('name') or 'Sin título'}\n"
        f"Tipo de entidad: {target.get('entity_type') or target.get('type') or 'entidad'}\n"
        f"Descripción breve actual:\n{target.get('brief_description') or target.get('description') or '—'}\n\n"
        f"Cuerpo actual:\n{target.get('extended_description') or target.get('body') or '—'}\n\n"
        f"Notas/contexto:\n{_compact_for_prompt(target.get('private_notes') or target.get('exportable_notes') or '—', 800)}\n\n"
        f"Proyecto: {project.get('name') or '—'}\n"
        f"Género: {_compact_for_prompt(genre, 500)}\n"
        f"Tono: {_compact_for_prompt(tone, 500)}\n"
        f"Realismo: {_compact_for_prompt(realism, 500)}\n"
        f"Estilo narrativo: {creative.get('narrative_style') or '—'}\n"
        f"Reglas creativas: {_compact_for_prompt(creative.get('creative_rules') or '—', 800)}\n"
        f"Worldbuilding activo: {project.get('worldbuilding_active', False)}\n"
        f"Contexto de relaciones: {_compact_for_prompt(context.get('neighborhood') or {}, 1200)}\n"
        f"Contexto causal por capas: {_compact_for_prompt(context.get('causal_context') or {}, 1600)}\n\n"
        f"Instrucción del usuario: {instruction or no_instruction}"
    )


def _selection_coherence_user_prompt(context: dict[str, Any], prompt_hint: str, language: str) -> str:
    project = context.get("project") or {}
    selection = context.get("selection") or {}
    creative = _legacy_creative(project)
    instruction = (prompt_hint or "").strip()
    if language == "en":
        return (
            f"Project: {project.get('name') or '—'}\n"
            f"Language: {project.get('primary_language') or 'en'}\n"
            f"Genre: {_compact_for_prompt(project.get('genre') or {}, 700)}\n"
            f"Tone: {_compact_for_prompt(project.get('tone') or {}, 700)}\n"
            f"Realism: {_compact_for_prompt(creative['realism'], 700)}\n"
            f"Style: {creative.get('narrative_style') or '—'}\n"
            f"Selected entities:\n{_compact_for_prompt(selection.get('entities') or [], 5000)}\n\n"
            f"Selected relationships:\n{_compact_for_prompt(selection.get('relations') or [], 5000)}\n\n"
            f"Relevant nearby context:\n{_compact_for_prompt(context.get('nearby_context') or {}, 3000)}\n\n"
            f"Causal layer context:\n{_compact_for_prompt(context.get('causal_context') or {}, 4000)}\n\n"
            f"User instruction: {instruction or 'Analyze joint narrative coherence of the selected subgraph.'}"
        )
    return (
        f"Proyecto: {project.get('name') or '—'}\n"
        f"Idioma: {project.get('primary_language') or 'es'}\n"
        f"Género: {_compact_for_prompt(project.get('genre') or {}, 700)}\n"
        f"Tono: {_compact_for_prompt(project.get('tone') or {}, 700)}\n"
        f"Realismo: {_compact_for_prompt(creative['realism'], 700)}\n"
        f"Estilo: {creative.get('narrative_style') or '—'}\n"
        f"Entidades seleccionadas:\n{_compact_for_prompt(selection.get('entities') or [], 5000)}\n\n"
        f"Relaciones seleccionadas:\n{_compact_for_prompt(selection.get('relations') or [], 5000)}\n\n"
        f"Contexto cercano relevante:\n{_compact_for_prompt(context.get('nearby_context') or {}, 3000)}\n\n"
        f"Contexto causal por capas:\n{_compact_for_prompt(context.get('causal_context') or {}, 4000)}\n\n"
        f"Instrucción del usuario: {instruction or 'Analiza la coherencia narrativa conjunta del subgrafo seleccionado.'}"
    )


def _selection_repair_user_prompt(context: dict[str, Any], proposal: str, prompt_hint: str, language: str) -> str:
    base = _selection_coherence_user_prompt(context, prompt_hint, language)
    if language == "en":
        return base + "\n\nChosen repair proposal:\n" + (proposal or "Rewrite with current canon.")
    return base + "\n\nPropuesta de reparación elegida:\n" + (proposal or "Reescribir con canon actual.")


def _relation_text_user_prompt(context: dict[str, Any], prompt_hint: str, language: str) -> str:
    target = context.get("target") or {}
    project = context.get("project") or {}
    creative = _legacy_creative(project)
    genre = project.get("genre") or {}
    tone = project.get("tone") or {}
    realism = creative["realism"]
    instruction = (prompt_hint or "").strip()

    source = target.get("source") or {}
    target_node = target.get("target_node") or target.get("target") or {}
    source_full = target.get("source_full") or source
    target_full = target.get("target_full") or target_node
    narrative_style = creative.get("narrative_style") or "—"
    creative_rules = creative.get("creative_rules") or "—"

    if language == "en":
        no_instruction = "No extra instruction: improve or complete the existing text coherently."
        parts = [
            f"Source entity: {_compact_for_prompt(source_full, 1200)}",
            f"Target entity: {_compact_for_prompt(target_full, 1200)}",
            f"Relation type: {target.get('relation_type') or target.get('type') or '—'}",
            f"Direction: {target.get('direction') or '—'}",
            f"Current description:\n{_compact_for_prompt(target.get('description') or '—', 800)}",
        ]
        body = target.get("body") or target.get("extended_description")
        if body:
            parts.append(f"Current body:\n{_compact_for_prompt(body, 1200)}")
        temporality = target.get("temporality") or target.get("temporal_context")
        if temporality:
            parts.append(f"Temporality: {temporality}")
        causality = target.get("causality")
        if causality:
            parts.append(f"Causality: {causality}")
        notes = target.get("notes") or target.get("private_notes") or target.get("exportable_notes")
        if notes:
            parts.append(f"Notes:\n{_compact_for_prompt(notes, 800)}")
        parts += [
            f"Project: {project.get('name') or '—'}",
            f"Language: {project.get('primary_language') or 'en'}",
            f"Genre: {_compact_for_prompt(genre, 500)}",
            f"Tone: {_compact_for_prompt(tone, 500)}",
            f"Realism: {_compact_for_prompt(realism, 500)}",
            f"Narrative style: {narrative_style}",
            f"Creative rules: {_compact_for_prompt(creative_rules, 800)}",
            f"Worldbuilding active: {project.get('worldbuilding_active', False)}",
            f"Neighborhood context: {_compact_for_prompt(context.get('neighborhood') or {}, 1200)}",
            f"User instruction: {instruction or no_instruction}",
        ]
        return "\n".join(parts)

    no_instruction = "Sin instrucción extra: mejora o completa el texto existente con coherencia."
    parts = [
        f"Entidad origen: {_compact_for_prompt(source_full, 1200)}",
        f"Entidad destino: {_compact_for_prompt(target_full, 1200)}",
        f"Tipo de relación: {target.get('relation_type') or target.get('type') or '—'}",
        f"Dirección: {target.get('direction') or '—'}",
        f"Descripción actual:\n{_compact_for_prompt(target.get('description') or '—', 800)}",
    ]
    body = target.get("body") or target.get("extended_description")
    if body:
        parts.append(f"Cuerpo actual:\n{_compact_for_prompt(body, 1200)}")
    temporality = target.get("temporality") or target.get("temporal_context")
    if temporality:
        parts.append(f"Temporalidad: {temporality}")
    causality = target.get("causality")
    if causality:
        parts.append(f"Causalidad: {causality}")
    notes = target.get("notes") or target.get("private_notes") or target.get("exportable_notes")
    if notes:
        parts.append(f"Notas:\n{_compact_for_prompt(notes, 800)}")
    parts += [
        f"Proyecto: {project.get('name') or '—'}",
        f"Idioma: {project.get('primary_language') or 'es'}",
        f"Género: {_compact_for_prompt(genre, 500)}",
        f"Tono: {_compact_for_prompt(tone, 500)}",
        f"Realismo: {_compact_for_prompt(realism, 500)}",
        f"Estilo narrativo: {narrative_style}",
        f"Reglas creativas: {_compact_for_prompt(creative_rules, 800)}",
        f"Worldbuilding activo: {project.get('worldbuilding_active', False)}",
        f"Contexto de relaciones: {_compact_for_prompt(context.get('neighborhood') or {}, 1200)}",
        f"Instrucción del usuario: {instruction or no_instruction}",
    ]
    return "\n".join(parts)


class AIContextActionService:
    """Runs contextual AI actions and records reviewable candidates."""

    def __init__(
        self,
        project_service: Any,
        candidate_service: Any,
        provider: AIProvider | None = None,
        provider_name: str = "simulated",
        allow_simulated: bool = False,
        ai_job_service: AIJobService | None = None,
    ):
        self.project_service = project_service
        self.candidate_service = candidate_service
        self.context_builder = NarrativeContextBuilder(project_service)
        # Every contextual action is a focused job through the shared command-bar
        # pipeline (gateway → provider.chat). When the host injects its command-bar
        # AIJobService, context-menu/panel jobs land in the SAME registry and show
        # up in the unified jobs tray; otherwise we own a private service.
        if ai_job_service is not None:
            self._jobs = ai_job_service
            self.provider = ai_job_service.provider
            self.allow_simulated = ai_job_service.allow_simulated
        else:
            self.provider = provider or create_provider(provider_name)
            self.allow_simulated = allow_simulated
            self._jobs = AIJobService(
                provider=self.provider,
                allow_simulated=allow_simulated,
                project_provider=lambda: getattr(self.project_service, "active_project", None),
            )

    def _provider_unconfigured_error(self) -> Error | None:
        provider_name = str(getattr(self.provider, "provider_name", "ai"))
        if provider_name == "simulated" and not self.allow_simulated:
            return Error("IA no configurada: configura un proveedor real para usar acciones IA.")
        return None

    def run_node_action(self, entity_id: str, action_type: str, *, prompt_hint: str = "", audience: str = "gm", language: str = "es") -> Result[AIContextActionResult, str]:
        job_type = job_type_for_action(action_type)
        if job_type == AIJobType.UNKNOWN:
            return Error(f"Unknown node AI action: {action_type}")
        context = self.context_builder.build_for_entity(entity_id, audience=audience)
        return self._run_focused(
            action_type=action_type, target_type="node", target_id=entity_id,
            job_type=job_type, context=context, prompt_hint=prompt_hint, language=language,
        )

    def run_node_text_suggestion(
        self,
        entity_id: str,
        *,
        prompt_hint: str = "",
        audience: str = "gm",
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        """Return a text-only inline suggestion for an entity.

        Runs an IMPROVE_TEXT focused job: it returns free text, never stages a
        candidate. The suggestion stays local UI text until the user accepts it
        and saves the entity through EntityService.
        """
        context = self.context_builder.build_for_entity(entity_id, audience=audience)
        lang = "en" if str(language).lower().startswith("en") else "es"
        prompt = _entity_text_user_prompt(context, prompt_hint, lang)
        return self._run_focused(
            action_type="improve_text", target_type="node", target_id=entity_id,
            job_type=AIJobType.IMPROVE_TEXT, context=context, prompt_hint=prompt,
            language=lang, raw_prompt=True,
            empty_error="La IA no devolvió una sugerencia de texto.",
        )

    def run_relation_text_suggestion(
        self,
        relation_id: str,
        *,
        prompt_hint: str = "",
        audience: str = "gm",
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        """Text-only inline suggestion for a relation (IMPROVE_TEXT focused job)."""
        context = self.context_builder.build_for_relation(relation_id, audience=audience)
        lang = "en" if str(language).lower().startswith("en") else "es"
        prompt = _relation_text_user_prompt(context, prompt_hint, lang)
        return self._run_focused(
            action_type="improve_relation_text", target_type="relation", target_id=relation_id,
            job_type=AIJobType.IMPROVE_TEXT, context=context, prompt_hint=prompt,
            language=lang, raw_prompt=True,
            empty_error="La IA no devolvió una sugerencia de texto.",
        )

    def run_selection_coherence_analysis(
        self,
        *,
        entity_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
        prompt_hint: str = "",
        audience: str = "gm",
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        """Analyze joint coherence for a selected subgraph without mutating canon."""
        if not (entity_ids or relation_ids):
            return Error("Selecciona al menos un nodo o una relación para analizar coherencia.")
        context = self.context_builder.build_for_graph_selection(entity_ids=entity_ids or [], relation_ids=relation_ids or [], audience=audience)
        selection = context.get("selection") or {}
        if not (selection.get("entities") or selection.get("relations")):
            return Error("La selección no contiene elementos visibles para analizar.")
        lang = "en" if str(language).lower().startswith("en") else "es"
        prompt = _selection_coherence_user_prompt(context, prompt_hint, lang)
        return self._run_focused(
            action_type="analyze_coherence", target_type="graph_selection", target_id=None,
            job_type=AIJobType.GENERATE_TEXT, context=context, prompt_hint=prompt, language=lang,
            raw_prompt=True, entity_ids=entity_ids, relation_ids=relation_ids,
            empty_error="La IA no devolvió un informe de coherencia.",
        )

    def run_selection_coherence_repair(
        self,
        *,
        entity_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
        proposal: str = "",
        prompt_hint: str = "",
        audience: str = "gm",
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        """Generate a reviewable repair patch for selected elements; no automatic apply."""
        if not (entity_ids or relation_ids):
            return Error("Selecciona elementos antes de generar una reparación.")
        context = self.context_builder.build_for_graph_selection(entity_ids=entity_ids or [], relation_ids=relation_ids or [], audience=audience)
        lang = "en" if str(language).lower().startswith("en") else "es"
        prompt = _selection_repair_user_prompt(context, proposal, prompt_hint, lang)
        return self._run_focused(
            action_type="repair_coherence", target_type="graph_selection", target_id=None,
            job_type=AIJobType.GENERATE_TEXT, context=context, prompt_hint=prompt, language=lang,
            raw_prompt=True, entity_ids=entity_ids, relation_ids=relation_ids,
            empty_error="La IA no devolvió una reparación.",
        )

    def run_relation_action(self, relation_id: str, action_type: str, *, prompt_hint: str = "", audience: str = "gm", language: str = "es") -> Result[AIContextActionResult, str]:
        # On a relation, "create_candidate" means propose a relation, not an entity.
        job_type = AIJobType.SUGGEST_RELATIONS if action_type == "create_candidate" else job_type_for_action(action_type)
        if job_type == AIJobType.UNKNOWN:
            return Error(f"Unknown relation AI action: {action_type}")
        context = self.context_builder.build_for_relation(relation_id, audience=audience)
        return self._run_focused(
            action_type=action_type, target_type="relation", target_id=relation_id,
            job_type=job_type, context=context, prompt_hint=prompt_hint, language=language,
        )

    def run_graph_action(
        self,
        action_type: str,
        *,
        entity_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
        prompt_hint: str = "",
        audience: str = "gm",
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        job_type = job_type_for_action(action_type)
        if job_type == AIJobType.UNKNOWN:
            return Error(f"Unknown graph AI action: {action_type}")
        context = self.context_builder.build_for_graph_selection(entity_ids=entity_ids or [], relation_ids=relation_ids or [], audience=audience)
        return self._run_focused(
            action_type=action_type, target_type="graph", target_id=None,
            job_type=job_type, context=context, prompt_hint=prompt_hint, language=language,
            entity_ids=entity_ids, relation_ids=relation_ids,
        )

    def _seed_context_scope(self, context: dict[str, Any], *, target_type: str, target_id: str | None, language: str, entity_ids=None, relation_ids=None) -> dict[str, Any]:
        """Build the focused context_scope the command-bar pipeline consumes."""
        selected_entities = list(entity_ids or ([target_id] if target_type == "node" and target_id else []))
        selected_relations = list(relation_ids or ([target_id] if target_type == "relation" and target_id else []))
        return {
            "authorized_context": context,
            "selected_entity_ids": selected_entities,
            "selected_relation_ids": selected_relations,
            "focus_entity_id": target_id if target_type == "node" else None,
            "focus_relation_id": target_id if target_type == "relation" else None,
            "audience": context.get("audience", "gm"),
            "language": language,
            "context_summary": _compact_context_summary(context),
        }

    def _run_focused(
        self,
        *,
        action_type: str,
        target_type: str,
        target_id: str | None,
        job_type: AIJobType,
        context: dict[str, Any],
        prompt_hint: str,
        language: str = "es",
        raw_prompt: bool = False,
        entity_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
        empty_error: str = "La IA no devolvió contenido.",
    ) -> Result[AIContextActionResult, str]:
        """Run a focused job through the shared command-bar pipeline.

        Output policy: text intents → inline text; analytical intents → report
        surfaced as a preview; generative intents → staged candidates persisted
        via CandidateService (preserving the menu's immediate-review behaviour).
        """
        unavailable = self._provider_unconfigured_error()
        if unavailable:
            return unavailable
        if context.get("target") == {"redacted": True, "reason": "not_visible_for_audience"}:
            return Error("Target not visible for requested audience")
        context_hash = _context_hash(context)
        scope = self._seed_context_scope(
            context, target_type=target_type, target_id=target_id, language=language,
            entity_ids=entity_ids, relation_ids=relation_ids,
        )
        if raw_prompt:
            prompt = prompt_hint
            # M6: en jobs raw_prompt (menú/panel) el target ya viaja embebido en
            # el prompt; reducir authorized_context a un resumen compacto evita
            # duplicar la entidad completa en el mensaje.
            scope["authorized_context"] = _compact_context_summary(context)
        else:
            prompt = (prompt_hint or "").strip() or (
                f"Acción '{action_type}' sobre la selección. Genera resultados "
                "revisables usando el contexto autorizado."
            )
        result = self._jobs.run_focused_job(job_type, prompt, context_scope=scope)
        if isinstance(result, Error):
            return result
        res = result.value.result or {}
        provider = str(res.get("provider") or getattr(self.provider, "provider_name", "ai"))
        open_questions = list(res.get("open_questions") or [])
        selection_payload = {
            "selected_entity_ids": list(scope.get("selected_entity_ids") or []),
            "selected_relation_ids": list(scope.get("selected_relation_ids") or []),
        }

        if job_type in _TEXT_JOB_TYPES:
            body = (res.get("text") or "").strip()
            if not body:
                return Error(empty_error)
            return Ok(AIContextActionResult(
                action_type=action_type, target_type=target_type, target_id=target_id,
                context_hash=context_hash, raw_text=body, candidates=[],
                previews=[self._preview_payload(action_type, target_type, target_id, selection_payload, body, context_hash)],
                observations=[], provider=provider,
            ))

        if job_type in _ANALYTICAL_JOB_TYPES:
            body = (res.get("report") or res.get("summary") or "").strip()
            return Ok(AIContextActionResult(
                action_type=action_type, target_type=target_type, target_id=target_id,
                context_hash=context_hash, raw_text=body, candidates=[],
                previews=[self._preview_payload(action_type, target_type, target_id, selection_payload, body, context_hash)],
                observations=open_questions, provider=provider,
            ))

        # Generative intents: persist staged candidates for review.
        candidates: list[Candidate] = []
        for staged in res.get("candidates") or []:
            if not isinstance(staged, dict):
                continue
            created = self._persist_candidate(
                staged, action_type=action_type, target_type=target_type,
                target_id=target_id, context=context, context_hash=context_hash, provider=provider,
            )
            if isinstance(created, Error):
                return created
            candidates.append(created.value)
        report = str(res.get("report") or "")
        previews: list[dict[str, Any]] = []
        if not candidates and (report or open_questions):
            previews.append(self._preview_payload(action_type, target_type, target_id, selection_payload, report, context_hash))
        return Ok(AIContextActionResult(
            action_type=action_type, target_type=target_type, target_id=target_id,
            context_hash=context_hash, raw_text=report, candidates=candidates,
            previews=previews, observations=open_questions, provider=provider,
        ))

    def _persist_candidate(
        self,
        staged: dict[str, Any],
        *,
        action_type: str,
        target_type: str,
        target_id: str | None,
        context: dict[str, Any],
        context_hash: str,
        provider: str,
    ) -> Result[Candidate, str]:
        data = dict(staged)
        metadata = dict(data.get("metadata") or {})
        metadata.update({
            "origin": "AIContextActionService",
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "context_hash": context_hash,
            "context_summary": _compact_context_summary(context),
            "provider": provider,
            "canonical_status": "candidate_non_canon",
        })
        data["metadata"] = metadata
        proposed = dict(data.get("proposed_data") or {})
        proposed.setdefault("canonical_status", "candidate_non_canon")
        proposed.setdefault("facts_status", "proposal_only_not_confirmed")
        data["proposed_data"] = proposed
        data["source"] = "ia"
        data.setdefault("affected_entity_ids", [target_id] if target_type == "node" and target_id else [])
        data.setdefault("affected_relation_ids", [target_id] if target_type == "relation" and target_id else [])
        return self.candidate_service.create_candidate(data)

    def _preview_payload(self, action_type: str, target_type: str, target_id: str | None, payload: dict[str, Any], raw_text: str, context_hash: str) -> dict[str, Any]:
        return {
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "context_hash": context_hash,
            "raw_text": raw_text,
            "payload": payload,
            "canonical_status": "preview_non_canon",
        }


__all__ = ["AIContextActionResult", "AIContextActionService"]
