"""I27 — Fase REDUCE: reconciliación global de menciones → ImportGraph.

Verifica el blocking determinista (fusión por nombre/alias, IDs provisionales,
relaciones reescritas a esos IDs, incidencias conservadas), la degradación sin IA
y el árbitro IA sobre clústeres en zona gris.
"""

from __future__ import annotations

import json

from packages.application.import_reconciliation_service import (
    _apply_merges,
    reconcile_mentions,
)
from packages.domain.result import is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider


def _node(local_id, name, kind="entity", aliases=None, **extra):
    m = {"local_id": local_id, "kind": kind, "name": name, "body": f"{name} aparece.",
         "aliases": aliases or [], "relevance": 0.7, "confidence": 0.8,
         "source_references": [{"segment_id": local_id}]}
    m.update(extra)
    return m


def _rel(local_id, source, target, rtype="protege"):
    return {"local_id": local_id, "kind": "relation", "source_name": source,
            "target_name": target, "relation_type": rtype, "relevance": 0.6,
            "confidence": 0.7, "source_references": []}


def _graph(mentions, **kw):
    res = reconcile_mentions(mentions, **kw)
    assert is_ok(res)
    return unwrap(res)


def test_duplicate_mentions_across_windows_merge_into_one():
    # Misma entidad en dos ventanas, nombre variante (similitud >= 0.86).
    mentions = [
        _node("w0_m0", "Reino del Norte"),
        _node("w1_m0", "Reino Norteno"),
    ]
    g = _graph(mentions)
    assert len(g.entities) == 1
    ent = g.entities[0]
    assert ent.provisional_id == "imp_e_0001"
    # Conserva la traza de ambas menciones.
    assert set(ent.mention_ids) == {"w0_m0", "w1_m0"}


def test_aliases_are_unified():
    mentions = [
        _node("w0_m0", "Arturo", aliases=["Rey Arturo"]),
        _node("w1_m0", "Rey Arturo"),
    ]
    g = _graph(mentions)
    assert len(g.entities) == 1
    ent = g.entities[0]
    all_forms = {ent.name, *ent.aliases}
    assert "Arturo" in all_forms and "Rey Arturo" in all_forms


def test_relations_reference_provisional_ids_not_names():
    mentions = [
        _node("w0_m0", "Aelar"),
        _node("w0_m1", "Lyra"),
        _rel("w0_m2", "Aelar", "Lyra", "protege"),
    ]
    g = _graph(mentions)
    assert len(g.relations) == 1
    rel = g.relations[0]
    pids = {e.name: e.provisional_id for e in g.entities}
    assert rel.source_provisional_id == pids["Aelar"]
    assert rel.target_provisional_id == pids["Lyra"]
    assert rel.relation_type == "protege"
    assert rel.provisional_id == "imp_r_0001"


def test_unresolvable_relation_endpoint_becomes_issue():
    mentions = [
        _node("w0_m0", "Aelar"),
        _rel("w0_m1", "Aelar", "Fantasma Inexistente", "protege"),
    ]
    g = _graph(mentions)
    assert len(g.relations) == 0
    issues = g.metadata["issues"]
    assert any("resoluble" in i["message"] for i in issues)


def test_branch_gets_branch_provisional_id():
    g = _graph([_node("w0_m0", "Los Guardianes", kind="branch", branch_type="faccion")])
    assert g.entities[0].provisional_id == "imp_b_0001"
    assert g.entities[0].is_branch


def test_map_issues_are_preserved():
    mentions = [
        _node("w0_m0", "Aelar"),
        {"local_id": "w0_m1", "kind": "issue", "message": "Fragmento ambiguo.",
         "source_references": []},
    ]
    g = _graph(mentions)
    assert any("ambiguo" in i["message"] for i in g.metadata["issues"])


def test_degradation_without_ai_keeps_gray_band_separate():
    # 0.833 < MERGE_THRESHOLD: sin árbitro IA NO se fusionan.
    mentions = [
        _node("w0_m0", "Casa Vance"),
        _node("w1_m0", "Casa de Vance del Sur"),
    ]
    g = _graph(mentions, provider=None)
    assert len(g.entities) == 2
    assert g.metadata["arbiter_used"] is False


class _MergingArbiter(AIProvider):
    """Árbitro que fusiona los dos clústeres ambiguos (ids 0 y 1)."""

    provider_name = "i27_arbiter"

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps({"merges": [[0, 1]]}), None


def test_arbiter_merges_gray_band_clusters():
    mentions = [
        _node("w0_m0", "Casa Vance"),
        _node("w1_m0", "Casa de Vance del Sur"),
    ]
    g = _graph(mentions, provider=_MergingArbiter())
    assert g.metadata["arbiter_used"] is True
    assert len(g.entities) == 1  # el árbitro las fundió


class _AbstainingArbiter(AIProvider):
    provider_name = "i27_abstain"

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps({"merges": []}), None


def test_arbiter_abstains_keeps_separate():
    mentions = [
        _node("w0_m0", "Casa Vance"),
        _node("w1_m0", "Casa de Vance del Sur"),
    ]
    g = _graph(mentions, provider=_AbstainingArbiter())
    assert len(g.entities) == 2


class _BrokenArbiter(AIProvider):
    provider_name = "i27_broken"

    def chat(self, system_prompt, user_message, timeout=None):
        return None, "HTTP 500"


def test_arbiter_failure_degrades_to_blocking():
    mentions = [
        _node("w0_m0", "Casa Vance"),
        _node("w1_m0", "Casa de Vance del Sur"),
    ]
    g = _graph(mentions, provider=_BrokenArbiter())
    assert len(g.entities) == 2  # falla → blocking determinista


def test_apply_merges_union_find():
    clusters = [
        {"mentions": [_node("a", "A")], "names": {"a"}},
        {"mentions": [_node("b", "B")], "names": {"b"}},
        {"mentions": [_node("c", "C")], "names": {"c"}},
    ]
    merged = _apply_merges(clusters, [{0, 2}])
    assert len(merged) == 2  # 0 y 2 fundidos, 1 aparte


def test_empty_mentions_yield_empty_graph():
    g = _graph([])
    assert g.entities == [] and g.relations == []
