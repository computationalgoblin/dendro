"""Ensamblado del mensaje de usuario para los jobs de IA.

RAG dejó de ser dueño del prompt: aquí se construye el mensaje completo con una
jerarquía de autoridad explícita (DIRIGE > RESTRINGE > INFORMA > ATMÓSFERA) y se
separan las fuentes por autoridad — canon confirmado, candidates pendientes,
imports sin revisar y RAG auxiliar — para que el modelo no las confunda. El
``rag_context_pack`` se PARTICIONA por ``kind`` en esas secciones etiquetadas en
vez de volcarse crudo en ``contexto_autorizado``.

El presupuesto de contexto ya no es global: cada intent resuelve a un tier
(:mod:`packages.application.context_budget`) con su propio reparto por sección.

``build_model_user_message`` se mantiene en ``ai_jobs`` como shim de
compatibilidad que delega en el :class:`PromptAssembler` por defecto.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from packages.application.context_budget import ContextBudgetManager
from packages.application.prompt_budget import enforce_budget

logger = logging.getLogger("narrative.prompt_assembler")


# Claves que ya viajan procesadas en otras secciones del mensaje. Se excluyen
# SIEMPRE de contexto_autorizado para evitar duplicación. `rag_context_pack` se
# añade aquí porque ahora se reparte en secciones etiquetadas por autoridad.
_DUPLICATED_CONTEXT_KEYS = frozenset(
    {
        "creative_brief",  # → configuracion_creativa (completa)
        "creative_context",  # → configuracion_creativa
        "branch_creative_context",  # → configuracion_creativa
        "contexto_causal",  # → posicion_causal
        "vecindario",  # → vecindario
        "cronologia",  # → cronologia (sección determinista compacta)
        "rag_context_pack",  # → canon_confirmado / candidates_pendientes / imports / rag_auxiliar
    }
)

# Etiquetas de autoridad visibles para el modelo (primera clave de cada sección).
_LABEL_CANON = "CANON CONFIRMADO — AUTORITATIVO. No lo contradigas."
_LABEL_CANDIDATES = (
    "CANDIDATES PENDIENTES — PROPUESTAS, NO canon. Trátalos como hipótesis revisables."
)
_LABEL_IMPORTS = (
    "AUXILIAR NO REVISADO — fuente externa importada. No se impone sobre el canon aceptado."
)
_LABEL_RAG = "RAG AUXILIAR — recuperado, NO autoritativo. Úsalo como apoyo, no como verdad."

# Kinds del corpus que SON canon aceptado.
_CANON_KINDS = frozenset({"entity", "branch", "relation", "world_layer", "milestone", "chronology"})


def _context_for_prompt(context: dict[str, Any]) -> dict[str, Any]:
    """Devuelve el context_scope SIN las claves que ya tienen su sección propia."""
    return {k: v for k, v in (context or {}).items() if k not in _DUPLICATED_CONTEXT_KEYS}


def _prune_empty(value: Any) -> Any:
    """Elimina recursivamente strings vacíos, listas/dicts vacíos y None.

    Conserva 0, False y demás valores legítimos (continuity_strictness=0,
    worldbuilding_active=False). Devuelve None cuando el valor queda vacío para
    que el contenedor lo descarte. Quita el ruido del payload (campos en blanco).
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, val in value.items():
            pruned = _prune_empty(val)
            if pruned is not None:
                out[key] = pruned
        return out or None
    if isinstance(value, (list, tuple)):
        out_list = [p for p in (_prune_empty(v) for v in value) if p is not None]
        return out_list or None
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    return value


def _configuracion_creativa(context: dict[str, Any]) -> dict[str, Any]:
    """RESTRINGE + ATMÓSFERA. Config creativa COMPLETA y determinista.

    Único hogar de la configuración creativa en el payload (antes repartida entre
    cerco_canon + parametros_permanentes, que la duplicaban). Lleva el brief
    entero —canon, negative_space, taste_memory, género/tono/realismo, poética,
    intención, motor narrativo, preferencias IA— y luego se poda de vacíos.
    """
    brief = context.get("creative_brief") or {}
    if not isinstance(brief, dict) or not brief:
        return {}
    section: dict[str, Any] = {
        "instruccion": (
            "Configuración creativa COMPLETA del proyecto. canon.hard_rules = canon duro "
            "(no lo contradigas; si la petición choca, devuélvelo como issue/proposal). "
            "negative_space = lo que debes evitar. taste_memory = gustos del usuario."
        ),
    }
    section.update(brief)
    return section


def _mentions_block(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Menciones con mini-ficha si el host la enriqueció (CONO)."""
    mentions = context.get("mentions")
    if not isinstance(mentions, dict):
        return []
    result: list[dict[str, Any]] = []
    for ref in mentions.get("refs") or []:
        if not isinstance(ref, dict):
            continue
        entry: dict[str, Any] = {"name": ref.get("name"), "ref_type": ref.get("ref_type")}
        brief = ref.get("brief")
        if isinstance(brief, dict):
            entry.update(brief)
        result.append(entry)
    return result


def _selection_block(context: dict[str, Any]) -> dict[str, Any]:
    """INFORMA. Entidad objetivo y anillo activo (CONO)."""
    return {
        "entity_ids": list(context.get("selected_entity_ids") or []),
        "relation_ids": list(context.get("selected_relation_ids") or []),
        "anillo_activo": context.get("active_ring_id") or context.get("focused_ring_id") or "",
        "focus_label": context.get("focus_label") or "",
    }


def _rag_authority_sections(context: dict[str, Any]) -> dict[str, Any]:
    """Particiona el rag_context_pack por `kind` en secciones por autoridad.

    Realiza el principio de la fase: canon, candidates, imports y RAG auxiliar no
    se mezclan. Cada sección lleva una etiqueta `autoridad` visible para el modelo.
    """
    pack = context.get("rag_context_pack")
    if not isinstance(pack, dict):
        return {}
    items = pack.get("items")
    if not isinstance(items, list):
        items = []

    canon: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    aux: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        entry = {
            "kind": it.get("kind"),
            "ref_id": it.get("ref_id"),
            "rendered_text": it.get("rendered_text"),
            "priority": it.get("priority"),
            "reason": it.get("reason"),
        }
        kind = it.get("kind")
        if kind == "candidate":
            candidates.append(entry)
        elif kind == "import_document":
            imports.append(entry)
        elif kind in _CANON_KINDS:
            canon.append(entry)
        else:  # issue, creative_config, desconocido → apoyo auxiliar
            aux.append(entry)

    out: dict[str, Any] = {}
    if canon:
        out["canon_confirmado"] = {"autoridad": _LABEL_CANON, "items": canon}
    if candidates:
        out["candidates_pendientes"] = {"autoridad": _LABEL_CANDIDATES, "items": candidates}
    if imports:
        out["importaciones_sin_revisar"] = {"autoridad": _LABEL_IMPORTS, "items": imports}
    warnings = pack.get("warnings")
    if aux or warnings:
        rag_section: dict[str, Any] = {"autoridad": _LABEL_RAG}
        if aux:
            rag_section["items"] = aux
        if warnings:
            rag_section["warnings"] = warnings
        out["rag_auxiliar"] = rag_section
    return out


# BETA1-AI01: chronology/milestone output spec, attached ONLY to time-related
# jobs (before it rode along on every message — pure noise + tokens).
_CHRONOLOGY_OUTPUT_FORMATS: dict[str, Any] = {
    "project_chronology_suggestion": {
        "kind": "project_chronology_suggestion",
        "title": "string",
        "mode": "none | vague_periods | full_calendar",
        "summary": "string",
        "periods": ["Antiguedad", "Historia reciente", "Actualidad"],
        "eras": ["string"],
        "era_lengths": {"Era Antigua": "integer years"},
        "months": ["string"],
        "month_lengths": {"Enero": "integer days"},
        "weekdays": ["string"],
        "current_date": {"era": "string", "year": "integer", "month": "string", "day": "integer"},
        "units": ["string"],
        "display_format": "string",
        "supports_exact_dates": "boolean",
        "date_resolution": "string",
        "rationale": "string",
        "risks": ["string"],
        "questions_for_user": ["string"],
    },
    "milestones": [
        {
            "title": "string",
            "summary": "string",
            "body": "string",
            "chronology_position": "string",
            "sort_index": "integer",
            "rationale": "string",
            "confidence": "low | medium | high",
        }
    ],
}

_CHRONOLOGY_HINT_TOKENS = (
    "hito",
    "cronolog",
    "calendar",
    "era",
    "milestone",
    "linea temporal",
    "línea temporal",
)


def _intent_value(plan: Any) -> str:
    """Valor string del intent del plan (sin importar AIJobType → evita ciclo)."""
    intent = getattr(plan, "intent", None)
    intent_type = getattr(intent, "intent_type", None)
    return str(getattr(intent_type, "value", intent_type) or "unknown")


def _wants_chronology_formats(plan: Any) -> bool:
    if _intent_value(plan) == "propose_milestones":
        return True
    text = f"{_intent_value(plan)} {getattr(plan, 'prompt', '')}".lower()
    return any(token in text for token in _CHRONOLOGY_HINT_TOKENS)


def _fase2_directives(context: dict[str, Any]) -> dict[str, Any] | None:
    """Surface the deterministic per-cell behaviours as explicit model directives."""
    ctx = dict(context or {})
    params: dict[str, Any] = {}
    instructions: list[str] = []

    count = ctx.get("suggestion_count")
    if count:
        params["numero_sugerencias"] = int(count)
        instructions.append(f"Devuelve exactamente {int(count)} sugerencia(s), ni más ni menos.")

    mentions = ctx.get("mentions") if isinstance(ctx.get("mentions"), dict) else {}
    refs = mentions.get("refs") or []
    if refs:
        params["referencias_at"] = refs
        names = ", ".join(str(r.get("name", "")) for r in refs if isinstance(r, dict))
        instructions.append(
            f"Usa como referencia SOLO las entidades/hitos mencionados con @: {names}."
        )

    explain_target = ctx.get("explain_target")
    if explain_target == "modify_refs":
        params["modo_explicar"] = "modificar_referencias"
        instructions.append(
            "Explicar con @referencias: modifica el TEXTO de las entidades/relaciones "
            "referenciadas para que expliquen la selección "
            "(claves 'entity_edits'/'relation_edits'); no crees entidades nuevas."
        )
    elif explain_target == "create_in_active_ring":
        params["modo_explicar"] = "crear_en_anillo_activo"
        ring = ctx.get("active_ring_id") or "el activo"
        instructions.append(
            f"Explicar sin referencias: crea hitos/entidades (máx {ctx.get('max_creations', 3)}) "
            f"en el anillo activo ({ring}) que expliquen la selección."
        )

    if ctx.get("ring_template"):
        params["plantilla_anillo"] = {"previous_ring_id": ctx.get("previous_ring_id") or ""}
        instructions.append(
            "Crear Anillo: genera UNA plantilla de anillos como estructura causal de "
            "dominios, derivando del anillo anterior y la configuración creativa. "
            "Clave 'rings' (name, domain, description, order, derived_from). "
            "Ignora cualquier selección."
        )

    pair = ctx.get("fanout_pair")
    if pair:
        params["par_relacion"] = list(pair)
        instructions.append(
            "Propón UNA relación entre exactamente este par de entidades (clave 'relations')."
        )

    if not params and not instructions:
        return None
    return {"parametros": params, "instrucciones": instructions}


class PromptAssembler:
    """Ensambla el mensaje de usuario para un plan de job IA.

    Sin estado mutable salvo el gestor de presupuesto (también inmutable), así
    que una instancia es segura de compartir entre jobs.
    """

    def __init__(self, budget_manager: ContextBudgetManager | None = None) -> None:
        self._budget = budget_manager or ContextBudgetManager()

    # -- API pública --------------------------------------------------------

    def assemble(self, plan: Any) -> str:
        """Construye el mensaje, aplica presupuesto por tier y devuelve JSON."""
        context = getattr(plan, "context", None) or {}
        intent = _intent_value(plan)

        sections = self._build_sections(plan, context)

        override = context.get("prompt_budget_tokens")
        budget = self._budget.input_budget(intent, override_tokens=override)
        percentages = self._budget.section_percentages(intent)

        trimmed = enforce_budget(sections, budget, section_percentages=percentages)

        self._log_debug(
            intent=intent,
            override=override,
            budget=budget,
            before=sections,
            after=trimmed,
            context=context,
        )
        return json.dumps(trimmed, ensure_ascii=False, indent=2)

    # -- construcción de secciones -----------------------------------------

    def _build_sections(self, plan: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Dict de secciones en orden de autoridad (DIRIGE→RESTRINGE→INFORMA→ATMÓSFERA)."""
        message: dict[str, Any] = {
            # --- DIRIGE ---
            "prompt_exacto_usuario": getattr(plan, "prompt", ""),  # sagrado
        }
        directives = _fase2_directives(context)
        if directives:
            message["directivas"] = directives
        mentions = _mentions_block(context)
        if mentions:
            message["menciones"] = mentions

        # --- RESTRINGE + ATMÓSFERA (config creativa completa y determinista) ---
        config_creativa = _configuracion_creativa(context)
        if config_creativa:
            message["configuracion_creativa"] = config_creativa

        cronologia = context.get("cronologia") if isinstance(context, dict) else None
        if isinstance(cronologia, dict) and cronologia:
            message["cronologia"] = cronologia

        # Secciones por autoridad derivadas del rag_context_pack.
        rag_sections = _rag_authority_sections(context)
        if "canon_confirmado" in rag_sections:
            message["canon_confirmado"] = rag_sections["canon_confirmado"]

        causal = context.get("contexto_causal") if isinstance(context, dict) else None
        if isinstance(causal, dict) and causal:
            message["posicion_causal"] = causal

        # --- INFORMA ---
        message["seleccion"] = _selection_block(context)
        vecindario = context.get("vecindario") if isinstance(context, dict) else None
        if isinstance(vecindario, dict) and vecindario.get("items"):
            message["vecindario"] = vecindario
        if "candidates_pendientes" in rag_sections:
            message["candidates_pendientes"] = rag_sections["candidates_pendientes"]
        if "importaciones_sin_revisar" in rag_sections:
            message["importaciones_sin_revisar"] = rag_sections["importaciones_sin_revisar"]
        if "rag_auxiliar" in rag_sections:
            message["rag_auxiliar"] = rag_sections["rag_auxiliar"]

        # --- RESIDUAL (sin duplicados) ---
        message["contexto_autorizado"] = _context_for_prompt(context)

        if _wants_chronology_formats(plan):
            message["formatos_h05"] = _CHRONOLOGY_OUTPUT_FORMATS

        # Poda recursiva de vacíos: quita el ruido (campos en blanco) antes de
        # presupuestar. formatos_h05 es un esquema-plantilla: no se poda.
        formatos = message.pop("formatos_h05", None)
        pruned = _prune_empty(message) or {}
        if formatos is not None:
            pruned["formatos_h05"] = formatos
        return pruned

    # -- observabilidad -----------------------------------------------------

    def _log_debug(
        self,
        *,
        intent: str,
        override: Any,
        budget: int,
        before: dict[str, Any],
        after: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return
        try:
            tier = self._budget.tier_for(intent)
            chars_per_section: dict[str, int] = {}
            for key, value in after.items():
                serialized = (
                    value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                )
                chars_per_section[key] = len(serialized)
            # tokens_to_chars(t) = int(t*3.5); invertimos: tokens ≈ chars / 3.5.
            est_tokens = {k: round(c / 3.5) for k, c in chars_per_section.items()}
            omitted = [k for k in before if k not in after]
            duplicates = sorted(k for k in _DUPLICATED_CONTEXT_KEYS if k in (context or {}))
            total_est = sum(est_tokens.values())
            inc_str = " ".join(f"{k}={v}" for k, v in est_tokens.items())
            logger.debug(
                "[PROMPT_DEBUG] intent=%s tier=%s input_budget=%s override=%s\n"
                "  sections_included(tokens): %s\n"
                "  sections_omitted: %s\n"
                "  duplicates_removed: %s\n"
                "  total_estimated_tokens=%s",
                intent,
                tier.value,
                budget,
                override or "-",
                inc_str or "(ninguna)",
                ", ".join(omitted) or "(ninguna)",
                duplicates or "(ninguno)",
                total_est,
            )
        except Exception:  # pragma: no cover - el log nunca debe tumbar un job
            return


__all__ = [
    "PromptAssembler",
    "build_model_user_message",
]


_DEFAULT_ASSEMBLER = PromptAssembler()


def build_model_user_message(plan: Any) -> str:
    """Shim de compatibilidad: delega en el PromptAssembler por defecto."""
    return _DEFAULT_ASSEMBLER.assemble(plan)
