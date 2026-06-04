"""Minimal desktop design-system widgets for B27.5 UX redesign.

These widgets are intentionally presentation-only. They do not import persistence
or infrastructure and do not mutate domain objects directly.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #F7F5EA;
    color: #4F4D38;
    font-family: "Georgia", "Courier New", serif;
    font-size: 13px;
}
QPushButton {
    background: #F8F6ED;
    border: 1px solid #D6D2BF;
    border-radius: 10px;
    padding: 8px 12px;
    color: #5C5A3E;
}
QPushButton:hover { background: #FFFFFF; border-color: #AAA579; }
QPushButton:pressed { background: #E7E4D4; }
QPushButton#primaryButton {
    background: #7A733D;
    border: 1px solid #6C6536;
    color: #FFFDF5;
    font-weight: 600;
}
QLabel#mutedLabel { color: #7C806E; }
QLabel#sectionTitle {
    font-size: 18px;
    font-weight: 700;
    color: #5D603F;
    font-family: Georgia, "Courier New", serif;
}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QTableWidget {
    background: #FFFDF7;
    border: 1px solid #D8D6C8;
    border-radius: 8px;
    color: #4F4D38;
    padding: 8px 10px;
    min-height: 28px;
    selection-background-color: #B5BBA5;
    font-family: "Segoe UI", "Inter", "Arial";
}
QComboBox {
    min-height: 32px;
    padding: 6px 28px 6px 10px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #7C806E;
}
QComboBox QAbstractItemView {
    background: #FFFDF7;
    border: 1px solid #D8D6C8;
    border-radius: 6px;
    color: #4F4D38;
    selection-background-color: #D6D2BF;
    selection-color: #3A3826;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 6px 8px;
    min-height: 28px;
    color: #4F4D38;
}
QComboBox QAbstractItemView::item:hover {
    background: #ECE9DA;
}
QComboBox QAbstractItemView::item:selected {
    background: #D6D2BF;
    color: #3A3826;
}
QTextEdit, QPlainTextEdit {
    min-height: 60px;
}
QTabWidget::pane { border: 1px solid #D8D6C8; border-radius: 12px; background: #F8F6ED; }
QTabBar::tab {
    background: #ECE9DA;
    color: #777660;
    padding: 8px 14px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #FFFDF7; color: #5C5A3E; }
QTableWidget { gridline-color: #E1DEC9; }
QHeaderView::section { background: #ECE9DA; color: #5C5A3E; padding: 6px; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #C7C6B8; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #AFA77A; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; }
QScrollBar::handle:horizontal { background: #C7C6B8; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #AFA77A; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""


ICON_GLYPHS = {
    "settings": "⚙",
    "project": "◇",
    "creation": "✧",
    "gallery": "◌",
    "session": "☉",
    "back": "←",
    "close": "✕",
    "add": "+",
    "edit": "✎",
    "delete": "✕",
    "refresh": "↻",
    "save": "💾",
    "search": "⌕",
    "filter": "▽",
    "expand": "▾",
    "collapse": "▸",
    "worldbuilding": "🌐",
    "layers": "☰",
}


class Card(QFrame):
    """Soft bordered card used by normal-mode product UI."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame#card { background: #FFFDF7; border: 1px solid #D8D6C8; "
            "border-radius: 16px; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(8)
        if title:
            self.title = QLabel(title)
            self.title.setStyleSheet("font-size: 16px; font-weight: 700;")
            self.title.setWordWrap(True)
            self.layout.addWidget(self.title)
        if subtitle:
            self.subtitle = QLabel(subtitle)
            self.subtitle.setObjectName("mutedLabel")
            self.subtitle.setWordWrap(True)
            self.layout.addWidget(self.subtitle)

    def add_text(self, text: str, muted: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        if muted:
            label.setObjectName("mutedLabel")
        self.layout.addWidget(label)
        return label

    def add_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self.layout.addLayout(row)
        return row


class Badge(QLabel):
    """Small chip/badge for user-facing states."""

    def __init__(self, text: str, tone: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        colors = {
            "neutral": ("#E8E5D6", "#5C5A3E"),
            "info": ("#E2E6D8", "#5F6F4D"),
            "success": ("#E4EBDD", "#58744A"),
            "warning": ("#EFE3C7", "#8A6849"),
            "danger": ("#F0D8D0", "#8A4E43"),
        }
        bg, fg = colors.get(tone, colors["neutral"])
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 9px; "
            "padding: 3px 8px; font-size: 12px; font-weight: 600;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("mutedLabel")
            sub.setWordWrap(True)
            layout.addWidget(sub)


class EmptyState(Card):
    def __init__(self, title: str, message: str, parent: QWidget | None = None):
        super().__init__(title, message, parent)
        self.setStyleSheet(
            "QFrame#card { background: #F8F6ED; border: 1px dashed #C9C5B1; "
            "border-radius: 14px; }"
        )


class AdvancedSection(QWidget):
    """Collapsible container for technical details visible only in advanced mode."""

    def __init__(self, title: str = "Datos técnicos", parent: QWidget | None = None):
        super().__init__(parent)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.body = QWidget()
        self.body.setVisible(False)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 6, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.body.setVisible(checked)


def make_scroll_area(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    return area


def enum_human(value: Any) -> str:
    raw = getattr(value, "value", value)
    text = str(raw or "—")
    return text.replace("_", " ").replace("-", " ").strip().capitalize() or "—"


def human_ref(name: str | None, kind: str | None = None) -> str:
    clean_name = (name or "Sin nombre").strip() or "Sin nombre"
    clean_kind = (kind or "").strip()
    return f"{clean_name} · {clean_kind}" if clean_kind else clean_name


def join_human(items: Iterable[Any], empty: str = "—") -> str:
    values = [str(item) for item in items if str(item)]
    return ", ".join(values) if values else empty
