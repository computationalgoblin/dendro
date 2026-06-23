"""BETA1-J08 — Clamp de naturaleza por tipo en el write path."""

from __future__ import annotations

import pytest

from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.domain.result import Ok
from packages.domain.temporal_models import TemporalNature


@pytest.fixture
def ps():
    svc = ProjectService()
    svc.create("Proyecto J08")
    return svc


def test_object_eternal_is_clamped_to_mortal(ps):
    # La IA propone un objeto eterno → la tabla manda: mortal.
    svc = EntityService(ps, ps.store)
    res = svc.create_entity(
        {"name": "Espada", "entity_type": "objeto", "temporal_nature": "eterno"}
    )
    assert isinstance(res, Ok)
    assert res.value.life_span.nature is TemporalNature.MORTAL


def test_creature_eternal_is_kept(ps):
    svc = EntityService(ps, ps.store)
    res = svc.create_entity(
        {"name": "Ángel", "entity_type": "criatura", "temporal_nature": "eterno"}
    )
    assert isinstance(res, Ok)
    assert res.value.life_span.nature is TemporalNature.ETERNO


def test_changing_type_to_object_clamps_nature(ps):
    # Una criatura eterna que se reclasifica a objeto pierde la eternidad.
    svc = EntityService(ps, ps.store)
    created = svc.create_entity(
        {"name": "X", "entity_type": "criatura", "temporal_nature": "eterno"}
    )
    assert isinstance(created, Ok)
    upd = svc.update_entity(created.value.id, {"entity_type": "objeto"})
    assert isinstance(upd, Ok)
    assert upd.value.life_span.nature is TemporalNature.MORTAL


def test_faction_branch_is_mortal(ps):
    svc = EntityService(ps, ps.store)
    res = svc.create_entity(
        {"name": "Orden", "entity_type": "faccion", "temporal_nature": "inmortal"}
    )
    assert isinstance(res, Ok)
    assert res.value.life_span.nature is TemporalNature.MORTAL
