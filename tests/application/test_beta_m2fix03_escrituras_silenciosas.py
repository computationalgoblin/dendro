"""BETA2-FIX-03 (G2-03) — escrituras que se perdían devolviendo Ok.

Dos caminos distintos, el mismo delito: la app tiraba el dato y decía que sí.

- `create_entity`/`update_entity` descartaban en silencio toda clave que no
  conocían (el showrunner del beta escribió 19 fichas con `description` y las
  19 nacieron vacías; regó a su protagonista sobre una ficha en blanco).
- aceptar una semilla de HITO lo appendeaba con los defaults del dominio
  (`status=candidate`, `created_at=""`, sin `candidate_id`) mientras el toast
  prometía «Semilla integrada al canon».

Deterministas: sin proveedor de IA, sin Qt.
"""

from __future__ import annotations

from packages.application.ai_jobs import AIJobService, AIJobType, stage_results
from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.coherence_repair import (
    apply_resolved_change,
    normalize_repair_changes,
    resolve_repair_changes,
)
from packages.application.command_prompts import system_prompt_for_intent
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.application.temporal_dating import PENDING_NOTE
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


def _services():
    ps = ProjectService(store=ProjectStore())
    ps.create(name="FIX03")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    cs = CandidateService(ps, es, rs)
    return ps, es, rs, cs


def _job(job_type=AIJobType.SUGGEST_COMPOSITE, prompt="haz algo", scope=None):
    ai = AIJobService(provider=None)
    return ai.create_job(job_type, prompt, context_scope=scope or {}, explicit=True).value


# ── A · entidades: ninguna clave se cae en silencio ────────────────────────


def test_create_entity_no_devuelve_ok_tirando_la_descripcion():
    """La firma EXACTA del tester (guionista-serie/sesion_1.py:81-91)."""
    _ps, es, _rs, _cs = _services()
    result = es.create_entity(
        {
            "name": "Nadia Ferrán",
            "entity_type": "personaje",
            "layer_ids": ["ring-1"],
            "description": "Ingeniera de reciclaje de la Cubierta 9.",
            "birth_year": -30,
        }
    )
    assert isinstance(result, Ok), getattr(result, "error", "")
    # Lo que el validador del arnés comprobaba y daba FAIL 19 veces.
    assert result.value.brief_description == "Ingeniera de reciclaje de la Cubierta 9."
    assert result.value.birth_year == -30


def test_create_entity_clave_desconocida_sin_alias_devuelve_error_que_la_nombra():
    _ps, es, _rs, _cs = _services()
    for clave in ("descripcion", "resumen"):
        result = es.create_entity(
            {"name": "X", "entity_type": "personaje", clave: "algo importante"}
        )
        assert isinstance(result, Error), f"{clave} pasó en silencio"
        assert clave in result.error  # nombra la clave
        assert "brief_description" in result.error  # y lista las válidas
    # y nada llegó al proyecto
    assert not _ps.active_project.entities


def test_create_entity_acepta_el_payload_real_de_stage_results():
    """Red de seguridad: el rechazo duro NO puede romper la aceptación de semillas."""
    ps, _es, _rs, cands = _services()
    job = _job(AIJobType.GENERATE_ENTITIES, "crea gente")
    staged = stage_results(
        {
            "hojas": [
                {
                    "name": "Eldrin",
                    "entity_type": "personaje",
                    "brief_description": "breve",
                    "body": "Un mago anciano.",
                    "temporal_nature": "mortal",
                }
            ],
            "ramas": [
                {
                    "name": "Orden del Fuego",
                    "entity_type": "institucion",
                    "brief_description": "una orden",
                    "hojas": [{"name": "Novicio", "entity_type": "personaje"}],
                }
            ],
        },
        job,
    )
    for raw in staged["candidates"]:
        made = cands.create_candidate(raw)
        assert isinstance(made, Ok), getattr(made, "error", "")
        accepted = cands.accept_candidate(made.value.id)
        assert isinstance(accepted, Ok), getattr(accepted, "error", "")
    names = {e.name for e in ps.active_project.entities}
    assert {"Eldrin", "Orden del Fuego", "Novicio"} <= names
    eldrin = next(e for e in ps.active_project.entities if e.name == "Eldrin")
    assert eldrin.extended_description == "Un mago anciano."


def test_update_entity_clave_desconocida_no_se_ignora_en_silencio():
    _ps, es, _rs, _cs = _services()
    ent = es.create_entity({"name": "Marta", "entity_type": "personaje"}).value
    result = es.update_entity(ent.id, {"resumen": "texto que se perdía"})
    assert isinstance(result, Error)
    assert "resumen" in result.error
    # y el alias documentado SÍ escribe donde debe
    ok_result = es.update_entity(ent.id, {"description": "Traductora."})
    assert isinstance(ok_result, Ok), getattr(ok_result, "error", "")
    assert ok_result.value.brief_description == "Traductora."


# ── B · el hito aceptado entra PROMOVIDO ───────────────────────────────────


def _stage_hito(cands, *, year=None, extra=None):
    job = _job(AIJobType.SUGGEST_COMPOSITE, "propón un hito")
    milestone = {"title": "El ultimátum de la carta", "summary": "Marta responde."}
    if year is not None:
        milestone["year"] = year
    milestone.update(extra or {})
    staged = stage_results({"hitos": [milestone]}, job)
    raw = next(c for c in staged["candidates"] if "Hito" in str(c["title"]))
    return cands.create_candidate(raw).value


def test_aceptar_semilla_de_hito_entra_como_canon_con_fechas_y_candidate_id():
    ps, _es, _rs, cands = _services()
    cand = _stage_hito(cands, year=2024)
    accepted = cands.accept_candidate(cand.id)
    assert isinstance(accepted, Ok), getattr(accepted, "error", "")

    hito = ps.active_project.causal_milestones[-1]
    assert hito.status.value == "canon"
    assert hito.created_at
    assert hito.updated_at
    assert hito.candidate_id == cand.id
    assert hito.year == 2024
    # y sobrevive al round-trip de disco (es lo que Nerea fue a leer)
    assert hito.to_dict()["status"] == "canon"


def test_aceptar_semilla_de_hito_sin_anio_queda_por_datar():
    ps, _es, _rs, cands = _services()
    cand = _stage_hito(cands)  # sin year: la IA no lo propuso
    assert isinstance(cands.accept_candidate(cand.id), Ok)

    hito = ps.active_project.causal_milestones[-1]
    assert hito.year is None  # ningún año inventado
    assert hito.temporality.notes == PENDING_NOTE  # marcado «por datar»
    assert hito.status.value == "canon"


def test_aprobar_hito_por_el_servicio_de_hitos_sigue_promoviendo():
    """La ruta buena (approve_hito) no se rompe al extraer el helper común."""
    ps, es, rs, cands = _services()
    hitos = CausalMilestoneService(project_service=ps, candidate_service=cands)
    created = hitos.create_hito_candidate(
        {"title": "Ilona empieza el diario", "year": 1978}
    )
    assert isinstance(created, Ok), getattr(created, "error", "")
    approved = hitos.approve_hito(created.value.id)
    assert isinstance(approved, Ok), getattr(approved, "error", "")
    assert approved.value.status.value == "canon"
    assert approved.value.created_at and approved.value.updated_at
    assert approved.value.candidate_id == created.value.id
    assert ps.active_project.causal_milestones[-1].id == approved.value.id
    assert es is not None and rs is not None


# ── C · la reparación de coherencia ────────────────────────────────────────


def test_reparacion_de_coherencia_crea_hito_canonico():
    ps, es, rs, _cs = _services()
    changes = normalize_repair_changes(
        [
            {
                "change_type": "create_milestone",
                "title": "La caída del canal",
                "summary": "El canal abierto se corta.",
            }
        ]
    )
    resolved = resolve_repair_changes(changes, ps.active_project)
    assert resolved, "el cambio de reparación no se resolvió"
    applied = apply_resolved_change(
        resolved[0],
        project=ps.active_project,
        entity_service=es,
        relation_service=rs,
    )
    assert isinstance(applied, Ok), getattr(applied, "error", "")

    hito = ps.active_project.causal_milestones[-1]
    assert hito.status.value == "canon"
    assert hito.created_at
    assert hito.updated_at


# ── D/E · río arriba: el año se pide y el orden no se fabrica ──────────────


def test_prompt_suggest_composite_pide_year_en_hitos():
    prompt = system_prompt_for_intent("suggest_composite")
    hitos_block = prompt.split('"hitos"', 1)
    assert len(hitos_block) == 2, "el prompt no declara el formato de hitos"
    # el `year` va DENTRO del bloque de hitos, antes del siguiente tipo
    bloque = hitos_block[1].split('"entity_edits"', 1)[0]
    assert '"year"' in bloque


def test_stage_results_no_fabrica_sort_index_cero():
    job = _job(AIJobType.SUGGEST_COMPOSITE, "propón un hito")
    staged = stage_results({"hitos": [{"title": "Sin orden", "summary": "x"}]}, job)
    raw = next(c for c in staged["candidates"] if "Hito" in str(c["title"]))
    meta = raw["proposed_data"]["milestone"]["metadata"]
    assert "sort_index" not in meta  # antes se estampaba 0 en TODO hito de IA

    # y si el modelo SÍ lo propone, se respeta
    staged2 = stage_results(
        {"hitos": [{"title": "Con orden", "summary": "x", "sort_index": 2}]}, job
    )
    raw2 = next(c for c in staged2["candidates"] if "Hito" in str(c["title"]))
    assert raw2["proposed_data"]["milestone"]["metadata"]["sort_index"] == 2


def test_stage_results_estadia_el_year_que_propone_el_modelo():
    job = _job(AIJobType.SUGGEST_COMPOSITE, "propón un hito")
    staged = stage_results({"hitos": [{"title": "Datado", "year": 2024}]}, job)
    raw = next(c for c in staged["candidates"] if "Hito" in str(c["title"]))
    assert raw["proposed_data"]["milestone"]["year"] == 2024


# ── F · relaciones: el aplanado silencioso ─────────────────────────────────


def test_create_relation_rechaza_tipo_fuera_del_dominio():
    ps, es, rs, _cs = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value

    result = rs.create_relation(a.id, b.id, "traduce_a")
    assert isinstance(result, Error)
    assert "traduce_a" in result.error
    assert "esta_relacionado_con" in result.error  # lista los válidos
    assert not ps.active_project.relations  # nada se guardó aplanado

    # vacío/None siguen siendo el default EXPLÍCITO
    default_none = rs.create_relation(a.id, b.id, None)
    assert isinstance(default_none, Ok), getattr(default_none, "error", "")
    assert default_none.value.relation_type.value == "esta_relacionado_con"

    # y un tipo del dominio se guarda TAL CUAL
    real = rs.create_relation(a.id, b.id, "causo")
    assert isinstance(real, Ok), getattr(real, "error", "")
    assert real.value.relation_type.value == "causo"


def test_create_relation_no_aplana_el_tipo_que_llega_en_data():
    ps, es, rs, _cs = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    result = rs.create_relation(
        a.id, b.id, None, {"relation_type": "hermana_de", "description": "x"}
    )
    assert isinstance(result, Error)
    assert "hermana_de" in result.error
    assert not ps.active_project.relations
