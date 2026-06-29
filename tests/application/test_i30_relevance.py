"""I30 — Relevancia en dos niveles (scoring + tiering en el grafo).

El umbral asigna RelevanceTier (fuerte/marginal) sin descartar nada: ambos niveles
viven en el grafo para que el asistente los presente en secciones distintas.
"""

from __future__ import annotations

from packages.application.import_reconciliation_service import (
    RELEVANCE_STRONG_THRESHOLD,
    apply_relevance_tiers,
    reconcile_mentions,
)
from packages.domain.import_models import ConsolidatedEntity, ImportGraph, RelevanceTier
from packages.domain.result import unwrap


def _node(local_id, name, relevance):
    return {"local_id": local_id, "kind": "entity", "name": name,
            "body": f"{name} aparece.", "relevance": relevance, "confidence": 0.8,
            "source_references": []}


def test_above_threshold_is_strong_below_is_marginal():
    mentions = [
        _node("w0_m0", "Protagonista", 0.95),
        _node("w0_m1", "Aldea Menor", 0.2),
    ]
    g = unwrap(reconcile_mentions(mentions))
    by_name = {e.name: e for e in g.entities}
    assert by_name["Protagonista"].relevance_tier is RelevanceTier.FUERTE
    assert by_name["Aldea Menor"].relevance_tier is RelevanceTier.MARGINAL


def test_nothing_is_discarded():
    mentions = [_node(f"w0_m{i}", f"E{i}", 0.1) for i in range(5)]
    g = unwrap(reconcile_mentions(mentions))
    # Todos marginales, pero TODOS presentes.
    assert len(g.entities) == 5
    assert all(e.relevance_tier is RelevanceTier.MARGINAL for e in g.entities)


def test_threshold_recorded_in_metadata():
    g = unwrap(reconcile_mentions([_node("w0_m0", "X", 0.8)]))
    assert g.metadata["relevance_threshold"] == RELEVANCE_STRONG_THRESHOLD


def test_apply_relevance_tiers_custom_threshold():
    g = ImportGraph(entities=[
        ConsolidatedEntity(provisional_id="imp_e_0001", name="A", relevance=0.5),
        ConsolidatedEntity(provisional_id="imp_e_0002", name="B", relevance=0.85),
    ])
    apply_relevance_tiers(g, threshold=0.8)
    assert g.entities[0].relevance_tier is RelevanceTier.MARGINAL
    assert g.entities[1].relevance_tier is RelevanceTier.FUERTE


def test_exact_threshold_is_strong():
    g = ImportGraph(entities=[
        ConsolidatedEntity(provisional_id="imp_e_0001", name="A",
                           relevance=RELEVANCE_STRONG_THRESHOLD),
    ])
    apply_relevance_tiers(g)
    assert g.entities[0].relevance_tier is RelevanceTier.FUERTE
