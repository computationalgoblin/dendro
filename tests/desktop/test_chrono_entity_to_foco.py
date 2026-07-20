"""BETA2-SUB-02: clic en una entidad de la cronología → Modo Foco (descripción)."""

from __future__ import annotations

from pathlib import Path


def test_chrono_entity_click_routes_to_foco():
    src = Path("hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
    # La cronología enruta la entidad al Foco (misma ruta que el doble-clic del Mapa),
    # ya NO al panel Node/Tree del drawer.
    assert "self.chrono.entityActivated.connect(self._on_map_entity_to_foco)" in src
    assert "self.chrono.entityActivated.connect(self._open_panel_for_entity)" not in src


def test_map_entity_to_foco_enters_description_mode():
    src = Path("hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
    # _on_map_entity_to_foco entra en Foco y centra la entidad (modo descripción:
    # el editor no se abre por defecto).
    body = src.split("def _on_map_entity_to_foco", 1)[1].split("def ", 1)[0]
    assert 'self.set_active_view("foco")' in body
    assert "center_entity(entity_id)" in body
