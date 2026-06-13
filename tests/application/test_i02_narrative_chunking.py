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


def test_i02_plain_text_chunks_by_paragraph_not_character_count(tmp_path):
    path = tmp_path / "long.txt"
    long_paragraph = "A" * 3000
    path.write_text(
        f"Escena larga\n{long_paragraph}\n\nNota final\nCierre breve.",
        encoding="utf-8",
    )

    result = PlainTextExtractor().extract(path, "src-long")

    assert is_ok(result)
    segments = unwrap(result)
    assert len(segments) == 2
    assert long_paragraph in segments[0].raw_text
    assert segments[0].metadata["chunk_order"] == 1
    assert segments[1].metadata["chunk_order"] == 2

