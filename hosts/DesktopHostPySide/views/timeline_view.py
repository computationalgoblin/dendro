"""TimelineView — timeline events with drawer-based creation (B31-T02)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerForm
from packages.domain.result import Error


class TimelineCreateForm(DrawerForm):
    """Create timeline event form for RightDrawer."""

    def __init__(self, ctx, ctrl, refresh_cb, parent=None):
        self._ctrl = ctrl
        self._refresh_cb = refresh_cb
        super().__init__(ctx, title="Crear evento", parent=parent)
        self._title = QLineEdit()
        self._date = QLineEdit()
        self.form_layout.addRow("Título:", self._title)
        self.form_layout.addRow("Fecha:", self._date)

    def _on_accept(self):
        title = self._title.text().strip()
        if not title:
            return
        r = self._ctrl.create({"title": title, "event_date": self._date.text()})
        if isinstance(r, Error):
            self.ctx.log("error", r.error)
        else:
            self.ctx.log("info", "Evento creado")
            self._refresh_cb()
        self._close_drawer()


class TimelineView(QWidget):
    def __init__(self, ctx, ctrl):
        super().__init__()
        self.ctx = ctx
        self.ctrl = ctrl
        self._build()

    def _build(self):
        l = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_c = QPushButton("Crear evento")
        btn_c.clicked.connect(self._create)
        act.addWidget(btn_c)
        btn_r = QPushButton("Refrescar")
        btn_r.clicked.connect(self.refresh)
        act.addWidget(btn_r)
        l.addLayout(act)
        self.t = QTableWidget()
        self.t.setColumnCount(4)
        self.t.setHorizontalHeaderLabels(["ID", "Título", "Fecha", "Orden"])
        l.addWidget(self.t)

    def refresh(self):
        evs = self.ctrl.list_all()
        self.t.setRowCount(len(evs))
        for i, e in enumerate(evs):
            self.t.setItem(i, 0, QTableWidgetItem(e.id[:12]))
            self.t.setItem(i, 1, QTableWidgetItem(e.title))
            self.t.setItem(i, 2, QTableWidgetItem(e.event_date[:16] if hasattr(e, "event_date") else ""))
            self.t.setItem(i, 3, QTableWidgetItem(str(getattr(e, "partial_order", "?"))))
        self.t.resizeColumnsToContents()

    def _create(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = TimelineCreateForm(self.ctx, self.ctrl, self.refresh)
        drawer.set_content(form, title="Crear evento")
        drawer.open()
