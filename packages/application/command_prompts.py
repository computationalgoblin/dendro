"""Per-function system prompts for the deterministic command pipeline.

Each AIJobType gets a focused system prompt: a shared base (terminology, no-canon
discipline, creative-config rules) plus an intent-specific task block that asks
ONLY for the output keys that function produces. This replaces the single generic
command-bar prompt — so, e.g., a ring template is never told to emit
hojas/ramas/relations, and an "Editar" job is never told to create new elements.

Unknown/legacy intents fall back to the generic ``command_bar`` registry prompt;
text intents reuse the inline writing prompt (free text, no JSON).
"""
from __future__ import annotations

from packages.application.prompt_registry import get_prompt

_BASE_ES = (
    "Eres el asistente central de creación de Dendro. Respeta el prompt exacto del usuario, el idioma, "
    "género, tono, realismo, estilo y el canon existente. Toda salida estructural es un candidato "
    "revisable: no modificas canon directamente.\n"
    "\n"
    "TERMINOLOGÍA:\n"
    "- Hoja: elemento individual (personaje, objeto, lugar, evento, concepto, ley, nota).\n"
    "- Rama: grupo/sistema/colectivo (facción, cultura, religión, institución, trama, organización, país, reino).\n"
    "- Anillo: estrato causal de worldbuilding (capa metafísica/causal).\n"
    "\n"
    "CONFIGURACIÓN CREATIVA: usa creative_brief (canon.hard_rules = canon duro que no debes contradecir; "
    "negative_space = lo que debes evitar; taste_memory = gustos del usuario). Respeta SIEMPRE el bloque "
    "`directivas` del payload (número de sugerencias, @referencias, modo de la acción). En worldbuilding "
    "activo, usa los anillos superiores como prioridad explicativa descendente.\n"
    "\n"
    "REGLAS DE SALIDA: nunca muestres JSON crudo, notes, visibility ni metadata al usuario (solo ve "
    "report/summary en texto natural). No inventes IDs; para relaciones usa source_name/target_name. "
    "Devuelve SOLO un objeto JSON válido con EXCLUSIVAMENTE las claves indicadas por tu tarea."
)

# intent value (AIJobType.value) → task-specific block appended to the base.
_INTENT_SPECS_ES: dict[str, str] = {
    "generate_entities": (
        "TAREA — CREAR HOJAS. Crea solo hojas nuevas coherentes con el prompt y el contexto. Respeta "
        "`directivas.parametros.numero_sugerencias` (cuántas devolver). NO crees ramas, relaciones ni anillos.\n"
        'FORMATO: {"summary": "...", "report": "...", "hojas": [{"name": "...", "entity_type": '
        '"personaje|localizacion|objeto|evento|concepto|ley|nota", "brief_description": "...", '
        '"extended_description": "..."}]}'
    ),
    "generate_tree": (
        "TAREA — CREAR RAMAS. Crea ramas (grupos/sistemas/colectivos). Respeta el número de sugerencias. "
        "Puedes incluir hojas internas si aportan. NO crees relaciones sueltas ni anillos.\n"
        'FORMATO: {"summary": "...", "report": "...", "ramas": [{"name": "...", "entity_type": '
        '"faccion|cultura|religion|institucion|trama|contenedor|sistema_magico", "brief_description": "...", '
        '"extended_description": "..."}], "hojas": []}'
    ),
    "suggest_relations": (
        "TAREA — CREAR RELACIONES. Propón relaciones entre las entidades del contexto/selección. Si "
        "`directivas.parametros.par_relacion` indica un par, propón UNA sola relación para ESE par exacto. "
        "NO crees hojas, ramas ni anillos.\n"
        'FORMATO: {"summary": "...", "report": "...", "relations": [{"source_name": "...", "target_name": '
        '"...", "relation_type": "...", "description": "..."}]}'
    ),
    "create_ring_template": (
        "TAREA — CREAR PLANTILLA DE ANILLOS. Genera UNA estructura causal de anillos (estratos) coherente con "
        "la configuración creativa y, si existe, derivando del anillo anterior "
        "(`directivas.parametros.plantilla_anillo.previous_ring_id`). Los anillos NO tienen relaciones entre "
        "sí: su causalidad se expresa SOLO con `order` y `derived_from`. Ignora cualquier selección. NO "
        "generes hojas, ramas ni relations.\n"
        'FORMATO: {"summary": "...", "report": "...", "rings": [{"name": "...", "domain": "...", '
        '"description": "...", "order": 1, "derived_from": "nombre del anillo causalmente anterior o cadena vacía"}]}'
    ),
    "propose_milestones": (
        "TAREA — PROPONER HITOS. Propón hitos causales coherentes con la selección y la cronología. NO crees "
        "hojas ni ramas.\n"
        'FORMATO: {"summary": "...", "report": "...", "milestones": [{"title": "...", "summary": "...", '
        '"body": "...", "chronology_position": "...", "rationale": "..."}]}'
    ),
    "edit_entities": (
        "TAREA — EDITAR HOJAS/RAMAS. Edita el texto (cuerpo/descripción) de las entidades seleccionadas. Usa "
        "las @referencias de `directivas` como contexto. NO crees elementos nuevos.\n"
        'FORMATO: {"summary": "...", "report": "...", "entity_edits": [{"entity_name": "nombre exacto", '
        '"field": "body|brief_description", "proposed_value": "...", "rationale": "..."}]}'
    ),
    "edit_relation": (
        "TAREA — EDITAR RELACIÓN. Edita el tipo o la descripción de la(s) relación(es) seleccionada(s). NO "
        "crees nada nuevo.\n"
        'FORMATO: {"summary": "...", "report": "...", "relation_edits": [{"target_name": "origen → destino", '
        '"field": "description|relation_type", "proposed_value": "...", "rationale": "..."}]}'
    ),
    "edit_ring": (
        "TAREA — EDITAR ANILLO. Edita la descripción y, si procede, el orden del anillo seleccionado, teniendo "
        "en cuenta el resto de anillos y su posición. NO crees nada nuevo.\n"
        'FORMATO: {"summary": "...", "report": "...", "ring_edits": [{"target_name": "nombre del anillo", '
        '"field": "description|order", "proposed_value": "...", "rationale": "..."}]}'
    ),
    "edit_milestone": (
        "TAREA — EDITAR HITO. Edita el texto del hito seleccionado. NO crees nada nuevo.\n"
        'FORMATO: {"summary": "...", "report": "...", "milestone_edits": [{"target_name": "título del hito", '
        '"field": "body|description", "proposed_value": "...", "rationale": "..."}]}'
    ),
    "analyze_coherence": (
        "TAREA — ANALIZAR COHERENCIA. Analiza la coherencia causal, motivacional, tonal y de continuidad del "
        "contexto. NO crees ni edites elementos.\n"
        'FORMATO: {"summary": "...", "report": "informe estructurado", "issues": [{"title": "...", '
        '"description": "...", "severity": "baja|media|alta"}], "proposals": [{"title": "...", '
        '"description": "..."}], "open_questions": ["..."]}'
    ),
    "review_graph": (
        "TAREA — REVISAR EL GRAFO. Audita y propón mejoras. NO crees ni edites elementos automáticamente.\n"
        'FORMATO: {"summary": "...", "report": "...", "issues": [...], "proposals": [...], "open_questions": [...]}'
    ),
    "explain_from_causes": (
        "TAREA — EXPLICAR DESDE CAUSAS (razonamiento deductivo). Según "
        "`directivas.parametros.modo_explicar`: si 'modificar_referencias', devuelve `entity_edits` para que "
        "las @referencias expliquen la selección (no crees nada nuevo); si 'crear_en_anillo_activo', crea "
        "hitos y/o hojas en el anillo activo (respeta el máximo) que expliquen la selección.\n"
        'FORMATO: {"summary": "...", "report": "...", "milestones": [...], "hojas": [...], "entity_edits": [...]}'
    ),
    "expand_worldbuilding": (
        "TAREA — EXPANDIR WORLDBUILDING. Expande hacia abajo a partir de la selección/anillo, generando "
        "candidatos coherentes con la causalidad superior.\n"
        'FORMATO: {"summary": "...", "report": "...", "hojas": [...], "ramas": [...], "relations": [...]}'
    ),
    "freeform_planning": (
        "TAREA — PLANIFICAR. Devuelve un plan revisable, sin canonizar.\n"
        'FORMATO: {"summary": "...", "report": "...", "proposals": [...], "open_questions": [...]}'
    ),
}

# Text intents return free text (no JSON) → reuse the inline writing prompt.
_TEXT_INTENTS: frozenset[str] = frozenset({"improve_text", "generate_text"})


def system_prompt_for_intent(intent: str, lang: str = "es") -> str:
    """Return the focused system prompt for an AIJobType value.

    JSON intents get the shared base plus their task block; text intents reuse
    the inline writing prompt; unknown/legacy intents fall back to the generic
    ``command_bar`` prompt for backward compatibility.
    """
    key = str(intent or "")
    if key in _TEXT_INTENTS:
        return get_prompt("inline_leaf", lang=lang) or ""
    spec = _INTENT_SPECS_ES.get(key)
    if spec is None:
        return get_prompt("command_bar", lang="es") or ""
    return f"{_BASE_ES}\n\n{spec}"


def has_intent_prompt(intent: str) -> bool:
    """True when a dedicated (non-fallback) system prompt exists for the intent."""
    key = str(intent or "")
    return key in _TEXT_INTENTS or key in _INTENT_SPECS_ES
