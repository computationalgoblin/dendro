"""Panel de revisión por-candidato (Fase A): sustituye la tabla «Semillas».

Se abre al pulsar una notificación de semilla. Muestra el encabezado y el texto
del candidato de forma legible y editable, y permite Aceptar/Rechazar. Aceptar
escribe las ediciones en el candidato y lo canoniza vía el servicio; Rechazar lo
descarta. (Prompt inline de edición asistida: pendiente para una fase posterior.)

No escribe en persistencia directamente: usa CandidateController (que envuelve el
CandidateService). El candidato es el modelo de dominio; al aceptar, el servicio
crea la entidad/relación/anillo correspondiente.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from packages.domain.result import Error

# Campos de texto del candidato por orden de preferencia para el cuerpo legible.
_BODY_FIELDS = ("extended_description", "body", "brief_description", "description", "summary")


def candidate_body_text(proposed_data: dict[str, Any]) -> str:
    """Extrae el texto legible más rico disponible del candidato."""
    if not isinstance(proposed_data, dict):
        return ""
    for key in _BODY_FIELDS:
        value = proposed_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class CandidateReviewPanel(QWidget):
    """Revisión ligera de un candidato: encabezado + texto editable + decisión."""

    def __init__(
        self,
        candidate: Any,
        controller: Any,
        *,
        on_decision: Callable[[str, str], None] | None = None,
        log: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._candidate = candidate
        self._controller = controller
        self._on_decision = on_decision
        self._log = log
        self._build()

    # ── construcción ──────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        kind = getattr(getattr(self._candidate, "candidate_type", None), "value", "")
        tag = QLabel(str(kind).replace("_", " ").upper() or "CANDIDATO")
        tag.setObjectName("badge")
        layout.addWidget(tag)

        self._title_edit = QLineEdit(str(getattr(self._candidate, "title", "") or ""))
        self._title_edit.setPlaceholderText("Encabezado del candidato")
        layout.addWidget(self._title_edit)

        proposed = dict(getattr(self._candidate, "proposed_data", {}) or {})
        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText("Texto del candidato")
        self._body_edit.setPlainText(candidate_body_text(proposed))
        self._body_edit.setMinimumHeight(200)
        layout.addWidget(self._body_edit, 1)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        row = QHBoxLayout()
        accept = QPushButton("Aceptar")
        accept.setObjectName("primaryButton")
        accept.clicked.connect(self._accept)
        reject = QPushButton("Rechazar")
        reject.clicked.connect(self._reject)
        row.addWidget(reject)
        row.addStretch(1)
        row.addWidget(accept)
        layout.addLayout(row)

    # ── decisiones ────────────────────────────────────────────────────────

    def _candidate_id(self) -> str:
        return str(getattr(self._candidate, "id", "") or "")

    def _apply_edits(self) -> None:
        """Escribe las ediciones del usuario en el candidato antes de aceptar."""
        new_title = self._title_edit.text().strip()
        if new_title:
            self._candidate.title = new_title
        proposed = getattr(self._candidate, "proposed_data", None)
        if isinstance(proposed, dict):
            body = self._body_edit.toPlainText().strip()
            # Reescribe el primer campo de texto existente; si no hay, usa body.
            target = next((k for k in _BODY_FIELDS if k in proposed), "body")
            proposed[target] = body
            if new_title and "name" in proposed:
                proposed["name"] = new_title

    def _accept(self) -> None:
        self._apply_edits()
        result = self._controller.accept(self._candidate_id())
        if isinstance(result, Error):
            self._status.setText(result.error)
            if self._log:
                self._log("error", result.error)
            return
        if self._log:
            self._log("info", "Semilla aceptada")
        if self._on_decision:
            self._on_decision(self._candidate_id(), "accept")

    def _reject(self) -> None:
        result = self._controller.reject(self._candidate_id())
        if isinstance(result, Error):
            self._status.setText(result.error)
            if self._log:
                self._log("error", result.error)
            return
        if self._log:
            self._log("info", "Semilla rechazada")
        if self._on_decision:
            self._on_decision(self._candidate_id(), "reject")


__all__ = ["CandidateReviewPanel", "candidate_body_text"]
