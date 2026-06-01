"""MainWindow — shell con sidebar + stack views + log (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
    QHBoxLayout,
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
from hosts.DesktopHostPySide.views.campaign_view import CampaignView, FactionFrontView, SecretsCluesView
from hosts.DesktopHostPySide.views.candidate_view import CandidateView
from hosts.DesktopHostPySide.views.corpus_view import CorpusView
from hosts.DesktopHostPySide.views.dashboard_view import DashboardView
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ctx = AppContext()
        self.controller = ProjectController()
        self.ctx.project_controller = self.controller
        self.ctx.log_sink = self.log_msg

        self.setWindowTitle("Narrative Architect — Desktop UI")
        self.setMinimumSize(1100, 700)

        self._build_controllers()
        self._build()
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
        self.secretsc = SecretsController(project_service=ps)
        self.factionc = FactionController(project_service=ps)
        self.wc = WritingController(project_service=ps)
        self.tlc = TimelineController(project_service=ps)
        self.fwc = FrameworkController(project_service=ps)
        self.src = SourceController(project_service=ps)
        self.lc = LayerController(project_service=ps)

    def _build(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)

        top = QHBoxLayout()
        self.project_label = QLabel("Sin proyecto")
        self.schema_label = QLabel("")
        self.ai_label = QLabel(self.ai.provider_info())
        btn_ai_test = QPushButton("Test AI")
        btn_ai_test.clicked.connect(self._test_ai)
        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        top.addWidget(self.project_label)
        top.addStretch()
        top.addWidget(self.schema_label)
        top.addWidget(QLabel("| AI:"))
        top.addWidget(self.ai_label)
        top.addWidget(btn_ai_test)
        top.addWidget(btn_save)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(180)
        for label in [
            "Dashboard",
            "Corpus",
            "Relations",
            "Candidates",
            "Issues/History",
            "Campaign",
            "Secrets/Clues",
            "Factions/Fronts",
            "Sessions",
            "Live/Post",
            "Import/Export",
            "Writing",
            "Timeline",
            "Frameworks",
            "Sources",
            "Layers",
        ]:
            self.sidebar.addItem(QListWidgetItem(label))
        self.sidebar.currentRowChanged.connect(self._navigate)
        splitter.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardView(self.ctx, self.controller)
        self.corpus_view = CorpusView(self.ctx, self.ec)
        self.relation_view = RelationView(self.ctx, self.rc)
        self.candidate_view = CandidateView(self.ctx, self.cc)
        self.issues_view = IssuesHistoryView(self.ctx, self.issuec, self.sc)
        self.campaign_view = CampaignView(self.ctx, self.ccamp)
        self.secrets_view = SecretsCluesView(self.ctx, self.secretsc)
        self.faction_view = FactionFrontView(self.ctx, self.factionc)
        self.session_view = SessionView(self.ctx, self.sc)
        self.live_post_view = LivePostView(self.ctx, self.sc, lmc=self.lmc, psc=self.psc)
        self.import_export_view = ImportExportView(self.ctx, self.controller)
        self.writing_view = WritingView(self.ctx, self.wc)
        self.timeline_view = TimelineView(self.ctx, self.tlc)
        self.framework_view = FrameworkView(self.ctx, self.fwc)
        self.source_view = SourceView(self.ctx, self.src)
        self.layer_view = LayerView(self.ctx, self.lc)

        for widget in [
            self.dashboard,
            self.corpus_view,
            self.relation_view,
            self.candidate_view,
            self.issues_view,
            self.campaign_view,
            self.secrets_view,
            self.faction_view,
            self.session_view,
            self.live_post_view,
            self.import_export_view,
            self.writing_view,
            self.timeline_view,
            self.framework_view,
            self.source_view,
            self.layer_view,
        ]:
            self.stack.addWidget(widget)

        splitter.addWidget(self.stack)
        layout.addWidget(splitter)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        layout.addWidget(self.log)

        self.sidebar.setCurrentRow(0)

    def _navigate(self, idx):
        if idx < 0:
            return
        self.stack.setCurrentIndex(idx)
        widget = self.stack.widget(idx)
        if hasattr(widget, "refresh"):
            try:
                widget.refresh()
            except Exception as exc:
                self.log_msg(f"Error refreshing {type(widget).__name__}: {exc}")
        self.log_msg(f"Navigated to section {idx}")

    def _save(self):
        try:
            self.controller.save()
            self.log_msg("Saved")
            self._refresh_all_views()
        except Exception as exc:
            self.log_msg(f"Error: {exc}")

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

    def log_msg(self, msg):
        self.log.append(msg)

    def on_project_loaded(self):
        self._refresh_all_views()
        self.log_msg("Project loaded")
