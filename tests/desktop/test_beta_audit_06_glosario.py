"""BETA-AUDIT-06: el vocabulario del jardín tiene que estar explicado EN la app.

Las definiciones buenas de arraigo / nutrida / iluminada existían desde el principio,
pero sólo dentro del prompt que se le manda al modelo (``command_prompts.py``, tarea
``water_entity``). El modelo tenía el glosario y el usuario no: en la interfaz, el
tooltip de cada métrica se limitaba a repetir su etiqueta («Arraigo» → «Arraigo»).

Estos tests fijan que el catálogo existe y que llega a las superficies donde el
usuario se topa con esas palabras por primera vez.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.field_help import (  # noqa: E402
    FIELD_HELP,
    glossary,
    metric_tooltip,
)

# El idioma propio de Dendro: lo que un usuario nuevo NO puede deducir.
VOCABULARIO = (
    "anillo",
    "rama",
    "hoja",
    "hito",
    "era",
    "capa",
    "lapso_vida",
    "canon",
    "fantasma",
    "semilla",
    "regar",
    "arraigo",
    "nutrida",
    "iluminada",
    "relevancia",
    "potencia_causal",
    "falta_regar",
    "secada",
    "memoria",
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_field_help_cubre_el_vocabulario_del_jardin():
    faltan = [t for t in VOCABULARIO if not glossary(t).strip()]
    assert not faltan, f"sin definición en FIELD_HELP: {faltan}"
    cortas = [t for t in VOCABULARIO if len(glossary(t)) <= 30]
    assert not cortas, (
        f"definiciones demasiado escuetas para explicar nada: {cortas}"
    )


def test_definicion_no_es_la_propia_palabra():
    for termino in VOCABULARIO:
        definicion = glossary(termino).strip().lower()
        assert definicion != termino.replace("_", " "), (
            f"la definición de «{termino}» se limita a repetir la palabra"
        )


def test_las_claves_del_glosario_no_pisan_la_configuracion_creativa():
    """El prefijo `glosario_` existe para no colisionar con los 30 campos de PA04."""
    creativos = {k for k in FIELD_HELP if not k.startswith("glosario_")}
    del_jardin = {k[len("glosario_") :] for k in FIELD_HELP if k.startswith("glosario_")}
    assert not (creativos & del_jardin), (
        "una clave del jardín pisa un campo de configuración creativa"
    )


def test_metric_tooltip_define_en_vez_de_repetir():
    for clave, etiqueta in (
        ("arraigo", "Arraigo"),
        ("nutrida", "Nutrida"),
        ("iluminada", "Iluminada"),
        ("relevancia", "Relevancia"),
    ):
        tooltip = metric_tooltip(clave, etiqueta)
        assert tooltip != etiqueta, f"«{etiqueta}» sigue explicándose con su propio nombre"
        assert glossary(clave) in tooltip


def test_franja_de_cultivo_explica_las_metricas(qapp):
    """La franja del pie de la tarjeta es donde más gente ve las 4 métricas."""
    from PySide6.QtWidgets import QLabel

    from hosts.DesktopHostPySide.widgets.foco.cultivation_strip import CultivationStrip

    franja = CultivationStrip()
    try:
        tooltips = " ".join(
            w.toolTip() for w in franja.findChildren(QLabel) if w.toolTip()
        )
        assert glossary("arraigo") in tooltips, (
            "la franja de cultivo no explica «arraigo» en ningún tooltip"
        )
        assert glossary("iluminada") in tooltips
    finally:
        franja.deleteLater()
        qapp.processEvents()


def test_chips_de_ficha_toman_el_texto_del_catalogo(qapp):
    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
    from packages.application.project_service import ProjectService
    from packages.domain.result import Ok

    servicio = ProjectService()
    assert isinstance(servicio.create("Glosario"), Ok)
    ctx = AppContext()
    ctx.project_controller = type("Stub", (), {"ps": servicio})()
    controlador = EntityController(servicio)
    hoja = controlador.create({"name": "Hoja", "entity_type": "nota"}).value

    panel = NodeDetailPanel(ctx, controlador, hoja.id, variant="foco")
    try:
        assert glossary("anillo") in panel.layer_combo.toolTip()
        assert glossary("relevancia") in panel.importance_combo.toolTip()
        assert glossary("rama") in panel.type_combo.toolTip()
    finally:
        panel.deleteLater()
        qapp.processEvents()
