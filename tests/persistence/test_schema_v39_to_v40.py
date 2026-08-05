"""BETA-AUDIT-11 · migración v39 → v40: poda de diagnósticos de riego.

Limpia lo que ya está en disco: huérfanos de entidades borradas y colas de
diagnósticos sin techo. Solo toca datos DERIVADOS —nunca canon—, así que ninguna otra
colección puede perder nada.
"""

from __future__ import annotations

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v39_to_v40,
    _MAX_DIAGNOSTICS_PER_ENTITY_V40,
)


def _diag(entity_id: str, dia: int) -> dict:
    return {
        "id": f"diag-{entity_id}-{dia}",
        "entity_id": entity_id,
        "created_at": f"2026-01-{dia:02d}T00:00:00+00:00",
        "scores": {"arraigo": 50},
        "summary": f"riego {dia}",
    }


def _proyecto_v39(diagnosticos: list[dict], entidades: list[str]) -> dict:
    return {
        "schema_version": 39,
        "id": "p1",
        "name": "Proyecto v39",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "entities": [{"id": e, "name": e} for e in entidades],
        "relations": [{"id": "r1", "source_id": "a", "target_id": "b"}],
        "causal_milestones": [{"id": "h1", "title": "Un hito"}],
        "narrative_memories": [{"id": "m1"}],
        "watering_diagnostics": diagnosticos,
    }


def test_retira_los_huerfanos():
    datos = _proyecto_v39(
        [_diag("a", 1), _diag("borrada", 2), _diag("b", 3)], entidades=["a", "b"]
    )
    migrado = _apply_migration_v39_to_v40(datos)
    assert {d["entity_id"] for d in migrado["watering_diagnostics"]} == {"a", "b"}
    assert migrado["schema_version"] == 40


def test_recorta_al_tope_conservando_los_mas_recientes():
    exceso = _MAX_DIAGNOSTICS_PER_ENTITY_V40 + 4
    datos = _proyecto_v39([_diag("a", i + 1) for i in range(exceso)], entidades=["a"])
    migrado = _apply_migration_v39_to_v40(datos)
    conservados = migrado["watering_diagnostics"]
    assert len(conservados) == _MAX_DIAGNOSTICS_PER_ENTITY_V40
    dias = sorted(int(d["created_at"][8:10]) for d in conservados)
    assert dias[-1] == exceso, "no conservó el diagnóstico más reciente"
    assert dias[0] == exceso - _MAX_DIAGNOSTICS_PER_ENTITY_V40 + 1


def test_no_pierde_ninguna_otra_coleccion():
    datos = _proyecto_v39([_diag("a", 1)], entidades=["a"])
    migrado = _apply_migration_v39_to_v40(datos)
    for coleccion in ("entities", "relations", "causal_milestones", "narrative_memories"):
        assert migrado[coleccion] == datos[coleccion], f"la migración tocó {coleccion}"


def test_tolera_un_proyecto_sin_diagnosticos():
    datos = _proyecto_v39([], entidades=["a"])
    del datos["watering_diagnostics"]
    migrado = _apply_migration_v39_to_v40(datos)
    assert migrado["watering_diagnostics"] == []
    assert migrado["schema_version"] == 40


def test_es_idempotente():
    exceso = _MAX_DIAGNOSTICS_PER_ENTITY_V40 + 3
    datos = _proyecto_v39([_diag("a", i + 1) for i in range(exceso)], entidades=["a"])
    una = _apply_migration_v39_to_v40(datos)
    dos = _apply_migration_v39_to_v40(dict(una, schema_version=39))
    assert una["watering_diagnostics"] == dos["watering_diagnostics"]


def test_la_version_actual_es_40():
    assert CURRENT_SCHEMA_VERSION == 40


def test_carga_de_extremo_a_extremo_desde_disco(tmp_path):
    """Un fichero v39 real en disco sube a v40 y sale podado."""
    import json

    from packages.persistence.store import ProjectStore

    exceso = _MAX_DIAGNOSTICS_PER_ENTITY_V40 + 2
    datos = _proyecto_v39(
        [_diag("a", i + 1) for i in range(exceso)] + [_diag("fantasma", 1)],
        entidades=["a"],
    )
    # `relations` apunta a ids inexistentes en este fixture mínimo: se limpia para
    # que la validación estructural no rechace el proyecto por otro motivo.
    datos["relations"] = []
    ruta = tmp_path / "v39.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")

    resultado = ProjectStore().load(ruta)
    assert hasattr(resultado, "value"), f"no cargó: {resultado}"
    proyecto = resultado.value
    assert len(proyecto.watering_diagnostics) == _MAX_DIAGNOSTICS_PER_ENTITY_V40
    assert all(d.entity_id == "a" for d in proyecto.watering_diagnostics)
