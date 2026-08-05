"""BETA-MULTIAGENT2-FIX-07 (G2-11): la wiki no puede nacer con los enlaces rotos.

En el beta multi-agente ronda 2, regar dos entidades produjo **27 enlaces rotos de
27**: la IA escribia el NOMBRE dentro de `ref_id` (porque el contexto solo le daba
UN id, el suyo) y nada lo resolvia contra el canon antes de persistirlo.

Aqui se fija la regla de la seccion 3.2.0 del contrato `wiki_memoria.md`: id exacto →
nombre exacto (plegando mayusculas y acentos) → ambiguo/descartado, contando siempre
lo que se cae.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.memory_ai_service import MemoryAIService
from packages.application.memory_payload import normalize_memory_payload
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.structured_reference_service import resolve_page_refs
from packages.application.wiki_lint_service import WikiLintService
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryIssue,
    MemoryIssueKind,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok
from packages.infrastructure.ai_provider import AIProvider


class _FakeProvider(AIProvider):
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    @property
    def provider_name(self):
        return "fake_fix07"

    def chat(self, system_prompt, user_message, timeout=None, **kwargs):
        self.calls.append((system_prompt, user_message))
        return json.dumps(self.payload, ensure_ascii=False), None


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _project(*, duplicar_beto: bool = False) -> Project:
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana"))
    p.entities.append(NarrativeEntity(id="e2", name="Beto"))
    p.entities.append(NarrativeEntity(id="e3", name="Miró de Andújar"))
    p.entities.append(
        NarrativeEntity(id="c1", name="Casa de Ébano", entity_type=EntityType.CONTENEDOR)
    )
    if duplicar_beto:
        p.entities.append(NarrativeEntity(id="e9", name="Beto"))
    p.causal_milestones.append(
        CausalMilestone(
            id="h7", title="El Cisma", year=904, status=CausalMilestoneStatus.CANDIDATE
        )
    )
    p.relations.append(
        NarrativeRelation(
            id="r1", source_id="e2", target_id="e1", relation_type=RelationType.SIRVE_A
        )
    )
    p.touch()
    return p


def _service(project, payload):
    ps = _FakeProjectService(active_project=project)
    mem = NarrativeMemoryService(ps)
    provider = _FakeProvider(payload)
    aijob = AIJobService(provider=provider, project_provider=lambda: ps.active_project)
    return MemoryAIService(ps, aijob, memory_service=mem), mem, ps


def _payload(**extra):
    base = {
        "resumen_editorial": "Ana, reina en el exilio.",
        "cuerpo": "Ana perdió el trono.",
    }
    base.update(extra)
    return base


# ── el caso del beta: nombres en el ref_id ───────────────────────────────────


@pytest.mark.application
def test_beta_m2fix07_los_nombres_se_resuelven_a_ids_y_la_wiki_nace_limpia():
    """El caso literal del beta: 1 id bueno, nombres, una ref muerta y un ancla rota."""
    payload = _payload(
        citations=[{"ref_kind": "entity", "ref_id": "e1", "nota": "auto-cita"}],
        wikilinks=[
            {"ref_kind": "entity", "ref_id": "Beto", "nota": "aliado"},
            {"ref_kind": "entity", "ref_id": "El Cisma"},
            {"ref_kind": "entity", "ref_id": "Un Personaje Que No Existe"},
        ],
        issues=[
            {
                "kind": "contradiccion",
                "texto": "Muere en el capítulo 3 y aparece viva después",
                "anclado_a": [{"ref_kind": "milestone", "ref_id": "h404"}],
            }
        ],
    )
    proj = _project()
    svc, mem, ps = _service(proj, payload)

    resultado = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar")
    assert isinstance(resultado, Ok)

    page = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    ids = [(w.ref_kind.value, w.ref_id) for w in page.wikilinks]
    assert ("entity", "e2") in ids  # "Beto" → su id real
    assert ("milestone", "h7") in ids  # "El Cisma" → id real Y kind corregido
    assert "Un Personaje Que No Existe" not in [w.ref_id for w in page.wikilinks]
    # La auto-cita, lo unico que funcionaba antes, sigue funcionando.
    assert [c.ref_id for c in page.citations] == ["e1"]
    # La incidencia SOBREVIVE aunque su anclaje irresoluble se caiga.
    assert page.issues and page.issues[0].kind == MemoryIssueKind.CONTRADICCION
    assert page.issues[0].anclado_a == []

    # Criterio 1: el lint sobre el proyecto recien regado no ve un solo enlace roto.
    report = WikiLintService(ps).lint().value
    assert report.broken_links == []


@pytest.mark.application
def test_beta_m2fix07_el_ok_trae_el_recuento_de_lo_resuelto_y_lo_caido():
    payload = _payload(
        wikilinks=[
            {"ref_kind": "entity", "ref_id": "Beto"},
            {"ref_kind": "entity", "ref_id": "fantasma"},
        ],
    )
    svc, _mem, _ps = _service(_project(), payload)

    conteos = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar").value["refs"]

    assert conteos == {"resueltos": 1, "ambiguos": 0, "descartados": 1}


@pytest.mark.application
def test_beta_m2fix07_nombre_con_acentos_y_mayusculas_distintas_resuelve():
    payload = _payload(wikilinks=[{"ref_kind": "entity", "ref_id": "MIRO DE ANDUJAR"}])
    svc, mem, _ps = _service(_project(), payload)

    svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar")

    page = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert [w.ref_id for w in page.wikilinks] == ["e3"]


@pytest.mark.application
def test_beta_m2fix07_nombre_duplicado_no_inventa_ganador():
    """Criterio 3: dos entidades «Beto» → el enlace NO se persiste, pero se cuenta."""
    payload = _payload(wikilinks=[{"ref_kind": "entity", "ref_id": "Beto"}])
    svc, mem, _ps = _service(_project(duplicar_beto=True), payload)

    conteos = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar").value["refs"]

    page = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert page.wikilinks == []
    assert conteos["ambiguos"] == 1 and conteos["descartados"] == 0


@pytest.mark.application
def test_beta_m2fix07_el_ref_kind_equivocado_se_corrige_al_real():
    """La IA dice `entity` de un hito y de una rama; el kind real manda."""
    payload = _payload(
        wikilinks=[
            {"ref_kind": "entity", "ref_id": "h7"},
            {"ref_kind": "entity", "ref_id": "c1"},
            {"ref_kind": "milestone", "ref_id": "r1"},
        ]
    )
    svc, mem, _ps = _service(_project(), payload)

    svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar")

    page = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert [(w.ref_kind.value, w.ref_id) for w in page.wikilinks] == [
        ("milestone", "h7"),
        ("branch", "c1"),
        ("relation", "r1"),
    ]


# ── los otros dos caminos de escritura heredan la resolucion ─────────────────


@pytest.mark.application
def test_beta_m2fix07_regen_hereda_la_resolucion():
    payload = _payload(wikilinks=[{"ref_kind": "entity", "ref_id": "Beto"}])
    svc, mem, _ps = _service(_project(), payload)
    # Sin Memoria previa, regen escribe directo; con ella, propone diff. Los dos
    # caminos pasan por el mismo `sections`, asi que se comprueban los dos.
    svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regen")
    assert [w.ref_id for w in mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.wikilinks] == [
        "e2"
    ]

    res = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regen")
    propuesta = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.pending_revision
    assert isinstance(res, Ok) and res.value["applied"] is False
    assert [w["ref_id"] for w in propuesta.after["wikilinks"]] == ["e2"]


@pytest.mark.application
def test_beta_m2fix07_rebuild_wiki_hereda_la_resolucion():
    payload = _payload(wikilinks=[{"ref_kind": "entity", "ref_id": "Beto"}])
    proj = _project()
    svc, _mem, ps = _service(proj, payload)

    res = svc.rebuild_wiki()

    assert isinstance(res, Ok) and res.value["failed"] == 0
    assert WikiLintService(ps).lint().value.broken_links == []


# ── el cuerpo no lleva sintaxis cruda a la cara del usuario ─────────────────


@pytest.mark.application
def test_beta_m2fix07_el_cuerpo_no_conserva_enlaces_inventados():
    data = normalize_memory_payload(
        {
            "resumen_editorial": "[[Ana]] es la reina.",
            "cuerpo": "La [Posada del Ciervo](ref_id: Posada del Ciervo) acoge a [[Beto|el mozo]].",
            "estado_actual": "Vive en [[Casa de Ébano]].",
        }
    ).value

    assert data["resumen_editorial"] == "Ana es la reina."
    assert data["cuerpo"] == "La Posada del Ciervo acoge a el mozo."
    assert data["estado_actual"] == "Vive en Casa de Ébano."
    assert "ref_id:" not in data["cuerpo"] and "[[" not in data["cuerpo"]


# ── el agujero del lint: los anclajes de incidencia ─────────────────────────


@pytest.mark.application
def test_beta_m2fix07_el_lint_ve_el_anclaje_de_incidencia_roto():
    """Criterio 7: 4 anclajes en un mundo del beta, 2 rotos, invisibles hasta ahora."""
    proj = _project()
    proj.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id="e1",
            resumen_editorial="Ana",
            issues=[
                MemoryIssue(
                    kind=MemoryIssueKind.CONTRADICCION,
                    texto="vive y murió",
                    anclado_a=[
                        MemoryCitation(MemoryTargetKind.MILESTONE, "h404"),
                        MemoryCitation(MemoryTargetKind.MILESTONE, "h7"),
                    ],
                )
            ],
        )
    )
    ps = _FakeProjectService(active_project=proj)

    report = WikiLintService(ps).lint().value

    assert len(report.broken_links) == 1
    assert "h404" in report.broken_links[0].detail
    assert "incidencia" in report.broken_links[0].detail


# ── determinismo: sin proveedor de IA no se gasta nada ──────────────────────


@pytest.mark.application
def test_beta_m2fix07_la_resolucion_es_determinista_y_no_usa_ia():
    """Criterio 10: `resolve_page_refs` es una funcion pura sobre el proyecto."""
    proj = _project()
    entrada = [
        MemoryCitation(MemoryTargetKind.ENTITY, "Beto"),
        MemoryCitation(MemoryTargetKind.ENTITY, "e1"),
        MemoryCitation(MemoryTargetKind.RELATION, "r1"),
        # Las relaciones NO estan indexadas por nombre (no tienen nombre corto):
        # o resuelven por id, o se caen.
        MemoryCitation(MemoryTargetKind.RELATION, "Beto sirve a Ana"),
        MemoryCitation(MemoryTargetKind.ENTITY, "nada"),
    ]

    salida = resolve_page_refs(proj, entrada)

    assert [(c.ref_kind.value, c.ref_id) for c in salida.resueltas] == [
        ("entity", "e2"),
        ("entity", "e1"),
        ("relation", "r1"),
    ]
    assert [c.ref_id for c in salida.descartadas] == ["Beto sirve a Ana", "nada"]
    assert salida.counts() == {"resueltos": 3, "ambiguos": 0, "descartados": 2}
    # La entrada no se muta: la funcion es pura.
    assert entrada[0].ref_id == "Beto"
