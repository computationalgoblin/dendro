"""Clasificador de zonas Raíces/Entorno/Brotes del Modo Foco (BETA2-FOCO-02)."""

from __future__ import annotations

import pytest

from packages.application.foco_zones import (
    CausalZone,
    classify_containers,
    classify_milestones,
    classify_neighbors,
)
from packages.application.world_layer_causal import set_causal_rank
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.world_layer import WorldLayer


def _project() -> Project:
    return Project(name="Zonas")


def _entity(project: Project, name: str, **kwargs) -> NarrativeEntity:
    entity = NarrativeEntity(name=name, **kwargs)
    project.entities.append(entity)
    project.touch()
    return entity


def _relate(
    project: Project,
    source: NarrativeEntity,
    target: NarrativeEntity,
    relation_type: RelationType,
) -> NarrativeRelation:
    relation = NarrativeRelation(
        source_id=source.id, target_id=target.id, relation_type=relation_type
    )
    project.relations.append(relation)
    project.touch()
    return relation


def _layer(project: Project, layer_id: str, rank: int | None) -> WorldLayer:
    layer = WorldLayer(id=layer_id, name=layer_id)
    if rank is not None:
        set_causal_rank(layer, rank)
    project.world_layers.append(layer)
    project.touch()
    return layer


def _zone_of(zones: dict, entity_id: str) -> tuple[str, str] | None:
    for zone_name, neighbors in zones.items():
        for neighbor in neighbors:
            if neighbor.entity_id == entity_id:
                return zone_name, neighbor.reason
    return None


@pytest.mark.application
class TestCausalSignals:
    def test_incoming_causo_is_root_and_outgoing_is_sprout(self):
        project = _project()
        center = _entity(project, "Centro")
        cause = _entity(project, "Guerra previa")
        effect = _entity(project, "Éxodo posterior")
        _relate(project, cause, center, RelationType.CAUSO)
        _relate(project, center, effect, RelationType.CAUSO)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, cause.id) == (CausalZone.RAICES.value, "causal")
        assert _zone_of(zones, effect.id) == (CausalZone.BROTES.value, "causal")

    def test_effect_as_source_family(self):
        project = _project()
        center = _entity(project, "Centro")
        root_a = _entity(project, "Origen A")
        root_b = _entity(project, "Origen B")
        sprout = _entity(project, "Derivada")
        _relate(project, center, root_a, RelationType.FUE_CAUSADO_POR)
        _relate(project, center, root_b, RelationType.DERIVA_DE)
        _relate(project, sprout, center, RelationType.DEPENDE_DE)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, root_a.id) == (CausalZone.RAICES.value, "causal")
        assert _zone_of(zones, root_b.id) == (CausalZone.RAICES.value, "causal")
        assert _zone_of(zones, sprout.id) == (CausalZone.BROTES.value, "causal")

    def test_cause_as_source_family(self):
        project = _project()
        center = _entity(project, "Centro")
        root = _entity(project, "Condición")
        sprout = _entity(project, "Consecuencia")
        _relate(project, root, center, RelationType.CONDICIONA)
        _relate(project, center, sprout, RelationType.PRODUCE_CONSECUENCIA_EN)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, root.id) == (CausalZone.RAICES.value, "causal")
        assert _zone_of(zones, sprout.id) == (CausalZone.BROTES.value, "causal")

    def test_conflicting_causal_signals_fall_to_entorno(self):
        project = _project()
        center = _entity(project, "Centro")
        twin = _entity(project, "Gemela")
        _relate(project, twin, center, RelationType.CAUSO)
        _relate(project, center, twin, RelationType.CAUSO)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, twin.id) == (CausalZone.ENTORNO.value, "conflicting")


@pytest.mark.application
class TestContainment:
    def test_container_branch_leaves_zones_and_goes_to_chain(self):
        # BETA2-FOCO-22: la contenedora NO es un satélite — la UI la dibuja
        # como marco envolvente; classify_containers la expone aparte.
        project = _project()
        center = _entity(project, "Hoja")
        branch = _entity(project, "Rama madre")
        _relate(project, branch, center, RelationType.CONTIENE)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, branch.id) is None  # fuera de las tres zonas
        chain = classify_containers(project, center.id)
        assert [c.entity_id for c in chain] == [branch.id]
        assert chain[0].reason == "container"

    def test_pertenece_a_outgoing_marks_container(self):
        project = _project()
        center = _entity(project, "Hoja")
        branch = _entity(project, "Rama madre")
        _relate(project, center, branch, RelationType.PERTENECE_A)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, branch.id) is None
        chain = classify_containers(project, center.id)
        assert [c.entity_id for c in chain] == [branch.id]

    def test_container_chain_walks_ancestors_immediate_first(self):
        project = _project()
        center = _entity(project, "Hoja")
        mother = _entity(project, "Madre")
        grandmother = _entity(project, "Abuela")
        _relate(project, mother, center, RelationType.CONTIENE)
        _relate(project, grandmother, mother, RelationType.CONTIENE)

        chain = classify_containers(project, center.id)
        assert [c.entity_id for c in chain] == [mother.id, grandmother.id]

    def test_children_go_to_brotes(self):
        project = _project()
        center = _entity(project, "Rama")
        child_a = _entity(project, "Miembro A")
        child_b = _entity(project, "Miembro B")
        _relate(project, center, child_a, RelationType.CONTIENE)
        _relate(project, child_b, center, RelationType.PERTENECE_A)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, child_a.id) == (CausalZone.BROTES.value, "child")
        assert _zone_of(zones, child_b.id) == (CausalZone.BROTES.value, "child")


@pytest.mark.application
class TestRankAndDefault:
    def test_upper_ring_is_root_lower_ring_is_sprout(self):
        project = _project()
        _layer(project, "layer_alto", 1)
        _layer(project, "layer_medio", 5)
        _layer(project, "layer_bajo", 9)
        center = _entity(project, "Centro", layer_ids=["layer_medio"])
        upper = _entity(project, "Premisa", layer_ids=["layer_alto"])
        lower = _entity(project, "Detalle", layer_ids=["layer_bajo"])
        _relate(project, upper, center, RelationType.ESTA_RELACIONADO_CON)
        _relate(project, center, lower, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, upper.id) == (CausalZone.RAICES.value, "causal_rank")
        assert _zone_of(zones, lower.id) == (CausalZone.BROTES.value, "causal_rank")

    def test_causal_relation_beats_ring_rank(self):
        project = _project()
        _layer(project, "layer_alto", 1)
        _layer(project, "layer_medio", 5)
        center = _entity(project, "Centro", layer_ids=["layer_medio"])
        upper = _entity(project, "Premisa derivada", layer_ids=["layer_alto"])
        # Aunque esté en anillo superior, el centro la CAUSA ⇒ brote.
        _relate(project, center, upper, RelationType.CAUSO)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, upper.id) == (CausalZone.BROTES.value, "causal")

    def test_no_signal_goes_to_entorno(self):
        project = _project()
        center = _entity(project, "Centro")
        peer = _entity(project, "Vecina plana")
        _relate(project, center, peer, RelationType.ES_ALIADO_DE)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, peer.id) == (CausalZone.ENTORNO.value, "default")


@pytest.mark.application
class TestMilestoneNeighbors:
    def test_milestone_coaffected_classified_by_year(self):
        project = _project()
        center = _entity(project, "Centro", birth_year=1000)
        elder = _entity(project, "Antigua")
        younger = _entity(project, "Posterior")
        project.causal_milestones.append(
            CausalMilestone(
                title="Guerra fundacional",
                year=900,
                status=CausalMilestoneStatus.CANON,
                affected_entity_ids=[center.id, elder.id],
            )
        )
        project.causal_milestones.append(
            CausalMilestone(
                title="Cisma tardío",
                year=1100,
                status=CausalMilestoneStatus.CANON,
                affected_entity_ids=[center.id, younger.id],
            )
        )
        project.touch()

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, elder.id) == (CausalZone.RAICES.value, "milestone")
        assert _zone_of(zones, younger.id) == (CausalZone.BROTES.value, "milestone")

    def test_relation_signal_wins_over_milestone_link(self):
        project = _project()
        center = _entity(project, "Centro", birth_year=1000)
        both = _entity(project, "Doble vínculo")
        _relate(project, center, both, RelationType.CAUSO)
        project.causal_milestones.append(
            CausalMilestone(
                title="Hito viejo",
                year=900,
                status=CausalMilestoneStatus.CANON,
                affected_entity_ids=[center.id, both.id],
            )
        )
        project.touch()

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, both.id) == (CausalZone.BROTES.value, "causal")

    def test_classify_milestones_by_year_and_status(self):
        project = _project()
        center = _entity(project, "Centro", birth_year=1000)
        founding = CausalMilestone(
            title="Fundación",
            year=1000,
            status=CausalMilestoneStatus.CANON,
            affected_entity_ids=[center.id],
        )
        later = CausalMilestone(
            title="Expansión",
            year=1100,
            status=CausalMilestoneStatus.HYPOTHESIS,
            affected_entity_ids=[center.id],
        )
        undated = CausalMilestone(
            title="Sin fecha",
            status=CausalMilestoneStatus.CANON,
            affected_entity_ids=[center.id],
        )
        rejected = CausalMilestone(
            title="Rechazado",
            year=800,
            status=CausalMilestoneStatus.REJECTED,
            affected_entity_ids=[center.id],
        )
        project.causal_milestones.extend([founding, later, undated, rejected])
        project.touch()

        zones = classify_milestones(project, center.id)
        # Año igual al nacimiento ⇒ raíz (evento fundacional).
        assert zones[CausalZone.RAICES.value] == [founding.id]
        assert zones[CausalZone.BROTES.value] == [later.id]
        assert zones[CausalZone.ENTORNO.value] == [undated.id]
        assert rejected.id not in (
            zones[CausalZone.RAICES.value]
            + zones[CausalZone.ENTORNO.value]
            + zones[CausalZone.BROTES.value]
        )


@pytest.mark.application
class TestMiscBehaviour:
    def test_ghost_neighbors_flagged(self):
        project = _project()
        center = _entity(project, "Centro")
        ghost = _entity(project, "¿Algo?", canon_state=CanonState.FANTASMA)
        _relate(project, ghost, center, RelationType.CAUSO)

        zones = classify_neighbors(project, center.id)
        raices = zones[CausalZone.RAICES.value]
        assert len(raices) == 1
        assert raices[0].is_ghost is True

    def test_archived_and_discarded_excluded(self):
        project = _project()
        center = _entity(project, "Centro")
        archived = _entity(project, "Vieja", canon_state=CanonState.ARCHIVADO)
        discarded = _entity(project, "Descartada", canon_state=CanonState.DESCARTADO)
        _relate(project, archived, center, RelationType.CAUSO)
        _relate(project, discarded, center, RelationType.CAUSO)

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, archived.id) is None
        assert _zone_of(zones, discarded.id) is None

    def test_unknown_center_returns_three_empty_zones(self):
        project = _project()
        zones = classify_neighbors(project, "no-existe")
        assert set(zones.keys()) == {"raices", "entorno", "brotes"}
        assert all(not neighbors for neighbors in zones.values())

    def test_deterministic_name_order_within_zone(self):
        project = _project()
        center = _entity(project, "Centro")
        for name in ("Zeta", "Alfa", "Momo"):
            peer = _entity(project, name)
            _relate(project, center, peer, RelationType.ES_ALIADO_DE)

        zones = classify_neighbors(project, center.id)
        names = [
            project.entity_by_id(neighbor.entity_id).name
            for neighbor in zones[CausalZone.ENTORNO.value]
        ]
        assert names == ["Alfa", "Momo", "Zeta"]


@pytest.mark.application
class TestContainerNotReaddedByMilestones:
    def test_milestone_coaffected_container_stays_out_of_zones(self):
        # FOCO-22: la contenedora es marco — un hito co-afectado no debe
        # devolverla a las zonas como satélite.
        project = _project()
        center = _entity(project, "Hoja", birth_year=10)
        branch = _entity(project, "Rama madre")
        _relate(project, branch, center, RelationType.CONTIENE)
        project.causal_milestones.append(
            CausalMilestone(
                title="Fundación",
                year=50,
                affected_entity_ids=[center.id, branch.id],
            )
        )

        zones = classify_neighbors(project, center.id)
        assert _zone_of(zones, branch.id) is None
        assert [c.entity_id for c in classify_containers(project, center.id)] == [branch.id]
