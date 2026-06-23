"""AI context summary for imported reference documents (I12).

Modo Contexto: un documento importado no genera canon, pero la IA produce un
resumen + fichas de contexto (no-canon) para mejorar la recuperación RAG. El
resultado se guarda en ``basket.metadata['context_summary']`` y lo indexa el
corpus_indexer como material de referencia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import json

from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest
from packages.application.import_ai_extraction_service import resolve_configured_provider
from packages.domain.import_models import ImportBasket
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider


IMPORT_CONTEXT_SUMMARY_INTENT = "import_context_summary"
IMPORT_CONTEXT_SUMMARY_TIMEOUT_SECONDS = 300
_MAX_CHARS = 12000  # cota de seguridad del material enviado al proveedor


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _document_text(basket: ImportBasket) -> str:
    parts: list[str] = []
    for segment in getattr(basket, "segments", []) or []:
        section = _as_text(getattr(segment, "section", ""))
        raw = _as_text(getattr(segment, "raw_text", ""))
        if not raw:
            continue
        parts.append(f"## {section}\n{raw}" if section else raw)
    text = "\n\n".join(parts)
    return text[:_MAX_CHARS]


def _normalize_topic_cards(value: Any) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                title = _as_text(item.get("title"))
                text = _as_text(item.get("text") or item.get("summary"))
                if title or text:
                    cards.append({"title": title, "text": text})
    return cards


@dataclass
class ImportContextSummaryService:
    """Provider-backed reference summary for context-mode baskets."""

    provider: AIProvider | None = None
    allow_simulated: bool = False
    timeout_seconds: int = IMPORT_CONTEXT_SUMMARY_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.provider = self.provider or resolve_configured_provider()

    def _provider_unconfigured_error(self) -> Error | None:
        provider_name = str(getattr(self.provider, "provider_name", "ai"))
        if provider_name == "simulated" and not self.allow_simulated:
            return Error(
                "IA no configurada para resumen de contexto; no se generara contenido simulado."
            )
        return None

    def summarize_basket(
        self,
        basket: ImportBasket,
        *,
        project_context: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any], str]:
        """Genera el resumen no-canon y lo guarda en basket.metadata.

        Nunca crea candidatos de canon ni muta el proyecto fuera de la metadata
        de la cesta.
        """
        unavailable = self._provider_unconfigured_error()
        if unavailable:
            return unavailable

        document_text = _document_text(basket)
        if not document_text:
            return Error("La cesta no tiene texto para resumir")

        project_context = project_context or {}
        gateway = AIRequestGateway(provider=self.provider)
        request = GatewayRequest(
            intent=IMPORT_CONTEXT_SUMMARY_INTENT,
            user_prompt=json.dumps(
                {"task": "summarize_reference_document", "document": document_text},
                ensure_ascii=False,
                default=str,
            ),
            context={
                "project_name": project_context.get("project_name", ""),
                "genre": project_context.get("genre", ""),
                "tone": project_context.get("tone", ""),
                "import_scope": "reference_material_only",
            },
            timeout=max(1, int(self.timeout_seconds or IMPORT_CONTEXT_SUMMARY_TIMEOUT_SECONDS)),
        )
        response = gateway.execute(request)
        if response.error:
            return Error(response.error)

        parsed = response.parsed_json
        if not isinstance(parsed, dict):
            return Error("Resumen IA malformado: se esperaba un objeto JSON.")

        summary = {
            "summary": _as_text(parsed.get("summary")),
            "topic_cards": _normalize_topic_cards(parsed.get("topic_cards")),
            "generated_at": _now_iso(),
            "provider": str(getattr(self.provider, "provider_name", "ai")),
        }
        basket.metadata["context_summary"] = summary
        basket.updated_at = summary["generated_at"]
        return Ok(summary)
