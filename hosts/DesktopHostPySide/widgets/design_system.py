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
    background: #101319;
    color: #ECEFF4;
    font-family: "Segoe UI", "Inter", "Arial";
    font-size: 13px;
}
QListWidget {
    background: #0B0E13;
    border: none;
    padding: 10px;
    outline: 0;
}
QListWidget::item {
    padding: 12px 14px;
    margin: 4px 0;
    border-radius: 10px;
    color: #B7C0CC;
}
QListWidget::item:selected {
    background: #263244;
    color: #FFFFFF;
}
QPushButton {
    background: #273142;
    border: 1px solid #38465D;
    border-radius: 10px;
    padding: 8px 12px;
    color: #ECEFF4;
}
QPushButton:hover { background: #334158; }
QPushButton:pressed { background: #1F2938; }
QPushButton#primaryButton {
    background: #5B7CFA;
    border: 1px solid #7691FF;
    color: white;
    font-weight: 600;
}
QLabel#mutedLabel { color: #8993A5; }
QLabel#sectionTitle { font-size: 18px; font-weight: 700; }
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QTableWidget {
    background: #151A23;
    border: 1px solid #2D3748;
    border-radius: 8px;
    color: #ECEFF4;
    padding: 6px;
}
QTabWidget::pane { border: 1px solid #252D3B; border-radius: 12px; }
QTabBar::tab {
    background: #151A23;
    color: #AAB4C3;
    padding: 8px 14px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #263244; color: white; }
/* B31: subtle scrollbars for studio feel */
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #2A3344; border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #3A4558; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent; height: 8px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: #2A3344; border-radius: 4px; min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #3A4558; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""


class Card(QFrame):
    """Soft bordered card used by normal-mode product UI."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame#card { background: #161B25; border: 1px solid #2B3546; "
            "border-radius: 14px; }"
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
            "neutral": ("#2A3342", "#C9D2E3"),
            "info": ("#1D3B53", "#9ED8FF"),
            "success": ("#1D4532", "#9FF0BD"),
            "warning": ("#51421D", "#FFE08A"),
            "danger": ("#50262C", "#FFB3BF"),
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
            "QFrame#card { background: #121720; border: 1px dashed #344157; "
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
