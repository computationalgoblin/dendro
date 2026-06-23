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
from packages.infrastructure.ai_provider import AIProvider

IMPORT_PROJECT_CONFIG_INTENT = "import_project_config"
IMPORT_PROJECT_CONFIG_TIMEOUT_SECONDS = 300
_MAX_CHARS = 12000  # cota del material enviado al proveedor

_SYSTEM_PROMPT = (
    "Eres un asistente de worldbuilding. A partir de un documento narrativo propones "
    "una CONFIGURACIÓN DE PROYECTO revisable, nunca canon. Devuelve SOLO un objeto JSON "
    "con esta forma:\n"
    "{\n"
    '  "chronology": {"mode": "none|vague_periods|full_calendar", '
    '"calendar_name": str, "present_year": int, '
    '"supports_exact_dates": bool, '
    '"eras": [{"name": str, "start_year": int, "end_year": int|null, "description": str}]},\n'
    '  "entity_temporal": [{"name": str, "birth_year": int|null, "death_year": int|null, '
    '"nature": "mortal|inmortal|eterno|atemporal", "note": str}],\n'
    '  "config": {"tone": str, "genre": str, '
    '"taxonomy": {"allowed_entity_types": [str], "allowed_branch_types": [str], '
    '"extraction_guidance": str}}\n'
    "}\n"
    "Reglas: NO inventes IDs. Usa 'mode' vago si el documento no da fechas exactas. "
    "Los años son enteros en el eje del mundo (pueden ser negativos). Solo incluye "
    "entity_temporal para entidades realmente datables en el texto."
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
    value = value if isinstance(value, dict) else {}
    taxonomy = value.get("taxonomy") if isinstance(value.get("taxonomy"), dict) else {}
    return {
        "tone": _as_text(value.get("tone")),
        "genre": _as_text(value.get("genre")),
        "taxonomy": {
            "allowed_entity_types": _str_list(taxonomy.get("allowed_entity_types")),
            "allowed_branch_types": _str_list(taxonomy.get("allowed_branch_types")),
            "extraction_guidance": _as_text(taxonomy.get("extraction_guidance")),
        },
    }


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
        gateway = AIRequestGateway(provider=self.provider)
        request = GatewayRequest(
            intent=IMPORT_PROJECT_CONFIG_INTENT,
            user_prompt=json.dumps(
                {
                    "task": "propose_project_configuration",
                    "document": document_text,
                    "known_entities": list(entity_names or []),
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
            "generated_at": _now_iso(),
            "provider": str(getattr(self.provider, "provider_name", "ai")),
            "applied": False,
        }
        basket.metadata["project_config_suggestion"] = proposal
        basket.updated_at = proposal["generated_at"]
        return Ok(proposal)
