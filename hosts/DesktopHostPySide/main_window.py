"""MainWindow — B27.5 product shell with Creation/Gallery/Session workspaces."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
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


class MainWindow(QMainWindow):
    """Three-space product shell: Creación, Galería, Sesión."""

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

    def _build_views(self):
        # Existing connected views are preserved and re-homed inside product workspaces.
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

    def _build_shell(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.project_label = QLabel("Sin proyecto")
        self.project_label.setStyleSheet("font-weight: 700;")
        self.schema_label = QLabel("")
        self.schema_label.setObjectName("mutedLabel")
        self.ai_label = QLabel(self.ai.provider_info())
        self.ai_label.setObjectName("mutedLabel")
        top.addWidget(self.project_label)
        top.addStretch()
        top.addWidget(self.schema_label)
        top.addWidget(QLabel("IA:"))
        top.addWidget(self.ai_label)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        for widget in [self.creation_workspace, self.gallery_workspace, self.session_workspace]:
            self.stack.addWidget(widget)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.setVisible(False)
        root.addWidget(self.log)

        self.sidebar.setCurrentRow(0)

    def _build_sidebar(self) -> QWidget:
        shell = QFrame()
        shell.setMaximumWidth(220)
        shell.setMinimumWidth(190)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel("Narrative\nArchitect")
        title.setStyleSheet("font-size: 20px; font-weight: 800; padding: 10px;")
        layout.addWidget(title)

        self.sidebar = QListWidget()
        for label in ["Creación", "Galería", "Sesión"]:
            self.sidebar.addItem(QListWidgetItem(label))
        self.sidebar.currentRowChanged.connect(self._navigate)
        layout.addWidget(self.sidebar, stretch=1)

        config = QFrame()
        config.setStyleSheet("QFrame { background: #0B0E13; border-radius: 12px; }")
        cfg = QVBoxLayout(config)
        cfg.setContentsMargins(10, 10, 10, 10)
        cfg.setSpacing(8)
        cfg.addWidget(QLabel("Proyecto / Configuración"))
        for text, handler in [
            ("Nuevo proyecto", self._new_project),
            ("Abrir proyecto", self._open_project),
            ("Guardar proyecto", self._save),
            ("Cerrar proyecto", self._close_project),
            ("Test IA", self._test_ai),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            cfg.addWidget(btn)
        self.advanced_toggle = QCheckBox("Modo avanzado")
        self.advanced_toggle.toggled.connect(self._set_advanced_mode)
        cfg.addWidget(self.advanced_toggle)
        self.debug_toggle = QCheckBox("Diagnóstico")
        self.debug_toggle.toggled.connect(self._set_debug_visible)
        cfg.addWidget(self.debug_toggle)
        layout.addWidget(config)
        return shell

    def _navigate(self, idx: int):
        if idx < 0:
            return
        self.stack.setCurrentIndex(idx)
        widget = self.stack.widget(idx)
        if hasattr(widget, "refresh"):
            try:
                widget.refresh()
            except Exception as exc:
                self.log_msg(f"Error refreshing {type(widget).__name__}: {exc}")
        self.log_msg(f"Navegación: {self.sidebar.item(idx).text()}")

    def _new_project(self):
        name, ok = QInputDialog.getText(self, "Nuevo proyecto", "Nombre del proyecto:")
        if not ok or not name.strip():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto", f"{name.strip()}.json", "JSON (*.json)")
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

    def _set_advanced_mode(self, enabled: bool):
        self.ctx.advanced_mode = bool(enabled)
        for widget in [self.creation_workspace, self.gallery_workspace, self.session_workspace, self.import_export_view]:
            if hasattr(widget, "set_advanced_mode"):
                widget.set_advanced_mode(bool(enabled))
        if not enabled and self.debug_toggle.isChecked():
            self.debug_toggle.setChecked(False)
        self.log_msg(f"Modo avanzado {'activado' if enabled else 'desactivado'}")
        self._refresh_all_views()

    def _set_debug_visible(self, enabled: bool):
        self.log.setVisible(bool(enabled) and self.ctx.advanced_mode)
        if enabled and not self.ctx.advanced_mode:
            self.log_msg("Activa Modo avanzado para ver Diagnóstico")
            self.debug_toggle.setChecked(False)

    def _refresh(self):
        try:
            c = self.controller.counts()
            if c:
                self.project_label.setText(f"Proyecto: {c['name']}")
                self.schema_label.setText(f"Schema v{c.get('schema', '?')}")
            else:
                self.project_label.setText("Sin proyecto")
                self.schema_label.setText("")
            self.ai_label.setText(self.ai.provider_info())
        except Exception as exc:
            self.log_msg(f"Refresh error: {exc}")

    def _refresh_all_views(self):
        self._refresh()
        if not hasattr(self, "stack"):
            return
        for i in range(self.stack.count()):
            widget = self.stack.widget(i)
            if hasattr(widget, "refresh"):
                try:
                    widget.refresh()
                except Exception as exc:
                    self.log_msg(f"Error refreshing {type(widget).__name__}: {exc}")

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

    def log_msg(self, msg: str):
        if hasattr(self, "log"):
            self.log.append(msg)

    def on_project_loaded(self):
        self._refresh_all_views()
        self.log_msg("Project loaded")
