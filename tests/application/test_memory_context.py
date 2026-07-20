"""BETA2-MEM-06: Memoria como sección determinista del prompt (canon > Memoria > cand.)."""

import json
from types import SimpleNamespace

import pytest

from packages.application.context_budget import FIXED_SECTIONS
from packages.application.memory_context import build_memory_prompt_section
from packages.application.prompt_assembler import PromptAssembler
from packages.domain.narrative_memory import (
    MemoryFreshness,
    MemoryIssue,
    MemoryIssueKind,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project


def _mem(target_kind, target_id, resumen, freshness=MemoryFreshness.REGADA, issues=None):
    return NarrativeMemory(
        target_kind=target_kind,
        target_id=target_id,
        resumen_editorial=resumen,
        freshness=freshness,
        issues=issues or [],
    )


def _project():
    p = Project(id="p", name="P")
    p.narrative_memories.append(_mem(MemoryTargetKind.PROJECT, "", "Resumen global del mundo."))
    p.narrative_memories.append(
        _mem(
            MemoryTargetKind.ENTITY,
            "e1",
            "Ana es la reina exiliada.",
            issues=[MemoryIssue(kind=MemoryIssueKind.CONTRADICCION, texto="Muere y revive")],
        )
    )
    p.narrative_memories.append(_mem(MemoryTargetKind.ENTITY, "e2", "Beto, no seleccionado."))
    return p


# ── constructor de la sección ──────────────────────────────────────────────────


@pytest.mark.application
def test_build_includes_global_and_selected_only():
    section = build_memory_prompt_section(_project(), selected_ids={"e1"})
    elementos = {b["elemento"] for b in section["bloques"]}
    assert "proyecto" in elementos
    assert "entity:e1" in elementos
    assert "entity:e2" not in elementos  # no seleccionado → fuera
    assert section["nota"].startswith("La Memoria es una lectura DERIVADA")
    # la contradicción viaja anclada al bloque
    e1 = next(b for b in section["bloques"] if b["elemento"] == "entity:e1")
    assert e1["contradicciones"] == ["Muere y revive"]


@pytest.mark.application
def test_build_flags_obsolete_memory():
    p = Project(id="p", name="P")
    p.narrative_memories.append(
        _mem(MemoryTargetKind.PROJECT, "", "resumen", freshness=MemoryFreshness.FALTA_REGAR)
    )
    section = build_memory_prompt_section(p)
    assert "aviso" in section and "obsoleta" in section["aviso"]


@pytest.mark.application
def test_build_returns_none_without_memory():
    assert build_memory_prompt_section(Project(id="p", name="P")) is None
    # bloque vacío (marcado falta_regar sin contenido) no cuenta
    p = Project(id="p", name="P")
    p.narrative_memories.append(_mem(MemoryTargetKind.PROJECT, "", ""))
    assert build_memory_prompt_section(p) is None


# ── integración en el ensamblado del prompt ────────────────────────────────────


def _plan(context, intent="suggest_relations"):
    return SimpleNamespace(
        prompt="haz algo",
        context=context,
        intent=SimpleNamespace(intent_type=SimpleNamespace(value=intent)),
    )


def _pack(items):
    return {"schema": "context_pack/v1", "items": items, "warnings": [], "truncated": False}


@pytest.mark.application
def test_contexto_wiki_is_the_fixed_section():
    # BETA2-WIKI-05: la Memoria ya no viaja como volcado fijo `memoria_derivada`;
    # el contexto seleccionado por navegación de la wiki es la sección fija.
    assert "contexto_wiki" in FIXED_SECTIONS
    assert "memoria_derivada" not in FIXED_SECTIONS


@pytest.mark.application
def test_prompt_includes_contexto_wiki_when_present():
    # WIKI-05: el consumidor (Sugerencias/Play) inyecta contexto_wiki = bundle navegado.
    context = {
        "contexto_wiki": {
            "nota": "Contexto seleccionado de la wiki (páginas derivadas) y del canon.",
            "paginas": [{"kind": "entity", "id": "e1", "resumen": "Ana, reina."}],
            "canon": [{"kind": "entity", "id": "e1", "ficha": {"nombre": "Ana"}}],
            "notas": [],
        }
    }
    msg = json.loads(PromptAssembler().assemble(_plan(context)))
    assert "contexto_wiki" in msg
    assert msg["contexto_wiki"]["paginas"][0]["id"] == "e1"
    assert msg["contexto_wiki"]["canon"][0]["ficha"]["nombre"] == "Ana"


@pytest.mark.application
def test_prompt_without_wiki_omits_section():
    msg = json.loads(PromptAssembler().assemble(_plan({"selected_entity_ids": ["e1"]})))
    assert "contexto_wiki" not in msg
    assert "memoria_derivada" not in msg
