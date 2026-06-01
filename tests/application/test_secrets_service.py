"""Tests for SecretsService (B21-T03)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from packages.application.secrets_service import SecretsService, KnowledgeRelationType
from packages.application.project_service import ProjectService
from packages.domain.project import Project
from packages.domain.entity import NarrativeEntity, EntityType, CanonState, VisibilityState
from packages.domain.secrets_models import (
    Secreto, Pista, RevelationState, DeliveryState, ClueForm,
)
from packages.domain.result import Ok, Error


def _make_project_with_entities() -> tuple[Project, SecretsService]:
    project = Project(name="Test")

    for name, etype in [
        ("Gandalf", EntityType.PERSONAJE), ("Saruman", EntityType.PERSONAJE),
        ("Rivendel", EntityType.LOCALIZACION),
    ]:
        project.entities.append(NarrativeEntity(
            name=name, entity_type=etype,
            canon_state=CanonState.CANONICO, visibility_state=VisibilityState.VISIBLE_USUARIO,
        ))

    ps = MagicMock(spec=ProjectService)
    ps.active_project = project
    ps.save.return_value = Ok(None)

    es = MagicMock()
    def get_by_id(eid):
        for e in project.entities:
            if e.id == eid: return Ok(e)
        return Error(f"Entity '{eid}' not found")
    es.get_by_id = get_by_id

    svc = SecretsService(project_service=ps, entity_service=es)
    return project, svc


# ── Secrets ─────────────────────────────────────────────────


class TestSecretsCRUD:
    def test_create_secret(self):
        _, svc = _make_project_with_entities()
        r = svc.create_secret({"content": "El Anillo es el Arma", "importance": 5})
        assert isinstance(r, Ok)
        assert r.value.content == "El Anillo es el Arma"
        assert r.value.importance == 5
        assert r.value.id.startswith("sec_")

    def test_create_no_content(self):
        _, svc = _make_project_with_entities()
        assert isinstance(svc.create_secret({"content": ""}), Error)

    def test_importance_out_of_range(self):
        _, svc = _make_project_with_entities()
        assert isinstance(svc.create_secret({"content": "x", "importance": 0}), Error)
        assert isinstance(svc.create_secret({"content": "x", "importance": 7}), Error)

    def test_list_by_state(self):
        _, svc = _make_project_with_entities()
        svc.create_secret({"content": "s1"})
        s2 = svc.create_secret({"content": "s2"}).value
        svc.reveal_secret(s2.id, "revelado")
        assert len(svc.list_secrets(state="oculto")) == 1
        assert len(svc.list_secrets(state="revelado")) == 1

    def test_get_hidden(self):
        _, svc = _make_project_with_entities()
        svc.create_secret({"content": "s1"})
        s2 = svc.create_secret({"content": "s2"}).value
        svc.reveal_secret(s2.id, "revelado")
        assert len(svc.get_hidden_secrets()) == 1


# ── Revelation ─────────────────────────────────────────────────


class TestRevelation:
    def test_valid_transition_oculto_to_rumoreado(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        r = svc.reveal_secret(s.id, "rumoreado")
        assert isinstance(r, Ok)
        assert r.value.revelation_state == RevelationState.rumoreado

    def test_oculto_to_parcial(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        r = svc.reveal_secret(s.id, "parcialmente_revelado")
        assert isinstance(r, Ok)

    def test_oculto_to_malinterpretado(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        r = svc.reveal_secret(s.id, "malinterpretado")
        assert isinstance(r, Ok)

    def test_oculto_to_revelado(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        r = svc.reveal_secret(s.id, "revelado")
        assert isinstance(r, Ok)

    def test_rumoreado_to_parcial(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        svc.reveal_secret(s.id, "rumoreado")
        r = svc.reveal_secret(s.id, "parcialmente_revelado")
        assert isinstance(r, Ok)

    def test_rumoreado_to_revelado(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        svc.reveal_secret(s.id, "rumoreado")
        r = svc.reveal_secret(s.id, "revelado")
        assert isinstance(r, Ok)

    def test_malinterpretado_to_parcial(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        svc.reveal_secret(s.id, "malinterpretado")
        r = svc.reveal_secret(s.id, "parcialmente_revelado")
        assert isinstance(r, Ok)

    def test_parcial_to_revelado(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        svc.reveal_secret(s.id, "parcialmente_revelado")
        r = svc.reveal_secret(s.id, "revelado")
        assert isinstance(r, Ok)

    def test_revelado_to_oculto_errors(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        svc.reveal_secret(s.id, "revelado")
        r = svc.reveal_secret(s.id, "oculto")
        assert isinstance(r, Error)

    def test_revelado_to_oculto_force(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        svc.reveal_secret(s.id, "revelado")
        r = svc.reveal_secret(s.id, "oculto", force=True)
        assert isinstance(r, Ok)
        assert r.value.revelation_state == RevelationState.oculto

    def test_reveal_with_session_and_form(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        r = svc.reveal_secret(s.id, "revelado", session_id="ses_1", form="sueño")
        assert r.value.actual_revelation_session_id == "ses_1"
        assert r.value.revelation_form == "sueño"


# ── Clues ─────────────────────────────────────────────────


class TestCluesCRUD:
    def test_create_clue(self):
        _, svc = _make_project_with_entities()
        r = svc.create_clue({"content": "Mapa antiguo", "clarity": 4})
        assert isinstance(r, Ok)
        assert r.value.clarity == 4

    def test_create_clue_out_of_range(self):
        _, svc = _make_project_with_entities()
        assert isinstance(svc.create_clue({"content": "x", "clarity": 0}), Error)
        assert isinstance(svc.create_clue({"content": "x", "loss_risk": 10}), Error)

    def test_create_clue_with_secret(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "secret"}).value
        r = svc.create_clue({"content": "clue", "associated_secret_id": s.id})
        assert isinstance(r, Ok)

    def test_create_clue_with_invalid_secret(self):
        _, svc = _make_project_with_entities()
        r = svc.create_clue({"content": "clue", "associated_secret_id": "sec_fake"})
        assert isinstance(r, Error)


class TestClueDelivery:
    def test_deliver_entregada(self):
        _, svc = _make_project_with_entities()
        c = svc.create_clue({"content": "test"}).value
        r = svc.deliver_clue(c.id, state="entregada")
        assert r.value.delivery_state == DeliveryState.entregada

    def test_deliver_perdida(self):
        _, svc = _make_project_with_entities()
        c = svc.create_clue({"content": "test"}).value
        r = svc.deliver_clue(c.id, state="perdida")
        assert r.value.delivery_state == DeliveryState.perdida

    def test_deliver_ignorada(self):
        _, svc = _make_project_with_entities()
        c = svc.create_clue({"content": "test"}).value
        r = svc.deliver_clue(c.id, state="ignorada")
        assert r.value.delivery_state == DeliveryState.ignorada

    def test_deliver_malinterpretada(self):
        _, svc = _make_project_with_entities()
        c = svc.create_clue({"content": "test"}).value
        r = svc.deliver_clue(c.id, state="malinterpretada")
        assert r.value.delivery_state == DeliveryState.malinterpretada

    def test_deliver_with_characters(self):
        _, svc = _make_project_with_entities()
        c = svc.create_clue({"content": "test"}).value
        r = svc.deliver_clue(c.id, character_ids=["ent_g"])
        assert "ent_g" in r.value.character_ids_who_know


class TestClueLinking:
    def test_link_to_secret(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "s"}).value
        c = svc.create_clue({"content": "c"}).value
        r = svc.link_clue_to_secret(c.id, s.id)
        assert isinstance(r, Ok)
        assert r.value.associated_secret_id == s.id

    def test_link_to_nonexistent_secret(self):
        _, svc = _make_project_with_entities()
        c = svc.create_clue({"content": "c"}).value
        assert isinstance(svc.link_clue_to_secret(c.id, "sec_fake"), Error)

    def test_unlink(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "s"}).value
        c = svc.create_clue({"content": "c", "associated_secret_id": s.id}).value
        r = svc.unlink_clue_from_secret(c.id)
        assert r.value.associated_secret_id is None


# ── Detection ─────────────────────────────────────────────────


class TestDetection:
    def test_find_secrets_without_clues(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "secret no clues"}).value
        assert len(svc.find_secrets_without_clues()) == 1

    def test_find_clues_without_secret(self):
        _, svc = _make_project_with_entities()
        svc.create_clue({"content": "orphan clue"})
        assert len(svc.find_clues_without_secret()) == 1

    def test_run_secret_validation_idempotent(self):
        _, svc = _make_project_with_entities()
        svc.create_secret({"content": "no clues"})
        issues1 = svc.run_secret_validation()
        assert len(issues1) >= 1
        issues2 = svc.run_secret_validation()
        assert len(issues2) == 0  # idempotent — no duplicates

    def test_find_revealed_without_consequences(self):
        _, svc = _make_project_with_entities()
        s = svc.create_secret({"content": "test"}).value
        svc.reveal_secret(s.id, "revelado")
        assert len(svc.find_revealed_without_consequences()) == 1


# ── Knowledge ─────────────────────────────────────────────────


class TestKnowledge:
    def test_knowledge_for_character_empty(self):
        _, svc = _make_project_with_entities()
        k = svc.get_knowledge_for_character("ent_nobody")
        assert k["entity_id"] == "ent_nobody"
        assert k["secrets_known"] == []

    def test_knowledge_from_manual_list(self):
        _, svc = _make_project_with_entities()
        gandalf = next(e for e in svc._active_project().entities if e.name == "Gandalf")
        s = svc.create_secret({"content": "secret", "who_knows_entity_ids": [gandalf.id]}).value
        k = svc.get_knowledge_for_character(gandalf.id)
        assert len(k["secrets_known"]) == 1
