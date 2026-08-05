"""BETA-MULTIAGENT-FIX-06: mensajería honesta (G-09 parcial del beta multi-agente).

- El mensaje de proveedor no configurado no menciona la CLI (eliminada en WS-G).
- Los errores de validación de servicios llegan en español.
- Un entity_type inventado se RECHAZA al crear; from_dict sigue tolerante (cargas).
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.application.ai_jobs import AIJobService
from packages.application.custom_type_service import CustomTypeService
from packages.application.entity_service import EntityService
from packages.application.era_service import EraService
from packages.application.world_layer_service import WorldLayerService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Error, Ok


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _ps() -> _FakeProjectService:
    return _FakeProjectService(active_project=Project(name="Mensajes"))


# ── Proveedor no configurado: sin CLI, con Ajustes ──────────────────────────


def test_provider_unconfigured_message_sin_cli():
    svc = AIJobService()  # sin provider → simulado → no configurado
    job = svc.create_job("water_entity", "prompt", context_scope={}, explicit=True)
    assert isinstance(job, Ok)
    result = svc.execute_job(job.value.id)
    assert isinstance(result, Error)
    assert "IA no configurada" in result.error
    assert "Ajustes" in result.error
    assert "CLI" not in result.error
    assert "NARRATIVE_AI_" not in result.error


# ── Errores de validación en español ────────────────────────────────────────


def test_create_entity_nombre_vacio_en_espanol():
    res = EntityService(_ps()).create_entity({"name": "", "entity_type": "personaje"})
    assert isinstance(res, Error)
    assert "nombre" in res.error.lower()
    assert "empty" not in res.error.lower()


def test_create_era_nombre_vacio_en_espanol():
    res = EraService(_ps()).create_era({"name": ""})
    assert isinstance(res, Error)
    assert "era" in res.error.lower()
    assert "empty" not in res.error.lower()


def test_create_layer_nombre_vacio_en_espanol():
    res = WorldLayerService(_ps()).create_layer("")
    assert isinstance(res, Error)
    assert "anillo" in res.error.lower()
    assert "empty" not in res.error.lower()


def test_create_custom_type_nombre_vacio_en_espanol():
    res = CustomTypeService(_ps()).create_entity_type({"name": "", "description": ""})
    assert isinstance(res, Error)
    assert "empty" not in res.error.lower()


# ── entity_type inventado: rechazo al crear, tolerancia al cargar ───────────


def test_create_entity_tipo_inventado_rechaza_con_tipos_validos():
    res = EntityService(_ps()).create_entity({"name": "Dragonzote", "entity_type": "dragonzote"})
    assert isinstance(res, Error)
    assert "dragonzote" in res.error
    assert "personaje" in res.error  # lista los tipos válidos


def test_create_entity_tipo_valido_y_sinonimo_siguen_funcionando():
    svc = EntityService(_ps())
    ok = svc.create_entity({"name": "Yara", "entity_type": "personaje"})
    assert isinstance(ok, Ok)
    assert ok.value.entity_type is EntityType.PERSONAJE


def test_from_dict_tipo_inventado_sigue_tolerante_para_cargas():
    entity = NarrativeEntity.from_dict({"name": "Vieja", "entity_type": "dragonzote"})
    assert entity.entity_type is EntityType.NOTA  # coerción de CARGA preservada
