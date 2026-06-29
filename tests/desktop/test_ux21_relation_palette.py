"""Paleta de relaciones centralizada y cálida (BETA1-UX21)."""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets import design_system as ds

# Azules/púrpuras fríos que el panel de detalle usaba por error (no deben reaparecer).
_COOL_DRIFT = {"#7C9BFF", "#7EC8A5", "#D46A6A", "#C9A5FF", "#9BB4C7", "#A4AEC0"}


def test_paleta_relaciones_es_calida() -> None:
    pal = ds.RELATION_KIND_PALETTE
    assert pal["pertenece_a"] == "#B28A3C"   # oro-oliva, no azul
    assert pal["es_enemigo_de"] == "#A65C54"  # granate
    assert pal["es_aliado_de"] == "#7E9568"   # salvia
    # Ningún valor frío en toda la paleta.
    assert not (set(pal.values()) & _COOL_DRIFT)


def test_helper_relation_kind_color() -> None:
    assert ds.relation_kind_color("PERTENECE_A") == "#B28A3C"
    assert ds.relation_kind_color("inexistente") == ds._RELATION_KIND_DEFAULT


def test_consumidores_comparten_la_paleta() -> None:
    from hosts.DesktopHostPySide.widgets import graph_canvas, relation_detail_panel

    assert graph_canvas._EDGE_COLORS is ds.RELATION_KIND_PALETTE
    assert relation_detail_panel._EDGE_COLORS is ds.RELATION_KIND_PALETTE


def test_detalle_de_relacion_ya_no_es_frio() -> None:
    from hosts.DesktopHostPySide.widgets import relation_detail_panel

    # El color por defecto de un tipo conocido es cálido y coincide con el canvas.
    assert relation_detail_panel._default_color_for_type("pertenece_a") == "#B28A3C"
    # Tipo desconocido → neutro cálido, no gris azulado.
    assert relation_detail_panel._default_color_for_type("zzz") not in _COOL_DRIFT
