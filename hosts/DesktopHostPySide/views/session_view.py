"""SessionView — session list with create (B27.1-T04)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                                QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox)
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.session_controller import SessionController
from packages.domain.result import Error

class SessionView(QWidget):
    def __init__(self, ctx: AppContext, sc: SessionController):
        super().__init__(); self.ctx = ctx; self.sc = sc; self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_create = QPushButton("Crear sesión"); btn_create.clicked.connect(self._create); act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar"); btn_refresh.clicked.connect(self.refresh); act.addWidget(btn_refresh)
        layout.addLayout(act)
        self.table = QTableWidget(); self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID","Name","State","Campaign"])
        self.table.itemSelectionChanged.connect(self._select); layout.addWidget(self.table)
        self.scene_table = QTableWidget(); self.scene_table.setColumnCount(4)
        self.scene_table.setHorizontalHeaderLabels(["ID","Name","Type","Order"]); layout.addWidget(self.scene_table)
        btns2 = QHBoxLayout()
        btn_add_scene = QPushButton("Añadir escena"); btn_add_scene.clicked.connect(self._add_scene); btns2.addWidget(btn_add_scene)
        layout.addLayout(btns2)

    def refresh(self):
        sessions = self.sc.list_all()
        self.table.setRowCount(len(sessions))
        for i, s in enumerate(sessions):
            self.table.setItem(i, 0, QTableWidgetItem(s.id[:12]))
            self.table.setItem(i, 1, QTableWidgetItem(s.name))
            self.table.setItem(i, 2, QTableWidgetItem(s.state.value))
            self.table.setItem(i, 3, QTableWidgetItem(s.campaign_id or ""))
        self.table.resizeColumnsToContents()
        # Update scene table if exists
        if hasattr(self, 'scene_table') and self.ctx.selected_session_id:
            self._show_scenes()

    def _select(self):
        row = self.table.currentRow()
        if row >= 0: self.ctx.selected_session_id = self.table.item(row, 0).text()

    def _create(self):
        dlg = QDialog(self); form = QFormLayout(dlg)
        name = QLineEdit()
        camp_cb = QComboBox(); camp_cb.addItem("(none)", "")
        for c in getattr(self.sc.ps.active_project, 'campaigns', []):
            camp_cb.addItem(f"{c.name} ({c.id[:8]})", c.id)
        form.addRow("Nombre:", name); form.addRow("Campaña:", camp_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            r = self.sc.create({"name": name.text(), "campaign_id": camp_cb.currentData()})
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Session created" if not isinstance(r, Error) else r.error)
            self.ctx.selected_session_id = r.value.id if not isinstance(r, Error) else None
            self.refresh()

    def _show_scenes(self):
        sid = self.ctx.selected_session_id
        if not sid: return
        for s in self.sc.list_all():
            if s.id.startswith(sid):
                self.scene_table.setRowCount(len(s.planned_scenes) + len(s.optional_scenes))
                i = 0
                for sc in s.planned_scenes:
                    self.scene_table.setItem(i, 0, QTableWidgetItem(sc.id[:8]))
                    self.scene_table.setItem(i, 1, QTableWidgetItem(sc.name)); self.scene_table.setItem(i, 2, QTableWidgetItem("planned"))
                    self.scene_table.setItem(i, 3, QTableWidgetItem(str(sc.order))); i += 1
                for sc in s.optional_scenes:
                    self.scene_table.setItem(i, 0, QTableWidgetItem(sc.id[:8]))
                    self.scene_table.setItem(i, 1, QTableWidgetItem(sc.name)); self.scene_table.setItem(i, 2, QTableWidgetItem("optional"))
                    self.scene_table.setItem(i, 3, QTableWidgetItem(str(sc.order))); i += 1
                self.scene_table.resizeColumnsToContents(); break

    def _add_scene(self):
        sid = self.ctx.selected_session_id
        if not sid: return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Scene", "Name:")
        if ok and name:
            self.sc.ss.add_scene(sid, {"name": name})
            self.ctx.log("info", f"Scene added: {name}")
            self._show_scenes()

