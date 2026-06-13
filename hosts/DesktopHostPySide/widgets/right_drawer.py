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

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    INK_SOFT,
    INK_STRONG,
    LINE,
    LINE_STRONG,
    SURFACE,
    SURFACE_HI,
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
        self._parent_ref = parent
        self._target_width = self._compute_target_width()
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self.setFixedHeight(parent.height() if parent else 800)
        self.setStyleSheet(
            f"QFrame#rightDrawer {{ "
            f"background: {SURFACE}; "
            f"border-left: 2px solid {LINE_STRONG}; "
            f"border-radius: 0px; "
            f"}}"
        )

        # Root layout: header + scrollable content
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setStyleSheet(
            f"background: {SURFACE_HI}; border-bottom: 1px solid {LINE};"
        )
        header.setFixedHeight(48)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 7, 12, 7)

        self._title = QLabel("")
        self._title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {INK_STRONG}; letter-spacing: 0.3px; "
            f"background: transparent; border: none;"
        )
        h_layout.addWidget(self._title)
        h_layout.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE}; "
            f"border-radius: 15px; color: {INK_SOFT}; font-size: 13px; }} "
            f"QPushButton:hover {{ background: {SURFACE}; border-color: {GOLD}; color: {INK_STRONG}; }}"
        )
        self._close_btn.clicked.connect(self.close)
        self._close_btn.setVisible(False)
        h_layout.addWidget(self._close_btn)

        self._root.addWidget(header)

        # Scrollable content area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {SURFACE}; border: none; }} "
            f"QScrollArea > QWidget > QWidget {{ background: {SURFACE}; }}"
        )
        self._scroll.viewport().setStyleSheet(f"background: {SURFACE};")
        self._root.addWidget(self._scroll, stretch=1)

        # Initially hidden
        self._content: QWidget | None = None
        self._animation: QPropertyAnimation | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    def _cancel_animation(self):
        if self._animation is None:
            return
        animation = self._animation
        self._animation = None
        animation.stop()

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
        self._cancel_animation()

        # Remove old content
        if self._content is not None:
            old = self._content
            old.hide()
            taken = self._scroll.takeWidget()
            if taken is not None:
                old = taken
            if old is not None:
                old.setParent(self)
                old.deleteLater()

        self._content = widget
        self._scroll.setWidget(widget)
        self._title.setText(title)
        widget.show()

    def open(self):
        """Show the drawer with a slide-in animation."""
        self._cancel_animation()
        self.update_target_width()
        self._close_btn.setVisible(True)
        # If already visible with content, just ensure correct width (no re-animation)
        if self.isVisible() and self.maximumWidth() >= self._target_width - 10:
            self.setMinimumWidth(self._target_width)
            self.setMaximumWidth(self._target_width)
            self.show()
            self.raise_()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
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
        self._cancel_animation()

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
                if self._animation is not animation:
                    return
                self.setMinimumWidth(0)
                self.setMaximumWidth(0)
                self.hide()
                if self._content is not None:
                    old = self._content
                    old.hide()
                    taken = self._scroll.takeWidget()
                    if taken is not None:
                        old = taken
                    if old is not None:
                        old.setParent(self)
                        old.deleteLater()
                    self._content = None
                self._animation = None
            animation.finished.connect(finish_close)
        else:
            def finish_open():
                if self._animation is animation:
                    self._animation = None
            animation.finished.connect(finish_open)
        animation.start()

    def keyPressEvent(self, event):
        """Close on Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
