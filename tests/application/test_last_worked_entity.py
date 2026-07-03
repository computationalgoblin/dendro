"""Última entidad trabajada por proyecto (BETA2-FOCO-03).

Se persiste en ``Project.metadata["last_worked_entity_id"]`` vía ProjectService:
viaja con el archivo del proyecto y Foco la centra al abrir.
"""

from __future__ import annotations

import pytest

from packages.application.project_service import ProjectService
from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Error, Ok


def _setup():
    project_service = ProjectService()
    project_service.create("Proyecto")
    return project_service


def _entity(project_service, name):
    entity = NarrativeEntity(name=name)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


@pytest.mark.application
class TestLastWorkedEntity:
    def test_set_and_get_roundtrip(self):
        project_service = _setup()
        entity = _entity(project_service, "Eldrin")

        assert isinstance(project_service.set_last_worked_entity(entity.id), Ok)
        result = project_service.get_last_worked_entity()
        assert isinstance(result, Ok)
        assert result.value == entity.id

    def test_unknown_entity_is_error(self):
        project_service = _setup()
        assert isinstance(project_service.set_last_worked_entity("nope"), Error)

    def test_empty_clears_the_mark(self):
        project_service = _setup()
        entity = _entity(project_service, "Eldrin")
        project_service.set_last_worked_entity(entity.id)

        assert isinstance(project_service.set_last_worked_entity(""), Ok)
        assert project_service.get_last_worked_entity().value == ""
        assert "last_worked_entity_id" not in project_service.active_project.metadata

    def test_deleted_entity_reads_as_empty(self):
        project_service = _setup()
        entity = _entity(project_service, "Efímera")
        project_service.set_last_worked_entity(entity.id)

        project_service.active_project.entities.remove(entity)
        project_service.active_project.touch()
        assert project_service.get_last_worked_entity().value == ""

    def test_survives_serialization(self):
        project_service = _setup()
        entity = _entity(project_service, "Eldrin")
        project_service.set_last_worked_entity(entity.id)

        data = project_service.active_project.to_dict()
        assert data["metadata"]["last_worked_entity_id"] == entity.id
        restored = Project.from_dict(data)
        assert restored.metadata["last_worked_entity_id"] == entity.id

    def test_no_active_project_is_error(self):
        project_service = ProjectService()
        assert isinstance(project_service.set_last_worked_entity("x"), Error)
        assert isinstance(project_service.get_last_worked_entity(), Error)
