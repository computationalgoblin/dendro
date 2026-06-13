"""Global tooltip suppression for the desktop host.

Some Qt styles render tooltips as black popup windows. In the beta Creation
workspace those popups are distracting during selection and text editing, so
the host suppresses tooltip events centrally.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QToolTip


class TooltipSuppressor(QObject):
    """Event filter that prevents Qt tooltip popups from being shown."""

    _HIDE_EVENT_TYPES = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.KeyPress,
        QEvent.Type.FocusIn,
        QEvent.Type.FocusOut,
        QEvent.Type.WindowDeactivate,
    }

    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        event_type = event.type()
        if event_type == QEvent.Type.ToolTip:
            QToolTip.hideText()
            return True
        if event_type in self._HIDE_EVENT_TYPES:
            QToolTip.hideText()
        return super().eventFilter(watched, event)


def install_tooltip_suppression(app: QApplication | None = None) -> TooltipSuppressor | None:
    app = app or QApplication.instance()
    if app is None:
        return None
    existing = getattr(app, "_dendro_tooltip_suppressor", None)
    if isinstance(existing, TooltipSuppressor):
        return existing
    suppressor = TooltipSuppressor(app)
    app.installEventFilter(suppressor)
    setattr(app, "_dendro_tooltip_suppressor", suppressor)
    return suppressor


__all__ = ["TooltipSuppressor", "install_tooltip_suppression"]
