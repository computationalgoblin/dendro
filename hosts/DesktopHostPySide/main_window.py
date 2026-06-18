"""MainWindow — B31 immersive home + fullscreen navigation.

Architecture (BETA1-A01):
  HomeView (portal, Creación only) → fullscreen Creation
  Gallery/Session workspaces disconnected from runtime (not instantiated).
  No permanent sidebar. Return button inside each space.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtWidgets import (
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

from packages.application.export_service import ExportService
from packages.domain.result import Ok
from hosts.DesktopHostPySide.views.candidate_view import CandidateView
from hosts.DesktopHostPySide.views.corpus_view import CorpusView
from hosts.DesktopHostPySide.views.home_view import HomeView
from hosts.DesktopHostPySide.views.import_export_view import ImportExportView
from hosts.DesktopHostPySide.views.layer_view import LayerView
from hosts.DesktopHostPySide.views.relation_view import RelationView
from hosts.DesktopHostPySide.views.source_view import SourceView


from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
from hosts.DesktopHostPySide.widgets.design_system import (
    APP_STYLESHEET,
    GOLD,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE,
    SURFACE,
    SURFACE_HI,
)
from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer
from hosts.DesktopHostPySide.widgets.left_drawer import LeftDrawer
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerTextPrompt
from hosts.DesktopHostPySide.widgets.settings_panels import AISettingsPanel, ConfigPanel, ProjectActionsPanel, ProjectPanel
from hosts.DesktopHostPySide.widgets.tooltip_suppression import install_tooltip_suppression


# Index constants for the stack widget (BETA1-A01: only Home + Creation in runtime)
_IDX_HOME = 0
_IDX_CREATION = 1


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
        install_tooltip_suppression()
        self.ctx = AppContext()
        self.controller = ProjectController()
        self.ctx.project_controller = self.controller
        self.ctx.log_sink = self.log_msg
        # BETA1-F02: el canvas guarda por la misma ruta que el Home
        self.ctx.request_save = self._save

        self.setWindowTitle("Dendro")
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_controllers()
        self._build_views()
        self._build_shell()
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
        # BETA1-H13: SessionController removed from Desktop runtime. Export UI
        # no longer exposes session/campaign export; ImportExportView builds
        # its own ImportController. See docs/architecture/A03_legacy_classification.md.
        self.export_service = ExportService(
            project_service=ps,
            entity_service=self.ec.es,
        )
        self.src = SourceController(project_service=ps)
        self.lc = LayerController(project_service=ps)

    # ── Views ────────────────────────────────────────────────────────────────

    def _build_views(self):
        # BETA1-H02: only views consumed by Home/Creation are present in the
        # Desktop runtime. Legacy session/campaign/gallery views were removed.
        self.corpus_view = CorpusView(self.ctx, self.ec)
        self.relation_view = RelationView(self.ctx, self.rc)
        self.candidate_view = CandidateView(self.ctx, self.cc)
        self.import_export_view = self._make_import_export_view()
        self.source_view = SourceView(self.ctx, self.src)
        self.layer_view = LayerView(self.ctx, self.lc)

        # Home portal
        self.home_view = HomeView(self.ctx)
        self.home_view.register_callback("navigate_creation", lambda: self._go_space(_IDX_CREATION))
        # BETA1-A01: navigate_gallery / navigate_session removed from wiring
        self.home_view.register_callback("project_menu", self._open_project_panel)
        self.home_view.register_callback("config_menu", self._open_config_panel)
        self.home_view.register_callback("new_project", self._new_project)
        self.home_view.register_callback("open_project", self._open_project)
        self.home_view.register_callback("save_project", self._save)
        self.home_view.register_callback("close_project", self._close_project)
        self.home_view.register_callback("ai_settings", self._open_ai_settings)
        # T05/H03: technical toggles are not exposed from Home.

        # Workspaces (preserve existing views inside them)
        self.creation_workspace = CreationWorkspace(
            self.ctx,
            corpus_view=self.corpus_view,
            relation_view=self.relation_view,
            candidate_view=self.candidate_view,
            import_export_view=self.import_export_view,
            source_view=self.source_view,
            layer_view=self.layer_view,
        )
        # BETA1-H02: legacy gallery/session workspace classes were physically
        # removed from views/workspaces.py.

    def _make_import_export_view(self):
        view = ImportExportView(self.ctx, self.controller, self.export_service)
        view.setWindowTitle("Importación documental")
        return view

    # ── Shell ────────────────────────────────────────────────────────────────

    def _build_shell(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Technical top bar: advanced-mode only. Normal Home has no persistent header.
        topbar = self._build_topbar()
        self._topbar = topbar
        topbar.setVisible(False)
        root.addWidget(topbar)

        # Stack + Drawers horizontal layout
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Left drawer (global, shared via AppContext) — for Config panel
        self.left_drawer = LeftDrawer(self)
        self.ctx.left_drawer = self.left_drawer
        body.addWidget(self.left_drawer)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.home_view)        # 0 - home
        self.stack.addWidget(self._wrap_space(self.creation_workspace, "Creación", _IDX_HOME))  # 1
        # BETA1-A01: stack only holds Home + Creation
        body.addWidget(self.stack, stretch=1)

        # Right drawer (global, shared via AppContext) — for Project panel
        self.drawer = RightDrawer(self)
        self.ctx.drawer = self.drawer
        body.addWidget(self.drawer)

        root.addLayout(body, stretch=1)

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
        """Update drawer heights on window resize."""
        super().resizeEvent(event)
        h = self.height()
        if hasattr(self, "left_drawer") and self.left_drawer is not None:
            self.left_drawer.setFixedHeight(h)
            self.left_drawer.update_target_width()
        if hasattr(self, "drawer") and self.drawer is not None:
            self.drawer.setFixedHeight(h)
            self.drawer.update_target_width()

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setStyleSheet(
            f"QFrame#topbar {{ background: {SURFACE_HI}; border-bottom: 1px solid {LINE}; }}"
        )
        bar.setFixedHeight(40)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(10)

        self._top_project = QLabel("Dendro")
        self._top_project.setStyleSheet(
            "font-weight: 700; font-size: 13px; color: #5C5A3E; "
            "background: transparent; border: none;"
        )
        layout.addWidget(self._top_project)

        self._top_schema = QLabel("")
        self._top_schema.setObjectName("mutedLabel")
        self._top_schema.setStyleSheet("font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self._top_schema)

        layout.addStretch()

        self._top_ai = QLabel(self.ai.provider_info())
        self._top_ai.setObjectName("mutedLabel")
        self._top_ai.setStyleSheet("font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self._top_ai)

        self._advanced_badge = QLabel("AVANZADO")
        self._advanced_badge.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #8A6849; "
            "background: #EFE3C7; border: 1px solid #C8AF8C; "
            "border-radius: 8px; padding: 3px 8px;"
        )
        layout.addWidget(self._advanced_badge)

        return bar

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

        back_btn = QPushButton("←")
        back_btn.setToolTip("Volver a Dendro")
        back_btn.setFixedSize(34, 30)
        back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE}; "
            f"border-radius: 15px; padding: 0px; color: {INK_SOFT}; font-size: 16px; }} "
            f"QPushButton:hover {{ background: {SURFACE}; border-color: {GOLD}; color: {INK_STRONG}; }}"
        )
        back_btn.clicked.connect(lambda: self._go_space(back_idx))
        nav_layout.addWidget(back_btn)

        space_title = QLabel(title)
        space_title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {INK_STRONG}; letter-spacing: 0.3px; "
            f"font-family: Georgia, 'Iowan Old Style', serif; background: transparent; border: none;"
        )
        nav_layout.addWidget(space_title)
        nav_layout.addStretch()

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
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        except Exception:
            pass

    def _apply_live_preferences(self):
        """Apply appearance preferences immediately."""
        _apptrace("UI apply_preferences")
        ctx = self.ctx
        # Font size
        size_map = {"small": "12px", "medium": "13px", "large": "16px"}
        base_size = size_map.get(ctx.font_size, "13px")

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
        self.setStyleSheet(APP_STYLESHEET + override)

        self.log_msg(f"Preferencias aplicadas: fuente {family} {base_size}")

    # ── Project actions ──────────────────────────────────────────────────────

    def _refresh_recent_project_option(self):
        # PA02: el botón "Continuar con X" se eliminó (el último proyecto se
        # auto-carga al arrancar). Este método ahora solo limpia recientes si la
        # ruta guardada ya no existe.
        path = self.ctx.last_project_path
        if path and not Path(path).exists():
            self.ctx.forget_missing_project(path)

    def _open_last_project(self):
        _apptrace(f"UI open_last_project path={self.ctx.last_project_path!r}")
        path = self.ctx.last_project_path
        if not path:
            self._refresh_recent_project_option()
            return
        if not Path(path).exists():
            self.log_msg("El último proyecto ya no existe; se ha quitado de recientes")
            self.ctx.forget_missing_project(path)
            self._refresh_recent_project_option()
            return
        try:
            self.controller.open(path)
            self.ctx.remember_project(path)
            self.log_msg(f"Proyecto abierto: {Path(path).name}")
            self._refresh_all_views()
            self._refresh_recent_project_option()
        except Exception as exc:
            self.log_msg(f"Error abriendo último proyecto: {exc}")

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
                # BETA1-F01: importar documento desde el área de proyecto
                "import_document": self._import_document,
            },
            on_preview=self._preview_project_change,
        )
        self.ctx.drawer.set_content(panel, title="Proyecto")
        self.ctx.drawer.open()

    def _preview_project_change(self, project_type: str, worldbuilding_active: bool):
        """Apply project type/worldbuilding as a live preview without saving."""
        # Update Home visibility immediately
        self.home_view.update_project_visibility(project_type, worldbuilding_active)
        # Update Creation workspace worldbuilding
        if hasattr(self, 'creation_workspace'):
            self.creation_workspace.set_worldbuilding_active(worldbuilding_active)

    def _import_document(self):
        """BETA1-F01: la importación se lanza desde el área de proyecto del
        Home; abre Creación y su utilidad de importación existente (la vista
        no se mueve de sitio — solo cambia la puerta de entrada)."""
        _apptrace("UI import_document")
        self._go_space(_IDX_CREATION)
        workspace = getattr(self, "creation_workspace", None)
        if workspace is not None and hasattr(workspace, "_open_utility"):
            self.import_export_view = self._make_import_export_view()
            workspace.import_export_view = self.import_export_view
            workspace._open_utility(self.import_export_view, title="Importación documental")

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
        _apptrace("UI open_ai_settings")
        if self.ctx.left_drawer is None:
            return
        panel = AISettingsPanel(self.ai, on_status=self._handle_ai_status)
        self.ctx.left_drawer.set_content(panel, title="Ajustes IA")
        self.ctx.left_drawer.open()

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

    def _open_project(self):
        _apptrace("UI open_project")
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.controller.open(path)
            self.ctx.remember_project(path)
            self._refresh_recent_project_option()
            self.log_msg(f"Proyecto abierto: {Path(path).name}")
            self._refresh_all_views()
            if self.ctx.drawer:
                self.ctx.drawer.close()
        except Exception as exc:
            self.log_msg(f"Error abriendo proyecto: {exc}")

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
                self.log_msg(f"Error guardando proyecto: {getattr(result, 'error', result)}")
                return False
            if self.controller.current_path:
                self.ctx.remember_project(self.controller.current_path)
                self._refresh_recent_project_option()
            self.log_msg("Proyecto guardado")
            self._refresh_all_views()
            if self.ctx.drawer:
                self.ctx.drawer.close()
            return True
        except Exception as exc:
            self.log_msg(f"Error guardando proyecto: {exc}")
            return False

    def closeEvent(self, event):
        if self._get_active_project() is None:
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
        event.accept()

    def _test_ai(self):
        result = self.ai.test_provider()
        if hasattr(result, "error"):
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
        for widget in [
            self.creation_workspace, self.import_export_view,
            self.corpus_view, self.relation_view, self.candidate_view,
            self.source_view, self.layer_view, self.home_view,
        ]:
            if not _qt_widget_alive(widget):
                continue
            if hasattr(widget, "set_advanced_mode"):
                try:
                    widget.set_advanced_mode(enabled)
                except Exception as exc:
                    self.log_msg(f"Error aplicando modo avanzado en {type(widget).__name__}: {exc}")
        if hasattr(self, "_advanced_badge"):
            # T05: Always hidden from UI
            self._advanced_badge.setVisible(False)
        if hasattr(self, "_topbar"):
            # T05: Always hidden from UI
            self._topbar.setVisible(False)
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
        _apptrace("UI refresh cascade")
        try:
            c = self.controller.counts()
            if c:
                self._top_project.setText(f"Dendro — {c['name']}")
                self._top_schema.setText(f"schema v{c.get('schema', '?')}")
            else:
                self._top_project.setText("Dendro")
                self._top_schema.setText("")
            self._top_ai.setText(self.ai.provider_info())
        except Exception as exc:
            self.log_msg(f"Refresh error: {exc}")

    def _refresh_all_views(self):
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
