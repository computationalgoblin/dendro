"""Structured AI extraction for imported document chunks (I03).

The service analyzes existing ``DocumentSegment`` chunks and returns
reviewable ``ImportCandidate`` objects. It never creates canon and it does not
fall back to simulated AI unless a test explicitly allows it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import json
import uuid

from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest
from packages.domain.candidate_issue import CandidateType
from packages.domain.import_models import DocumentSegment, ImportBasket, ImportCandidate, ImportReviewState
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider, create_provider


IMPORT_EXTRACTION_INTENT = "import_extraction"
IMPORT_EXTRACTION_TIMEOUT_SECONDS = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _confidence(value: Any, default: float = 0.5) -> float:
    if isinstance(value, str):
        lookup = {"low": 0.35, "medium": 0.6, "high": 0.85, "baja": 0.35, "media": 0.6, "alta": 0.85}
        if value.lower().strip() in lookup:
            return lookup[value.lower().strip()]
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.0, min(1.0, parsed))


def _segment_chunk_id(segment: DocumentSegment) -> str:
    metadata = getattr(segment, "metadata", {}) or {}
    return _as_text(metadata.get("chunk_id") or segment.id)


def _source_reference(segment: DocumentSegment) -> dict[str, Any]:
    metadata = getattr(segment, "metadata", {}) or {}
    raw_text = _as_text(getattr(segment, "raw_text", ""))
    quote = raw_text[:280]
    if len(raw_text) > 280:
        quote += "..."
    return {
        "source_id": getattr(segment, "source_id", ""),
        "source_name": _as_text(metadata.get("file_name")),
        "segment_id": getattr(segment, "id", ""),
        "chunk_id": _segment_chunk_id(segment),
        "section_path": _as_text(metadata.get("section_path") or getattr(segment, "section", "")),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "char_start": metadata.get("char_start", getattr(segment, "start_offset", 0)),
        "char_end": metadata.get("char_end", getattr(segment, "end_offset", 0)),
        "quote_excerpt": quote,
        "extraction_method": _as_text(metadata.get("extraction_method")),
    }


def _segment_payload(segment: DocumentSegment) -> dict[str, Any]:
    metadata = getattr(segment, "metadata", {}) or {}
    return {
        "segment_id": getattr(segment, "id", ""),
        "chunk_id": _segment_chunk_id(segment),
        "section": getattr(segment, "section", ""),
        "section_path": metadata.get("section_path", getattr(segment, "section", "")),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "char_start": metadata.get("char_start", getattr(segment, "start_offset", 0)),
        "char_end": metadata.get("char_end", getattr(segment, "end_offset", 0)),
        "text": getattr(segment, "raw_text", ""),
    }


def _find_forbidden_provider_id(payload: Any, path: str = "$") -> str | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}"
            if key_text.endswith("_id") and value:
                return next_path
            found = _find_forbidden_provider_id(value, next_path)
            if found:
                return found
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            found = _find_forbidden_provider_id(item, f"{path}[{index}]")
            if found:
                return found
    return None


def _candidate_type_for_kind(kind: str) -> str:
    mapping = {
        "entity": CandidateType.ENTIDAD.value,
        "branch": CandidateType.ENTIDAD.value,
        "relation": CandidateType.RELACION.value,
        "milestone": CandidateType.CAMBIO.value,
        "ring_suggestion": CandidateType.CAMBIO.value,
        "merge_suggestion": CandidateType.FUSION.value,
        "import_issue": CandidateType.INCIDENCIA.value,
    }
    return mapping.get(kind, CandidateType.FRAGMENTO_IMPORTADO.value)


def _title_for_payload(kind: str, payload: dict[str, Any]) -> str:
    return (
        _as_text(payload.get("title"))
        or _as_text(payload.get("name"))
        or _as_text(payload.get("ring_name"))
        or _as_text(payload.get("message"))
        or kind
    )


def _issue_candidate(segment: DocumentSegment, message: str, *, review_state: ImportReviewState) -> ImportCandidate:
    source_references = [_source_reference(segment)]
    payload = {
        "kind": "import_issue",
        "issue_type": "ai_import_extraction",
        "severity": "media",
        "message": message,
        "affected_source_references": source_references,
        "source_references": source_references,
        "suggested_fix": "Reintentar la extraccion IA o revisar manualmente el chunk.",
    }
    return ImportCandidate(
        id=_new_id(),
        segment_id=getattr(segment, "id", ""),
        candidate_type=CandidateType.INCIDENCIA.value,
        proposed_data=payload,
        confidence=0.0,
        review_state=review_state,
    )


IMPORT_EXTRACTION_SYSTEM_PROMPT = """\
Eres el extractor de importacion documental de Dendro.
Devuelve SOLO JSON valido. No incluyas Markdown ni explicaciones fuera del JSON.
No crees canon. No inventes IDs. Usa nombres cuando no exista un ID canonico.

JSON esperado:
{
  "candidates": [
    {
      "kind": "entity | branch | relation | milestone | ring_suggestion | merge_suggestion | import_issue",
      "name": "string opcional",
      "title": "string opcional",
      "summary": "string opcional",
      "body": "string opcional",
      "confidence": 0.0,
      "confidence_reason": "string",
      "aliases": ["string"],
      "entity_type": "personaje | localizacion | objeto | evento | concepto | otro",
      "branch_type": "faccion | cultura | institucion | trama | contenedor | otro",
      "source_name": "string para relaciones",
      "target_name": "string para relaciones",
      "relation_type": "string para relaciones",
      "date_label": "string para hitos",
      "structured_date": {},
      "evidence": "string",
      "message": "string para import_issue"
    }
  ]
}

Si el chunk es ambiguo o insuficiente, devuelve un candidate con kind import_issue.
"""


@dataclass
class ImportAIExtractionService:
    """Provider-backed structured extraction for import chunks."""

    provider: AIProvider | None = None
    allow_simulated: bool = False
    timeout_seconds: int = IMPORT_EXTRACTION_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.provider = self.provider or create_provider()

    def _provider_unconfigured_error(self) -> Error | None:
        provider_name = str(getattr(self.provider, "provider_name", "ai"))
        if provider_name == "simulated" and not self.allow_simulated:
            return Error("IA no configurada para extraccion de importacion; no se generara contenido simulado.")
        return None

    def extract_from_segments(
        self,
        segments: list[DocumentSegment],
        *,
        project_context: dict[str, Any] | None = None,
    ) -> Result[list[ImportCandidate], str]:
        """Analyze chunks and return reviewable import candidates."""

        unavailable = self._provider_unconfigured_error()
        if unavailable:
            return unavailable
        if not segments:
            return Ok([])

        candidates: list[ImportCandidate] = []
        for segment in segments:
            result = self._extract_segment(segment, project_context=project_context or {})
            if isinstance(result, Error):
                return result
            candidates.extend(result.value)
        return Ok(candidates)

    def extract_for_basket(
        self,
        basket: ImportBasket,
        *,
        project_context: dict[str, Any] | None = None,
        replace_existing: bool = False,
    ) -> Result[list[ImportCandidate], str]:
        """Analyze a basket and append reviewable candidates to it."""

        result = self.extract_from_segments(
            list(getattr(basket, "segments", []) or []),
            project_context=project_context,
        )
        if isinstance(result, Error):
            return result
        if replace_existing:
            basket.import_candidates = list(result.value)
        else:
            basket.import_candidates.extend(result.value)
        basket.updated_at = _now_iso()
        basket.metadata.setdefault("ai_extraction", {})
        basket.metadata["ai_extraction"].update({
            "provider": str(getattr(self.provider, "provider_name", "ai")),
            "candidate_count": len(result.value),
            "updated_at": basket.updated_at,
        })
        return result

    def _extract_segment(
        self,
        segment: DocumentSegment,
        *,
        project_context: dict[str, Any],
    ) -> Result[list[ImportCandidate], str]:
        gateway = AIRequestGateway(provider=self.provider)
        request = GatewayRequest(
            intent=IMPORT_EXTRACTION_INTENT,
            user_prompt=json.dumps({
                "task": "extract_reviewable_import_candidates",
                "chunk": _segment_payload(segment),
            }, ensure_ascii=False, default=str),
            context={
                "project_name": project_context.get("project_name", ""),
                "genre": project_context.get("genre", ""),
                "tone": project_context.get("tone", ""),
                "import_scope": "review_candidates_only",
            },
            system_prompt_override=IMPORT_EXTRACTION_SYSTEM_PROMPT,
            timeout=max(1, int(self.timeout_seconds or IMPORT_EXTRACTION_TIMEOUT_SECONDS)),
        )
        response = gateway.execute(request)
        if response.error:
            error_type = response.metadata.get("error_type")
            if error_type == "validation":
                return Ok([_issue_candidate(
                    segment,
                    f"Output IA malformado rechazado: {response.error}",
                    review_state=ImportReviewState.RECHAZADO,
                )])
            return Error(response.error)

        parsed = response.parsed_json
        if not isinstance(parsed, dict):
            return Ok([_issue_candidate(
                segment,
                "Output IA malformado rechazado: se esperaba un objeto JSON.",
                review_state=ImportReviewState.RECHAZADO,
            )])
        raw_candidates = parsed.get("candidates")
        if not isinstance(raw_candidates, list):
            return Ok([_issue_candidate(
                segment,
                "Output IA malformado rechazado: falta la lista candidates.",
                review_state=ImportReviewState.RECHAZADO,
            )])

        candidates: list[ImportCandidate] = []
        for raw in raw_candidates:
            payload = _as_dict(raw)
            if not payload:
                candidates.append(_issue_candidate(
                    segment,
                    "Output IA malformado rechazado: candidate vacio o no-objeto.",
                    review_state=ImportReviewState.RECHAZADO,
                ))
                continue
            item = self._candidate_from_payload(segment, payload)
            candidates.append(item)
        return Ok(candidates)

    def _candidate_from_payload(self, segment: DocumentSegment, payload: dict[str, Any]) -> ImportCandidate:
        kind = _as_text(payload.get("kind")).lower()
        if kind not in {
            "entity",
            "branch",
            "relation",
            "milestone",
            "ring_suggestion",
            "merge_suggestion",
            "import_issue",
        }:
            return _issue_candidate(
                segment,
                f"Output IA malformado rechazado: kind no soportado ({kind or 'vacio'}).",
                review_state=ImportReviewState.RECHAZADO,
            )

        forbidden = _find_forbidden_provider_id(payload)
        if forbidden:
            return _issue_candidate(
                segment,
                f"Output IA rechazado: el provider intento inventar un ID en {forbidden}.",
                review_state=ImportReviewState.RECHAZADO,
            )

        source_references = [_source_reference(segment)]
        normalized = dict(payload)
        normalized["kind"] = kind
        normalized.setdefault("title", _title_for_payload(kind, normalized))
        normalized.setdefault("summary", _as_text(normalized.get("description") or normalized.get("body")))
        normalized.setdefault("source_references", source_references)
        normalized.setdefault("review_notes", [])
        normalized.setdefault("suggested_actions", [])
        normalized.setdefault("duplicate_candidates", [])
        normalized.setdefault("contradiction_candidates", [])
        normalized["source_references"] = source_references
        normalized["ai_extraction"] = {
            "provider": str(getattr(self.provider, "provider_name", "ai")),
            "intent": IMPORT_EXTRACTION_INTENT,
        }

        return ImportCandidate(
            id=_new_id(),
            segment_id=getattr(segment, "id", ""),
            candidate_type=_candidate_type_for_kind(kind),
            proposed_data=normalized,
            proposed_relations=_as_list(normalized.get("proposed_relations")),
            confidence=_confidence(normalized.get("confidence"), 0.5),
            possible_duplicates=[],
            possible_contradictions=[],
            review_state=ImportReviewState.PENDIENTE,
        )

