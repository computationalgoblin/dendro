"""BETA2-WIKI-03: proyección determinista del índice de la wiki."""

import pytest

from packages.application.wiki_index_service import WikiIndexService
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryFreshness,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Ok
from packages.domain.world_layer import WorldLayer


def _project():
    p = Project(id="p", name="P")
    p.world_layers.append(
        WorldLayer(id="l_nar", name="Narrativa", metadata={"causal_rank": "13"})
    )
    p.world_layers.append(
        WorldLayer(id="l_fis", name="Física", metadata={"causal_rank": "3"})
    )
    ana = NarrativeEntity(id="e1", name="Ana", brief_description="Reina.", layer_ids=["l_nar"])
    beto = NarrativeEntity(id="e2", name="Beto", brief_description="Aliado.", layer_ids=["l_nar"])
    p.entities.extend([ana, beto])
    p.relations.append(NarrativeRelation(id="r1", source_id="e1", target_id="e2"))
    return p


@pytest.mark.application
def test_index_is_complete_even_without_pages():
    p = _project()
    idx = WikiIndexService().build_index(p)
    assert isinstance(idx, Ok)
    index = idx.value
    # Todo elemento canónico aparece: 2 anillos + 2 entidades + 1 relación.
    kinds = [e.kind for e in index.entries]
    assert kinds.count("ring") == 2
    assert kinds.count("entity") == 2
    assert kinds.count("relation") == 1
    # Sin páginas: todo sin_memoria y sin página.
    ana = index.entry_for("entity", "e1")
    assert ana.page_freshness == MemoryFreshness.SIN_MEMORIA.value
    assert ana.has_page is False
    # one_line derivada de la ficha (nombre + breve).
    assert "Ana" in ana.one_line and "Reina" in ana.one_line


@pytest.mark.application
def test_entity_carries_primary_ring_and_rank():
    p = _project()
    # Ana pertenece a dos anillos; el primario es el de menor rank causal (Física #3).
    p.entity_by_id("e1").layer_ids = ["l_nar", "l_fis"]
    index = WikiIndexService().build_index(p).value
    ana = index.entry_for("entity", "e1")
    assert ana.ring == "Física"
    assert ana.rank == 3


@pytest.mark.application
def test_one_line_uses_page_lead_when_present():
    p = _project()
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id="e1",
            resumen_editorial="Ana, reina en el exilio que conspira.",
            cuerpo="cuerpo largo",
            freshness=MemoryFreshness.REGADA,
        )
    )
    index = WikiIndexService().build_index(p).value
    ana = index.entry_for("entity", "e1")
    assert ana.one_line == "Ana, reina en el exilio que conspira."
    assert ana.page_freshness == MemoryFreshness.REGADA.value
    assert ana.has_page is True


@pytest.mark.application
def test_contextual_pages_do_not_represent_the_element():
    p = _project()
    # Una página contextual (context != "") no aporta el one_line del índice general.
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id="e1",
            context="guerra",
            resumen_editorial="Ana en tiempos de guerra.",
            freshness=MemoryFreshness.REGADA,
        )
    )
    index = WikiIndexService().build_index(p).value
    ana = index.entry_for("entity", "e1")
    assert ana.has_page is False
    assert "Reina" in ana.one_line  # sigue usando la ficha, no la página contextual


@pytest.mark.application
def test_relation_name_uses_entity_names():
    p = _project()
    index = WikiIndexService().build_index(p).value
    rel = index.entry_for("relation", "r1")
    assert "Ana" in rel.name and "Beto" in rel.name


@pytest.mark.application
def test_signature_changes_when_a_page_is_added():
    p = _project()
    svc = WikiIndexService()
    sig1 = svc.build_index(p).value.signature
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY, target_id="e1", resumen_editorial="lead"
        )
    )
    sig2 = svc.build_index(p).value.signature
    assert sig1 != sig2


@pytest.mark.application
def test_compact_for_prompt_is_bounded_and_flags_omissions():
    p = _project()
    index = WikiIndexService().build_index(p).value
    total = len(index.entries)
    compact = WikiIndexService().compact_for_prompt(index, max_entries=2)
    assert len(compact["entradas"]) == 2
    assert compact["omitidas"] == total - 2
    assert compact["conteos"]["entity"] == 2


@pytest.mark.application
def test_build_index_tolerates_no_project():
    idx = WikiIndexService().build_index(None)
    assert isinstance(idx, Ok)
    assert idx.value.entries == ()
