"""MainWindow — shell con sidebar + stack views + log (B27.1-T01)."""
from __future__ import annotations
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QTextEdit, QFileDialog, QSplitter, QStackedWidget, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.project_controller import ProjectController
from hosts.DesktopHostPySide.views.dashboard_view import DashboardView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ctx = AppContext()
        self.controller = ProjectController()
        self.ctx.project_controller = self.controller
        self.setWindowTitle("Narrative Architect — Desktop UI MVP")
        self.setMinimumSize(900, 600)
        self._build()
        self._refresh()

    def _build(self):
        cw = QWidget(); self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)

        # Top bar
        top = QHBoxLayout()
        self.project_label = QLabel("Sin proyecto"); top.addWidget(self.project_label)
        top.addStretch()
        self.schema_label = QLabel(""); top.addWidget(self.schema_label)
        top.addWidget(QLabel("| AI:"))
        self.ai_label = QLabel("simulated"); top.addWidget(self.ai_label)
        btn_save = QPushButton("Guardar"); btn_save.clicked.connect(self._save); top.addWidget(btn_save)
        layout.addLayout(top)

        # Body: sidebar + stack
        splitter = QSplitter(Qt.Horizontal)
        self.sidebar = QListWidget(); self.sidebar.setMaximumWidth(160)
        for label in ["Dashboard", "Corpus", "Relations", "Candidates", "Issues/History", "Sessions", "Live/Post", "Import/Export"]:
            self.sidebar.addItem(QListWidgetItem(label))
        self.sidebar.currentRowChanged.connect(self._navigate)
        splitter.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardView(self.ctx, self.controller)
        self.stack.addWidget(self.dashboard)
        # T02: Corpus + Relations
        from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
        from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
        from hosts.DesktopHostPySide.views.corpus_view import CorpusView
        from hosts.DesktopHostPySide.views.relation_view import RelationView
        self.ec = EntityController(project_service=self.controller.ps)
        self.rc = RelationController(project_service=self.controller.ps)
        self.stack.addWidget(CorpusView(self.ctx, self.ec))
        self.stack.addWidget(RelationView(self.ctx, self.rc))
        # T03: Candidates + Issues/History
        from hosts.DesktopHostPySide.controllers.candidate_controller import CandidateController
        from hosts.DesktopHostPySide.views.candidate_view import CandidateView
        from hosts.DesktopHostPySide.views.issues_history_view import IssuesHistoryView
        self.cc = CandidateController(project_service=self.controller.ps)
        self.stack.addWidget(CandidateView(self.ctx, self.cc))
        self.stack.addWidget(IssuesHistoryView(self.ctx, self.controller))
        # T04: Sessions + Live/Post
        from hosts.DesktopHostPySide.controllers.session_controller import SessionController
        from hosts.DesktopHostPySide.views.session_view import SessionView
        from hosts.DesktopHostPySide.views.live_post_view import LivePostView
        self.sc = SessionController(project_service=self.controller.ps)
        self.stack.addWidget(SessionView(self.ctx, self.sc))
        self.stack.addWidget(LivePostView(self.ctx, self.sc))
        # Placeholders for remaining views
        for _ in range(2): self.stack.addWidget(QLabel("Coming soon..."))
        splitter.addWidget(self.stack)
        layout.addWidget(splitter)

        # Log panel
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(120)
        layout.addWidget(self.log)

    def _navigate(self, idx):
        self.stack.setCurrentIndex(idx)
        self.log_msg(f"Navigated to section {idx}")

    def _save(self):
        try: self.controller.save(); self.log_msg("Saved")
        except Exception as e: self.log_msg(f"Error: {e}")

    def _refresh(self):
        try:
            c = self.controller.counts()
            if c: self.project_label.setText(f"Proyecto: {c['name']}")
            self.schema_label.setText(f"Schema v{c.get('schema','?')}")
        except Exception: pass

    def log_msg(self, msg): self.log.append(msg)

    def on_project_loaded(self):
        self._refresh()
        self.dashboard.refresh()
        self.log_msg("Project loaded")
