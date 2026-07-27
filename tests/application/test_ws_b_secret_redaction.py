"""BETA-CIERRE WS-B (B1): los secretos NUNCA se transmiten a la IA.

Verifica la redacción en los cuatro bordes de egreso hacia el proveedor:
watering context, índice compacto de la wiki, y navegación (búsqueda + read_canon/open_page).
El contenido reservado no aparece en lo que viajaría en el prompt; el canon completo sigue
disponible para la UI (no se toca el modelo).
"""

from __future__ import annotations

import pytest

from packages.application.ai_privacy import is_withheld_from_ai, relation_withheld
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.watering_service import WateringService
from packages.application.wiki_index_service import WikiIndexService
from packages.application.wiki_navigator import WikiNavigator
from packages.domain.entity import CanonState, NarrativeEntity, VisibilityState
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok

# Texto distintivo que NO debe salir jamás al proveedor.
SECRET = "conspira-para-derrocar-al-rey"
SECRET_NAME = "Mordax el Traidor"


def _ps_with_secret():
    ps = ProjectService()
    ps.create("Jardín")
    project = ps.active_project
    hero = NarrativeEntity(
        id="hero", name="Ana", brief_description="Reina en el exilio.",
        visibility_state=VisibilityState.VISIBLE_USUARIO,
    )
    ally = NarrativeEntity(
        id="ally", name="Beto", brief_description="Aliado leal y público.",
        visibility_state=VisibilityState.VISIBLE_USUARIO,
    )
    villain = NarrativeEntity(
        id="villain", name=SECRET_NAME, brief_description=SECRET,
        extended_description=SECRET, visibility_state=VisibilityState.SECRETO_MUNDO,
    )
    project.entities.extend([hero, ally, villain])
    project.relations.append(
        NarrativeRelation(id="r_ally", source_id="hero", target_id="ally",
                          relation_type=RelationType.ESTA_RELACIONADO_CON))
    project.relations.append(
        NarrativeRelation(id="r_vill", source_id="hero", target_id="villain",
                          relation_type=RelationType.ESTA_RELACIONADO_CON))
    project.touch()
    return ps, project


@pytest.mark.application
def test_predicate_flags_secret_states_only():
    def e(**kw):
        return NarrativeEntity(name="x", **kw)

    assert is_withheld_from_ai(e(visibility_state=VisibilityState.SECRETO_MUNDO))
    assert is_withheld_from_ai(e(visibility_state=VisibilityState.PRIVADO_AUTOR))
    assert is_withheld_from_ai(e(visibility_state=VisibilityState.NO_EXPORTABLE))
    assert is_withheld_from_ai(e(visibility_state=VisibilityState.PREPARADO_NO_REVELADO))
    assert is_withheld_from_ai(e(canon_state=CanonState.SECRETO_CANONICO))
    # Defaults (VISIBLE_USUARIO / CANONICO) no se ocultan — la IA sigue funcionando.
    assert not is_withheld_from_ai(e())
    assert not is_withheld_from_ai(e(visibility_state=VisibilityState.PUBLICO_MUNDO))
    assert not is_withheld_from_ai(None)


@pytest.mark.application
def test_watering_context_redacts_secret_neighbor_but_keeps_public():
    ps, _ = _ps_with_secret()
    watering = WateringService(ps, ai_job_service=None, history_service=HistoryService(ps))
    res = watering.build_watering_context("hero")
    assert isinstance(res, Ok), res.error if isinstance(res, Error) else ""
    text = res.value["text"]
    assert SECRET not in text
    assert SECRET_NAME not in text
    assert "[entidad reservada]" in text  # la vecina secreta viaja redactada
    assert "Beto" in text  # ...pero la vecina pública NO se redacta (sin over-redaction)


@pytest.mark.application
def test_watering_refuses_secret_focus():
    ps, _ = _ps_with_secret()
    watering = WateringService(ps, ai_job_service=None, history_service=HistoryService(ps))
    res = watering.build_watering_context("villain")
    assert isinstance(res, Error)
    assert "reservada" in res.error.lower()


@pytest.mark.application
def test_index_marks_secret_and_compact_redacts():
    _, project = _ps_with_secret()
    index = WikiIndexService().build_index(project).value
    villain = index.entry_for("entity", "villain")
    assert villain.secret is True
    ally = index.entry_for("entity", "ally")
    assert ally.secret is False
    # Relación con extremo secreto también reservada.
    assert index.entry_for("relation", "r_vill").secret is True
    assert index.entry_for("relation", "r_ally").secret is False
    # El índice compacto (lo que viaja a la IA) no filtra nombre ni contenido secretos.
    compact = WikiIndexService().compact_for_prompt(index)
    blob = str(compact)
    assert SECRET not in blob
    assert SECRET_NAME not in blob
    assert "Beto" in blob  # los públicos siguen apareciendo


@pytest.mark.application
def test_navigator_search_and_reads_never_serve_secret():
    ps, project = _ps_with_secret()
    nav = WikiNavigator(project_service=ps)
    index = WikiIndexService().build_index(project).value
    # Búsqueda: aunque la query casa con el secreto, no aparece en los resultados.
    search = nav._do_search(index, "Mordax Traidor derrocar")
    ids = [hit["id"] for hit in (search or {}).get("resultados", [])]
    assert "villain" not in ids
    def fulfill(op, target_id):
        return nav._fulfill(project, index, {"op": op, "kind": "entity", "id": target_id})

    # read_canon / open_page de un elemento reservado no sirven nada.
    assert fulfill("read_canon", "villain") is None
    assert fulfill("open_page", "villain") is None
    # ...pero un elemento público sí se sirve.
    served = fulfill("read_canon", "ally")
    assert served is not None and served["id"] == "ally"


@pytest.mark.application
def test_relation_withheld_when_endpoint_secret():
    _, project = _ps_with_secret()
    r_vill = project.relation_by_id("r_vill")
    r_ally = project.relation_by_id("r_ally")
    assert relation_withheld(project, r_vill) is True
    assert relation_withheld(project, r_ally) is False
