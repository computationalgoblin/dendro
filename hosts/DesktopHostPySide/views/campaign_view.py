"""CampaignView + SecretsCluesView + FactionFrontView in tabs (B27.2-T06)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
                                QPushButton, QLabel, QLineEdit, QDialog, QFormLayout, QDialogButtonBox)
from hosts.DesktopHostPySide.app_context import AppContext
from packages.domain.result import Error

class CampaignView(QWidget):
    def __init__(self, ctx: AppContext, ctrl): super().__init__(); self.ctx = ctx; self.ctrl = ctrl; self._build()
    def _build(self):
        l = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_create = QPushButton("Crear campaña"); btn_create.clicked.connect(self._create); act.addWidget(btn_create)
        btn = QPushButton("Refrescar"); btn.clicked.connect(self.refresh); act.addWidget(btn)
        l.addLayout(act)
        self.table = QTableWidget(); self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID","Name","System","State"]); l.addWidget(self.table)
    def _create(self):
        dlg = QDialog(self); form = QFormLayout(dlg)
        name = QLineEdit(); system = QLineEdit()
        form.addRow("Nombre:", name); form.addRow("Sistema:", system)
        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            r = self.ctrl.create({"name": name.text(), "game_system": system.text()})
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Campaign {name.text()} created" if not isinstance(r, Error) else r.error)
            self.refresh()

    def refresh(self):
        camps = self.ctrl.list_all()
        self.table.setRowCount(len(camps))
        for i, c in enumerate(camps):
            self.table.setItem(i,0,QTableWidgetItem(c.id[:12])); self.table.setItem(i,1,QTableWidgetItem(c.name))
            self.table.setItem(i,2,QTableWidgetItem(c.game_system)); self.table.setItem(i,3,QTableWidgetItem(c.state.value))
        self.table.resizeColumnsToContents()

class SecretsCluesView(QWidget):
    def __init__(self, ctx: AppContext, ctrl): super().__init__(); self.ctx = ctx; self.ctrl = ctrl; self._build()
    def _build(self):
        l = QVBoxLayout(self); tabs = QTabWidget()
        self.secrets_table = QTableWidget(); self.secrets_table.setColumnCount(4)
        self.secrets_table.setHorizontalHeaderLabels(["ID","Content","Revelation","Visibility"]); tabs.addTab(self.secrets_table, "Secrets")
        self.clues_table = QTableWidget(); self.clues_table.setColumnCount(4)
        self.clues_table.setHorizontalHeaderLabels(["ID","Content","Delivery","Associated Secret"]); tabs.addTab(self.clues_table, "Clues")
        l.addWidget(tabs); btn = QPushButton("Refrescar"); btn.clicked.connect(self.refresh); l.addWidget(btn)
    def refresh(self):
        p = self.ctrl._proj
        secrets = getattr(p, 'secrets', [])
        self.secrets_table.setRowCount(len(secrets))
        for i, s in enumerate(secrets):
            self.secrets_table.setItem(i,0,QTableWidgetItem(s.id[:12])); self.secrets_table.setItem(i,1,QTableWidgetItem(s.content[:60]))
            self.secrets_table.setItem(i,2,QTableWidgetItem(s.revelation_state.value)); self.secrets_table.setItem(i,3,QTableWidgetItem(s.visibility_state or ""))
        self.secrets_table.resizeColumnsToContents()
        clues = getattr(p, 'clues', [])
        self.clues_table.setRowCount(len(clues))
        for i, c in enumerate(clues):
            self.clues_table.setItem(i,0,QTableWidgetItem(c.id[:12])); self.clues_table.setItem(i,1,QTableWidgetItem(c.content[:60]))
            self.clues_table.setItem(i,2,QTableWidgetItem(c.delivery_state.value)); self.clues_table.setItem(i,3,QTableWidgetItem(c.associated_secret_id[:12] if c.associated_secret_id else ""))
        self.clues_table.resizeColumnsToContents()

class FactionFrontView(QWidget):
    def __init__(self, ctx: AppContext, ctrl): super().__init__(); self.ctx = ctx; self.ctrl = ctrl; self._build()
    def _build(self):
        l = QVBoxLayout(self); tabs = QTabWidget()
        self.faction_table = QTableWidget(); self.faction_table.setColumnCount(4)
        self.faction_table.setHorizontalHeaderLabels(["ID","Name","State","Allies/Enemies"]); tabs.addTab(self.faction_table, "Factions")
        btn_fext = QPushButton("Crear extensión de facción"); btn_fext.clicked.connect(self._create_faction_extension); l.addWidget(btn_fext)
        self.front_table = QTableWidget(); self.front_table.setColumnCount(4)
        self.front_table.setHorizontalHeaderLabels(["ID","Name","Type","State"]); tabs.addTab(self.front_table, "Fronts")
        l.addWidget(tabs); btn = QPushButton("Refrescar"); btn.clicked.connect(self.refresh); l.addWidget(btn)
    def _create_faction_extension(self):
        """For FACCION entities without Faction extension, create one."""
        p = self.ctrl._proj
        entities = getattr(p, 'entities', [])
        faction_entities = [e for e in entities if e.entity_type.value == 'faccion']
        existing_eids = {f.entity_id for f in getattr(p, 'factions', [])}
        pending = [e for e in faction_entities if e.id not in existing_eids]
        if not pending: self.ctx.log("info", "No pending FACCION entities"); return
        from PySide6.QtWidgets import QInputDialog
        ids = [f"{e.name} ({e.id[:8]})" for e in pending]
        item, ok = QInputDialog.getItem(self, "Create Faction Extension", "Entity:", ids, 0, False)
        if ok and item:
            eid = item.split("(")[1].rstrip(")")
            from packages.application.faction_service import FactionService
            fs = FactionService(project_service=self.ctrl.ps)
            r = fs.create_faction(entity_id=eid, name=item.split(" (")[0])
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Faction extension created" if not isinstance(r, Error) else r.error)
            self.refresh()

    def refresh(self):
        p = self.ctrl._proj
        factions = getattr(p, 'factions', [])
        self.faction_table.setRowCount(len(factions))
        for i, f in enumerate(factions):
            self.faction_table.setItem(i,0,QTableWidgetItem(f.id[:12])); self.faction_table.setItem(i,1,QTableWidgetItem(f.name))
            self.faction_table.setItem(i,2,QTableWidgetItem(f.state.value)); self.faction_table.setItem(i,3,QTableWidgetItem(f"A:{len(f.ally_faction_ids)} E:{len(f.enemy_faction_ids)}"))
        self.faction_table.resizeColumnsToContents()
        fronts = getattr(p, 'fronts', [])
        self.front_table.setRowCount(len(fronts))
        for i, f in enumerate(fronts):
            self.front_table.setItem(i,0,QTableWidgetItem(f.id[:12])); self.front_table.setItem(i,1,QTableWidgetItem(f.name))
            self.front_table.setItem(i,2,QTableWidgetItem(f.front_type.value if hasattr(f.front_type,'value') else str(f.front_type)))
            self.front_table.setItem(i,3,QTableWidgetItem(f.state.value if hasattr(f.state,'value') else str(f.state)))
        self.front_table.resizeColumnsToContents()
