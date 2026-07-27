"""BETA-CIERRE WS-N: correcciones del detector estructural (BETA2-STRUCT).

1) `branch_move` reconoce las ramas REALES (FACCION/CULTURA/LOCALIZACION/… + legacy
   CONTENEDOR), no solo el literal "contenedor". Antes, a una rama moderna con miembros
   se le proponía un `ring_move` SUELTO que, al aceptar, la movía sola y huérfanaba a sus
   miembros — rompiendo la contención (el invariante que STRUCT-06 debía garantizar).
2) `ascending_exception` es simétrico respecto a la orientación source/target de la relación
   (antes subdetectaba ~la mitad de las relaciones elegibles).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.application.causal_potency import set_basal_potency
from packages.application.structural_analysis_service import StructuralAnalysisService
from packages.application.world_layer_causal import set_causal_rank
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.world_layer import WorldLayer


@dataclass
class _FakePS:
    active_project: Project


def _project3() -> tuple[Project, list[str]]:
    p = Project(id="p", name="P")
    rings: list[str] = []
    for i, rank in enumerate((1, 2, 3), start=1):
        layer = WorldLayer(id=f"r{i}", name=f"Anillo{i}")
        set_causal_rank(layer, rank)
        p.world_layers.append(layer)
        rings.append(layer.id)
    return p, rings


def _svc(p: Project) -> StructuralAnalysisService:
    return StructuralAnalysisService(_FakePS(active_project=p))


@pytest.mark.application
def test_is_branch_with_content_recognizes_modern_branch_types():
    p, rings = _project3()
    faction = NarrativeEntity(
        id="fac", name="Los Grises", entity_type=EntityType.FACCION, layer_ids=[rings[2]]
    )
    spy = NarrativeEntity(
        id="spy", name="Espía", entity_type=EntityType.PERSONAJE, layer_ids=[rings[2]]
    )
    legacy = NarrativeEntity(
        id="leg", name="Vieja rama", entity_type=EntityType.CONTENEDOR, layer_ids=[rings[2]]
    )
    p.entities.extend([faction, spy, legacy])
    p.relations.append(
        NarrativeRelation(id="c1", source_id="fac", target_id="spy",
                          relation_type=RelationType.CONTIENE))
    p.relations.append(
        NarrativeRelation(id="c2", source_id="leg", target_id="spy",
                          relation_type=RelationType.CONTIENE))
    p.touch()

    assert StructuralAnalysisService._is_branch_with_content(p, faction) is True  # tipo moderno
    assert StructuralAnalysisService._is_branch_with_content(p, legacy) is True  # compat legacy
    assert StructuralAnalysisService._is_branch_with_content(p, spy) is False  # hoja sin contenido


@pytest.mark.application
def test_modern_branch_gets_branch_move_not_loose_ring_move():
    p, rings = _project3()
    faction = NarrativeEntity(
        id="fac", name="Los Grises", entity_type=EntityType.FACCION, layer_ids=[rings[2]]
    )
    set_basal_potency(faction, 95)  # potencia alta atribuida, pero en el anillo exterior
    member = NarrativeEntity(
        id="m", name="Miembro", entity_type=EntityType.PERSONAJE, layer_ids=[rings[2]]
    )
    set_basal_potency(member, 90)
    p.entities.extend([faction, member])
    p.relations.append(
        NarrativeRelation(id="c", source_id="fac", target_id="m",
                          relation_type=RelationType.CONTIENE))
    p.touch()

    findings = _svc(p).analyze().value
    # STRUCT-06: la facción NO puede aparecer como ring_move suelto (movería el contenedor
    # solo y huérfanaría a sus miembros)...
    assert not any(f.kind == "ring_move" and f.target_id == "fac" for f in findings)
    # ...sino como branch_move (arrastra el subárbol).
    branch = [f for f in findings if f.kind == "branch_move" and f.target_id == "fac"]
    assert len(branch) == 1
    assert "m" in branch[0].proposed_data["member_ids"]


@pytest.mark.application
def test_ascending_exception_is_orientation_symmetric():
    p, rings = _project3()
    high = NarrativeEntity(  # anillo interior (pos 1)
        id="high", name="Rey", entity_type=EntityType.PERSONAJE, layer_ids=[rings[0]]
    )
    low = NarrativeEntity(  # anillo exterior (pos 3), con potencia alta atribuida
        id="low", name="Susurro", entity_type=EntityType.PERSONAJE, layer_ids=[rings[2]]
    )
    set_basal_potency(low, 85)
    p.entities.extend([high, low])
    # Relación NO causal, autorada ALTO→BAJO (source=high, target=low): el extremo de alta
    # potencia es el TARGET. Antes NO se detectaba; ahora sí (simetría).
    p.relations.append(
        NarrativeRelation(id="r", source_id="high", target_id="low",
                          relation_type=RelationType.ESTA_RELACIONADO_CON))
    p.touch()

    asc = [f for f in _svc(p).analyze().value if f.kind == "ascending_exception"]
    assert len(asc) == 1
    assert asc[0].proposed_data["source_entity_id"] == "low"  # el extremo inferior
    assert asc[0].proposed_data["target_entity_id"] == "high"
