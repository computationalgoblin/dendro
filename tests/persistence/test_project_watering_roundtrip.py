"""Persistencia del jardín: riego, secadas, fantasmas y última entidad (BETA2-FOCO-01).

Roundtrip real en disco con ``ProjectStore`` (guardado atómico + migración al cargar).
"""

from __future__ import annotations

import json

import pytest

from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.domain.watering import WateringDiagnostic
from packages.persistence.store import ProjectStore


def _project_with_watering() -> Project:
    project = Project(name="Jardín")
    entity = NarrativeEntity(name="Eldrin")
    ghost = NarrativeEntity(name="¿Una orden secreta?", canon_state=CanonState.FANTASMA)
    project.entities.extend([entity, ghost])
    project.watering_diagnostics.append(
        WateringDiagnostic(
            entity_id=entity.id,
            scores={"arraigo": 30, "nutrida": 70, "iluminada": 20, "relevancia": 50},
            summary="Necesita raíces.",
            metric_explanations={"arraigo": "Sin contexto previo que la haga verosímil."},
            risks=["Flota sin causa"],
            context_manifest={"entity_ids": [entity.id], "estimated_tokens": 900},
            provider="simulated",
            model="sim-1",
            cost_class="bajo",
        )
    )
    project.watering_paused_entity_ids.append(entity.id)
    project.metadata["last_worked_entity_id"] = entity.id
    return project


@pytest.mark.persistence
class TestWateringRoundtrip:
    def test_save_and_load_preserves_watering(self, tmp_path):
        store = ProjectStore()
        path = tmp_path / "proyecto.json"
        project = _project_with_watering()
        entity_id = project.entities[0].id

        save_result = store.save(project, path)
        assert isinstance(save_result, Ok), getattr(save_result, "error", None)

        load_result = store.load(path)
        assert isinstance(load_result, Ok), getattr(load_result, "error", None)
        loaded = load_result.value

        assert len(loaded.watering_diagnostics) == 1
        diag = loaded.watering_diagnostics[0]
        assert diag.entity_id == entity_id
        assert diag.scores == {"arraigo": 30, "nutrida": 70, "iluminada": 20, "relevancia": 50}
        assert diag.summary == "Necesita raíces."
        assert diag.metric_explanations["arraigo"].startswith("Sin contexto")
        assert diag.context_manifest["estimated_tokens"] == 900

        assert loaded.watering_paused_entity_ids == [entity_id]
        assert loaded.metadata["last_worked_entity_id"] == entity_id

        ghosts = [e for e in loaded.entities if e.canon_state == CanonState.FANTASMA]
        assert len(ghosts) == 1
        assert ghosts[0].name == "¿Una orden secreta?"

    def test_v32_project_file_loads_and_migrates(self, tmp_path):
        # Proyecto antiguo (v32, sin colecciones de riego) debe cargar sin pérdida.
        path = tmp_path / "viejo.json"
        raw = {
            "schema_version": 32,
            "id": "p32",
            "name": "Antiguo",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "entities": [{"id": "e1", "name": "Eldrin"}],
            "relations": [],
        }
        path.write_text(json.dumps(raw), encoding="utf-8")

        store = ProjectStore()
        load_result = store.load(path)
        assert isinstance(load_result, Ok), getattr(load_result, "error", None)
        loaded = load_result.value

        assert loaded.watering_diagnostics == []
        assert loaded.watering_paused_entity_ids == []
        assert loaded.entities[0].name == "Eldrin"

    def test_v33_roundtrip_without_migration(self, tmp_path):
        # Guardar (v33) y recargar: no debe pasar por migración ni perder nada.
        store = ProjectStore()
        path = tmp_path / "nuevo.json"
        store.save(_project_with_watering(), path)

        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["schema_version"] == 33

        reloaded = store.load(path)
        assert isinstance(reloaded, Ok)
        assert len(reloaded.value.watering_diagnostics) == 1
