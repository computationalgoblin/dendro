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
from packages.application.foco_zones import classify_neighbors

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
            on_saved=self._on_form_saved,
        )
        self._form_scroll.setWidget(self._form_panel)

    def _on_form_saved(self, *args: Any) -> None:
        """Autosave del formulario: refresca el LIENZO (vecindario/estados) sin
        reconstruir el formulario — no se puede perder el cursor al escribir."""
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
