"""FocoView: composición del Modo Foco (BETA2-FOCO-08).

Vista PRINCIPAL de Creación: lienzo de zonas (FocoCanvas) + tarjeta central de
la entidad en foco superpuesta como widget real (patrón de overlays de la
casa). En este ticket la tarjeta es un resumen compacto; el formulario completo
con autosave llega en FOCO-09 y la sustituye en el mismo hueco.

Estado que NO se persiste: historial de foco (atrás) e ids resaltadas — solo en
memoria (decisión de producto). Lo ÚNICO persistido es la última entidad
trabajada, vía servicio de aplicación (``ProjectService.set_last_worked_entity``).
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_SOFT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    RADIUS_LG,
    SURFACE_HI,
    EmptyState,
)
from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoCanvas
from hosts.DesktopHostPySide.widgets.foco.foco_lifeline import FocoLifelineBand
from hosts.DesktopHostPySide.widgets.foco.foco_popover import (
    EntitySearchPopover,
    QuickCreatePopover,
)
from hosts.DesktopHostPySide.widgets.foco.foco_tool_rail import FocoToolRail
from packages.application.foco_zones import classify_neighbors
from packages.domain.result import Error

# Tipos de entidad que cuentan como "rama" para el popover Añadir a rama.
_BRANCH_TYPES = {
    "contenedor",
    "faccion",
    "cultura",
    "sistema_magico",
    "religion",
    "institucion",
    "trama",
}

_HISTORY_LIMIT = 50


class FocoView(QWidget):
    """Escritorio causal: una entidad al centro, su jardín alrededor."""

    entityCentered = Signal(str)  # noqa: N815 — convención Qt de señales
    openInMapRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    openInChronoRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # FOCO-10: re-emisión de la banda local con las MISMAS firmas que la
    # cronología global — el workspace reutiliza sus slots de persistencia.
    lifespanEdited = Signal(str, int, object)  # noqa: N815 — convención Qt de señales
    milestoneCreateRequested = Signal(int, str)  # noqa: N815 — convención Qt de señales
    # FOCO-11: el riego lo orquesta el workspace (autorización + drawer, FOCO-12).
    waterRequested = Signal(list)  # noqa: N815 — ids a regar (selección o centro)
    dryRequested = Signal(str)  # noqa: N815 — Secar (sin IA)
    cultivateRequested = Signal(str)  # noqa: N815 — Cultivar (sin IA)
    # FOCO-13: click en una Semilla de zona ⇒ revisión (flujo humano existente).
    seedReviewRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # FOCO-19: toda mutación hecha desde Foco (crear/relacionar/fantasma/
    # convertir/vincular/editar formulario) avisa al workspace para que el
    # Mapa se reconstruya al entrar (antes quedaba desactualizado).
    dataChanged = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(
        self,
        *,
        project_provider: Callable[[], Any],
        last_entity_getter: Callable[[], str] | None = None,
        last_entity_setter: Callable[[str], Any] | None = None,
        ctx: Any = None,
        entity_controller: Any = None,
        relation_controller: Any = None,
        milestone_controller: Any = None,
        watering_service: Any = None,
        ghost_service: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_provider = project_provider
        self._last_entity_getter = last_entity_getter
        self._last_entity_setter = last_entity_setter
        # FOCO-09: con ctx + entity_controller el centro embebe el FORMULARIO
        # real (NodeDetailPanel variant="foco", autosave 800 ms); sin ellos se
        # muestra la tarjeta-resumen (tests/consumidores ligeros).
        self.ctx = ctx
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.milestone_controller = milestone_controller
        self.watering_service = watering_service
        self.ghost_service = ghost_service
        self._center_id = ""
        self._history: list[str] = []
        self._form_panel: Any = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.canvas = FocoCanvas(self)
        layout.addWidget(self.canvas, 1)
        self.canvas.satelliteActivated.connect(self.center_entity)
        self.canvas.seedClicked.connect(self.seedReviewRequested)

        # FOCO-11: rail izquierdo de herramientas (columna única de iconos).
        self.tool_rail = FocoToolRail(self)
        self.tool_rail.toolTriggered.connect(self._on_tool)
        self.canvas.selectionChanged.connect(lambda _ids: self._refresh_tool_context())
        self._popover: Any = None  # referencia viva del popover abierto

        self._center_card = self._build_center_card()
        self._adjacent_card = self._build_adjacent_card()
        self._empty = EmptyState(
            "Crea tu primera entidad",
            "El jardín está vacío. Planta la primera entidad con la herramienta "
            "de creación y empieza a cultivarla.",
        )
        self._empty.setParent(self)
        self._empty.hide()

    # ------------------------------------------------------------------
    # Tarjeta central (resumen; FOCO-09 la sustituye por el formulario real)
    # ------------------------------------------------------------------

    def _build_center_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("focoCenterCard")
        card.setStyleSheet(
            f"QFrame#focoCenterCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: {RADIUS_LG}px; }}"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(14)
        outer.addLayout(row, 1)
        # FOCO-10: cronología LOCAL bajo el editor, mismo ancho que el formulario.
        self.lifeline = FocoLifelineBand(card)
        self.lifeline.lifespanEdited.connect(self._on_lifeline_span_edited)
        self.lifeline.milestoneCreateRequested.connect(self.milestoneCreateRequested)
        self.lifeline.milestoneActivated.connect(self._open_milestone_adjacent)
        self.lifeline.hide()
        outer.addWidget(self.lifeline)

        self._image_placeholder = QFrame(card)
        self._image_placeholder.setFixedSize(84, 84)
        self._image_placeholder.setStyleSheet(
            f"QFrame {{ border: 1px dashed {LINE_SOFT}; border-radius: 12px; "
            "background: rgba(255,255,255,0.4); }}"
        )
        row.addWidget(self._image_placeholder, 0, Qt.AlignmentFlag.AlignTop)

        column = QVBoxLayout()
        column.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(8)
        self._back_button = QPushButton("◀", card)
        self._back_button.setToolTip("Volver al foco anterior")
        self._back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_button.setFixedSize(26, 26)
        self._back_button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {LINE_SOFT}; border-radius: 13px; "
            f"background: transparent; color: {INK_SOFT}; }}"
            "QPushButton:hover { background: rgba(255,255,255,0.6); }"
        )
        self._back_button.clicked.connect(self.go_back)
        self._back_button.setVisible(False)
        header.addWidget(self._back_button, 0)
        self._name_label = QLabel("", card)
        self._name_label.setStyleSheet(
            f"color: {INK_STRONG}; font-family: Georgia, serif; "
            "font-size: 17px; font-weight: 700; border: none; background: transparent;"
        )
        header.addWidget(self._name_label, 1)
        column.addLayout(header)
        self._type_label = QLabel("", card)
        self._type_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; border: none; background: transparent;"
        )
        column.addWidget(self._type_label)
        self._brief_label = QLabel("", card)
        self._brief_label.setWordWrap(True)
        self._brief_label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: 12px; border: none; background: transparent;"
        )
        column.addWidget(self._brief_label, 1)
        row.addLayout(column, 1)
        # FOCO-09: hueco del formulario real (NodeDetailPanel), en scroll para
        # que el editor completo quepa en el centro del lienzo.
        self._form_scroll = QScrollArea(card)
        self._form_scroll.setWidgetResizable(True)
        self._form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._form_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._form_scroll.hide()
        row.addWidget(self._form_scroll, 2)
        card.hide()
        return card

    def _build_adjacent_card(self) -> QFrame:
        """Panel ADYACENTE al formulario (relación/hito) — decisión de producto:
        estos editores no van al drawer derecho (reservado al riego)."""
        card = QFrame(self)
        card.setObjectName("focoAdjacentCard")
        card.setStyleSheet(
            f"QFrame#focoAdjacentCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {LINE_SOFT}; border-radius: {RADIUS_LG}px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(6)
        header = QHBoxLayout()
        self._adjacent_title = QLabel("", card)
        self._adjacent_title.setStyleSheet(
            f"color: {INK_STRONG}; font-weight: 700; font-size: 13px; "
            "border: none; background: transparent;"
        )
        header.addWidget(self._adjacent_title, 1)
        close_button = QPushButton("✕", card)
        close_button.setFixedSize(24, 24)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {LINE_SOFT}; border-radius: 12px; "
            f"background: transparent; color: {INK_SOFT}; }}"
        )
        close_button.clicked.connect(self.close_adjacent)
        header.addWidget(close_button, 0)
        layout.addLayout(header)
        self._adjacent_scroll = QScrollArea(card)
        self._adjacent_scroll.setWidgetResizable(True)
        self._adjacent_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._adjacent_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        layout.addWidget(self._adjacent_scroll, 1)
        card.hide()
        return card

    def _position_overlays(self) -> None:
        hole = self.canvas.center_hole_rect()
        # Con formulario embebido la tarjeta usa TODO el hueco central; el
        # resumen compacto solo necesita la franja superior.
        card_height = (
            int(hole.height()) if self._form_panel is not None else int(min(hole.height(), 170))
        )
        self._center_card.setGeometry(int(hole.x()), int(hole.y()), int(hole.width()), card_height)
        self._center_card.raise_()
        self.tool_rail.adjustSize()
        self.tool_rail.move(12, max(12, (self.height() - self.tool_rail.height()) // 2))
        self.tool_rail.raise_()
        if not self._adjacent_card.isHidden():
            adjacent_width = max(260, min(380, self.width() - int(hole.right()) - 24))
            self._adjacent_card.setGeometry(
                int(hole.right()) + 10, int(hole.y()), adjacent_width, int(hole.height())
            )
            self._adjacent_card.raise_()
        if self._empty.isVisible():
            self._empty.adjustSize()
            self._empty.move(
                (self.width() - self._empty.width()) // 2,
                (self.height() - self._empty.height()) // 2,
            )
            self._empty.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_overlays()

    # ------------------------------------------------------------------
    # Ciclo de foco
    # ------------------------------------------------------------------

    def _project(self) -> Any:
        provider = self._project_provider
        return provider() if callable(provider) else None

    def current_entity_id(self) -> str:
        return self._center_id

    def history_ids(self) -> list[str]:
        return list(self._history)

    def refresh(self) -> None:
        """Entra/reentra en Foco: última entidad trabajada, o primera, o vacío."""
        project = self._project()
        if project is None or not getattr(project, "entities", None):
            self._center_id = ""
            self._history = []
            self.canvas.set_zones("", {})
            self._center_card.hide()
            self._empty.show()
            self._position_overlays()
            self._refresh_tool_context()
            return
        self._empty.hide()
        candidate = self._center_id
        if not candidate or project.entity_by_id(candidate) is None:
            candidate = ""
            if callable(self._last_entity_getter):
                candidate = str(self._last_entity_getter() or "")
            if not candidate or project.entity_by_id(candidate) is None:
                candidate = project.entities[0].id
        self.center_entity(candidate, push_history=False)

    def center_entity(self, entity_id: str, *, push_history: bool = True) -> None:
        """Centra una entidad: reconstruye zonas y recuerda la última trabajada."""
        project = self._project()
        if project is None:
            return
        entity = project.entity_by_id(str(entity_id))
        if entity is None:
            self.refresh()
            return
        if push_history and self._center_id and self._center_id != entity.id:
            self._history.append(self._center_id)
            del self._history[:-_HISTORY_LIMIT]
        self._center_id = entity.id
        if callable(self._last_entity_setter):
            # Best-effort: recordar el foco jamás debe romper el centrado.
            self._last_entity_setter(entity.id)

        self.close_adjacent()
        self._rebuild_canvas(project, entity)
        self._update_center_card(entity)
        self._back_button.setVisible(bool(self._history))
        self._center_card.show()
        self._position_overlays()
        self._refresh_tool_context()
        self.entityCentered.emit(entity.id)

    def _rebuild_canvas(self, project: Any, entity: Any) -> None:
        zones_payload: dict[str, list[dict]] = {}
        for zone, neighbors in classify_neighbors(project, entity.id).items():
            entries: list[dict] = []
            for neighbor in neighbors:
                other = project.entity_by_id(neighbor.entity_id)
                if other is None:
                    continue
                entries.append(
                    {
                        "entity_id": other.id,
                        "name": other.name,
                        "entity_type": getattr(other.entity_type, "value", str(other.entity_type)),
                        "is_ghost": neighbor.is_ghost,
                        "zone": zone,
                        "reason": neighbor.reason,
                    }
                )
            zones_payload[zone] = entries
        self.canvas.set_zones(entity.id, zones_payload)

    def _form_capable(self) -> bool:
        return self.ctx is not None and self.entity_controller is not None

    def _refresh_lifeline(self, entity: Any) -> None:
        milestones: list[Any] = []
        # El controller del host lo llama list_for_leaf; el servicio, list_hitos_for_leaf.
        lister = getattr(self.milestone_controller, "list_for_leaf", None) or getattr(
            self.milestone_controller, "list_hitos_for_leaf", None
        )
        if callable(lister):
            result = lister(entity.id)
            value = getattr(result, "value", result)
            if isinstance(value, list):
                milestones = value
        self.lifeline.set_entity(entity, milestones)
        self.lifeline.show()

    def _on_lifeline_span_edited(self, entity_id: str, birth: int, death: Any) -> None:
        # Re-emite hacia el workspace (persistencia por EntityController) y
        # refresca el lienzo: el lapso puede recolocar hitos por zona.
        self.lifespanEdited.emit(entity_id, birth, death)
        self._on_form_saved()

    def _open_milestone_adjacent(self, milestone_id: str) -> None:
        if self.ctx is None or self.milestone_controller is None or not milestone_id:
            return
        from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

        panel = MilestoneDetailPanel(
            self.ctx,
            self.milestone_controller,
            milestone_id,
            entity_controller=self.entity_controller,
            on_saved=lambda: self._refresh_lifeline_current(),
        )
        self.open_adjacent_widget(panel, "Hito")

    def _refresh_lifeline_current(self) -> None:
        project = self._project()
        if project is None or not self._center_id:
            return
        entity = project.entity_by_id(self._center_id)
        if entity is not None:
            self._refresh_lifeline(entity)

    def _update_center_card(self, entity: Any) -> None:
        self._refresh_lifeline(entity)
        if self._form_capable():
            self._mount_form(entity.id)
            for widget in (self._name_label, self._type_label, self._brief_label):
                widget.hide()
            self._form_scroll.show()
            return
        self._form_scroll.hide()
        for widget in (self._name_label, self._type_label, self._brief_label):
            widget.show()
        self._name_label.setText(entity.name)
        type_value = getattr(entity.entity_type, "value", str(entity.entity_type))
        canon_value = getattr(entity.canon_state, "value", str(entity.canon_state))
        suffix = " · fantasma (borrador interno)" if canon_value == "fantasma" else ""
        self._type_label.setText(f"{type_value}{suffix}")
        brief = " ".join(str(entity.brief_description or "").split())
        self._brief_label.setText(brief[:280] + ("…" if len(brief) > 280 else ""))

    def _mount_form(self, entity_id: str) -> None:
        """Instancia NUEVA del formulario por recentrado (patrón de la casa)."""
        from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

        if self._form_panel is not None:
            self._form_panel.deleteLater()
        self._form_panel = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            entity_id,
            variant="foco",
            relation_controller=self.relation_controller,
            milestone_controller=self.milestone_controller,
            on_open_relation=self._open_relation_adjacent,
            # FOCO-20: el «+» de la sección Relaciones abre el mismo flujo que
            # la herramienta del rail (buscador + crear-fantasma si no existe).
            on_create_relation=lambda: self._on_tool("create_relation"),
            on_saved=self._on_form_saved,
        )
        self._form_scroll.setWidget(self._form_panel)

    def _on_form_saved(self, *args: Any) -> None:
        """Autosave del formulario: refresca el LIENZO (vecindario/estados) sin
        reconstruir el formulario — no se puede perder el cursor al escribir."""
        # FOCO-19: el nombre/tipo editados también se ven en el Mapa.
        self.dataChanged.emit()
        project = self._project()
        if project is None or not self._center_id:
            return
        entity = project.entity_by_id(self._center_id)
        if entity is not None:
            self._rebuild_canvas(project, entity)

    # ------------------------------------------------------------------
    # Panel adyacente (relación / hito) — decisión 9: NO en el drawer derecho
    # ------------------------------------------------------------------

    def open_adjacent_widget(self, widget: QWidget, title: str) -> None:
        old = self._adjacent_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._adjacent_scroll.setWidget(widget)
        self._adjacent_title.setText(title)
        self._adjacent_card.show()
        self._position_overlays()

    def close_adjacent(self) -> None:
        if self._adjacent_card.isHidden():
            return
        old = self._adjacent_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._adjacent_card.hide()

    def _open_relation_adjacent(self, relation_id: str) -> None:
        if self.ctx is None or self.relation_controller is None or not relation_id:
            return
        from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

        panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            entity_controller=self.entity_controller,
            milestone_controller=self.milestone_controller,
            on_saved=self._on_form_saved,
        )
        self.open_adjacent_widget(panel, "Relación")

    def go_back(self) -> None:
        """Historial de foco en memoria: vuelve al centro anterior."""
        while self._history:
            previous = self._history.pop()
            project = self._project()
            if project is not None and project.entity_by_id(previous) is not None:
                self.center_entity(previous, push_history=False)
                self._back_button.setVisible(bool(self._history))
                return
        self._back_button.setVisible(False)

    # Accesos usados por la barra superior / rail (FOCO-11).
    def request_open_in_map(self) -> None:
        if self._center_id:
            self.openInMapRequested.emit(self._center_id)

    def request_open_in_chrono(self) -> None:
        if self._center_id:
            self.openInChronoRequested.emit(self._center_id)

    # ------------------------------------------------------------------
    # Rail de herramientas (FOCO-11): contexto de selección y acciones
    # ------------------------------------------------------------------

    @staticmethod
    def _canon_of(entity: Any) -> str:
        return str(getattr(getattr(entity, "canon_state", None), "value", "")).lower()

    def _selection_context(self) -> dict:
        project = self._project()
        center = (
            project.entity_by_id(self._center_id)
            if project is not None and self._center_id
            else None
        )
        selection = self.canvas.selected_ids()
        selection_has_ghost = False
        if project is not None:
            for selected_id in selection:
                other = project.entity_by_id(selected_id)
                if other is not None and self._canon_of(other) == "fantasma":
                    selection_has_ghost = True
                    break
        paused = list(getattr(project, "watering_paused_entity_ids", []) or [])
        return {
            "has_project": project is not None,
            "center_id": center.id if center is not None else "",
            "center_is_ghost": center is not None and self._canon_of(center) == "fantasma",
            "center_is_paused": center is not None and center.id in paused,
            "selection": selection,
            "selection_has_ghost": selection_has_ghost,
        }

    def _refresh_tool_context(self) -> None:
        self.tool_rail.set_selection_context(self._selection_context())

    def _log_error(self, message: str) -> None:
        log = getattr(self.ctx, "log", None)
        if callable(log):
            log("error", message)

    def _entities(self) -> list[Any]:
        project = self._project()
        return list(getattr(project, "entities", []) or []) if project is not None else []

    def _branch_candidates(self) -> list[Any]:
        return [
            entity
            for entity in self._entities()
            if str(getattr(getattr(entity, "entity_type", None), "value", "")).lower()
            in _BRANCH_TYPES
            and self._canon_of(entity) != "fantasma"
        ]

    def _ghost_target(self) -> str:
        """Fantasma sobre el que actúan Convertir/Vincular: el centro o la selección."""
        context = self._selection_context()
        if context["center_is_ghost"]:
            return context["center_id"]
        project = self._project()
        if project is not None:
            for selected_id in self.canvas.selected_ids():
                other = project.entity_by_id(selected_id)
                if other is not None and self._canon_of(other) == "fantasma":
                    return selected_id
        return ""

    def _recenter(self, entity_id: str | None = None) -> None:
        target = entity_id or self._center_id
        if target:
            self.center_entity(target, push_history=False)

    def _on_tool(self, tool_id: str) -> None:  # noqa: PLR0912 — dispatcher plano del rail
        anchor = self.tool_rail.anchor_for(tool_id)
        project = self._project()
        if project is None:
            return
        center_id = self._center_id
        if tool_id == "create_entity":
            self._popover = QuickCreatePopover(title="Nueva entidad", on_submit=self._create_entity)
            self._popover.open_next_to(anchor)
        elif tool_id == "create_related" and center_id:
            self._popover = QuickCreatePopover(
                title="Nueva entidad relacionada", on_submit=self._create_related
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "create_branch" and center_id:
            self._popover = QuickCreatePopover(
                title="Nueva rama contenedora", on_submit=self._create_branch
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "ghost_node":
            self._popover = QuickCreatePopover(
                title="Nuevo nodo fantasma",
                submit_text="Crear fantasma",
                with_description=True,
                on_submit=self._create_ghost,
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "create_relation" and center_id:
            self._popover = EntitySearchPopover(
                entities_provider=self._entities,
                on_pick=self._relate_to,
                on_create_ghost=self._ghost_and_relate,
                exclude_ids={center_id},
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "ghost_relation" and center_id:
            self._popover = EntitySearchPopover(
                entities_provider=self._entities,
                on_pick=self._ghost_relate_to,
                on_create_ghost=self._ghost_and_relate,
                exclude_ids={center_id},
                placeholder="Vincular (pendiente) con…",
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "add_to_branch" and center_id:
            self._popover = EntitySearchPopover(
                entities_provider=self._branch_candidates,
                on_pick=self._add_to_branch,
                placeholder="Buscar rama…",
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "create_milestone" and center_id:
            self.lifeline._request_create()
        elif tool_id == "ghost_convert":
            self._convert_ghost(self._ghost_target())
        elif tool_id == "ghost_link":
            ghost_id = self._ghost_target()
            if ghost_id:
                self._popover = EntitySearchPopover(
                    entities_provider=self._entities,
                    on_pick=lambda target_id, g=ghost_id: self._link_ghost(g, target_id),
                    exclude_ids={ghost_id},
                    only_real=True,
                    placeholder="Vincular fantasma con…",
                )
                self._popover.open_next_to(anchor)
        elif tool_id == "water":
            # FOCO-19: la central se asume SIEMPRE seleccionada — la selección
            # de satélites se le SUMA (antes la sustituía).
            ids = list(self.canvas.selected_ids())
            if center_id and center_id not in ids:
                ids.insert(0, center_id)
            if ids:
                self.waterRequested.emit(ids)
        elif tool_id == "dry" and center_id:
            self.dryRequested.emit(center_id)
        elif tool_id == "cultivate" and center_id:
            self.cultivateRequested.emit(center_id)
        elif tool_id == "view_map":
            self.request_open_in_map()
        elif tool_id == "view_chrono":
            self.request_open_in_chrono()

    # -- acciones de creación/vinculación (todas vía controllers/servicios) --

    def _create_entity(self, payload: dict) -> None:
        if self.entity_controller is None:
            return
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.dataChanged.emit()
        self.center_entity(result.value.id)

    def _create_related(self, payload: dict) -> None:
        if self.entity_controller is None or self.relation_controller is None:
            return
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        relation = self.relation_controller.create(
            self._center_id, result.value.id, "esta_relacionado_con"
        )
        if isinstance(relation, Error):
            self._log_error(relation.error)
        self.dataChanged.emit()
        # La central sigue siendo una (spec): la nueva aparece en su zona.
        self._recenter()

    def _create_branch(self, payload: dict) -> None:
        if self.entity_controller is None or self.relation_controller is None:
            return
        payload = dict(payload)
        payload["entity_type"] = "contenedor"
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        relation = self.relation_controller.create(result.value.id, self._center_id, "contiene")
        if isinstance(relation, Error):
            self._log_error(relation.error)
        self.dataChanged.emit()
        self._recenter()

    def _create_ghost(self, payload: dict) -> None:
        if self.ghost_service is None:
            return
        result = self.ghost_service.create_ghost(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        # Nace vinculado (relación fantasma) al centro si lo hay → zona Entorno.
        if self._center_id:
            self.ghost_service.create_ghost_relation(self._center_id, result.value.id)
        self.dataChanged.emit()
        self._recenter()

    def _ghost_and_relate(self, name: str) -> None:
        """«No existe» en el popover de relación → fantasma + vínculo pendiente."""
        if self.ghost_service is None or not self._center_id:
            return
        result = self.ghost_service.create_ghost({"name": name})
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.ghost_service.create_ghost_relation(self._center_id, result.value.id)
        self.dataChanged.emit()
        self._recenter()

    def _relate_to(self, target_id: str) -> None:
        if self.relation_controller is None or not self._center_id:
            return
        result = self.relation_controller.create(self._center_id, target_id, "esta_relacionado_con")
        if isinstance(result, Error):
            self._log_error(result.error)
        self.dataChanged.emit()
        self._recenter()

    def _ghost_relate_to(self, target_id: str) -> None:
        if self.ghost_service is None or not self._center_id:
            return
        result = self.ghost_service.create_ghost_relation(self._center_id, target_id)
        if isinstance(result, Error):
            self._log_error(result.error)
        self.dataChanged.emit()
        self._recenter()

    def _add_to_branch(self, branch_id: str) -> None:
        if self.relation_controller is None or not self._center_id:
            return
        result = self.relation_controller.create(branch_id, self._center_id, "contiene")
        if isinstance(result, Error):
            self._log_error(result.error)
        self.dataChanged.emit()
        self._recenter()

    def _convert_ghost(self, ghost_id: str) -> None:
        if self.ghost_service is None or not ghost_id:
            return
        result = self.ghost_service.convert_to_entity(ghost_id)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.dataChanged.emit()
        self._recenter(ghost_id if ghost_id == self._center_id else None)

    def _link_ghost(self, ghost_id: str, target_id: str) -> None:
        if self.ghost_service is None:
            return
        result = self.ghost_service.link_to_existing(ghost_id, target_id)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        # El fantasma desaparece: el foco pasa a la entidad real vinculada.
        if ghost_id == self._center_id:
            self.center_entity(target_id, push_history=False)
        else:
            self._recenter()
