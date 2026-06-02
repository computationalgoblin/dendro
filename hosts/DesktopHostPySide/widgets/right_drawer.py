"""RightDrawer — Slide-in panel for B31 immersive UX.

Replaces QDialog editing with a right-side drawer that opens
inside the main window with a smooth animation.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class RightDrawer(QFrame):
    """Reusable right-side drawer panel.

    Usage:
        drawer = RightDrawer(parent)
        # Set content:
        drawer.set_content(my_widget)
        drawer.open()
        # or close:
        drawer.close()
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("rightDrawer")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._target_width = 440
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self.setFixedHeight(parent.height() if parent else 800)
        self.setStyleSheet(
            "QFrame#rightDrawer { "
            "background: #131820; "
            "border-left: 1px solid #252D3B; "
            "border-radius: 0px; "
            "}"
        )

        # Root layout: header + scrollable content
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setStyleSheet("background: #0D1017; border-bottom: 1px solid #1E2530;")
        header.setFixedHeight(44)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 6, 14, 6)

        self._title = QLabel("")
        self._title.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #ECEFF4; "
            "background: transparent; border: none;"
        )
        h_layout.addWidget(self._title)
        h_layout.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #2B3546; "
            "border-radius: 6px; color: #8993A5; font-size: 14px; } "
            "QPushButton:hover { background: #1A2030; color: #CDD5E0; }"
        )
        self._close_btn.clicked.connect(self.close)
        h_layout.addWidget(self._close_btn)

        self._root.addWidget(header)

        # Scrollable content area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("background: transparent;")
        self._root.addWidget(self._scroll, stretch=1)

        # Initially hidden
        self._content: QWidget | None = None
        self._animation: QPropertyAnimation | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    def set_content(self, widget: QWidget, title: str = ""):
        """Set the drawer content widget."""
        # Remove old content
        if self._content is not None:
            old = self._scroll.takeWidget()
            if old:
                old.deleteLater()

        self._content = widget
        self._scroll.setWidget(widget)
        self._title.setText(title)

    def open(self):
        """Show the drawer with a slide-in animation."""
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._animate_width(self.maximumWidth(), self._target_width)

    def close(self):
        """Hide the drawer with a slide-out animation."""
        if not self.isVisible():
            return
        self._animate_width(self.maximumWidth(), 0, cleanup=True)

    def _animate_width(self, start: int, end: int, *, cleanup: bool = False):
        if self._animation is not None:
            self._animation.stop()
        animation = QPropertyAnimation(self, b"maximumWidth")
        animation.setDuration(180)
        animation.setStartValue(max(0, int(start)))
        animation.setEndValue(max(0, int(end)))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation = animation

        if cleanup:
            def finish_close():
                self.hide()
                if self._content is not None:
                    old = self._scroll.takeWidget()
                    if old:
                        old.deleteLater()
                    self._content = None
            animation.finished.connect(finish_close)
        animation.start()

    def keyPressEvent(self, event):
        """Close on Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
