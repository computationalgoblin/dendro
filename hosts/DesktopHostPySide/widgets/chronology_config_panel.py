"""Editor del calendario del proyecto (BETA2-CAL).

Hospeda el ``CalendarEditor`` unificado (eras encadenadas + presente + extensiones de
meses/semana) y lo persiste a través de ``ProjectChronologyController.configure_calendar``.
Sustituye al antiguo editor de tres modos; se conserva el nombre de clase porque lo
importan ``settings_panels`` y ``views/workspaces`` (drawer "Calendario y eras").
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.calendar_editor import CalendarEditor
from hosts.DesktopHostPySide.widgets.design_system import INK_OLIVE, LINE_CARD
from packages.domain.result import Error


class ChronologyConfigPanel(QGroupBox):
    """Editor del calendario del proyecto (una sola experiencia extensible)."""

    def __init__(
        self,
        controller: Any,
        *,
        on_saved: Callable[[], None] | None = None,
        compact: bool = False,
        parent=None,
    ):
        super().__init__("Calendario del proyecto", parent)
        self.controller = controller
        self.on_saved = on_saved
        self.compact = bool(compact)
        self.setObjectName("chronologyConfigPanel")
        self.setStyleSheet(
            f"QGroupBox#chronologyConfigPanel {{ color: {INK_OLIVE}; font-weight: 600; "
            f"border: 1px solid {LINE_CARD}; border-radius: 10px; margin-top: 8px; "
            "padding-top: 14px; background: transparent; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        self.editor = CalendarEditor(compact=compact)
        scroll = QScrollArea()
        scroll.setObjectName("chronologyConfigScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.addWidget(self.editor)
        holder_layout.addStretch(1)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        self.help_label = QLabel(
            "Arrastra las asas para ajustar eras y coloca la línea del presente."
        )
        self.help_label.setObjectName("mutedLabel")
        self.help_label.setWordWrap(True)
        root.addWidget(self.help_label)

        row = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("mutedLabel")
        self.status.setWordWrap(True)
        row.addWidget(self.status, 1)
        save = QPushButton("Guardar calendario")
        save.setObjectName("saveChronologyConfigButton")
        save.clicked.connect(self.save)
        row.addWidget(save)
        root.addLayout(row)

        self.refresh()

    def refresh(self) -> None:
        if self.controller is None or not hasattr(self.controller, "calendar_view"):
            self.status.setText("Cronología no disponible")
            return
        result = self.controller.calendar_view()
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.editor.set_value(result.value)

    def save(self) -> None:
        if self.controller is None or not hasattr(self.controller, "configure_calendar"):
            self.status.setText("Cronología no disponible")
            return
        result = self.controller.configure_calendar(self.editor.value())
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.status.setText("Calendario guardado")
        if self.on_saved is not None:
            self.on_saved()
