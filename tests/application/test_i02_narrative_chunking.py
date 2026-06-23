from __future__ import annotations

from packages.domain.result import is_ok, unwrap
from packages.infrastructure.text_extractor import MarkdownExtractor, PlainTextExtractor


def test_i02_markdown_chunking_preserves_heading_hierarchy_lists_and_order(tmp_path):
    path = tmp_path / "setting.md"
    path.write_text(
        "# Corona Exterior\n"
        "Presenta las fuerzas lejanas.\n\n"
        "## Linajes\n"
        "- Casa Alba\n"
        "- Casa Umbria\n\n"
        "## Conflictos\n"
        "La frontera norte esta en disputa.\n",
        encoding="utf-8",
    )

    result = MarkdownExtractor().extract(path, "src-chunk")

    assert is_ok(result)
    segments = unwrap(result)
    assert [segment.metadata["chunk_order"] for segment in segments] == list(range(1, len(segments) + 1))
    assert [segment.metadata["block_type"] for segment in segments] == [
        "heading",
        "paragraph",
        "heading",
        "list",
        "heading",
        "paragraph",
    ]
    assert segments[0].raw_text == "# Corona Exterior"
    assert segments[3].raw_text == "- Casa Alba\n- Casa Umbria"
    assert segments[3].metadata["section_path"] == "Corona Exterior > Linajes"
    assert segments[5].metadata["section_path"] == "Corona Exterior > Conflictos"
    assert [segment.start_offset for segment in segments] == sorted(segment.start_offset for segment in segments)


def test_i02_plain_text_packs_by_target_size_and_splits_oversized(tmp_path):
    # I11: el troceado agrupa por tamaño objetivo y parte los párrafos gigantes
    # (> CHUNK_MAX_CHARS) por frontera, sin pérdida de texto.
    from packages.infrastructure.text_extractor import CHUNK_MAX_CHARS

    path = tmp_path / "long.txt"
    long_paragraph = "A" * 3000
    path.write_text(
        f"Escena larga\n{long_paragraph}\n\nNota final\nCierre breve.",
        encoding="utf-8",
    )

    result = PlainTextExtractor().extract(path, "src-long")

    assert is_ok(result)
    segments = unwrap(result)
    # El párrafo gigante se parte: más de un segmento, ninguno supera el tope.
    assert len(segments) >= 2
    assert all(len(s.raw_text) <= CHUNK_MAX_CHARS for s in segments)
    # Sin pérdida: las 3000 'A' siguen estando (repartidas entre sub-chunks).
    assert sum(s.raw_text.count("A") for s in segments) == 3000
    # chunk_order secuencial e invariante id == chunk_id.
    assert [s.metadata["chunk_order"] for s in segments] == list(range(1, len(segments) + 1))
    assert all(s.id == s.metadata["chunk_id"] for s in segments)

