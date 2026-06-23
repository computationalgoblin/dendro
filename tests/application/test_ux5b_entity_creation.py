"""BETA1-UX5b — creación de entidades correcta (nombre, cuerpo, anillo).

Deterministas (sin modelo). Cubren los bugs reportados por el usuario:
- El cuerpo del modelo debe persistir (`extended_description`, no `body`).
- La entidad nace en el anillo SELECCIONADO/enfocado si lo hay.
- El nombre staged es el real (sin prefijo "Hoja candidata:").
"""
from __future__ import annotations

from packages.application.ai_jobs import AIJobService, AIJobType, _first_active_layer, stage_results
from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.persistence.store import ProjectStore


def _services():
    ps = ProjectService(store=ProjectStore())
    ps.create(name="UX5b")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    return ps, es, rs, CandidateService(ps, es, rs)


def _job(job_type, prompt="haz algo", scope=None):
    ai = AIJobService(provider=None)
    return ai.create_job(job_type, prompt, context_scope=scope or {}, explicit=True).value


def _hoja(result):
    return next(c for c in result["candidates"] if str(c["title"]).startswith("Hoja"))


# ── Cuerpo: extended_description persiste ─────────────────────────────────


def test_hoja_staged_with_extended_description():
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un personaje")
    payload = {"hojas": [
        {"name": "Eldrin", "entity_type": "personaje", "brief_description": "breve",
         "extended_description": "Un mago anciano de larga historia."},
    ]}
    pd = _hoja(stage_results(payload, job))["proposed_data"]
    assert pd["extended_description"] == "Un mago anciano de larga historia."
    assert "body" not in pd  # ya no se usa la clave que se perdía


def test_hoja_body_key_is_mapped_to_extended_description():
    # Compatibilidad: si el modelo devuelve `body`, también debe persistir.
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un personaje")
    payload = {"hojas": [
        {"name": "Mara", "entity_type": "personaje", "body": "Cazadora del norte."},
    ]}
    pd = _hoja(stage_results(payload, job))["proposed_data"]
    assert pd["extended_description"] == "Cazadora del norte."


def test_accepting_hoja_persists_body_to_canon():
    ps, _es, _rs, cands = _services()
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un personaje")
    payload = {"hojas": [
        {"name": "Eldrin", "entity_type": "personaje",
         "extended_description": "Un mago anciano."},
    ]}
    hoja = _hoja(stage_results(payload, job))
    made = cands.create_candidate(hoja).value
    cands.accept_candidate(made.id)
    ent = next(e for e in ps.active_project.entities if e.name == "Eldrin")
    assert ent.extended_description == "Un mago anciano."  # cuerpo NO perdido
    assert ent.name == "Eldrin"  # sin prefijo "Hoja candidata:"


# ── Anillo: nace en el seleccionado/enfocado ──────────────────────────────


def test_first_active_layer_prefers_focused_ring():
    assert _first_active_layer({"active_ring_id": "ring-7"}) == "ring-7"
    assert _first_active_layer({"focused_ring_id": "ring-9"}) == "ring-9"
    # respaldo al filtro visual si no hay anillo enfocado
    assert _first_active_layer({"active_layer_ids": ["ring-1", "ring-2"]}) == "ring-1"
    assert _first_active_layer({}) == ""


def test_hoja_staged_in_focused_ring():
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un personaje",
               scope={"active_ring_id": "ring-7", "active_layer_ids": ["ring-otro"]})
    payload = {"hojas": [{"name": "Eldrin", "entity_type": "personaje"}]}
    pd = _hoja(stage_results(payload, job))["proposed_data"]
    assert pd["layer_ids"] == ["ring-7"]  # el anillo enfocado, no el del filtro


def test_rama_staged_with_extended_description():
    job = _job(AIJobType.GENERATE_TREE, "crea una orden")
    payload = {"ramas": [
        {"name": "Orden del Fuego", "entity_type": "institucion",
         "brief_description": "breve", "extended_description": "Una orden milenaria."},
    ]}
    pd = next(c for c in stage_results(payload, job)["candidates"]
              if str(c["title"]).startswith("Rama"))["proposed_data"]
    assert pd["extended_description"] == "Una orden milenaria."
