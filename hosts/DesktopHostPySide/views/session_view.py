"""SessionView — sessions/scenes basic management (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.session_controller import SessionController
from packages.domain.result import Error


class SessionView(QWidget):
    def __init__(self, ctx: AppContext, sc: SessionController):
        super().__init__()
        self.ctx = ctx
        self.sc = sc
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        for label, handler in [
            ("Crear sesión", self._create),
            ("Añadir escena", self._add_scene),
            ("Eliminar escena", self._remove_scene),
            ("Session check", self._session_check),
            ("Suggest material", self._suggest_material),
            ("Refrescar", self.refresh),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            act.addWidget(btn)
        layout.addLayout(act)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "State", "Campaign"])
        self.table.itemSelectionChanged.connect(self._select)
        layout.addWidget(self.table)

        self.scene_table = QTableWidget()
        self.scene_table.setColumnCount(4)
        self.scene_table.setHorizontalHeaderLabels(["Scene ID", "Name", "Type", "Order"])
        layout.addWidget(self.scene_table)

    def _selected_session_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _select(self):
        session_id = self._selected_session_id()
        if session_id:
            self.ctx.selected_session_id = session_id
            self._show_scenes()

    def refresh(self):
        sessions = self.sc.list_all()
        self.table.setRowCount(len(sessions))
        for i, session in enumerate(sessions):
            id_item = QTableWidgetItem(session.id[:12])
            id_item.setData(Qt.UserRole, session.id)
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, QTableWidgetItem(session.name))
            self.table.setItem(i, 2, QTableWidgetItem(session.state.value))
            self.table.setItem(i, 3, QTableWidgetItem(session.campaign_id or ""))
        self.table.resizeColumnsToContents()
        if self.ctx.selected_session_id:
            self._show_scenes()

    def _create(self):
        if not getattr(self.sc.ps.active_project, "campaigns", []):
            self.ctx.log("error", "No hay campañas. Crea una campaña antes de una sesión.")
            return
        dlg = QDialog(self)
        form = QFormLayout(dlg)
        name_input = QLineEdit()
        camp_cb = QComboBox()
        for campaign in getattr(self.sc.ps.active_project, "campaigns", []):
            camp_cb.addItem(f"{campaign.name} ({campaign.id[:8]})", campaign.id)
        form.addRow("Nombre:", name_input)
        form.addRow("Campaña:", camp_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            result = self.sc.create({"name": name_input.text(), "campaign_id": camp_cb.currentData()})
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.selected_session_id = result.value.id
                self.ctx.log("info", f"Session created: {result.value.id}")
                self.refresh()

    def _session_obj(self):
        sid = self.ctx.selected_session_id
        if not sid:
            return None
        for session in self.sc.list_all():
            if session.id == sid:
                return session
        return None

    def _show_scenes(self):
        session = self._session_obj()
        if session is None:
            self.scene_table.setRowCount(0)
            return
        scenes = [(scene, "planned") for scene in session.planned_scenes] + [(scene, "optional") for scene in session.optional_scenes]
        self.scene_table.setRowCount(len(scenes))
        for i, (scene, scene_type) in enumerate(scenes):
            id_item = QTableWidgetItem(scene.id[:12])
            id_item.setData(Qt.UserRole, (scene.id, scene_type))
            self.scene_table.setItem(i, 0, id_item)
            self.scene_table.setItem(i, 1, QTableWidgetItem(scene.name))
            self.scene_table.setItem(i, 2, QTableWidgetItem(scene_type))
            self.scene_table.setItem(i, 3, QTableWidgetItem(str(scene.order)))
        self.scene_table.resizeColumnsToContents()

    def _add_scene(self):
        sid = self.ctx.selected_session_id
        if not sid:
            self.ctx.log("error", "Selecciona una sesión")
            return
        name, ok = QInputDialog.getText(self, "Añadir escena", "Nombre:")
        if ok and name:
            result = self.sc.add_scene(sid, {"name": name})
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Scene added: {result.value.id}")
                self._show_scenes()

    def _remove_scene(self):
        sid = self.ctx.selected_session_id
        row = self.scene_table.currentRow()
        if not sid or row < 0:
            self.ctx.log("error", "Selecciona una escena")
            return
        scene_id, target = self.scene_table.item(row, 0).data(Qt.UserRole)
        result = self.sc.remove_scene(sid, scene_id, target=target)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Scene removed: {scene_id}")
            self._show_scenes()

    def _session_check(self):
        sid = self.ctx.selected_session_id
        if not sid:
            self.ctx.log("error", "Selecciona una sesión")
            return
        result = self.sc.check(sid)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Session check: {result.value}")

    def _suggest_material(self):
        sid = self.ctx.selected_session_id
        if not sid:
            self.ctx.log("error", "Selecciona una sesión")
            return
        result = self.sc.suggest_material(sid)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Suggest material creado: {getattr(result.value, 'id', result.value)}")
