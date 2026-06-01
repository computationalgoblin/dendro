from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QComboBox
from hosts.DesktopHostPySide.app_context import AppContext
from packages.domain.result import Error

class TimelineView(QWidget):
    def __init__(self, ctx, ctrl): super().__init__(); self.ctx=ctx; self.ctrl=ctrl; self._build()
    def _build(self):
        l=QVBoxLayout(self); act=QHBoxLayout()
        btn_c=QPushButton("Crear evento"); btn_c.clicked.connect(self._create); act.addWidget(btn_c)
        btn_r=QPushButton("Refrescar"); btn_r.clicked.connect(self.refresh); act.addWidget(btn_r); l.addLayout(act)
        self.t=QTableWidget(); self.t.setColumnCount(4); self.t.setHorizontalHeaderLabels(["ID","Title","Date","Order"]); l.addWidget(self.t)
    def refresh(self):
        evs=self.ctrl.list_all(); self.t.setRowCount(len(evs))
        for i,e in enumerate(evs):
            self.t.setItem(i,0,QTableWidgetItem(e.id[:12])); self.t.setItem(i,1,QTableWidgetItem(e.title))
            self.t.setItem(i,2,QTableWidgetItem(e.event_date[:16] if hasattr(e,'event_date') else ""))
            self.t.setItem(i,3,QTableWidgetItem(str(getattr(e,'partial_order','?')))); self.t.resizeColumnsToContents()
    def _create(self):
        dlg=QDialog(self); form=QFormLayout(dlg); title=QLineEdit(); date=QLineEdit()
        form.addRow("Title:",title); form.addRow("Date:",date)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject); form.addRow(btns)
        if dlg.exec():
            r=self.ctrl.create({"title":title.text(),"event_date":date.text()})
            self.ctx.log("info" if not isinstance(r,Error) else "error", f"Event created" if not isinstance(r,Error) else r.error); self.refresh()
