"""Panel del recorrido cronológico en marcha (CRON).

Ventana ÚNICA del paso: lectura editorial de la IA, diagnóstico, y TODOS los
cambios propuestos (nuevas entidades, ediciones con diff antes→después,
relaciones, hitos) como tarjetas EDITABLES con casilla de inclusión. El usuario
edita en sitio y aplica el bloque ('Aplicar cambios') o desmarca piezas. No toca
servicios: emite señales que el host enruta al controlador (aplicación atómica).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_SEVERITY_LABEL = {"alta": "● alta", "media": "● media", "baja": "● baja"}


class _ChangeCard(QGroupBox):
    """Tarjeta editable de un cambio propuesto (un candidato)."""

    def __init__(self, change: dict[str, Any], parent: Any = None):
        super().__init__(parent)
        self._change = dict(change or {})
        self._kind = str(self._change.get("kind") or "")
        self._fields: dict[str, Any] = {}

        self.setTitle(str(self._change.get("header") or "Cambio propuesto"))
        self.setCheckable(self._kind != "report")
        self.setChecked(self._kind != "report")

        layout = QVBoxLayout(self)
        before = self._change.get("before")
        if before:
            layout.addWidget(QLabel("Canon actual (antes):"))
            prev = QTextEdit()
            prev.setReadOnly(True)
            prev.setPlainText(str(before))
            prev.setMaximumHeight(70)
            layout.addWidget(prev)
            layout.addWidget(QLabel("Propuesta (después, editable):"))

        form = QFormLayout()
        for field in self._change.get("fields") or []:
            key = str(field.get("key") or "")
            if not key:
                continue
            if field.get("multiline"):
                widget = QTextEdit()
                widget.setPlainText(str(field.get("value") or ""))
                widget.setMaximumHeight(80)
            else:
                widget = QLineEdit(str(field.get("value") or ""))
            self._fields[key] = widget
            form.addRow(str(field.get("label") or key), widget)
        layout.addLayout(form)

        if self._kind == "report":
            note = QLabel("Solo lectura (no aplica cambios al canon).")
            note.setWordWrap(True)
            layout.addWidget(note)

    def _value(self, widget: Any) -> str:
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return widget.text().strip()

    def is_included(self) -> bool:
        return self._kind != "report" and self.isChecked()

    def apply_item(self) -> dict[str, Any] | None:
        """{candidate_id, edited_data} con las ediciones del usuario, o None."""
        if not self.is_included():
            return None
        cid = str(self._change.get("candidate_id") or "")
        if not cid:
            return None
        values = {key: self._value(widget) for key, widget in self._fields.items()}
        if self._change.get("apply") == "milestone":
            base = dict(self._change.get("base") or {})
            year = values.pop("year", None)
            if year is not None:
                base["year"] = _opt_int(year)
            base.update({k: v for k, v in values.items()})
            edited = {"milestone": base}
        else:
            edited = values
        return {"candidate_id": cid, "edited_data": edited}


class ChronologyWalkRunnerPanel(QWidget):
    """UI del paso a paso del recorrido (ventana única editable)."""

    advanceRequested = Signal()
    stopRequested = Signal()
    decisionRequested = Signal(str)
    applyRequested = Signal(list)  # [{candidate_id, edited_data}]

    def __init__(self, parent: Any = None):
        super().__init__(parent)
        self._cards: list[_ChangeCard] = []
        root = QVBoxLayout(self)

        self._title = QLabel("Recorrido cronológico")
        self._title.setProperty("role", "heading")
        root.addWidget(self._title)

        self._status = QLabel("")
        root.addWidget(self._status)

        root.addWidget(QLabel("Lectura editorial:"))
        self._reading = QTextEdit()
        self._reading.setReadOnly(True)
        self._reading.setMaximumHeight(140)
        root.addWidget(self._reading)

        root.addWidget(QLabel("Diagnóstico / problemas:"))
        self._issues = QListWidget()
        self._issues.setMaximumHeight(110)
        root.addWidget(self._issues)

        root.addWidget(QLabel("Cambios propuestos (editables):"))
        self._changes_area = QScrollArea()
        self._changes_area.setWidgetResizable(True)
        self._changes_container = QWidget()
        self._changes_layout = QVBoxLayout(self._changes_container)
        self._changes_layout.addStretch(1)
        self._changes_area.setWidget(self._changes_container)
        root.addWidget(self._changes_area, 1)

        self._candidates_label = QLabel("Cambios propuestos: 0")
        root.addWidget(self._candidates_label)

        apply_row = QHBoxLayout()
        apply_row.addStretch(1)
        self._apply_btn = QPushButton("Aplicar cambios")
        self._apply_btn.setObjectName("primaryButton")
        self._apply_btn.clicked.connect(self._on_apply)
        self._apply_btn.setEnabled(False)
        apply_row.addWidget(self._apply_btn)
        root.addLayout(apply_row)

        buttons = QHBoxLayout()
        self._decide_btn = QPushButton("Registrar decisión")
        self._advance_btn = QPushButton("Avanzar")
        self._stop_btn = QPushButton("Parar")
        self._decide_btn.clicked.connect(lambda: self.decisionRequested.emit("revisado"))
        self._advance_btn.clicked.connect(self.advanceRequested.emit)
        self._stop_btn.clicked.connect(self.stopRequested.emit)
        buttons.addWidget(self._decide_btn)
        buttons.addStretch(1)
        buttons.addWidget(self._stop_btn)
        buttons.addWidget(self._advance_btn)
        root.addLayout(buttons)

    def show_step(self, result: dict[str, Any]) -> None:
        """Renderiza el resultado de ``analyze_step`` (dict de stage_results + walk)."""
        result = dict(result or {})
        payload = dict(result.get("model_payload") or {})
        walk = dict(result.get("walk") or {})

        self._reading.setPlainText(
            str(payload.get("report") or result.get("report") or result.get("summary") or "")
        )

        self._issues.clear()
        for issue in payload.get("issues") or []:
            if not isinstance(issue, dict):
                continue
            sev = _SEVERITY_LABEL.get(str(issue.get("severity")), "●")
            kind = str(issue.get("kind") or "")
            title = str(issue.get("title") or issue.get("description") or "Problema")
            self._issues.addItem(f"{sev}  [{kind}] {title}")

        stopped = bool(walk.get("stopped"))
        if stopped:
            reason = str(walk.get("stop_reason") or "Problema duro detectado")
            self._status.setText(f"⏸ Detenido: {reason}. Registra una decisión para continuar.")
        else:
            self._status.setText("▶ Recorrido en marcha.")
        # Con parada dura, avanzar se bloquea hasta decidir.
        self._advance_btn.setEnabled(not stopped)

    def set_changes(self, changes: list[dict[str, Any]]) -> None:
        """Construye las tarjetas editables de los cambios propuestos del paso."""
        for card in self._cards:
            card.setParent(None)
        self._cards = []
        applicable = 0
        for change in changes or []:
            card = _ChangeCard(change)
            self._changes_layout.insertWidget(self._changes_layout.count() - 1, card)
            self._cards.append(card)
            if str(change.get("kind")) != "report":
                applicable += 1
        self._candidates_label.setText(f"Cambios propuestos: {len(self._cards)}")
        self._apply_btn.setEnabled(applicable > 0)
        # Feedback claro: si la IA no propone nada accionable en este hito, dilo
        # (no es un bug: el hito puede ser coherente) e invita a avanzar.
        if applicable == 0:
            self._status.setText(
                "Sin cambios que aplicar en este hito (coherente). Pulsa 'Avanzar'."
            )

    def _on_apply(self) -> None:
        items = [card.apply_item() for card in self._cards]
        items = [it for it in items if it]
        if items:
            self.applyRequested.emit(items)

    def set_status(self, text: str) -> None:
        self._status.setText(str(text))

    def mark_applied(self, applied_count: int) -> None:
        self._apply_btn.setEnabled(False)
        self._status.setText(
            f"✓ {applied_count} cambio(s) aplicado(s). Pulsa 'Avanzar' para seguir."
        )

    def set_busy(self, busy: bool) -> None:
        self._advance_btn.setEnabled(not busy)
        self._decide_btn.setEnabled(not busy)
        self._stop_btn.setEnabled(not busy)
        self._apply_btn.setEnabled(not busy and bool(self._cards))
        if busy:
            self._status.setText("… Analizando el hito actual.")


def _opt_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
