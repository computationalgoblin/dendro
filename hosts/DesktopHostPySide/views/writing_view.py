"""WritingView — tree widget with drawer-based editing (B31-T02)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerForm
from packages.domain.result import Error


class WritingCreateForm(DrawerForm):
    """Create writing unit form for RightDrawer."""

    def __init__(self, ctx, wc, refresh_cb, parent=None):
        self._wc = wc
        self._refresh_cb = refresh_cb
        super().__init__(ctx, title="Crear unidad de escritura", parent=parent)
        self._title_input = QLineEdit()
        self._type_cb = QComboBox()
        self._type_cb.addItems(["historia", "arco", "capitulo", "escena"])
        self.form_layout.addRow("Título:", self._title_input)
        self.form_layout.addRow("Tipo:", self._type_cb)

    def _on_accept(self):
        title = self._title_input.text().strip()
        if not title:
            return
        r = self._wc.create({"title": title, "unit_type": self._type_cb.currentText()})
        if isinstance(r, Error):
            self.ctx.log("error", r.error)
        else:
            self.ctx.log("info", "Unidad de escritura creada")
            self._refresh_cb()
        self._close_drawer()


class WritingView(QWidget):
    def __init__(self, ctx: AppContext, wc):
        super().__init__()
        self.ctx = ctx
        self.wc = wc
        self._build()

    def _build(self):
        l = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_create = QPushButton("Crear unidad")
        btn_create.clicked.connect(self._create)
        act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar")
        btn_refresh.clicked.connect(self.refresh)
        act.addWidget(btn_refresh)
        l.addLayout(act)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Título", "Tipo", "Estado"])
        l.addWidget(self.tree)

    def refresh(self):
        self.tree.clear()
        units = self.wc.list_all()
        items = {}
        for u in units:
            item = QTreeWidgetItem([
                u.title,
                u.unit_type.value if hasattr(u.unit_type, "value") else str(u.unit_type),
                u.revision_state.value if hasattr(u.revision_state, "value") else str(u.revision_state),
            ])
            pid = u.parent_unit_id
            if pid and pid in items:
                items[pid].addChild(item)
            else:
                self.tree.addTopLevelItem(item)
            items[u.id] = item
        self.tree.expandAll()

    def _create(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = WritingCreateForm(self.ctx, self.wc, self.refresh)
        drawer.set_content(form, title="Crear unidad de escritura")
        drawer.open()
