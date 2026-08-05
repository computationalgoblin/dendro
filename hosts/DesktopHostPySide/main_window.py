"""MainWindow — B31 immersive home + fullscreen navigation.

Architecture (BETA1-A01):
  HomeView (portal, Creación only) → fullscreen Creation
  Gallery/Session workspaces disconnected from runtime (not instantiated).
  No permanent sidebar. Return button inside each space.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.widgets.modal_overlay import ModalOverlay
from hosts.DesktopHostPySide.controllers.ai_controller import AIController
from hosts.DesktopHostPySide.controllers.candidate_controller import CandidateController
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from hosts.DesktopHostPySide.controllers.layer_controller import LayerController
from hosts.DesktopHostPySide.controllers.project_controller import ProjectController
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from hosts.DesktopHostPySide.controllers.source_controller import SourceController
from hosts.DesktopHostPySide.undo_history import UndoHistory

from packages.domain.result import Error, Ok
from hosts.DesktopHostPySide.views.home_view import HomeView


from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
from hosts.DesktopHostPySide.widgets.design_system import (
    APP_STYLESHEET,
    GOLD,
    apply_light_theme,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE,
    SURFACE,
    SURFACE_HI,
)
from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_alive, shutdown_workers
from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer
from hosts.DesktopHostPySide.widgets.left_drawer import LeftDrawer
from hosts.DesktopHostPySide.widgets.settings_panels import ConfigPanel, ProjectPanel
from hosts.DesktopHostPySide.widgets.toast_layer import ToastLayer


# Index constants for the stack widget (BETA1-A01: only Home + Creation in runtime)
_IDX_HOME = 0
_IDX_CREATION = 1
# BETA-AUDIT-01: ventana de coalescencia del guardado a disco, en ms. Por encima del
# antirrebote de 800 ms de los formularios, para que la validación del payload se
# asiente antes de escribir y para que un lote de riego no escriba por entidad.
_AUTOSAVE_DEBOUNCE_MS = 1500


def _qt_widget_alive(widget) -> bool:
    if widget is None:
        return False
    try:
        widget.objectName()
    except RuntimeError:
        return False
    return True


class MainWindow(QMainWindow):
    """Immersive home + fullscreen space navigation (B31-T01)."""

    def __init__(self):
        super().__init__()
        # BETA2-FOCO-17: la supresión global de tooltips (BETA1-F00) se retira
        # — con paleta clara + QToolTip estilado los tooltips vuelven a ser
        # legibles y el rail de Foco los necesita. El tema claro se aplica
        # también aquí (idempotente) para cubrir arranques que no pasan por
        # main() — p. ej. el arnés visual.
        app = QApplication.instance()
        if app is not None:
            apply_light_theme(app)
        self.ctx = AppContext()
        self.controller = ProjectController()
        self.ctx.project_controller = self.controller
        self.ctx.log_sink = self.log_msg
        # BETA1-F02: el canvas guarda por la misma ruta que el Home
        self.ctx.request_save = self._save

        self.setWindowTitle("Dendro")
        # BETA-CIERRE WS-M/B3: mínimo que CABE en portátiles comunes. El anterior
        # (1180×760) desbordaba 1366×768 y 1080p@150% (1280×720 lógico): la ventana no
        # cabía ni encogía y Guardar/toasts quedaban bajo la barra de tareas. La entrada
        # real (main.py) abre maximizada; este mínimo permite además reducir a mano.
        self.setMinimumSize(1100, 640)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_controllers()
        self._build_views()
        self._build_shell()
        # FIX-13 (G2-19): Deshacer/Rehacer/Guardar existían solo como teclas.
        self._build_menus()
        # UX13: capa de toasts app-wide; ctx.notify(msg, kind) la alimenta.
        self._toast_layer = ToastLayer(self)
        # UX33: levanta los toasts sobre la command bar para que queden junto al
        # botón Guardar (abajo-derecha), no pegados al borde inferior.
        self._toast_layer.set_bottom_offset(120)
        self.ctx.notify_sink = lambda msg, kind="info": self._toast_layer.show_toast(
            msg, kind=kind
        )
        # WS-O: los fallos serios (apertura/guardado) usan un banner persistente
        # con «Abrir registro», en vez de un toast fugaz con ruta incopiable.
        self.ctx.recovery_sink = lambda msg: self._toast_layer.show_recovery(
            msg, on_open_log=self._open_logs_folder
        )
        # WS-C: deshacer/rehacer por instantánea de documento (Ctrl+Z / Ctrl+Y).
        # Debe existir antes de _open_last_project (que reinicia el historial).
        self._undo_history = UndoHistory()
        self._restoring = False
        self._undo_project_id = None
        # BETA-AUDIT-01: antirrebote del guardado a DISCO. Es independiente del
        # antirrebote de 800 ms de los formularios (que gobierna cuándo se valida y
        # aplica el payload en memoria): este coalesce las escrituras para que una
        # ráfaga de teclas —o un lote de riego— no produzca una escritura por
        # elemento. Cada save crea además una copia `.bak`, así que guardar de más
        # quema el historial de copias (ver BETA-AUDIT-15).
        self._dirty = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(_AUTOSAVE_DEBOUNCE_MS)
        self._autosave_timer.timeout.connect(self._flush_autosave)
        self._apply_live_preferences()
        self._apply_advanced_mode(self.ctx.advanced_mode)
        # PA02: auto-carga el último proyecto al arrancar (queda cargado pero el
        # usuario sigue en Home; entra a Creación desde la tarjeta cuando quiera).
        self._open_last_project()

    # ── Controllers ──────────────────────────────────────────────────────────

    def _build_controllers(self):
        ps = self.controller.ps
        self.ai = AIController(ps)
        self.ec = EntityController(project_service=ps)
        self.rc = RelationController(project_service=ps)
        self.cc = CandidateController(project_service=ps)
        self.src = SourceController(project_service=ps)
        self.lc = LayerController(project_service=ps)
        # Autoguardado silencioso (sin toast/refresh/diálogo). Lo consume quien lo necesite.
        self.ctx.request_save_silent = self._save_active_project_silent
        # BETA-AUDIT-01: toda mutación por controlador programa un guardado DIFERIDO
        # a disco. Antes solo mutaba memoria y una caída perdía la sesión entera.
        # Va en los controladores (no en cada panel) para cubrir también las
        # superficies que mutan sin formulario: arrastrar un lapso de vida, crear
        # una relación en el Mapa, convertir un fantasma.
        self.ctx.request_save_debounced = self._schedule_silent_save
        # BETA-MULTIAGENT2-FIX-14 (G2-22): `self.cc` faltaba en esta lista. Aceptar
        # una semilla no ensuciaba el proyecto → no había autoguardado → no había
        # instantánea → Ctrl+Z no llegaba. Y los candidatos que estadía un job de IA
        # (`_auto_stage_and_notify` → `controller.create`) vivían solo en RAM.
        for ctrl in (self.ec, self.rc, self.cc):
            ctrl.on_mutated = self._schedule_silent_save
        # SHIP-01: cualquier vista puede llevar al usuario a los Ajustes de IA.
        self.ctx.open_ai_settings = self._open_ai_settings

    # ── Views ────────────────────────────────────────────────────────────────

    def _build_views(self):
        # BETA2-UX-02: las vistas-tabla legacy (Corpus/Relation/Candidate/Source/
        # Layer) eran inalcanzables (el stack solo monta Home+Creación) y solo
        # servían de envoltorio para transportar sus controllers. Se eliminaron:
        # la Creación recibe los controllers directamente.

        # Home portal
        self.home_view = HomeView(self.ctx)
        self.home_view.register_callback("navigate_creation", lambda: self._go_space(_IDX_CREATION))
        # BETA1-A01: navigate_gallery / navigate_session removed from wiring
        self.home_view.register_callback("project_menu", self._open_project_panel)
        self.home_view.register_callback("config_menu", self._open_config_panel)
        # SHIP-02: los recientes del Home abren el proyecto por ruta a un clic.
        self.home_view.register_callback("open_recent", self._open_project_path)
        # SHIP-04: Acerca de Dendro (versión + identidad).
        self.home_view.register_callback("about", self._open_about_dialog)
        # BETA-AUDIT-05: canal de feedback de la beta cerrada.
        self.home_view.register_callback("report_problem", self._report_problem)
        # BETA2-MEM-10: visor editorial de Memoria (función de proyecto).
        self.home_view.register_callback("memory_menu", self._open_memory_panel)
        # FIX-11 (fase A): «Salud del proyecto» — una sola puerta a «qué va mal».
        self.home_view.register_callback("health_menu", self._open_health_panel)
        self.home_view.register_callback("new_project", self._new_project)
        self.home_view.register_callback("open_project", self._open_project)
        self.home_view.register_callback("save_project", self._save)
        self.home_view.register_callback("close_project", self._close_project)
        self.home_view.register_callback("ai_settings", self._open_ai_settings)
        # WS-D: puerta al proyecto de ejemplo (visible solo si el asset viaja con la app).
        self.home_view.register_callback("open_sample", self._open_sample_project)
        self.home_view.set_sample_available(self._bundled_sample_path() is not None)
        # T05/H03: technical toggles are not exposed from Home.

        # Workspaces: la Creación recibe los controllers directamente (BETA2-UX-02).
        self.creation_workspace = CreationWorkspace(
            self.ctx,
            entity_controller=self.ec,
            relation_controller=self.rc,
            candidate_controller=self.cc,
            source_controller=self.src,
            layer_controller=self.lc,
        )
        # BETA1-H02: legacy gallery/session workspace classes were physically
        # removed from views/workspaces.py.

    # ── Shell ────────────────────────────────────────────────────────────────

    def _build_menus(self):
        """Barra de menús con acciones NOMBRADAS (BETA-MULTIAGENT2-FIX-13, G2-19).

        Hasta aquí la ventana no tenía ni una sola `QAction`: Deshacer, Rehacer y
        Guardar existían y funcionaban, pero SOLO como teclas dentro de
        `keyPressEvent`. Una escritora los descubrió por casualidad («por probar,
        pulso Ctrl+Z. Y funciona»); nadie más tenía forma de enterarse.

        Esto es PEGAMENTO, no función nueva: cada acción llama al handler que ya
        existía. `keyPressEvent` se conserva TAL CUAL —incluida la razón por la
        que vive ahí— porque es lo que deja que los campos de texto conserven su
        deshacer nativo. Comprobado en este repo: con una `QAction` de ámbito de
        ventana y `QKeySequence.Undo`, un `QLineEdit` con el foco SIGUE deshaciendo
        su propia edición (Qt manda `ShortcutOverride` al widget con foco primero)
        y la acción no se dispara. El atajo se ENSEÑA sin robarlo.
        """
        barra = self.menuBar()
        barra.clear()
        # Referencias fuertes desde Python: sin ellas el recolector se lleva los
        # QAction y el menú se queda con punteros muertos («Internal C++ object
        # already deleted» al leer su texto).
        self._menu_actions: list[QAction] = []
        self._menus = []

        def _accion(menu, texto, handler_name, atajo=None, *, tip=""):
            action = QAction(texto, self)
            if atajo is not None:
                action.setShortcut(atajo)
            action.setStatusTip(tip or texto)
            # Enlace TARDÍO por nombre: la acción llama al handler que exista en
            # ese momento — el mismo que usa `keyPressEvent`, sin copiarlo.
            action.triggered.connect(lambda _checked=False, n=handler_name: getattr(self, n)())
            menu.addAction(action)
            self._menu_actions.append(action)
            return action

        def _menu(titulo):
            menu = barra.addMenu(titulo)
            self._menus.append(menu)
            return menu

        archivo = _menu("&Archivo")
        _accion(archivo, "Guardar", "_save", QKeySequence.StandardKey.Save,
                tip="Guarda el proyecto en su fichero")
        _accion(archivo, "Exportar…", "_export_project",
                tip="Exporta el proyecto a un fichero aparte")
        # El QAction que devuelve `addSeparator()` también necesita una referencia
        # fuerte en Python, o el menú acaba con un puntero muerto.
        self._menu_actions.append(archivo.addSeparator())
        _accion(archivo, "Ajustes", "_open_config_panel",
                tip="Apariencia, tamaño de letra e IA")
        # El QAction que devuelve `addSeparator()` también necesita una referencia
        # fuerte en Python, o el menú acaba con un puntero muerto.
        self._menu_actions.append(archivo.addSeparator())
        # Sin atajo: en Windows `StandardKey.Quit` no resuelve a nada útil y el
        # menú acababa enseñando un «Exit» fantasma.
        _accion(archivo, "Salir", "close", tip="Cierra Dendro (ofrece guardar)")

        edicion = _menu("&Edición")
        self.action_undo = _accion(
            edicion, "Deshacer", "_undo", QKeySequence.StandardKey.Undo,
            tip="Deshace el último cambio del canon",
        )
        self.action_redo = _accion(
            edicion, "Rehacer", "_redo", QKeySequence.StandardKey.Redo,
            tip="Rehace el cambio deshecho",
        )

        ayuda = _menu("A&yuda")
        _accion(ayuda, "Glosario", "_open_glossary",
                tip="Qué significan anillo, regar, semilla, foco…")
        _accion(ayuda, "Acerca de Dendro", "_open_about_dialog")
        _accion(ayuda, "Reportar un problema", "_report_problem")
        return barra

    def _open_glossary(self) -> None:
        """FIX-13 (G2-20): el glosario, en una superficie que se LEE sin hover."""
        _apptrace("UI open_glossary")
        from hosts.DesktopHostPySide.widgets.field_help import GlossaryPanel

        if self.ctx.drawer is None:
            return
        if getattr(self.ctx, "left_drawer", None) and self.ctx.left_drawer.isVisible():
            self.ctx.left_drawer.close()
        self.ctx.drawer.set_content(GlossaryPanel(), title="Glosario")
        self.ctx.drawer.open()

    def _build_shell(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # BETA2-UX-02: la barra técnica superior (topbar) estaba siempre oculta;
        # se eliminó. Home no tiene cabecera persistente.

        # Stack horizontal layout. Los cajones YA NO viven aquí: son overlay
        # (ver abajo), así que el stack ocupa el 100% del ancho y la command bar
        # nunca se estrecha al abrir un cajón.
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.home_view)        # 0 - home
        self.stack.addWidget(self._wrap_space(self.creation_workspace, "Creación", _IDX_HOME))  # 1
        # BETA1-A01: stack only holds Home + Creation
        body.addWidget(self.stack, stretch=1)

        root.addLayout(body, stretch=1)

        # Cajones como OVERLAY: hijos del widget central (como ModalOverlay), NO
        # en el layout `body`. Flotan sobre el área del grafo y terminan justo
        # encima de la command bar (ver _drawer_overlay_rect), de modo que ni el
        # grafo ni la barra se estrechan. set_area_provider inyecta esa región.
        self.left_drawer = LeftDrawer(cw)           # for Config panel
        self.ctx.left_drawer = self.left_drawer
        self.left_drawer.set_area_provider(self._drawer_overlay_rect)
        self.drawer = RightDrawer(cw)               # for Project panel
        self.ctx.drawer = self.drawer
        self.drawer.set_area_provider(self._drawer_overlay_rect)
        # Reposicionar el rect reservado al cambiar Home↔Creación (Home no tiene
        # command bar). Al navegar los cajones se cierran, pero es barato y robusto.
        self.stack.currentChanged.connect(self._reposition_drawers)

        # Diagnostic log (hidden by default)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        self.log.setVisible(False)
        root.addWidget(self.log)

        # PA02: overlay modal centrado dentro de la app (wizard, etc.). Hijo del
        # widget central para cubrirlo entero; no es una ventana del SO.
        self.modal_overlay = ModalOverlay(cw)
        self.ctx.modal_overlay = self.modal_overlay

        # BETA1-G08: la elevación del cajón la pinta el propio RightDrawer en su
        # borde izquierdo (paintEvent) — NADA de QGraphicsDropShadowEffect, que
        # cachea el render del panel y deja menús/botones en blanco al tocar.

        status = QStatusBar()
        status.setObjectName("ambientStatusBar")
        status.setStyleSheet(
            f"QStatusBar#ambientStatusBar {{ background: {SURFACE}; color: {INK_MUTED}; "
            f"border-top: 1px solid {LINE}; padding-left: 10px; font-size: 11px; }}"
        )
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        status.showMessage("Listo")

        # Start at home
        self.stack.setCurrentIndex(_IDX_HOME)

    def resizeEvent(self, event):
        """Recolocar los cajones overlay al redimensionar la ventana."""
        super().resizeEvent(event)
        for drawer in (getattr(self, "left_drawer", None), getattr(self, "drawer", None)):
            if drawer is not None:
                drawer.update_target_width()
                drawer.reposition()

    def _drawer_overlay_rect(self) -> QRect:
        """Región (coords del widget central) que un cajón overlay puede cubrir:
        el área del stack MENOS la command bar inferior cuando Creación está
        activa (Home no tiene barra). Así el cajón flota sobre el grafo y su borde
        inferior queda justo encima de la barra, que conserva el ancho completo."""
        g = self.stack.geometry()
        reserved = (
            CreationWorkspace.COMMAND_BAR_HEIGHT
            if self.stack.currentIndex() == _IDX_CREATION
            else 0
        )
        return QRect(g.x(), g.y(), g.width(), max(0, g.height() - reserved))

    def _reposition_drawers(self, *_args) -> None:
        """Reaplica la geometría overlay de ambos cajones (cambio de página)."""
        for drawer in (getattr(self, "left_drawer", None), getattr(self, "drawer", None)):
            if drawer is not None:
                drawer.reposition()


    def _wrap_space(self, workspace: QWidget, title: str, back_idx: int) -> QWidget:
        """Wrap a workspace with a return button bar at the top."""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Navigation bar
        navbar = QFrame()
        navbar.setObjectName("spaceNavbar")
        navbar.setStyleSheet(
            f"QFrame#spaceNavbar {{ background: {SURFACE_HI}; border-bottom: 1px solid {LINE}; }}"
        )
        navbar.setFixedHeight(44)
        nav_layout = QHBoxLayout(navbar)
        nav_layout.setContentsMargins(12, 5, 16, 5)

        back_btn = QPushButton()
        back_btn.setToolTip("Volver a Dendro")
        back_btn.setFixedSize(34, 30)
        back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE}; "
            f"border-radius: 15px; padding: 0px; }} "
            f"QPushButton:hover {{ background: {SURFACE}; border-color: {GOLD}; }}"
        )
        icons.set_button_icon(back_btn, "back", color=INK_SOFT, size=16)
        back_btn.clicked.connect(lambda: self._go_space(back_idx))
        nav_layout.addWidget(back_btn)

        space_title = QLabel(title)
        space_title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {INK_STRONG}; letter-spacing: 0.3px; "
            f"font-family: Georgia, 'Iowan Old Style', serif; background: transparent; border: none;"
        )
        nav_layout.addWidget(space_title)
        nav_layout.addStretch()

        # FOCO-28: las píldoras de modo (Foco | Mapa | Cronología) viven en el
        # banner superior (antes flotaban sobre el lienzo de Creación). addWidget
        # REPARENTA el QFrame existente; sus `_mode_buttons` son los mismos, así
        # que el resaltado del modo activo (`_update_mode_pill`) sigue vigente.
        if hasattr(workspace, "view_toggle_widget"):
            nav_layout.addWidget(workspace.view_toggle_widget())

        layout.addWidget(navbar)
        layout.addWidget(workspace, stretch=1)
        return wrapper

    # ── Navigation ───────────────────────────────────────────────────────────

    def _go_space(self, idx: int):
        _apptrace(f"UI go_space idx={idx}")
        # BETA1-A01: only Home and Creation are navigable in this runtime
        if idx not in (_IDX_HOME, _IDX_CREATION):
            _apptrace(f"UI go_space blocked idx={idx} (fuera de alcance BETA1)")
            return
        if idx == _IDX_CREATION and self._get_active_project() is None:
            _apptrace("UI go_space blocked creation without active project")
            self.log_msg("Abre o crea un proyecto antes de entrar en Creación")
            self.home_view.refresh()
            return
        # Reset outgoing widget's opacity to prevent ghost rendering
        current = self.stack.currentWidget()
        if current and current.graphicsEffect():
            current.graphicsEffect().setOpacity(1.0)
        # Close drawers when navigating AWAY from current space
        self._clear_contextual_surface()
        self.stack.setCurrentIndex(idx)
        widget = self.stack.widget(idx)
        self._animate_stack_arrival(widget)
        # Refresh the space's content
        if idx == _IDX_HOME:
            self.home_view.refresh()
            if hasattr(self.home_view, "animate_arrival"):
                self.home_view.animate_arrival()
        else:
            # The actual workspace is inside the wrapper
            wrapper = widget
            if hasattr(wrapper, "layout"):
                for i in range(wrapper.layout().count()):
                    child = wrapper.layout().itemAt(i).widget()
                    if child and hasattr(child, "refresh"):
                        try:
                            child.refresh()
                        except Exception as exc:
                            self.log_msg(f"Error refreshing: {exc}")
        self.log_msg(f"Navegación: {'Dendro' if idx == _IDX_HOME else 'Creación'}")

    def _clear_contextual_surface(self):
        if getattr(self.ctx, "left_drawer", None) is not None:
            self.ctx.left_drawer.close()
        if getattr(self.ctx, "drawer", None) is not None:
            self.ctx.drawer.close()
        self.ctx.selected_entity_id = None
        self.ctx.selected_relation_id = None
        self.ctx.selected_candidate_id = None
        self.ctx.selected_session_id = None
        self.ctx.selected_campaign_id = None

    def _animate_stack_arrival(self, widget: QWidget):
        # Home has its own animate_arrival() — skip stack opacity animation
        # to prevent ghost workspaces showing through semi-transparent Home.
        idx = self.stack.indexOf(widget)
        if idx == _IDX_HOME:
            return

        effect = widget.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        try:
            effect.setOpacity(0.60)
            duration = self.ctx.animation_duration(380)
            animation = QPropertyAnimation(effect, b"opacity", widget)
            animation.setDuration(duration)
            animation.setStartValue(0.60)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            # El efecto no puede quedarse instalado: QGraphicsEffect sobre un
            # widget dinámico (el workspace con el canvas) cachea el render y
            # acaba blanqueándolo (regla documentada en design_system).
            animation.finished.connect(
                lambda w=widget: _qt_alive(w) and w.setGraphicsEffect(None)
            )
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        except Exception as exc:  # noqa: BLE001 — la animación nunca rompe la navegación
            _apptrace(f"UI stack-anim degradada: {exc}")
            if _qt_alive(widget):
                widget.setGraphicsEffect(None)

    def _apply_live_preferences(self):
        """Apply appearance preferences immediately."""
        _apptrace("UI apply_preferences")
        ctx = self.ctx
        # BETA-MULTIAGENT2-FIX-13 (G2-18): el override de abajo SÍ emitía el
        # tamaño correcto, pero perdía la batalla de precedencia contra los ~190
        # `font-size:` literales que los widgets se ponen a sí mismos (en Qt la
        # hoja del PROPIO widget gana a la del ancestro). Resultado medido por la
        # tester: 11 px en «Mediano» y 11 px en «Grande».
        # La escala del design system reescribe ESOS literales — el único punto
        # donde el arreglo funciona de verdad — y `apply_font_scale` la reaplica
        # al árbol ya construido.
        from hosts.DesktopHostPySide.widgets import design_system as _ds

        _ds.set_font_scale(ctx.font_size)
        base_size = f"{_ds.TYPE_BODY_PX}px"

        # Font family
        family = ctx.font_family or "Georgia"

        # Build dynamic stylesheet override — use SPECIFIC selectors (not *)
        # so they win the CSS specificity battle against APP_STYLESHEET.
        # QMainWindow,QWidget is the highest-specificity base rule.
        override = (
            f"QMainWindow, QWidget, QFrame, QDialog {{ "
            f"font-size: {base_size}; font-family: {family}, 'Courier New', serif; }} "
            f"QLabel, QPushButton, QComboBox, QLineEdit, QTextEdit, "
            f"QPlainTextEdit, QCheckBox, QRadioButton, QGroupBox, "
            f"QTabWidget, QTabBar::tab, QHeaderView::section, "
            f"QListWidget, QTreeWidget, QTableWidget, "
            f"QSpinBox, QDoubleSpinBox, QDateEdit, "
            f"QScrollBar {{ "
            f"font-size: {base_size}; font-family: {family}, 'Courier New', serif; }}"
        )
        # Apply as a secondary stylesheet on top of APP_STYLESHEET
        self.setStyleSheet(_ds.scale_stylesheet(APP_STYLESHEET) + override)
        # …y el árbol ya construido (lo que Carmen tenía delante al cambiar el
        # ajuste): cada widget conserva su hoja original y se reescala desde ella,
        # así que llamar N veces no compone tamaños.
        _ds.apply_font_scale(self)
        # Las superficies que nazcan DESPUÉS (cajones, paneles, diálogos) traen sus
        # propios píxeles literales: el vigía las reescala al mostrarse. Solo se
        # engancha si la escala no es «Mediano».
        app = QApplication.instance()
        if app is not None:
            _ds.sync_font_scale_watcher(app)

        self.log_msg(f"Preferencias aplicadas: fuente {family} {base_size}")

    # ── Project actions ──────────────────────────────────────────────────────

    def _refresh_recent_project_option(self):
        # PA02: el botón "Continuar con X" se eliminó (el último proyecto se
        # auto-carga al arrancar). Limpia recientes muertos y repuebla la lista
        # del Home (SHIP-02).
        path = self.ctx.last_project_path
        if path and not Path(path).exists():
            self.ctx.forget_missing_project(path)
        if hasattr(self, "home_view"):
            self.home_view.refresh_recents()

    def _open_last_project(self):
        _apptrace(f"UI open_last_project path={self.ctx.last_project_path!r}")
        # WS-C: la auto-carga de arranque NO abre un modal de restauración (bloquearía el
        # inicio); un fallo se avisa con toast. La restauración se ofrece en aperturas
        # explícitas (recientes/diálogo), donde el usuario ya está interactuando.
        self._open_project_path(self.ctx.last_project_path, offer_restore=False)

    def _open_project_path(self, path: str, *, offer_restore: bool = True):
        """SHIP-02: abre un proyecto por ruta (auto-carga y recientes del Home)."""
        if not path:
            self._refresh_recent_project_option()
            # SHIP-07: sin proyecto, refrescar el Home para que la tarjeta
            # «Creación» se atenúe y muestre «Abre o crea un proyecto» — si no,
            # arrancaba encendida e invitando a «ENTRAR» pero inerte.
            if hasattr(self, "home_view"):
                self.home_view.refresh()
            return
        if not Path(path).exists():
            self.ctx.notify("El proyecto ya no existe; se ha quitado de recientes.", "info")
            self.ctx.forget_missing_project(path)
            self._refresh_recent_project_option()
            return
        try:
            result = self.controller.open(path)
            if isinstance(result, Error):
                # WS-C: fallo VISIBLE (antes solo statusbar → parecía olvido de datos) y,
                # en aperturas explícitas, ofrecer restaurar una copia .bak si la hay.
                if not (offer_restore and self._offer_backup_restore(path, result.error)):
                    # WS-O: banner PERSISTENTE con «Abrir registro» (no un toast fugaz).
                    self.ctx.notify_recovery(f"No se pudo abrir el proyecto: {result.error}")
                return
            self.ctx.remember_project(path)
            self.log_msg(f"Proyecto abierto: {Path(path).name}")
            self._refresh_all_views()
            self._refresh_recent_project_option()
        except Exception as exc:
            if not (offer_restore and self._offer_backup_restore(path, str(exc))):
                self.ctx.notify_recovery(f"No se pudo abrir el proyecto: {exc}")

    def _offer_backup_restore(self, path: str, error: str) -> bool:
        """WS-C: si abrir falló y hay copias `.bak`, ofrecer restaurar la más reciente.

        La restauración va por ``ProjectMaintenanceService`` (la UI nunca escribe
        persistencia directamente). Devuelve True si se restauró y reabrió con éxito.
        """
        from packages.application.project_maintenance_service import ProjectMaintenanceService

        svc = ProjectMaintenanceService(self.controller.store)
        try:
            backups = svc.list_backups(Path(path))
        except Exception:  # noqa: BLE001
            backups = []
        if not backups:
            return False
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("No se pudo abrir el proyecto")
        box.setText(
            f"No se pudo abrir «{Path(path).name}»:\n{error}\n\n"
            f"Hay {len(backups)} copia(s) de seguridad. ¿Restaurar la más reciente?"
        )
        restore_btn = box.addButton("Restaurar copia", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not restore_btn:
            return False
        res = svc.restore_backup(Path(path), backups[0])
        if isinstance(res, Error):
            self.ctx.notify(f"No se pudo restaurar la copia: {res.error}", "error")
            return False
        reopened = self.controller.open(path)
        if isinstance(reopened, Error):
            self.ctx.notify(f"Copia restaurada, pero no reabre: {reopened.error}", "error")
            return False
        self.ctx.remember_project(path)
        self.ctx.notify("Proyecto restaurado desde una copia de seguridad.", "success")
        self._refresh_all_views()
        self._refresh_recent_project_option()
        return True

    def _open_project_panel(self):
        _apptrace("UI open_project_panel")
        if self.ctx.drawer is None:
            return
        # TOGGLE: if already open, close it
        if self.ctx.drawer.isVisible():
            self.ctx.drawer.close()
            return
        # Mutual exclusion: close left drawer if open
        if getattr(self.ctx, 'left_drawer', None) and self.ctx.left_drawer.isVisible():
            self.ctx.left_drawer.close()
        panel = ProjectPanel(
            ctx=self.ctx,
            callbacks={
                "new_project": self._new_project,
                "open_project": self._open_project,
                "save_project": self._save,
                "close_project": self._close_project,
                # BETA-AUDIT-04 / BETA-AUDIT-15
                "export_project": self._export_project,
                "restore_backup": self._restore_backup_dialog,
            },
            on_preview=self._preview_project_change,
        )
        self.ctx.drawer.set_content(panel, title="Proyecto")
        self.ctx.drawer.open()

    def _open_memory_panel(self, select_key=None):
        """BETA2-MEM-10: visor/EDITOR de la wiki de Memoria (función de proyecto).

        FIX-11 (fase C): el panel recibe el ``ctx`` para poder PEDIR el guardado a
        disco (``request_save_silent``) — antes una página escrita a mano vivía solo
        en memoria hasta que otra mutación cualquiera disparaba el autoguardado.
        ``select_key`` deja abrirlo ya posado sobre una página (lo usa «Salud del
        proyecto» para saltar a la página con el enlace roto).
        """
        _apptrace("UI open_memory_panel")
        if self.ctx.drawer is None:
            return
        if self.ctx.drawer.isVisible():
            if select_key is None:
                self.ctx.drawer.close()
                return
            # Con destino explícito no se cierra: se reutiliza el cajón.
        if getattr(self.ctx, "left_drawer", None) and self.ctx.left_drawer.isVisible():
            self.ctx.left_drawer.close()
        ws = getattr(self, "creation_workspace", None)
        mem_svc = getattr(ws, "memory_service", None) if ws is not None else None
        if mem_svc is None:
            return
        from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

        panel = MemoryViewerPanel(mem_svc, getattr(ws, "memory_ai_service", None), ctx=self.ctx)
        self.ctx.drawer.set_content(panel, title="Memoria")
        self.ctx.drawer.open()
        if select_key is not None:
            panel.select_page(select_key)

    def _open_health_panel(self):
        """FIX-11 (fase A): panel único «Salud del proyecto» (pestañas).

        El lint de la wiki ya existía y funcionaba —determinista, sin IA— pero no
        tenía ninguna puerta desde `hosts/`. Vive aquí, bajo demanda, sin contador
        permanente en la esquina (G2-07). Una sola puerta a «qué va mal»:
        Continuidad + Wiki + Estructura (el panel que ya existía, aquí como
        pestaña; su píldora de Creación sigue siendo la puerta en contexto). La
        pestaña *Continuidad* (FIX-10) entra la primera: es lo que el usuario
        viene a mirar.
        """
        _apptrace("UI open_health_panel")
        if self.ctx.drawer is None:
            return
        if self.ctx.drawer.isVisible():
            self.ctx.drawer.close()
            return
        if getattr(self.ctx, "left_drawer", None) and self.ctx.left_drawer.isVisible():
            self.ctx.left_drawer.close()
        ps = getattr(self.controller, "ps", None)
        if ps is None or getattr(ps, "active_project", None) is None:
            self.ctx.notify("Abre un proyecto para revisar su salud", "info")
            return
        from hosts.DesktopHostPySide.widgets.memory_viewer_panel import element_label
        from hosts.DesktopHostPySide.widgets.project_health_panel import ProjectHealthPanel
        from packages.application.wiki_lint_service import WikiLintService

        ws = getattr(self, "creation_workspace", None)
        lint = WikiLintService(ps, ai_job_service=getattr(ws, "ai_job_service", None))
        panel = ProjectHealthPanel(
            lint,
            on_open_page=self._open_memory_panel,
            element_label=lambda kind, tid: element_label(ps.active_project, kind, tid),
        )
        self._add_structure_tab(panel, ws)
        self._add_continuity_tab(panel, ps)
        self.ctx.drawer.set_content(panel, title="Salud del proyecto")
        self.ctx.drawer.open()

    def _add_continuity_tab(self, panel, ps) -> None:
        """FIX-10 (G2-15): la Continuidad, PRIMERA pestaña y por delante de la wiki.

        Es lo que el usuario viene a buscar cuando abre «qué va mal»: que su
        propia historia no se contradiga. Coste IA cero, sin red y sin proveedor.
        El descarte lo aplica el servicio; aquí solo se pide guardar a disco.
        """
        try:
            from hosts.DesktopHostPySide.widgets.continuity_panel import ContinuityTab
            from packages.application.continuity_service import ContinuityService

            panel.add_section(
                "Continuidad",
                ContinuityTab(
                    ContinuityService(ps),
                    on_dismissed=getattr(self.ctx, "request_save_silent", None),
                ),
                index=0,
            )
            panel.show_section("Continuidad")
        except Exception as exc:  # noqa: BLE001 — una pestaña no puede tumbar el panel
            self.ctx.log("error", f"No se pudo montar la pestaña de Continuidad: {exc}")

    def _add_structure_tab(self, panel, ws) -> None:
        """Cuelga el panel de Estructura como pestaña (misma clase, misma lógica)."""
        svc = getattr(ws, "structural_service", None)
        accept = getattr(ws, "_accept_structural_finding", None)
        if svc is None or not callable(accept):
            return
        try:
            from hosts.DesktopHostPySide.widgets.structure_review_panel import (
                StructureReviewPanel,
            )

            panel.add_section(
                "Estructura",
                StructureReviewPanel(
                    svc,
                    on_accept=accept,
                    on_close=lambda: self.ctx.drawer.close(),
                    log=self.ctx.log,
                ),
            )
        except Exception as exc:  # noqa: BLE001 — una pestaña no puede tumbar el panel
            self.ctx.log("error", f"No se pudo montar la pestaña de Estructura: {exc}")

    def _preview_project_change(self, project_type: str, worldbuilding_active: bool):
        """Apply project type/worldbuilding as a live preview without saving."""
        # Update Home visibility immediately
        self.home_view.update_project_visibility(project_type, worldbuilding_active)
        # Update Creation workspace worldbuilding
        if hasattr(self, 'creation_workspace'):
            self.creation_workspace.set_worldbuilding_active(worldbuilding_active)

    def _open_config_panel(self):
        _apptrace("UI open_config_panel")
        if self.ctx.left_drawer is None:
            return
        # TOGGLE: if already open, close it
        if self.ctx.left_drawer.isVisible():
            self.ctx.left_drawer.close()
            return
        # Mutual exclusion: close right drawer if open
        if self.ctx.drawer is not None and self.ctx.drawer.isVisible():
            self.ctx.drawer.close()
        panel = ConfigPanel(
            ctx=self.ctx,
            ai_controller=self.ai,
            on_status=self._handle_ai_status,
            on_apply=self._apply_live_preferences,
        )
        self.ctx.left_drawer.set_content(panel, title="Configuración")
        self.ctx.left_drawer.open()

    def _open_ai_settings(self):
        # SHIP-07: el aviso «IA no configurada» abre la MISMA ConfigPanel que la
        # Home (persiste vía ctx.save_preferences y prueba conexión en un hilo),
        # abierta directamente en la pestaña IA. El antiguo AISettingsPanel no
        # persistía la clave (se perdía al reiniciar) y congelaba la UI al probar.
        _apptrace("UI open_ai_settings")
        if self.ctx.left_drawer is None:
            return
        if self.ctx.drawer is not None and self.ctx.drawer.isVisible():
            self.ctx.drawer.close()
        panel = ConfigPanel(
            ctx=self.ctx,
            ai_controller=self.ai,
            on_status=self._handle_ai_status,
            on_apply=self._apply_live_preferences,
            initial_tab=1,
        )
        self.ctx.left_drawer.set_content(panel, title="Configuración")
        self.ctx.left_drawer.open()

    def _open_about_dialog(self):
        """SHIP-04 / WS-O: identidad + acceso a los registros para reportar problemas."""
        _apptrace("UI open_about")
        from hosts.DesktopHostPySide.app_context import _log_dir
        from packages.domain.config import AppConfig

        version = AppConfig().app_version
        data_dir = _log_dir()
        box = QMessageBox(self)
        box.setWindowTitle("Acerca de Dendro")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            f"<b>Dendro</b> — arquitecto narrativo<br>"
            f"Versión {version} (beta)<br><br>"
            "Un escritorio tranquilo para crear mundos y relatos. "
            "La IA sugiere y cultiva; tu canon solo cambia cuando tú aceptas.<br><br>"
            "Tus proyectos se guardan donde tú eliges; preferencias y registros, en:<br>"
            f"<code>{data_dir}</code><br><br>"
            "¿Algo falla? Pulsa «Abrir carpeta de registros» y adjunta "
            "<code>dendro.log</code> / <code>dendro_crash.log</code> al reportarlo."
        )
        open_logs = box.addButton(
            "Abrir carpeta de registros", QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_logs:
            self._open_logs_folder()

    def _open_logs_folder(self) -> None:
        """WS-O: abre la carpeta de registros (About + banner de recuperación)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from hosts.DesktopHostPySide.app_context import _log_dir

        data_dir = _log_dir()
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir)))

    def _export_project(self) -> None:
        """BETA-AUDIT-04: saca el mundo a una carpeta de Markdown legible sin Dendro.

        `ExportService` existía, estaba testado y ningún fichero del host lo importaba:
        no había forma de exportar salvo copiar el JSON a mano. Los cuatro perfiles de
        la auditoría lo pidieron; es la respuesta a «¿y si mañana abandonáis esto?».
        """
        from packages.application.export_service import ExportService

        if self.controller.ps.active_project is None:
            self.ctx.notify("Abre un proyecto antes de exportar", "info")
            return
        carpeta = QFileDialog.getExistingDirectory(self, "Exportar el mundo a una carpeta")
        if not carpeta:
            return
        # Se exporta con audiencia «gm» (todo menos fantasmas): es TU copia de
        # seguridad legible, no una versión para enseñar. Los filtros por audiencia
        # del servicio quedan para cuando exista una superficie que los ofrezca.
        resultado = ExportService(project_service=self.controller.ps).export_markdown_bundle(
            carpeta, audience="gm"
        )
        if isinstance(resultado, Error):
            self.ctx.notify(f"No se pudo exportar: {resultado.error}", "error")
            return
        datos = resultado.value
        self.ctx.notify(
            f"Exportadas {datos['entidades']} entidades a {datos['carpeta']}", "success"
        )
        self.log_msg(f"Exportado a {datos['carpeta']} ({datos['entidades']} entidades)")

    def _restore_backup_dialog(self) -> None:
        """BETA-AUDIT-15: restaurar ELIGIENDO la copia, no la más reciente a ciegas.

        Hasta ahora restaurar sólo existía como reacción a un fallo de apertura, y
        tomaba `backups[0]` sin enseñar fechas. PRUEBA-GUIADA.md §13 pedía probarlo
        desde el panel de Proyecto, donde no estaba.
        """
        from datetime import datetime

        from PySide6.QtWidgets import QInputDialog

        ruta = self.controller.current_path
        if not ruta:
            self.ctx.notify("Guarda el proyecto una vez antes de restaurar copias", "info")
            return
        origen = Path(ruta)
        copias = sorted(
            origen.parent.glob(f"{origen.stem}*.bak*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not copias:
            self.ctx.notify("Todavía no hay copias de seguridad de este proyecto", "info")
            return
        etiquetas = [
            f"{datetime.fromtimestamp(p.stat().st_mtime):%d/%m/%Y %H:%M:%S}"
            f"  ·  {p.stat().st_size // 1024} KB  ·  {p.name}"
            for p in copias
        ]
        elegida, ok = QInputDialog.getItem(
            self,
            "Restaurar copia de seguridad",
            "Se guardará una copia del estado actual antes de restaurar.\n"
            "Elige a qué momento quieres volver:",
            etiquetas,
            0,
            False,
        )
        if not ok or not elegida:
            return
        destino = copias[etiquetas.index(elegida)]
        confirmar = QMessageBox.question(
            self,
            "Restaurar copia",
            f"Vas a sustituir el proyecto por la copia de {elegida.split('  ·  ')[0]}.\n"
            "El estado actual se guardará como copia antes de hacerlo. ¿Continuar?",
        )
        if confirmar != QMessageBox.StandardButton.Yes:
            return
        resultado = self.controller.ps.store.restore_backup(origen, destino)
        if isinstance(resultado, Error):
            self.ctx.notify(f"No se pudo restaurar: {resultado.error}", "error")
            return
        self._open_project_path(str(origen))
        self.ctx.notify(f"Restaurada la copia de {elegida.split('  ·  ')[0]}", "success")

    def _report_problem(self) -> None:
        """BETA-AUDIT-05: prepara un informe de incidencia para la beta cerrada.

        Copia al portapapeles un bloque con versión, sistema y las últimas líneas del
        registro, abre el correo con ese mismo texto y deja la carpeta de registros a
        mano. Nada se envía solo: el usuario revisa y decide.
        """
        import platform
        from urllib.parse import quote

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from hosts.DesktopHostPySide.app_context import _log_dir
        from packages.domain.config import AppConfig

        version = AppConfig().app_version
        lineas: list[str] = []
        try:
            registro = _log_dir() / "dendro.log"
            if registro.exists():
                cola = registro.read_text(encoding="utf-8", errors="replace").splitlines()
                lineas = cola[-40:]
        except Exception as exc:  # noqa: BLE001 — reportar nunca debe romper
            lineas = [f"(no se pudo leer el registro: {exc})"]

        cuerpo = (
            "Cuéntame qué hacías y qué esperabas que pasara:\n\n\n"
            "----- datos técnicos (no los borres) -----\n"
            f"Dendro {APP_VERSION}\n"
            f"{platform.platform()} · Python {platform.python_version()}\n"
            f"Registro: {_log_dir() / 'dendro.log'}\n\n"
            "Últimas líneas del registro:\n" + ("\n".join(lineas) or "(vacío)")
        )

        app = QApplication.instance()
        if app is not None:
            app.clipboard().setText(cuerpo)

        asunto = f"Dendro {version} — informe de la beta"
        QDesktopServices.openUrl(
            QUrl(f"mailto:?subject={quote(asunto)}&body={quote(cuerpo)}")
        )
        self.ctx.notify(
            "Informe copiado al portapapeles. Si no se ha abierto tu correo, pégalo "
            "donde quieras contármelo.",
            "info",
        )

    def _handle_ai_status(self, msg: str):
        """Log AI status and refresh contextual AI consumers after settings changes."""
        self.log_msg(f"IA: {msg}")
        if hasattr(self, "creation_workspace") and hasattr(self.creation_workspace, "refresh_ai_controller"):
            self.creation_workspace.refresh_ai_controller()

    def _new_project(self):
        """Nuevo proyecto — abre el wizard como overlay modal centrado (PA02)."""
        _apptrace("UI new_project")
        from hosts.DesktopHostPySide.widgets.project_wizard import ProjectWizard

        wizard = ProjectWizard(self.modal_overlay)
        wizard.cancelled.connect(self.modal_overlay.dismiss)
        wizard.accepted.connect(lambda: self._create_project_from_wizard(wizard))
        self.modal_overlay.open_widget(wizard)

    def _create_project_from_wizard(self, wizard):
        """Crea y guarda el proyecto a partir del wizard ya aceptado."""
        cfg = wizard.collect_config()
        name = cfg.get("name", "Sin nombre").strip() or "Sin nombre"

        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar proyecto", f"{name}.json", "JSON (*.json)"
        )
        if not path:
            # El usuario canceló el guardado: el wizard sigue abierto para reintentar.
            return
        try:
            result = self.controller.create(name, path)
            if not isinstance(result, Ok):
                self.log_msg(f"Error creando proyecto: {result.error}")
                return
            # Apply wizard config to the newly created project
            active = self.controller.ps.active_project
            if active is not None:
                wizard.apply_to_project(active)
            save_result = self.controller.save()
            if not isinstance(save_result, Ok):
                self.log_msg(f"Error guardando proyecto: {save_result.error}")
                return
            self.ctx.remember_project(path)
            self._refresh_recent_project_option()
            self.log_msg(f"Proyecto creado: {Path(path).name}")
            self._refresh_all_views()
            self.modal_overlay.dismiss()
            if self.ctx.drawer:
                self.ctx.drawer.close()
        except Exception as exc:
            self.log_msg(f"Error creando proyecto: {exc}")

    def _bundled_sample_path(self):
        """WS-D: ruta del proyecto de ejemplo (junto al exe congelado; repo/ejemplos en dev)."""
        import sys

        if getattr(sys, "frozen", False):
            base = Path(sys.executable).resolve().parent / "ejemplos"
        else:
            base = Path(__file__).resolve().parents[2] / "ejemplos"
        if not base.is_dir():
            return None
        samples = sorted(base.glob("**/*.json"))
        return samples[0] if samples else None

    def _sample_workspace_dir(self) -> Path:
        """WS-D: carpeta ESCRIBIBLE donde se copia el ejemplo (overridable en tests)."""
        return Path.home() / "Dendro"

    def _open_sample_project(self) -> None:
        """WS-D: abre el proyecto de muestra para explorar Dendro sin partir de cero.

        Se COPIA a una ubicación escribible antes de abrir: el ejemplo viaja junto
        al exe (a menudo en Archivos de programa, solo-lectura), así que abrirlo en
        sitio rompería Guardar y ensuciaría la muestra compartida. Si ya se copió
        antes, se abre esa copia (conserva las ediciones del usuario)."""
        sample = self._bundled_sample_path()
        if sample is None:
            self.ctx.notify("No hay proyecto de ejemplo disponible.", "info")
            return
        import shutil

        dest_dir = self._sample_workspace_dir()
        dest = dest_dir / sample.name
        try:
            if not dest.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(sample), str(dest))
                # El sidecar de assets (<stem>.assets/) viaja con el proyecto.
                src_assets = sample.parent / f"{sample.stem}.assets"
                if src_assets.is_dir():
                    shutil.copytree(
                        str(src_assets),
                        str(dest_dir / f"{dest.stem}.assets"),
                        dirs_exist_ok=True,
                    )
        except Exception as exc:  # noqa: BLE001 — si no se puede copiar, abrir en sitio
            self.ctx.log("error", f"No se pudo copiar el ejemplo: {exc}")
            self._open_project_path(str(sample))
            return
        self._open_project_path(str(dest))

    def _open_project(self):
        _apptrace("UI open_project")
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", "JSON (*.json)")
        if not path:
            return
        try:
            result = self.controller.open(path)
            if isinstance(result, Error):
                if not self._offer_backup_restore(path, result.error):
                    self.ctx.notify(f"No se pudo abrir el proyecto: {result.error}", "error")
                return
            self.ctx.remember_project(path)
            self._refresh_recent_project_option()
            self.log_msg(f"Proyecto abierto: {Path(path).name}")
            self._refresh_all_views()
            if self.ctx.drawer:
                self.ctx.drawer.close()
        except Exception as exc:
            if not self._offer_backup_restore(path, str(exc)):
                self.ctx.notify(f"No se pudo abrir el proyecto: {exc}", "error")

    def _close_project(self):
        _apptrace("UI close_project")
        try:
            self.controller.close()
            self.log_msg("Proyecto cerrado")
            self._refresh_all_views()
            if self.ctx.drawer:
                self.ctx.drawer.close()
        except Exception as exc:
            self.log_msg(f"Error cerrando proyecto: {exc}")

    def _save(self):
        _apptrace("UI save")
        self._save_active_project()

    def _save_active_project(self) -> bool:
        try:
            if self.controller.ps.active_project is None:
                self.log_msg("No hay proyecto activo que guardar")
                return True
            if not self.controller.current_path:
                project = self.controller.ps.active_project
                default_name = f"{getattr(project, 'name', 'proyecto') or 'proyecto'}.json"
                path, _ = QFileDialog.getSaveFileName(
                    self, "Guardar proyecto", default_name, "JSON (*.json)"
                )
                if not path:
                    return False
                self.controller.current_path = str(path)
            result = self.controller.save()
            if not isinstance(result, Ok):
                self.ctx.notify(
                    f"Error guardando proyecto: {getattr(result, 'error', result)}", "error"
                )
                return False
            if self.controller.current_path:
                self.ctx.remember_project(self.controller.current_path)
                self._refresh_recent_project_option()
            self.ctx.notify("Proyecto guardado", "success")
            self._mark_saved()  # BETA-AUDIT-01: el disco ya refleja la memoria
            self._refresh_all_views()
            if self.ctx.drawer:
                self.ctx.drawer.close()
            return True
        except Exception as exc:
            self.log_msg(f"Error guardando proyecto: {exc}")
            return False

    def _save_active_project_silent(self) -> bool:
        """UX33: guarda el proyecto SIN efectos de UI (autoguardado silencioso).

        A diferencia de ``_save_active_project``, no muestra toast "Proyecto
        guardado", no refresca todas las vistas, no cierra el cajón y NO abre un
        diálogo si falta ruta (en ese caso no guarda). Pensado para correr en el
        hilo principal sin interrumpir al usuario."""
        try:
            if self.controller.ps.active_project is None:
                return True
            if not self.controller.current_path:
                self.log_msg("Autoguardado: sin ruta de proyecto; cambios en memoria")
                # BETA-MULTIAGENT2-FIX-14 (G2-22): sin ruta no hay disco, pero SÍ hay
                # deshacer. Los diálogos de borrado prometen ahora Ctrl+Z «mientras la
                # ventana siga abierta»; esa promesa tiene que cumplirse también en un
                # proyecto que todavía no se ha guardado nunca.
                self._record_undo_snapshot()
                return False
            result = self.controller.save()
            if not isinstance(result, Ok):
                self.ctx.notify(
                    f"Error en autoguardado: {getattr(result, 'error', result)}", "error"
                )
                return False
            self.ctx.remember_project(self.controller.current_path)
            self._record_undo_snapshot()  # WS-C: captura el estado asentado
            self._mark_saved()  # BETA-AUDIT-01
            return True
        except Exception as exc:  # noqa: BLE001 — el autoguardado nunca rompe la app
            self.log_msg(f"Error en autoguardado: {exc}")
            return False

    # ── BETA-AUDIT-01: guardado diferido a disco ─────────────────────────────

    def _schedule_silent_save(self) -> None:
        """Marca el proyecto como sucio y (re)arranca la ventana de antirrebote.

        Lo llaman los controladores tras cada mutación asentada. No escribe aquí:
        escribe ``_flush_autosave`` cuando el usuario deja de teclear.
        """
        self._dirty = True
        self._publish_save_state()
        self._autosave_timer.start()

    def _flush_autosave(self) -> bool:
        """Escribe a disco si hay cambios pendientes. Idempotente y seguro.

        Si falla (p. ej. un proyecto que aún no tiene ruta) el estado sigue sucio:
        el diálogo de cierre y la píldora «Guardar» siguen siendo la red de seguridad.
        """
        self._autosave_timer.stop()
        if not self._dirty:
            return True
        return self._save_active_project_silent()

    def _mark_saved(self) -> None:
        """El disco ya refleja la memoria: cancela el diferido pendiente."""
        self._autosave_timer.stop()
        self._dirty = False
        self._publish_save_state()

    def _publish_save_state(self) -> None:
        """Publica el estado de guardado para que la píldora «Guardar» no mienta."""
        self.ctx.unsaved_changes = self._dirty
        hook = getattr(self.ctx, "on_save_state_changed", None)
        if callable(hook):
            try:
                hook(self._dirty)
            except Exception:  # noqa: BLE001 — un indicador nunca rompe el guardado
                pass

    # ── WS-C: deshacer/rehacer por instantánea de documento ──────────────────

    def _project_snapshot(self):
        """Serialización canónica del proyecto activo (la misma que persiste), o None."""
        project = self.controller.ps.active_project
        return project.to_dict() if project is not None else None

    def reset_undo_history(self) -> None:
        """Fija el estado base del historial (al cargar/crear un proyecto)."""
        self._undo_history.reset(self._project_snapshot())

    def _sync_undo_base_if_project_changed(self) -> None:
        """Reinicia el historial cuando cambia la IDENTIDAD del proyecto activo
        (cargar/crear/cerrar). Una restauración de undo mantiene el mismo id (el
        snapshot lo preserva) → no dispara reinicio; un refresco normal tampoco."""
        if getattr(self, "_restoring", False):
            return
        project = self.controller.ps.active_project
        pid = getattr(project, "id", None) if project is not None else None
        if pid != self._undo_project_id:
            self._undo_project_id = pid
            self.reset_undo_history()

    def _record_undo_snapshot(self) -> None:
        """Registra el estado tras una mutación asentada (no durante una restauración)."""
        if getattr(self, "_restoring", False):
            return
        self._undo_history.record(self._project_snapshot())

    def _restore_undo_snapshot(self, snapshot: dict) -> None:
        """Reemplaza el proyecto activo por el snapshot y refresca + persiste."""
        from packages.domain.project import Project

        self._restoring = True
        try:
            self.controller.ps.active_project = Project.from_dict(snapshot)
            self._refresh_all_views()
            self._save_active_project_silent()  # el fichero refleja lo restaurado
        finally:
            self._restoring = False

    def _undo(self) -> None:
        # BETA-MULTIAGENT2-FIX-14 (G2-22): asienta lo que esté en vuelo ANTES de
        # deshacer. La instantánea solo se registra al vencer el antirrebote de
        # 1.500 ms, así que un Ctrl+Z inmediato caía en «Nada que deshacer» — y el
        # diálogo de borrado promete ahora que se puede deshacer «mientras la
        # ventana siga abierta». Sin esto la promesa sería falsa durante 1,5 s.
        self._flush_autosave()
        snapshot = self._undo_history.undo()
        if snapshot is None:
            self.log_msg("Nada que deshacer")
            return
        self._restore_undo_snapshot(snapshot)
        self.log_msg("Deshecho")

    def _redo(self) -> None:
        snapshot = self._undo_history.redo()
        if snapshot is None:
            self.log_msg("Nada que rehacer")
            return
        self._restore_undo_snapshot(snapshot)
        self.log_msg("Rehecho")

    def keyPressEvent(self, event):  # noqa: N802 (Qt API)
        # Ctrl+Z / Ctrl+Y (y Ctrl+Shift+Z) para deshacer/rehacer canon. Solo llega
        # aquí si el widget con foco NO consumió la tecla: los campos de texto
        # (QLineEdit/QTextEdit) conservan su deshacer nativo de edición.
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            key = event.key()
            # BETA-AUDIT-01: Ctrl+S no existía en todo el host. Va antes que el
            # deshacer por ser la tecla más esperada, y no interfiere con él.
            if key == Qt.Key.Key_S and not shift:
                self._save()
                event.accept()
                return
            if key == Qt.Key.Key_Z and not shift:
                self._undo()
                event.accept()
                return
            if key == Qt.Key.Key_Y or (key == Qt.Key.Key_Z and shift):
                self._redo()
                event.accept()
                return
        super().keyPressEvent(event)

    def _flush_pending_form_autosaves(self) -> int:
        """BETA-MULTIAGENT2-FIX-14 (G2-23): vuelca los formularios a medio escribir.

        Los paneles de detalle (`NodeDetailPanel`, `MilestoneDetailPanel`,
        `RelationDetailPanel`) tienen su PROPIO antirrebote de 800 ms: hasta que
        vence, lo tecleado no ha llegado ni al modelo en memoria. Cerrar dentro de
        esa ventana se comía la última frase aunque el usuario respondiera
        «Guardar», porque `_save_active_project` persiste el modelo tal como está.

        El barrido es GENÉRICO a propósito: `foco_view._flush_form_autosave` solo
        mira `self._form_panel` y dejaba fuera el panel de hito (que no volcaba
        NADIE, nunca), los formularios del cajón del Mapa y los dos del modo dual.

        Devuelve cuántos temporizadores se volcaron (para los tests).
        """
        volcados = 0
        try:
            candidatos = QApplication.allWidgets()
        except Exception:  # noqa: BLE001 — sin QApplication no hay nada que volcar
            return 0
        for widget in candidatos:
            # El `_autosave_timer` de una VENTANA es el guardado diferido del
            # proyecto, no un formulario a medio escribir: dispararlo aquí
            # escribiría a disco antes de preguntar y se llevaría por delante el
            # «Descartar» del usuario. Ese lo gestiona `closeEvent` aparte.
            if isinstance(widget, QMainWindow):
                continue
            timer = getattr(widget, "_autosave_timer", None)
            if timer is None or not _qt_alive(widget):
                continue
            try:
                if not timer.isActive():
                    continue
                timer.stop()
                timer.timeout.emit()  # dispara el mismo slot que habría disparado solo
                volcados += 1
            except RuntimeError:
                continue  # widget con el objeto C++ ya destruido: nada que volcar
            except Exception as exc:  # noqa: BLE001 — un panel roto no impide cerrar
                self.log_msg(f"Error volcando el formulario al cerrar: {exc}")
        return volcados

    def closeEvent(self, event):
        # BETA-MULTIAGENT2-FIX-14 (G2-23): PRIMERO volcar lo escrito en los
        # formularios (su antirrebote propio de 800 ms), porque eso puede ensuciar
        # el proyecto; solo después se para el diferido y se pregunta. Al revés el
        # diálogo mentiría sobre lo que hay en disco.
        self._flush_pending_form_autosaves()
        # BETA-AUDIT-01: si queda un guardado diferido en vuelo, asiéntalo antes de
        # preguntar nada — así el diálogo refleja el estado real del disco.
        self._autosave_timer.stop()
        if self._get_active_project() is None:
            shutdown_workers()
            event.accept()
            return
        answer = QMessageBox.question(
            self,
            "Guardar progreso",
            "Hay un proyecto activo. ¿Quieres guardar el progreso antes de salir?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if answer == QMessageBox.StandardButton.Save and not self._save_active_project():
            event.ignore()
            return
        shutdown_workers()
        event.accept()

    def _test_ai(self):
        result = self.ai.test_provider()
        if isinstance(result, Error):
            self.log_msg(f"AI ERROR: {result.error}")
            return
        resp = result.value
        if getattr(resp, "error", None):
            self.log_msg(f"AI ERROR: {resp.error}")
            return
        self.log_msg(f"AI: {resp.provider} — {resp.raw_text[:100]}")

    def _toggle_advanced(self):
        _apptrace(f"UI toggle_advanced new_state={not self.ctx.advanced_mode}")
        new_state = not self.ctx.advanced_mode
        self.ctx.set_advanced_mode(new_state)
        self._apply_advanced_mode(new_state)
        self.log_msg(f"Modo avanzado {'activado' if new_state else 'desactivado'}")
        self._refresh_all_views()

    def _apply_advanced_mode(self, enabled: bool):
        """Propagate advanced/debug visibility to every workspace/view."""
        # BETA1-A02: only runtime widgets (Home/Creation) receive the toggle
        for widget in [self.creation_workspace, self.home_view]:
            if not _qt_widget_alive(widget):
                continue
            if hasattr(widget, "set_advanced_mode"):
                try:
                    widget.set_advanced_mode(enabled)
                except Exception as exc:
                    self.log_msg(f"Error aplicando modo avanzado en {type(widget).__name__}: {exc}")
        if hasattr(self, "log") and not enabled:
            self.log.setVisible(False)
        # Also propagate worldbuilding to creation workspace
        if hasattr(self, "creation_workspace"):
            project = self._get_active_project()
            if project:
                wb = getattr(project, "worldbuilding_active", False)
                self.creation_workspace.set_worldbuilding_active(wb)

    def _get_active_project(self):
        return self.controller.ps.active_project

    # ── Refresh ──────────────────────────────────────────────────────────────

    def _refresh(self):
        # BETA2-UX-02: el topbar técnico (única superficie que consumía estos
        # contadores) se eliminó; el cascade de refresco lo gestionan las vistas.
        _apptrace("UI refresh cascade")

    def _refresh_all_views(self):
        self._sync_undo_base_if_project_changed()  # WS-C: rebase del historial al cambiar de proyecto
        self._refresh()
        self.home_view.refresh()
        if not hasattr(self, "stack"):
            return
        for i in range(self.stack.count()):
            widget = self.stack.widget(i)
            # Unwrap if it's a space wrapper
            if hasattr(widget, "layout"):
                for j in range(widget.layout().count()):
                    child = widget.layout().itemAt(j).widget()
                    if child and hasattr(child, "refresh"):
                        try:
                            child.refresh()
                        except Exception as exc:
                            self.log_msg(f"Error refreshing {type(child).__name__}: {exc}")

    def log_msg(self, msg: str):
        if hasattr(self, "log"):
            self.log.append(msg)
        if hasattr(self, "statusBar") and self.statusBar() is not None:
            clean = str(msg).strip()
            timeout = 7000 if clean.lower().startswith(("error", "fallo", "no se", "warning")) else 3500
            self.statusBar().showMessage(clean, timeout)

    def on_project_loaded(self):
        self._refresh_all_views()
        self.log_msg("Project loaded")
