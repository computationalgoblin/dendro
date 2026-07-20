"""BETA2-CAL-06 — Diálogo ancho para editar el calendario del proyecto.

La configuración del calendario abría antes en el cajón lateral estrecho, donde la
timeline y las rejillas de meses/semana se recortaban. Este diálogo modal, ancho y
centrado (mismo lenguaje que ``PortraitEditorDialog``) da holgura al editor.

Reutiliza ``ChronologyConfigPanel`` (editor + carga + "Guardar calendario"); al
guardar con éxito, cierra el diálogo y avisa al consumidor (``on_saved``) para que
refresque su vista. La UI nunca escribe persistencia directa: el panel guarda a
través de ``CalendarService`` vía el controller.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.chronology_config_panel import ChronologyConfigPanel
from hosts.DesktopHostPySide.widgets.design_system import SURFACE_HI


class CalendarEditorDialog(QDialog):
    """Editor de calendario a tamaño amplio, modal y centrado."""

    def __init__(
        self,
        controller,
        *,
        on_saved: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calendario y eras")
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {SURFACE_HI}; }}")
        self.setMinimumSize(900, 640)
        self.resize(980, 720)
        self._external_on_saved = on_saved

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        self.panel = ChronologyConfigPanel(controller, on_saved=self._handle_saved, compact=False)
        self.panel.refresh()
        root.addWidget(self.panel, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.reject)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _handle_saved(self) -> None:
        if self._external_on_saved is not None:
            self._external_on_saved()
        self.accept()


__all__ = ["CalendarEditorDialog"]
