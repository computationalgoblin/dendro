"""MainWindow — B31 immersive home + fullscreen navigation.

Architecture:
  HomeView (portal with 3 cards) → fullscreen Creation/Gallery/Session
  No permanent sidebar. Return button inside each space.
  All existing views/controllers preserved and re-homed.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.ai_controller import AIController
from hosts.DesktopHostPySide.controllers.campaign_controller import CampaignController
from hosts.DesktopHostPySide.controllers.candidate_controller import CandidateController
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from hosts.DesktopHostPySide.controllers.faction_controller import FactionController
from hosts.DesktopHostPySide.controllers.framework_controller import FrameworkController
from hosts.DesktopHostPySide.controllers.import_controller import ImportController
from hosts.DesktopHostPySide.controllers.issue_controller import IssueController
from hosts.DesktopHostPySide.controllers.layer_controller import LayerController
from hosts.DesktopHostPySide.controllers.live_mode_controller import LiveModeController
from hosts.DesktopHostPySide.controllers.post_session_controller import PostSessionController
from hosts.DesktopHostPySide.controllers.project_controller import ProjectController
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from hosts.DesktopHostPySide.controllers.secrets_controller import SecretsController
from hosts.DesktopHostPySide.controllers.session_controller import SessionController
from hosts.DesktopHostPySide.controllers.source_controller import SourceController
from hosts.DesktopHostPySide.controllers.timeline_controller import TimelineController
from hosts.DesktopHostPySide.controllers.writing_controller import WritingController
from packages.application.export_service import ExportService
from hosts.DesktopHostPySide.views.campaign_view import CampaignView, FactionFrontView, SecretsCluesView
from hosts.DesktopHostPySide.views.candidate_view import CandidateView
from hosts.DesktopHostPySide.views.corpus_view import CorpusView
from hosts.DesktopHostPySide.views.framework_view import FrameworkView
from hosts.DesktopHostPySide.views.home_view import HomeView
from hosts.DesktopHostPySide.views.import_export_view import ImportExportView
from hosts.DesktopHostPySide.views.issues_history_view import IssuesHistoryView
from hosts.DesktopHostPySide.views.layer_view import LayerView
from hosts.DesktopHostPySide.views.live_post_view import LivePostView
from hosts.DesktopHostPySide.views.relation_view import RelationView
from hosts.DesktopHostPySide.views.session_view import SessionView
from hosts.DesktopHostPySide.views.source_view import SourceView
from hosts.DesktopHostPySide.views.timeline_view import TimelineView
from hosts.DesktopHostPySide.views.writing_view import WritingView
from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace, GalleryWorkspace, SessionWorkspace
from hosts.DesktopHostPySide.widgets.design_system import APP_STYLESHEET


# Index constants for the stack widget
_IDX_HOME = 0
_IDX_CREATION = 1
_IDX_GALLERY = 2
_IDX_SESSION = 3


class MainWindow(QMainWindow):
    """Immersive home + fullscreen space navigation (B31-T01)."""

    def __init__(self):
        super().__init__()
        self.ctx = AppContext()
        self.controller = ProjectController()
        self.ctx.project_controller = self.controller
        self.ctx.log_sink = self.log_msg

        self.setWindowTitle("Narrative Architect")
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(APP_STYLESHEET)

        self._build_controllers()
        self._build_views()
        self._build_shell()
        self._refresh_all_views()

    # ── Controllers ──────────────────────────────────────────────────────────

    def _build_controllers(self):
        ps = self.controller.ps
        self.ai = AIController(ps)
        self.ec = EntityController(project_service=ps)
        self.rc = RelationController(project_service=ps)
        self.cc = CandidateController(project_service=ps)
        self.issuec = IssueController(project_service=ps)
        self.sc = SessionController(project_service=ps)
        self.lmc = LiveModeController(
            project_service=ps,
            session_service=self.sc.ss,
            secrets_service=self.sc.sec,
            entity_service=self.sc.es,
        )
        self.psc = PostSessionController(project_service=ps, session_service=self.sc.ss)
        self.ic = ImportController(project_service=ps)
        self.ccamp = CampaignController(project_service=ps)
        self.export_service = ExportService(
            project_service=ps,
            entity_service=self.ec.es,
            session_service=self.sc.ss,
        )
        self.secretsc = SecretsController(project_service=ps)
        self.factionc = FactionController(project_service=ps)
        self.wc = WritingController(project_service=ps)
        self.tlc = TimelineController(project_service=ps)
        self.fwc = FrameworkController(project_service=ps)
        self.src = SourceController(project_service=ps)
        self.lc = LayerController(project_service=ps)

    # ── Views ────────────────────────────────────────────────────────────────

    def _build_views(self):
        # All existing connected views are preserved.
        self.corpus_view = CorpusView(self.ctx, self.ec)
        self.relation_view = RelationView(self.ctx, self.rc)
        self.candidate_view = CandidateView(self.ctx, self.cc)
        self.issues_view = IssuesHistoryView(self.ctx, self.issuec, self.sc)
        self.campaign_view = CampaignView(self.ctx, self.ccamp)
        self.secrets_view = SecretsCluesView(self.ctx, self.secretsc)
        self.faction_view = FactionFrontView(self.ctx, self.factionc)
        self.session_view = SessionView(self.ctx, self.sc)
        self.live_post_view = LivePostView(self.ctx, self.sc, lmc=self.lmc, psc=self.psc)
        self.import_export_view = ImportExportView(self.ctx, self.controller, self.export_service)
        self.writing_view = WritingView(self.ctx, self.wc)
        self.timeline_view = TimelineView(self.ctx, self.tlc)
        self.framework_view = FrameworkView(self.ctx, self.fwc)
        self.source_view = SourceView(self.ctx, self.src)
        self.layer_view = LayerView(self.ctx, self.lc)

        # Home portal
        self.home_view = HomeView(self.ctx)
        self.home_view.register_callback("navigate_creation", lambda: self._go_space(_IDX_CREATION))
        self.home_view.register_callback("navigate_gallery", lambda: self._go_space(_IDX_GALLERY))
        self.home_view.register_callback("navigate_session", lambda: self._go_space(_IDX_SESSION))
        self.home_view.register_callback("new_project", self._new_project)
        self.home_view.register_callback("open_project", self._open_project)
        self.home_view.register_callback("save_project", self._save)
        self.home_view.register_callback("close_project", self._close_project)
        self.home_view.register_callback("ai_settings", self._test_ai)
        self.home_view.register_callback("toggle_advanced", self._toggle_advanced)
        self.home_view.register_callback("toggle_diagnostic", self._toggle_diagnostic)

        # Workspaces (preserve existing views inside them)
        self.creation_workspace = CreationWorkspace(
            self.ctx,
            corpus_view=self.corpus_view,
            relation_view=self.relation_view,
            candidate_view=self.candidate_view,
            import_export_view=self.import_export_view,
            writing_view=self.writing_view,
            timeline_view=self.timeline_view,
            framework_view=self.framework_view,
            source_view=self.source_view,
            layer_view=self.layer_view,
        )
        self.gallery_workspace = GalleryWorkspace(self.ctx)
        self.session_workspace = SessionWorkspace(
            self.ctx,
            campaign_view=self.campaign_view,
            faction_view=self.faction_view,
            session_view=self.session_view,
            live_post_view=self.live_post_view,
            secrets_view=self.secrets_view,
            issues_view=self.issues_view,
        )

    # ── Shell ────────────────────────────────────────────────────────────────

    def _build_shell(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar: always visible, minimal
        topbar = self._build_topbar()
        root.addWidget(topbar)

        # Stack: home + 3 spaces
        self.stack = QStackedWidget()
        self.stack.addWidget(self.home_view)        # 0 - home
        self.stack.addWidget(self._wrap_space(self.creation_workspace, "Creación", _IDX_HOME))  # 1
        self.stack.addWidget(self._wrap_space(self.gallery_workspace, "Galería", _IDX_HOME))    # 2
        self.stack.addWidget(self._wrap_space(self.session_workspace, "Sesión", _IDX_HOME))     # 3
        root.addWidget(self.stack, stretch=1)

        # Diagnostic log (hidden by default)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        self.log.setVisible(False)
        root.addWidget(self.log)

        # Start at home
        self.stack.setCurrentIndex(_IDX_HOME)

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setStyleSheet(
            "QFrame#topbar { background: #0B0E13; border-bottom: 1px solid #1E2530; }"
        )
        bar.setFixedHeight(40)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(10)

        self._top_project = QLabel("Narrative Architect")
        self._top_project.setStyleSheet(
            "font-weight: 700; font-size: 13px; color: #ECEFF4; "
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
            "QFrame#spaceNavbar { background: #0D1017; border-bottom: 1px solid #1E2530; }"
        )
        navbar.setFixedHeight(42)
        nav_layout = QHBoxLayout(navbar)
        nav_layout.setContentsMargins(12, 4, 16, 4)

        back_btn = QPushButton("← Inicio")
        back_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #2B3546; "
            "border-radius: 8px; padding: 4px 12px; color: #8993A5; font-size: 12px; } "
            "QPushButton:hover { background: #1A2030; color: #CDD5E0; }"
        )
        back_btn.clicked.connect(lambda: self._go_space(back_idx))
        nav_layout.addWidget(back_btn)

        space_title = QLabel(title)
        space_title.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #ECEFF4; "
            "background: transparent; border: none;"
        )
        nav_layout.addWidget(space_title)
        nav_layout.addStretch()

        layout.addWidget(navbar)
        layout.addWidget(workspace, stretch=1)
        return wrapper

    # ── Navigation ───────────────────────────────────────────────────────────

    def _go_space(self, idx: int):
        self.stack.setCurrentIndex(idx)
        widget = self.stack.widget(idx)
        # Refresh the space's content
        if idx == _IDX_HOME:
            self.home_view.refresh()
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
        self.log_msg(f"Navegación: {'Inicio' if idx == _IDX_HOME else ['','Creación','Galería','Sesión'][idx]}")

    # ── Project actions ──────────────────────────────────────────────────────

    def _new_project(self):
        name, ok = QInputDialog.getText(self, "Nuevo proyecto", "Nombre del proyecto:")
        if not ok or not name.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar proyecto", f"{name.strip()}.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            self.controller.create(name.strip(), path)
            self.controller.save()
            self.log_msg(f"Proyecto creado: {Path(path).name}")
            self._refresh_all_views()
        except Exception as exc:
            self.log_msg(f"Error creando proyecto: {exc}")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.controller.open(path)
            self.log_msg(f"Proyecto abierto: {Path(path).name}")
            self._refresh_all_views()
        except Exception as exc:
            self.log_msg(f"Error abriendo proyecto: {exc}")

    def _close_project(self):
        try:
            self.controller.close()
            self.log_msg("Proyecto cerrado")
            self._refresh_all_views()
        except Exception as exc:
            self.log_msg(f"Error cerrando proyecto: {exc}")

    def _save(self):
        try:
            self.controller.save()
            self.log_msg("Proyecto guardado")
            self._refresh_all_views()
        except Exception as exc:
            self.log_msg(f"Error guardando proyecto: {exc}")

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
        new_state = not self.ctx.advanced_mode
        self.ctx.advanced_mode = new_state
        for widget in [
            self.creation_workspace, self.gallery_workspace,
            self.session_workspace, self.import_export_view,
            self.home_view,
        ]:
            if hasattr(widget, "set_advanced_mode"):
                widget.set_advanced_mode(new_state)
        self.log_msg(f"Modo avanzado {'activado' if new_state else 'desactivado'}")
        self._refresh_all_views()

    def _toggle_diagnostic(self):
        visible = not self.log.isVisible()
        self.log.setVisible(visible and self.ctx.advanced_mode)
        if visible and not self.ctx.advanced_mode:
            self.log_msg("Activa Modo avanzado para ver Diagnóstico")

    # ── Refresh ──────────────────────────────────────────────────────────────

    def _refresh(self):
        try:
            c = self.controller.counts()
            if c:
                self._top_project.setText(f"Narrative Architect — {c['name']}")
                self._top_schema.setText(f"v{c.get('schema', '?')}")
            else:
                self._top_project.setText("Narrative Architect")
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

    def on_project_loaded(self):
        self._refresh_all_views()
        self.log_msg("Project loaded")
