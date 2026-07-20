import json

import pytest

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.era import Era
from packages.domain.project import Project
from packages.domain.project_chronology import ProjectChronology
from packages.domain.result import Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v23_to_v24,
    _apply_migration_v34_to_v35,
    validate_project_structure,
)
from packages.persistence.store import ProjectStore, load_project_data


def _v34_chronology(metadata, *, eras=None, present_year=0):
    """Cronología on-disk v34 con una única era abierta 'Presente' salvo que se indique."""
    if eras is None:
        eras = [Era(name="Presente", start_year=0, end_year=None, order=0).to_dict()]
    return {
        "id": "project_chronology",
        "eras": eras,
        "present_year": present_year,
        "metadata": dict(metadata),
    }


@pytest.mark.persistence
def test_schema_v24_adds_empty_project_chronology_to_v23_projects():
    old_data = Project(id="proj-v23", name="Legacy B41").to_dict()
    old_data["schema_version"] = 23
    old_data.pop("project_chronology", None)

    migrated = _apply_migration_v23_to_v24(old_data)

    assert migrated["schema_version"] == 24
    assert migrated["project_chronology"]["id"] == "project_chronology"
    assert migrated["project_chronology"]["milestone_ids"] == []


@pytest.mark.persistence
def test_validate_project_structure_rejects_non_dict_project_chronology():
    data = Project(id="proj-bad", name="Bad").to_dict()
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    data["project_chronology"] = ["not-dict"]

    error = validate_project_structure(data)

    assert error == "Project config section 'project_chronology' must be a JSON object, got list"


@pytest.mark.persistence
def test_project_store_roundtrips_chronology_and_causal_milestones(tmp_path):
    project = Project(id="proj-h02", name="H02")
    project.causal_milestones.append(
        CausalMilestone(
            id="hito-1",
            title="Juramento de las Siete Puertas",
            affected_entity_ids=["leaf-1"],
        )
    )
    project.project_chronology = ProjectChronology(
        calendar_name="Calendario de la Frontera",
        description="Cronologia principal de campana.",
        calendar_system="diegetic",
        milestone_ids=["hito-1"],
        metadata={"view": "future-filtered"},
    )
    path = tmp_path / "chronology.json"

    store = ProjectStore()
    save_result = store.save(project, path)
    load_result = store.load(path)

    assert isinstance(save_result, Ok)
    assert isinstance(load_result, Ok)
    assert load_result.value.project_chronology.calendar_name == "Calendario de la Frontera"
    assert load_result.value.project_chronology.milestone_ids == ["hito-1"]
    assert load_result.value.project_chronology.metadata == {"view": "future-filtered"}
    assert load_result.value.causal_milestones[0].title == "Juramento de las Siete Puertas"


@pytest.mark.persistence
def test_project_store_roundtrips_edited_milestone_chronology_fields(tmp_path):
    project = Project(id="proj-h03", name="H03")
    project.causal_milestones.append(
        CausalMilestone(
            id="hito-editado",
            title="Titulo editado",
            description="Resumen editado",
            rationale="Cuerpo editado",
            metadata={
                "sort_index": 4,
                "chronology_key": "Era de ceniza",
                "primary_entity_id": "leaf-1",
                "body": "Cuerpo editado",
            },
            affected_entity_ids=["leaf-1"],
        )
    )
    project.project_chronology = ProjectChronology(milestone_ids=["hito-editado"])
    path = tmp_path / "edited-hito.json"

    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)
    loaded = store.load(path)

    assert isinstance(loaded, Ok)
    hito = loaded.value.causal_milestones[0]
    assert hito.title == "Titulo editado"
    assert hito.description == "Resumen editado"
    assert hito.rationale == "Cuerpo editado"
    assert hito.metadata["sort_index"] == 4
    assert hito.metadata["chronology_key"] == "Era de ceniza"
    assert hito.metadata["primary_entity_id"] == "leaf-1"


@pytest.mark.persistence
def test_load_project_data_migrates_v23_to_current_schema(tmp_path):
    old_data = Project(id="proj-v23", name="Legacy B41").to_dict()
    old_data["schema_version"] = 23
    old_data.pop("project_chronology", None)
    path = tmp_path / "legacy-v23.json"
    path.write_text(json.dumps(old_data), encoding="utf-8")

    loaded = load_project_data(path)

    assert isinstance(loaded, Ok)
    assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loaded.value["project_chronology"]["milestone_ids"] == []


# ── BETA2-CAL: migración v34 → v35 (calendario unificado) ────────────────────


@pytest.mark.persistence
def test_v35_full_calendar_reconstructs_chained_eras_and_present():
    data = Project(id="p", name="N").to_dict()
    data["schema_version"] = 34
    data["project_chronology"] = _v34_chronology(
        {
            "mode": "full_calendar",
            "past_eras": ["Era A", "Era B"],
            "eras": ["Era A", "Era B"],
            "era_lengths": {"Era A": 100, "Era B": 50},
            "months": ["M1", "M2"],
            "month_lengths": {"M1": 10, "M2": 20},
            "weekdays": ["a", "b", "c", "d", "e", "f", "g"],
            "current_date": {"era": "Era B", "year": 10, "month": "M1", "day": 1},
            "current_year": 1,
        }
    )

    migrated = _apply_migration_v34_to_v35(data)
    chrono = migrated["project_chronology"]

    assert migrated["schema_version"] == 35
    assert [(e["name"], e["start_year"], e["end_year"]) for e in chrono["eras"]] == [
        ("Era A", 0, 99),
        ("Era B", 100, None),
    ]
    # Presente derivado de current_date: Era B (start 100) año 10 → 109.
    assert chrono["present_year"] == 109
    meta = chrono["metadata"]
    assert meta["mode"] == "full_calendar"
    assert meta["week_anchor"] == 0
    assert meta["calendar"]["months"] == [
        {"name": "M1", "length": 10},
        {"name": "M2", "length": 20},
    ]
    assert meta["calendar"]["weekdays"] == ["a", "b", "c", "d", "e", "f", "g"]


@pytest.mark.persistence
def test_v35_vague_periods_become_chained_eras_without_months():
    data = Project(id="p", name="N").to_dict()
    data["schema_version"] = 34
    data["project_chronology"] = _v34_chronology(
        {
            "mode": "vague_periods",
            "periods": ["Antiguedad", "Actualidad"],
            "eras": ["Antiguedad", "Actualidad"],
            "era_lengths": {"Antiguedad": 1, "Actualidad": 1},
        }
    )

    chrono = _apply_migration_v34_to_v35(data)["project_chronology"]

    assert [(e["name"], e["start_year"], e["end_year"]) for e in chrono["eras"]] == [
        ("Antiguedad", 0, 0),
        ("Actualidad", 1, None),
    ]
    assert chrono["metadata"]["mode"] == "vague_periods"
    assert chrono["metadata"]["calendar"]["months"] == []


@pytest.mark.persistence
def test_v35_none_keeps_single_era_and_present_year():
    data = Project(id="p", name="N").to_dict()
    data["schema_version"] = 34
    data["project_chronology"] = _v34_chronology({"mode": "none"}, present_year=5)

    chrono = _apply_migration_v34_to_v35(data)["project_chronology"]

    assert len(chrono["eras"]) == 1
    assert chrono["eras"][0]["name"] == "Presente"
    assert chrono["present_year"] == 5
    assert chrono["metadata"]["mode"] == "none"


@pytest.mark.persistence
def test_v35_preserves_real_closed_eras_and_custom_metadata():
    real_eras = [
        Era(name="A", start_year=0, end_year=99, order=0).to_dict(),
        Era(name="B", start_year=100, end_year=None, order=1).to_dict(),
    ]
    data = Project(id="p", name="N").to_dict()
    data["schema_version"] = 34
    data["project_chronology"] = _v34_chronology(
        {"mode": "vague_periods", "era_lengths": {"A": 100, "B": 50}, "foo": "bar"},
        eras=real_eras,
        present_year=42,
    )

    chrono = _apply_migration_v34_to_v35(data)["project_chronology"]

    # Eras reales (≥2) NO se reconstruyen; present_year intacto; metadata sin pérdida.
    assert [e["name"] for e in chrono["eras"]] == ["A", "B"]
    assert chrono["present_year"] == 42
    assert chrono["metadata"]["foo"] == "bar"


@pytest.mark.persistence
def test_v35_migration_is_idempotent():
    data = Project(id="p", name="N").to_dict()
    data["schema_version"] = 34
    data["project_chronology"] = _v34_chronology(
        {
            "mode": "full_calendar",
            "era_lengths": {"Era A": 100, "Era B": 50},
            "past_eras": ["Era A", "Era B"],
            "months": ["M1"],
            "month_lengths": {"M1": 10},
            "weekdays": ["a", "b"],
            "current_date": {"era": "Era B", "year": 3, "month": "M1", "day": 1},
        }
    )

    once = _apply_migration_v34_to_v35(data)
    twice = _apply_migration_v34_to_v35(dict(once))

    assert twice["project_chronology"] == once["project_chronology"]
    assert twice["schema_version"] == 35


@pytest.mark.persistence
def test_v35_end_to_end_load_migrates_without_loss(tmp_path):
    data = Project(id="p", name="N").to_dict()
    data["schema_version"] = 34
    data["project_chronology"] = _v34_chronology(
        {
            "mode": "full_calendar",
            "era_lengths": {"Era A": 100, "Era B": 50},
            "past_eras": ["Era A", "Era B"],
            "months": ["M1", "M2"],
            "month_lengths": {"M1": 10, "M2": 20},
            "weekdays": ["a", "b", "c", "d", "e", "f", "g"],
            "current_date": {"era": "Era B", "year": 10, "month": "M1", "day": 1},
        }
    )
    path = tmp_path / "legacy-v34.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_project_data(path)

    assert isinstance(loaded, Ok)
    assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION
    chrono = loaded.value["project_chronology"]
    assert [e["name"] for e in chrono["eras"]] == ["Era A", "Era B"]
    assert chrono["present_year"] == 109
