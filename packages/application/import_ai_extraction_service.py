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
import os
import uuid

from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest
from packages.application.prompt_registry import get_prompt
from packages.domain.candidate_issue import CandidateType
from packages.domain.import_models import DocumentSegment, ImportBasket, ImportCandidate, ImportReviewState
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider, create_provider


def resolve_configured_provider() -> AIProvider:
    """Resuelve el proveedor IA configurado, igual que el resto de jobs.

    Lee ``NARRATIVE_AI_PROVIDER`` del entorno (que el host desktop espeja desde la
    config del usuario en ``AppContext._apply_ai_environment`` y el CLI desde
    variables de entorno). Sin configurar → simulado (la extracción lo bloquea).

    Antes se llamaba ``create_provider()`` sin argumentos, cuyo *default* es
    ``"simulated"``, por lo que SIEMPRE devolvía el simulado aunque el usuario
    tuviera IA configurada.
    """
    provider_name = os.environ.get("NARRATIVE_AI_PROVIDER", "simulated") or "simulated"
    return create_provider(provider_name)


IMPORT_EXTRACTION_INTENT = "import_extraction"
IMPORT_EXTRACTION_TIMEOUT_SECONDS = 300

# Objetivo de caracteres por *ventana* de extracción. Los chunkers de I02
# trocean por párrafo (línea en blanco), generando miles de segmentos diminutos
# en documentos grandes. Hacer una llamada IA por párrafo no escala (2776
# párrafos ≈ 2776 round-trips secuenciales). Agrupamos párrafos adyacentes hasta
# esta cota antes de extraer: 1 llamada por ventana, menos round-trips y mejor
# contexto para el modelo. La procedencia se conserva (la ventana abarca el rango
# char_start–char_end de sus párrafos).
IMPORT_EXTRACTION_WINDOW_CHARS = 5000

# Llamadas IA concurrentes por defecto (proveedores cloud aguantan paralelismo;
# un modelo local serializa igual, sin daño). Configurable por entorno con
# ``NARRATIVE_IMPORT_MAX_WORKERS``. El orden de salida es estable
# independientemente del orden de finalización.
IMPORT_EXTRACTION_MAX_WORKERS = 4


def resolve_import_concurrency() -> int:
    """Nº de llamadas IA concurrentes para la extracción de importación.

    Lee ``NARRATIVE_IMPORT_MAX_WORKERS`` del entorno; sin configurar usa
    ``IMPORT_EXTRACTION_MAX_WORKERS``. Acotado a [1, 16]. Pon ``1`` para forzar
    secuencial (p. ej. modelos locales que rechazan requests concurrentes).
    """
    raw = os.environ.get("NARRATIVE_IMPORT_MAX_WORKERS", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = IMPORT_EXTRACTION_MAX_WORKERS
    return max(1, min(value, 16))


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


def _merge_window(group: list[DocumentSegment]) -> DocumentSegment:
    """Funde varios segmentos adyacentes en uno solo para una única llamada IA.

    El segmento resultante concatena el texto, abarca el rango de offsets del
    primero al último y conserva la metadata del primero (file_name, section_path,
    chunk_id, extraction_method) actualizando char_start/char_end al rango total.
    Registra los ids/chunk_ids constituyentes en ``metadata['window_segment_ids']``
    para trazabilidad. Un grupo de uno se devuelve intacto (sin overhead).
    """
    if len(group) == 1:
        return group[0]
    first, last = group[0], group[-1]
    text = "\n\n".join(_as_text(getattr(seg, "raw_text", "")) for seg in group)
    metadata = dict(getattr(first, "metadata", {}) or {})
    char_start = metadata.get("char_start", getattr(first, "start_offset", 0))
    metadata["char_start"] = char_start
    metadata["char_end"] = (
        (getattr(last, "metadata", {}) or {}).get("char_end", getattr(last, "end_offset", 0))
    )
    metadata["window_segment_ids"] = [getattr(seg, "id", "") for seg in group]
    metadata["window_chunk_ids"] = [_segment_chunk_id(seg) for seg in group]
    metadata["window_size"] = len(group)
    return DocumentSegment(
        id=getattr(first, "id", ""),
        source_id=getattr(first, "source_id", ""),
        section=getattr(first, "section", ""),
        raw_text=text,
        start_offset=getattr(first, "start_offset", 0),
        end_offset=getattr(last, "end_offset", 0),
        confidence=min((getattr(seg, "confidence", 1.0) for seg in group), default=1.0),
        metadata=metadata,
    )


def _is_heading(segment: DocumentSegment) -> bool:
    """True si el segmento es un encabezado markdown (no texto de cuerpo)."""
    metadata = getattr(segment, "metadata", {}) or {}
    return _as_text(metadata.get("block_type")) == "heading"


def _window_segments(
    segments: list[DocumentSegment], max_chars: int
) -> list[DocumentSegment]:
    """Agrupa segmentos adyacentes en ventanas de ~``max_chars`` caracteres.

    Chunking smart (consciente de estructura):
      - Cada ventana se traduce en UNA llamada IA.
      - Se rompe la ventana cuando: (a) añadir el segmento excedería ``max_chars``,
        o (b) el segmento es un **encabezado** markdown → empieza ventana nueva con
        el encabezado a la cabeza, de modo que cada sección se analiza junta y con
        su título por delante (mejor procedencia y mejor contexto para el modelo).
      - Un segmento que por sí solo excede ``max_chars`` queda en su propia ventana
        (no se parte: respeta los límites del chunker).

    En texto plano (sin encabezados) degrada a puro agrupado por tamaño, que es
    justo lo que colapsa los miles de párrafos. ``max_chars <= 0`` desactiva el
    agrupado (una ventana por segmento).
    """
    if max_chars <= 0 or len(segments) <= 1:
        return list(segments)
    windows: list[DocumentSegment] = []
    current: list[DocumentSegment] = []
    current_len = 0
    for segment in segments:
        seg_len = len(_as_text(getattr(segment, "raw_text", "")))
        size_break = current and current_len + seg_len > max_chars
        heading_break = current and _is_heading(segment)
        if size_break or heading_break:
            windows.append(_merge_window(current))
            current = []
            current_len = 0
        current.append(segment)
        current_len += seg_len + 2  # separador "\n\n"
    if current:
        windows.append(_merge_window(current))
    return windows


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
        "ring_suggestion": CandidateType.ANILLO.value,
        "merge_suggestion": CandidateType.FUSION.value,
        "import_issue": CandidateType.INCIDENCIA.value,
    }
    return mapping.get(kind, CandidateType.FRAGMENTO_IMPORTADO.value)


def _str_set(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(v).strip().lower() for v in value if str(v).strip()}
    return set()


def _taxonomy_prompt_block(taxonomy: dict[str, Any], canon_digest: dict[str, Any]) -> str:
    """Bloque de texto inyectado al system prompt con la taxonomía + canon.

    Devuelve "" cuando no hay nada que acotar (comportamiento histórico).
    """
    taxonomy = _as_dict(taxonomy)
    canon_digest = _as_dict(canon_digest)
    lines: list[str] = []
    ents = _as_list(taxonomy.get("allowed_entity_types"))
    branches = _as_list(taxonomy.get("allowed_branch_types"))
    rings = _as_list(taxonomy.get("allowed_ring_ids"))
    guidance = _as_text(taxonomy.get("extraction_guidance"))
    if ents:
        lines.append(f"- entity_type permitidos: {', '.join(str(e) for e in ents)}")
    if branches:
        lines.append(f"- branch_type permitidos: {', '.join(str(b) for b in branches)}")
    if rings:
        lines.append(f"- anillos permitidos (ring_id): {', '.join(str(r) for r in rings)}")
    if guidance:
        lines.append(f"- guía de extracción: {guidance}")
    digest_lines: list[str] = []
    for label, key in (("Entidades", "entities"), ("Ramas", "branches"), ("Anillos", "rings")):
        names = _as_list(canon_digest.get(key))
        if names:
            digest_lines.append(f"- {label}: {', '.join(str(n) for n in names[:40])}")
    block: list[str] = []
    if lines:
        block.append("TAXONOMIA DEL PROYECTO (acota la extracción):")
        block.extend(lines)
    if digest_lines:
        block.append("CANON EXISTENTE (para desambiguar, no dupliques):")
        block.extend(digest_lines)
    return ("\n".join(block)).strip()


def _build_import_system_prompt(taxonomy: dict[str, Any], canon_digest: dict[str, Any], lang: str = "es") -> str:
    base = get_prompt(IMPORT_EXTRACTION_INTENT, lang) or ""
    block = _taxonomy_prompt_block(taxonomy, canon_digest)
    if block:
        return f"{base}\n\n{block}"
    return base


def _taxonomy_violation(kind: str, payload: dict[str, Any], taxonomy: dict[str, Any]) -> str | None:
    """Devuelve el motivo si el candidato viola la taxonomía, o None.

    Solo restringe cuando la lista correspondiente es no vacía.
    """
    taxonomy = _as_dict(taxonomy)
    if kind == "entity":
        allowed = _str_set(taxonomy.get("allowed_entity_types"))
        value = _as_text(payload.get("entity_type")).lower()
        if allowed and value and value not in allowed:
            return f"entity_type '{value}' fuera de la taxonomía del proyecto"
    elif kind == "branch":
        allowed = _str_set(taxonomy.get("allowed_branch_types"))
        value = _as_text(payload.get("branch_type")).lower()
        if allowed and value and value not in allowed:
            return f"branch_type '{value}' fuera de la taxonomía del proyecto"
    elif kind == "ring_suggestion":
        allowed = _str_set(taxonomy.get("allowed_ring_ids"))
        value = _as_text(payload.get("ring_id")).lower()
        if allowed and value and value not in allowed:
            return f"anillo '{value}' fuera de la taxonomía del proyecto"
    return None


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


@dataclass
class ImportAIExtractionService:
    """Provider-backed structured extraction for import chunks."""

    provider: AIProvider | None = None
    allow_simulated: bool = False
    timeout_seconds: int = IMPORT_EXTRACTION_TIMEOUT_SECONDS
    window_chars: int = IMPORT_EXTRACTION_WINDOW_CHARS
    max_workers: int = 1

    def __post_init__(self) -> None:
        self.provider = self.provider or resolve_configured_provider()

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
        progress_callback: Any = None,
        should_cancel: Any = None,
    ) -> Result[list[ImportCandidate], str]:
        """Analyze chunks and return reviewable import candidates.

        ``progress_callback(done, total, label)`` se invoca por segmento para dar
        feedback ("Analizando 3/12"). ``should_cancel()`` permite cancelar entre
        segmentos: se devuelve lo acumulado hasta el corte.
        """

        unavailable = self._provider_unconfigured_error()
        if unavailable:
            return unavailable
        if not segments:
            return Ok([])

        # Agrupar párrafos adyacentes en ventanas: 1 llamada IA por ventana en vez
        # de por párrafo. El progreso se reporta sobre ventanas (lo que el usuario
        # espera de verdad).
        windows = _window_segments(list(segments), self.window_chars)
        if self.max_workers and self.max_workers > 1 and len(windows) > 1:
            return self._extract_windows_concurrent(
                windows,
                project_context=project_context or {},
                progress_callback=progress_callback,
                should_cancel=should_cancel,
            )

        candidates: list[ImportCandidate] = []
        total = len(windows)
        for index, segment in enumerate(windows):
            if should_cancel is not None and should_cancel():
                break
            if progress_callback is not None:
                label = _as_text(getattr(segment, "section", "")) or f"ventana {index + 1}"
                progress_callback(index, total, label)
            result = self._extract_segment(segment, project_context=project_context or {})
            if isinstance(result, Error):
                return result
            candidates.extend(result.value)
        if progress_callback is not None:
            progress_callback(total, total, "completado")
        return Ok(candidates)

    def _extract_windows_concurrent(
        self,
        windows: list[DocumentSegment],
        *,
        project_context: dict[str, Any],
        progress_callback: Any = None,
        should_cancel: Any = None,
    ) -> Result[list[ImportCandidate], str]:
        """Extrae varias ventanas en paralelo conservando el orden de salida.

        Las llamadas al proveedor corren en un pool de hilos; el consumo de
        resultados (``progress_callback``/``should_cancel``) ocurre en este hilo,
        así que no necesitan ser thread-safe. La salida se reordena por índice de
        ventana → determinista pese al orden de finalización. Ante un error duro o
        cancelación se cancelan las ventanas pendientes y se devuelve lo acumulado
        (cancelación) o el error.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(windows)
        slices: list[list[ImportCandidate] | None] = [None] * total
        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        error: Error | None = None
        try:
            future_to_index = {
                executor.submit(
                    self._extract_segment, window, project_context=project_context
                ): index
                for index, window in enumerate(windows)
            }
            done = 0
            for future in as_completed(future_to_index):
                if should_cancel is not None and should_cancel():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                index = future_to_index[future]
                result = future.result()
                if isinstance(result, Error):
                    error = result
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                slices[index] = result.value
                done += 1
                if progress_callback is not None:
                    label = _as_text(getattr(windows[index], "section", "")) or f"ventana {index + 1}"
                    progress_callback(done, total, label)
        finally:
            executor.shutdown(wait=True)

        if error is not None:
            return error
        candidates: list[ImportCandidate] = []
        for chunk in slices:
            if chunk:
                candidates.extend(chunk)
        if progress_callback is not None:
            progress_callback(total, total, "completado")
        return Ok(candidates)

    def extract_for_basket(
        self,
        basket: ImportBasket,
        *,
        project_context: dict[str, Any] | None = None,
        replace_existing: bool = False,
        progress_callback: Any = None,
        should_cancel: Any = None,
    ) -> Result[list[ImportCandidate], str]:
        """Analyze a basket and append reviewable candidates to it."""

        result = self.extract_from_segments(
            list(getattr(basket, "segments", []) or []),
            project_context=project_context,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
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
        taxonomy = _as_dict(project_context.get("import_taxonomy"))
        canon_digest = _as_dict(project_context.get("canon_digest"))
        lang = _as_text(project_context.get("language")) or "es"
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
                "import_taxonomy": taxonomy,
            },
            system_prompt_override=_build_import_system_prompt(taxonomy, canon_digest, lang),
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
            item = self._candidate_from_payload(segment, payload, taxonomy=taxonomy)
            candidates.append(item)
        return Ok(candidates)

    def _candidate_from_payload(
        self,
        segment: DocumentSegment,
        payload: dict[str, Any],
        *,
        taxonomy: dict[str, Any] | None = None,
    ) -> ImportCandidate:
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

        # Validación contra la taxonomía del proyecto (Modo Canon dirigido).
        taxonomy = _as_dict(taxonomy)
        violation = _taxonomy_violation(kind, payload, taxonomy)
        if violation:
            strict = bool(taxonomy.get("strict"))
            # strict → se rechaza; permisivo → incidencia revisable (PENDIENTE).
            return _issue_candidate(
                segment,
                f"Candidato fuera de taxonomía: {violation}.",
                review_state=ImportReviewState.RECHAZADO if strict else ImportReviewState.PENDIENTE,
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

