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
from packages.application.foco_zones import classify_neighbors

_HISTORY_LIMIT = 50


class FocoView(QWidget):
    """Escritorio causal: una entidad al centro, su jardín alrededor."""

    entityCentered = Signal(str)  # noqa: N815 — convención Qt de señales
    openInMapRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    openInChronoRequested = Signal(str)  # noqa: N815 — convención Qt de señales

    def __init__(
        self,
        *,
        project_provider: Callable[[], Any],
        last_entity_getter: Callable[[], str] | None = None,
        last_entity_setter: Callable[[str], Any] | None = None,
        watering_service: Any = None,
        ghost_service: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_provider = project_provider
        self._last_entity_getter = last_entity_getter
        self._last_entity_setter = last_entity_setter
        self.watering_service = watering_service
        self.ghost_service = ghost_service
        self._center_id = ""
        self._history: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.canvas = FocoCanvas(self)
        layout.addWidget(self.canvas, 1)
        self.canvas.satelliteActivated.connect(self.center_entity)

        self._center_card = self._build_center_card()
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
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(14)

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
        card.hide()
        return card

    def _position_overlays(self) -> None:
        hole = self.canvas.center_hole_rect()
        self._center_card.setGeometry(
            int(hole.x()), int(hole.y()), int(hole.width()), int(min(hole.height(), 170))
        )
        self._center_card.raise_()
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

        self._name_label.setText(entity.name)
        type_value = getattr(entity.entity_type, "value", str(entity.entity_type))
        canon_value = getattr(entity.canon_state, "value", str(entity.canon_state))
        suffix = " · fantasma (borrador interno)" if canon_value == "fantasma" else ""
        self._type_label.setText(f"{type_value}{suffix}")
        brief = " ".join(str(entity.brief_description or "").split())
        self._brief_label.setText(brief[:280] + ("…" if len(brief) > 280 else ""))
        self._back_button.setVisible(bool(self._history))
        self._center_card.show()
        self._position_overlays()
        self.entityCentered.emit(entity.id)

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
