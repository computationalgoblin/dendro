"""BETA-AUDIT-02: la visibilidad vuelve a ser editable desde la Ficha.

BETA2-UX-03 dejó el campo en pass-through («ya no editable»), y eso dejó sin uso el
borde de redacción que WS-B construyó para el cierre de beta: el README prometía que
lo marcado como privado o secreto no se comparte con la IA, pero **nada podía
marcarse**. Además §4 y §14 de PRUEBA-GUIADA.md eran inejecutables.

La cadena que fijan estos tests: elegir en el chip → guardar → el motor lo considera
reservado → no viaja a la IA.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.app_context import AppContext  # noqa: E402
from hosts.DesktopHostPySide.controllers.entity_controller import (  # noqa: E402
    EntityController,
)
from hosts.DesktopHostPySide.widgets.node_detail_panel import (  # noqa: E402
    _VISIBILITY_CHOICES,
    NodeDetailPanel,
)
from packages.application.ai_privacy import is_withheld_from_ai  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _panel(nombre="Testigo"):
    servicio = ProjectService()
    assert isinstance(servicio.create("Privacidad"), Ok)
    ctx = AppContext()
    ctx.project_controller = type("Stub", (), {"ps": servicio})()
    controlador = EntityController(servicio)
    entidad = controlador.create({"name": nombre, "entity_type": "personaje"}).value
    panel = NodeDetailPanel(ctx, controlador, entidad.id, variant="foco")
    return panel, controlador, entidad, servicio


def test_el_chip_ofrece_los_estados_reservados(qapp):
    ofrecidos = {v for v, _ in _VISIBILITY_CHOICES}
    assert "visible_usuario" in ofrecidos, "falta el estado por defecto"
    # Los cuatro que el motor trata como reservados tienen que ser alcanzables:
    # si no, ai_privacy protege datos que el usuario no puede producir.
    for reservado in (
        "privado_autor",
        "secreto_mundo",
        "preparado_no_revelado",
        "no_exportable",
    ):
        assert reservado in ofrecidos, f"no se puede marcar «{reservado}» desde la Ficha"


def test_marcar_secreta_persiste_y_la_oculta_a_la_ia(qapp):
    panel, controlador, entidad, _ = _panel()
    try:
        idx = panel.visibility_combo.findData("secreto_mundo")
        assert idx >= 0
        panel.visibility_combo.setCurrentIndex(idx)
        panel._do_save(refresh_after=False)

        guardada = controlador.get(entidad.id).value
        assert str(getattr(guardada.visibility_state, "value", guardada.visibility_state)) == (
            "secreto_mundo"
        )
        assert is_withheld_from_ai(guardada), (
            "marcada como secreta pero el borde de privacidad la seguiría enviando a la IA"
        )
    finally:
        panel.deleteLater()
        qapp.processEvents()


def test_una_entidad_normal_no_se_oculta(qapp):
    panel, controlador, entidad, _ = _panel("Publica")
    try:
        panel._do_save(refresh_after=False)
        guardada = controlador.get(entidad.id).value
        assert not is_withheld_from_ai(guardada)
    finally:
        panel.deleteLater()
        qapp.processEvents()


def test_no_degrada_un_estado_fuera_del_subconjunto(qapp):
    """Un proyecto viejo puede traer uno de los 9 estados que la Ficha no lista."""
    panel, controlador, entidad, _ = _panel("Rumor")
    try:
        assert isinstance(controlador.update(entidad.id, {"visibility_state": "rumor"}), Ok)
        panel.refresh()
        assert panel.visibility_combo.currentData() == "rumor", (
            "el combo no conservó un estado que él no ofrece"
        )
        panel._do_save(refresh_after=False)
        guardada = controlador.get(entidad.id).value
        assert str(getattr(guardada.visibility_state, "value", guardada.visibility_state)) == (
            "rumor"
        ), "guardar degradó en silencio un estado que el usuario no eligió aquí"
    finally:
        panel.deleteLater()
        qapp.processEvents()


def test_la_casilla_ocultar_secretas_esta_en_el_layout(qapp):
    """Se construía, se conectaba y se leía, pero nunca se añadía a ningún layout."""
    from hosts.DesktopHostPySide.widgets.filter_popover import FilterPopover

    servicio = ProjectService()
    assert isinstance(servicio.create("Filtros"), Ok)
    popover = FilterPopover(
        project_provider=lambda: servicio.active_project,
        on_apply=lambda _s: None,
        on_clear=lambda: None,
    )
    try:
        # Un widget que nunca se añade a un layout se queda sin geometría asignada:
        # ese era exactamente el síntoma («Ocultar secretas» construida y conectada,
        # pero invisible porque le faltaba el addRow).
        assert popover.hide_secret.parentWidget() is not None
        assert popover.hide_secret.width() > 1, (
            "«Ocultar secretas» sigue huérfana: no la coloca ningún layout"
        )
    finally:
        popover.deleteLater()
        qapp.processEvents()
