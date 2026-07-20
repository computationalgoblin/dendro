"""Navegación por anillos del Modo Foco (BETA2-FOCO-25, ronda 3)."""

from __future__ import annotations

import pytest

from packages.application.foco_rings import (
    UNCLASSIFIED_RING_ID,
    _containment_related,
    branch_members,
    classify_ring_neighbors,
    ring_id_for,
    ring_navigation,
)
from packages.application.world_layer_causal import set_causal_rank
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.world_layer import WorldLayer


def _project() -> Project:
    return Project(name="Anillos")


def _entity(project: Project, name: str, *, layer: str | None = None, **kwargs) -> NarrativeEntity:
    layer_ids = [layer] if layer else []
    entity = NarrativeEntity(name=name, layer_ids=layer_ids, **kwargs)
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


def _ids(neighbors) -> list[str]:
    return [n.entity_id for n in neighbors]


@pytest.mark.application
class TestRingIdFor:
    """BETA2-CLEANUP-PANELES: ring_id_for → id del anillo del centro, o None."""

    def test_returns_layer_id_for_classified_entity(self):
        project = _project()
        _layer(project, "l2", 2)
        center = _entity(project, "Centro", layer="l2")
        assert ring_id_for(project, center.id) == "l2"

    def test_returns_none_for_unclassified_entity(self):
        project = _project()
        _layer(project, "l1", 1)
        huerfana = _entity(project, "Huérfana")  # sin capa ni contenedor
        assert ring_id_for(project, huerfana.id) is None

    def test_inherits_container_ring(self):
        # Sin capa propia hereda el anillo de la rama contenedora directa.
        project = _project()
        _layer(project, "l2", 2)
        rama = _entity(project, "Casa", layer="l2", entity_type="faccion")
        miembro = _entity(project, "Miembro")
        _relate(project, rama, miembro, RelationType.CONTIENE)
        assert ring_id_for(project, miembro.id) == "l2"

    def test_empty_or_missing_id_returns_none(self):
        project = _project()
        assert ring_id_for(project, "") is None
        assert ring_id_for(project, "no-existe") is None


@pytest.mark.application
class TestClassifyRingNeighbors:
    def test_superior_ring_to_raices_inferior_to_brotes_same_to_entorno(self):
        project = _project()
        _layer(project, "l1", 1)
        _layer(project, "l2", 2)
        _layer(project, "l3", 3)
        center = _entity(project, "Centro", layer="l2")
        arriba = _entity(project, "Arriba", layer="l1")
        abajo = _entity(project, "Abajo", layer="l3")
        lado = _entity(project, "Lado", layer="l2")
        for other in (arriba, abajo, lado):
            _relate(project, center, other, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert _ids(zones["raices"]) == [arriba.id]
        assert _ids(zones["brotes"]) == [abajo.id]
        assert _ids(zones["entorno"]) == [lado.id]

    def test_containment_not_in_any_band(self):
        # FOCO-30: CONTIENE/PERTENECE_A no aparecen en las bandas (van a la
        # estantería de la tarjeta + el marco). Una relación normal del mismo
        # anillo sí se ve.
        project = _project()
        _layer(project, "l2", 2)
        center = _entity(project, "Casa", layer="l2", entity_type="faccion")
        miembro = _entity(project, "Miembro", layer="l2")
        aliado = _entity(project, "Aliado", layer="l2")
        _relate(project, center, miembro, RelationType.CONTIENE)
        _relate(project, center, aliado, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        banded = _ids(zones["raices"]) + _ids(zones["entorno"]) + _ids(zones["brotes"])
        assert miembro.id not in banded  # contención fuera de bandas
        assert aliado.id in _ids(zones["entorno"])  # relación normal sí

    def test_branch_members_lists_live_contents_by_name(self):
        project = _project()
        _layer(project, "l2", 2)
        casa = _entity(project, "Casa", layer="l2", entity_type="faccion")
        zeta = _entity(project, "Zeta", layer="l2")
        alfa = _entity(project, "Alfa", layer="l2")
        _relate(project, casa, zeta, RelationType.CONTIENE)
        _relate(project, casa, alfa, RelationType.CONTIENE)

        assert branch_members(project, casa.id) == [alfa.id, zeta.id]  # orden por nombre

    def test_raices_sorted_most_superior_first(self):
        project = _project()
        _layer(project, "l1", 1)
        _layer(project, "l2", 2)
        _layer(project, "l4", 4)
        center = _entity(project, "Centro", layer="l4")
        r1 = _entity(project, "Zeta", layer="l1")  # más superior aunque el nombre sea el último
        r2 = _entity(project, "Alfa", layer="l2")
        _relate(project, center, r1, RelationType.ESTA_RELACIONADO_CON)
        _relate(project, center, r2, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert _ids(zones["raices"]) == [r1.id, r2.id]  # rango 1 antes que rango 2

    def test_brotes_sorted_nearest_inferior_first(self):
        project = _project()
        _layer(project, "l2", 2)
        _layer(project, "l3", 3)
        _layer(project, "l5", 5)
        center = _entity(project, "Centro", layer="l2")
        near = _entity(project, "Zeta", layer="l3")
        far = _entity(project, "Alfa", layer="l5")
        _relate(project, center, near, RelationType.ESTA_RELACIONADO_CON)
        _relate(project, center, far, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert _ids(zones["brotes"]) == [near.id, far.id]  # rango 3 antes que rango 5

    def test_unranked_layer_is_outer_ring(self):
        # Como en el Mapa: una capa sin rango se ordena DESPUÉS de las rankeadas
        # (anillo exterior) — sigue siendo comparable para la navegación.
        project = _project()
        _layer(project, "l1", 1)
        _layer(project, "meta", None)  # capa sin rango ⇒ anillo exterior
        center = _entity(project, "Centro", layer="l1")
        exterior = _entity(project, "Exterior", layer="meta")
        _relate(project, center, exterior, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert _ids(zones["brotes"]) == [exterior.id]

    def test_no_layer_at_all_is_outermost_ring(self):
        # Entidad sin NINGUNA capa (ni rama de la que heredar) ⇒ anillo
        # "__unclassified__", que como en el Mapa es el anillo MÁS exterior.
        project = _project()
        _layer(project, "l1", 1)
        center = _entity(project, "Centro", layer="l1")
        suelta = _entity(project, "Suelta")
        _relate(project, center, suelta, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert _ids(zones["brotes"]) == [suelta.id]
        # Y el salto Shift+↓ la alcanza (antes las sin capa eran invisibles).
        assert ring_navigation(project, center.id).down == suelta.id

    def test_project_layer_without_persisted_rank_inherits_default_rank(self):
        # Proyectos reales: capas por defecto SIN causal_rank persistido — el
        # rango se hereda de default_world_layers (mismo merge que el Mapa).
        project = _project()
        for layer_id in ("layer_metafisica", "layer_narrativa"):
            layer = WorldLayer(id=layer_id, name=layer_id)  # sin metadata causal
            project.world_layers.append(layer)
        center = _entity(project, "Centro", layer="layer_narrativa")  # rank default 13
        arriba = _entity(project, "Arriba", layer="layer_metafisica")  # rank default 1
        _relate(project, center, arriba, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert _ids(zones["raices"]) == [arriba.id]
        nav = ring_navigation(project, center.id)
        assert nav.up == arriba.id

    def test_branch_mates_separated_and_excluded_from_other_zones(self):
        project = _project()
        _layer(project, "l2", 2)
        center = _entity(project, "Centro", layer="l2")
        rama = _entity(project, "Rama", layer="l2")
        hermana = _entity(project, "Hermana", layer="l2")
        _relate(project, rama, center, RelationType.CONTIENE)
        _relate(project, rama, hermana, RelationType.CONTIENE)
        # relación directa además de ser compañera de rama: sigue en branch_mates, no en entorno.
        _relate(project, center, hermana, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert _ids(zones["branch_mates"]) == [hermana.id]
        assert hermana.id not in _ids(zones["entorno"])
        # La rama contenedora no aparece como satélite (se dibuja como marco).
        assert rama.id not in _ids(zones["entorno"] + zones["raices"] + zones["brotes"])

    def test_leaf_inherits_ring_from_container(self):
        project = _project()
        _layer(project, "l3", 3)
        _layer(project, "l1", 1)
        rama = _entity(project, "Rama", layer="l3")
        hijo = _entity(project, "Hijo")  # sin capa propia
        _relate(project, rama, hijo, RelationType.CONTIENE)
        arriba = _entity(project, "Arriba", layer="l1")
        _relate(project, hijo, arriba, RelationType.ESTA_RELACIONADO_CON)

        # El hijo hereda el anillo de la rama (rango 3): l1 (rango 1) es superior ⇒ raíces.
        zones = classify_ring_neighbors(project, hijo.id)
        assert _ids(zones["raices"]) == [arriba.id]

    def test_excluded_canon_ignored(self):
        project = _project()
        _layer(project, "l1", 1)
        _layer(project, "l2", 2)
        center = _entity(project, "Centro", layer="l2")
        archivada = _entity(
            project, "Archivada", layer="l1", canon_state=CanonState.ARCHIVADO
        )
        _relate(project, center, archivada, RelationType.ESTA_RELACIONADO_CON)

        zones = classify_ring_neighbors(project, center.id)
        assert archivada.id not in _ids(zones["raices"])


@pytest.mark.application
class TestRingNavigation:
    def test_prev_next_cycle_by_name(self):
        project = _project()
        _layer(project, "l2", 2)
        a = _entity(project, "Alfa", layer="l2")
        b = _entity(project, "Beta", layer="l2")
        c = _entity(project, "Gamma", layer="l2")

        nav = ring_navigation(project, b.id)
        assert nav.prev == a.id
        assert nav.next == c.id
        # Envoltura cíclica en los extremos.
        assert ring_navigation(project, a.id).prev == c.id
        assert ring_navigation(project, c.id).next == a.id

    def test_rotation_orders_by_connection_related_first(self):
        # FOCO-28: la ruleta rota primero por las MÁS relacionadas con el centro,
        # no alfabéticamente. Centro se relaciona solo con Zeta ⇒ Zeta es su vecino
        # de rotación aunque «Alfa» sea alfabéticamente anterior.
        project = _project()
        _layer(project, "l2", 2)
        center = _entity(project, "Centro", layer="l2")
        alfa = _entity(project, "Alfa", layer="l2")  # sin relación con el centro
        zeta = _entity(project, "Zeta", layer="l2")  # relacionada con el centro
        _relate(project, center, zeta, RelationType.ESTA_RELACIONADO_CON)

        nav = ring_navigation(project, center.id)
        assert nav.next == zeta.id  # la relacionada rota adyacente al centro
        assert nav.prev == alfa.id  # la no relacionada queda al otro lado

    def test_single_entity_ring_has_no_rotation(self):
        project = _project()
        _layer(project, "l2", 2)
        solo = _entity(project, "Solo", layer="l2")
        nav = ring_navigation(project, solo.id)
        assert nav.prev == "" and nav.next == ""

    def test_up_prefers_related_nearest_superior_ring(self):
        project = _project()
        _layer(project, "l1", 1)
        _layer(project, "l2", 2)
        _layer(project, "l3", 3)
        center = _entity(project, "Centro", layer="l3")
        cercana = _entity(project, "Cercana", layer="l2")  # rango 2 (adyacente)
        lejana = _entity(project, "Lejana", layer="l1")  # rango 1 (más superior)
        _relate(project, center, cercana, RelationType.ESTA_RELACIONADO_CON)
        _relate(project, center, lejana, RelationType.ESTA_RELACIONADO_CON)

        nav = ring_navigation(project, center.id)
        assert nav.up == cercana.id  # el anillo más cercano gana

    def test_up_falls_back_to_any_adjacent_ring_entity(self):
        project = _project()
        _layer(project, "l1", 1)
        _layer(project, "l3", 3)
        center = _entity(project, "Centro", layer="l3")
        # Sin relación superior: salta a una entidad cualquiera del anillo adyacente superior.
        vecina = _entity(project, "Vecina", layer="l1")

        nav = ring_navigation(project, center.id)
        assert nav.up == vecina.id

    def test_down_symmetric(self):
        project = _project()
        _layer(project, "l1", 1)
        _layer(project, "l2", 2)
        center = _entity(project, "Centro", layer="l1")
        abajo = _entity(project, "Abajo", layer="l2")

        nav = ring_navigation(project, center.id)
        assert nav.down == abajo.id
        assert nav.up == ""  # no hay anillo superior a rango 1

    def test_unclassified_center_has_no_ring_jump(self):
        project = _project()
        center = _entity(project, "Centro")  # sin capa ⇒ anillo no clasificado
        assert center is not None
        other = _entity(project, "Otra", layer=None)
        _relate(project, center, other, RelationType.ESTA_RELACIONADO_CON)

        nav = ring_navigation(project, center.id)
        # Sin más anillos en el proyecto no hay salto posible en ninguna dirección.
        assert nav.up == "" and nav.down == ""
        # Ambas comparten el anillo no clasificado ⇒ rotación disponible.
        assert nav.next == other.id

    def test_rotation_mixes_leaves_and_branches(self):
        # FOCO-31: la rotación MEZCLA hojas y ramas del mismo anillo (antes solo
        # rotaba entre iguales de especie). Aquí ninguna rama contiene al centro.
        project = _project()
        _layer(project, "l2", 2)
        hoja_a = _entity(project, "Alfa", layer="l2")
        rama = _entity(project, "Beta rama", layer="l2", entity_type="contenedor")
        hoja_b = _entity(project, "Gamma", layer="l2")

        nav = ring_navigation(project, hoja_a.id)
        # Orden por nombre: Alfa(0) → Beta rama(1) → Gamma(2). Desde Alfa:
        assert nav.next == rama.id  # una RAMA es ahora una parada de la rotación
        assert nav.prev == hoja_b.id

    def test_rotation_excludes_containing_branch(self):
        # FOCO-31: una rama que contiene (transitivamente) al centro NO aparece en
        # la rotación — se alcanza con ↑.
        project = _project()
        _layer(project, "l2", 2)
        hoja_a = _entity(project, "Alfa", layer="l2")
        rama = _entity(project, "Beta rama", layer="l2", entity_type="contenedor")
        hoja_b = _entity(project, "Gamma", layer="l2")
        _relate(project, rama, hoja_a, RelationType.CONTIENE)

        nav = ring_navigation(project, hoja_a.id)
        assert nav.next == hoja_b.id  # la rama contenedora queda fuera
        assert nav.prev == hoja_b.id  # cíclico solo entre las dos hojas
        assert nav.container == rama.id  # la rama se alcanza con ↑

    def test_branch_rotation_excludes_its_own_members(self):
        # FOCO-31: desde una rama enfocada, sus PROPIOS contenidos no salen en la
        # rotación (se ven en la estantería / ↓); sí rota a iguales del anillo.
        project = _project()
        _layer(project, "l2", 2)
        rama = _entity(project, "Beta rama", layer="l2", entity_type="contenedor")
        miembro_a = _entity(project, "Alfa", layer="l2")
        miembro_b = _entity(project, "Gamma", layer="l2")
        vecina = _entity(project, "Zeta vecina", layer="l2")
        _relate(project, rama, miembro_a, RelationType.CONTIENE)
        _relate(project, rama, miembro_b, RelationType.CONTIENE)

        nav = ring_navigation(project, rama.id)
        # Solo la vecina (no contenida) es parada de rotación.
        assert nav.next == vecina.id
        assert nav.prev == vecina.id
        assert nav.member == miembro_a.id  # los miembros se alcanzan con ↓

    def test_up_goes_to_container_and_down_to_first_member(self):
        # FOCO-25: ↑ sube a la rama contenedora; ↓ (desde una rama) baja a la
        # primera entidad contenida.
        project = _project()
        _layer(project, "l2", 2)
        rama = _entity(project, "Rama", layer="l2", entity_type="contenedor")
        hija_b = _entity(project, "Beta", layer="l2")
        hija_a = _entity(project, "Alfa", layer="l2")
        _relate(project, rama, hija_a, RelationType.CONTIENE)
        _relate(project, rama, hija_b, RelationType.CONTIENE)

        assert ring_navigation(project, hija_a.id).container == rama.id
        assert ring_navigation(project, rama.id).member == hija_a.id  # primera por nombre
        assert ring_navigation(project, hija_a.id).member == ""  # una hoja no tiene miembros


@pytest.mark.application
def test_containment_related_transitive_ancestors_and_descendants():
    # FOCO-31: cierre transitivo — abuela ⊃ madre ⊃ hija ⊃ nieta.
    project = _project()
    abuela = _entity(project, "Abuela", entity_type="contenedor")
    madre = _entity(project, "Madre", entity_type="contenedor")
    hija = _entity(project, "Hija", entity_type="contenedor")
    nieta = _entity(project, "Nieta")
    _relate(project, abuela, madre, RelationType.CONTIENE)
    _relate(project, madre, hija, RelationType.CONTIENE)
    _relate(project, hija, nieta, RelationType.CONTIENE)

    related = _containment_related(project, madre.id)
    # Ancestro (abuela) + descendientes transitivos (hija, nieta); nunca ella misma.
    assert related == {abuela.id, hija.id, nieta.id}


@pytest.mark.application
def test_containment_related_survives_cycle():
    # Una contención mal formada (ciclo) no cuelga ni se auto-incluye.
    project = _project()
    a = _entity(project, "A", entity_type="contenedor")
    b = _entity(project, "B", entity_type="contenedor")
    _relate(project, a, b, RelationType.CONTIENE)
    _relate(project, b, a, RelationType.CONTIENE)

    assert _containment_related(project, a.id) == {b.id}


@pytest.mark.application
def test_unclassified_ring_id_stable():
    assert UNCLASSIFIED_RING_ID == "__unclassified__"
