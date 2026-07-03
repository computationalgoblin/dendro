"""Ensamblado del mensaje de usuario para los jobs de IA.

RAG dejó de ser dueño del prompt: aquí se construye el mensaje completo con una
jerarquía de autoridad explícita (DIRIGE > RESTRINGE > INFORMA > ATMÓSFERA) y se
separan las fuentes por autoridad — canon confirmado, candidates pendientes
y RAG auxiliar — para que el modelo no las confunda. El
``rag_context_pack`` se PARTICIONA por ``kind`` en esas secciones etiquetadas en
vez de volcarse crudo en ``contexto_autorizado``.

El presupuesto de contexto ya no es global: cada intent resuelve a un tier
(:mod:`packages.application.context_budget`) con su propio reparto por sección.

``build_model_user_message`` se mantiene en ``ai_jobs`` como shim de
compatibilidad que delega en el :class:`PromptAssembler` por defecto.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from packages.application.context_budget import ContextBudgetManager
from packages.application.prompt_budget import _estimate_tokens, enforce_budget_report

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
        "rag_context_pack",  # → canon / candidates / rag_auxiliar
    }
)

# Etiquetas de autoridad visibles para el modelo (primera clave de cada sección).
_LABEL_CANON = "CANON CONFIRMADO — AUTORITATIVO. No lo contradigas."
_LABEL_CANDIDATES = (
    "CANDIDATES PENDIENTES — PROPUESTAS, NO canon. Trátalos como hipótesis revisables."
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
    # PA04 forward-compat: aquí se inyectará en el futuro `resumen_proyecto` —
    # un resumen periódico del contenido actual del proyecto (regenerado fuera de
    # línea) que viajará en cada prompt. Punto de inserción reservado; sin job/UI aún.
    section: dict[str, Any] = {
        "instruccion": (
            "Configuración creativa COMPLETA del proyecto (5 secciones). "
            "reglas.reglas_canon = canon duro (no lo contradigas; si la petición choca, "
            "devuélvelo como issue/proposal). reglas.evitar = lo que debes evitar. "
            "identidad/direccion/motor/estilo guían tono, género y rumbo narrativo."
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
    block: dict[str, Any] = {
        "entity_ids": list(context.get("selected_entity_ids") or []),
        "relation_ids": list(context.get("selected_relation_ids") or []),
        "anillo_activo": context.get("active_ring_id") or context.get("focused_ring_id") or "",
        "focus_label": context.get("focus_label") or "",
    }
    # UX5c: la NATURALEZA del anillo activo (descripción + dominio) viaja al modelo
    # para que cree/edite entidades coherentes con ese anillo, no solo con su nombre.
    ring = context.get("active_ring")
    if isinstance(ring, dict) and ring:
        if ring.get("name"):
            block["anillo_activo_nombre"] = ring["name"]
        if ring.get("description"):
            block["anillo_activo_descripcion"] = ring["description"]
        if ring.get("domain"):
            block["anillo_activo_dominio"] = ring["domain"]
        block["coherencia_anillo"] = (
            "Si hay anillo activo, la entidad/edición DEBE encajar en su naturaleza, "
            "escala y temática (su descripción y dominio mandan): p. ej. un anillo "
            "cosmológico ⇒ entidades cosmológicas, no mundanas."
        )
    # DC-UX4-HITO: hitos seleccionados con sus datos VIGENTES (título, año, texto), para
    # que `editar:hito` tenga el dato de partida y pueda calcular el resultado (p. ej.
    # adelantar un siglo = year + 100). Sin esto el modelo rechaza la edición.
    milestones = context.get("selected_milestones")
    if isinstance(milestones, list) and milestones:
        block["hitos_seleccionados"] = milestones
        block["coherencia_hito"] = (
            "Para editar un hito, parte de sus datos vigentes (arriba): calcula el "
            "`year` resultante a partir del año actual y reescribe el texto sobre el "
            "contenido actual. NO pidas datos que ya están aquí."
        )
    return block


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
        elif kind in _CANON_KINDS:
            canon.append(entry)
        else:  # issue, creative_config, desconocido → apoyo auxiliar
            aux.append(entry)

    out: dict[str, Any] = {}
    if canon:
        out["canon_confirmado"] = {"autoridad": _LABEL_CANON, "items": canon}
    if candidates:
        out["candidates_pendientes"] = {"autoridad": _LABEL_CANDIDATES, "items": candidates}
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


# ---------------------------------------------------------------------------
# Vista previa de contexto (UX3): exclusión por sección/item + estructura legible
# ---------------------------------------------------------------------------

# Etiquetas en español por sección (para la UI; el modelo ve las claves crudas).
SECTION_LABELS: dict[str, str] = {
    "prompt_exacto_usuario": "Tu petición",
    "directivas": "Directivas",
    "menciones": "Menciones (@)",
    "configuracion_creativa": "Configuración creativa",
    "cronologia": "Cronología",
    "canon_confirmado": "Canon confirmado",
    "posicion_causal": "Posición causal",
    "seleccion": "Selección",
    "vecindario": "Vecindario",
    "candidates_pendientes": "Candidatos pendientes",
    "rag_auxiliar": "RAG auxiliar",
    "contexto_autorizado": "Contexto autorizado",
    "formatos_h05": "Formato de salida",
}

# Secciones RAG-derivadas → qué `kind` del pack las nutre (para excluir por sección).
_RAG_SECTION_KINDS: dict[str, frozenset[str] | None] = {
    "canon_confirmado": _CANON_KINDS,
    "candidates_pendientes": frozenset({"candidate"}),
    "rag_auxiliar": None,  # el resto (issue, creative_config, desconocido)
}

# Secciones deterministas excluibles → claves del context_scope que las generan.
_DETERMINISTIC_SECTION_KEYS: dict[str, tuple[str, ...]] = {
    "cronologia": ("cronologia",),
    "posicion_causal": ("contexto_causal",),
    "vecindario": ("vecindario",),
    "seleccion": ("selected_entity_ids", "selected_relation_ids"),
}

# Lo que el usuario PUEDE quitar en la vista previa (lo demás es fijo/sagrado).
_EXCLUDABLE_SECTIONS: frozenset[str] = frozenset(
    set(_RAG_SECTION_KINDS) | set(_DETERMINISTIC_SECTION_KEYS)
)


def _section_for_kind(kind: Any) -> str:
    """Sección de autoridad a la que pertenece un item del pack, por ``kind``."""
    if kind == "candidate":
        return "candidates_pendientes"
    if kind in _CANON_KINDS:
        return "canon_confirmado"
    return "rag_auxiliar"


def apply_section_exclusions(
    context: dict[str, Any],
    excluded_sections: Any,
    excluded_item_ids: Any,
) -> dict[str, Any]:
    """Devuelve una copia del context_scope sin las secciones/items excluidos.

    Pura y defensiva. Las secciones deterministas se quitan eliminando sus claves
    de origen; las RAG-derivadas filtran ``rag_context_pack['items']`` por ``kind``
    (sección entera) y por ``ref_id`` (item suelto). Las secciones fijas/sagradas
    no son excluibles: aunque lleguen en la lista, se ignoran.
    """
    ctx = copy.deepcopy(dict(context or {}))
    sections = {s for s in (excluded_sections or []) if s in _EXCLUDABLE_SECTIONS}
    item_ids = {str(i) for i in (excluded_item_ids or []) if str(i)}

    for sec in sections:
        for key in _DETERMINISTIC_SECTION_KEYS.get(sec, ()):
            ctx.pop(key, None)

    pack = ctx.get("rag_context_pack")
    if isinstance(pack, dict) and isinstance(pack.get("items"), list):
        kept: list[Any] = []
        for it in pack["items"]:
            if not isinstance(it, dict):
                continue
            if str(it.get("ref_id") or "") in item_ids:
                continue
            if _section_for_kind(it.get("kind")) in sections:
                continue
            kept.append(it)
        new_pack = dict(pack)
        new_pack["items"] = kept
        ctx["rag_context_pack"] = new_pack
    return ctx


def _short_text(value: Any, *, limit: int = 320) -> str:
    """Texto recortado de un item para previsualizar sin volcar todo el rendered."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def build_context_preview(preview: dict[str, Any]) -> dict[str, Any]:
    """Convierte ``PromptAssembler.preview()`` en una estructura para la UI.

    Una fila por sección (con etiqueta, tokens estimados, si es fija y si se
    recortó por presupuesto) y, en las secciones con ``items``, una sub-fila por
    item (ref_id, kind, tokens y un extracto del texto). Refleja lo que REALMENTE
    se enviará (``trimmed``, ya con presupuesto y exclusiones aplicados).
    """
    trimmed = preview.get("trimmed") or {}
    sections_out: list[dict[str, Any]] = []
    for key, value in trimmed.items():
        items_out: list[dict[str, Any]] = []
        raw_items = value.get("items") if isinstance(value, dict) else None
        if isinstance(raw_items, list):
            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                items_out.append(
                    {
                        "ref_id": str(it.get("ref_id") or ""),
                        "kind": str(it.get("kind") or ""),
                        "est_tokens": _estimate_tokens(it),
                        "text": _short_text(it.get("rendered_text")),
                    }
                )
        sections_out.append(
            {
                "key": key,
                "label": SECTION_LABELS.get(key, key),
                "fixed": key not in _EXCLUDABLE_SECTIONS,
                "est_tokens": _estimate_tokens(value),
                "truncado": bool(isinstance(value, dict) and value.get("truncado")),
                "items": items_out,
            }
        )
    return {
        "intent": preview.get("intent"),
        "tier": preview.get("tier"),
        "input_budget": preview.get("input_budget"),
        "total_tokens": sum(s["est_tokens"] for s in sections_out),
        "sections": sections_out,
        "warnings": list(preview.get("warnings") or []),
    }


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
        return self.assemble_with_warnings(plan)[0]

    def assemble_with_warnings(self, plan: Any) -> tuple[str, list[str]]:
        """Como ``assemble`` pero devuelve también los avisos de truncado por
        presupuesto (para que el job los registre y la UI no presente un recorte
        silencioso)."""
        pv = self.preview(plan)
        self._log_debug(
            intent=pv["intent"],
            override=pv["override"],
            budget=pv["input_budget"],
            before=pv["sections"],
            after=pv["trimmed"],
            context=pv["context"],
        )
        return json.dumps(pv["trimmed"], ensure_ascii=False, indent=2), list(
            pv.get("warnings") or []
        )

    def preview(self, plan: Any) -> dict[str, Any]:
        """Igual que ``assemble`` pero SIN serializar: devuelve las secciones antes
        y después del presupuesto, el tier y el budget. Lo usan la vista previa de
        contexto (UX3) y ``assemble`` (única fuente del ensamblado). Si el contexto
        trae ``preview_exclusions`` (secciones/items que el usuario quitó en la
        vista previa), se aplican aquí, así el job real respeta lo mismo al ejecutar.
        """
        context = getattr(plan, "context", None) or {}
        excl = context.get("preview_exclusions")
        if isinstance(excl, dict) and (excl.get("sections") or excl.get("item_ids")):
            context = apply_section_exclusions(
                context, excl.get("sections") or [], excl.get("item_ids") or []
            )
        intent = _intent_value(plan)
        sections = self._build_sections(plan, context)
        override = context.get("prompt_budget_tokens")
        budget = self._budget.input_budget(intent, override_tokens=override)
        percentages = self._budget.section_percentages(intent)
        trimmed, warnings = enforce_budget_report(
            sections, budget, section_percentages=percentages
        )
        return {
            "intent": intent,
            "tier": self._budget.tier_for(intent).value,
            "input_budget": budget,
            "override": override,
            "percentages": percentages,
            "sections": sections,
            "trimmed": trimmed,
            "warnings": warnings,
            "context": context,
        }

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
    "apply_section_exclusions",
    "build_context_preview",
    "build_model_user_message",
]


_DEFAULT_ASSEMBLER = PromptAssembler()


def build_model_user_message(plan: Any) -> str:
    """Shim de compatibilidad: delega en el PromptAssembler por defecto."""
    return _DEFAULT_ASSEMBLER.assemble(plan)


def build_model_user_message_with_warnings(plan: Any) -> tuple[str, list[str]]:
    """Como ``build_model_user_message`` pero devuelve también los avisos de
    truncado por presupuesto."""
    return _DEFAULT_ASSEMBLER.assemble_with_warnings(plan)
