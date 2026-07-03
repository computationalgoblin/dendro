"""GhostService: ciclo de vida de nodos fantasma + exclusiones de canon (BETA2-FOCO-04)."""

from __future__ import annotations

import pytest

from packages.application.corpus_indexer import ARCHIVED_CANON_STATES
from packages.application.entity_service import EntityService
from packages.application.export_service import ExportService
from packages.application.ghost_service import GhostService
from packages.application.history_service import HistoryService
from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.result import Error, Ok


def _setup():
    project_service = ProjectService()
    project_service.create("Fantasmas")
    entity_service = EntityService(project_service)
    relation_service = RelationService(project_service)
    history_service = HistoryService(project_service)
    ghost_service = GhostService(
        project_service, entity_service, relation_service, history_service
    )
    return project_service, entity_service, ghost_service


def _real_entity(project_service, name):
    entity = NarrativeEntity(name=name)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _events(project_service):
    return [entry.event_type.value for entry in project_service.active_project.history]


@pytest.mark.application
class TestGhostLifecycle:
    def test_create_ghost_persists_with_ghost_canon(self):
        project_service, _, ghost_service = _setup()
        result = ghost_service.create_ghost(
            {"name": "¿Una orden en la sombra?", "brief_description": "Algo conspira aquí."}
        )
        assert isinstance(result, Ok), getattr(result, "error", None)
        ghost = result.value
        assert ghost.canon_state == CanonState.FANTASMA
        assert ghost in project_service.active_project.entities
        assert "creacion_entidad" in _events(project_service)

    def test_create_ghost_requires_name(self):
        _, _, ghost_service = _setup()
        assert isinstance(ghost_service.create_ghost({"name": "  "}), Error)

    def test_ghost_relation_is_ghost_and_validates_endpoints(self):
        project_service, _, ghost_service = _setup()
        real = _real_entity(project_service, "Eldrin")
        ghost = ghost_service.create_ghost({"name": "¿Mentor perdido?"}).value

        relation = ghost_service.create_ghost_relation(real.id, ghost.id, "conoce_parcialmente")
        assert isinstance(relation, Ok), getattr(relation, "error", None)
        assert relation.value.canon_state == CanonState.FANTASMA

        missing = ghost_service.create_ghost_relation(real.id, "no-existe")
        assert isinstance(missing, Error)

    def test_convert_to_entity_matures_relations_to_real_endpoints(self):
        project_service, _, ghost_service = _setup()
        real = _real_entity(project_service, "Eldrin")
        ghost = ghost_service.create_ghost({"name": "¿Hermandad?"}).value
        other_ghost = ghost_service.create_ghost({"name": "¿Fundador?"}).value
        to_real = ghost_service.create_ghost_relation(ghost.id, real.id).value
        to_ghost = ghost_service.create_ghost_relation(ghost.id, other_ghost.id).value

        result = ghost_service.convert_to_entity(ghost.id)
        assert isinstance(result, Ok), getattr(result, "error", None)
        assert result.value.canon_state == CanonState.CANONICO
        # La relación hacia la entidad real madura; la que apunta a otro fantasma no.
        assert to_real.canon_state == CanonState.CANONICO
        assert to_ghost.canon_state == CanonState.FANTASMA
        assert "cambio_canon" in _events(project_service)

    def test_convert_requires_ghost(self):
        project_service, _, ghost_service = _setup()
        real = _real_entity(project_service, "Eldrin")
        assert isinstance(ghost_service.convert_to_entity(real.id), Error)
        assert isinstance(ghost_service.convert_to_entity("nope"), Error)

    def test_link_to_existing_rewires_and_discards_ghost(self):
        project_service, _, ghost_service = _setup()
        real = _real_entity(project_service, "La Orden Real")
        neighbor = _real_entity(project_service, "Testigo")
        ghost = ghost_service.create_ghost({"name": "¿La orden?"}).value
        rewired = ghost_service.create_ghost_relation(ghost.id, neighbor.id).value
        redundant = ghost_service.create_ghost_relation(ghost.id, real.id).value
        project_service.set_last_worked_entity(ghost.id)

        result = ghost_service.link_to_existing(ghost.id, real.id)
        assert isinstance(result, Ok), getattr(result, "error", None)

        project = project_service.active_project
        assert project.entity_by_id(ghost.id) is None
        # La relación al vecino queda re-apuntada a la entidad real y madura.
        assert rewired.source_id == real.id
        assert rewired.target_id == neighbor.id
        assert rewired.canon_state == CanonState.CANONICO
        # La relación fantasma→destino se elimina (sería un self-loop).
        assert redundant not in project.relations
        # La última entidad trabajada apunta ahora a la real.
        assert project_service.get_last_worked_entity().value == real.id
        assert "fusion_entidades" in _events(project_service)

    def test_link_requires_real_target(self):
        _, _, ghost_service = _setup()
        ghost_a = ghost_service.create_ghost({"name": "¿A?"}).value
        ghost_b = ghost_service.create_ghost({"name": "¿B?"}).value
        assert isinstance(ghost_service.link_to_existing(ghost_a.id, ghost_b.id), Error)
        assert isinstance(ghost_service.link_to_existing(ghost_a.id, ghost_a.id), Error)

    def test_discard_removes_ghost_and_its_relations(self):
        project_service, _, ghost_service = _setup()
        real = _real_entity(project_service, "Eldrin")
        ghost = ghost_service.create_ghost({"name": "¿Sombra?"}).value
        ghost_service.create_ghost_relation(ghost.id, real.id)
        project_service.set_last_worked_entity(ghost.id)

        result = ghost_service.discard(ghost.id)
        assert isinstance(result, Ok)
        project = project_service.active_project
        assert project.entity_by_id(ghost.id) is None
        assert project.relations_for(real.id) == []
        assert project_service.get_last_worked_entity().value == ""
        assert "descarte_fantasma" in _events(project_service)


@pytest.mark.application
class TestCanonExclusions:
    def test_rag_indexer_treats_ghost_as_non_canon(self):
        # Contrato: el corpus canon no indexa fantasmas.
        assert "fantasma" in ARCHIVED_CANON_STATES

    def test_export_excludes_ghosts_for_every_audience(self):
        project_service, _, ghost_service = _setup()
        _real_entity(project_service, "Eldrin")
        ghost = ghost_service.create_ghost({"name": "¿Sombra?"}).value
        export_service = ExportService(project_service)

        for audience in ("gm", "player", "public"):
            names = [e.name for e in export_service._filter_entities(audience)]
            assert "¿Sombra?" not in names

        profile = export_service.export_entity_profile(ghost.id, audience="gm")
        assert isinstance(profile, Error)

        data = export_service.export_all(audience="gm")
        assert isinstance(data, Ok)
        assert all(item["name"] != "¿Sombra?" for item in data.value["entities"])

    def test_context_builder_hides_ghosts_from_non_gm(self):
        project_service, _, ghost_service = _setup()
        ghost = ghost_service.create_ghost({"name": "¿Sombra?"}).value
        builder = NarrativeContextBuilder(project_service)

        assert builder._can_include_entity(ghost, "player") is False
        # La audiencia gm SÍ lo ve (marcado por su canon_state en la ficha).
        assert builder._can_include_entity(ghost, "gm") is True

    def test_ghost_summary_carries_its_canon_state_marker(self):
        project_service, _, ghost_service = _setup()
        ghost = ghost_service.create_ghost({"name": "¿Sombra?"}).value
        builder = NarrativeContextBuilder(project_service)
        context = builder.build_for_entity(ghost.id, audience="gm")
        target = context.get("target") or {}
        assert str(target.get("canon_state", "")).lower() == "fantasma"
