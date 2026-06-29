"""IA genera una configuración de proyecto a partir de un documento (I13).

Al importar, la IA propone (a nivel documento, UNA llamada) una **configuración de
proyecto revisable**: calendario (modo + eras + año presente), ubicación temporal
de las entidades extraídas (birth/death/nature) y config auxiliar (tono/género/
taxonomía). La propuesta se guarda en ``basket.metadata['project_config_suggestion']``
y NO escribe canon ni config: aplicarla es una acción explícita del usuario.

Sin proveedor IA real (simulado, no permitido) se BLOQUEA con error claro, igual
que la extracción de candidatos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest
from packages.application.import_ai_extraction_service import resolve_configured_provider
from packages.domain.import_models import ImportBasket
from packages.domain.result import Error, Ok, Result
from packages.domain.world_layer import default_world_layers
from packages.infrastructure.ai_provider import AIProvider

IMPORT_PROJECT_CONFIG_INTENT = "import_project_config"
IMPORT_PROJECT_CONFIG_TIMEOUT_SECONDS = 300
_MAX_CHARS = 12000  # cota del material enviado al proveedor

_SYSTEM_PROMPT = (
    "Eres un asistente de worldbuilding. A partir de un documento narrativo propones "
    "el ANDAMIAJE del mundo (configuración + calendario + anillos causales + hitos), "
    "revisable y nunca canon. Devuelve SOLO un objeto JSON con esta forma:\n"
    "{\n"
    '  "chronology": {"mode": "none|vague_periods|full_calendar", '
    '"calendar_name": str, "present_year": int, '
    '"supports_exact_dates": bool, '
    '"eras": [{"name": str, "start_year": int, "end_year": int|null, "description": str}]},\n'
    '  "entity_temporal": [{"name": str, "birth_year": int|null, "death_year": int|null, '
    '"nature": "mortal|inmortal|eterno|atemporal", "note": str}],\n'
    '  "config": {"tone": str, "genre": str},\n'
    '  "world_layers": {"activate_default_layer_ids": [str], '
    '"custom_layers": [{"name": str, "description": str, "causal_role": str, '
    '"causal_parent_layer_ids": [str]}]},\n'
    '  "milestones": [{"title": str, "description": str, '
    '"milestone_type": "origen|fundacion|ruptura|guerra|pacto|traicion|descubrimiento|'
    'catastrofe|migracion|reforma|ascenso|caida|revelacion|consecuencia|otro", '
    '"year": int|null, "date_label": str, "affected_layer_ids": [str], "tags": [str], '
    '"rationale": str}]\n'
    "}\n"
    "ANILLOS (world_layers): un anillo es un estrato CAUSAL del mundo (capa), no temporal. "
    "Recibes en 'available_layers' el catálogo de capas predefinidas (con id y rol causal). "
    "En 'activate_default_layer_ids' incluye SOLO los ids de ese catálogo que sean relevantes "
    "para este mundo. En 'custom_layers' añade anillos a medida solo si el mundo necesita una "
    "capa causal que el catálogo no cubre; 'causal_parent_layer_ids' referencia ids del "
    "catálogo o nombres de otras custom_layers.\n"
    "HITOS (milestones): eventos causales fundacionales que explican cómo el mundo llegó a su "
    "estado (origen, fundación, guerra, ruptura...). Data cada hito con 'year' (eje del mundo) "
    "cuando el texto lo permita; 'affected_layer_ids' referencia ids del catálogo o nombres de "
    "custom_layers. No inventes hitos triviales: solo los estructurales.\n"
    "Reglas: NO inventes IDs de capa fuera del catálogo o de tus custom_layers. Usa 'mode' "
    "vago si el documento no da fechas exactas. Los años son enteros en el eje del mundo "
    "(pueden ser negativos). Solo incluye entity_temporal para entidades realmente datables."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _document_text(basket: ImportBasket) -> str:
    parts: list[str] = []
    for segment in getattr(basket, "segments", []) or []:
        raw = _as_text(getattr(segment, "raw_text", ""))
        if not raw:
            continue
        section = _as_text(getattr(segment, "section", ""))
        parts.append(f"## {section}\n{raw}" if section else raw)
    return "\n\n".join(parts)[:_MAX_CHARS]


def _norm_chronology(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    mode = _as_text(value.get("mode")) or "vague_periods"
    if mode not in {"none", "vague_periods", "full_calendar"}:
        mode = "vague_periods"
    eras: list[dict[str, Any]] = []
    for era in value.get("eras") or []:
        if not isinstance(era, dict):
            continue
        name = _as_text(era.get("name"))
        if not name:
            continue
        eras.append({
            "name": name,
            "start_year": _int_or_none(era.get("start_year")),
            "end_year": _int_or_none(era.get("end_year")),
            "description": _as_text(era.get("description")),
        })
    return {
        "mode": mode,
        "calendar_name": _as_text(value.get("calendar_name")),
        "present_year": _int_or_none(value.get("present_year")),
        "supports_exact_dates": bool(value.get("supports_exact_dates", False)),
        "eras": eras,
    }


def _norm_entity_temporal(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _as_text(item.get("name"))
        if not name:
            continue
        nature = _as_text(item.get("nature")).lower()
        if nature not in {"mortal", "inmortal", "eterno", "atemporal"}:
            nature = "mortal"
        out.append({
            "name": name,
            "birth_year": _int_or_none(item.get("birth_year")),
            "death_year": _int_or_none(item.get("death_year")),
            "nature": nature,
            "note": _as_text(item.get("note")),
        })
    return out


def _norm_config(value: Any) -> dict[str, Any]:
    # PA04: la taxonomía de importación se eliminó; la propuesta solo lleva tono/género.
    value = value if isinstance(value, dict) else {}
    return {
        "tone": _as_text(value.get("tone")),
        "genre": _as_text(value.get("genre")),
    }


_MILESTONE_TYPES = {
    "origen", "fundacion", "ruptura", "guerra", "pacto", "traicion",
    "descubrimiento", "catastrofe", "migracion", "reforma", "ascenso",
    "caida", "revelacion", "consecuencia", "otro",
}


def _valid_default_layer_ids() -> set[str]:
    return {wl.id for wl in default_world_layers()}


def _norm_world_layers(value: Any) -> dict[str, Any]:
    """Normaliza la propuesta de anillos (capas causales).

    ``activate_default_layer_ids`` se filtra contra el catálogo predefinido para
    no materializar ids inventados; ``custom_layers`` conserva los anillos a medida.
    """
    value = value if isinstance(value, dict) else {}
    valid_ids = _valid_default_layer_ids()
    activate: list[str] = []
    for raw in _str_list(value.get("activate_default_layer_ids")):
        if raw in valid_ids and raw not in activate:
            activate.append(raw)
    custom: list[dict[str, Any]] = []
    for item in value.get("custom_layers") or []:
        if not isinstance(item, dict):
            continue
        name = _as_text(item.get("name"))
        if not name:
            continue
        custom.append({
            "name": name,
            "description": _as_text(item.get("description")),
            "causal_role": _as_text(item.get("causal_role")),
            "causal_parent_layer_ids": _str_list(item.get("causal_parent_layer_ids")),
        })
    return {"activate_default_layer_ids": activate, "custom_layers": custom}


def _norm_milestones(value: Any) -> list[dict[str, Any]]:
    """Normaliza la propuesta de hitos causales (datados, con capas afectadas)."""
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _as_text(item.get("title")) or _as_text(item.get("name"))
        if not title:
            continue
        mtype = _as_text(item.get("milestone_type")).lower()
        if mtype not in _MILESTONE_TYPES:
            mtype = "otro"
        out.append({
            "title": title,
            "description": _as_text(item.get("description")),
            "milestone_type": mtype,
            "year": _int_or_none(item.get("year")),
            "date_label": _as_text(item.get("date_label")),
            "affected_layer_ids": _str_list(item.get("affected_layer_ids")),
            "tags": _str_list(item.get("tags")),
            "rationale": _as_text(item.get("rationale")),
        })
    return out


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


@dataclass
class ImportProjectConfigService:
    """Provider-backed reviewable project-config proposal from a document."""

    provider: AIProvider | None = None
    allow_simulated: bool = False
    timeout_seconds: int = IMPORT_PROJECT_CONFIG_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.provider = self.provider or resolve_configured_provider()

    def _provider_unconfigured_error(self) -> Error | None:
        provider_name = str(getattr(self.provider, "provider_name", "ai"))
        if provider_name == "simulated" and not self.allow_simulated:
            return Error(
                "IA no configurada para generar configuración de proyecto; "
                "no se generara contenido simulado."
            )
        return None

    def generate_for_basket(
        self,
        basket: ImportBasket,
        *,
        project_context: dict[str, Any] | None = None,
        entity_names: list[str] | None = None,
    ) -> Result[dict[str, Any], str]:
        """Genera la propuesta de config y la guarda en basket.metadata.

        Nunca crea canon ni muta la config del proyecto: solo escribe en la
        metadata de la cesta. Devuelve la propuesta normalizada.
        """
        unavailable = self._provider_unconfigured_error()
        if unavailable:
            return unavailable

        document_text = _document_text(basket)
        if not document_text:
            return Error("La cesta no tiene texto para configurar el proyecto")

        project_context = project_context or {}
        available_layers = [
            {
                "id": wl.id,
                "name": wl.name,
                "causal_role": wl.metadata.get("causal_role", ""),
            }
            for wl in default_world_layers()
        ]
        gateway = AIRequestGateway(provider=self.provider)
        request = GatewayRequest(
            intent=IMPORT_PROJECT_CONFIG_INTENT,
            user_prompt=json.dumps(
                {
                    "task": "propose_world_scaffolding",
                    "document": document_text,
                    "known_entities": list(entity_names or []),
                    "available_layers": available_layers,
                },
                ensure_ascii=False,
                default=str,
            ),
            context={
                "project_name": project_context.get("project_name", ""),
                "genre": project_context.get("genre", ""),
                "tone": project_context.get("tone", ""),
            },
            system_prompt_override=_SYSTEM_PROMPT,
            timeout=max(1, int(self.timeout_seconds or IMPORT_PROJECT_CONFIG_TIMEOUT_SECONDS)),
        )
        response = gateway.execute(request)
        if response.error:
            return Error(response.error)

        parsed = response.parsed_json
        if not isinstance(parsed, dict):
            return Error("Propuesta de config IA malformada: se esperaba un objeto JSON.")

        proposal = {
            "chronology": _norm_chronology(parsed.get("chronology")),
            "entity_temporal": _norm_entity_temporal(parsed.get("entity_temporal")),
            "config": _norm_config(parsed.get("config")),
            "world_layers": _norm_world_layers(parsed.get("world_layers")),
            "milestones": _norm_milestones(parsed.get("milestones")),
            "generated_at": _now_iso(),
            "provider": str(getattr(self.provider, "provider_name", "ai")),
            "applied": False,
        }
        basket.metadata["project_config_suggestion"] = proposal
        basket.updated_at = proposal["generated_at"]
        return Ok(proposal)
