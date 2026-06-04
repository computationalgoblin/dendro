"""Tests for B32 TreeMeta semantic metadata helper."""
from __future__ import annotations

from packages.application.tree_meta import (
    KEY_COLOR,
    KEY_ICON,
    KEY_INTERNAL_RULES,
    KEY_NARRATIVE_ROLE,
    KEY_OPEN_QUESTIONS,
    KEY_TREE_TYPE,
    NARRATIVE_ROLES,
    TREE_TYPES,
    TreeMeta,
)


def test_tree_meta_defaults_for_existing_entities_without_metadata():
    meta = TreeMeta.from_metadata({})

    assert meta.tree_type == ""
    assert meta.narrative_role == ""
    assert meta.internal_rules == []
    assert meta.open_questions == []
    assert meta.color == ""
    assert meta.icon == ""
    assert meta.validate() == []


def test_tree_meta_reads_existing_custom_metadata():
    metadata = {
        KEY_TREE_TYPE: "faccion",
        KEY_NARRATIVE_ROLE: "central",
        KEY_INTERNAL_RULES: ["Solo habla el consejo"],
        KEY_OPEN_QUESTIONS: ["¿Quién traicionó el pacto?"],
        KEY_COLOR: "#AA5500",
        KEY_ICON: "♜",
        "unrelated": "preserved",
    }

    meta = TreeMeta.from_metadata(metadata)

    assert meta.tree_type == "faccion"
    assert meta.narrative_role == "central"
    assert meta.internal_rules == ["Solo habla el consejo"]
    assert meta.open_questions == ["¿Quién traicionó el pacto?"]
    assert meta.color == "#AA5500"
    assert meta.icon == "♜"


def test_tree_meta_merge_preserves_non_tree_metadata():
    original = {"unrelated": "preserved", KEY_TREE_TYPE: "cultura"}
    meta = TreeMeta(
        tree_type="reino",
        narrative_role="activo_presente",
        internal_rules=["La corona decide los juramentos"],
        open_questions=["¿Quién hereda si cae la reina?"],
        color="#336699",
        icon="◇",
    )

    merged = meta.merge_into(original)

    assert merged["unrelated"] == "preserved"
    assert merged[KEY_TREE_TYPE] == "reino"
    assert merged[KEY_NARRATIVE_ROLE] == "activo_presente"
    assert merged[KEY_INTERNAL_RULES] == ["La corona decide los juramentos"]
    assert merged[KEY_OPEN_QUESTIONS] == ["¿Quién hereda si cae la reina?"]
    assert merged[KEY_COLOR] == "#336699"
    assert merged[KEY_ICON] == "◇"
    assert original[KEY_TREE_TYPE] == "cultura"


def test_tree_meta_apply_to_updates_only_known_fields():
    original = {"unrelated": "preserved"}

    merged = TreeMeta.apply_to(
        original,
        tree_type="familia",
        narrative_role="secreto",
        ignored_field="ignored",
    )

    assert merged["unrelated"] == "preserved"
    assert merged[KEY_TREE_TYPE] == "familia"
    assert merged[KEY_NARRATIVE_ROLE] == "secreto"
    assert "ignored_field" not in merged


def test_tree_meta_validation_allowed_and_rejected_values():
    assert "faccion" in TREE_TYPES
    assert "central" in NARRATIVE_ROLES
    assert TreeMeta(tree_type="faccion", narrative_role="central").validate() == []

    issues = TreeMeta(tree_type="carpeta", narrative_role="decorativo").validate()

    assert "tree_type 'carpeta' not in allowed values" in issues
    assert "narrative_role 'decorativo' not in allowed values" in issues
