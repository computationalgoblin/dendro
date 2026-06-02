"""Campaign / Secrets / Factions desktop views (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerForm
from hosts.DesktopHostPySide.widgets.inspector_panel import InspectorPanel
from packages.domain.campaign_models import CampaignState
from packages.domain.faction_models import FactionState, FrontState, FrontType
from packages.domain.result import Error


def _enum_values(enum_cls):
    return [item.value for item in enum_cls]


def _split_csv(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _as_list(value):
    return value if isinstance(value, list) else []


def _as_dict(value):
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# DrawerForm subclasses for the RightDrawer pattern
# ---------------------------------------------------------------------------

class CreateCampaignForm(DrawerForm):
    def __init__(self, ctx, ctrl, refresh_cb, parent=None):
        super().__init__(ctx, title="Crear campaña", parent=parent)
        self.ctrl = ctrl
        self._refresh_cb = refresh_cb
        self.name = QLineEdit()
        self.system = QLineEdit()
        self.tone = QLineEdit()
        self.genre = QLineEdit()
        self.world_entity_id = QLineEdit()
        self.state = QComboBox()
        self.state.addItems(_enum_values(CampaignState))
        self.description = QLineEdit()
        self.form_layout.addRow("Nombre:", self.name)
        self.form_layout.addRow("Sistema:", self.system)
        self.form_layout.addRow("Tono:", self.tone)
        self.form_layout.addRow("Género:", self.genre)
        self.form_layout.addRow("World entity ID:", self.world_entity_id)
        self.form_layout.addRow("Estado:", self.state)
        self.form_layout.addRow("Descripción:", self.description)

    def _on_accept(self):
        result = self.ctrl.create({
            "name": self.name.text(),
            "game_system": self.system.text(),
            "tone": self.tone.text(),
            "genre": self.genre.text(),
            "world_entity_id": self.world_entity_id.text() or None,
            "state": self.state.currentText(),
            "description": self.description.text(),
        })
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Campaign created: {result.value.id}")
            self._close_drawer()
            self._refresh_cb()


class CreateClockForm(DrawerForm):
    def __init__(self, ctx, ctrl, campaign_id, refresh_cb, parent=None):
        super().__init__(ctx, title="Crear clock", parent=parent)
        self.ctrl = ctrl
        self._campaign_id = campaign_id
        self._refresh_cb = refresh_cb
        self.name = QLineEdit()
        self.max_value = QLineEdit("4")
        self.form_layout.addRow("Nombre:", self.name)
        self.form_layout.addRow("Max value:", self.max_value)

    def _on_accept(self):
        result = self.ctrl.create_clock(
            self._campaign_id,
            {"name": self.name.text(), "max_value": int(self.max_value.text() or "4")},
        )
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Clock created: {result.value.id}")
            self._close_drawer()
            self._refresh_cb()


class CreateFrontForm(DrawerForm):
    def __init__(self, ctx, ctrl, refresh_cb, parent=None):
        super().__init__(ctx, title="Crear front", parent=parent)
        self.ctrl = ctrl
        self._refresh_cb = refresh_cb
        self.name = QLineEdit()
        self.front_type = QComboBox()
        self.front_type.addItems(_enum_values(FrontType))
        self.state = QComboBox()
        self.state.addItems(_enum_values(FrontState))
        self.description = QLineEdit()
        self.faction_id = QLineEdit()
        self.form_layout.addRow("Nombre:", self.name)
        self.form_layout.addRow("Tipo:", self.front_type)
        self.form_layout.addRow("Estado:", self.state)
        self.form_layout.addRow("Descripción:", self.description)
        self.form_layout.addRow("Faction ID:", self.faction_id)

    def _on_accept(self):
        result = self.ctrl.create_front({
            "name": self.name.text(),
            "front_type": self.front_type.currentText(),
            "state": self.state.currentText(),
            "description": self.description.text(),
            "faction_id": self.faction_id.text() or None,
        })
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Front created: {result.value.id}")
            self._close_drawer()
            self._refresh_cb()


class AddStageForm(DrawerForm):
    def __init__(self, ctx, ctrl, front_id, refresh_cb, parent=None):
        super().__init__(ctx, title="Añadir stage", parent=parent)
        self.ctrl = ctrl
        self._front_id = front_id
        self._refresh_cb = refresh_cb
        self.name = QLineEdit()
        self.threshold = QLineEdit("0")
        self.description = QLineEdit()
        self.form_layout.addRow("Nombre:", self.name)
        self.form_layout.addRow("Threshold:", self.threshold)
        self.form_layout.addRow("Descripción:", self.description)

    def _on_accept(self):
        try:
            threshold_value = int(self.threshold.text() or "0")
        except ValueError:
            threshold_value = 0
        result = self.ctrl.add_stage(
            self._front_id,
            {"name": self.name.text(), "threshold": threshold_value, "description": self.description.text()},
        )
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Stage added to front: {self._front_id}")
            self._close_drawer()
            self._refresh_cb()


# ---------------------------------------------------------------------------
# View classes
# ---------------------------------------------------------------------------

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
        body = QHBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "System", "State"])
        self.table.itemSelectionChanged.connect(self._select)
        body.addWidget(self.table, 3)
        self.inspector = InspectorPanel("Campaign Inspector")
        body.addWidget(self.inspector, 1)
        l.addLayout(body)
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
            self._bind_campaign(campaign_id)

    def _campaign_fields(self, campaign):
        return [
            {"name": "name", "label": "Nombre", "value": campaign.name},
            {"name": "description", "label": "Descripción", "kind": "multiline", "value": campaign.description},
            {"name": "world_entity_id", "label": "World entity ID", "value": campaign.world_entity_id or ""},
            {"name": "game_system", "label": "Sistema", "value": campaign.game_system},
            {"name": "tone", "label": "Tono", "value": campaign.tone},
            {"name": "genre", "label": "Género", "value": campaign.genre},
            {"name": "state", "label": "Estado", "kind": "combo", "value": campaign.state, "options": _enum_values(CampaignState)},
            {"name": "players", "label": "Players JSON", "kind": "json", "value": [p.to_dict() if hasattr(p, "to_dict") else p for p in campaign.players]},
            {"name": "player_character_entity_ids", "label": "PC entity IDs (csv)", "value": campaign.player_character_entity_ids},
            {"name": "session_entity_ids", "label": "Session entity IDs (csv)", "value": campaign.session_entity_ids},
            {"name": "session_ids", "label": "Session IDs (csv)", "value": campaign.session_ids},
            {"name": "active_plot_entity_ids", "label": "Plot IDs (csv)", "value": campaign.active_plot_entity_ids},
            {"name": "active_faction_entity_ids", "label": "Faction entity IDs (csv)", "value": campaign.active_faction_entity_ids},
            {"name": "active_location_entity_ids", "label": "Location IDs (csv)", "value": campaign.active_location_entity_ids},
            {"name": "secret_entity_ids", "label": "Secret IDs (csv)", "value": campaign.secret_entity_ids},
            {"name": "clue_entity_ids", "label": "Clue IDs (csv)", "value": campaign.clue_entity_ids},
            {"name": "clock_ids", "label": "Clock IDs (csv)", "value": campaign.clock_ids},
            {"name": "private_notes", "label": "Private notes JSON", "kind": "json", "value": campaign.private_notes},
            {"name": "public_summaries", "label": "Public summaries JSON", "kind": "json", "value": campaign.public_summaries},
            {"name": "visibility_rules", "label": "Visibility rules JSON", "kind": "json", "value": campaign.visibility_rules},
            {"name": "history", "label": "History JSON", "kind": "json", "value": campaign.history},
            {"name": "metadata", "label": "Metadata JSON", "kind": "json", "value": campaign.metadata},
        ]

    def _campaign_payload(self, values):
        payload = dict(values)
        for key in ("player_character_entity_ids", "session_entity_ids", "session_ids", "active_plot_entity_ids", "active_faction_entity_ids", "active_location_entity_ids", "secret_entity_ids", "clue_entity_ids", "clock_ids"):
            payload[key] = _split_csv(payload.get(key))
        for key in ("players", "private_notes", "public_summaries", "history"):
            payload[key] = _as_list(payload.get(key))
        payload["visibility_rules"] = _as_dict(payload.get("visibility_rules"))
        payload["metadata"] = _as_dict(payload.get("metadata"))
        return payload

    def _bind_campaign(self, campaign_id):
        result = self.ctrl.get(campaign_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        campaign = result.value
        self.inspector.bind(
            title=f"Campaign · {campaign.name}",
            object_id=campaign.id,
            fields=self._campaign_fields(campaign),
            on_save=lambda values, cid=campaign.id: self._save_campaign(cid, values),
            on_revert=lambda cid=campaign.id: self._bind_campaign(cid),
        )

    def _save_campaign(self, campaign_id, values):
        result = self.ctrl.update(campaign_id, self._campaign_payload(values))
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            raise RuntimeError(result.error)
        self.ctx.log("info", f"Campaign updated: {campaign_id}")
        self.refresh()
        self._select_campaign_row(campaign_id)

    def _select_campaign_row(self, campaign_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.UserRole) == campaign_id:
                self.table.selectRow(row)
                return

    def _create(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = CreateCampaignForm(self.ctx, self.ctrl, self.refresh)
        drawer.set_content(form, title="Crear campaña")
        drawer.open()

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
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = CreateClockForm(self.ctx, self.ctrl, campaign_id, self._overview)
        drawer.set_content(form, title="Crear clock")
        drawer.open()

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
            ("Añadir stage", self._add_stage),
            ("Ally", self._ally),
            ("Enemy", self._enemy),
            ("Detect issues", self._detect_issues),
            ("Refrescar", self.refresh),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            act.addWidget(btn)
        l.addLayout(act)

        body = QHBoxLayout()
        tabs = QTabWidget()
        self.faction_table = QTableWidget()
        self.faction_table.setColumnCount(5)
        self.faction_table.setHorizontalHeaderLabels(["ID", "Name", "State", "Entity", "Allies/Enemies"])
        self.faction_table.itemSelectionChanged.connect(self._bind_selected_faction)
        tabs.addTab(self.faction_table, "Factions")
        self.front_table = QTableWidget()
        self.front_table.setColumnCount(4)
        self.front_table.setHorizontalHeaderLabels(["ID", "Name", "Type", "State"])
        self.front_table.itemSelectionChanged.connect(self._bind_selected_front)
        tabs.addTab(self.front_table, "Fronts")
        self.stage_table = QTableWidget()
        self.stage_table.setColumnCount(5)
        self.stage_table.setHorizontalHeaderLabels(["Front ID", "Stage", "Name", "Threshold", "Terminal"])
        self.stage_table.itemSelectionChanged.connect(self._bind_selected_stage)
        tabs.addTab(self.stage_table, "Stages")
        body.addWidget(tabs, 3)
        self.inspector = InspectorPanel("Faction/Front Inspector")
        body.addWidget(self.inspector, 1)
        l.addLayout(body)

    def _selected_faction_id(self):
        row = self.faction_table.currentRow()
        if row < 0:
            return None
        item = self.faction_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _selected_front_id(self):
        row = self.front_table.currentRow()
        if row < 0:
            return None
        item = self.front_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _selected_stage_ref(self):
        row = self.stage_table.currentRow()
        if row < 0:
            return None
        item = self.stage_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _bind_selected_faction(self):
        faction_id = self._selected_faction_id()
        if not faction_id:
            return
        result = self.ctrl.get_faction(faction_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        faction = result.value
        fields = [
            {"name": "name", "label": "Nombre", "value": faction.name},
            {"name": "state", "label": "Estado", "kind": "combo", "value": faction.state, "options": _enum_values(FactionState)},
            {"name": "ideology", "label": "Ideología", "kind": "multiline", "value": faction.ideology},
            {"name": "methods", "label": "Métodos", "kind": "multiline", "value": faction.methods},
            {"name": "objectives", "label": "Objetivos JSON", "kind": "json", "value": faction.objectives},
            {"name": "resources", "label": "Recursos JSON", "kind": "json", "value": faction.resources},
            {"name": "relation_with_pcs", "label": "Relación PCs", "kind": "multiline", "value": faction.relation_with_pcs},
            {"name": "relation_with_factions", "label": "Relación facciones", "kind": "multiline", "value": faction.relation_with_factions},
            {"name": "possible_reactions", "label": "Reacciones JSON", "kind": "json", "value": faction.possible_reactions},
            {"name": "inaction_consequences", "label": "Inacción JSON", "kind": "json", "value": faction.inaction_consequences},
            {"name": "intervention_consequences", "label": "Intervención JSON", "kind": "json", "value": faction.intervention_consequences},
        ]
        self.inspector.bind(
            title=f"Faction · {faction.name}",
            object_id=faction.id,
            fields=fields,
            on_save=lambda values, fid=faction.id: self._save_faction(fid, values),
            on_revert=self._bind_selected_faction,
        )

    def _save_faction(self, faction_id, values):
        payload = dict(values)
        for key in ("objectives", "resources", "possible_reactions", "inaction_consequences", "intervention_consequences"):
            payload[key] = _as_list(payload.get(key))
        result = self.ctrl.update_faction(faction_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            raise RuntimeError(result.error)
        self.ctx.log("info", f"Faction updated: {faction_id}")
        self.refresh()

    def _bind_selected_front(self):
        front_id = self._selected_front_id()
        if not front_id:
            return
        result = self.ctrl.get_front(front_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        front = result.value
        fields = [
            {"name": "name", "label": "Nombre", "value": front.name},
            {"name": "front_type", "label": "Tipo", "kind": "combo", "value": front.front_type, "options": _enum_values(FrontType)},
            {"name": "description", "label": "Descripción", "kind": "multiline", "value": front.description},
            {"name": "faction_id", "label": "Faction ID", "value": front.faction_id or ""},
            {"name": "state", "label": "Estado", "kind": "combo", "value": front.state, "options": _enum_values(FrontState)},
            {"name": "current_stage_index", "label": "Stage actual", "value": front.current_stage_index},
            {"name": "entity_id", "label": "Entity ID", "value": front.entity_id or ""},
            {"name": "clock_id", "label": "Clock ID", "value": front.clock_id or ""},
            {"name": "advance_conditions", "label": "Avance JSON", "kind": "json", "value": front.advance_conditions},
            {"name": "retreat_conditions", "label": "Retroceso JSON", "kind": "json", "value": front.retreat_conditions},
            {"name": "session_ids", "label": "Session IDs (csv)", "value": front.session_ids},
            {"name": "affected_entity_ids", "label": "Affected IDs (csv)", "value": front.affected_entity_ids},
            {"name": "visibility_state", "label": "Visibilidad", "value": front.visibility_state},
            {"name": "stages", "label": "Stages JSON", "kind": "json", "value": [s.to_dict() for s in front.stages]},
            {"name": "metadata", "label": "Metadata JSON", "kind": "json", "value": front.metadata},
        ]
        self.inspector.bind(
            title=f"Front · {front.name}",
            object_id=front.id,
            fields=fields,
            on_save=lambda values, fid=front.id: self._save_front(fid, values),
            on_revert=self._bind_selected_front,
        )

    def _save_front(self, front_id, values):
        payload = dict(values)
        for key in ("advance_conditions", "retreat_conditions", "stages"):
            payload[key] = _as_list(payload.get(key))
        for key in ("session_ids", "affected_entity_ids"):
            payload[key] = _split_csv(payload.get(key))
        payload["metadata"] = _as_dict(payload.get("metadata"))
        try:
            payload["current_stage_index"] = int(payload.get("current_stage_index") or 0)
        except (TypeError, ValueError):
            payload["current_stage_index"] = 0
        result = self.ctrl.update_front(front_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            raise RuntimeError(result.error)
        self.ctx.log("info", f"Front updated: {front_id}")
        self.refresh()

    def _bind_selected_stage(self):
        ref = self._selected_stage_ref()
        if ref is None:
            return
        front_id, stage_index = ref
        result = self.ctrl.get_front(front_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        front = result.value
        if stage_index < 0 or stage_index >= len(front.stages):
            self.ctx.log("error", "Stage fuera de rango")
            return
        stage = front.stages[stage_index]
        fields = [
            {"name": "name", "label": "Nombre", "value": stage.name},
            {"name": "threshold", "label": "Threshold", "value": stage.threshold},
            {"name": "description", "label": "Descripción", "kind": "multiline", "value": stage.description},
            {"name": "consequences", "label": "Consecuencias JSON", "kind": "json", "value": stage.consequences},
            {"name": "conditions", "label": "Condiciones JSON", "kind": "json", "value": stage.conditions},
            {"name": "is_terminal", "label": "Terminal", "kind": "checkbox", "value": stage.is_terminal},
        ]
        self.inspector.bind(
            title=f"Stage · {stage.name}",
            object_id=f"{front.id}#{stage_index}",
            fields=fields,
            on_save=lambda values, fid=front.id, idx=stage_index: self._save_stage(fid, idx, values),
            on_revert=self._bind_selected_stage,
        )

    def _save_stage(self, front_id, stage_index, values):
        result = self.ctrl.get_front(front_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            raise RuntimeError(result.error)
        front = result.value
        stages = [stage.to_dict() for stage in front.stages]
        if stage_index < 0 or stage_index >= len(stages):
            raise RuntimeError("Stage fuera de rango")
        payload = dict(values)
        payload["consequences"] = _as_list(payload.get("consequences"))
        payload["conditions"] = _as_list(payload.get("conditions"))
        try:
            payload["threshold"] = int(payload.get("threshold") or 0)
        except (TypeError, ValueError):
            payload["threshold"] = 0
        stages[stage_index] = payload
        update = self.ctrl.update_front(front_id, {"stages": stages})
        if isinstance(update, Error):
            self.ctx.log("error", update.error)
            raise RuntimeError(update.error)
        self.ctx.log("info", f"Stage updated: {front_id}#{stage_index}")
        self.refresh()

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
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = CreateFrontForm(self.ctx, self.ctrl, self.refresh)
        drawer.set_content(form, title="Crear front")
        drawer.open()

    def _add_stage(self):
        front_id = self._selected_front_id()
        if not front_id:
            self.ctx.log("error", "Selecciona un front")
            return
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = AddStageForm(self.ctx, self.ctrl, front_id, self.refresh)
        drawer.set_content(form, title="Añadir stage")
        drawer.open()

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
        stage_rows = []
        for i, front in enumerate(fronts):
            id_item = QTableWidgetItem(front.id[:12])
            id_item.setData(Qt.UserRole, front.id)
            self.front_table.setItem(i, 0, id_item)
            self.front_table.setItem(i, 1, QTableWidgetItem(front.name))
            self.front_table.setItem(i, 2, QTableWidgetItem(front.front_type.value if hasattr(front.front_type, "value") else str(front.front_type)))
            self.front_table.setItem(i, 3, QTableWidgetItem(front.state.value if hasattr(front.state, "value") else str(front.state)))
            for idx, stage in enumerate(front.stages):
                stage_rows.append((front, idx, stage))
        self.front_table.resizeColumnsToContents()

        self.stage_table.setRowCount(len(stage_rows))
        for i, (front, idx, stage) in enumerate(stage_rows):
            front_item = QTableWidgetItem(front.id[:12])
            front_item.setData(Qt.UserRole, (front.id, idx))
            self.stage_table.setItem(i, 0, front_item)
            self.stage_table.setItem(i, 1, QTableWidgetItem(str(idx)))
            self.stage_table.setItem(i, 2, QTableWidgetItem(stage.name))
            self.stage_table.setItem(i, 3, QTableWidgetItem(str(stage.threshold)))
            self.stage_table.setItem(i, 4, QTableWidgetItem("yes" if stage.is_terminal else "no"))
        self.stage_table.resizeColumnsToContents()
