"""BETA-CIERRE WS-L (B4): el índice de la wiki viaja ACOTADO en el prompt.

Sin tope, el índice completo se re-enviaba en cada ronda de navegación (coste de
entrada ilimitado, riesgo de desbordar el contexto en proyectos grandes). El tope
recorta lo que viaja, prioriza el foco, y lo omitido sigue siendo alcanzable por search.
"""

from __future__ import annotations

import pytest

from packages.application.project_service import ProjectService
from packages.application.wiki_index_service import WikiIndexService
from packages.application.wiki_navigator import WikiNavigator
from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project


def _project_n_entities(n: int) -> Project:
    p = Project(id="p", name="P")
    for i in range(n):
        name = f"Nodo{chr(65 + i)}"  # NodoA, NodoB, ... (alfabético, sin dígitos)
        p.entities.append(
            NarrativeEntity(id=f"e{i}", name=name, brief_description=f"{name} descripción")
        )
    return p


@pytest.mark.application
def test_compact_caps_and_notes_omitted():
    index = WikiIndexService().build_index(_project_n_entities(10)).value
    compact = WikiIndexService().compact_for_prompt(index, max_entries=3)
    assert len(compact["entradas"]) == 3
    assert compact["omitidas"] == len(index.entries) - 3
    assert "search" in compact["nota"].lower()  # se avisa cómo llegar a lo omitido


@pytest.mark.application
def test_no_cap_by_default_shows_all():
    index = WikiIndexService().build_index(_project_n_entities(5)).value
    compact = WikiIndexService().compact_for_prompt(index)  # sin max_entries
    assert len(compact["entradas"]) == len(index.entries)
    assert "omitidas" not in compact


@pytest.mark.application
def test_focus_priority_survives_the_cap():
    index = WikiIndexService().build_index(_project_n_entities(10)).value
    # Cap agresivo (2) que normalmente dejaría fuera a e9, pero es el foco → se prioriza.
    compact = WikiIndexService().compact_for_prompt(
        index, max_entries=2, priority_ids=["e9"]
    )
    blob = str(compact["entradas"])
    assert "e9" in blob


@pytest.mark.application
def test_search_still_finds_capped_out_entry():
    # El recorte del índice compacto NO oculta nada a search: usa el índice completo.
    index = WikiIndexService().build_index(_project_n_entities(10)).value
    nav = WikiNavigator(project_service=ProjectService())
    hits = nav._do_search(index, "NodoH")  # e7
    ids = [h["id"] for h in (hits or {}).get("resultados", [])]
    assert "e7" in ids
