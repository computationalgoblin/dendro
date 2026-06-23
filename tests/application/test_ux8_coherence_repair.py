"""UX8 — reparación de coherencia: cambios CONCRETOS sobre canon (no literales).

Cubre el núcleo host-agnóstico:
- normalize_repair_changes: valida/normaliza la salida del modelo.
- resolve_repair_changes: antes/después/etiqueta/aplicable contra el canon actual.
- apply_resolved_change: aplica cada tipo de cambio vía servicios de aplicación.
- stage_results / run_focused_job: el job REPAIR_COHERENCE devuelve un plan, no semillas.
"""
from __future__ import annotations

import json

from packages.application.ai_jobs import AIJobService, AIJobType
from packages.application.coherence_repair import (
    apply_resolved_change,
    normalize_repair_changes,
    resolve_repair_changes,
)
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.result import Ok
from packages.persistence.store import ProjectStore


def _services():
    ps = ProjectService(store=ProjectStore())
    ps.create(name="UX8")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    return ps, es, rs


class _FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, response: str):
        self.response = response

    def chat(self, system_prompt, user_message, timeout=None, *,
             temperature=None, max_tokens=None, json_mode=False):
        return self.response, None


# ── normalize ───────────────────────────────────────────────────────────────


def test_normalize_drops_invalid_and_vague_changes():
    raw = [
        {"change_type": "edit_entity", "entity_name": "Vex", "proposed_value": "Texto."},
        {"change_type": "edit_entity", "entity_name": "Vex"},  # sin texto → fuera
        {"change_type": "unknown_type", "entity_name": "x", "proposed_value": "y"},  # tipo inválido
        {"change_type": "create_relation", "source_name": "A", "target_name": "B"},  # sin contenido
        "no-dict",
    ]
    out = normalize_repair_changes(raw)
    assert len(out) == 1
    assert out[0]["change_type"] == "edit_entity"
    assert out[0]["field"] == "body"  # default


def test_normalize_relation_requires_endpoints_and_some_content():
    out = normalize_repair_changes([
        {"change_type": "create_relation", "source_name": "A", "target_name": "B",
         "relation_type": "es_enemigo_de"},
    ])
    assert len(out) == 1 and out[0]["relation_type"] == "es_enemigo_de"


# ── resolve (antes/después) ───────────────────────────────────────────────────


def test_resolve_edit_entity_before_after_and_applicable():
    ps, es, _rs = _services()
    es.create_entity({"name": "Casa Vex", "entity_type": "contenedor",
                      "extended_description": "Una casa noble."})
    changes = normalize_repair_changes([
        {"change_type": "edit_entity", "entity_name": "Casa Vex", "field": "body",
         "proposed_value": "Casa noble en declive."},
        {"change_type": "edit_entity", "entity_name": "Inexistente", "field": "body",
         "proposed_value": "x"},
    ])
    res = resolve_repair_changes(changes, ps.active_project)
    assert res[0]["before"] == "Una casa noble."
    assert res[0]["after"] == "Casa noble en declive."
    assert res[0]["applicable"] is True
    assert "cuerpo" in res[0]["label"]
    assert res[1]["applicable"] is False  # entidad inexistente


def test_resolve_create_relation_marks_no_existe():
    ps, es, _rs = _services()
    es.create_entity({"name": "A", "entity_type": "personaje"})
    es.create_entity({"name": "B", "entity_type": "personaje"})
    changes = normalize_repair_changes([
        {"change_type": "create_relation", "source_name": "A", "target_name": "B",
         "relation_type": "es_enemigo_de", "body": "Rivalidad antigua."},
    ])
    res = resolve_repair_changes(changes, ps.active_project)
    assert res[0]["before"] == "(no existe)"
    assert res[0]["after"] == "Rivalidad antigua."
    assert res[0]["applicable"] is True


# ── apply ─────────────────────────────────────────────────────────────────────


def test_apply_edit_entity_writes_canon():
    ps, es, rs = _services()
    es.create_entity({"name": "Casa Vex", "entity_type": "contenedor",
                      "extended_description": "Una casa noble."})
    changes = normalize_repair_changes([
        {"change_type": "edit_entity", "entity_name": "Casa Vex", "field": "body",
         "proposed_value": "Casa noble en declive."},
    ])
    res = resolve_repair_changes(changes, ps.active_project)
    out = apply_resolved_change(res[0], project=ps.active_project,
                                entity_service=es, relation_service=rs)
    assert isinstance(out, Ok)
    ent = next(e for e in ps.active_project.entities if e.name == "Casa Vex")
    assert ent.extended_description == "Casa noble en declive."


def test_apply_create_relation_with_body():
    ps, es, rs = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    changes = normalize_repair_changes([
        {"change_type": "create_relation", "source_name": "A", "target_name": "B",
         "relation_type": "es_enemigo_de", "description": "Enemigos.",
         "body": "Rivalidad antigua."},
    ])
    res = resolve_repair_changes(changes, ps.active_project)
    out = apply_resolved_change(res[0], project=ps.active_project,
                                entity_service=es, relation_service=rs)
    assert isinstance(out, Ok)
    rel = ps.active_project.relations[0]
    assert {rel.source_id, rel.target_id} == {a.id, b.id}
    assert rel.relation_type.value == "es_enemigo_de"
    assert rel.custom_metadata.get("_body") == "Rivalidad antigua."


def test_apply_edit_relation_updates_type_and_body():
    ps, es, rs = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    rs.create_relation(source_id=a.id, target_id=b.id, relation_type="es_aliado_de", data={})
    changes = normalize_repair_changes([
        {"change_type": "edit_relation", "source_name": "A", "target_name": "B",
         "relation_type": "es_enemigo_de", "body": "Ahora se odian."},
    ])
    res = resolve_repair_changes(changes, ps.active_project)
    out = apply_resolved_change(res[0], project=ps.active_project,
                                entity_service=es, relation_service=rs)
    assert isinstance(out, Ok)
    rel = ps.active_project.relations[0]
    assert rel.relation_type.value == "es_enemigo_de"
    assert rel.custom_metadata.get("_body") == "Ahora se odian."


def test_apply_uses_edited_after_text():
    # El usuario edita el texto «después» antes de aplicar → se aplica lo editado.
    ps, es, rs = _services()
    es.create_entity({"name": "Casa Vex", "entity_type": "contenedor",
                      "extended_description": "viejo"})
    changes = normalize_repair_changes([
        {"change_type": "edit_entity", "entity_name": "Casa Vex", "field": "body",
         "proposed_value": "propuesta IA"},
    ])
    res = resolve_repair_changes(changes, ps.active_project)
    res[0]["after"] = "texto editado por el usuario"
    apply_resolved_change(res[0], project=ps.active_project,
                          entity_service=es, relation_service=rs)
    ent = next(e for e in ps.active_project.entities if e.name == "Casa Vex")
    assert ent.extended_description == "texto editado por el usuario"


def test_apply_create_milestone():
    ps, es, rs = _services()
    changes = normalize_repair_changes([
        {"change_type": "create_milestone", "title": "La Ruptura", "summary": "Cae la casa."},
    ])
    res = resolve_repair_changes(changes, ps.active_project)
    out = apply_resolved_change(res[0], project=ps.active_project,
                                entity_service=es, relation_service=rs)
    assert isinstance(out, Ok)
    assert any(m.title == "La Ruptura" for m in ps.active_project.causal_milestones)


# ── pipeline: el job no produce semillas, sino un plan ─────────────────────────


def test_repair_job_returns_plan_not_candidates():
    payload = {
        "summary": "2 reparaciones",
        "repair_changes": [
            {"change_type": "edit_entity", "entity_name": "Vex", "field": "body",
             "proposed_value": "Texto reparado."},
            {"change_type": "vago"},  # se descarta
        ],
    }
    ai = AIJobService(provider=_FakeProvider(json.dumps(payload)))
    result = ai.run_focused_job(AIJobType.REPAIR_COHERENCE, "repara", context_scope={})
    assert isinstance(result, Ok)
    data = result.value.result
    assert data["kind"] == "repair_plan"
    assert data["candidates"] == []  # nunca semillas
    assert len(data["repair_changes"]) == 1  # el vago se descartó
