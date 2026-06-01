"""WritingView — tree widget (B27.2-T09)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout,
                                QLineEdit, QDialog, QFormLayout, QDialogButtonBox, QComboBox)
from hosts.DesktopHostPySide.app_context import AppContext
from packages.domain.result import Error

class WritingView(QWidget):
    def __init__(self, ctx: AppContext, wc): super().__init__(); self.ctx = ctx; self.wc = wc; self._build()
    def _build(self):
        l = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_create = QPushButton("Crear unidad"); btn_create.clicked.connect(self._create); act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar"); btn_refresh.clicked.connect(self.refresh); act.addWidget(btn_refresh)
        l.addLayout(act)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Title","Type","State"]); l.addWidget(self.tree)

    def refresh(self):
        self.tree.clear()
        units = self.wc.list_all()
        items = {}
        for u in units:
            item = QTreeWidgetItem([u.title, u.unit_type.value if hasattr(u.unit_type,'value') else str(u.unit_type),
                                    u.revision_state.value if hasattr(u.revision_state,'value') else str(u.revision_state)])
            pid = u.parent_unit_id
            if pid and pid in items: items[pid].addChild(item)
            else: self.tree.addTopLevelItem(item)
            items[u.id] = item
        self.tree.expandAll()

    def _create(self):
        dlg = QDialog(self); form = QFormLayout(dlg)
        title = QLineEdit(); type_cb = QComboBox(); type_cb.addItems(["historia","arco","capitulo","escena"])
        form.addRow("Title:", title); form.addRow("Type:", type_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            r = self.wc.create({"title": title.text(), "unit_type": type_cb.currentText()})
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Writing unit created" if not isinstance(r, Error) else r.error)
            self.refresh()
