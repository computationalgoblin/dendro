"""I20 — Agrupado de segmentos en ventanas para extracción IA.

El chunker de I02 trocea por párrafo, generando miles de segmentos diminutos en
documentos grandes. Hacer una llamada IA por párrafo no escala (2776 párrafos ≈
2776 round-trips). La extracción agrupa párrafos adyacentes en ventanas de ~N
caracteres → MUCHAS menos llamadas, conservando procedencia y candidatos ricos.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from packages.application.import_ai_extraction_service import (
    IMPORT_EXTRACTION_WINDOW_CHARS,
    ImportAIExtractionService,
    _window_segments,
    resolve_import_concurrency,
)
from packages.domain.import_models import DocumentSegment
from packages.domain.result import is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider


class _CountingProvider(AIProvider):
    """Proveedor real-fake thread-safe que cuenta cuántas llamadas recibe."""

    provider_name = "i20_counting"

    def __init__(self, *, name_for_call=None, delay: float = 0.0):
        self.calls = 0
        self._lock = threading.Lock()
        self._name_for_call = name_for_call
        self._delay = delay

    def chat(self, system_prompt, user_message, timeout=None):
        if self._delay:
            time.sleep(self._delay)
        with self._lock:
            self.calls += 1
            call_index = self.calls
        name = self._name_for_call(call_index) if self._name_for_call else "Eldrin"
        return json.dumps({
            "candidates": [{
                "kind": "entity",
                "name": name,
                "entity_type": "personaje",
                "summary": "Mago del Norte.",
                "body": "Custodia la Torre de Marfil.",
                "confidence": 0.8,
            }]
        }, ensure_ascii=False), None


def _small_segments(count: int, *, chars: int = 200) -> list[DocumentSegment]:
    segments = []
    for i in range(count):
        start = i * chars
        segments.append(DocumentSegment(
            id=f"seg-{i:04d}",
            source_id="src-1",
            section=f"Párrafo {i}",
            raw_text="x" * chars,
            start_offset=start,
            end_offset=start + chars,
            metadata={"char_start": start, "char_end": start + chars, "chunk_id": f"src-1-chunk-{i:04d}"},
        ))
    return segments


@pytest.mark.application
def test_window_collapses_many_paragraphs_into_few():
    # 100 párrafos de 200 chars = 20.000 chars → ~4 ventanas con cota 5000.
    segments = _small_segments(100, chars=200)
    windows = _window_segments(segments, IMPORT_EXTRACTION_WINDOW_CHARS)
    assert len(windows) < 10
    # La unión de las ventanas abarca todo el rango de offsets original.
    assert windows[0].start_offset == segments[0].start_offset
    assert windows[-1].end_offset == segments[-1].end_offset


@pytest.mark.application
def test_extraction_makes_one_call_per_window_not_per_segment():
    segments = _small_segments(100, chars=200)
    provider = _CountingProvider()
    svc = ImportAIExtractionService(provider=provider)  # window_chars por defecto
    result = svc.extract_from_segments(segments)
    assert is_ok(result)
    # Sin ventanas serían 100 llamadas; con ventanas, un puñado.
    assert provider.calls < 10
    assert provider.calls >= 1
    # Cada ventana sigue produciendo candidatos ricos.
    cands = unwrap(result)
    assert cands
    assert cands[0].proposed_data.get("body")


@pytest.mark.application
def test_oversized_segment_keeps_its_own_window():
    # Un párrafo gigante (> cota) no se parte: ocupa su propia ventana.
    big = DocumentSegment(id="big", source_id="s", raw_text="y" * 9000, start_offset=0, end_offset=9000)
    small = DocumentSegment(id="small", source_id="s", raw_text="z" * 100, start_offset=9000, end_offset=9100)
    windows = _window_segments([big, small], 5000)
    assert len(windows) == 2
    assert windows[0].id == "big"


@pytest.mark.application
def test_windowing_disabled_keeps_one_per_segment():
    segments = _small_segments(5, chars=100)
    windows = _window_segments(segments, 0)
    assert len(windows) == 5


@pytest.mark.application
def test_window_progress_reports_over_windows():
    segments = _small_segments(40, chars=200)
    provider = _CountingProvider()
    svc = ImportAIExtractionService(provider=provider)
    seen: list[tuple[int, int]] = []
    svc.extract_from_segments(segments, progress_callback=lambda done, total, label: seen.append((done, total)))
    # total reportado = nº de ventanas, no 40.
    assert seen
    total = seen[-1][1]
    assert total < 40
    assert seen[-1] == (total, total)  # cierre "completado"


# ── Chunking smart: ventanas conscientes de encabezados markdown ──────────────


def _heading(idx: int, start: int) -> DocumentSegment:
    return DocumentSegment(
        id=f"h-{idx}", source_id="s", section=f"Sección {idx}", raw_text=f"# Sección {idx}",
        start_offset=start, end_offset=start + 12,
        metadata={"block_type": "heading", "char_start": start, "char_end": start + 12},
    )


def _para(idx: int, start: int, chars: int = 100) -> DocumentSegment:
    return DocumentSegment(
        id=f"p-{idx}", source_id="s", section="cuerpo", raw_text="w" * chars,
        start_offset=start, end_offset=start + chars,
        metadata={"block_type": "paragraph", "char_start": start, "char_end": start + chars},
    )


@pytest.mark.application
def test_heading_starts_a_new_window():
    # Dos secciones pequeñas que cabrían juntas por tamaño: el encabezado fuerza corte.
    segments = [
        _heading(1, 0), _para(1, 12, 100), _para(2, 112, 100),
        _heading(2, 212), _para(3, 224, 100),
    ]
    windows = _window_segments(segments, IMPORT_EXTRACTION_WINDOW_CHARS)
    assert len(windows) == 2  # una ventana por sección, no una sola por tamaño
    # Cada ventana arranca con su encabezado.
    assert windows[0].raw_text.startswith("# Sección 1")
    assert windows[1].raw_text.startswith("# Sección 2")


# ── Paralelismo ───────────────────────────────────────────────────────────────


@pytest.mark.application
def test_concurrent_preserves_output_order():
    # Cada ventana produce un candidato con nombre = orden de FINALIZACIÓN, pero la
    # salida debe ordenarse por índice de ventana. Con delays inversos forzamos que
    # las últimas ventanas terminen antes.
    segments = _small_segments(6, chars=6000)  # cada párrafo > cota → 1 ventana c/u
    windows = _window_segments(segments, IMPORT_EXTRACTION_WINDOW_CHARS)
    assert len(windows) == 6
    seq_provider = _CountingProvider(name_for_call=lambda i: f"ent-{i}")
    seq = ImportAIExtractionService(provider=seq_provider, max_workers=1)
    seq_names = [c.proposed_data["name"] for c in unwrap(seq.extract_from_segments(segments))]

    par_provider = _CountingProvider(name_for_call=lambda i: f"ent-{i}")
    par = ImportAIExtractionService(provider=par_provider, max_workers=4)
    result = par.extract_from_segments(segments)
    assert is_ok(result)
    par_cands = unwrap(result)
    # Mismo nº de candidatos y mismas llamadas que secuencial.
    assert len(par_cands) == len(seq_names) == 6
    assert par_provider.calls == 6


@pytest.mark.application
def test_concurrent_runs_faster_than_sequential():
    segments = _small_segments(8, chars=6000)  # 8 ventanas
    delay = 0.05
    seq = ImportAIExtractionService(provider=_CountingProvider(delay=delay), max_workers=1)
    par = ImportAIExtractionService(provider=_CountingProvider(delay=delay), max_workers=8)

    t0 = time.perf_counter()
    unwrap(seq.extract_from_segments(segments))
    seq_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    unwrap(par.extract_from_segments(segments))
    par_elapsed = time.perf_counter() - t0

    # 8 ventanas en paralelo ≈ 1 delay; en serie ≈ 8 delays. Margen amplio.
    assert par_elapsed < seq_elapsed / 2


@pytest.mark.application
def test_concurrent_cancel_returns_partial():
    segments = _small_segments(20, chars=6000)
    provider = _CountingProvider(delay=0.02)
    svc = ImportAIExtractionService(provider=provider, max_workers=4)
    # Cancela tras las primeras finalizaciones.
    state = {"done": 0}

    def should_cancel():
        return state["done"] >= 2

    def progress(done, total, label):
        state["done"] = done

    result = svc.extract_from_segments(segments, progress_callback=progress, should_cancel=should_cancel)
    assert is_ok(result)
    # Devuelve lo acumulado, no las 20 ventanas.
    assert len(unwrap(result)) < 20


@pytest.mark.application
def test_resolve_concurrency_from_env(monkeypatch):
    monkeypatch.delenv("NARRATIVE_IMPORT_MAX_WORKERS", raising=False)
    assert resolve_import_concurrency() >= 1
    monkeypatch.setenv("NARRATIVE_IMPORT_MAX_WORKERS", "8")
    assert resolve_import_concurrency() == 8
    monkeypatch.setenv("NARRATIVE_IMPORT_MAX_WORKERS", "999")
    assert resolve_import_concurrency() == 16  # acotado
    monkeypatch.setenv("NARRATIVE_IMPORT_MAX_WORKERS", "basura")
    assert resolve_import_concurrency() >= 1  # default ante valor inválido
