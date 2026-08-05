"""BETA-MULTIAGENT2-FIX-13 · TANDA D — etiquetas y descubribilidad (G2-19).

    «Si no pone lo que hace, para mí no existe.» — Carmen, sobre los once
    círculos de 32×32 del rail de Foco, con la papelera dentro.

    «Por probar, pulso Ctrl+Z. Y funciona. 0,19 segundos.» — Vera, que buscaba el
    deshacer «como quien busca las llaves». No había ninguna superficie donde un
    humano pudiera enterarse de que existía: la ventana no tenía ni una QAction.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── el rail de herramientas ────────────────────────────────────────────────


def _rail(qapp):
    from hosts.DesktopHostPySide.widgets.foco.foco_tool_rail import FocoToolRail

    return FocoToolRail()


def test_beta_m2fix13_las_once_herramientas_tienen_nombre_accesible(qapp):
    from hosts.DesktopHostPySide.widgets.foco.foco_tool_rail import _COLUMN

    rail = _rail(qapp)
    try:
        # La columna son once entradas: diez herramientas sueltas + el grupo.
        assert len(_COLUMN) == 11
        sin_nombre = [tid for tid, b in rail._buttons.items() if not b.accessibleName().strip()]
        assert not sin_nombre, f"botones sin nombre accesible: {sin_nombre}"
        sin_nombre_grupo = [
            gid for gid, b in rail._group_buttons.items() if not b.accessibleName().strip()
        ]
        assert not sin_nombre_grupo, sin_nombre_grupo
        # …y la descripción larga (el antiguo tooltip) sigue estando.
        assert all(b.accessibleDescription().strip() for b in rail._buttons.values())
    finally:
        rail.deleteLater()
        qapp.processEvents()


def test_beta_m2fix13_las_herramientas_llevan_rotulo_visible(qapp):
    """`accessibleName` es barato y sirve a los lectores de pantalla, pero NO lo
    ve Carmen. Decisión del ticket (pregunta abierta 1): rótulo visible por
    defecto, con interruptor para plegar a iconos."""
    rail = _rail(qapp)
    try:
        assert rail.labels_visible() is True, "el rail nace con los nombres a la vista"
        de_la_columna = [b for b in rail._buttons.values() if b in rail._column_buttons]
        assert len(de_la_columna) == 10  # las diez sueltas (las 4 fantasma van al flyout)
        sin_texto = [b.accessibleName() for b in de_la_columna if not b.text().strip()]
        assert not sin_texto, f"herramientas sin rótulo visible: {sin_texto}"
        assert rail._buttons["delete_focus"].text().strip() == "Eliminar"

        # …y se puede plegar a iconos sin perder el nombre accesible.
        rail.set_labels_visible(False)
        assert all(not b.text() for b in de_la_columna)
        assert all(b.accessibleName().strip() for b in rail._buttons.values())
        assert rail._buttons["delete_focus"].width() == 32
    finally:
        rail.deleteLater()
        qapp.processEvents()


def test_beta_m2fix13_la_herramienta_destructiva_se_distingue(qapp):
    """El de borrar tiene que distinguirse de los otros diez por algo más que su
    icono: aquí, tinta y borde de aviso."""
    rail = _rail(qapp)
    try:
        borrar = rail._buttons["delete_focus"].styleSheet()
        crear = rail._buttons["create_entity"].styleSheet()
        assert borrar != crear
        assert "#A65C54" in borrar or "#7E3B36" in borrar
        assert "#A65C54" not in crear and "#7E3B36" not in crear
    finally:
        rail.deleteLater()
        qapp.processEvents()


# ── la barra de menús ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def ventana(qapp):
    from hosts.DesktopHostPySide.main_window import MainWindow

    mw = MainWindow()
    yield mw
    # OJO: `closeEvent` abre un QMessageBox modal si hay proyecto activo (colgaría
    # la suite en offscreen). Se suelta el proyecto antes de cerrar.
    try:
        mw.controller.ps.active_project = None
    except Exception:  # noqa: BLE001
        pass
    mw.close()
    mw.deleteLater()
    qapp.processEvents()


def _acciones(ventana) -> dict[str, list[tuple[str, str]]]:
    """Menú → [(texto, atajo)].

    TRAMPA de PySide6 (costó un rato): el QMenu que devuelve `QAction.menu()`
    llega con propiedad de Python. En cuanto se suelta ese envoltorio, el QMenu
    —y con él sus QAction— se destruyen, y toda lectura posterior revienta con
    «Internal C++ object already deleted», aunque la ventana siga viva. Por eso
    se leen los menús desde la lista que la ventana conserva (`_menus`), no
    desde `menuBar().actions()[i].menu()`.
    """
    salida: dict[str, list[tuple[str, str]]] = {}
    for menu in ventana._menus:
        filas = [(a.text(), a.shortcut().toString()) for a in menu.actions()]
        salida[menu.title().replace("&", "")] = filas
    return salida


def test_beta_m2fix13_la_ventana_tiene_menus_con_acciones_nombradas(ventana):
    menus = _acciones(ventana)
    assert {"Archivo", "Edición", "Ayuda"} <= set(menus), menus.keys()

    textos_archivo = [texto for texto, _atajo in menus["Archivo"]]
    assert "Guardar" in textos_archivo
    assert any("Exportar" in t for t in textos_archivo)
    assert "Ajustes" in textos_archivo
    assert "Salir" in textos_archivo

    # El atajo se ENSEÑA en el menú (que es de lo que iba el hallazgo: existía y
    # no había forma de enterarse).
    atajo_deshacer = next(a for t, a in menus["Edición"] if "Deshacer" in t)
    assert atajo_deshacer == QKeySequence("Ctrl+Z").toString()
    atajo_rehacer = next(a for t, a in menus["Edición"] if "Rehacer" in t)
    assert atajo_rehacer == QKeySequence(QKeySequence.StandardKey.Redo).toString()
    assert ventana.action_undo.shortcut() == QKeySequence("Ctrl+Z")

    textos_ayuda = [texto for texto, _atajo in menus["Ayuda"]]
    assert "Glosario" in textos_ayuda
    assert any("Acerca de" in t for t in textos_ayuda)
    assert any("Reportar" in t for t in textos_ayuda)


def test_beta_m2fix13_deshacer_por_menu_y_por_teclado_hacen_lo_mismo(ventana):
    """La acción de menú NO reimplementa nada: llama al mismo `_undo` que ya vivía
    en `keyPressEvent`. Se comprueba disparando la acción y contando llamadas."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    llamadas: list[str] = []
    original = ventana._undo
    ventana._undo = lambda: llamadas.append("undo")  # type: ignore[method-assign]
    try:
        deshacer = next(a for a in ventana._menu_actions if a.text() == "Deshacer")
        deshacer.trigger()
        assert llamadas == ["undo"], "la acción de menú no llama a _undo"

        evento = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
        )
        ventana.keyPressEvent(evento)
        assert llamadas == ["undo", "undo"], "Ctrl+Z dejó de deshacer"
    finally:
        ventana._undo = original  # type: ignore[method-assign]


def test_beta_m2fix13_los_atajos_de_teclado_siguen_vivos(ventana):
    """Ctrl+S, Ctrl+Y y Ctrl+Shift+Z tienen que seguir funcionando exactamente
    igual: la barra de menús AÑADE una puerta, no sustituye la que había."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    vistos: list[str] = []
    originales = (ventana._save, ventana._redo)
    ventana._save = lambda: vistos.append("save")  # type: ignore[method-assign]
    ventana._redo = lambda: vistos.append("redo")  # type: ignore[method-assign]
    try:
        ctrl = Qt.KeyboardModifier.ControlModifier
        ctrl_shift = ctrl | Qt.KeyboardModifier.ShiftModifier
        for tecla, mods in (
            (Qt.Key.Key_S, ctrl),
            (Qt.Key.Key_Y, ctrl),
            (Qt.Key.Key_Z, ctrl_shift),
        ):
            ventana.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, tecla, mods))
        assert vistos == ["save", "redo", "redo"]
    finally:
        ventana._save, ventana._redo = originales  # type: ignore[method-assign]


def test_beta_m2fix13_ayuda_glosario_abre_una_superficie_visible(ventana, qapp):
    """Criterio 13: el glosario deja de ser sólo un tooltip."""
    from hosts.DesktopHostPySide.widgets.field_help import GlossaryPanel

    ventana._open_glossary()
    qapp.processEvents()
    cajon = ventana.ctx.drawer
    assert cajon is not None
    assert cajon.findChild(GlossaryPanel) is not None, "el glosario no llegó al cajón"
    cajon.close()
    qapp.processEvents()
