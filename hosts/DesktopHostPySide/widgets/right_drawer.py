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

from hosts.DesktopHostPySide.widgets.design_system import fade_in


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
        self._parent_ref = parent
        self._target_width = self._compute_target_width()
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self.setFixedHeight(parent.height() if parent else 800)
        self.setStyleSheet(
            "QFrame#rightDrawer { "
            "background: #F8F6ED; "
            "border-left: 1px solid #D8D6C8; "
            "border-radius: 0px; "
            "}"
        )

        # Root layout: header + scrollable content
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setStyleSheet("background: #EEECDD; border-bottom: 1px solid #D8D6C8;")
        header.setFixedHeight(44)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 6, 14, 6)

        self._title = QLabel("")
        self._title.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #5C5A3E; "
            "background: transparent; border: none;"
        )
        h_layout.addWidget(self._title)
        h_layout.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #D0CCB8; "
            "border-radius: 6px; color: #6F6A42; font-size: 14px; } "
            "QPushButton:hover { background: #F8F5EA; color: #504B2E; }"
        )
        self._close_btn.clicked.connect(self.close)
        self._close_btn.setVisible(False)
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

    def _compute_target_width(self) -> int:
        """Compute proportional drawer width: 42% of parent, clamped to [380, 620]."""
        pw = 0
        if self._parent_ref is not None:
            pw = self._parent_ref.width()
        # Before first layout pass, parent.width() is 0 — fall back to screen or minimum
        if pw < 200:
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    pw = screen.availableGeometry().width()
            if pw < 200:
                pw = 1180  # MainWindow minimum size fallback
        target = int(pw * 0.42)
        return max(380, min(620, target))

    def update_target_width(self):
        """Recalculate target width (call on parent resize)."""
        self._target_width = self._compute_target_width()

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
        fade_in(widget, duration_ms=180, start_opacity=0.0)

    def open(self):
        """Show the drawer with a slide-in animation."""
        self.update_target_width()
        self._close_btn.setVisible(True)
        # If already visible with content, just ensure correct width (no re-animation)
        if self.isVisible() and self.maximumWidth() >= self._target_width - 10:
            return
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        # Animate both min and max width together so the drawer is always [min, max]
        self._animate_width(0, self._target_width)

    def close(self):
        """Hide the drawer with a slide-out animation."""
        if not self.isVisible():
            return
        self._close_btn.setVisible(False)
        self._animate_width(self.maximumWidth(), 0, cleanup=True)

    def _animate_width(self, start: int, end: int, *, cleanup: bool = False):
        if self._animation is not None:
            self._animation.stop()

        # Animate maximumWidth
        animation = QPropertyAnimation(self, b"maximumWidth")
        animation.setDuration(300)
        animation.setStartValue(max(0, int(start)))
        animation.setEndValue(max(0, int(end)))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation = animation

        # Keep minimumWidth in lockstep so the drawer can't collapse to 0 while open
        if end > 0:
            self.setMinimumWidth(max(0, int(start)))
            animation.valueChanged.connect(
                lambda v: self.setMinimumWidth(max(0, int(v)))
            )

        if cleanup:
            def finish_close():
                self.setMinimumWidth(0)
                self.setMaximumWidth(0)
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
