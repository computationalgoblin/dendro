"""BETA1-UX4 — arreglos de los comandos de la command bar (deterministas, sin modelo)."""
from __future__ import annotations

from packages.application.ai_jobs import AIJobService, AIJobType, stage_results
from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.entity import NarrativeEntity, normalize_entity_type
from packages.domain.result import Error
from packages.infrastructure.ai_provider import SimulatedAIProvider
from packages.persistence.store import ProjectStore


def _services():
    ps = ProjectService(store=ProjectStore())
    ps.create(name="UX4")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    return ps, es, rs, CandidateService(ps, es, rs)


def _job(job_type, prompt="haz algo", scope=None):
    ai = AIJobService(provider=SimulatedAIProvider())
    return ai.create_job(job_type, prompt, context_scope=scope or {}, explicit=True).value


def _rama_candidate(result):
    return next(c for c in result["candidates"] if str(c["title"]).startswith("Rama"))


def _accept(cands, cand):
    return cands.accept_candidate(cands.create_candidate(cand).value.id)


def _by_id(ps, entity_id):
    return next(e for e in ps.active_project.entities if e.id == entity_id)


# ── Fix 1 (C1/C2): Crear Rama → contenedor ───────────────────────────────


def test_rama_staged_as_contenedor_preserving_semantic_type():
    job = _job(AIJobType.GENERATE_TREE, "crea una orden de monjes")
    payload = {"ramas": [
        {"name": "Orden del Fuego", "entity_type": "religion", "brief_description": "x"},
    ]}
    pd = _rama_candidate(stage_results(payload, job))["proposed_data"]
    assert pd["entity_type"] == "contenedor"  # el render lo dibuja como árbol
    meta = pd["custom_metadata"]
    assert meta["semantic_type"] == "religion"  # tipo rico preservado aparte
    assert meta["display_type"] == "rama"       # marcador que sobrevive a from_dict
    assert meta["candidate_tree"] is True


def test_accepting_rama_creates_contenedor_entity():
    ps, _es, _rs, cands = _services()
    job = _job(AIJobType.GENERATE_TREE, "crea una orden")
    payload = {"ramas": [{"name": "Orden del Fuego", "entity_type": "institucion"}]}
    rama = _rama_candidate(stage_results(payload, job))
    made = cands.create_candidate(rama).value
    acc = cands.accept_candidate(made.id)
    assert not hasattr(acc, "error") or acc.__class__.__name__ == "Ok"
    ent = ps.active_project.entities[-1]
    assert ent.entity_type.value == "contenedor"  # => render como contenedor
    assert ent.custom_metadata.get("semantic_type") == "institucion"
    assert ent.custom_metadata.get("candidate_tree") is True


def test_accepting_populated_rama_creates_children_with_contiene():
    ps, _es, _rs, cands = _services()
    job = _job(AIJobType.GENERATE_TREE, "crea una orden con jerarquía")
    payload = {"ramas": [{
        "name": "Orden del Fuego",
        "entity_type": "institucion",
        "hojas": [
            {"name": "Gran Maestre", "entity_type": "personaje"},
            {"name": "Novicio", "entity_type": "personaje"},
        ],
    }]}
    rama = _rama_candidate(stage_results(payload, job))
    assert len(rama["proposed_data"]["child_leaves"]) == 2
    made = cands.create_candidate(rama).value
    cands.accept_candidate(made.id)
    proj = ps.active_project
    # 1 contenedor + 2 hojas hijas
    names = {e.name for e in proj.entities}
    assert {"Orden del Fuego", "Gran Maestre", "Novicio"} <= names
    container = next(e for e in proj.entities if e.name == "Orden del Fuego")
    assert container.entity_type.value == "contenedor"
    # 2 relaciones 'contiene' del contenedor a sus hojas
    contiene = [r for r in proj.relations
                if r.relation_type.value == "contiene" and r.source_id == container.id]
    assert len(contiene) == 2


def test_empty_rama_creates_no_children():
    ps, _es, _rs, cands = _services()
    job = _job(AIJobType.GENERATE_TREE, "crea una orden vacía")
    payload = {"ramas": [{"name": "Orden Hueca", "entity_type": "institucion"}]}
    rama = _rama_candidate(stage_results(payload, job))
    cands.accept_candidate(cands.create_candidate(rama).value.id)
    assert len(ps.active_project.entities) == 1  # solo el contenedor
    assert ps.active_project.relations == []


# ── UX5d: rama con entidades SELECCIONADAS las inserta, no las duplica ──────


def _two_jinns(es):
    a = es.create_entity({"name": "Jinn de Fuego", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "Jinn de Humo", "entity_type": "personaje"}).value
    return a.id, b.id


def test_rama_with_selection_drops_generated_hojas_and_keeps_existing_members():
    ps, es, _rs, cands = _services()
    id_a, id_b = _two_jinns(es)
    job = _job(
        AIJobType.GENERATE_TREE, "crea una rama con los dos jinns",
        scope={"selected_entity_ids": [id_a, id_b]},
    )
    # El modelo regurgita los jinns como hojas NUEVAS (lo que causaba los duplicados).
    payload = {"ramas": [{
        "name": "Cofradía de los Jinn", "entity_type": "faccion",
        "hojas": [
            {"name": "Jinn de Fuego", "entity_type": "personaje"},
            {"name": "Jinn de Humo", "entity_type": "personaje"},
        ],
    }]}
    pd = _rama_candidate(stage_results(payload, job))["proposed_data"]
    assert pd["child_leaves"] == []  # se descartan: no se duplican
    assert pd["contained_entity_ids"] == [id_a, id_b]  # miembros = selección existente


def test_accepting_rama_with_selection_links_existing_without_creating_new():
    ps, es, _rs, cands = _services()
    id_a, id_b = _two_jinns(es)
    job = _job(
        AIJobType.GENERATE_TREE, "crea una rama con los dos jinns",
        scope={"selected_entity_ids": [id_a, id_b]},
    )
    payload = {"ramas": [{
        "name": "Cofradía de los Jinn", "entity_type": "faccion",
        "hojas": [{"name": "Jinn de Fuego", "entity_type": "personaje"}],
    }]}
    rama = _rama_candidate(stage_results(payload, job))
    cands.accept_candidate(cands.create_candidate(rama).value.id)
    proj = ps.active_project
    # 2 jinns + 1 rama = 3 entidades; NO se crearon jinns nuevos
    assert len(proj.entities) == 3
    assert sum(1 for e in proj.entities if e.name == "Jinn de Fuego") == 1
    container = next(e for e in proj.entities if e.name == "Cofradía de los Jinn")
    contiene = [r for r in proj.relations
                if r.relation_type.value == "contiene" and r.source_id == container.id]
    assert {r.target_id for r in contiene} == {id_a, id_b}


def test_rama_without_selection_keeps_generated_hojas():
    # Control: sin selección, la rama sigue naciendo con las hojas del modelo.
    job = _job(AIJobType.GENERATE_TREE, "crea una orden con jerarquía")
    payload = {"ramas": [{
        "name": "Orden del Fuego", "entity_type": "institucion",
        "hojas": [{"name": "Gran Maestre", "entity_type": "personaje"}],
    }]}
    pd = _rama_candidate(stage_results(payload, job))["proposed_data"]
    assert len(pd["child_leaves"]) == 1
    assert pd["contained_entity_ids"] == []


# ── UX5f: crear una entidad con una RAMA seleccionada la inserta EN la rama ──


def _hoja_candidate(result):
    return next(c for c in result["candidates"] if str(c["title"]).startswith("Hoja"))


def test_creating_hoja_with_branch_selected_inserts_it_into_branch():
    ps, es, _rs, cands = _services()
    rama = es.create_entity({"name": "Casa Vex", "entity_type": "contenedor",
                             "layer_ids": ["ring1"]}).value
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un heredero",
               {"selected_entity_ids": [rama.id]})
    payload = {"hojas": [{"name": "Lyra Vex", "entity_type": "personaje"}]}
    hoja = _hoja_candidate(stage_results(payload, job))
    cands.accept_candidate(cands.create_candidate(hoja).value.id)
    proj = ps.active_project
    nueva = next(e for e in proj.entities if e.name == "Lyra Vex")
    contiene = [r for r in proj.relations
                if r.relation_type.value == "contiene"
                and r.source_id == rama.id and r.target_id == nueva.id]
    assert len(contiene) == 1  # la hoja entra DENTRO de la rama
    assert nueva.layer_ids == ["ring1"]  # hereda el anillo del contenedor


def test_creating_hoja_with_non_container_selected_does_not_contain():
    # Control: si lo seleccionado NO es una rama, no se inserta en nada.
    ps, es, _rs, cands = _services()
    other = es.create_entity({"name": "Korr", "entity_type": "personaje"}).value
    job = _job(AIJobType.GENERATE_ENTITIES, "crea otro",
               {"selected_entity_ids": [other.id]})
    payload = {"hojas": [{"name": "Aldric", "entity_type": "personaje"}]}
    hoja = _hoja_candidate(stage_results(payload, job))
    cands.accept_candidate(cands.create_candidate(hoja).value.id)
    assert all(r.relation_type.value != "contiene" for r in ps.active_project.relations)


def test_creating_hoja_referencing_branch_does_not_insert():
    # @ mención (no selección): la rama se referencia pero la hoja NO entra en ella.
    ps, es, _rs, cands = _services()
    es.create_entity({"name": "Casa Vex", "entity_type": "contenedor"}).value
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un aliado de @Casa Vex",
               {"selected_entity_ids": []})  # solo mencionada, no seleccionada
    payload = {"hojas": [{"name": "Externo", "entity_type": "personaje"}]}
    hoja = _hoja_candidate(stage_results(payload, job))
    cands.accept_candidate(cands.create_candidate(hoja).value.id)
    assert all(r.relation_type.value != "contiene" for r in ps.active_project.relations)


def test_hoja_still_renders_as_leaf():
    # Control: una hoja normal NO debe volverse contenedor.
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un herrero")
    payload = {"hojas": [{"name": "Aldric", "entity_type": "personaje"}]}
    hoja = next(c for c in stage_results(payload, job)["candidates"]
                if str(c["title"]).startswith("Hoja"))
    assert hoja["proposed_data"]["entity_type"] == "personaje"


# ── Fix 2 (C5): Editar aplica a canon al aceptar ─────────────────────────


def _edit_candidate(result):
    # PLAY-15: la forma canónica del candidato de edición es `edit_fields`
    # (patch multi-campo); el escalar viejo pervive solo en candidatos ya
    # persistidos, no en los recién stageados.
    return next(c for c in result["candidates"]
                if (c.get("proposed_data") or {}).get("edit_fields")
                or (c.get("proposed_data") or {}).get("edit_proposed_value"))


def test_accepting_entity_edit_applies_to_canon():
    ps, es, _rs, cands = _services()
    ent = es.create_entity({"name": "Aldric", "entity_type": "personaje",
                            "extended_description": "Un herrero."}).value
    job = _job(AIJobType.EDIT_ENTITIES, "más sombrío", {"selected_entity_ids": [ent.id]})
    payload = {"entity_edits": [
        {"entity_name": "Aldric", "field": "body", "proposed_value": "Cicatriz y deuda."},
    ]}
    _accept(cands, _edit_candidate(stage_results(payload, job)))
    assert _by_id(ps, ent.id).extended_description == "Cicatriz y deuda."


def test_accepting_entity_edit_brief_field():
    ps, es, _rs, cands = _services()
    ent = es.create_entity({"name": "Mara", "entity_type": "personaje"}).value
    job = _job(AIJobType.EDIT_ENTITIES, "x", {"selected_entity_ids": [ent.id]})
    payload = {"entity_edits": [
        {"entity_name": "Mara", "field": "brief_description", "proposed_value": "Espía taciturna."},
    ]}
    _accept(cands, _edit_candidate(stage_results(payload, job)))
    assert _by_id(ps, ent.id).brief_description == "Espía taciturna."


def test_accepting_relation_edit_applies_to_canon():
    ps, es, rs, cands = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    rel = rs.create_relation(source_id=a.id, target_id=b.id,
                             relation_type="es_aliado_de", data={}).value
    job = _job(AIJobType.EDIT_RELATION, "rivalidad", {"selected_relation_ids": [rel.id]})
    payload = {"relation_edits": [
        {"target_name": "A → B", "field": "description", "proposed_value": "Rivalidad latente."},
    ]}
    _accept(cands, _edit_candidate(stage_results(payload, job)))
    assert ps.active_project.relations[0].description == "Rivalidad latente."


def test_accepting_ring_edit_applies_to_canon():
    from packages.domain.world_layer import WorldLayer
    ps, _es, _rs, cands = _services()
    ps.active_project.world_layers.append(
        WorldLayer(id="ring1", name="Geografía", description="viejo", order=0,
                   is_visible=True, is_default=False))
    job = _job(AIJobType.EDIT_RING, "más árido", {})
    payload = {"ring_edits": [
        {"target_name": "Geografía", "field": "description", "proposed_value": "Clima árido."},
    ]}
    _accept(cands, _edit_candidate(stage_results(payload, job)))
    layer = next(x for x in ps.active_project.world_layers if x.name == "Geografía")
    assert layer.description == "Clima árido."


def test_accepting_milestone_edit_applies_to_canon():
    from packages.domain.causal_milestone import CausalMilestone
    ps, _es, _rs, cands = _services()
    ps.active_project.causal_milestones.append(
        CausalMilestone.from_dict({"title": "Fundación", "description": "viejo"}))
    job = _job(AIJobType.EDIT_MILESTONE, "x", {})
    payload = {"milestone_edits": [
        {"target_name": "Fundación", "field": "description", "proposed_value": "Nueva desc."},
    ]}
    _accept(cands, _edit_candidate(stage_results(payload, job)))
    hito = next(m for m in ps.active_project.causal_milestones if m.title == "Fundación")
    assert hito.description == "Nueva desc."


def test_accepting_milestone_year_edit_redates_in_canon():
    """DC-UX4-HITO: 'adelanta un siglo' → editar la datación (year) del hito."""
    from packages.domain.causal_milestone import CausalMilestone
    ps, _es, _rs, cands = _services()
    ps.active_project.causal_milestones.append(
        CausalMilestone.from_dict({"title": "Caída", "description": "x", "year": 1200}))
    job = _job(AIJobType.EDIT_MILESTONE, "adelanta un siglo", {})
    payload = {"milestone_edits": [
        {"target_name": "Caída", "field": "year", "proposed_value": "1100"},
    ]}
    _accept(cands, _edit_candidate(stage_results(payload, job)))
    hito = next(m for m in ps.active_project.causal_milestones if m.title == "Caída")
    assert hito.year == 1100
    assert hito.temporality.year == 1100  # espejo entero autoritativo (J01)


def test_accepting_milestone_year_edit_rejects_non_integer():
    """Un 'año' no numérico no debe corromper la datación: accept devuelve Error."""
    from packages.domain.causal_milestone import CausalMilestone
    ps, _es, _rs, cands = _services()
    ps.active_project.causal_milestones.append(
        CausalMilestone.from_dict({"title": "Caída", "year": 1200}))
    job = _job(AIJobType.EDIT_MILESTONE, "x", {})
    payload = {"milestone_edits": [
        {"target_name": "Caída", "field": "year", "proposed_value": "hace mucho"},
    ]}
    made = cands.create_candidate(_edit_candidate(stage_results(payload, job))).value
    res = cands.accept_candidate(made.id)
    assert isinstance(res, Error)
    hito = next(m for m in ps.active_project.causal_milestones if m.title == "Caída")
    assert hito.year == 1200  # intacto


def test_selected_milestone_brief_carries_current_year_and_text():
    """DC-UX4-HITO: el hito seleccionado debe viajar al modelo con sus datos vigentes."""
    from packages.application.ai_jobs import _selected_milestones_brief
    from packages.domain.causal_milestone import CausalMilestone
    ps, _es, _rs, _cands = _services()
    hito = CausalMilestone.from_dict(
        {"title": "Caída de Vael", "description": "El reino se hundió.", "year": 1200})
    ps.active_project.causal_milestones.append(hito)
    briefs = _selected_milestones_brief(
        ps.active_project, {"selected_milestone_ids": [hito.id]})
    assert briefs == [{"id": hito.id, "title": "Caída de Vael",
                       "year": 1200, "description": "El reino se hundió."}]


def test_selection_block_renders_selected_milestones_for_the_prompt():
    """El bloque de selección expone los hitos al prompt (no solo entidades/anillos)."""
    from packages.application.prompt_assembler import _selection_block
    block = _selection_block({"selected_milestones": [
        {"id": "m1", "title": "Caída de Vael", "year": 1200, "description": "x"}]})
    assert block["hitos_seleccionados"][0]["year"] == 1200
    assert "coherencia_hito" in block  # instrucción de editar a partir del dato vigente


# ── Fix 3 (C6): Crear Relación usa el par exacto de la selección ──────────


def test_crear_relacion_uses_fanout_pair_ids_ignoring_model_names():
    ps, es, rs, cands = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    job = _job(AIJobType.SUGGEST_RELATIONS, "relaciona",
               {"selected_entity_ids": [a.id, b.id], "fanout_pair": [a.id, b.id]})
    # El modelo inventa nombres que NO casan con la selección.
    payload = {"relations": [
        {"source_name": "Inexistente1", "target_name": "Inexistente2",
         "relation_type": "es_enemigo_de", "description": "rivalidad latente"},
    ]}
    rel = next(c for c in stage_results(payload, job)["candidates"]
               if c["candidate_type"] == "relacion")
    pd = rel["proposed_data"]
    assert pd["source_id"] == a.id and pd["target_id"] == b.id  # ids reales del par
    assert pd["relation_type"] == "es_enemigo_de"
    cands.accept_candidate(cands.create_candidate(rel).value.id)
    created = ps.active_project.relations
    assert len(created) == 1
    assert {created[0].source_id, created[0].target_id} == {a.id, b.id}


def test_crear_relacion_synthesizes_pair_even_without_model_relations():
    ps, es, rs, cands = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    job = _job(AIJobType.SUGGEST_RELATIONS, "relaciona",
               {"selected_entity_ids": [a.id, b.id], "fanout_pair": [a.id, b.id]})
    payload = {"summary": "sin relaciones", "relations": []}  # modelo no devuelve nada
    rels = [c for c in stage_results(payload, job)["candidates"]
            if c["candidate_type"] == "relacion"]
    assert len(rels) == 1
    pd = rels[0]["proposed_data"]
    assert {pd["source_id"], pd["target_id"]} == {a.id, b.id}


# ── UX5g: una relación creada rellena descripción breve Y cuerpo ──────────


def _relation_candidate(result):
    return next(c for c in result["candidates"] if c["candidate_type"] == "relacion")


def test_relation_candidate_carries_body_in_custom_metadata():
    ps, es, _rs, cands = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    job = _job(AIJobType.SUGGEST_RELATIONS, "relaciona",
               {"selected_entity_ids": [a.id, b.id], "fanout_pair": [a.id, b.id]})
    payload = {"relations": [
        {"source_name": "A", "target_name": "B", "relation_type": "es_aliado_de",
         "description": "Aliados de conveniencia.", "body": "Su alianza nació en la guerra."},
    ]}
    pd = _relation_candidate(stage_results(payload, job))["proposed_data"]
    assert pd["description"] == "Aliados de conveniencia."  # breve
    assert pd["custom_metadata"]["_body"] == "Su alianza nació en la guerra."  # cuerpo


def test_accepting_relation_fills_both_description_and_body():
    ps, es, _rs, cands = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    job = _job(AIJobType.SUGGEST_RELATIONS, "relaciona",
               {"selected_entity_ids": [a.id, b.id], "fanout_pair": [a.id, b.id]})
    payload = {"relations": [
        {"source_name": "A", "target_name": "B", "relation_type": "es_aliado_de",
         "description": "Aliados de conveniencia.", "body": "Su alianza nació en la guerra."},
    ]}
    rel = _relation_candidate(stage_results(payload, job))
    cands.accept_candidate(cands.create_candidate(rel).value.id)
    created = ps.active_project.relations[0]
    assert created.description == "Aliados de conveniencia."
    assert created.custom_metadata.get("_body") == "Su alianza nació en la guerra."


def test_relation_without_body_omits_empty_custom_metadata():
    # Control: si el modelo no da cuerpo, no se inyecta un _body vacío.
    job = _job(AIJobType.SUGGEST_RELATIONS, "relaciona", {"fanout_pair": ["a", "b"]})
    payload = {"relations": [
        {"source_name": "A", "target_name": "B", "relation_type": "es_aliado_de",
         "description": "Solo breve."},
    ]}
    pd = _relation_candidate(stage_results(payload, job))["proposed_data"]
    assert "custom_metadata" not in pd


# ── Fix 4 (C3): taxonomía fiel (sin degradar a nota) ─────────────────────


def test_normalize_entity_type_maps_known_synonyms():
    assert normalize_entity_type("concepto") == "regla_del_mundo"
    assert normalize_entity_type("ley") == "regla_del_mundo"
    assert normalize_entity_type("lugar") == "localizacion"
    assert normalize_entity_type("organizacion") == "institucion"
    assert normalize_entity_type("raza") == "criatura"
    # un tipo ya válido pasa intacto; uno desconocido también (lo gestiona _parse_enum)
    assert normalize_entity_type("personaje") == "personaje"
    assert normalize_entity_type("xyz") == "xyz"


def test_from_dict_does_not_degrade_known_synonym_to_nota():
    ent = NarrativeEntity.from_dict({"name": "El Vacío", "entity_type": "concepto"})
    assert ent.entity_type.value == "regla_del_mundo"  # antes: nota


def test_accepting_hoja_with_synonym_type_keeps_meaning():
    ps, _es, _rs, cands = _services()
    job = _job(AIJobType.GENERATE_ENTITIES, "crea un concepto")
    payload = {"hojas": [{"name": "Equilibrio", "entity_type": "concepto"}]}
    hoja = next(c for c in stage_results(payload, job)["candidates"]
                if str(c["title"]).startswith("Hoja"))
    cands.accept_candidate(cands.create_candidate(hoja).value.id)
    assert ps.active_project.entities[-1].entity_type.value == "regla_del_mundo"


def test_entity_edit_falls_back_to_selection_when_name_mismatch():
    # Si el modelo nombra mal la entidad, se aplica a la seleccionada (respaldo).
    ps, es, _rs, cands = _services()
    ent = es.create_entity({"name": "Korr", "entity_type": "personaje"}).value
    job = _job(AIJobType.EDIT_ENTITIES, "x", {"selected_entity_ids": [ent.id]})
    payload = {"entity_edits": [
        {"entity_name": "Nombre Que No Existe", "field": "body", "proposed_value": "Texto nuevo."},
    ]}
    _accept(cands, _edit_candidate(stage_results(payload, job)))
    assert _by_id(ps, ent.id).extended_description == "Texto nuevo."


# ── UX5e: editar una relación produce UNA sola semilla (tipo + contenido) ──


def _relation_edit_candidates(result):
    return [c for c in result["candidates"]
            if (c.get("proposed_data") or {}).get("edit_kind") == "relation_edits"]


def test_relation_edit_two_field_entries_collapse_into_one_seed():
    # El modelo parte la edición en dos entradas (tipo y descripción) para la MISMA
    # relación → debe salir UNA sola semilla con ambos campos (bug reportado: dos).
    job = _job(AIJobType.EDIT_RELATION, "rivalidad", {"selected_relation_ids": ["r1"]})
    payload = {"relation_edits": [
        {"target_name": "A → B", "field": "relation_type", "proposed_value": "es_enemigo_de"},
        {"target_name": "A → B", "field": "description", "proposed_value": "Rivalidad latente."},
    ]}
    edits = _relation_edit_candidates(stage_results(payload, job))
    assert len(edits) == 1
    pd = edits[0]["proposed_data"]
    assert pd["edit_relation_type"] == "es_enemigo_de"
    assert pd["edit_proposed_value"] == "Rivalidad latente."


def test_relation_edit_combined_format_single_seed():
    job = _job(AIJobType.EDIT_RELATION, "rivalidad", {"selected_relation_ids": ["r1"]})
    payload = {"relation_edits": [
        {"target_name": "A → B", "relation_type": "es_enemigo_de",
         "description": "Rivalidad latente."},
    ]}
    edits = _relation_edit_candidates(stage_results(payload, job))
    assert len(edits) == 1
    pd = edits[0]["proposed_data"]
    assert pd["edit_relation_type"] == "es_enemigo_de"
    assert pd["edit_proposed_value"] == "Rivalidad latente."


def test_accepting_relation_edit_applies_both_type_and_description():
    ps, es, rs, cands = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    rel = rs.create_relation(source_id=a.id, target_id=b.id,
                             relation_type="es_aliado_de", data={}).value
    job = _job(AIJobType.EDIT_RELATION, "rivalidad", {"selected_relation_ids": [rel.id]})
    payload = {"relation_edits": [
        {"target_name": "A → B", "relation_type": "es_enemigo_de",
         "description": "Rivalidad latente."},
    ]}
    edits = _relation_edit_candidates(stage_results(payload, job))
    cands.accept_candidate(cands.create_candidate(edits[0]).value.id)
    updated = ps.active_project.relations[0]
    assert updated.relation_type.value == "es_enemigo_de"
    assert updated.description == "Rivalidad latente."


def test_accepting_type_only_relation_edit_applies_type():
    # Edición solo de tipo (sin contenido nuevo): una sola semilla, se aplica el tipo.
    ps, es, rs, cands = _services()
    a = es.create_entity({"name": "A", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "B", "entity_type": "personaje"}).value
    rel = rs.create_relation(source_id=a.id, target_id=b.id,
                             relation_type="es_aliado_de",
                             data={"description": "Vieja descripción."}).value
    job = _job(AIJobType.EDIT_RELATION, "ahora rivales", {"selected_relation_ids": [rel.id]})
    payload = {"relation_edits": [
        {"target_name": "A → B", "relation_type": "es_enemigo_de"},
    ]}
    edits = _relation_edit_candidates(stage_results(payload, job))
    assert len(edits) == 1
    assert edits[0]["proposed_data"]["edit_proposed_value"] == ""  # sin contenido nuevo
    cands.accept_candidate(cands.create_candidate(edits[0]).value.id)
    updated = ps.active_project.relations[0]
    assert updated.relation_type.value == "es_enemigo_de"
    assert updated.description == "Vieja descripción."  # descripción intacta
