"""Tests for Bloque 21 secrets domain models (B21-T01)."""

from __future__ import annotations

import pytest

from packages.domain.secrets_models import (
    RevelationState,
    DeliveryState,
    ClueForm,
    Secreto,
    Pista,
    _now,
    _parse_enum,
    _parse_list,
    _parse_str,
    _parse_int,
    _parse_dict,
    _clamp_range,
)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


class TestClampRange:
    def test_clamp_in_range(self):
        assert _clamp_range(3, 1, 5, 3) == 3

    def test_clamp_below_min(self):
        assert _clamp_range(0, 1, 5, 3) == 1

    def test_clamp_above_max(self):
        assert _clamp_range(7, 1, 5, 3) == 5

    def test_clamp_none_returns_default(self):
        assert _clamp_range(None, 1, 5, 3) == 3

    def test_clamp_bool_returns_default(self):
        assert _clamp_range(True, 1, 5, 3) == 3

    def test_clamp_float(self):
        # round(4.7) = 5, clamped to 5
        assert _clamp_range(4.7, 1, 5, 3) == 5

    def test_clamp_string(self):
        assert _clamp_range("5", 1, 5, 3) == 5

    def test_clamp_invalid_string_returns_default(self):
        assert _clamp_range("bogus", 1, 5, 3) == 3


# ═══════════════════════════════════════════════════════════════════════
# RevelationState
# ═══════════════════════════════════════════════════════════════════════


class TestRevelationState:
    def test_five_values(self):
        states = list(RevelationState)
        assert len(states) == 5
        values = {s.value for s in states}
        assert values == {"oculto", "parcialmente_revelado", "revelado", "rumoreado", "malinterpretado"}

    def test_is_str_enum(self):
        assert RevelationState.oculto == "oculto"

    def test_parse_invalid_returns_default(self):
        assert _parse_enum(RevelationState, "inventado", RevelationState.oculto) == RevelationState.oculto


# ═══════════════════════════════════════════════════════════════════════
# DeliveryState
# ═══════════════════════════════════════════════════════════════════════


class TestDeliveryState:
    def test_five_values(self):
        states = list(DeliveryState)
        assert len(states) == 5
        values = {s.value for s in states}
        assert values == {"pendiente", "entregada", "perdida", "ignorada", "malinterpretada"}

    def test_is_str_enum(self):
        assert DeliveryState.pendiente == "pendiente"


# ═══════════════════════════════════════════════════════════════════════
# ClueForm
# ═══════════════════════════════════════════════════════════════════════


class TestClueForm:
    def test_eight_values(self):
        states = list(ClueForm)
        assert len(states) == 8
        values = {s.value for s in states}
        assert values == {
            "documento", "testimonio", "objeto", "rastro",
            "rumor", "vision", "sueño", "descubrimiento",
        }


# ═══════════════════════════════════════════════════════════════════════
# Secreto
# ═══════════════════════════════════════════════════════════════════════


class TestSecreto:
    def test_minimal_creation(self):
        s = Secreto(content="El secreto")
        assert s.content == "El secreto"
        assert s.id.startswith("sec_")
        assert s.revelation_state == RevelationState.oculto
        assert s.importance == 3
        assert s.entity_id is None
        assert s.created_at != ""

    def test_full_fields(self):
        s = Secreto(
            id="sec_abc",
            content="El Anillo es el Arma",
            entity_id="ent_secreto_1",
            affected_entity_ids=["ent_frodo", "ent_gandalf"],
            revelation_state=RevelationState.rumoreado,
            who_knows_entity_ids=["ent_gandalf"],
            who_suspects_entity_ids=["ent_saruman"],
            who_ignores_entity_ids=["ent_frodo"],
            who_hides_entity_ids=["ent_sauron"],
            associated_clue_ids=["clu_1", "clu_2"],
            revelation_consequences=["Guerra"],
            concealment_consequences=["Sauron gana"],
            planned_revelation_session_ids=["ses_1"],
            actual_revelation_session_id="ses_2",
            revelation_form="visión",
            importance=5,
            canon_state="canonico",
            visibility_state="secreto_en_mundo",
            metadata={"layer": "main"},
        )
        assert s.id == "sec_abc"
        assert s.content == "El Anillo es el Arma"
        assert s.entity_id == "ent_secreto_1"
        assert s.revelation_state == RevelationState.rumoreado
        assert len(s.who_knows_entity_ids) == 1
        assert s.importance == 5

    def test_field_count_is_21(self):
        s = Secreto(content="test")
        d = s.to_dict()
        assert len(d) == 21, f"Expected 21 fields, got {len(d)}: {sorted(d.keys())}"

    def test_entity_id_none_valid(self):
        s = Secreto(content="test", entity_id=None)
        assert s.entity_id is None
        d = s.to_dict()
        assert d["entity_id"] is None

    def test_entity_id_set(self):
        s = Secreto(content="test", entity_id="ent_sec_42")
        assert s.entity_id == "ent_sec_42"

    def test_importance_clamped(self):
        s = Secreto(content="test", importance=10)
        assert s.importance == 5
        s2 = Secreto(content="test", importance=-1)
        assert s2.importance == 1

    def test_to_dict(self):
        s = Secreto(content="Secreto", importance=4, entity_id="ent_sec_1")
        d = s.to_dict()
        assert d["content"] == "Secreto"
        assert d["importance"] == 4
        assert d["entity_id"] == "ent_sec_1"
        assert d["revelation_state"] == "oculto"

    def test_from_dict(self):
        data = {
            "id": "sec_xyz",
            "content": "Loaded secret",
            "entity_id": "ent_s",
            "revelation_state": "revelado",
            "importance": 2,
            "who_knows_entity_ids": ["e1"],
            "associated_clue_ids": ["clu_a"],
        }
        s = Secreto.from_dict(data)
        assert s.id == "sec_xyz"
        assert s.content == "Loaded secret"
        assert s.entity_id == "ent_s"
        assert s.revelation_state == RevelationState.revelado
        assert s.importance == 2

    def test_from_dict_empty(self):
        s = Secreto.from_dict({})
        assert s.content == ""
        assert s.id.startswith("sec_")

    def test_from_dict_entity_id_absent(self):
        s = Secreto.from_dict({"content": "test"})
        assert s.entity_id is None

    def test_roundtrip(self):
        s = Secreto(
            content="Roundtrip",
            entity_id="ent_sec_99",
            affected_entity_ids=["e1", "e2"],
            revelation_state=RevelationState.parcialmente_revelado,
            who_knows_entity_ids=["e3"],
            who_suspects_entity_ids=["e4"],
            who_ignores_entity_ids=["e5"],
            who_hides_entity_ids=["e6"],
            associated_clue_ids=["clu_1"],
            revelation_consequences=["c1"],
            concealment_consequences=["c2"],
            planned_revelation_session_ids=["s1"],
            actual_revelation_session_id="s2",
            revelation_form="sueño",
            importance=4,
            canon_state="canonico",
            visibility_state="visible_usuario",
            metadata={"k": "v"},
        )
        d = s.to_dict()
        s2 = Secreto.from_dict(d)
        assert s2.id == s.id
        assert s2.content == s.content
        assert s2.entity_id == s.entity_id
        assert s2.affected_entity_ids == s.affected_entity_ids
        assert s2.revelation_state == s.revelation_state
        assert s2.who_knows_entity_ids == s.who_knows_entity_ids
        assert s2.who_suspects_entity_ids == s.who_suspects_entity_ids
        assert s2.who_ignores_entity_ids == s.who_ignores_entity_ids
        assert s2.who_hides_entity_ids == s.who_hides_entity_ids
        assert s2.associated_clue_ids == s.associated_clue_ids
        assert s2.importance == s.importance


# ═══════════════════════════════════════════════════════════════════════
# Pista
# ═══════════════════════════════════════════════════════════════════════


class TestPista:
    def test_minimal_creation(self):
        c = Pista(content="Una pista")
        assert c.content == "Una pista"
        assert c.id.startswith("clu_")
        assert c.delivery_state == DeliveryState.pendiente
        assert c.clarity == 3
        assert c.redundancy == 1
        assert c.loss_risk == 3
        assert c.entity_id is None
        assert c.associated_secret_id is None

    def test_full_fields(self):
        c = Pista(
            id="clu_abc",
            content="Mapa antiguo",
            entity_id="ent_pista_1",
            associated_secret_id="sec_1",
            source_entity_id="ent_rivendel",
            location_entity_id="ent_biblioteca",
            associated_npc_entity_id="ent_elrond",
            delivery_form=ClueForm.documento,
            delivery_state=DeliveryState.entregada,
            clarity=4,
            redundancy=2,
            loss_risk=1,
            planned_session_ids=["ses_3"],
            delivered_session_id="ses_4",
            character_ids_who_know=["ent_gandalf"],
            probable_interpretation="El Anillo está en Mordor",
            possible_misinterpretations=["Está en las Montañas"],
        )
        assert c.id == "clu_abc"
        assert c.entity_id == "ent_pista_1"
        assert c.associated_secret_id == "sec_1"
        assert c.delivery_state == DeliveryState.entregada
        assert c.clarity == 4

    def test_field_count_is_20(self):
        c = Pista(content="test")
        d = c.to_dict()
        assert len(d) == 20, f"Expected 20 fields, got {len(d)}: {sorted(d.keys())}"

    def test_without_secret_valid(self):
        c = Pista(content="Pista sin secreto")
        assert c.associated_secret_id is None

    def test_clarity_clamped(self):
        c = Pista(content="test", clarity=10)
        assert c.clarity == 5
        c2 = Pista(content="test", clarity=0)
        assert c2.clarity == 1

    def test_to_dict(self):
        c = Pista(content="Pista", clarity=5, redundancy=3, entity_id="ent_p")
        d = c.to_dict()
        assert d["content"] == "Pista"
        assert d["clarity"] == 5
        assert d["redundancy"] == 3
        assert d["entity_id"] == "ent_p"

    def test_from_dict(self):
        data = {
            "id": "clu_xyz",
            "content": "Loaded clue",
            "entity_id": "ent_c",
            "associated_secret_id": "sec_x",
            "delivery_form": "testimonio",
            "delivery_state": "entregada",
            "clarity": 2,
            "redundancy": 3,
            "loss_risk": 4,
        }
        c = Pista.from_dict(data)
        assert c.id == "clu_xyz"
        assert c.entity_id == "ent_c"
        assert c.associated_secret_id == "sec_x"
        assert c.delivery_form == ClueForm.testimonio
        assert c.delivery_state == DeliveryState.entregada
        assert c.clarity == 2

    def test_from_dict_empty(self):
        c = Pista.from_dict({})
        assert c.content == ""
        assert c.id.startswith("clu_")

    def test_roundtrip(self):
        c = Pista(
            content="Roundtrip",
            entity_id="ent_p_99",
            associated_secret_id="sec_r",
            source_entity_id="ent_src",
            location_entity_id="ent_loc",
            associated_npc_entity_id="ent_npc",
            delivery_form=ClueForm.vision,
            delivery_state=DeliveryState.ignorada,
            clarity=5,
            redundancy=3,
            loss_risk=2,
            planned_session_ids=["s1"],
            delivered_session_id="s2",
            character_ids_who_know=["c1"],
            probable_interpretation="pi",
            possible_misinterpretations=["mi1"],
            metadata={"k": "v"},
        )
        d = c.to_dict()
        c2 = Pista.from_dict(d)
        assert c2.id == c.id
        assert c2.content == c.content
        assert c2.entity_id == c.entity_id
        assert c2.associated_secret_id == c.associated_secret_id
        assert c2.source_entity_id == c.source_entity_id
        assert c2.delivery_form == c.delivery_form
        assert c2.delivery_state == c.delivery_state
        assert c2.clarity == c.clarity
        assert c2.redundancy == c.redundancy
        assert c2.loss_risk == c.loss_risk


# ═══════════════════════════════════════════════════════════════════════
# No external dependencies
# ═══════════════════════════════════════════════════════════════════════


class TestNoDependencies:
    def test_models_are_stdlib_only(self):
        import packages.domain.secrets_models as m
        allowed_mods = {
            "dataclasses", "datetime", "enum", "typing", "uuid", "builtins",
            "__future__",
        }
        for name in dir(m):
            if name.startswith("_"):
                continue
            obj = getattr(m, name)
            if hasattr(obj, "__module__"):
                mod = obj.__module__
                if not mod.startswith("packages.domain.secrets_models"):
                    assert mod in allowed_mods, f"Unexpected import: {name} from {mod}"
