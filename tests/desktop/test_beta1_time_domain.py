"""BETA1-G02: dominio temporal — eras, años de vida, año de hito, migración.

Contrato: docs/architecture/G01_time_contract.md. Sin Qt: dominio, servicios
de aplicación y persistencia (migración v24→v25 + roundtrip).
"""
from __future__ import annotations

import pytest

from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.entity_service import EntityService
from packages.application.era_service import EraService
from packages.application.project_service import ProjectService
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.entity import NarrativeEntity, validate_entity
from packages.domain.era import Era
from packages.domain.project_chronology import ProjectChronology
from packages.domain.result import Error, Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v24_to_v25,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def ps() -> ProjectService:
    service = ProjectService()
    result = service.create("Tiempo Test BETA1")
    assert isinstance(result, Ok), f"create project failed: {result}"
    return service


# ── Era (dominio) ─────────────────────────────────────────────────────────

def test_era_roundtrip_and_contains():
    era = Era(name="Edad Oscura", start_year=-500, end_year=-1, order=1)
    data = era.to_dict()
    back = Era.from_dict(data)
    assert back.name == "Edad Oscura"
    assert back.start_year == -500 and back.end_year == -1
    assert back.contains(-250) and not back.contains(0)
    # Era abierta
    open_era = Era(name="Presente", start_year=0, end_year=None)
    assert open_era.contains(0) and open_era.contains(99999)
    assert Era.from_dict(open_era.to_dict()).end_year is None


def test_chronology_eras_serialization_and_era_for_year():
    chrono = ProjectChronology()
    chrono.eras = [
        Era(name="Antigua", start_year=-1000, end_year=-1),
        Era(name="Presente", start_year=0, end_year=None),
    ]
    chrono.present_year = 42
    back = ProjectChronology.from_dict(chrono.to_dict())
    assert [era.name for era in back.eras] == ["Antigua", "Presente"]
    assert back.present_year == 42
    assert back.era_for_year(-500).name == "Antigua"
    assert back.era_for_year(42).name == "Presente"
    assert back.era_for_year(-2000) is None


def test_chronology_ensure_default_era_idempotent():
    chrono = ProjectChronology()
    first = chrono.ensure_default_era()
    second = chrono.ensure_default_era()
    assert first is second
    assert len(chrono.eras) == 1
    assert first.name == "Presente" and first.end_year is None


# ── Entidad: birth/death (dominio) ────────────────────────────────────────

def test_entity_years_serialization():
    entity = NarrativeEntity(name="Eldrin", birth_year=-12, death_year=88)
    back = NarrativeEntity.from_dict(entity.to_dict())
    assert back.birth_year == -12 and back.death_year == 88
    # Tolerancia: clave ausente → None (transitorio pre-migración)
    legacy = NarrativeEntity.from_dict({"name": "Viejo"})
    assert legacy.birth_year is None and legacy.death_year is None


def test_entity_death_before_birth_is_invalid():
    entity = NarrativeEntity(name="Paradoja", birth_year=100, death_year=50)
    issues = validate_entity(entity)
    assert any("death_year" in issue for issue in issues)


# ── Hito: year (dominio) ─────────────────────────────────────────────────

def test_milestone_year_serialization():
    hito = CausalMilestone(title="La Ruptura", year=-3)
    back = CausalMilestone.from_dict(hito.to_dict())
    assert back.year == -3
    assert CausalMilestone.from_dict({"title": "Sin año"}).year is None


# ── No-atemporalidad por defecto (servicios) ──────────────────────────────

def test_create_entity_defaults_birth_year_to_present(ps):
    ps.active_project.project_chronology.present_year = 312
    svc = EntityService(ps, ps.store)
    result = svc.create_entity({"name": "Nueva", "entity_type": "personaje"})
    assert isinstance(result, Ok)
    assert result.value.birth_year == 312
    assert result.value.death_year is None


def test_create_entity_respects_explicit_birth_year(ps):
    ps.active_project.project_chronology.present_year = 312
    svc = EntityService(ps, ps.store)
    result = svc.create_entity({"name": "Antigua", "entity_type": "personaje", "birth_year": -40})
    assert isinstance(result, Ok)
    assert result.value.birth_year == -40


def test_update_entity_edits_years(ps):
    svc = EntityService(ps, ps.store)
    created = svc.create_entity({"name": "Mortal", "entity_type": "personaje"})
    assert isinstance(created, Ok)
    updated = svc.update_entity(created.value.id, {"birth_year": 10, "death_year": 90})
    assert isinstance(updated, Ok)
    assert updated.value.birth_year == 10 and updated.value.death_year == 90
    # Incoherencia → rechazada por validación
    bad = svc.update_entity(created.value.id, {"death_year": 5})
    assert isinstance(bad, Error)


def test_create_milestone_defaults_year_to_present(ps):
    ps.active_project.project_chronology.present_year = 7
    svc = CausalMilestoneService(project_service=ps)
    result = svc.create_hito_manual({"title": "Hito ahora"})
    assert isinstance(result, Ok)
    assert result.value.year == 7
    explicit = svc.create_hito_manual({"title": "Hito antiguo", "year": -100})
    assert isinstance(explicit, Ok)
    assert explicit.value.year == -100


# ── EraService ────────────────────────────────────────────────────────────

def test_era_service_crud_and_present_year(ps):
    svc = EraService(project_service=ps)
    listed = svc.list_eras()
    assert isinstance(listed, Ok)
    assert len(listed.value) == 1 and listed.value[0].name == "Presente"

    created = svc.create_era({"name": "Edad de Hierro", "start_year": -300, "end_year": -1, "order": 1})
    assert isinstance(created, Ok)
    assert len(svc.list_eras().value) == 2

    updated = svc.update_era(created.value.id, {"name": "Edad del Hierro", "start_year": -350})
    assert isinstance(updated, Ok)
    assert updated.value.name == "Edad del Hierro" and updated.value.start_year == -350

    assert isinstance(svc.create_era({"name": ""}), Error)
    assert isinstance(svc.create_era({"name": "X", "start_year": 10, "end_year": 5}), Error)

    assert isinstance(svc.set_present_year(99), Ok)
    assert svc.get_present_year().value == 99

    derived = svc.era_for_year(-100)
    assert isinstance(derived, Ok) and derived.value.name == "Edad del Hierro"

    deleted = svc.delete_era(created.value.id)
    assert isinstance(deleted, Ok)
    # La última era no se puede borrar
    last_id = svc.list_eras().value[0].id
    assert isinstance(svc.delete_era(last_id), Error)


def test_era_service_overlap_is_warning_not_block(ps):
    svc = EraService(project_service=ps)
    svc.list_eras()  # asegura "Presente" (0..None)
    result = svc.create_era({"name": "Solapada", "start_year": 5, "end_year": 50})
    assert isinstance(result, Ok)  # no bloquea
    assert svc.overlap_warnings()  # pero avisa


# ── Migración v24 → v25 ──────────────────────────────────────────────────

def _minimal_v24_data() -> dict:
    return {
        "schema_version": 24,
        "project_chronology": ProjectChronology().to_dict(),
        "entities": [
            {"id": "e1", "name": "Vieja", "entity_type": "personaje"},
            {"id": "e2", "name": "Fechada", "entity_type": "nota", "birth_year": 33},
        ],
        "causal_milestones": [
            {"id": "h1", "title": "Sin año"},
            {"id": "h2", "title": "Con año", "year": -9},
        ],
    }


def test_migration_v24_to_v25_backfills_time():
    migrated = _apply_migration_v24_to_v25(_minimal_v24_data())
    assert migrated["schema_version"] == 25 == CURRENT_SCHEMA_VERSION
    chrono = migrated["project_chronology"]
    assert chrono["present_year"] == 0
    assert len(chrono["eras"]) == 1
    era = chrono["eras"][0]
    assert era["name"] == "Presente" and era["start_year"] == 0 and era["end_year"] is None
    by_id = {raw["id"]: raw for raw in migrated["entities"]}
    assert by_id["e1"]["birth_year"] == 0 and by_id["e1"]["death_year"] is None
    assert by_id["e2"]["birth_year"] == 33  # no pisa valores existentes
    hitos = {raw["id"]: raw for raw in migrated["causal_milestones"]}
    assert hitos["h1"]["year"] == 0
    assert hitos["h2"]["year"] == -9


def test_migration_is_idempotent_on_v25_shape():
    once = _apply_migration_v24_to_v25(_minimal_v24_data())
    twice = _apply_migration_v24_to_v25(dict(once, schema_version=24))
    assert twice["project_chronology"]["eras"] == once["project_chronology"]["eras"]
    assert twice["entities"] == once["entities"]


# ── Persistencia: roundtrip completo ─────────────────────────────────────

def test_time_fields_survive_save_and_reopen(ps, tmp_path):
    era_svc = EraService(project_service=ps)
    era_svc.list_eras()
    era_svc.set_present_year(500)
    era_svc.create_era({"name": "Fundación", "start_year": -200, "end_year": -1, "order": 1})

    entity_svc = EntityService(ps, ps.store)
    created = entity_svc.create_entity({"name": "Cron", "entity_type": "personaje"})
    assert isinstance(created, Ok) and created.value.birth_year == 500

    hito_svc = CausalMilestoneService(project_service=ps)
    hito = hito_svc.create_hito_manual({"title": "El Pacto", "year": -150})
    assert isinstance(hito, Ok)

    path = tmp_path / "tiempo.dendro.json"
    assert isinstance(ps.save(path), Ok)

    reopened_service = ProjectService()
    reopened = reopened_service.open(path)
    assert isinstance(reopened, Ok), f"open failed: {getattr(reopened, 'error', '')}"
    project = reopened.value
    chrono = project.project_chronology
    assert chrono.present_year == 500
    assert {era.name for era in chrono.eras} == {"Presente", "Fundación"}
    entity = next(e for e in project.entities if e.name == "Cron")
    assert entity.birth_year == 500 and entity.death_year is None
    milestone = next(h for h in project.causal_milestones if h.title == "El Pacto")
    assert milestone.year == -150
