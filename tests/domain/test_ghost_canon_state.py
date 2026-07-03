"""CanonState.FANTASMA — nodos y relaciones fantasma (BETA2-FOCO-01)."""

from __future__ import annotations

import pytest

from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.relation import NarrativeRelation


@pytest.mark.domain
class TestGhostCanonState:
    def test_fantasma_parses_from_string(self):
        assert CanonState("fantasma") == CanonState.FANTASMA

    def test_entity_roundtrip(self):
        e = NarrativeEntity(name="¿Una orden secreta?", canon_state=CanonState.FANTASMA)
        restored = NarrativeEntity.from_dict(e.to_dict())
        assert restored.canon_state == CanonState.FANTASMA
        assert restored.name == "¿Una orden secreta?"

    def test_relation_roundtrip(self):
        r = NarrativeRelation(source_id="a", target_id="b", canon_state=CanonState.FANTASMA)
        restored = NarrativeRelation.from_dict(r.to_dict())
        assert restored.canon_state == CanonState.FANTASMA

    def test_unknown_canon_still_degrades_to_default(self):
        # La tolerancia de _parse_enum no cambia: un valor desconocido cae al default.
        e = NarrativeEntity.from_dict({"id": "e1", "name": "X", "canon_state": "no_existe"})
        assert e.canon_state == CanonState.CANONICO

    def test_default_canon_is_not_fantasma(self):
        # BETA2-FOCO-16 (canon total): las entidades normales nacen CANONICO;
        # fantasma es siempre una elección explícita.
        assert NarrativeEntity(name="Normal").canon_state == CanonState.CANONICO
