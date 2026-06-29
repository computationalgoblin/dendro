"""I11-F3 — re-troceado opt-in de baskets ya importados.

Re-empaqueta los segmentos persistidos con el chunker de tamaño objetivo, sin el
documento original, losless. Sube `chunking_version` a 2 y regenera ids.
"""

from __future__ import annotations

from pathlib import Path

from packages.application.import_service import ImportService
from packages.domain.import_models import DocumentSegment, ImportBasket
from packages.domain.project import Project
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.text_extractor import repack_segments


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i21.json")


def _legacy_segments(n=4, chars=120):
    segs = []
    for i in range(n):
        start = i * chars
        segs.append(DocumentSegment(
            id=f"src-chunk-{i:04d}", source_id="src", section=f"P{i}",
            raw_text="x" * chars, start_offset=start, end_offset=start + chars,
            metadata={"chunk_id": f"src-chunk-{i:04d}", "chunk_order": i + 1,
                      "block_type": "paragraph", "section_path": f"P{i}",
                      "chunking_version": 1, "file_name": "lore.txt", "format": "text_plain",
                      "extraction_method": "plain_text"},
        ))
    return segs


# ── repack_segments (infraestructura) ─────────────────────────────────────────


def test_repack_merges_and_stamps_version():
    packed = repack_segments(_legacy_segments(4, 120))
    # 4 párrafos cortos (~480 chars) caben bajo el objetivo → un segmento.
    assert len(packed) == 1
    assert packed[0].metadata["chunking_version"] == 2
    assert packed[0].id == packed[0].metadata["chunk_id"]
    # Sin pérdida de texto.
    assert packed[0].raw_text.count("x") == 480


def test_repack_empty_is_safe():
    assert repack_segments([]) == []


def test_repack_preserves_source_and_format():
    packed = repack_segments(_legacy_segments(2))
    assert packed[0].source_id == "src"
    assert packed[0].metadata["format"] == "text_plain"
    assert packed[0].metadata["file_name"] == "lore.txt"


# ── ImportService.rechunk_basket (aplicación) ─────────────────────────────────


def _service_with_basket(segments):
    proj = Project(name="I21")
    basket = ImportBasket(id="b1", source_id="src", segments=segments, import_candidates=[],
                          review_state="pendiente", import_mode="canon", metadata={})
    proj.import_baskets = [basket]
    return ImportService(project_service=FakeProjectService(proj)), proj, basket


def test_rechunk_basket_replaces_segments():
    svc, _proj, basket = _service_with_basket(_legacy_segments(4, 120))
    result = svc.rechunk_basket("b1")
    assert is_ok(result)
    assert unwrap(result) == 1
    assert len(basket.segments) == 1
    assert basket.segments[0].metadata["chunking_version"] == 2
    assert basket.metadata.get("rechunked_at")


def test_rechunk_empty_basket_returns_zero():
    svc, _proj, _basket = _service_with_basket([])
    assert unwrap(svc.rechunk_basket("b1")) == 0


def test_rechunk_missing_basket_errors():
    svc, _proj, _basket = _service_with_basket(_legacy_segments(2))
    assert is_error(svc.rechunk_basket("nope"))
