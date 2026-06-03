"""Drawer forms — reusable inline form widgets for RightDrawer.

These replace QDialog-based forms with drawer-compatible widgets.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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


class DrawerForm(QWidget):
    """Base form widget for RightDrawer content.

    Provides a standard layout with title, form fields, and
    Accept/Cancel buttons. When accepted, calls _on_accept().
    When cancelled, closes the drawer.
    """

    def __init__(self, ctx, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._title = title
        self._build_base()

    def _build_base(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        if self._title:
            lbl = QLabel(self._title)
            lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #5C5A3E;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(10)
        layout.addLayout(self.form_layout)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #D0CCB8; "
            "border-radius: 8px; padding: 8px 16px; color: #6F6A42; } "
            "QPushButton:hover { background: #F8F5EA; }"
        )
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._accept_btn = QPushButton("Guardar")
        self._accept_btn.setObjectName("primaryButton")
        self._accept_btn.clicked.connect(self._on_accept)
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._accept_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

    def _on_accept(self):
        """Override in subclass. Called when user clicks Guardar."""
        pass

    def _on_cancel(self):
        """Close the drawer."""
        if self.ctx.drawer:
            self.ctx.drawer.close()

    def _close_drawer(self):
        if self.ctx.drawer:
            self.ctx.drawer.close()


class DrawerTextPrompt(DrawerForm):
    """One-field text prompt inside RightDrawer."""

    def __init__(self, ctx, title: str, label: str, on_accept, *, default: str = "", parent: QWidget | None = None):
        self._callback = on_accept
        super().__init__(ctx, title=title, parent=parent)
        self.input = QLineEdit(default)
        self.form_layout.addRow(label, self.input)

    def _on_accept(self):
        text = self.input.text().strip()
        if text:
            self._callback(text)
        self._close_drawer()


class DrawerSelectPrompt(DrawerForm):
    """Single select prompt inside RightDrawer.

    options are tuples of (label, value). Labels must be human-readable.
    """

    def __init__(self, ctx, title: str, label: str, options, on_accept, parent: QWidget | None = None):
        self._callback = on_accept
        self._options = list(options)
        super().__init__(ctx, title=title, parent=parent)
        self.combo = QComboBox()
        for option_label, value in self._options:
            self.combo.addItem(str(option_label), value)
        self.form_layout.addRow(label, self.combo)

    def _on_accept(self):
        self._callback(self.combo.currentData())
        self._close_drawer()
