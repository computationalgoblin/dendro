"""Panel de proyecto «Hilos sueltos» (BETA-MULTIAGENT2-FIX-09, G2-15).

Lo que un guionista necesita ver de un vistazo: **qué planté y no recogí**. La
consulta existía en `causal_milestone_service` desde B41 —midiendo otra cosa: 20
de 20 hitos— y no tenía una sola pantalla; el controlador la exponía y nadie la
llamaba.

Definición que se enseña (la del servicio, única en el repo): un hito es un hilo
suelto si **ningún hito posterior lo declara como causa**, excluyendo los
hitos-marco (contención temporal, no setups). El panel lo dice en español para
que el usuario sepa exactamente qué está contando, y con 0 hilos sueltos dice que
no hay ninguno (silencio honesto, no una caja vacía).

Coste IA cero: es una consulta determinista sobre el canon. La UI no escribe
persistencia: solo lee el controlador y navega al hito.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import PanelScaffold
from hosts.DesktopHostPySide.widgets.milestone_labels import milestone_temporal_label

_EXPLICACION = (
    "Hitos que ningún hito posterior recoge: nadie los declara como causa. "
    "Los hitos-marco (los que solo contienen a otros) no cuentan."
)

_SIN_HILOS = (
    "No hay hilos sueltos: todo lo que plantaste tiene consecuencia declarada."
)


class LooseThreadsPanel(QWidget):
    """Lista los hilos sueltos del proyecto y abre el hito al clicar."""

    def __init__(
        self,
        controller: Any,
        *,
        on_open_milestone: Callable[[str], None] | None = None,
        on_close: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._on_open = on_open_milestone
        self._on_close = on_close
        self.setMinimumWidth(420)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._hitos = self._loose_threads()
        scaffold = PanelScaffold(
            "Hilos sueltos", badge=str(len(self._hitos)), badge_tone="gold"
        )
        outer.addWidget(scaffold)
        body = scaffold.body

        explicacion = QLabel(_EXPLICACION)
        explicacion.setObjectName("mutedLabel")
        explicacion.setWordWrap(True)
        body.addWidget(explicacion)

        self.threads_list = QListWidget()
        self.threads_list.setObjectName("looseThreadsList")
        self.threads_list.itemClicked.connect(self._open_selected)
        body.addWidget(self.threads_list, 1)

        self.empty_label = QLabel(_SIN_HILOS)
        self.empty_label.setObjectName("mutedLabel")
        self.empty_label.setWordWrap(True)
        body.addWidget(self.empty_label)

        close = QPushButton("Cerrar")
        close.setObjectName("closeLooseThreadsButton")
        close.clicked.connect(self._close)
        body.addWidget(close)
        self._fill()

    # ── datos ────────────────────────────────────────────────────────────

    def _loose_threads(self) -> list[Any]:
        getter = getattr(self._controller, "hitos_without_consequences", None)
        if not callable(getter):
            return []
        try:
            return list(getter() or [])
        except Exception:  # noqa: BLE001 — un panel nunca rompe el flujo
            return []

    def _fill(self) -> None:
        self.threads_list.clear()
        for hito in self._hitos:
            titulo = str(getattr(hito, "title", "") or "Hito sin título")
            item = QListWidgetItem(f"{titulo}  ·  {milestone_temporal_label(hito)}")
            item.setData(Qt.ItemDataRole.UserRole, str(getattr(hito, "id", "")))
            self.threads_list.addItem(item)
        hay = bool(self._hitos)
        self.threads_list.setVisible(hay)
        self.empty_label.setVisible(not hay)

    # ── acciones ─────────────────────────────────────────────────────────

    def _open_selected(self, item: Any) -> None:
        if self._on_open is None or item is None:
            return
        hito_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if hito_id:
            self._on_open(hito_id)

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
