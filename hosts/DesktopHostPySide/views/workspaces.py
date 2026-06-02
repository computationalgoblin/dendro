"""Product workspaces for the B27.5 Desktop UX shell.

These wrappers reorganize existing connected views into three product spaces
without deleting functionality. Technical CRUD screens are kept behind advanced
mode while normal mode starts from clean cards/overviews.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget
from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
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
        self.graph.entitySelected.connect(self._open_node_panel)
        self.graph.relationSelected.connect(self._open_relation_panel)

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
        )
        self.ctx.drawer.set_content(panel, title="Relación")
        self.ctx.drawer.open()


class GalleryWorkspace(QWidget):
    """Notion-like clean gallery over existing project data."""

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(22, 22, 22, 22)
        self.grid.setSpacing(14)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(make_scroll_area(self.container))

    def _clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def refresh(self):
        self._clear()
        p = self._project()
        if p is None:
            self.grid.addWidget(EmptyState("Galería", "Abre un proyecto para ver tus elementos como tarjetas."), 0, 0)
            return
        self.grid.addWidget(SectionHeader("Galería", "Vista limpia de entidades, campañas, facciones y sesiones."), 0, 0, 1, 3)
        cards = []
        for entity in getattr(p, "entities", []) or []:
            kind = enum_human(getattr(entity, "entity_type", "Entidad"))
            cards.append((human_ref(getattr(entity, "name", ""), kind), getattr(entity, "brief", "") or getattr(entity, "description", ""), kind))
        for campaign in getattr(p, "campaigns", []) or []:
            cards.append((human_ref(getattr(campaign, "name", ""), "Campaña"), getattr(campaign, "description", ""), "Campaña"))
        for faction in getattr(p, "factions", []) or []:
            cards.append((human_ref(getattr(faction, "name", ""), "Facción"), getattr(faction, "description", ""), "Facción"))
        for session in getattr(p, "sessions", []) or []:
            cards.append((human_ref(getattr(session, "name", ""), "Sesión"), getattr(session, "context_summary", ""), "Sesión"))
        if not cards:
            self.grid.addWidget(EmptyState("Sin elementos", "Crea nodos, campañas o sesiones para verlos aquí."), 1, 0)
            return
        for idx, (title, subtitle, badge) in enumerate(cards):
            card = Card(title, subtitle or "Sin descripción breve")
            row = card.add_row()
            row.addWidget(Badge(badge, "info"))
            row.addStretch()
            self.grid.addWidget(card, 1 + idx // 3, idx % 3)

    def set_advanced_mode(self, enabled: bool):
        return


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
        return


class SessionOverview(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.container = QWidget()
        self.layout_cards = QVBoxLayout(self.container)
        self.layout_cards.setContentsMargins(22, 22, 22, 22)
        self.layout_cards.setSpacing(14)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(make_scroll_area(self.container))

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _clear(self):
        while self.layout_cards.count():
            item = self.layout_cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh(self):
        self._clear()
        p = self._project()
        self.layout_cards.addWidget(SectionHeader(
            "Sesión",
            "Flujo dividido en Campaña, Preparación y En vivo/Post para evitar saturación."
        ))
        if p is None:
            self.layout_cards.addWidget(EmptyState("Sin proyecto", "Abre un proyecto desde Configuración."))
            self.layout_cards.addStretch()
            return
        summary = [
            ("Campañas", len(getattr(p, "campaigns", []) or []), "info"),
            ("Sesiones", len(getattr(p, "sessions", []) or []), "info"),
            ("Facciones", len(getattr(p, "factions", []) or []), "warning"),
            ("Frentes", len(getattr(p, "fronts", []) or []), "warning"),
            ("Clocks", len(getattr(p, "campaign_clocks", []) or []), "success"),
            ("Pistas", len(getattr(p, "clues", []) or []), "success"),
            ("Secretos", len(getattr(p, "secrets", []) or []), "danger"),
        ]
        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setSpacing(12)
        for idx, (title, count, tone) in enumerate(summary):
            card = Card(title, f"{count} elementos")
            row = card.add_row()
            row.addWidget(Badge(str(count), tone))
            row.addStretch()
            grid.addWidget(card, idx // 3, idx % 3)
        self.layout_cards.addWidget(grid_container)
        self.layout_cards.addStretch()
