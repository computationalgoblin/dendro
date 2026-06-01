"""Campaign / Secrets / Factions desktop views (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from packages.domain.result import Error


class CampaignView(QWidget):
    def __init__(self, ctx: AppContext, ctrl):
        super().__init__()
        self.ctx = ctx
        self.ctrl = ctrl
        self._build()

    def _build(self):
        l = QVBoxLayout(self)
        act = QHBoxLayout()
        for label, handler in [
            ("Crear campaña", self._create),
            ("Añadir player", self._add_player),
            ("Crear clock", self._create_clock),
            ("Overview", self._overview),
            ("Refrescar", self.refresh),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            act.addWidget(btn)
        l.addLayout(act)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "System", "State"])
        self.table.itemSelectionChanged.connect(self._select)
        l.addWidget(self.table)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(160)
        l.addWidget(self.output)

    def _selected_campaign_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _select(self):
        campaign_id = self._selected_campaign_id()
        if campaign_id:
            self.ctx.selected_campaign_id = campaign_id

    def _create(self):
        dlg = QDialog(self)
        form = QFormLayout(dlg)
        name = QLineEdit()
        system = QLineEdit()
        description = QLineEdit()
        form.addRow("Nombre:", name)
        form.addRow("Sistema:", system)
        form.addRow("Descripción:", description)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            result = self.ctrl.create({"name": name.text(), "game_system": system.text(), "description": description.text()})
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Campaign created: {result.value.id}")
                self.refresh()

    def _add_player(self):
        campaign_id = self._selected_campaign_id() or self.ctx.selected_campaign_id
        if not campaign_id:
            self.ctx.log("error", "Selecciona una campaña")
            return
        player_name, ok = QInputDialog.getText(self, "Añadir jugador", "Nombre:")
        if ok and player_name:
            result = self.ctrl.add_player(campaign_id, player_name)
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Player added: {result.value.id}")
                self._overview()

    def _create_clock(self):
        campaign_id = self._selected_campaign_id() or self.ctx.selected_campaign_id
        if not campaign_id:
            self.ctx.log("error", "Selecciona una campaña")
            return
        dlg = QDialog(self)
        form = QFormLayout(dlg)
        name = QLineEdit()
        max_value = QLineEdit("4")
        form.addRow("Nombre:", name)
        form.addRow("Max value:", max_value)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            result = self.ctrl.create_clock(campaign_id, {"name": name.text(), "max_value": int(max_value.text() or "4")})
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Clock created: {result.value.id}")
                self._overview()

    def _overview(self):
        campaign_id = self._selected_campaign_id() or self.ctx.selected_campaign_id
        if not campaign_id:
            self.output.setPlainText("Selecciona una campaña")
            return
        result = self.ctrl.overview(campaign_id)
        if isinstance(result, Error):
            self.output.setPlainText(f"Error: {result.error}")
            self.ctx.log("error", result.error)
            return
        self.output.setPlainText(str(result.value))

    def refresh(self):
        campaigns = self.ctrl.list_all()
        self.table.setRowCount(len(campaigns))
        for i, campaign in enumerate(campaigns):
            id_item = QTableWidgetItem(campaign.id[:12])
            id_item.setData(Qt.UserRole, campaign.id)
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, QTableWidgetItem(campaign.name))
            self.table.setItem(i, 2, QTableWidgetItem(campaign.game_system))
            self.table.setItem(i, 3, QTableWidgetItem(campaign.state.value))
        self.table.resizeColumnsToContents()


class SecretsCluesView(QWidget):
    def __init__(self, ctx: AppContext, ctrl):
        super().__init__()
        self.ctx = ctx
        self.ctrl = ctrl
        self._build()

    def _build(self):
        l = QVBoxLayout(self)
        act = QHBoxLayout()
        for label, handler in [
            ("Crear secreto", self._create_secret),
            ("Crear pista", self._create_clue),
            ("Reveal secret", self._reveal_secret),
            ("Deliver clue", self._deliver_clue),
            ("Detect issues", self._detect_issues),
            ("Refrescar", self.refresh),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            act.addWidget(btn)
        l.addLayout(act)

        tabs = QTabWidget()
        self.secrets_table = QTableWidget()
        self.secrets_table.setColumnCount(4)
        self.secrets_table.setHorizontalHeaderLabels(["ID", "Content", "Revelation", "Visibility"])
        tabs.addTab(self.secrets_table, "Secrets")
        self.clues_table = QTableWidget()
        self.clues_table.setColumnCount(4)
        self.clues_table.setHorizontalHeaderLabels(["ID", "Content", "Delivery", "Associated Secret"])
        tabs.addTab(self.clues_table, "Clues")
        l.addWidget(tabs)

    def _selected_secret_id(self):
        row = self.secrets_table.currentRow()
        if row < 0:
            return None
        item = self.secrets_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _selected_clue_id(self):
        row = self.clues_table.currentRow()
        if row < 0:
            return None
        item = self.clues_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _create_secret(self):
        text, ok = QInputDialog.getText(self, "Crear secreto", "Contenido:")
        if ok and text:
            result = self.ctrl.create_secret({"content": text})
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Secret created: {result.value.id}")
                self.refresh()

    def _create_clue(self):
        text, ok = QInputDialog.getText(self, "Crear pista", "Contenido:")
        if not (ok and text):
            return
        data = {"content": text}
        secret_id = self._selected_secret_id()
        if secret_id:
            data["associated_secret_id"] = secret_id
        result = self.ctrl.create_clue(data)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Clue created: {result.value.id}")
            self.refresh()

    def _reveal_secret(self):
        secret_id = self._selected_secret_id()
        if not secret_id:
            self.ctx.log("error", "Selecciona un secreto")
            return
        result = self.ctrl.reveal_secret(secret_id, "parcialmente_revelado")
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Secret revealed: {secret_id}")
            self.refresh()

    def _deliver_clue(self):
        clue_id = self._selected_clue_id()
        if not clue_id:
            self.ctx.log("error", "Selecciona una pista")
            return
        result = self.ctrl.deliver_clue(clue_id, state="entregada")
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Clue delivered: {clue_id}")
            self.refresh()

    def _detect_issues(self):
        issues = self.ctrl.run_validation()
        self.ctx.log("info", f"Secret/clue issues detectadas: {len(issues)}")

    def refresh(self):
        secrets = self.ctrl.list_secrets()
        self.secrets_table.setRowCount(len(secrets))
        for i, secret in enumerate(secrets):
            id_item = QTableWidgetItem(secret.id[:12])
            id_item.setData(Qt.UserRole, secret.id)
            self.secrets_table.setItem(i, 0, id_item)
            self.secrets_table.setItem(i, 1, QTableWidgetItem(secret.content[:60]))
            self.secrets_table.setItem(i, 2, QTableWidgetItem(secret.revelation_state.value))
            visibility = getattr(getattr(secret, "visibility_state", None), "value", getattr(secret, "visibility_state", ""))
            self.secrets_table.setItem(i, 3, QTableWidgetItem(str(visibility)))
        self.secrets_table.resizeColumnsToContents()

        clues = self.ctrl.list_clues()
        self.clues_table.setRowCount(len(clues))
        for i, clue in enumerate(clues):
            id_item = QTableWidgetItem(clue.id[:12])
            id_item.setData(Qt.UserRole, clue.id)
            self.clues_table.setItem(i, 0, id_item)
            self.clues_table.setItem(i, 1, QTableWidgetItem(clue.content[:60]))
            self.clues_table.setItem(i, 2, QTableWidgetItem(clue.delivery_state.value))
            self.clues_table.setItem(i, 3, QTableWidgetItem(clue.associated_secret_id[:12] if clue.associated_secret_id else ""))
        self.clues_table.resizeColumnsToContents()


class FactionFrontView(QWidget):
    def __init__(self, ctx: AppContext, ctrl):
        super().__init__()
        self.ctx = ctx
        self.ctrl = ctrl
        self._build()

    def _build(self):
        l = QVBoxLayout(self)
        act = QHBoxLayout()
        for label, handler in [
            ("Crear extensión de facción", self._create_faction_extension),
            ("Crear front", self._create_front),
            ("Ally", self._ally),
            ("Enemy", self._enemy),
            ("Detect issues", self._detect_issues),
            ("Refrescar", self.refresh),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            act.addWidget(btn)
        l.addLayout(act)

        tabs = QTabWidget()
        self.faction_table = QTableWidget()
        self.faction_table.setColumnCount(5)
        self.faction_table.setHorizontalHeaderLabels(["ID", "Name", "State", "Entity", "Allies/Enemies"])
        tabs.addTab(self.faction_table, "Factions")
        self.front_table = QTableWidget()
        self.front_table.setColumnCount(4)
        self.front_table.setHorizontalHeaderLabels(["ID", "Name", "Type", "State"])
        tabs.addTab(self.front_table, "Fronts")
        l.addWidget(tabs)

    def _selected_faction_id(self):
        row = self.faction_table.currentRow()
        if row < 0:
            return None
        item = self.faction_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _pending_entities(self):
        return self.ctrl.pending_faction_entities()

    def _create_faction_extension(self):
        pending = self._pending_entities()
        if not pending:
            self.ctx.log("info", "No hay entidades FACCION pendientes")
            return
        labels = [f"{entity.name} ({entity.id})" for entity in pending]
        item, ok = QInputDialog.getItem(self, "Create Faction Extension", "Entity:", labels, 0, False)
        if ok and item:
            entity_id = item[item.rfind("(") + 1 : -1]
            name = item[: item.rfind(" (")]
            result = self.ctrl.create_faction({"entity_id": entity_id, "name": name})
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Faction extension created: {result.value.id}")
                self.refresh()

    def _create_front(self):
        name, ok = QInputDialog.getText(self, "Crear front", "Nombre:")
        if ok and name:
            result = self.ctrl.create_front({"name": name})
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Front created: {result.value.id}")
                self.refresh()

    def _ally(self):
        faction_id = self._selected_faction_id()
        factions = self.ctrl.list_factions()
        if not faction_id or len(factions) < 2:
            self.ctx.log("error", "Necesitas al menos dos facciones")
            return
        options = [f"{f.name} ({f.id})" for f in factions if f.id != faction_id]
        item, ok = QInputDialog.getItem(self, "Add ally", "Target:", options, 0, False)
        if ok and item:
            other_id = item[item.rfind("(") + 1 : -1]
            result = self.ctrl.add_ally(faction_id, other_id)
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Faction ally linked: {faction_id} ↔ {other_id}")
                self.refresh()

    def _enemy(self):
        faction_id = self._selected_faction_id()
        factions = self.ctrl.list_factions()
        if not faction_id or len(factions) < 2:
            self.ctx.log("error", "Necesitas al menos dos facciones")
            return
        options = [f"{f.name} ({f.id})" for f in factions if f.id != faction_id]
        item, ok = QInputDialog.getItem(self, "Add enemy", "Target:", options, 0, False)
        if ok and item:
            other_id = item[item.rfind("(") + 1 : -1]
            result = self.ctrl.add_enemy(faction_id, other_id)
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Faction enemy linked: {faction_id} ↔ {other_id}")
                self.refresh()

    def _detect_issues(self):
        issues = self.ctrl.run_validation()
        self.ctx.log("info", f"Faction issues detectadas: {len(issues)}")

    def refresh(self):
        factions = self.ctrl.list_factions()
        self.faction_table.setRowCount(len(factions))
        for i, faction in enumerate(factions):
            id_item = QTableWidgetItem(faction.id[:12])
            id_item.setData(Qt.UserRole, faction.id)
            self.faction_table.setItem(i, 0, id_item)
            self.faction_table.setItem(i, 1, QTableWidgetItem(faction.name))
            self.faction_table.setItem(i, 2, QTableWidgetItem(faction.state.value))
            self.faction_table.setItem(i, 3, QTableWidgetItem(faction.entity_id))
            self.faction_table.setItem(i, 4, QTableWidgetItem(f"A:{len(faction.ally_faction_ids)} E:{len(faction.enemy_faction_ids)}"))
        self.faction_table.resizeColumnsToContents()

        fronts = self.ctrl.list_fronts()
        self.front_table.setRowCount(len(fronts))
        for i, front in enumerate(fronts):
            self.front_table.setItem(i, 0, QTableWidgetItem(front.id[:12]))
            self.front_table.setItem(i, 1, QTableWidgetItem(front.name))
            self.front_table.setItem(i, 2, QTableWidgetItem(front.front_type.value if hasattr(front.front_type, "value") else str(front.front_type)))
            self.front_table.setItem(i, 3, QTableWidgetItem(front.state.value if hasattr(front.state, "value") else str(front.state)))
        self.front_table.resizeColumnsToContents()
