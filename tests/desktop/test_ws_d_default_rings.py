"""BETA-CIERRE WS-D: anillos por defecto opt-in en el wizard de creación.

Un proyecto nuevo arrancaba con el Mapa VACÍO (sin anillos), sin explicar dónde
va cada cosa. El wizard ahora ofrece (marcado por defecto) sembrar las 16 capas
causales predefinidas. La vía automática/no-wizard sigue vacía (BETA1-B05), así
que no rompe el contrato de «no auto-aplicar plantilla».
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from packages.domain.project import Project  # noqa: E402
from packages.domain.world_layer import (  # noqa: E402
    WorldLayer,
    default_world_layers,
    starter_world_layers,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _wizard(app):
    from hosts.DesktopHostPySide.widgets.project_wizard import ProjectWizard

    w = ProjectWizard()
    w.name_edit.setText("Mundo con anillos")
    return w


def test_checkbox_on_by_default_and_seeds_starter_rings(app):
    """BETA-AUDIT-09: siembra el set de ARRANQUE, no los 16 del mapa causal.

    Sembrar los 16 abría el Mapa de un proyecto nuevo con dieciséis anillos vacíos
    encabezados por «Metafísica y cosmología» — la casilla se añadió para no dejar
    perdido al usuario y conseguía lo contrario. Los 16 siguen siendo la referencia
    del contrato §10.3 y los usa la migración v7; sólo cambia con qué se arranca.
    """
    w = _wizard(app)
    assert w.seed_rings_check.isChecked()  # recomendado por defecto
    cfg = w.collect_config()
    assert cfg["seed_default_rings"] is True

    proj = Project()
    assert proj.world_layers == []
    w.apply_to_project(proj)

    expected = [layer.id for layer in starter_world_layers()]
    assert [layer.id for layer in proj.world_layers] == expected
    assert 3 <= len(proj.world_layers) <= 6
    # Los ids son los MISMOS que en el mapa completo: adoptar la estructura entera
    # más tarde no duplica anillos ni pierde el rango causal.
    completos = {layer.id for layer in default_world_layers()}
    assert {layer.id for layer in proj.world_layers} <= completos


def test_unchecked_leaves_map_empty(app):
    w = _wizard(app)
    w.seed_rings_check.setChecked(False)
    cfg = w.collect_config()
    assert cfg["seed_default_rings"] is False

    proj = Project()
    w.apply_to_project(proj)
    assert proj.world_layers == []  # blanco: el usuario eligió empezar sin anillos


def test_seeding_does_not_clobber_existing_rings(app):
    w = _wizard(app)  # checkbox marcado
    proj = Project()
    proj.world_layers = [WorldLayer(id="layer_user", name="Anillo propio", order=1)]
    w.apply_to_project(proj)
    # No pisa lo que ya existía (preset u otra fuente).
    assert [layer.id for layer in proj.world_layers] == ["layer_user"]
