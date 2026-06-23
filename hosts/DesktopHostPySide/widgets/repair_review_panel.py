"""UX8 — panel de revisión de reparación de coherencia.

Muestra los cambios CONCRETOS propuestos por la IA como una lista revisable con,
por cada cambio: una casilla para incluirlo, el ANTES (canon actual, solo lectura)
y el DESPUÉS (texto propuesto, editable). El usuario ajusta y pulsa «Aplicar
seleccionados»; el host aplica cada cambio a canon vía servicios (acción humana
explícita — la IA nunca escribe canon por su cuenta).

El panel es tonto respecto a canon: recibe cambios YA resueltos
(`coherence_repair.resolve_repair_changes`) y devuelve los seleccionados (con el
`after` posiblemente editado) al host vía `on_apply`.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class RepairReviewPanel(QWidget):
    def __init__(
        self,
        resolved_changes: list[dict[str, Any]],
        *,
        on_apply: Callable[[list[dict[str, Any]]], None],
        on_cancel: Callable[[], None],
        log: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._changes = list(resolved_changes or [])
        self._on_apply = on_apply
        self._on_cancel = on_cancel
        self._log = log
        # Filas: (change_dict, checkbox, after_editor). Solo las aplicables tienen editor.
        self._rows: list[tuple[dict[str, Any], QCheckBox, QTextEdit | None]] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        n = len(self._changes)
        title = QLabel(f"Reparar coherencia ({n} cambio{'s' if n != 1 else ''})")
        title.setObjectName("badge")
        layout.addWidget(title)

        if not self._changes:
            empty = QLabel(
                "La IA no propuso ningún cambio concreto sobre el canon. "
                "Las sugerencias vagas quedan como preguntas abiertas en el informe."
            )
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            holder = QWidget()
            col = QVBoxLayout(holder)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(8)
            for change in self._changes:
                col.addWidget(self._build_row(change))
            col.addStretch(1)
            scroll.setWidget(holder)
            layout.addWidget(scroll, 1)

        status = QLabel("")
        status.setWordWrap(True)
        self._status = status
        layout.addWidget(status)

        row = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self._cancel)
        apply_btn = QPushButton("Aplicar seleccionados")
        apply_btn.setObjectName("primaryButton")
        apply_btn.clicked.connect(self._apply)
        apply_btn.setEnabled(n > 0)
        row.addWidget(cancel)
        row.addStretch(1)
        row.addWidget(apply_btn)
        layout.addLayout(row)

    def _build_row(self, change: dict[str, Any]) -> QWidget:
        frame = QFrame()
        frame.setObjectName("repairRow")
        v = QVBoxLayout(frame)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(4)

        applicable = bool(change.get("applicable", True))
        check = QCheckBox(str(change.get("label") or "Cambio"))
        check.setChecked(applicable)
        check.setEnabled(applicable)
        v.addWidget(check)

        if change.get("note"):
            note = QLabel(str(change["note"]))
            note.setObjectName("muted")
            note.setWordWrap(True)
            v.addWidget(note)

        before = QLabel(f"antes: {change.get('before') or '—'}")
        before.setObjectName("muted")
        before.setWordWrap(True)
        v.addWidget(before)

        editor: QTextEdit | None = None
        if applicable:
            v.addWidget(QLabel("ahora (editable):"))
            editor = QTextEdit()
            editor.setPlainText(str(change.get("after") or ""))
            editor.setMinimumHeight(70)
            v.addWidget(editor)
        else:
            after = QLabel(f"ahora: {change.get('after') or '—'}")
            after.setObjectName("muted")
            after.setWordWrap(True)
            v.addWidget(after)

        self._rows.append((change, check, editor))
        return frame

    def selected_changes(self) -> list[dict[str, Any]]:
        """Cambios marcados, con el `after` actualizado desde su editor."""
        out: list[dict[str, Any]] = []
        for change, check, editor in self._rows:
            if not check.isChecked():
                continue
            updated = dict(change)
            if editor is not None:
                updated["after"] = editor.toPlainText().strip()
            out.append(updated)
        return out

    def _apply(self) -> None:
        selected = self.selected_changes()
        if not selected:
            self._status.setText("Marca al menos un cambio para aplicar.")
            return
        if self._log:
            self._log("info", f"Aplicando {len(selected)} reparación(es) de coherencia")
        self._on_apply(selected)

    def _cancel(self) -> None:
        self._on_cancel()


__all__ = ["RepairReviewPanel"]
