"""Paleta de tipos de entidad centralizada (BETA1-UX15).

Verifica que la paleta existe, que el helper resuelve colores y defaults, y que
los consumidores (graph_canvas, node_detail_panel) usan EXACTAMENTE los mismos
colores que antes (dedup sin cambio visual).
"""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets import design_system as ds


def test_paleta_es_calida_y_tiene_tipos_clave() -> None:
    pal = ds.ENTITY_KIND_PALETTE
    for kind in ("personaje", "lugar", "organizacion", "faccion", "objeto", "nota"):
        assert kind in pal
    # Valores canónicos UX05 (cálidos), no azules fríos.
    assert pal["personaje"] == "#C07B53"
    assert pal["lugar"] == "#7E9568"


def test_helper_default() -> None:
    assert ds.entity_kind_color("personaje") == "#C07B53"
    assert ds.entity_kind_color("PERSONAJE") == "#C07B53"  # normaliza mayúsculas
    assert ds.entity_kind_color("inexistente") == ds._ENTITY_KIND_DEFAULT
    assert ds.entity_kind_color(None, default="#000000") == "#000000"


def test_consumidores_usan_la_misma_paleta() -> None:
    from hosts.DesktopHostPySide.widgets import graph_canvas, node_detail_panel

    # Misma fuente: cero divergencia entre canvas y panel de detalle.
    assert graph_canvas._NODE_COLORS is ds.ENTITY_KIND_PALETTE
    assert node_detail_panel._NODE_COLORS is ds.ENTITY_KIND_PALETTE


def test_equivalencia_de_hex_con_valores_previos() -> None:
    # Snapshot de los valores que existían antes de centralizar (anti-regresión).
    esperado = {
        "personaje": "#C07B53",
        "lugar": "#7E9568",
        "organizacion": "#B28A3C",
        "faccion": "#A65C54",
        "objeto": "#937083",
        "evento": "#C8A24C",
        "concepto": "#8E8A6A",
        "contenedor": "#A89878",
        "nota": "#9A8E72",
    }
    for kind, hexv in esperado.items():
        assert ds.ENTITY_KIND_PALETTE[kind] == hexv
