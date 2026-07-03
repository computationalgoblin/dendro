"""Popovers del Modo Foco (BETA2-FOCO-11).

Formaliza el patrón ad-hoc de la casa (``QFrame`` con ``Qt.Popup`` +
``mapToGlobal``) en una clase reutilizable, y aporta los dos popovers de datos
del rail: búsqueda de entidad (con «crear fantasma» si no hay resultados) y
alta rápida (nombre + descripción opcional). Las herramientas actúan al click;
si necesitan datos, el popover se abre JUNTO a la herramienta (spec).
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_SOFT,
    INK_MUTED,
    INK_STRONG,
    LINE_SOFT,
    POPUP_BG,
)

_MAX_RESULTS = 8


class Popover(QFrame):
    """Marco flotante anclado a un widget (patrón Qt.Popup de la casa)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("focoPopover")
        self.setStyleSheet(
            f"QFrame#focoPopover {{ background: {POPUP_BG}; border: 1px solid {GOLD_SOFT}; "
            "border-radius: 12px; }"
            f"QLabel {{ color: {INK_MUTED}; background: transparent; border: none; }}"
            f"QLineEdit, QTextEdit {{ background: #FFFDF8; border: 1px solid {LINE_SOFT}; "
            "border-radius: 8px; padding: 4px 8px; }"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 12)
        self._layout.setSpacing(6)

    def body_layout(self) -> QVBoxLayout:
        return self._layout

    def open_next_to(self, anchor: QWidget) -> None:
        """Muestra el popover pegado al lateral derecho del ancla."""
        self.adjustSize()
        top_right = anchor.mapToGlobal(QPoint(anchor.width() + 6, 0))
        self.move(top_right)
        self.show()


class EntitySearchPopover(Popover):
    """Búsqueda en vivo de entidades del proyecto.

    ``on_pick(entity_id)`` al elegir; si no hay resultados y se pasó
    ``on_create_ghost``, ofrece «Crear fantasma “<texto>”» (spec: desde el
    popover de relación se puede crear el placeholder al vuelo).
    """

    def __init__(
        self,
        *,
        entities_provider: Callable[[], list[Any]],
        on_pick: Callable[[str], None],
        on_create_ghost: Callable[[str], None] | None = None,
        placeholder: str = "Buscar entidad…",
        exclude_ids: set[str] | None = None,
        only_ghosts: bool = False,
        only_real: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entities_provider = entities_provider
        self._on_pick = on_pick
        self._on_create_ghost = on_create_ghost
        self._exclude_ids = set(exclude_ids or ())
        self._only_ghosts = bool(only_ghosts)
        self._only_real = bool(only_real)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(placeholder)
        self.search_edit.textChanged.connect(self._refresh)
        self._layout.addWidget(self.search_edit)
        self.results = QListWidget(self)
        self.results.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; color: {INK_STRONG}; }} "
            f"QListWidget::item:selected {{ background: {GOLD_SOFT}; border-radius: 6px; }}"
        )
        self.results.itemActivated.connect(self._pick_item)
        self.results.itemClicked.connect(self._pick_item)
        self._layout.addWidget(self.results)
        self.ghost_button = QPushButton("", self)
        self.ghost_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ghost_button.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px dashed {GOLD}; "
            f"border-radius: 8px; color: {INK_STRONG}; padding: 4px 8px; }}"
        )
        self.ghost_button.clicked.connect(self._create_ghost)
        self.ghost_button.hide()
        self._layout.addWidget(self.ghost_button)
        self._refresh("")

    # -- API también usable desde tests (sin ratón) --------------------

    def set_query(self, text: str) -> None:
        self.search_edit.setText(text)

    def result_ids(self) -> list[str]:
        return [
            self.results.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.results.count())
        ]

    def pick_first(self) -> None:
        if self.results.count():
            self._pick_item(self.results.item(0))

    def create_ghost_from_query(self) -> None:
        self._create_ghost()

    # -- interno --------------------------------------------------------

    def _matches(self, query: str) -> list[Any]:
        query = query.casefold().strip()
        found = []
        for entity in self._entities_provider() or []:
            if getattr(entity, "id", "") in self._exclude_ids:
                continue
            canon = str(getattr(getattr(entity, "canon_state", None), "value", "")).lower()
            is_ghost = canon == "fantasma"
            if self._only_ghosts and not is_ghost:
                continue
            if self._only_real and is_ghost:
                continue
            name = str(getattr(entity, "name", ""))
            if query and query not in name.casefold():
                continue
            found.append(entity)
        found.sort(key=lambda e: str(getattr(e, "name", "")).casefold())
        return found[:_MAX_RESULTS]

    def _refresh(self, text: str) -> None:
        self.results.clear()
        for entity in self._matches(text):
            canon = str(getattr(getattr(entity, "canon_state", None), "value", "")).lower()
            suffix = "  (fantasma)" if canon == "fantasma" else ""
            item = QListWidgetItem(f"{getattr(entity, 'name', '')}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, getattr(entity, "id", ""))
            self.results.addItem(item)
        query = self.search_edit.text().strip()
        can_ghost = self._on_create_ghost is not None and bool(query) and not self.results.count()
        self.ghost_button.setVisible(can_ghost)
        if can_ghost:
            self.ghost_button.setText(f"Crear fantasma «{query}»")

    def _pick_item(self, item: QListWidgetItem) -> None:
        entity_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self.hide()
        if entity_id:
            self._on_pick(entity_id)

    def _create_ghost(self) -> None:
        query = self.search_edit.text().strip()
        if not query or self._on_create_ghost is None:
            return
        self.hide()
        self._on_create_ghost(query)


class QuickCreatePopover(Popover):
    """Alta rápida (nombre + descripción opcional) para entidad/rama/fantasma."""

    def __init__(
        self,
        *,
        title: str,
        on_submit: Callable[[dict], None],
        submit_text: str = "Crear",
        with_description: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_submit = on_submit
        self._layout.addWidget(QLabel(title, self))
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Nombre…")
        self._layout.addWidget(self.name_edit)
        self.description_edit: QTextEdit | None = None
        if with_description:
            self.description_edit = QTextEdit(self)
            self.description_edit.setPlaceholderText("¿Qué pretende ser? (indicación vaga)")
            self.description_edit.setFixedHeight(64)
            self._layout.addWidget(self.description_edit)
        self.submit_button = QPushButton(submit_text, self)
        self.submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_button.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; border: none; border-radius: 10px; "
            "color: #FCF8EC; font-weight: 600; padding: 6px 12px; }"
        )
        self.submit_button.clicked.connect(self.submit)
        self._layout.addWidget(self.submit_button)
        self.name_edit.returnPressed.connect(self.submit)

    def submit(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            return
        payload: dict = {"name": name}
        if self.description_edit is not None:
            description = self.description_edit.toPlainText().strip()
            if description:
                payload["brief_description"] = description
        self.hide()
        self._on_submit(payload)
