"""BETA-MULTIAGENT2-FIX-03 (G2-03) — la Cronología deja de decir «Orden 0».

El mundo de la diseñadora de producto (`ux-producto/mundo/la-traductora.json`):
`present_year = 0`, seis hitos escritos a mano SIN `sort_index` y uno de la IA
con `sort_index = 0` fabricado por `ai_jobs`. Solo ese llevaba sub-etiqueta, y
era un nombre de campo interno («Orden») asomando por la interfaz.

La capa de cálculo (`build_chrono_layout`, `_milestone_sub_label`) es pura: se
testea sin ventana, con la plataforma offscreen.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from hosts.DesktopHostPySide.widgets.chrono_canvas import (  # noqa: E402
    _milestone_sub_label,
    build_chrono_layout,
)
from packages.application.ai_jobs import AIJobService, AIJobType, stage_results  # noqa: E402
from packages.application.candidate_service import CandidateService  # noqa: E402
from packages.application.entity_service import EntityService  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.application.relation_service import RelationService  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


def _world():
    ps = ProjectService()
    assert isinstance(ps.create("FIX03 crono"), Ok)
    ps.active_project.project_chronology.present_year = 0
    es = EntityService(ps, ps.store)
    rs = RelationService(project_service=ps)
    es.create_entity({"name": "Marta", "entity_type": "personaje", "birth_year": 1990})
    return ps, CandidateService(ps, es, rs)


def _aceptar_hito_ia(cands, milestone: dict) -> str:
    ai = AIJobService(provider=None)
    job = ai.create_job(
        AIJobType.SUGGEST_COMPOSITE, "propón un hito", context_scope={}, explicit=True
    ).value
    staged = stage_results({"hitos": [milestone]}, job)
    raw = next(c for c in staged["candidates"] if "Hito" in str(c["title"]))
    cand = cands.create_candidate(raw).value
    accepted = cands.accept_candidate(cand.id)
    assert isinstance(accepted, Ok), getattr(accepted, "error", "")
    return cand.id


def test_beta_m2fix03_hito_aceptado_no_muestra_orden_cero():
    ps, cands = _world()
    _aceptar_hito_ia(cands, {"title": "El ultimátum de la carta", "summary": "x"})

    layout = build_chrono_layout(ps.active_project)
    marks = [m for m in layout.milestones if m.title == "El ultimátum de la carta"]
    assert marks, "el hito aceptado no llegó al layout de la Cronología"
    for mark in marks:
        assert "Orden" not in mark.sub_label
        assert mark.sub_label == ""


def test_beta_m2fix03_hito_aceptado_es_canon_con_fechas():
    """El mismo accept que dibuja la Cronología deja el registro honesto."""
    ps, cands = _world()
    cand_id = _aceptar_hito_ia(
        cands, {"title": "Marta encuentra la carta", "summary": "x", "year": 2024}
    )
    hito = ps.active_project.causal_milestones[-1]
    assert hito.status.value == "canon"
    assert hito.created_at and hito.updated_at
    assert hito.candidate_id == cand_id
    assert hito.year == 2024


def test_beta_m2fix03_sub_label_solo_con_posicion_real():
    class _Hito:
        def __init__(self, meta):
            self.metadata = meta

    assert _milestone_sub_label(_Hito({"sort_index": 0})) == ""
    assert _milestone_sub_label(_Hito({})) == ""
    assert _milestone_sub_label(_Hito({"sort_index": None})) == ""
    assert "Orden" not in _milestone_sub_label(_Hito({"sort_index": 2}))
    assert _milestone_sub_label(_Hito({"sort_index": 2})) == "2.º"
    # el desambiguador de calendario completo (mes/día) no se toca
    assert _milestone_sub_label(_Hito({"exact_date": {"month": "3", "day": "14"}})) == "3 14"
