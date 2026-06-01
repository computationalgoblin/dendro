"""Tests for ExportService (B26-T03)."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from packages.application.export_service import ExportService
from packages.application.project_service import ProjectService
from packages.domain.project import Project
from packages.domain.entity import NarrativeEntity, EntityType, CanonState, VisibilityState
from packages.domain.secrets_models import Secreto
from packages.domain.result import Ok, Error

def _mk():
    p = Project(name="Test")
    p.entities.append(NarrativeEntity(name="Pub", entity_type=EntityType.LOCALIZACION, canon_state=CanonState.CANONICO, visibility_state=VisibilityState.PUBLICO_MUNDO))
    p.entities.append(NarrativeEntity(name="Secret", entity_type=EntityType.SECRETO, canon_state=CanonState.CANONICO, visibility_state=VisibilityState.PRIVADO_AUTOR))
    p.secrets.append(Secreto(content="Hidden"))
    ps = MagicMock(spec=ProjectService); ps.active_project = p
    return p, ExportService(project_service=ps)

class TestExportService:
    def test_public_summary_filters_private(self):
        _, svc = _mk(); r = svc.export_public_summary("public")
        assert isinstance(r, Ok); assert "Pub" in r.value; assert "Secret" not in r.value
    def test_gm_summary_includes_all(self):
        _, svc = _mk(); r = svc.export_public_summary("gm")
        assert isinstance(r, Ok); assert "Pub" in r.value; assert "Secrets: 1" in r.value
    def test_player_summary_filters_private_entities(self):
        _, svc = _mk(); r = svc.export_public_summary("player")
        assert isinstance(r, Ok); assert "Secret" not in r.value
    def test_entity_profile_public_blocked(self):
        _, svc = _mk()
        r = svc.export_entity_profile(p.entities[1].id, "public")
        assert isinstance(r, Error)
    def test_export_all_gm(self):
        _, svc = _mk(); r = svc.export_all("gm")
        assert isinstance(r, Ok); assert r.value["total_entities"] == 2; assert r.value["total_secrets"] == 1

p = None
try:
    _, svc = _mk(); p = svc._proj()
except: pass
