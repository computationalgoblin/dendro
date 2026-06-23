"""Panel de configuración previa al recorrido cronológico (CRON).

Selección de Modo (Consistencia/Creativo/Mixto), Profundidad, Agresividad y
Dirección, partiendo de un hito ya seleccionado. Emite ``submitted`` con la
configuración; no toca servicios (eso lo hace el host vía controlador).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from packages.domain.chronology_walk import (
    WalkAggressiveness,
    WalkDepth,
    WalkDirection,
    WalkMode,
)

_DIRECTIONS = [
    ("Hacia el futuro", WalkDirection.FUTURE),
    ("Hacia el pasado", WalkDirection.PAST),
]
_MODES = [
    ("Mixto (equilibrado)", WalkMode.MIXTO),
    ("Consistencia (severo)", WalkMode.CONSISTENCIA),
    ("Creativo (expansivo)", WalkMode.CREATIVO),
]
_DEPTHS = [
    ("Normal", WalkDepth.NORMAL),
    ("Ligera", WalkDepth.LIGERA),
    ("Profunda", WalkDepth.PROFUNDA),
]
_AGGRESSIVENESS = [
    ("Sugerir reparaciones", WalkAggressiveness.REPARAR),
    ("Solo señalar", WalkAggressiveness.SENALAR),
    ("Sugerir nuevas piezas", WalkAggressiveness.NUEVAS_PIEZAS),
]


class ChronologyWalkConfigPanel(QGroupBox):
    """Configura un recorrido cronológico antes de iniciarlo."""

    submitted = Signal(dict)
    cancelled = Signal()

    def __init__(self, start_milestone_id: str, start_title: str = "", parent: Any = None):
        super().__init__("Iniciar creación cronológica", parent)
        self._start_milestone_id = str(start_milestone_id)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self._start_label = QLabel(start_title or self._start_milestone_id)
        form.addRow("Hito de inicio:", self._start_label)

        self._direction = _combo(_DIRECTIONS)
        self._mode = _combo(_MODES)
        self._depth = _combo(_DEPTHS)
        self._aggressiveness = _combo(_AGGRESSIVENESS)
        form.addRow("Dirección:", self._direction)
        form.addRow("Modo:", self._mode)
        form.addRow("Profundidad:", self._depth)
        form.addRow("Agresividad:", self._aggressiveness)
        root.addLayout(form)

        buttons = QHBoxLayout()
        self._start_btn = QPushButton("Iniciar recorrido")
        self._cancel_btn = QPushButton("Cancelar")
        self._start_btn.clicked.connect(self._on_submit)
        self._cancel_btn.clicked.connect(self.cancelled.emit)
        buttons.addStretch(1)
        buttons.addWidget(self._cancel_btn)
        buttons.addWidget(self._start_btn)
        root.addLayout(buttons)

    def config(self) -> dict[str, Any]:
        """Configuración actual seleccionada (enums de dominio).

        Qt aplana los ``str``-Enum a su cadena en ``currentData``; se recoercen
        al enum para que el contrato del panel devuelva tipos de dominio.
        """
        return {
            "start_milestone_id": self._start_milestone_id,
            "direction": _coerce(WalkDirection, self._direction.currentData()),
            "mode": _coerce(WalkMode, self._mode.currentData()),
            "depth": _coerce(WalkDepth, self._depth.currentData()),
            "aggressiveness": _coerce(WalkAggressiveness, self._aggressiveness.currentData()),
        }

    def _on_submit(self) -> None:
        self.submitted.emit(self.config())


def _combo(options: list[tuple[str, Any]]) -> QComboBox:
    combo = QComboBox()
    for label, value in options:
        combo.addItem(label, value)
    return combo


def _coerce(enum_cls, value):
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return value
