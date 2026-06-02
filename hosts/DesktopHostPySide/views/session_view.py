"""SessionView — sessions/scenes basic management (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.session_controller import SessionController
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerForm
from hosts.DesktopHostPySide.widgets.inspector_panel import InspectorPanel
from hosts.DesktopHostPySide.widgets.technical_visibility import set_columns_visible
from packages.domain.result import Error
from packages.domain.session_models import SceneType, SessionState


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


class CreateSessionForm(DrawerForm):
    """Drawer form for creating a new session."""

    def __init__(self, ctx, sc, on_created, parent=None):
        super().__init__(ctx, title="Crear sesión", parent=parent)
        self.sc = sc
        self._on_created = on_created

        self.name_input = QLineEdit()
        self.camp_cb = QComboBox()
        for campaign in getattr(self.sc.ps.active_project, "campaigns", []):
            self.camp_cb.addItem(campaign.name, campaign.id)
        self.form_layout.addRow("Nombre:", self.name_input)
        self.form_layout.addRow("Campaña:", self.camp_cb)

    def _on_accept(self):
        result = self.sc.create({"name": self.name_input.text(), "campaign_id": self.camp_cb.currentData()})
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.selected_session_id = result.value.id
            self.ctx.log("info", f"Session created: {result.value.id}")
            self._close_drawer()
            self._on_created()


class AddSceneForm(DrawerForm):
    """Drawer form for adding a scene to a session."""

    def __init__(self, ctx, sc, session_id, on_added, parent=None):
        super().__init__(ctx, title="Añadir escena", parent=parent)
        self.sc = sc
        self._session_id = session_id
        self._on_added = on_added

        self.name = QLineEdit()
        self.target = QComboBox(); self.target.addItem("planned", "planned"); self.target.addItem("optional", "optional")
        self.scene_type = QComboBox(); self.scene_type.addItems(_enum_values(SceneType))
        self.order = QLineEdit("0")
        self.location_id = QLineEdit()
        self.npc_ids = QLineEdit()
        self.description = QLineEdit()
        self.notes = QLineEdit()
        self.form_layout.addRow("Nombre:", self.name)
        self.form_layout.addRow("Lista:", self.target)
        self.form_layout.addRow("Tipo:", self.scene_type)
        self.form_layout.addRow("Orden:", self.order)
        self.form_layout.addRow("Ubicación:", self.location_id)
        self.form_layout.addRow("PNJs (csv):", self.npc_ids)
        self.form_layout.addRow("Descripción:", self.description)
        self.form_layout.addRow("Notas:", self.notes)

    def _on_accept(self):
        try:
            order_value = int(self.order.text() or "0")
        except ValueError:
            order_value = 0
        result = self.sc.add_scene(self._session_id, {
            "name": self.name.text(),
            "description": self.description.text(),
            "scene_type": self.scene_type.currentText(),
            "order": order_value,
            "location_id": self.location_id.text() or None,
            "npc_ids": _split_csv(self.npc_ids.text()),
            "notes": self.notes.text(),
        }, target=self.target.currentData())
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Scene added: {result.value.id}")
            self._close_drawer()
            self._on_added()


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

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Estado", "Campaña"])
        self.table.itemSelectionChanged.connect(self._select)
        left.addWidget(self.table)

        self.scene_table = QTableWidget()
        self.scene_table.setColumnCount(4)
        self.scene_table.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo", "Orden"])
        self.scene_table.itemSelectionChanged.connect(self._bind_selected_scene)
        left.addWidget(self.scene_table)
        body.addLayout(left, 3)
        self.inspector = InspectorPanel("Session Inspector")
        body.addWidget(self.inspector, 1)
        layout.addLayout(body)
        self.set_advanced_mode(self.ctx.advanced_mode)

    def set_advanced_mode(self, enabled: bool):
        set_columns_visible(self.table, [0], bool(enabled))
        set_columns_visible(self.scene_table, [0], bool(enabled))
        self.inspector.set_advanced_mode(enabled)

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
            self._bind_session(session_id)

    def _session_fields(self, session):
        return [
            {"name": "name", "label": "Nombre", "value": session.name},
            {"name": "campaign_id", "label": "Campaign ID", "value": session.campaign_id},
            {"name": "entity_id", "label": "Entity ID", "value": session.entity_id or ""},
            {"name": "session_number", "label": "Número", "value": session.session_number},
            {"name": "real_date", "label": "Fecha real", "value": session.real_date},
            {"name": "internal_date", "label": "Fecha interna", "value": session.internal_date},
            {"name": "context_summary", "label": "Contexto", "kind": "multiline", "value": session.context_summary},
            {"name": "gm_objectives", "label": "Objetivos GM JSON", "kind": "json", "value": session.gm_objectives},
            {"name": "player_known_objectives", "label": "Objetivos jugadores JSON", "kind": "json", "value": session.player_known_objectives},
            {"name": "planned_scenes", "label": "Escenas previstas JSON", "kind": "json", "value": [s.to_dict() for s in session.planned_scenes]},
            {"name": "optional_scenes", "label": "Escenas opcionales JSON", "kind": "json", "value": [s.to_dict() for s in session.optional_scenes]},
            {"name": "planned_location_ids", "label": "Location IDs (csv)", "value": session.planned_location_ids},
            {"name": "planned_npc_ids", "label": "NPC IDs (csv)", "value": session.planned_npc_ids},
            {"name": "relevant_faction_ids", "label": "Faction IDs (csv)", "value": session.relevant_faction_ids},
            {"name": "active_conflict_ids", "label": "Conflict IDs (csv)", "value": session.active_conflict_ids},
            {"name": "available_clue_ids", "label": "Clue IDs (csv)", "value": session.available_clue_ids},
            {"name": "revealable_secret_ids", "label": "Secret IDs (csv)", "value": session.revealable_secret_ids},
            {"name": "clock_ids", "label": "Clock IDs (csv)", "value": session.clock_ids},
            {"name": "rumors", "label": "Rumores JSON", "kind": "json", "value": session.rumors},
            {"name": "encounters", "label": "Encuentros JSON", "kind": "json", "value": session.encounters},
            {"name": "rewards", "label": "Recompensas JSON", "kind": "json", "value": session.rewards},
            {"name": "complications", "label": "Complicaciones JSON", "kind": "json", "value": session.complications},
            {"name": "expected_consequences", "label": "Consecuencias JSON", "kind": "json", "value": session.expected_consequences},
            {"name": "open_questions", "label": "Preguntas JSON", "kind": "json", "value": session.open_questions},
            {"name": "improvised_material", "label": "Improvisado JSON", "kind": "json", "value": session.improvised_material},
            {"name": "private_notes", "label": "Notas privadas JSON", "kind": "json", "value": session.private_notes},
            {"name": "player_safe_summary", "label": "Resumen jugadores", "kind": "multiline", "value": session.player_safe_summary},
            {"name": "continuity_checklist", "label": "Continuidad JSON", "kind": "json", "value": session.continuity_checklist},
            {"name": "ia_suggestion_candidate_ids", "label": "IA candidate IDs (csv)", "value": session.ia_suggestion_candidate_ids},
            {"name": "state", "label": "Estado", "kind": "combo", "value": session.state, "options": _enum_values(SessionState)},
            {"name": "post_session_summary", "label": "Post-session", "kind": "multiline", "value": session.post_session_summary},
            {"name": "source_id", "label": "Source ID", "value": session.source_id or ""},
            {"name": "metadata", "label": "Metadata JSON", "kind": "json", "value": session.metadata},
        ]

    def _session_payload(self, values):
        payload = dict(values)
        for key in ("planned_location_ids", "planned_npc_ids", "relevant_faction_ids", "active_conflict_ids", "available_clue_ids", "revealable_secret_ids", "clock_ids", "ia_suggestion_candidate_ids"):
            if key in payload:
                payload[key] = _split_csv(payload.get(key))
        for key in ("gm_objectives", "player_known_objectives", "planned_scenes", "optional_scenes", "rumors", "encounters", "rewards", "complications", "expected_consequences", "open_questions", "improvised_material", "private_notes", "continuity_checklist"):
            if key in payload:
                payload[key] = _as_list(payload.get(key))
        if "metadata" in payload:
            payload["metadata"] = _as_dict(payload.get("metadata"))
        if "session_number" in payload:
            try:
                payload["session_number"] = int(payload.get("session_number") or 0)
            except (TypeError, ValueError):
                payload["session_number"] = 0
        return payload

    def _bind_session(self, session_id):
        result = self.sc.get(session_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        session = result.value
        self.inspector.bind(
            title=f"Session · {session.name}",
            object_id=session.id,
            fields=self._session_fields(session),
            on_save=lambda values, sid=session.id: self._save_session(sid, values),
            on_revert=lambda sid=session.id: self._bind_session(sid),
        )

    def _save_session(self, session_id, values):
        result = self.sc.update(session_id, self._session_payload(values))
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            raise RuntimeError(result.error)
        self.ctx.log("info", f"Session updated: {session_id}")
        self.refresh()
        self._select_session_row(session_id)

    def _select_session_row(self, session_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.UserRole) == session_id:
                self.table.selectRow(row)
                return

    def _selected_scene_ref(self):
        row = self.scene_table.currentRow()
        if row < 0:
            return None
        item = self.scene_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _scene_fields(self, scene):
        return [
            {"name": "name", "label": "Nombre", "value": scene.name},
            {"name": "description", "label": "Descripción", "kind": "multiline", "value": scene.description},
            {"name": "scene_type", "label": "Tipo", "kind": "combo", "value": scene.scene_type, "options": _enum_values(SceneType)},
            {"name": "order", "label": "Orden", "value": scene.order},
            {"name": "location_id", "label": "Location ID", "value": scene.location_id or ""},
            {"name": "npc_ids", "label": "NPC IDs (csv)", "value": scene.npc_ids},
            {"name": "notes", "label": "Notas", "kind": "multiline", "value": scene.notes},
        ]

    def _bind_selected_scene(self):
        ref = self._selected_scene_ref()
        session = self._session_obj()
        if ref is None or session is None:
            return
        scene_id, target = ref
        scenes = session.optional_scenes if target == "optional" else session.planned_scenes
        for scene in scenes:
            if scene.id == scene_id:
                self.inspector.bind(
                    title=f"Scene · {scene.name}",
                    object_id=scene.id,
                    fields=self._scene_fields(scene),
                    on_save=lambda values, sid=session.id, scid=scene.id, tgt=target: self._save_scene(sid, scid, tgt, values),
                    on_revert=self._bind_selected_scene,
                )
                return

    def _save_scene(self, session_id, scene_id, target, values):
        result = self.sc.get(session_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            raise RuntimeError(result.error)
        session = result.value
        planned = [scene.to_dict() for scene in session.planned_scenes]
        optional = [scene.to_dict() for scene in session.optional_scenes]
        scenes = optional if target == "optional" else planned
        for idx, scene in enumerate(scenes):
            if scene.get("id") == scene_id:
                payload = dict(values)
                payload["id"] = scene_id
                payload["npc_ids"] = _split_csv(payload.get("npc_ids"))
                try:
                    payload["order"] = int(payload.get("order") or 0)
                except (TypeError, ValueError):
                    payload["order"] = 0
                scenes[idx] = payload
                update = self.sc.update(session_id, {"planned_scenes": planned, "optional_scenes": optional})
                if isinstance(update, Error):
                    self.ctx.log("error", update.error)
                    raise RuntimeError(update.error)
                self.ctx.log("info", f"Scene updated: {scene_id}")
                self.refresh()
                self._select_session_row(session_id)
                return
        raise RuntimeError(f"Scene '{scene_id}' not found")

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
        self.set_advanced_mode(self.ctx.advanced_mode)
        if self.ctx.selected_session_id:
            self._show_scenes()

    def _create(self):
        if not getattr(self.sc.ps.active_project, "campaigns", []):
            self.ctx.log("error", "No hay campañas. Crea una campaña antes de una sesión.")
            return
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = CreateSessionForm(self.ctx, self.sc, self.refresh)
        drawer.set_content(form, title="Crear sesión")
        drawer.open()

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
        for i, (scene, scene_target) in enumerate(scenes):
            id_item = QTableWidgetItem(scene.id[:12])
            id_item.setData(Qt.UserRole, (scene.id, scene_target))
            self.scene_table.setItem(i, 0, id_item)
            self.scene_table.setItem(i, 1, QTableWidgetItem(scene.name))
            self.scene_table.setItem(i, 2, QTableWidgetItem(scene.scene_type.value if hasattr(scene.scene_type, "value") else str(scene.scene_type)))
            self.scene_table.setItem(i, 3, QTableWidgetItem(str(scene.order)))
        self.scene_table.resizeColumnsToContents()
        self.set_advanced_mode(self.ctx.advanced_mode)

    def _add_scene(self):
        sid = self.ctx.selected_session_id
        if not sid:
            self.ctx.log("error", "Selecciona una sesión")
            return
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = AddSceneForm(self.ctx, self.sc, sid, self._show_scenes)
        drawer.set_content(form, title="Añadir escena")
        drawer.open()

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
