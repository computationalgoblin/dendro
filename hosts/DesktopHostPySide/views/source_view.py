from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton


class SourceView(QWidget):
    def __init__(self, ctx, ctrl):
        super().__init__()
        self.ctx = ctx
        self.ctrl = ctrl
        self._build()

    def _build(self):
        l = QVBoxLayout(self)
        btn = QPushButton("Refrescar")
        btn.clicked.connect(self.refresh)
        l.addWidget(btn)
        self.t = QTableWidget()
        self.t.setColumnCount(3)
        self.t.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo"])
        l.addWidget(self.t)

    def refresh(self):
        srcs = self.ctrl.list_all()
        self.t.setRowCount(len(srcs))
        for i, source in enumerate(srcs):
            source_type = getattr(source.source_type, "value", str(source.source_type))
            self.t.setItem(i, 0, QTableWidgetItem(source.id[:12]))
            self.t.setItem(i, 1, QTableWidgetItem(getattr(source, "name", "")))
            self.t.setItem(i, 2, QTableWidgetItem(source_type))
        self.t.resizeColumnsToContents()
