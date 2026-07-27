"""BETA-CIERRE WS-C (core): redes de seguridad de datos.

1) La rotación de `.bak` conserva los snapshots MÁS NUEVOS (antes congelaba los más
   viejos y descartaba el recién creado).
2) La carga RECHAZA proyectos con ids duplicados (defensa contra la corrupción por
   doble materialización que arregló SHIP-07); los validadores existían pero no se
   invocaban.
"""

from __future__ import annotations

import json

import pytest

from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


@pytest.mark.persistence
def test_backup_rotation_keeps_newest_not_oldest(tmp_path):
    path = tmp_path / "p.json"
    store = ProjectStore()
    # v1 crea el fichero; v2..v5 crean backups del estado anterior a cada guardado.
    for i in range(1, 6):
        assert isinstance(store.save(Project(name=f"v{i}"), path), Ok)

    backups = store.get_backup_paths(path)
    assert backups, "debería existir al menos una copia de seguridad"
    names = {json.loads(b.read_text(encoding="utf-8"))["name"] for b in backups}

    # El backup más nuevo = el estado justo ANTES del último guardado (v4).
    newest = json.loads(backups[0].read_text(encoding="utf-8"))
    assert newest["name"] == "v4", f"rotación congelada en un estado viejo: {names}"
    # Y jamás debe sobrevivir el estado más viejo cuando hay rotación.
    assert "v1" not in names, f"la rotación conserva el más viejo: {names}"


@pytest.mark.persistence
def test_load_rejects_duplicate_entity_ids(tmp_path):
    path = tmp_path / "dup_ent.json"
    store = ProjectStore()
    assert isinstance(store.save(Project(name="ok"), path), Ok)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["entities"] = [
        {"id": "dup", "name": "A", "entity_type": "personaje"},
        {"id": "dup", "name": "B", "entity_type": "personaje"},
    ]
    path.write_text(json.dumps(data), encoding="utf-8")

    result = store.load(path)
    assert isinstance(result, Error)
    assert "duplicate entity id" in result.error.lower()


@pytest.mark.persistence
def test_load_rejects_duplicate_relation_ids(tmp_path):
    path = tmp_path / "dup_rel.json"
    store = ProjectStore()
    assert isinstance(store.save(Project(name="ok"), path), Ok)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["entities"] = [
        {"id": "e1", "name": "A", "entity_type": "personaje"},
        {"id": "e2", "name": "B", "entity_type": "personaje"},
    ]
    data["relations"] = [
        {"id": "rdup", "source_id": "e1", "target_id": "e2",
         "relation_type": "esta_relacionado_con"},
        {"id": "rdup", "source_id": "e2", "target_id": "e1",
         "relation_type": "esta_relacionado_con"},
    ]
    path.write_text(json.dumps(data), encoding="utf-8")

    result = store.load(path)
    assert isinstance(result, Error)
    assert "duplicate relation id" in result.error.lower()


@pytest.mark.persistence
def test_load_still_accepts_a_normal_project(tmp_path):
    # Guarda contra over-rejection: un proyecto normal (ids únicos) sigue cargando.
    path = tmp_path / "ok.json"
    store = ProjectStore()
    project = Project(name="Mundo")
    assert isinstance(store.save(project, path), Ok)
    result = store.load(path)
    assert isinstance(result, Ok)
    assert result.value.name == "Mundo"
