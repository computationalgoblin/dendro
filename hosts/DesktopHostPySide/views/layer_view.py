from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton


class LayerView(QWidget):
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
        self.t.setHorizontalHeaderLabels(["ID", "Nombre", "Visible"])
        l.addWidget(self.t)

    def refresh(self):
        layers = self.ctrl.list_all()
        self.t.setRowCount(len(layers))
        for i, layer in enumerate(layers):
            visible = getattr(layer, "is_visible", getattr(layer, "visible", True))
            self.t.setItem(i, 0, QTableWidgetItem(layer.id[:12]))
            self.t.setItem(i, 1, QTableWidgetItem(layer.name))
            self.t.setItem(i, 2, QTableWidgetItem("sí" if visible else "no"))
        self.t.resizeColumnsToContents()
