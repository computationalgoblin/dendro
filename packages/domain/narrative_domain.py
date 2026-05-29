"""
Narrative domain enum — §10.2.

Provides ``NarrativeDomain``, the structured classification for project domains
(world, history, campaign, shared, unassigned).

Pure domain model — stdlib only.
"""

from __future__ import annotations

from enum import Enum


class NarrativeDomain(str, Enum):
    """Narrative domain classification (§10.2).

    Determines which conceptual domain a narrative entity belongs to.
    An entity can belong to multiple domains via ``NarrativeEntity.domain_ids``.

    Values are lowercase strings for direct use in ``domain_ids: list[str]``.
    """

    MUNDO = "mundo"               # Mundo o escenario
    HISTORIA = "historia"         # Historia
    CAMPANA = "campaña"           # Campaña
    COMPARTIDO = "compartido"     # Material compartido entre varios
    SIN_ASIGNAR = "sin_asignar"   # Material no asignado


# Ordered list for display purposes
NARRATIVE_DOMAIN_ORDER: list[str] = [
    NarrativeDomain.MUNDO.value,
    NarrativeDomain.HISTORIA.value,
    NarrativeDomain.CAMPANA.value,
    NarrativeDomain.COMPARTIDO.value,
    NarrativeDomain.SIN_ASIGNAR.value,
]
