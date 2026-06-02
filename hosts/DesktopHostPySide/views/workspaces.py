"""Product workspaces for the B27.5 Desktop UX shell.

These wrappers reorganize existing connected views into three product spaces
without deleting functionality. Technical CRUD screens are kept behind advanced
mode while normal mode starts from clean cards/overviews.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.ai_context_controller import AIContextController
from hosts.DesktopHostPySide.widgets.entity_card import EntityCard
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget
from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
from hosts.DesktopHostPySide.widgets.relation_create_panel import RelationCreatePanel
from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    Card,
    EmptyState,
    SectionHeader,
    enum_human,
    human_ref,
    make_scroll_area,
)
from packages.domain.result import Error


class CreationWorkspace(QTabWidget):
    """Creation space: graph-first normal entry, technical tools in advanced tabs."""

    def __init__(self, ctx: AppContext, *, corpus_view, relation_view, candidate_view,
                 import_export_view, writing_view, timeline_view, framework_view,
                 source_view=None, layer_view=None):
        super().__init__()
        self.ctx = ctx
        self.graph = GraphCanvasWidget(ctx)
        self.import_export_view = import_export_view
        self.writing_view = writing_view
        self.timeline_view = timeline_view
        self.framework_view = framework_view
        self.corpus_view = corpus_view
        self.relation_view = relation_view
        self.candidate_view = candidate_view
        self.source_view = source_view
        self.layer_view = layer_view
        self.entity_controller = getattr(corpus_view, "ec", None)
        self.relation_controller = getattr(relation_view, "rc", None)
        self.ai_context_controller = None
        project_controller = getattr(ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is not None:
            self.ai_context_controller = AIContextController(project_service)
        self.graph.set_ai_controller(self.ai_context_controller)
        self.graph.entitySelected.connect(self._open_node_panel)
        self.graph.relationSelected.connect(self._open_relation_panel)
        self.graph.relationCreateRequested.connect(self._open_relation_create_panel)

        self.addTab(self.graph, "Grafo")
        self.addTab(self.import_export_view, "Importación")
        self.addTab(self.writing_view, "Escritura")
        self.addTab(self.timeline_view, "Timeline")
        self.addTab(self.framework_view, "Frameworks")
        self._advanced_tab_indexes = []
        for title, widget in [
            ("Corpus técnico", self.corpus_view),
            ("Relaciones técnicas", self.relation_view),
            ("Candidatos técnicos", self.candidate_view),
        ]:
            self.addTab(widget, title)
            self._advanced_tab_indexes.append(self.count() - 1)
        # Optional advanced-only views
        if self.source_view is not None:
            self.addTab(self.source_view, "Fuentes")
            self._advanced_tab_indexes.append(self.count() - 1)
        if self.layer_view is not None:
            self.addTab(self.layer_view, "Capas")
            self._advanced_tab_indexes.append(self.count() - 1)
        self.set_advanced_mode(ctx.advanced_mode)

    def set_advanced_mode(self, enabled: bool):
        for idx in self._advanced_tab_indexes:
            if hasattr(self, "setTabVisible"):
                self.setTabVisible(idx, enabled)
        for widget in [self.import_export_view, self.graph]:
            if hasattr(widget, "set_advanced_mode"):
                widget.set_advanced_mode(enabled)

    def refresh(self):
        for widget in [self.graph, self.import_export_view, self.writing_view, self.timeline_view,
                       self.framework_view, self.corpus_view, self.relation_view, self.candidate_view,
                       self.source_view, self.layer_view]:
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()

    def _open_node_panel(self, entity_id: str):
        if self.entity_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de nodo")
            return
        panel = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            entity_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
        )
        self.ctx.drawer.set_content(panel, title="Nodo")
        self.ctx.drawer.open()

    def _open_relation_panel(self, relation_id: str):
        if self.relation_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de relación")
            return
        panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
        )
        self.ctx.drawer.set_content(panel, title="Relación")
        self.ctx.drawer.open()

    def _entity_by_id(self, entity_id: str):
        pc = self.ctx.project_controller
        project = pc.ps.active_project if pc else None
        if project is None:
            return None
        for entity in getattr(project, "entities", []) or []:
            if getattr(entity, "id", None) == entity_id:
                return entity
        return None

    def _entity_label(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return "Entidad no encontrada"
        kind = getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "entidad"))
        return human_ref(getattr(entity, "name", "Sin nombre"), enum_human(str(kind)))

    def _relation_exists(self, source_id: str, target_id: str) -> bool:
        if self.relation_controller is None:
            return False
        for relation in self.relation_controller.list_all():
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if (src, tgt) == (source_id, target_id) or (src, tgt) == (target_id, source_id):
                return True
        return False

    def _open_relation_create_panel(self, source_id: str, target_id: str):
        controller = self.relation_controller
        drawer = self.ctx.drawer
        if controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear relación: servicio no disponible")
            return
        if source_id == target_id:
            self.ctx.log("error", "No se puede crear una relación sobre la misma entidad")
            return
        if self._relation_exists(source_id, target_id):
            self.ctx.log("error", "Ya existe una relación entre esas entidades")
            return

        def create_relation(relation_type: str, description: str):
            result = controller.create(
                source_id,
                target_id,
                relation_type,
                {"description": description} if description else {},
            )
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
                return
            relation = result.value
            relation_id = getattr(relation, "id", "")
            self.ctx.log("info", "Relación creada desde el grafo")
            self.refresh()
            if relation_id:
                self._open_relation_panel(relation_id)

        panel = RelationCreatePanel(
            self._entity_label(source_id),
            self._entity_label(target_id),
            on_create=create_relation,
            on_cancel=drawer.close,
        )
        drawer.set_content(panel, title="Crear relación")
        drawer.open()


class GalleryWorkspace(QWidget):
    """Immersive gallery of narrative material."""

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(22, 22, 22, 22)
        self.grid.setSpacing(14)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Galería",
            "Explora tu material narrativo en tarjetas limpias, sin datos técnicos en modo normal."
        ))
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, tipo o descripción…")
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search, 2)
        self.kind_filter = QComboBox()
        self.kind_filter.addItems(["Todo", "Entidades", "Campañas", "Sesiones", "Facciones", "Secretos/Pistas"])
        self.kind_filter.currentTextChanged.connect(self.refresh)
        filters.addWidget(self.kind_filter)
        self.group_filter = QComboBox()
        self.group_filter.addItems(["Sin agrupar", "Agrupar por tipo", "Agrupar por estado"])
        self.group_filter.currentTextChanged.connect(self.refresh)
        filters.addWidget(self.group_filter)
        self.toggle_filters = QPushButton("Filtros")
        self.toggle_filters.clicked.connect(self._toggle_filters)
        filters.addWidget(self.toggle_filters)
        header_layout.addLayout(filters)
        self.filters_hint = QLabel("Secretos y pistas solo se muestran para perfil GM. IDs y JSON permanecen ocultos en modo normal.")
        self.filters_hint.setObjectName("mutedLabel")
        self.filters_hint.setWordWrap(True)
        self.filters_hint.hide()
        header_layout.addWidget(self.filters_hint)
        layout.addWidget(header)
        layout.addWidget(make_scroll_area(self.container), 1)

    def _clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _toggle_filters(self):
        self.filters_hint.setVisible(not self.filters_hint.isVisible())

    def _is_gm(self) -> bool:
        return str(getattr(self.ctx, "current_audience", "gm") or "gm").lower() == "gm"

    def _entity_relations(self, project, entity_id: str) -> str:
        names = []
        for relation in getattr(project, "relations", []) or []:
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if entity_id not in {src, tgt}:
                continue
            other_id = tgt if src == entity_id else src
            for entity in getattr(project, "entities", []) or []:
                if getattr(entity, "id", "") == other_id:
                    names.append(getattr(entity, "name", "Entidad"))
                    break
            if len(names) >= 2:
                break
        return "Relaciones: " + ", ".join(names) if names else "Sin relaciones destacadas"

    def _items(self, project) -> list[dict]:
        items: list[dict] = []
        for entity in getattr(project, "entities", []) or []:
            kind_key = str(getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "entidad")))
            visibility = str(getattr(getattr(entity, "visibility_state", None), "value", getattr(entity, "visibility_state", "")))
            if not self._is_gm() and visibility in {"secreto_mundo", "privado_gm", "oculto"}:
                continue
            canon = str(getattr(getattr(entity, "canon_state", None), "value", getattr(entity, "canon_state", "")))
            items.append({
                "id": getattr(entity, "id", ""),
                "source": entity,
                "source_type": "entity",
                "title": getattr(entity, "name", "Sin nombre"),
                "kind": enum_human(kind_key),
                "kind_key": kind_key,
                "subtitle": getattr(entity, "brief_description", "") or getattr(entity, "brief", "") or getattr(entity, "description", ""),
                "symbol": "◆",
                "badges": [(enum_human(canon or "canon"), "success"), (enum_human(visibility or "visible"), "info")],
                "relation_summary": self._entity_relations(project, getattr(entity, "id", "")),
                "group_type": enum_human(kind_key),
                "group_state": enum_human(canon or "canon"),
            })
        for campaign in getattr(project, "campaigns", []) or []:
            items.append({
                "id": getattr(campaign, "id", ""),
                "source": campaign,
                "source_type": "campaign",
                "title": getattr(campaign, "name", "Sin campaña"),
                "kind": "Campaña",
                "kind_key": "campaña",
                "subtitle": getattr(campaign, "description", "") or "Campaña narrativa",
                "symbol": "◎",
                "badges": [("Campaña", "info")],
                "relation_summary": f"Sesiones: {len(getattr(campaign, 'session_ids', []) or [])}",
                "group_type": "Campaña",
                "group_state": "Campaña",
            })
        for faction in getattr(project, "factions", []) or []:
            items.append({
                "id": getattr(faction, "id", ""),
                "source": faction,
                "source_type": "faction",
                "title": getattr(faction, "name", "Sin facción"),
                "kind": "Facción",
                "kind_key": "faccion",
                "subtitle": getattr(faction, "description", "") or "Facción del mundo",
                "symbol": "◈",
                "badges": [("Facción", "warning")],
                "relation_summary": f"Aliados/enemigos: {len(getattr(faction, 'ally_faction_ids', []) or [])}/{len(getattr(faction, 'enemy_faction_ids', []) or [])}",
                "group_type": "Facción",
                "group_state": "Facción",
            })
        for session in getattr(project, "sessions", []) or []:
            items.append({
                "id": getattr(session, "id", ""),
                "source": session,
                "source_type": "session",
                "title": getattr(session, "title", "") or getattr(session, "name", "Sesión"),
                "kind": "Sesión",
                "kind_key": "sesión",
                "subtitle": getattr(session, "context_summary", "") or getattr(session, "summary", "") or "Sesión preparada",
                "symbol": "◌",
                "badges": [("Sesión", "info")],
                "relation_summary": f"Escenas: {len(getattr(session, 'scenes', []) or [])}",
                "group_type": "Sesión",
                "group_state": "Sesión",
            })
        if self._is_gm():
            for secret in getattr(project, "secrets", []) or []:
                items.append({
                    "id": getattr(secret, "id", ""),
                    "source": secret,
                    "source_type": "secret",
                    "title": getattr(secret, "title", "") or "Secreto",
                    "kind": "Secreto",
                    "kind_key": "secreto",
                    "subtitle": getattr(secret, "content", "") or getattr(secret, "description", "") or "Secreto narrativo",
                    "symbol": "✦",
                    "badges": [("GM", "danger")],
                    "relation_summary": "Visible solo para dirección",
                    "group_type": "Secretos/Pistas",
                    "group_state": "GM",
                })
            for clue in getattr(project, "clues", []) or []:
                items.append({
                    "id": getattr(clue, "id", ""),
                    "source": clue,
                    "source_type": "clue",
                    "title": getattr(clue, "title", "") or "Pista",
                    "kind": "Pista",
                    "kind_key": "pista",
                    "subtitle": getattr(clue, "content", "") or getattr(clue, "description", "") or "Pista narrativa",
                    "symbol": "✧",
                    "badges": [("GM", "success")],
                    "relation_summary": "Revelación controlada",
                    "group_type": "Secretos/Pistas",
                    "group_state": "GM",
                })
        return items

    def _filtered_items(self, items: list[dict]) -> list[dict]:
        text = self.search.text().strip().lower()
        kind_filter = self.kind_filter.currentText()
        def matches(item: dict) -> bool:
            haystack = " ".join(str(item.get(key, "")) for key in ["title", "kind", "subtitle", "relation_summary"]).lower()
            if text and text not in haystack:
                return False
            source_type = item.get("source_type")
            if kind_filter == "Entidades" and source_type != "entity":
                return False
            if kind_filter == "Campañas" and source_type != "campaign":
                return False
            if kind_filter == "Sesiones" and source_type != "session":
                return False
            if kind_filter == "Facciones" and source_type != "faction":
                return False
            if kind_filter == "Secretos/Pistas" and source_type not in {"secret", "clue"}:
                return False
            return True
        return [item for item in items if matches(item)]

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.grid.addWidget(EmptyState("Galería", "Abre un proyecto para ver tus elementos como tarjetas."), 0, 0)
            return
        items = self._filtered_items(self._items(project))
        if not items:
            self.grid.addWidget(EmptyState("Sin elementos", "Crea contenido o ajusta búsqueda/filtros para poblar esta galería."), 0, 0)
            return
        group_mode = self.group_filter.currentText()
        row = 0
        col = 0
        current_group = None
        for item in sorted(items, key=lambda x: (x.get("group_type", ""), x.get("title", ""))):
            group = ""
            if group_mode == "Agrupar por tipo":
                group = str(item.get("group_type") or item.get("kind") or "Elementos")
            elif group_mode == "Agrupar por estado":
                group = str(item.get("group_state") or "Estado")
            if group and group != current_group:
                current_group = group
                col = 0
                if row > 0:
                    row += 1
                self.grid.addWidget(SectionHeader(group, ""), row, 0, 1, 3)
                row += 1
            card = EntityCard(item)
            card.clicked.connect(self._open_detail)
            self.grid.addWidget(card, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

    def _open_detail(self, item: dict):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de galería")
            return
        detail = QWidget()
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        layout.addWidget(SectionHeader(str(item.get("title") or "Detalle"), str(item.get("kind") or "Elemento")))
        layout.addWidget(QLabel(str(item.get("subtitle") or "Sin descripción breve")))
        layout.addWidget(QLabel(str(item.get("relation_summary") or "")))
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {item.get('id', '')}\nTipo fuente: {item.get('source_type', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(detail, title="Detalle")
        self.ctx.drawer.open()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()


class SessionWorkspace(QTabWidget):
    """Session space divided into Campaña, Preparación and En vivo/Post."""

    def __init__(self, ctx: AppContext, *, campaign_view, faction_view, session_view,
                 live_post_view, secrets_view, issues_view=None):
        super().__init__()
        self.ctx = ctx
        self.overview = SessionOverview(ctx)
        self.campaign_view = campaign_view
        self.faction_view = faction_view
        self.session_view = session_view
        self.live_post_view = live_post_view
        self.secrets_view = secrets_view
        self.issues_view = issues_view
        self.addTab(self.overview, "Resumen")
        self.addTab(self.campaign_view, "Campaña")
        self.addTab(self.session_view, "Preparación")
        self.addTab(self.faction_view, "Facciones/Frentes")
        self.addTab(self.secrets_view, "Secretos/Pistas")
        self.addTab(self.live_post_view, "En vivo/Post")
        if self.issues_view is not None:
            self.addTab(self.issues_view, "Incidencias")

    def refresh(self):
        for widget in [self.overview, self.campaign_view, self.session_view, self.faction_view,
                       self.secrets_view, self.live_post_view, self.issues_view]:
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()

    def set_advanced_mode(self, enabled: bool):
        if hasattr(self.overview, "set_advanced_mode"):
            self.overview.set_advanced_mode(enabled)


class SessionOverview(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.selected_campaign_id: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Sesión",
            "Estado de campaña para dirigir: relojes, frentes y facciones en una sola superficie tranquila."
        ))
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Campaña:"))
        self.campaign_selector = QComboBox()
        self.campaign_selector.currentIndexChanged.connect(self._campaign_changed)
        controls.addWidget(self.campaign_selector, 1)
        self.status_label = QLabel("Sin campaña")
        self.status_label.setObjectName("mutedLabel")
        controls.addWidget(self.status_label)
        header_layout.addLayout(controls)
        root.addWidget(header)

        self.container = QWidget()
        self.layout_cards = QVBoxLayout(self.container)
        self.layout_cards.setContentsMargins(22, 22, 22, 22)
        self.layout_cards.setSpacing(14)
        root.addWidget(make_scroll_area(self.container), 1)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _clear(self):
        while self.layout_cards.count():
            item = self.layout_cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _campaign_changed(self):
        self.selected_campaign_id = self.campaign_selector.currentData()
        self.refresh()

    def _campaigns(self, project):
        return list(getattr(project, "campaigns", []) or [])

    def _selected_campaign(self, project):
        campaigns = self._campaigns(project)
        if not campaigns:
            return None
        if self.selected_campaign_id:
            for campaign in campaigns:
                if getattr(campaign, "id", "") == self.selected_campaign_id:
                    return campaign
        self.selected_campaign_id = getattr(campaigns[0], "id", "")
        return campaigns[0]

    def _populate_campaign_selector(self, project):
        campaigns = self._campaigns(project)
        current = self.selected_campaign_id
        self.campaign_selector.blockSignals(True)
        self.campaign_selector.clear()
        for campaign in campaigns:
            self.campaign_selector.addItem(getattr(campaign, "name", "Campaña"), getattr(campaign, "id", ""))
        if current:
            idx = self.campaign_selector.findData(current)
            if idx >= 0:
                self.campaign_selector.setCurrentIndex(idx)
        self.campaign_selector.blockSignals(False)

    def _clocks_for_campaign(self, project, campaign):
        ids = set(getattr(campaign, "clock_ids", []) or [])
        clocks = list(getattr(project, "campaign_clocks", []) or [])
        return [clock for clock in clocks if not ids or getattr(clock, "id", "") in ids]

    def _fronts_for_campaign(self, project, campaign):
        campaign_clock_ids = set(getattr(campaign, "clock_ids", []) or [])
        campaign_sessions = set(getattr(campaign, "session_ids", []) or [])
        fronts = []
        for front in getattr(project, "fronts", []) or []:
            if getattr(front, "clock_id", None) in campaign_clock_ids:
                fronts.append(front)
                continue
            if campaign_sessions and set(getattr(front, "session_ids", []) or []) & campaign_sessions:
                fronts.append(front)
        return fronts or list(getattr(project, "fronts", []) or [])

    def _factions_for_campaign(self, project, campaign):
        active_entities = set(getattr(campaign, "active_faction_entity_ids", []) or [])
        factions = []
        for faction in getattr(project, "factions", []) or []:
            if not active_entities or getattr(faction, "entity_id", "") in active_entities or getattr(faction, "id", "") in active_entities:
                factions.append(faction)
        return factions

    def _progress_card(self, clock):
        current = max(0, int(getattr(clock, "current_value", 0) or 0))
        max_value = max(1, int(getattr(clock, "max_value", 1) or 1))
        card = Card(getattr(clock, "name", "Clock"), getattr(clock, "description", "") or "Reloj de campaña")
        row = card.add_row()
        row.addWidget(Badge(enum_human(str(getattr(getattr(clock, "state", None), "value", getattr(clock, "state", "activo")))), "warning"))
        row.addStretch()
        bar = QProgressBar()
        bar.setRange(0, max_value)
        bar.setValue(min(current, max_value))
        bar.setFormat(f"{current}/{max_value}")
        card.layout().addWidget(bar)
        btn_row = card.add_row()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._open_detail("Clock", clock, [
            ("Estado", enum_human(str(getattr(getattr(clock, "state", None), "value", getattr(clock, "state", ""))))),
            ("Progreso", f"{current}/{max_value}"),
            ("Condiciones de avance", ", ".join(getattr(clock, "advance_conditions", []) or []) or "—"),
        ]))
        btn_row.addStretch()
        btn_row.addWidget(btn)
        return card

    def _simple_card(self, title: str, subtitle: str, badge: str, tone: str, obj, details: list[tuple[str, str]]):
        card = Card(title, subtitle or "Sin descripción")
        row = card.add_row()
        row.addWidget(Badge(badge, tone))
        row.addStretch()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._open_detail(badge, obj, details))
        row.addWidget(btn)
        return card

    def _open_detail(self, title: str, obj, details: list[tuple[str, str]]):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de sesión")
            return
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        name = getattr(obj, "name", title)
        layout.addWidget(SectionHeader(str(name), title))
        description = getattr(obj, "description", "") or getattr(obj, "relation_with_pcs", "") or "Sin descripción"
        desc = QLabel(str(description))
        desc.setWordWrap(True)
        layout.addWidget(desc)
        for label, value in details:
            row = QHBoxLayout()
            left = QLabel(label)
            left.setObjectName("mutedLabel")
            row.addWidget(left)
            value_label = QLabel(value or "—")
            value_label.setWordWrap(True)
            row.addWidget(value_label, 1)
            layout.addLayout(row)
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {getattr(obj, 'id', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(panel, title="Sesión")
        self.ctx.drawer.open()

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.campaign_selector.clear()
            self.status_label.setText("Sin proyecto")
            self.layout_cards.addWidget(EmptyState("Sin proyecto", "Abre un proyecto desde Configuración."))
            self.layout_cards.addStretch()
            return
        self._populate_campaign_selector(project)
        campaign = self._selected_campaign(project)
        if campaign is None:
            self.status_label.setText("Sin campañas")
            self.layout_cards.addWidget(EmptyState("Sin campañas", "Crea una campaña para preparar sesiones."))
            self.layout_cards.addStretch()
            return
        self.status_label.setText(enum_human(str(getattr(getattr(campaign, "state", None), "value", getattr(campaign, "state", "activa")))))
        summary = Card(getattr(campaign, "name", "Campaña"), getattr(campaign, "description", "") or "Campaña activa")
        row = summary.add_row()
        for label, value, tone in [
            ("Sistema", getattr(campaign, "game_system", "") or "—", "info"),
            ("Tono", getattr(campaign, "tone", "") or "—", "info"),
            ("Sesiones", str(len(getattr(campaign, "session_ids", []) or [])), "success"),
            ("Jugadores", str(len(getattr(campaign, "players", []) or [])), "success"),
        ]:
            row.addWidget(Badge(f"{label}: {value}", tone))
        row.addStretch()
        detail_row = summary.add_row()
        detail_btn = QPushButton("Detalle campaña")
        detail_btn.clicked.connect(lambda: self._open_detail("Campaña", campaign, [
            ("Sistema", getattr(campaign, "game_system", "") or "—"),
            ("Tono", getattr(campaign, "tone", "") or "—"),
            ("Género", getattr(campaign, "genre", "") or "—"),
        ]))
        detail_row.addStretch()
        detail_row.addWidget(detail_btn)
        self.layout_cards.addWidget(summary)

        clocks = self._clocks_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Clocks", "Progreso visual de amenazas, frentes y cuenta atrás."))
        if clocks:
            for clock in clocks:
                self.layout_cards.addWidget(self._progress_card(clock))
        else:
            self.layout_cards.addWidget(EmptyState("Sin clocks", "No hay relojes asociados a esta campaña."))

        fronts = self._fronts_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Frentes activos", "Procesos dinámicos y amenazas de la campaña."))
        if fronts:
            for front in fronts:
                stage = getattr(front, "current_stage_index", 0)
                stages = getattr(front, "stages", []) or []
                subtitle = getattr(front, "description", "") or (stages[stage].description if stages and stage < len(stages) else "Frente narrativo")
                self.layout_cards.addWidget(self._simple_card(
                    getattr(front, "name", "Frente"),
                    subtitle,
                    enum_human(str(getattr(getattr(front, "state", None), "value", getattr(front, "state", "latente")))),
                    "warning",
                    front,
                    [("Etapa", f"{stage + 1}/{len(stages) or 1}"), ("Tipo", enum_human(str(getattr(getattr(front, "front_type", None), "value", getattr(front, "front_type", "frente")))))]
                ))
        else:
            self.layout_cards.addWidget(EmptyState("Sin frentes", "No hay frentes activos para esta campaña."))

        factions = self._factions_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Facciones", "Actores activos y relaciones de presión."))
        if factions:
            for faction in factions:
                self.layout_cards.addWidget(self._simple_card(
                    getattr(faction, "name", "Facción"),
                    getattr(faction, "relation_with_pcs", "") or getattr(faction, "ideology", "") or "Facción activa",
                    enum_human(str(getattr(getattr(faction, "state", None), "value", getattr(faction, "state", "activa")))),
                    "info",
                    faction,
                    [("Aliados", str(len(getattr(faction, "ally_faction_ids", []) or []))), ("Enemigos", str(len(getattr(faction, "enemy_faction_ids", []) or []))), ("Recursos", ", ".join(getattr(faction, "resources", []) or []) or "—")]
                ))
        else:
            self.layout_cards.addWidget(EmptyState("Sin facciones", "No hay facciones activas vinculadas."))

        self.layout_cards.addWidget(SectionHeader("Siguientes zonas", "Preparación/escenas y Live/Post se completan en T10B/T10C."))
        self.layout_cards.addWidget(EmptyState("Preparación y Live/Post", "Placeholder deliberado de T10A; se implementa en los tickets siguientes."))
        self.layout_cards.addStretch()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()
