"""I29 — Fase DATE: datación validada contra las eras (no bloqueante).

datado / sin_datar / fuera_de_rango; ramas datadas desde el rango de sus miembros;
nada se bloquea (todo sigue presente en el grafo).
"""

from __future__ import annotations

from packages.application.import_dating import apply_dating
from packages.application.import_reconciliation_service import reconcile_mentions
from packages.domain.import_models import (
    ConsolidatedEntity,
    DatingStatus,
    ImportGraph,
)
from packages.domain.result import unwrap

# Eras CERRADAS [0..500] para poder probar el tope superior.
_CLOSED = {"present_year": 400, "eras": [{"name": "Edad", "start_year": 0, "end_year": 500}]}
# Era abierta → sin tope superior.
_OPEN = {"present_year": 1000, "eras": [{"name": "Presente", "start_year": 0, "end_year": None}]}


def _ent(pid, name, **kw):
    return ConsolidatedEntity(provisional_id=pid, name=name, **kw)


def test_undated_is_sin_datar():
    g = ImportGraph(entities=[_ent("imp_e_0001", "X")])
    apply_dating(g, chronology=_CLOSED)
    assert g.entities[0].dating_status is DatingStatus.SIN_DATAR


def test_valid_year_in_range_is_datado():
    g = ImportGraph(entities=[_ent("imp_e_0001", "X", birth_year=100, death_year=300)])
    apply_dating(g, chronology=_CLOSED)
    assert g.entities[0].dating_status is DatingStatus.DATADO


def test_year_out_of_range_is_fuera_de_rango_not_blocking():
    g = ImportGraph(entities=[_ent("imp_e_0001", "X", birth_year=800)])
    apply_dating(g, chronology=_CLOSED)
    assert g.entities[0].dating_status is DatingStatus.FUERA_DE_RANGO
    # No bloquea: la entidad sigue en el grafo.
    assert len(g.entities) == 1


def test_birth_after_death_is_fuera_de_rango():
    g = ImportGraph(entities=[_ent("imp_e_0001", "X", birth_year=300, death_year=100)])
    apply_dating(g, chronology=_CLOSED)
    assert g.entities[0].dating_status is DatingStatus.FUERA_DE_RANGO


def test_open_era_has_no_upper_bound():
    g = ImportGraph(entities=[_ent("imp_e_0001", "X", birth_year=5000)])
    apply_dating(g, chronology=_OPEN)
    assert g.entities[0].dating_status is DatingStatus.DATADO


def test_branch_derives_dating_from_members():
    members = [
        _ent("imp_e_0001", "A", birth_year=100, death_year=200),
        _ent("imp_e_0002", "B", birth_year=150, death_year=400),
    ]
    branch = _ent("imp_b_0001", "Casa", kind="branch",
                  member_ids=["imp_e_0001", "imp_e_0002"])
    g = ImportGraph(entities=[*members, branch])
    apply_dating(g, chronology=_CLOSED)
    assert branch.birth_year == 100   # min de nacimientos
    assert branch.death_year == 400   # máx de muertes
    assert branch.dating_status is DatingStatus.DATADO


def test_no_eras_means_no_range_constraint():
    g = ImportGraph(entities=[_ent("imp_e_0001", "X", birth_year=-9999)])
    apply_dating(g, chronology={})
    # Sin eras definidas no hay rango → datado (hay fecha, sin violación).
    assert g.entities[0].dating_status is DatingStatus.DATADO


def test_reconcile_applies_dating_from_context():
    mentions = [{
        "local_id": "w0_m0", "kind": "entity", "name": "Rey", "body": "Un rey.",
        "birth_year": 800, "relevance": 0.8, "confidence": 0.9, "source_references": [],
    }]
    g = unwrap(reconcile_mentions(mentions, project_context={"chronology_applied": _CLOSED}))
    assert g.metadata["dating_applied"] is True
    assert g.entities[0].dating_status is DatingStatus.FUERA_DE_RANGO
