"""BETA1-J03 — Migración v26 → v27: lapso temporal rico + backfill incierto.

Carga un proyecto v26 viejo y verifica: no-pérdida de años, marca 'incierto'
en lo derivado del presente, conservación de fechas explícitas, e idempotencia.
"""

from __future__ import annotations

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v26_to_v27,
)


def _v26_project(present_year=312):
    return {
        "id": "p1",
        "name": "Proyecto",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "schema_version": 26,
        "project_chronology": {"present_year": present_year, "eras": []},
        "entities": [
            # Derivada del presente → incierta.
            {
                "id": "e_present",
                "name": "PorInercia",
                "birth_year": present_year,
                "death_year": None,
            },
            # Fecha explícita histórica → exacta, conservada.
            {"id": "e_hist", "name": "Histórica", "birth_year": -40, "death_year": 12},
        ],
        "relations": [
            {
                "id": "r1",
                "source_id": "e_present",
                "target_id": "e_hist",
                "birth_year": 5,
                "death_year": None,
            },
        ],
        "causal_milestones": [
            {"id": "h_present", "title": "Inercia", "year": present_year, "temporality": {}},
            {"id": "h_hist", "title": "Antiguo", "year": -1000, "temporality": {}},
        ],
    }


def test_current_version_is_at_least_27():
    # CRON bump a v28: la migración temporal (v27) ya no es la cabeza, pero sigue presente.
    assert CURRENT_SCHEMA_VERSION >= 27


def test_entities_gain_life_span_without_year_loss():
    out = _apply_migration_v26_to_v27(_v26_project())
    by_id = {e["id"]: e for e in out["entities"]}

    hist = by_id["e_hist"]["life_span"]
    assert hist["start"]["year"] == -40  # no se pierde
    assert hist["end"]["year"] == 12
    assert hist["start"]["precision"] == "exact"  # fecha explícita conservada
    assert hist["ongoing"] is False

    present = by_id["e_present"]["life_span"]
    assert present["start"]["year"] == 312  # el año se conserva
    assert present["start"]["precision"] == "unknown"  # marcado incierto
    assert "no fundamentado" in present["start"]["notes"]
    assert present["ongoing"] is True


def test_relation_gains_life_span():
    out = _apply_migration_v26_to_v27(_v26_project())
    span = out["relations"][0]["life_span"]
    assert span["start"]["year"] == 5
    assert span["ongoing"] is True


def test_milestone_temporality_reflects_year_and_uncertainty():
    out = _apply_migration_v26_to_v27(_v26_project())
    by_id = {m["id"]: m for m in out["causal_milestones"]}
    # No se añade campo nuevo: el hito mantiene su 'year'; el temporality refleja.
    assert by_id["h_present"]["temporality"]["year"] == 312
    assert by_id["h_present"]["temporality"]["precision"] == "unknown"
    assert by_id["h_hist"]["temporality"]["year"] == -1000


def test_version_is_bumped():
    out = _apply_migration_v26_to_v27(_v26_project())
    assert out["schema_version"] == 27


def test_idempotent_does_not_rebuild_existing_life_span():
    out1 = _apply_migration_v26_to_v27(_v26_project())
    # Simular re-migración: ya hay life_span → no se reconstruye ni se pierde.
    out2 = _apply_migration_v26_to_v27(out1)
    by_id1 = {e["id"]: e for e in out1["entities"]}
    by_id2 = {e["id"]: e for e in out2["entities"]}
    assert by_id1["e_hist"]["life_span"] == by_id2["e_hist"]["life_span"]


def test_full_roundtrip_through_store(tmp_path):
    """Carga real v26 → v27 vía store (lee de disco), sin pérdida y versión final."""
    import json

    from packages.domain.result import Ok
    from packages.persistence.store import load_project_data

    path = tmp_path / "proyecto_v26.json"
    path.write_text(json.dumps(_v26_project()), encoding="utf-8")

    result = load_project_data(path)
    assert isinstance(result, Ok), getattr(result, "error", "")
    data = result.value
    # CRON bump a v28: la cadena de migración sigue hasta la cabeza actual.
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    by_id = {e["id"]: e for e in data["entities"]}
    assert by_id["e_hist"]["life_span"]["start"]["year"] == -40
    assert by_id["e_present"]["life_span"]["start"]["precision"] == "unknown"
