"""Fase 2: staging for the new focused job types.

CREATE_RING_TEMPLATE and the structured EDIT_* jobs must produce reviewable
candidates (never canon). Verified end-to-end through run_focused_job with a
stub provider — no real IA needed.
"""
from __future__ import annotations

import json

from packages.application.ai_jobs import (
    AIJobService,
    AIJobStatus,
    AIJobType,
    CommandBarIntent,
    build_job_plan,
)
from packages.application.prompt_assembler import build_model_user_message
from packages.domain.result import Ok


class FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, response: str):
        self.response = response

    def chat(self, system_prompt, user_message, timeout=None, *,
             temperature=None, max_tokens=None, json_mode=False):
        return self.response, None


def _run(job_type, response):
    service = AIJobService(provider=FakeProvider(response))
    result = service.run_focused_job(job_type, "haz algo revisable", context_scope={})
    assert isinstance(result, Ok)
    assert result.value.status == AIJobStatus.READY_FOR_REVIEW
    return result.value.result


def _candidates_of_kind(result, **match):
    out = []
    for c in result["candidates"]:
        data = c.get("proposed_data", {})
        if all(data.get(k) == v for k, v in match.items()):
            out.append(c)
    return out


def test_ring_template_stages_ring_candidates():
    result = _run(
        AIJobType.CREATE_RING_TEMPLATE,
        '{"summary": "Plantilla", "rings": ['
        '{"name": "Materia", "order": 1, "description": "Sustrato"},'
        '{"name": "Vida", "order": 2, "description": "Bio", "derived_from": "Materia"}]}',
    )
    rings = _candidates_of_kind(result, kind="ring_template")
    assert len(rings) == 2
    assert rings[0]["candidate_type"] == "sugerencia_ia"
    assert rings[0]["proposed_data"]["ring_name"] == "Materia"
    assert rings[1]["proposed_data"]["derived_from"] == "Materia"
    # No canon mutation flag.
    assert rings[0]["proposed_data"].get("kind") == "ring_template"


def test_ring_template_does_not_stage_ring_to_ring_relations():
    # The model may volunteer causal relations between rings; the graph has no
    # ring↔ring relation, so none should be staged.
    result = _run(
        AIJobType.CREATE_RING_TEMPLATE,
        '{"rings": [{"name": "Materia", "order": 1}, {"name": "Vida", "order": 2}],'
        ' "relations": [{"source_name": "Materia", "target_name": "Vida", "relation_type": "deriva"}]}',
    )
    assert _candidates_of_kind(result, kind="ring_template")  # rings still staged
    assert all(c["candidate_type"] != "relacion" for c in result["candidates"])


def test_edit_relation_stages_reviewable_edit():
    result = _run(
        AIJobType.EDIT_RELATION,
        '{"relation_edits": [{"target_name": "Ariadna -> Namar", "field": "description",'
        ' "proposed_value": "Una alianza tensa por deudas pasadas.", "rationale": "Da matiz"}]}',
    )
    edits = _candidates_of_kind(result, edit_kind="relation_edits")
    assert len(edits) == 1
    c = edits[0]
    assert c["candidate_type"] == "sugerencia_ia"
    assert c["proposed_data"]["edit_field"] == "description"
    assert "alianza tensa" in c["proposed_data"]["edit_proposed_value"]


def test_edit_ring_and_milestone_stage_edits():
    ring_result = _run(
        AIJobType.EDIT_RING,
        '{"ring_edits": [{"target_name": "Geografía", "field": "order", "proposed_value": "3"}]}',
    )
    assert _candidates_of_kind(ring_result, edit_kind="ring_edits")

    ms_result = _run(
        AIJobType.EDIT_MILESTONE,
        '{"milestone_edits": [{"target_name": "El Juramento Roto", "field": "body",'
        ' "proposed_value": "Se reescribe el origen del conflicto."}]}',
    )
    assert _candidates_of_kind(ms_result, edit_kind="milestone_edits")


def test_edit_jobs_never_emit_structural_entity_candidates():
    result = _run(
        AIJobType.EDIT_RELATION,
        '{"relation_edits": [{"target_name": "A->B", "field": "description",'
        ' "proposed_value": "x"}]}',
    )
    assert all(c["candidate_type"] != "entidad" for c in result["candidates"])


# --- F2.6: model-message directives ---------------------------------------

def _message_for(intent_type, context):
    intent = CommandBarIntent(intent_type, 1.0, "selection", "entity_candidates")
    plan = build_job_plan(intent, "haz algo", context)
    return json.loads(build_model_user_message(plan))


def test_directives_carry_suggestion_count_and_mentions():
    msg = _message_for(AIJobType.GENERATE_ENTITIES, {
        "suggestion_count": 2,
        "mentions": {
            "refs": [{"name": "Guerra del Trono", "ref_id": "h1", "ref_type": "milestone"}],
            "unresolved": [], "overflow": False,
        },
    })
    params = msg["directivas"]["parametros"]
    assert params["numero_sugerencias"] == 2
    assert any("Guerra del Trono" in i for i in msg["directivas"]["instrucciones"])


def test_directives_encode_explain_branching():
    refs = _message_for(AIJobType.EXPLAIN_FROM_CAUSES, {"explain_target": "modify_refs"})
    assert refs["directivas"]["parametros"]["modo_explicar"] == "modificar_referencias"
    ring = _message_for(
        AIJobType.EXPLAIN_FROM_CAUSES,
        {"explain_target": "create_in_active_ring", "active_ring_id": "r1", "max_creations": 3},
    )
    assert ring["directivas"]["parametros"]["modo_explicar"] == "crear_en_anillo_activo"


def test_directives_flag_ring_template_and_fanout_pair():
    rt = _message_for(
        AIJobType.CREATE_RING_TEMPLATE, {"ring_template": True, "previous_ring_id": "r0"}
    )
    assert rt["directivas"]["parametros"]["plantilla_anillo"]["previous_ring_id"] == "r0"
    fo = _message_for(AIJobType.SUGGEST_RELATIONS, {"fanout_pair": ["a", "b"]})
    assert fo["directivas"]["parametros"]["par_relacion"] == ["a", "b"]


def test_no_directives_when_no_overrides():
    msg = _message_for(AIJobType.ANALYZE_COHERENCE, {})
    assert "directivas" not in msg
