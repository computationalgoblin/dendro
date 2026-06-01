"""Tests for Bloque 21 schema v15 — secrets and clues collections (B21-T02)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v14_to_v15,
    _validate_secrets,
    _validate_clues,
)
from packages.persistence.store import load_project_data, save_project_data
from packages.domain.project import Project
from packages.domain.result import Ok, Error
from packages.domain.secrets_models import Secreto, Pista


class TestSchemaV15:
    def test_current_version_is_15(self):
        assert CURRENT_SCHEMA_VERSION == 18

    def test_migration_adds_empty_lists(self):
        data = {"schema_version": 14, "campaigns": [], "writing_units": []}
        result = _apply_migration_v14_to_v15(data)
        assert result["schema_version"] == 15
        assert result["secrets"] == []
        assert result["clues"] == []

    def test_migration_preserves_campaigns(self):
        data = {"schema_version": 14, "campaigns": [{"id": "c1", "name": "Test"}], "writing_units": []}
        result = _apply_migration_v14_to_v15(data)
        assert len(result["campaigns"]) == 1


class TestValidateSecrets:
    def test_empty_valid(self): assert _validate_secrets([]) == []
    def test_valid_secret(self):
        assert _validate_secrets([{"id": "s1", "content": "test"}]) == []
    def test_no_content_error(self):
        assert len(_validate_secrets([{"id": "s1"}])) > 0
    def test_empty_content_error(self):
        assert len(_validate_secrets([{"id": "s1", "content": ""}])) > 0
    def test_duplicate_ids(self):
        assert len(_validate_secrets([{"id": "s1", "content": "a"}, {"id": "s1", "content": "b"}])) > 0
    def test_entity_id_empty_error(self):
        assert len(_validate_secrets([{"id": "s1", "content": "x", "entity_id": ""}])) > 0
    def test_importance_out_of_range(self):
        assert len(_validate_secrets([{"id": "s1", "content": "x", "importance": 0}])) > 0
        assert len(_validate_secrets([{"id": "s1", "content": "x", "importance": 7}])) > 0


class TestValidateClues:
    def test_empty_valid(self): assert _validate_clues([]) == []
    def test_valid_clue(self):
        assert _validate_clues([{"id": "c1", "content": "test"}]) == []
    def test_associated_secret_cross_ref(self):
        errors = _validate_clues(
            [{"id": "c1", "content": "test", "associated_secret_id": "sec_x"}],
            all_secret_ids={"sec_y"}
        )
        assert len(errors) > 0
    def test_clarity_out_of_range(self):
        assert len(_validate_clues([{"id": "c1", "content": "x", "clarity": 0}])) > 0


class TestSecretsPersistence:
    def test_save_load_roundtrip(self, tmp_path: Path):
        path = tmp_path / "secrets_project.json"
        p = Project(name="Test")
        p.secrets.append(Secreto(content="El secreto", importance=5))
        p.clues.append(Pista(content="La pista", clarity=3))
        save_result = save_project_data(p.to_dict(), path)
        assert isinstance(save_result, Ok)

        load_result = load_project_data(path)
        assert isinstance(load_result, Ok)
        data = load_result.value
        assert data["schema_version"] == 18
        assert len(data["secrets"]) == 1
        assert data["secrets"][0]["content"] == "El secreto"
        assert data["secrets"][0]["importance"] == 5
        assert len(data["clues"]) == 1
        assert data["clues"][0]["clarity"] == 3

    def test_v14_migrates_to_v15(self, tmp_path: Path):
        path = tmp_path / "v14_project.json"
        v14 = {"schema_version": 14, "id": "p", "name": "Old",
               "created_at": "2026-01-01T00:00:00+00:00",
               "updated_at": "2026-01-01T00:00:00+00:00",
               "writing_units": [], "campaigns": []}
        path.write_text(json.dumps(v14))
        result = load_project_data(path)
        assert isinstance(result, Ok)
        assert result.value.get("secrets") == []
        assert result.value.get("clues") == []
