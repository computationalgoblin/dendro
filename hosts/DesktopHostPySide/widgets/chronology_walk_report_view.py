"""Vista del informe final del recorrido cronológico (CRON).

Renderiza un ``ChronologyWalkReport`` (artefacto de revisión, no canon): rango,
veredicto, huecos críticos, contradicciones, candidatos creados y próximos pasos.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ChronologyWalkReportView(QWidget):
    """Muestra el informe de cierre de un recorrido."""

    closed = Signal()

    def __init__(self, parent: Any = None):
        super().__init__(parent)
        root = QVBoxLayout(self)

        self._title = QLabel("Informe de recorrido cronológico")
        self._title.setProperty("role", "heading")
        root.addWidget(self._title)

        self._verdict = QLabel("")
        self._verdict.setWordWrap(True)
        root.addWidget(self._verdict)

        self._range = QLabel("")
        root.addWidget(self._range)

        root.addWidget(QLabel("Contradicciones:"))
        self._contradictions = QListWidget()
        root.addWidget(self._contradictions, 1)

        root.addWidget(QLabel("Huecos críticos:"))
        self._gaps = QListWidget()
        root.addWidget(self._gaps, 1)

        root.addWidget(QLabel("Próximos pasos recomendados:"))
        self._next_steps = QListWidget()
        root.addWidget(self._next_steps, 1)

        self._candidates = QLabel("")
        root.addWidget(self._candidates)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._close_btn = QPushButton("Cerrar")
        self._close_btn.clicked.connect(self.closed.emit)
        buttons.addWidget(self._close_btn)
        root.addLayout(buttons)

    def show_report(self, report: Any) -> None:
        """Renderiza un ChronologyWalkReport (o su dict)."""
        data = report.to_dict() if hasattr(report, "to_dict") else dict(report or {})

        self._verdict.setText(f"Veredicto: {data.get('verdict', '')}")
        analyzed = len(data.get("milestones_analyzed") or [])
        up_to = data.get("timeline_reviewed_up_to_milestone_id", "")
        self._range.setText(
            f"Hitos analizados: {analyzed} · Cronología revisada hasta: {up_to or '—'}"
        )

        self._fill(self._contradictions, data.get("contradictions"), "title")
        self._fill(self._gaps, data.get("critical_gaps"), "title")
        self._next_steps.clear()
        for step in data.get("recommended_next_steps") or []:
            self._next_steps.addItem(str(step))

        self._candidates.setText(
            f"Candidatos creados durante el recorrido: {len(data.get('candidates_created') or [])}"
        )

    @staticmethod
    def _fill(widget: QListWidget, items: Any, key: str) -> None:
        widget.clear()
        for item in items or []:
            if isinstance(item, dict):
                text = str(item.get(key) or item.get("description") or item.get("kind") or "—")
            else:
                text = str(item)
            widget.addItem(text)
