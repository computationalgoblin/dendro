"""Reusable right-side InspectorPanel for DesktopHostPySide (B27.4).

The panel is intentionally UI-only: it renders editable domain fields and calls a
save callback provided by a controller-backed view. It never imports persistence
or infrastructure and never mutates domain objects directly.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from enum import Enum
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.technical_visibility import is_technical_field


class InspectorPanel(QWidget):
    """Contextual right-side editor with Save/Revert/Copy ID affordances."""

    def __init__(self, title: str = "Inspector", parent=None):
        super().__init__(parent)
        self._fields: dict[str, QWidget] = {}
        self._initial: dict[str, Any] = {}
        self._on_save: Callable[[dict[str, Any]], Any] | None = None
        self._on_revert: Callable[[], None] | None = None
        self._object_id = ""
        self._advanced_mode = False

        layout = QVBoxLayout(self)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title)

        self.id_label = QLabel("ID: —")
        self.id_label.setTextInteractionFlags(self.id_label.textInteractionFlags() | self.id_label.textInteractionFlags())
        self.id_label.setVisible(False)
        layout.addWidget(self.id_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        self.form = QFormLayout()
        layout.addLayout(self.form)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Guardar")
        self.save_button.clicked.connect(self.save)
        self.revert_button = QPushButton("Revertir")
        self.revert_button.clicked.connect(self.revert)
        self.copy_id_button = QPushButton("Copiar ID")
        self.copy_id_button.clicked.connect(self.copy_id)
        self.copy_id_button.setVisible(False)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.revert_button)
        buttons.addWidget(self.copy_id_button)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.setMinimumWidth(360)
        self.clear("Selecciona un elemento")

    def clear(self, message: str = "Selecciona un elemento") -> None:
        self._clear_form()
        self._fields = {}
        self._initial = {}
        self._on_save = None
        self._on_revert = None
        self._object_id = ""
        self.title.setText("Inspector")
        self.id_label.setText(message)
        self.id_label.setVisible(False)
        self.status_label.setText("")
        self.status_label.setVisible(False)
        self.save_button.setEnabled(False)
        self.revert_button.setEnabled(False)
        self.copy_id_button.setEnabled(False)
        self.copy_id_button.setVisible(self._advanced_mode)

    def bind(
        self,
        *,
        title: str,
        object_id: str,
        fields: list[dict[str, Any]],
        on_save: Callable[[dict[str, Any]], Any],
        on_revert: Callable[[], None] | None = None,
    ) -> None:
        self._clear_form()
        self._fields = {}
        self._initial = {}
        self._on_save = on_save
        self._on_revert = on_revert
        self._object_id = object_id
        self.title.setText(title)
        self.status_label.setText("")
        self.status_label.setVisible(False)
        self.id_label.setText(f"ID: {object_id}")
        self.id_label.setVisible(self._advanced_mode)
        for spec in fields:
            name = spec["name"]
            if not self._advanced_mode and is_technical_field(name, spec.get("label")):
                continue
            value = spec.get("value", "")
            widget = self._make_widget(spec, value)
            self._fields[name] = widget
            self._initial[name] = self._normalise_value(value, spec.get("kind", "text"))
            self.form.addRow(spec.get("label", name), widget)
        self.save_button.setEnabled(True)
        self.revert_button.setEnabled(True)
        self.copy_id_button.setEnabled(bool(object_id) and self._advanced_mode)
        self.copy_id_button.setVisible(self._advanced_mode)

    def values(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for name, widget in self._fields.items():
            data[name] = self._widget_value(widget)
        return data

    def set_advanced_mode(self, enabled: bool) -> None:
        """Show/hide technical affordances; caller rebinds fields on refresh."""
        self._advanced_mode = bool(enabled)
        self.id_label.setVisible(self._advanced_mode and bool(self._object_id))
        self.copy_id_button.setVisible(self._advanced_mode)
        self.copy_id_button.setEnabled(self._advanced_mode and bool(self._object_id))

    def save(self) -> None:
        if self._on_save is None:
            return
        try:
            self._on_save(self.values())
            self.status_label.setText("Guardado")
            self.status_label.setVisible(True)
        except Exception as exc:  # UI boundary: no raw traceback to console
            self.status_label.setText(f"Error guardando: {exc}")
            self.status_label.setVisible(True)

    def revert(self) -> None:
        if self._on_revert is not None:
            self._on_revert()
            return
        for name, value in self._initial.items():
            widget = self._fields[name]
            self._set_widget_value(widget, value)

    def copy_id(self) -> None:
        if not self._object_id:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._object_id)

    def _clear_form(self) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)

    def _make_widget(self, spec: dict[str, Any], value: Any) -> QWidget:
        kind = spec.get("kind", "text")
        if kind == "combo":
            combo = QComboBox()
            options = [self._enum_text(v) for v in spec.get("options", [])]
            combo.addItems(options)
            text = self._enum_text(value)
            index = combo.findText(text)
            if index >= 0:
                combo.setCurrentIndex(index)
            return combo
        if kind in {"multiline", "json"}:
            edit = QTextEdit()
            edit.setMinimumHeight(70 if kind == "multiline" else 110)
            edit.setPlainText(self._format_value(value, kind))
            return edit
        if kind == "checkbox":
            checkbox = QCheckBox()
            checkbox.setChecked(bool(value))
            return checkbox
        edit = QLineEdit()
        edit.setText(self._format_value(value, kind))
        return edit

    def _widget_value(self, widget: QWidget) -> Any:
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QTextEdit):
            text = widget.toPlainText()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QLineEdit):
            return widget.text()
        return ""

    def _set_widget_value(self, widget: QWidget, value: Any) -> None:
        if isinstance(widget, QComboBox):
            idx = widget.findText(str(value))
            if idx >= 0:
                widget.setCurrentIndex(idx)
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(self._format_value(value, "json" if isinstance(value, (dict, list)) else "multiline"))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(self._format_value(value, "text"))

    def _format_value(self, value: Any, kind: str) -> str:
        if isinstance(value, Enum):
            return str(value.value)
        if kind == "json" or isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value or "")

    def _normalise_value(self, value: Any, kind: str) -> Any:
        if isinstance(value, Enum):
            return value.value
        return value

    def _enum_text(self, value: Any) -> str:
        return str(value.value) if isinstance(value, Enum) else str(value)
