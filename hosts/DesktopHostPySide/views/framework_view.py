from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton
from hosts.DesktopHostPySide.app_context import AppContext

class FrameworkView(QWidget):
    def __init__(self, ctx, ctrl): super().__init__(); self.ctx=ctx; self.ctrl=ctrl; self._build()
    def _build(self):
        l=QVBoxLayout(self); btn=QPushButton("Refrescar"); btn.clicked.connect(self.refresh); l.addWidget(btn)
        self.t=QTableWidget(); self.t.setColumnCount(3); self.t.setHorizontalHeaderLabels(["ID","Name","Active"]); l.addWidget(self.t)
    def refresh(self):
        fws=self.ctrl.list_all(); self.t.setRowCount(len(fws))
        for i,f in enumerate(fws): self.t.setItem(i,0,QTableWidgetItem(f.id[:12])); self.t.setItem(i,1,QTableWidgetItem(f.name)); self.t.setItem(i,2,QTableWidgetItem(str(f.active))); self.t.resizeColumnsToContents()
