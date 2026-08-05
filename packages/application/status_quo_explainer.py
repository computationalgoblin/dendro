"""Status quo explainer — B41-T07.

Generates a structured report of the current world state using causal milestones,
identifying gaps, orphans, and worldbuilding opportunities. Never mutates canon.
"""

from __future__ import annotations

from typing import Any

from packages.application.causal_links import loose_threads


def explain_status_quo(project: Any) -> dict[str, Any]:
    """Produce a status-quo report for a project using its causal milestones.

    Returns a serializable dict with:
    - summary: text overview
    - hitos_count: number of milestones
    - hitos_without_consequences: hitos que ningún hito posterior recoge
      (`causal_links.loose_threads`, la única implementación de la consulta)
    - relations_without_hito: causal relations not explained by any milestone
    - opportunities: suggestions for worldbuilding expansion
    """
    if project is None:
        return {
            "summary": "No hay proyecto activo.",
            "hitos_count": 0,
            "hitos_without_consequences": 0,
            "relations_without_hito": 0,
            "opportunities": [],
        }

    hitos = list(getattr(project, "causal_milestones", []) or [])
    relations = list(getattr(project, "relations", []) or [])
    entities = list(getattr(project, "entities", []) or [])

    # Hitos «plantados sin recoger». BETA-MULTIAGENT2-FIX-09: aquí vivía la
    # consulta PARALELA (con su propia definición) de la que hay en
    # `causal_milestone_service`. Ahora las dos consumen la MISMA función.
    hitos_without = loose_threads(project)

    # Relations not explained by any milestone
    explained_ids: set[str] = set()
    for hito in hitos:
        explained_ids.update(getattr(hito, "caused_relation_ids", []) or [])

    causal_types = {
        "causo", "fue_causado_por", "deriva_de", "condiciona",
        "explica", "contradice", "produce_consecuencia_en",
    }
    relations_without = [
        r for r in relations
        if _rtype_value(r) in causal_types and getattr(r, "id", "") not in explained_ids
    ]

    # Opportunities: entities with no milestone mention
    mentioned_entities: set[str] = set()
    for hito in hitos:
        mentioned_entities.update(getattr(hito, "affected_entity_ids", []) or [])
    unmentioned = [
        e for e in entities
        if getattr(e, "id", "") not in mentioned_entities
        and getattr(getattr(e, "entity_type", ""), "value", "") != "contenedor"
    ]

    opportunities: list[str] = []
    if unmentioned:
        names = [getattr(e, "name", "?") for e in unmentioned[:5]]
        opportunities.append(
            f"Hojas sin hito asociado: {', '.join(names)}. Considerar qué hitos las afectan."
        )
    if relations_without:
        opportunities.append(
            f"{len(relations_without)} relación(es) causal(es) sin hito explicativo."
        )
    if hitos_without:
        opportunities.append(
            f"{len(hitos_without)} hito(s) sin consecuencias visibles en el grafo."
        )

    summary_parts: list[str] = []
    if hitos:
        summary_parts.append(f"Hay {len(hitos)} hito(s) en el proyecto.")
    else:
        summary_parts.append("No hay hitos definidos todavía.")
    if relations_without:
        summary_parts.append(f"{len(relations_without)} relación(es) carecen de hito explicativo.")
    summary = " ".join(summary_parts)

    return {
        "summary": summary,
        "hitos_count": len(hitos),
        "hitos_without_consequences": len(hitos_without),
        "relations_without_hito": len(relations_without),
        "opportunities": opportunities,
    }


def _rtype_value(rel) -> str:
    rtype = getattr(rel, "relation_type", "")
    if hasattr(rtype, "value"):
        return str(rtype.value).lower()
    return str(rtype).lower()
