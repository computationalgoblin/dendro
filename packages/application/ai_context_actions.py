"""Contextual AI actions for B31-T08.

All actions build context with NarrativeContextBuilder and produce reviewable
candidates/previews. They never mutate canon directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.domain.ai_models import AIMode, AIOperation, AuthorizedContext
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider, create_provider


_NODE_ACTIONS: dict[str, AIMode] = {
    "generate_text": AIMode.EXPAND_ENTITY,
    "improve_text": AIMode.REWRITE_DESCRIPTION,
    "suggest_relations": AIMode.SUGGEST_RELATIONS,
    "suggest_conflict": AIMode.CRITICAL_ANALYSIS,
    "suggest_secrets": AIMode.CONTINUITY_QUESTION,
    "suggest_clues": AIMode.CONTINUITY_QUESTION,
    "detect_contradictions": AIMode.CONSISTENCY_ANALYSIS,
    "summarize": AIMode.SUMMARIZE,
    "create_candidate": AIMode.GENERATE_ENTITY,
}
_RELATION_ACTIONS: dict[str, AIMode] = {
    "deepen": AIMode.EXPAND_ENTITY,
    "suggest_evolution": AIMode.CONTINUITY_QUESTION,
    "suggest_scene": AIMode.GENERATE_ENTITY,
    "detect_contradiction": AIMode.CONSISTENCY_ANALYSIS,
    "suggest_secret_clue": AIMode.CONTINUITY_QUESTION,
    "create_candidate": AIMode.GENERATE_RELATION,
}
_GRAPH_ACTIONS: dict[str, AIMode] = {
    "suggest_missing_nodes": AIMode.GENERATE_ENTITY,
    "suggest_missing_relations": AIMode.SUGGEST_RELATIONS,
    "detect_isolated_zones": AIMode.CRITICAL_ANALYSIS,
    "detect_inconsistencies": AIMode.CONSISTENCY_ANALYSIS,
    "suggest_emergent_plots": AIMode.CONTINUITY_QUESTION,
    "describe_tree": AIMode.SUMMARIZE,
}
_PREVIEW_ACTIONS = {"summarize", "detect_contradictions", "detect_contradiction", "detect_isolated_zones", "detect_inconsistencies"}


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


def _authorized_context(context: dict[str, Any]) -> AuthorizedContext:
    project = context.get("project") or {}
    target_type = context.get("target_type")
    target_id = context.get("target_id")
    selected_entities = [target_id] if target_type == "entity" and target_id else []
    selected_relations = [target_id] if target_type == "relation" and target_id else []
    neighborhood = context.get("neighborhood") or {}
    entities = []
    target = context.get("target")
    if isinstance(target, dict) and target.get("id") and target_type == "entity":
        entities.append(target)
    entities.extend(neighborhood.get("entities") or [])
    relations = []
    if isinstance(target, dict) and target.get("id") and target_type == "relation":
        relations.append(target)
    relations.extend(neighborhood.get("relations") or [])
    return AuthorizedContext(
        project_name=project.get("name", ""),
        selected_entity_ids=selected_entities,
        selected_relation_ids=selected_relations,
        audience=context.get("audience", "gm"),
        project_config_snapshot={
            "tone": project.get("tone", {}),
            "genre": project.get("genre", {}),
            "realism": project.get("realism", {}),
            "constraints": context.get("constraints", {}),
            "context_hash": _context_hash(context),
        },
        context_entities=entities,
        context_relations=relations,
        context_history=context.get("history") or [],
        context_issues=context.get("issues") or [],
    )


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



_ENTITY_TEXT_SYSTEM_PROMPT_ES = (
    "Eres un asistente de escritura integrado en Dendro. Tu tarea es mejorar o completar "
    "el contenido textual de la entidad seleccionada. Usa el nombre, tipo, descripción, "
    "cuerpo actual, notas y contexto del proyecto. Respeta el género, tono, realismo, "
    "estilo narrativo e idioma configurados. Sigue especialmente la instrucción opcional "
    "del usuario si existe. Devuelve únicamente el texto sugerido para incorporar al cuerpo "
    "o descripción de la entidad. No devuelvas JSON. No devuelvas una ficha Entity/Name/Type. "
    "No crees entidades, relaciones, secretos ni canon nuevo salvo que el usuario lo pida "
    "explícitamente. No modifiques el proyecto. Responde en español."
)

_ENTITY_TEXT_SYSTEM_PROMPT_EN = (
    "You are a writing assistant integrated into Dendro. Your task is to improve or complete "
    "the textual content of the selected entity. Use the name, type, current description, "
    "current body, notes, and project context. Respect the configured genre, tone, realism, "
    "narrative style, and language. Follow the optional user instruction especially when it "
    "exists. Return only the suggested text to incorporate into the entity body or description. "
    "Do not return JSON. Do not return an Entity/Name/Type sheet. Do not create entities, "
    "relationships, secrets, or new canon unless the user explicitly asks for it. Do not modify "
    "the project. Respond in English."
)

_RELATION_TEXT_SYSTEM_PROMPT_ES = (
    "Eres un asistente de escritura integrado en Dendro. Tu tarea es mejorar o completar "
    "el contenido textual de una relación narrativa entre dos entidades. Usa el origen, "
    "destino, tipo de relación, dirección, descripción, cuerpo, notas y contexto creativo "
    "del proyecto. Respeta idioma, género, tono, realismo y estilo narrativo. Sigue "
    "especialmente la instrucción opcional del usuario si existe. Devuelve únicamente el "
    "texto sugerido para la relación. No devuelvas JSON. No devuelvas una ficha técnica. "
    "No crees entidades, relaciones, árboles, secretos ni canon nuevo. No modifiques el proyecto."
)

_RELATION_TEXT_SYSTEM_PROMPT_EN = (
    "You are a writing assistant integrated into Dendro. Your task is to improve or complete "
    "the textual content of a narrative relationship between two entities. Use source, target, "
    "relationship type, direction, current description, body, notes, and project creative context. "
    "Respect language, genre, tone, realism, and narrative style. Follow the optional user "
    "instruction especially when it exists. Return only the suggested text for the relationship. "
    "Do not return JSON. Do not return a technical sheet. Do not create entities, relationships, "
    "trees, secrets, or new canon. Do not modify the project."
)

_COHERENCE_SYSTEM_PROMPT_ES = (
    "Eres un editor de coherencia narrativa integrado en Dendro. Tu tarea es analizar si un "
    "conjunto de entidades y relaciones encaja con el canon existente, la motivación de los "
    "personajes y la configuración creativa del proyecto. No debes modificar contenido durante "
    "el análisis. No debes crear entidades ni relaciones. Devuelve observaciones claras y "
    "propuestas de reparación. Respeta el idioma configurado. Prioriza coherencia causal, "
    "motivacional, tonal y dramática. Estructura la respuesta con secciones: Veredicto global, "
    "Observaciones por entidad, Observaciones por relación, Contradicciones, Huecos de motivación, "
    "Continuidad, Riesgos tonales, Oportunidades dramáticas, Propuestas de reparación y Preguntas abiertas."
)

_COHERENCE_SYSTEM_PROMPT_EN = (
    "You are a narrative coherence editor integrated into Dendro. Analyze whether a selected set "
    "of entities and relationships fits the existing canon, character motivation, and project "
    "creative configuration. Do not modify content during analysis. Do not create entities or "
    "relationships. Return clear observations and repair proposals. Prioritize causal, motivational, "
    "tonal, and dramatic coherence. Structure the response with sections: Global verdict, Entity "
    "observations, Relationship observations, Contradictions, Motivation gaps, Continuity, Tonal "
    "risks, Dramatic opportunities, Repair proposals, and Open questions."
)

_COHERENCE_REPAIR_SYSTEM_PROMPT_ES = (
    "Eres un editor de coherencia narrativa integrado en Dendro. Genera una reparación aplicable "
    "solo a los nodos y relaciones seleccionados. No crees entidades ni relaciones. Devuelve primero "
    "un resumen narrativo breve y después un bloque JSON estricto entre <PATCH_JSON> y </PATCH_JSON>. "
    "El JSON debe tener: {\"entities\":[{\"id\":...,\"brief_description\":...,\"extended_description\":...}], "
    "\"relations\":[{\"id\":...,\"description\":...,\"body\":...}]}. Incluye solo campos que deban cambiar."
)

_COHERENCE_REPAIR_SYSTEM_PROMPT_EN = (
    "You are a narrative coherence editor integrated into Dendro. Generate an applicable repair "
    "only for selected nodes and relationships. Do not create entities or relationships. Return a "
    "brief narrative summary first, then a strict JSON block between <PATCH_JSON> and </PATCH_JSON>. "
    "The JSON must have: {\"entities\":[{\"id\":...,\"brief_description\":...,\"extended_description\":...}], "
    "\"relations\":[{\"id\":...,\"description\":...,\"body\":...}]}. Include only fields that should change."
)


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


def _entity_text_user_prompt(context: dict[str, Any], prompt_hint: str, language: str) -> str:
    target = context.get("target") or {}
    project = context.get("project") or {}
    creative = project.get("creative_config") or project.get("creative_project_config") or {}
    genre = project.get("genre") or {}
    tone = project.get("tone") or {}
    realism = project.get("realism") or {}
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
            f"Neighborhood context: {_compact_for_prompt(context.get('neighborhood') or {}, 1200)}\n\n"
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
        f"Contexto de relaciones: {_compact_for_prompt(context.get('neighborhood') or {}, 1200)}\n\n"
        f"Instrucción del usuario: {instruction or no_instruction}"
    )


def _selection_coherence_user_prompt(context: dict[str, Any], prompt_hint: str, language: str) -> str:
    project = context.get("project") or {}
    selection = context.get("selection") or {}
    creative = project.get("creative_config") or project.get("creative_project_config") or {}
    instruction = (prompt_hint or "").strip()
    if language == "en":
        return (
            f"Project: {project.get('name') or '—'}\n"
            f"Language: {project.get('primary_language') or 'en'}\n"
            f"Genre: {_compact_for_prompt(project.get('genre') or {}, 700)}\n"
            f"Tone: {_compact_for_prompt(project.get('tone') or {}, 700)}\n"
            f"Realism: {_compact_for_prompt(project.get('realism') or {}, 700)}\n"
            f"Style: {creative.get('narrative_style') or '—'}\n"
            f"Selected entities:\n{_compact_for_prompt(selection.get('entities') or [], 5000)}\n\n"
            f"Selected relationships:\n{_compact_for_prompt(selection.get('relations') or [], 5000)}\n\n"
            f"Relevant nearby context:\n{_compact_for_prompt(context.get('nearby_context') or {}, 3000)}\n\n"
            f"User instruction: {instruction or 'Analyze joint narrative coherence of the selected subgraph.'}"
        )
    return (
        f"Proyecto: {project.get('name') or '—'}\n"
        f"Idioma: {project.get('primary_language') or 'es'}\n"
        f"Género: {_compact_for_prompt(project.get('genre') or {}, 700)}\n"
        f"Tono: {_compact_for_prompt(project.get('tone') or {}, 700)}\n"
        f"Realismo: {_compact_for_prompt(project.get('realism') or {}, 700)}\n"
        f"Estilo: {creative.get('narrative_style') or '—'}\n"
        f"Entidades seleccionadas:\n{_compact_for_prompt(selection.get('entities') or [], 5000)}\n\n"
        f"Relaciones seleccionadas:\n{_compact_for_prompt(selection.get('relations') or [], 5000)}\n\n"
        f"Contexto cercano relevante:\n{_compact_for_prompt(context.get('nearby_context') or {}, 3000)}\n\n"
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
    creative = project.get("creative_config") or project.get("creative_project_config") or {}
    genre = project.get("genre") or {}
    tone = project.get("tone") or {}
    realism = project.get("realism") or {}
    instruction = (prompt_hint or "").strip()

    source = target.get("source") or {}
    target_node = target.get("target_node") or target.get("target") or {}
    source_full = target.get("source_full") or source
    target_full = target.get("target_full") or target_node
    narrative_style = creative.get("narrative_style") or project.get("narrative_style") or "—"
    creative_rules = creative.get("creative_rules") or project.get("creative_rules") or "—"

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
    ):
        self.project_service = project_service
        self.candidate_service = candidate_service
        self.context_builder = NarrativeContextBuilder(project_service)
        self.provider = provider or create_provider(provider_name)

    def run_node_action(self, entity_id: str, action_type: str, *, prompt_hint: str = "", audience: str = "gm") -> Result[AIContextActionResult, str]:
        mode = _NODE_ACTIONS.get(action_type)
        if mode is None:
            return Error(f"Unknown node AI action: {action_type}")
        context = self.context_builder.build_for_entity(entity_id, audience=audience)
        return self._run("node", entity_id, action_type, mode, context, prompt_hint)

    def run_node_text_suggestion(
        self,
        entity_id: str,
        *,
        prompt_hint: str = "",
        audience: str = "gm",
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        """Return a text-only inline suggestion for an entity.

        This path is deliberately NOT routed through generate_candidates() and
        never calls CandidateService. It is for the entity detail panel only:
        the suggestion remains local UI text until the user accepts it and then
        saves the entity through EntityService.
        """
        context = self.context_builder.build_for_entity(entity_id, audience=audience)
        if context.get("target") == {"redacted": True, "reason": "not_visible_for_audience"}:
            return Error("Target not visible for requested audience")
        context_hash = _context_hash(context)
        lang = "en" if str(language).lower().startswith("en") else "es"
        system_prompt = _ENTITY_TEXT_SYSTEM_PROMPT_EN if lang == "en" else _ENTITY_TEXT_SYSTEM_PROMPT_ES
        user_prompt = _entity_text_user_prompt(context, prompt_hint, lang)
        try:
            text, error = self.provider.chat(system_prompt, user_prompt)
        except Exception as exc:
            return Error(f"Provider error: {exc}")
        if error:
            return Error(str(error))
        cleaned = (text or "").strip()
        if not cleaned:
            return Error("La IA no devolvió una sugerencia de texto.")
        return Ok(AIContextActionResult(
            action_type="improve_text",
            target_type="node",
            target_id=entity_id,
            context_hash=context_hash,
            raw_text=cleaned,
            candidates=[],
            previews=[self._preview_payload("improve_text", "node", entity_id, {}, cleaned, context_hash)],
            observations=[],
            provider=getattr(self.provider, "provider_name", "ai"),
        ))

    def run_relation_text_suggestion(
        self,
        relation_id: str,
        *,
        prompt_hint: str = "",
        audience: str = "gm",
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        """Return a text-only inline suggestion for a relation."""
        context = self.context_builder.build_for_relation(relation_id, audience=audience)
        if context.get("target") == {"redacted": True, "reason": "not_visible_for_audience"}:
            return Error("Target not visible for requested audience")
        context_hash = _context_hash(context)
        lang = "en" if str(language).lower().startswith("en") else "es"
        system_prompt = _RELATION_TEXT_SYSTEM_PROMPT_EN if lang == "en" else _RELATION_TEXT_SYSTEM_PROMPT_ES
        user_prompt = _relation_text_user_prompt(context, prompt_hint, lang)
        try:
            text, error = self.provider.chat(system_prompt, user_prompt)
        except Exception as exc:
            return Error(f"Provider error: {exc}")
        if error:
            return Error(str(error))
        cleaned = (text or "").strip()
        if not cleaned:
            return Error("La IA no devolvió una sugerencia de texto.")
        return Ok(AIContextActionResult(
            action_type="improve_relation_text",
            target_type="relation",
            target_id=relation_id,
            context_hash=context_hash,
            raw_text=cleaned,
            candidates=[],
            previews=[self._preview_payload("improve_relation_text", "relation", relation_id, {}, cleaned, context_hash)],
            observations=[],
            provider=getattr(self.provider, "provider_name", "ai"),
        ))

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
        context_hash = _context_hash(context)
        lang = "en" if str(language).lower().startswith("en") else "es"
        system_prompt = _COHERENCE_SYSTEM_PROMPT_EN if lang == "en" else _COHERENCE_SYSTEM_PROMPT_ES
        user_prompt = _selection_coherence_user_prompt(context, prompt_hint, lang)
        try:
            text, error = self.provider.chat(system_prompt, user_prompt)
        except Exception as exc:
            return Error(f"Provider error: {exc}")
        if error:
            return Error(str(error))
        cleaned = (text or "").strip()
        if not cleaned:
            return Error("La IA no devolvió un informe de coherencia.")
        return Ok(AIContextActionResult(
            action_type="analyze_coherence",
            target_type="graph_selection",
            target_id=None,
            context_hash=context_hash,
            raw_text=cleaned,
            candidates=[],
            previews=[self._preview_payload("analyze_coherence", "graph_selection", None, {
                "selected_entity_ids": list(entity_ids or []),
                "selected_relation_ids": list(relation_ids or []),
                "selection_summary": _compact_context_summary(context),
            }, cleaned, context_hash)],
            observations=[],
            provider=getattr(self.provider, "provider_name", "ai"),
        ))

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
        context_hash = _context_hash(context)
        lang = "en" if str(language).lower().startswith("en") else "es"
        system_prompt = _COHERENCE_REPAIR_SYSTEM_PROMPT_EN if lang == "en" else _COHERENCE_REPAIR_SYSTEM_PROMPT_ES
        user_prompt = _selection_repair_user_prompt(context, proposal, prompt_hint, lang)
        try:
            text, error = self.provider.chat(system_prompt, user_prompt)
        except Exception as exc:
            return Error(f"Provider error: {exc}")
        if error:
            return Error(str(error))
        cleaned = (text or "").strip()
        if not cleaned:
            return Error("La IA no devolvió una reparación.")
        return Ok(AIContextActionResult(
            action_type="repair_coherence",
            target_type="graph_selection",
            target_id=None,
            context_hash=context_hash,
            raw_text=cleaned,
            candidates=[],
            previews=[self._preview_payload("repair_coherence", "graph_selection", None, {
                "selected_entity_ids": list(entity_ids or []),
                "selected_relation_ids": list(relation_ids or []),
                "proposal": proposal,
            }, cleaned, context_hash)],
            observations=[],
            provider=getattr(self.provider, "provider_name", "ai"),
        ))

    def run_relation_action(self, relation_id: str, action_type: str, *, prompt_hint: str = "", audience: str = "gm") -> Result[AIContextActionResult, str]:
        mode = _RELATION_ACTIONS.get(action_type)
        if mode is None:
            return Error(f"Unknown relation AI action: {action_type}")
        context = self.context_builder.build_for_relation(relation_id, audience=audience)
        return self._run("relation", relation_id, action_type, mode, context, prompt_hint)

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
        mode = _GRAPH_ACTIONS.get(action_type)
        if mode is None:
            return Error(f"Unknown graph AI action: {action_type}")
        context = self.context_builder.build_for_graph_selection(entity_ids=entity_ids or [], relation_ids=relation_ids or [], audience=audience)
        return self._run("graph", None, action_type, mode, context, prompt_hint, language=language)

    def _run(
        self,
        target_type: str,
        target_id: str | None,
        action_type: str,
        mode: AIMode,
        context: dict[str, Any],
        prompt_hint: str,
        language: str = "es",
    ) -> Result[AIContextActionResult, str]:
        if context.get("target") == {"redacted": True, "reason": "not_visible_for_audience"}:
            return Error("Target not visible for requested audience")
        context_hash = _context_hash(context)
        operation = AIOperation(
            mode=mode,
            context=_authorized_context(context),
            prompt_hint=self._prompt(action_type, prompt_hint, context, language=language),
            entity_id=target_id if target_type == "node" else None,
            entity_ids=[target_id] if target_type == "node" and target_id else [],
            max_candidates=3,
        )
        try:
            response = self.provider.invoke(operation)
        except Exception as exc:
            return Error(f"Provider error: {exc}")
        if response.error:
            return Error(response.error)

        candidates: list[Candidate] = []
        previews: list[dict[str, Any]] = []
        for index, payload in enumerate(response.candidates or []):
            payload = dict(payload)
            payload.setdefault("canonical_status", "candidate_non_canon")
            payload.setdefault("facts_status", "proposal_only_not_confirmed")
            if action_type in _PREVIEW_ACTIONS:
                previews.append(self._preview_payload(action_type, target_type, target_id, payload, response.raw_text, context_hash))
                continue
            created = self._create_candidate(
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                context=context,
                context_hash=context_hash,
                payload=payload,
                raw_text=response.raw_text,
                provider=response.provider,
                index=index,
            )
            if isinstance(created, Error):
                return Error(created.error)
            candidates.append(created.value)

        if not candidates and not previews and (response.raw_text or response.observations):
            previews.append(self._preview_payload(action_type, target_type, target_id, {}, response.raw_text, context_hash))

        return Ok(AIContextActionResult(
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            raw_text=response.raw_text,
            candidates=candidates,
            previews=previews,
            observations=list(response.observations or []),
            provider=response.provider,
        ))

    def _create_candidate(
        self,
        *,
        action_type: str,
        target_type: str,
        target_id: str | None,
        context: dict[str, Any],
        context_hash: str,
        payload: dict[str, Any],
        raw_text: str,
        provider: str,
        index: int,
    ) -> Result[Candidate, str]:
        title = payload.get("name") or payload.get("title") or f"IA {action_type} #{index + 1}"
        metadata = {
            "origin": "AIContextActionService",
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "context_hash": context_hash,
            "context_summary": _compact_context_summary(context),
            "provider": provider,
            "raw_text_preview": raw_text[:500],
            "canonical_status": "candidate_non_canon",
        }
        data = {
            "title": title,
            "candidate_type": _candidate_type_for(action_type, payload),
            "proposed_data": payload,
            "affected_entity_ids": [target_id] if target_type == "node" and target_id else [],
            "affected_relation_ids": [target_id] if target_type == "relation" and target_id else [],
            "source": "ia",
            "source_id": None,
            "confidence": float(payload.get("confidence", 0.5) or 0.5),
            "justification": payload.get("justification") or raw_text[:500],
            "expected_impact": payload.get("expected_impact", "Sugerencia revisable; no canon hasta aceptación explícita."),
            "possible_contradictions": payload.get("possible_contradictions", []),
            "metadata": metadata,
        }
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

    def _prompt(self, action_type: str, prompt_hint: str, context: dict[str, Any], language: str = "es") -> str:
        lang_note = f"\nIdioma de respuesta: {language}." if language else ""
        return (
            "Acción IA contextual: " + action_type + "\n"
            "Restricciones: no modificar canon; producir candidatos/previews revisables; "
            "no tratar candidatos no canonizados como hechos.\n"
            f"Context hash: {_context_hash(context)}\n"
            f"Resumen: {_json_dumps(_compact_context_summary(context))}\n"
            f"Instrucción adicional: {prompt_hint or '—'}"
            f"{lang_note}"
        )


__all__ = ["AIContextActionResult", "AIContextActionService"]
