"""I11 — Chunking con tamaño objetivo: forma + comparación de retrieval.

Dos bloques:

1. **Forma de `_pack_chunks`**: fusiona párrafos cortos, parte gigantes por frase,
   no cruza encabezados/listas, sin pérdida de texto, offsets contiguos.
2. **Comparación de retrieval (proxy)**: un hecho repartido en varios párrafos
   cortos. Con el troceado NUEVO el hecho completo cae en un único chunk coherente;
   con el VIEJO queda fragmentado en varios registros del corpus. El ranking RAG
   real es trabajo futuro (tickets E); aquí se usa un ranker-proxy por solapamiento
   de términos sobre `index.items(IMPORT_DOCUMENT)` como medida de granularidad.
"""

from __future__ import annotations

import pytest

from packages.application.corpus_indexer import CorpusIndexer
from packages.application.narrative_rag_contract import CorpusItemKind
from packages.domain.import_models import ImportBasket
from packages.domain.project import Project
from packages.domain.result import unwrap
from packages.infrastructure.text_extractor import (
    CHUNK_MAX_CHARS,
    PlainTextExtractor,
    _pack_chunks,
    _TextChunk,
)

# ── Bloque 1: forma de _pack_chunks ───────────────────────────────────────────


def _para(text: str, start: int) -> _TextChunk:
    return _TextChunk(text=text, section=text[:10], start_offset=start,
                      end_offset=start + len(text), section_path=text[:10], block_type="paragraph")


def _heading(text: str, start: int) -> _TextChunk:
    return _TextChunk(text=text, section=text, start_offset=start, end_offset=start + len(text),
                      section_path=text, block_type="heading", heading_level=1)


def _list(text: str, start: int) -> _TextChunk:
    return _TextChunk(text=text, section="lista", start_offset=start,
                      end_offset=start + len(text), section_path="lista", block_type="list")


def test_pack_merges_short_paragraphs():
    chunks = [_para("Alfa.", 0), _para("Beta.", 10), _para("Gamma.", 20)]
    packed = _pack_chunks(chunks, target_chars=1200, max_chars=CHUNK_MAX_CHARS)
    assert len(packed) == 1
    assert "Alfa." in packed[0].text and "Gamma." in packed[0].text
    assert packed[0].start_offset == 0
    assert packed[0].end_offset == 26  # end del último


def test_pack_disabled_with_target_zero():
    chunks = [_para("Alfa.", 0), _para("Beta.", 10)]
    packed = _pack_chunks(chunks, target_chars=0, max_chars=CHUNK_MAX_CHARS)
    assert len(packed) == 2  # troceado histórico intacto


def test_pack_does_not_cross_heading_or_list():
    chunks = [
        _heading("# Sec", 0),
        _para("Cuerpo uno.", 6),
        _para("Cuerpo dos.", 20),
        _list("- a\n- b", 40),
        _para("Otro.", 60),
    ]
    packed = _pack_chunks(chunks, target_chars=1200, max_chars=CHUNK_MAX_CHARS)
    # heading | (cuerpo uno+dos fusionados) | list | otro = 4
    assert [c.block_type for c in packed] == ["heading", "paragraph", "list", "paragraph"]
    assert "Cuerpo uno." in packed[1].text and "Cuerpo dos." in packed[1].text


def test_pack_splits_oversized_paragraph_by_sentence():
    big = " ".join(f"Frase numero {i}." for i in range(400))  # >> max_chars
    chunks = [_para(big, 0)]
    packed = _pack_chunks(chunks, target_chars=1200, max_chars=CHUNK_MAX_CHARS)
    assert len(packed) >= 2
    assert all(len(c.text) <= CHUNK_MAX_CHARS for c in packed)
    # Sin pérdida de palabras de contenido.
    assert sum(c.text.count("Frase") for c in packed) == 400


def test_pack_preserves_text_without_loss():
    chunks = [_para("Uno dos tres.", 0), _para("Cuatro cinco.", 20)]
    packed = _pack_chunks(chunks, target_chars=1200, max_chars=CHUNK_MAX_CHARS)
    joined = " ".join(c.text for c in packed)
    for word in ("Uno", "dos", "tres", "Cuatro", "cinco"):
        assert word in joined


# ── Bloque 2: comparación de retrieval (proxy) ────────────────────────────────

_FACT_DOC = (
    "Granada es una ciudad del sur.\n\n"
    "En Granada se alza la Alhambra.\n\n"
    "La Alhambra fue un palacio.\n\n"
    "Granada fue capital del reino nazari.\n"
)
_QUERY_TERMS = ("granada", "alhambra", "palacio", "capital", "nazari")


def _index_with_target(tmp_path, monkeypatch, target: str):
    monkeypatch.setenv("NARRATIVE_CHUNK_TARGET_CHARS", target)
    doc = tmp_path / "granada.txt"
    doc.write_text(_FACT_DOC, encoding="utf-8")
    segments = unwrap(PlainTextExtractor().extract(doc, "src-granada"))
    project = Project(id="proj-i11", name="I11")
    project.import_baskets = [ImportBasket(
        id="basket-granada", source_id="src-granada", segments=segments,
        import_candidates=[], review_state="pendiente", import_mode="contexto",
        metadata={"file_path": str(doc), "import_mode": "contexto"},
    )]
    return CorpusIndexer().index_project(project)


def _coverage(text: str, terms) -> int:
    low = text.lower()
    return sum(1 for t in terms if t in low)


def _best_coverage(index, terms) -> int:
    records = index.items(CorpusItemKind.IMPORT_DOCUMENT)
    assert records, "el corpus debe tener registros de importación"
    return max(_coverage(r.rendered_text, terms) for r in records)


@pytest.mark.application
def test_new_chunking_keeps_fact_in_one_coherent_chunk(tmp_path, monkeypatch):
    # NUEVO (objetivo por defecto): los 4 párrafos cortos caben en un chunk →
    # el top-1 cubre TODOS los términos del hecho.
    index = _index_with_target(tmp_path, monkeypatch, "1200")
    assert _best_coverage(index, _QUERY_TERMS) == len(_QUERY_TERMS)


@pytest.mark.application
def test_old_chunking_fragments_the_fact(tmp_path, monkeypatch):
    # VIEJO (target=0, un chunk por párrafo): ningún registro cubre el hecho
    # completo; el mejor queda por debajo.
    index = _index_with_target(tmp_path, monkeypatch, "0")
    assert _best_coverage(index, _QUERY_TERMS) < len(_QUERY_TERMS)


@pytest.mark.application
def test_new_beats_old_on_fact_coverage(tmp_path, monkeypatch):
    new_cov = _best_coverage(_index_with_target(tmp_path, monkeypatch, "1200"), _QUERY_TERMS)
    old_cov = _best_coverage(_index_with_target(tmp_path, monkeypatch, "0"), _QUERY_TERMS)
    assert new_cov > old_cov
