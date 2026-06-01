from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton
from hosts.DesktopHostPySide.app_context import AppContext

class LayerView(QWidget):
    def __init__(self, ctx, ctrl): super().__init__(); self.ctx=ctx; self.ctrl=ctrl; self._build()
    def _build(self):
        l=QVBoxLayout(self); btn=QPushButton("Refrescar"); btn.clicked.connect(self.refresh); l.addWidget(btn)
        self.t=QTableWidget(); self.t.setColumnCount(3); self.t.setHorizontalHeaderLabels(["ID","Name","Visible"]); l.addWidget(self.t)
    def refresh(self):
        lays=self.ctrl.list_all(); self.t.setRowCount(len(lays))
        for i,la in enumerate(lays): self.t.setItem(i,0,QTableWidgetItem(la.id[:12])); self.t.setItem(i,1,QTableWidgetItem(la.name)); self.t.setItem(i,2,QTableWidgetItem(str(la.visible))); self.t.resizeColumnsToContents()
