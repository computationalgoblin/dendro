"""BETA-MULTIAGENT2-FIX-07 (G2-12): el contexto de Memoria no puede perder la dirección.

El canon del guionista decía, sin ambigüedad, `Nadia Kerr --sirve_a--> Otho Vann`. Las
dos páginas escritas en el mismo lote se contradijeron: la de Nadia la llamaba sirviente
de Otho (bien) y la de Otho lo declaraba «Subordinado de Nadia Kerr» (al revés).

La causa no era el modelo: `_build_context` renderizaba `sirve_a→Nadia Kerr` viniera la
relación de entrada o de salida, y eso en español se lee «(yo) sirvo a Nadia». Aquí se
fija la dirección explícita, los ids de vecinas/hitos/relaciones (sin los cuales ningún
wikilink puede ser correcto) y que el recorte de relaciones se declare.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.application.memory_ai_service import (
    _MAX_CONTEXT_RELATIONS,
    MemoryAIService,
)
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _project() -> Project:
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="nadia", name="Nadia Kerr"))
    p.entities.append(NarrativeEntity(id="otho", name="Otho Vann"))
    p.relations.append(
        NarrativeRelation(
            id="r1", source_id="nadia", target_id="otho", relation_type=RelationType.SIRVE_A
        )
    )
    return p


def _context(project: Project, target_id: str, kind=MemoryTargetKind.ENTITY) -> str:
    ps = _FakeProjectService(active_project=project)
    svc = MemoryAIService(ps, ai_job_service=None)
    return svc._build_context(project, kind, target_id, "")


# ── la dirección, en las dos direcciones ────────────────────────────────────


@pytest.mark.application
def test_beta_m2fix07_el_destino_de_la_relacion_no_se_lee_como_origen():
    """Otho es a quien Nadia sirve: su contexto no puede decir lo contrario."""
    ctx = _context(_project(), "otho")

    # La cadena ambigua que escribía el código anterior ya no aparece.
    assert "sirve_a→Nadia Kerr" not in ctx
    assert "[entra] Nadia Kerr (entity:nadia) —sirve_a→ ESTA ENTIDAD" in ctx
    assert "[sale]" not in ctx


@pytest.mark.application
def test_beta_m2fix07_el_origen_de_la_relacion_se_marca_como_origen():
    ctx = _context(_project(), "nadia")

    assert "[sale] ESTA ENTIDAD —sirve_a→ Otho Vann (entity:otho)" in ctx
    assert "[entra]" not in ctx


# ── los ids que la IA necesita para escribir wikilinks correctos ────────────


@pytest.mark.application
def test_beta_m2fix07_el_contexto_enumera_vecinas_hitos_y_relaciones_con_su_id():
    proj = _project()
    proj.entities[1].birth_year = 10
    proj.causal_milestones.append(
        CausalMilestone(
            id="h7",
            title="El Cisma",
            year=5,
            status=CausalMilestoneStatus.CANDIDATE,
            affected_entity_ids=["otho"],
        )
    )

    ctx = _context(proj, "otho")

    assert "entity:nadia" in ctx  # la vecina, con kind + id + nombre
    assert "Nadia Kerr" in ctx
    assert "relation:r1" in ctx  # el vínculo, con su propio id
    assert "milestone:h7" in ctx  # el hito en el que participa
    assert "El Cisma" in ctx


@pytest.mark.application
def test_beta_m2fix07_el_contexto_de_un_hito_lista_a_sus_participantes_con_id():
    proj = _project()
    proj.causal_milestones.append(
        CausalMilestone(
            id="h7",
            title="El Cisma",
            year=5,
            status=CausalMilestoneStatus.CANDIDATE,
            affected_entity_ids=["nadia", "otho"],
        )
    )

    ctx = _context(proj, "h7", kind=MemoryTargetKind.MILESTONE)

    assert "Nadia Kerr (entity:nadia)" in ctx
    assert "Otho Vann (entity:otho)" in ctx


@pytest.mark.application
def test_beta_m2fix07_el_contexto_de_una_relacion_nombra_sus_extremos_con_id():
    ctx = _context(_project(), "r1", kind=MemoryTargetKind.RELATION)

    assert "Nadia Kerr (entity:nadia) —sirve_a→ Otho Vann (entity:otho)" in ctx
    assert "el ORIGEN es Nadia Kerr" in ctx


# ── el recorte se declara (contrato §9: no truncar callando) ────────────────


@pytest.mark.application
def test_beta_m2fix07_el_recorte_de_relaciones_se_declara_en_el_texto():
    proj = _project()
    total_extra = _MAX_CONTEXT_RELATIONS + 3
    for i in range(total_extra):
        proj.entities.append(NarrativeEntity(id=f"x{i}", name=f"Extra {i}"))
        proj.relations.append(
            NarrativeRelation(
                id=f"rx{i}",
                source_id="otho",
                target_id=f"x{i}",
                relation_type=RelationType.CONOCE,
            )
        )

    ctx = _context(proj, "otho")

    total = total_extra + 1  # + la relación con Nadia
    assert f"hay {total} relaciones" in ctx
    assert f"quedan {total - _MAX_CONTEXT_RELATIONS} sin mostrar" in ctx


@pytest.mark.application
def test_beta_m2fix07_sin_relaciones_no_hay_bloque_de_relaciones():
    proj = Project(id="p", name="P")
    proj.entities.append(NarrativeEntity(id="solo", name="Solo"))

    ctx = _context(proj, "solo")

    assert "RELACIONES" not in ctx
