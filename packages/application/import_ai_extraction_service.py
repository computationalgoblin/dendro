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
# I23 Fase 3: agrupacion estructural a nivel documento (ramas + membresia + anidamiento).
IMPORT_GROUPING_INTENT = "import_grouping"
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


def _framework_prompt_block(
    chronology_applied: dict[str, Any], world_layers: list[dict[str, Any]]
) -> str:
    """Bloque con el marco ya aplicado (calendario + anillos) para Fase 2.

    Permite a la IA datar el span existencial y asignar layer_ids contra estructuras
    reales. Devuelve "" si no hay marco (comportamiento histórico, sin datación dirigida).
    """
    chronology_applied = _as_dict(chronology_applied)
    block: list[str] = []
    present = chronology_applied.get("present_year")
    eras = _as_list(chronology_applied.get("eras"))
    if present is not None or eras:
        lines: list[str] = ["MARCO TEMPORAL (data las entidades contra este calendario):"]
        cal = _as_text(chronology_applied.get("calendar_name"))
        if cal:
            lines.append(f"- calendario: {cal}")
        if present is not None:
            lines.append(f"- año presente: {present}")
        for era in eras:
            era = _as_dict(era)
            name = _as_text(era.get("name"))
            if not name:
                continue
            start, end = era.get("start_year"), era.get("end_year")
            lines.append(f"- era '{name}': {start}..{end if end is not None else 'abierta'}")
        block.extend(lines)
    rings = [r for r in (world_layers or []) if isinstance(r, dict) and _as_text(r.get("id"))]
    if rings:
        block.append("ANILLOS DISPONIBLES (asigna layer_ids eligiendo de estos ids):")
        for ring in rings:
            rid = _as_text(ring.get("id"))
            name = _as_text(ring.get("name"))
            role = _as_text(ring.get("causal_role"))
            label = f"- {rid} ({name})"
            if role:
                label += f" — {role}"
            block.append(label)
    return ("\n".join(block)).strip()


def _build_import_system_prompt(
    taxonomy: dict[str, Any],
    canon_digest: dict[str, Any],
    lang: str = "es",
    *,
    chronology_applied: dict[str, Any] | None = None,
    world_layers: list[dict[str, Any]] | None = None,
) -> str:
    base = get_prompt(IMPORT_EXTRACTION_INTENT, lang) or ""
    parts = [base]
    block = _taxonomy_prompt_block(taxonomy, canon_digest)
    if block:
        parts.append(block)
    framework = _framework_prompt_block(chronology_applied or {}, world_layers or [])
    if framework:
        parts.append(framework)
    return "\n\n".join(parts)


def _build_grouping_system_prompt(
    world_layers: list[dict[str, Any]] | None = None, lang: str = "es"
) -> str:
    """System prompt de la pasada de agrupación (I23 Fase 3).

    Reusa el bloque ANILLOS DISPONIBLES de ``_framework_prompt_block`` (sin marco
    temporal: a la rama solo le interesan los anillos para clasificarla).
    """
    base = get_prompt(IMPORT_GROUPING_INTENT, lang) or ""
    parts = [base]
    rings = _framework_prompt_block({}, world_layers or [])
    if rings:
        parts.append(rings)
    return "\n\n".join(parts)


_KNOWN_BRANCH_TYPES = {"faccion", "cultura", "religion", "institucion", "trama", "contenedor"}


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


# I24: marcadores de un rechazo POR CONTENIDO del proveedor (filtro de seguridad).
# Un 400 con estos términos NO es sistémico: solo afecta a esa sección (ficción de
# tono oscuro, etc.). Se omite la sección y se sigue; cualquier otro error de proveedor
# (auth, max_tokens, conexión, 429, modelo…) se considera sistémico y corta con progreso.
_CONTENT_REJECTION_MARKERS = (
    "unsafe", "sensitive content", "potentially unsafe", "content policy",
    "content_filter", "content filter", "contenido sensible", "safety",
)


def _is_content_rejection(error: str) -> bool:
    low = str(error or "").lower()
    return any(marker in low for marker in _CONTENT_REJECTION_MARKERS)


def _window_key(window: DocumentSegment) -> str:
    """Clave estable de una ventana para reanudar sin repetir trabajo.

    Las ventanas se recomputan de ``basket.segments`` (que no cambian tras importar),
    así que esta clave es estable entre ejecuciones. Para ventanas fundidas usa los ids
    de sus segmentos constituyentes; para una sola, su id."""
    metadata = getattr(window, "metadata", {}) or {}
    ids = metadata.get("window_segment_ids")
    if isinstance(ids, list) and ids:
        return ",".join(str(i) for i in ids)
    return str(getattr(window, "id", "") or "")


def _issue_candidate(
    segment: DocumentSegment,
    message: str,
    *,
    review_state: ImportReviewState,
    issue_type: str = "ai_import_extraction",
    suggested_fix: str = "Reintentar la extraccion IA o revisar manualmente el chunk.",
) -> ImportCandidate:
    source_references = [_source_reference(segment)]
    payload = {
        "kind": "import_issue",
        "issue_type": issue_type,
        "severity": "media",
        "message": message,
        "affected_source_references": source_references,
        "source_references": source_references,
        "suggested_fix": suggested_fix,
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
        completed_keys: set[str] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Result[list[ImportCandidate], str]:
        """Analyze chunks and return reviewable import candidates.

        ``progress_callback(done, total, label)`` se invoca por segmento para dar
        feedback ("Analizando 3/12"). ``should_cancel()`` permite cancelar entre
        segmentos: se devuelve lo acumulado hasta el corte.

        I24 (resiliente + reanudable):
        - ``completed_keys`` (claves de ventana ya procesadas en ejecuciones previas)
          se SALTAN: sus candidatos ya están en el basket.
        - ``state`` (dict mutable de salida) recoge ``completed_keys`` (las terminadas
          ahora), ``aborted``/``abort_reason`` (si un error sistémico cortó) y
          ``total_windows``. Un error de proveedor NO sistémico ya llega como incidencia
          (no aborta); uno sistémico corta pero conserva el progreso parcial.
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
        if state is not None:
            state["total_windows"] = len(windows)
        already = set(completed_keys or ())
        pending = [w for w in windows if _window_key(w) not in already]
        if not pending:
            return Ok([])
        if self.max_workers and self.max_workers > 1 and len(pending) > 1:
            return self._extract_windows_concurrent(
                pending,
                project_context=project_context or {},
                progress_callback=progress_callback,
                should_cancel=should_cancel,
                state=state,
            )

        candidates: list[ImportCandidate] = []
        total = len(pending)
        for index, segment in enumerate(pending):
            if should_cancel is not None and should_cancel():
                break
            if progress_callback is not None:
                label = _as_text(getattr(segment, "section", "")) or f"ventana {index + 1}"
                progress_callback(index, total, label)
            result = self._extract_segment(segment, project_context=project_context or {})
            if isinstance(result, Error):
                # Sistémico: corta pero conserva lo acumulado (reanudable). La ventana
                # NO se marca completada → se reintentará al reanudar.
                if state is not None:
                    state["aborted"] = True
                    state["abort_reason"] = str(result.error)
                break
            candidates.extend(result.value)
            if state is not None:
                state.setdefault("completed_keys", set()).add(_window_key(segment))
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
        state: dict[str, Any] | None = None,
    ) -> Result[list[ImportCandidate], str]:
        """Extrae varias ventanas en paralelo conservando el orden de salida.

        Las llamadas al proveedor corren en un pool de hilos; el consumo de
        resultados (``progress_callback``/``should_cancel``) ocurre en este hilo,
        así que no necesitan ser thread-safe. La salida se reordena por índice de
        ventana → determinista pese al orden de finalización. I24: ante un error
        SISTÉMICO se cancelan las pendientes pero se CONSERVA lo ya obtenido (parcial
        reanudable); las ventanas Ok se marcan completadas en ``state``.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(windows)
        slices: list[list[ImportCandidate] | None] = [None] * total
        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        abort_reason: str | None = None
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
                    abort_reason = str(result.error)
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                slices[index] = result.value
                if state is not None:
                    state.setdefault("completed_keys", set()).add(_window_key(windows[index]))
                done += 1
                if progress_callback is not None:
                    label = _as_text(getattr(windows[index], "section", "")) or f"ventana {index + 1}"
                    progress_callback(done, total, label)
        finally:
            executor.shutdown(wait=True)

        candidates: list[ImportCandidate] = []
        for chunk in slices:
            if chunk:
                candidates.extend(chunk)
        if abort_reason is not None:
            if state is not None:
                state["aborted"] = True
                state["abort_reason"] = abort_reason
        elif progress_callback is not None:
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
        """Analyze a basket and append reviewable candidates to it.

        I24: resiliente + reanudable. Salta las ventanas ya completadas en
        ejecuciones previas (``basket.metadata['ai_extraction']['completed_window_keys']``)
        y registra el progreso para poder reanudar. Un error sistémico corta pero
        conserva (y persiste) lo extraído hasta ese punto.
        """
        prior = _as_dict(getattr(basket, "metadata", {}).get("ai_extraction"))
        completed_keys = {str(k) for k in (prior.get("completed_window_keys") or [])}
        state: dict[str, Any] = {"completed_keys": set(completed_keys)}

        result = self.extract_from_segments(
            list(getattr(basket, "segments", []) or []),
            project_context=project_context,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
            completed_keys=completed_keys,
            state=state,
        )
        if isinstance(result, Error):
            # Solo errores de arranque (proveedor no configurado): nada que persistir.
            return result

        new_candidates = list(result.value)
        # Al REANUDAR (hay ventanas completadas previas) SIEMPRE se hace append: nunca
        # se pisa el progreso, aunque el llamante pida replace_existing.
        if replace_existing and not completed_keys:
            basket.import_candidates = new_candidates
        else:
            basket.import_candidates.extend(new_candidates)

        basket.updated_at = _now_iso()
        all_completed = sorted(str(k) for k in (state.get("completed_keys") or set()))
        total_windows = int(state.get("total_windows") or len(all_completed))
        skipped_sections = sum(
            1 for c in basket.import_candidates
            if _as_dict(getattr(c, "proposed_data", {})).get("issue_type") == "ai_content_rejected"
        )
        meta = basket.metadata.setdefault("ai_extraction", {})
        meta.update({
            "provider": str(getattr(self.provider, "provider_name", "ai")),
            "candidate_count": len(basket.import_candidates),
            "completed_window_keys": all_completed,
            "total_windows": total_windows,
            "pending_sections": max(0, total_windows - len(all_completed)),
            "extracted_last_run": len(new_candidates),
            "skipped_sections": skipped_sections,
            "aborted": bool(state.get("aborted")),
            "abort_reason": str(state.get("abort_reason") or ""),
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
        chronology_applied = _as_dict(project_context.get("chronology_applied"))
        world_layers = _as_list(project_context.get("world_layers"))
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
            system_prompt_override=_build_import_system_prompt(
                taxonomy,
                canon_digest,
                lang,
                chronology_applied=chronology_applied,
                world_layers=world_layers,
            ),
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
            # I24: un rechazo POR CONTENIDO (filtro del proveedor) afecta solo a esta
            # sección → incidencia revisable y SE SIGUE con el resto del documento.
            if _is_content_rejection(response.error):
                return Ok([_issue_candidate(
                    segment,
                    "El proveedor rechazó esta sección por su filtro de contenido: "
                    f"{response.error}",
                    review_state=ImportReviewState.PENDIENTE,
                    issue_type="ai_content_rejected",
                    suggested_fix=(
                        "Revisa la sección manualmente o reanaliza con un proveedor sin "
                        "filtro de contenido."
                    ),
                )])
            # Cualquier otro error de proveedor es sistémico → corta (con progreso).
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

    # ── I23 Fase 3: agrupación estructural en ramas ──────────────────────────
    def propose_branches_for_basket(
        self,
        basket: ImportBasket,
        *,
        project_context: dict[str, Any] | None = None,
    ) -> Result[list[ImportCandidate], str]:
        """Agrupa las entidades ya extraídas en ramas y AÑADE candidatos al basket.

        Una sola llamada IA a nivel documento sobre el conjunto de hojas/ramas
        extraídas. La respuesta se EXPANDE en candidatos revisables: una entidad
        contenedora por rama + una relación ``contiene`` por miembro y por
        anidamiento (rama→subrama). Reutiliza el pipeline de relaciones (la
        ``contiene`` resuelve sus extremos por nombre al aceptar). Degrada con
        claridad si no hay proveedor; si no hay entidades agrupables, no añade nada.
        """
        unavailable = self._provider_unconfigured_error()
        if unavailable:
            return unavailable
        project_context = _as_dict(project_context)

        entities = self._grouping_inputs(basket)
        if not entities:
            return Ok([])

        world_layers = _as_list(project_context.get("world_layers"))
        gateway = AIRequestGateway(provider=self.provider)
        request = GatewayRequest(
            intent=IMPORT_GROUPING_INTENT,
            user_prompt=json.dumps({
                "task": "group_entities_into_branches",
                "entities": entities,
            }, ensure_ascii=False, default=str),
            context={
                "project_name": project_context.get("project_name", ""),
                "import_scope": "review_candidates_only",
            },
            system_prompt_override=_build_grouping_system_prompt(world_layers),
            timeout=max(1, int(self.timeout_seconds or IMPORT_EXTRACTION_TIMEOUT_SECONDS)),
        )
        response = gateway.execute(request)
        if response.error:
            return Error(response.error)
        parsed = response.parsed_json
        if not isinstance(parsed, dict):
            return Error("Output IA de agrupación malformado: se esperaba un objeto JSON.")

        source_ref = {
            "source_id": getattr(basket, "source_id", ""),
            "extraction_method": IMPORT_GROUPING_INTENT,
        }
        new_candidates = self._expand_branches(
            _as_list(parsed.get("branches")), world_layers, source_ref
        )
        if new_candidates:
            basket.import_candidates.extend(new_candidates)
            basket.updated_at = _now_iso()
            basket.metadata.setdefault("ai_grouping", {})
            basket.metadata["ai_grouping"].update({
                "provider": str(getattr(self.provider, "provider_name", "ai")),
                "branch_candidate_count": sum(
                    1 for c in new_candidates
                    if c.candidate_type == CandidateType.ENTIDAD.value
                ),
                "updated_at": basket.updated_at,
            })
        return Ok(new_candidates)

    def _grouping_inputs(self, basket: ImportBasket) -> list[dict[str, Any]]:
        """Resumen compacto de las hojas/ramas ya extraídas (insumo de la pasada).

        Excluye incidencias y candidatos descartados/fusionados; expone solo lo que
        el agrupador necesita para decidir membresía (nombre/tipo/brief/body)."""
        out: list[dict[str, Any]] = []
        for cand in list(getattr(basket, "import_candidates", []) or []):
            data = _as_dict(getattr(cand, "proposed_data", {}))
            kind = _as_text(data.get("kind")).lower()
            if kind not in {"entity", "branch"}:
                continue
            state = getattr(cand, "review_state", None)
            if state in (ImportReviewState.RECHAZADO, ImportReviewState.FUSIONADO):
                continue
            name = _as_text(data.get("name") or data.get("title"))
            if not name:
                continue
            out.append({
                "name": name,
                "type": _as_text(data.get("entity_type") or data.get("branch_type")),
                "is_branch": kind == "branch",
                "brief": _as_text(data.get("summary") or data.get("brief_description")),
                "body": _as_text(data.get("body") or data.get("description"))[:600],
            })
        return out

    def _expand_branches(
        self,
        branches: list[Any],
        world_layers: list[dict[str, Any]],
        source_ref: dict[str, Any],
    ) -> list[ImportCandidate]:
        """Expande la salida de agrupación en candidatos branch + relaciones contiene."""
        valid_layer_ids = {
            _as_text(r.get("id"))
            for r in world_layers
            if isinstance(r, dict) and _as_text(r.get("id"))
        }
        out: list[ImportCandidate] = []
        seen_contiene: set[tuple[str, str]] = set()

        def _add_contiene(container: str, member: str) -> None:
            if not container or not member or container.strip().lower() == member.strip().lower():
                return
            key = (container.strip().lower(), member.strip().lower())
            if key in seen_contiene:
                return
            seen_contiene.add(key)
            out.append(self._make_contiene_candidate(container, member, source_ref))

        for raw in branches:
            b = _as_dict(raw)
            name = _as_text(b.get("name"))
            if not name:
                continue
            btype = _as_text(b.get("branch_type")).lower() or "contenedor"
            if btype not in _KNOWN_BRANCH_TYPES:
                btype = "contenedor"
            layer_ids = [
                lid for lid in (_as_text(x) for x in _as_list(b.get("layer_ids"))) if lid
                and (not valid_layer_ids or lid in valid_layer_ids)
            ]
            out.append(self._make_branch_candidate(
                name, btype, _as_text(b.get("body")), layer_ids, source_ref
            ))
            for member in _as_list(b.get("members")):
                _add_contiene(name, _as_text(member))
            parent = _as_text(b.get("parent"))
            if parent and parent.lower() != "null":
                _add_contiene(parent, name)
        return out

    def _make_branch_candidate(
        self,
        name: str,
        branch_type: str,
        body: str,
        layer_ids: list[str],
        source_ref: dict[str, Any],
    ) -> ImportCandidate:
        summary = (body.split(".", 1)[0][:200] if body else "")
        normalized = {
            "kind": "branch",
            "name": name,
            "title": name,
            "branch_type": branch_type,
            "entity_type": branch_type,
            "summary": summary,
            "body": body,
            "layer_ids": list(layer_ids),
            "source_references": [source_ref],
            "ai_extraction": {
                "provider": str(getattr(self.provider, "provider_name", "ai")),
                "intent": IMPORT_GROUPING_INTENT,
            },
        }
        return ImportCandidate(
            id=_new_id(),
            segment_id="",
            candidate_type=CandidateType.ENTIDAD.value,
            proposed_data=normalized,
            confidence=0.6,
            review_state=ImportReviewState.PENDIENTE,
        )

    def _make_contiene_candidate(
        self, container_name: str, member_name: str, source_ref: dict[str, Any]
    ) -> ImportCandidate:
        normalized = {
            "kind": "relation",
            "title": f"{container_name} contiene {member_name}",
            "relation_type": "contiene",
            "source_name": container_name,
            "target_name": member_name,
            "summary": f"{container_name} contiene a {member_name}",
            "source_references": [source_ref],
            "ai_extraction": {
                "provider": str(getattr(self.provider, "provider_name", "ai")),
                "intent": IMPORT_GROUPING_INTENT,
            },
        }
        return ImportCandidate(
            id=_new_id(),
            segment_id="",
            candidate_type=CandidateType.RELACION.value,
            proposed_data=normalized,
            confidence=0.6,
            review_state=ImportReviewState.PENDIENTE,
        )

