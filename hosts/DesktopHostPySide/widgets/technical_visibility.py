"""Technical visibility helpers for B31 advanced mode.

UI-only helpers. They do not access persistence or mutate domain state.
"""
from __future__ import annotations

from PySide6.QtWidgets import QTableWidget


TECHNICAL_FIELD_NAMES = {
    "id",
    "source_id",
    "target_id",
    "entity_id",
    "campaign_id",
    "session_id",
    "faction_id",
    "front_id",
    "clock_id",
    "location_id",
    "npc_ids",
    "domain_ids",
    "layer_ids",
    "metadata",
    "custom_metadata",
    "custom_type_id",
    "custom_fields",
    "source",
    "source ids",
    "source id",
    "payload",
    "json",
}


def is_technical_field(name: str, label: str | None = None) -> bool:
    """Return True when a field belongs only in advanced/debug UI."""
    text = f"{name} {label or ''}".lower().replace("-", "_")
    return any(token in text for token in TECHNICAL_FIELD_NAMES)


def set_columns_visible(table: QTableWidget, columns: list[int], visible: bool) -> None:
    """Show/hide a group of columns defensively."""
    for column in columns:
        if 0 <= column < table.columnCount():
            table.setColumnHidden(column, not visible)


def safe_ref(name: str, kind: str | None = None) -> str:
    """Human-readable reference for normal mode; never includes raw IDs."""
    name = (name or "Sin nombre").strip() or "Sin nombre"
    if kind:
        return f"{name} · {kind}"
    return name
