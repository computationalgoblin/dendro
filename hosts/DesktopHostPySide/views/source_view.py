from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton
from hosts.DesktopHostPySide.app_context import AppContext

class SourceView(QWidget):
    def __init__(self, ctx, ctrl): super().__init__(); self.ctx=ctx; self.ctrl=ctrl; self._build()
    def _build(self):
        l=QVBoxLayout(self); btn=QPushButton("Refrescar"); btn.clicked.connect(self.refresh); l.addWidget(btn)
        self.t=QTableWidget(); self.t.setColumnCount(3); self.t.setHorizontalHeaderLabels(["ID","Title","Type"]); l.addWidget(self.t)
    def refresh(self):
        srcs=self.ctrl.list_all(); self.t.setRowCount(len(srcs))
        for i,s in enumerate(srcs): self.t.setItem(i,0,QTableWidgetItem(s.id[:12])); self.t.setItem(i,1,QTableWidgetItem(s.title)); self.t.setItem(i,2,QTableWidgetItem(s.source_type.value if hasattr(s.source_type,'value') else str(s.source_type))); self.t.resizeColumnsToContents()
