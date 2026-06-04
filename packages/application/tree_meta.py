"""TreeMeta — semantic metadata helper for container (tree) entities.

B32-T01: reads/writes tree-specific keys from NarrativeEntity.custom_metadata
without touching the domain model or schema.

Key convention: ``tree_*`` prefix to avoid collisions with other metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Canonical key names ──────────────────────────────────────────────

KEY_TREE_TYPE = "tree_type"
KEY_NARRATIVE_ROLE = "tree_narrative_role"
KEY_INTERNAL_RULES = "tree_internal_rules"
KEY_OPEN_QUESTIONS = "tree_open_questions"
KEY_COLOR = "tree_color"
KEY_ICON = "tree_icon"


# ── Allowed values ───────────────────────────────────────────────────

TREE_TYPES: list[str] = [
    "faccion",
    "organizacion",
    "cultura",
    "reino",
    "familia",
    "religion",
    "sistema",
    "capa",
    "trama",
    "institucion",
    "conflicto",
    "estructura_narrativa",
    "personalizado",
]

NARRATIVE_ROLES: list[str] = [
    "central",
    "secundario",
    "ambiental",
    "secreto",
    "historico",
    "activo_presente",
    "antagonista_estructural",
    "soporte_narrativo",
]


# ── Defaults ─────────────────────────────────────────────────────────

DEFAULT_TREE_TYPE = ""
DEFAULT_NARRATIVE_ROLE = ""
DEFAULT_INTERNAL_RULES: list[str] = []
DEFAULT_OPEN_QUESTIONS: list[str] = []
DEFAULT_COLOR = ""
DEFAULT_ICON = ""


# ── Helper class ─────────────────────────────────────────────────────

@dataclass
class TreeMeta:
    """Typed accessor for tree-specific custom_metadata keys.

    Usage::

        meta = TreeMeta.from_metadata(entity.custom_metadata)
        print(meta.tree_type)
        meta.tree_type = "faccion"
        meta.internal_rules.append("Nadie abandona vivo.")
        entity.custom_metadata = meta.to_metadata()
    """

    tree_type: str = DEFAULT_TREE_TYPE
    narrative_role: str = DEFAULT_NARRATIVE_ROLE
    internal_rules: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    color: str = DEFAULT_COLOR
    icon: str = DEFAULT_ICON

    # ── Read from entity metadata ────────────────────────────────

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> TreeMeta:
        """Build TreeMeta from an entity's ``custom_metadata`` dict."""
        return cls(
            tree_type=str(metadata.get(KEY_TREE_TYPE, DEFAULT_TREE_TYPE)),
            narrative_role=str(metadata.get(KEY_NARRATIVE_ROLE, DEFAULT_NARRATIVE_ROLE)),
            internal_rules=list(metadata.get(KEY_INTERNAL_RULES, DEFAULT_INTERNAL_RULES)),
            open_questions=list(metadata.get(KEY_OPEN_QUESTIONS, DEFAULT_OPEN_QUESTIONS)),
            color=str(metadata.get(KEY_COLOR, DEFAULT_COLOR)),
            icon=str(metadata.get(KEY_ICON, DEFAULT_ICON)),
        )

    # ── Write back to entity metadata ────────────────────────────

    def to_metadata(self) -> dict[str, Any]:
        """Return a dict suitable for ``entity.custom_metadata``.

        Merges tree keys into the existing metadata, preserving
        non-tree keys untouched.
        """
        return {
            KEY_TREE_TYPE: self.tree_type,
            KEY_NARRATIVE_ROLE: self.narrative_role,
            KEY_INTERNAL_RULES: list(self.internal_rules),
            KEY_OPEN_QUESTIONS: list(self.open_questions),
            KEY_COLOR: self.color,
            KEY_ICON: self.icon,
        }

    # ── Merge into existing metadata (preserves non-tree keys) ───

    def merge_into(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Merge tree keys into *metadata*, returning a new dict."""
        result = dict(metadata)
        result.update(self.to_metadata())
        return result

    # ── Validation ───────────────────────────────────────────────

    def validate(self) -> list[str]:
        """Return a list of validation issues (empty = valid)."""
        issues: list[str] = []
        if self.tree_type and self.tree_type not in TREE_TYPES:
            issues.append(f"tree_type '{self.tree_type}' not in allowed values")
        if self.narrative_role and self.narrative_role not in NARRATIVE_ROLES:
            issues.append(f"narrative_role '{self.narrative_role}' not in allowed values")
        return issues

    # ── Convenience: apply to entity ─────────────────────────────

    @staticmethod
    def apply_to(entity_custom_metadata: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Update individual tree keys in-place and return the merged dict.

        Example::

            entity.custom_metadata = TreeMeta.apply_to(
                entity.custom_metadata, tree_type="faccion", color="#FF8800"
            )
        """
        meta = TreeMeta.from_metadata(entity_custom_metadata)
        for key, value in kwargs.items():
            if hasattr(meta, key):
                setattr(meta, key, value)
        return meta.merge_into(entity_custom_metadata)


__all__ = [
    "TreeMeta",
    "TREE_TYPES",
    "NARRATIVE_ROLES",
    "KEY_TREE_TYPE",
    "KEY_NARRATIVE_ROLE",
    "KEY_INTERNAL_RULES",
    "KEY_OPEN_QUESTIONS",
    "KEY_COLOR",
    "KEY_ICON",
]
