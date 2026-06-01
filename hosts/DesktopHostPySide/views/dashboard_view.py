"""DashboardView — project counts and open/create actions (B27.1-T01)."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog
from hosts.DesktopHostPySide.app_context import AppContext

class DashboardView(QWidget):
    def __init__(self, ctx: AppContext, controller):
        super().__init__()
        self.ctx = ctx; self.controller = controller
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        btns = QHBoxLayout()
        btn_open = QPushButton("Abrir proyecto"); btn_open.clicked.connect(self._open)
        btn_create = QPushButton("Crear proyecto"); btn_create.clicked.connect(self._create)
        btns.addWidget(btn_open); btns.addWidget(btn_create); layout.addLayout(btns)

        self.counts_label = QLabel("Sin proyecto cargado")
        self.counts_label.setStyleSheet("font-size: 13px; padding: 10px;")
        layout.addWidget(self.counts_label)
        layout.addStretch()

    def refresh(self):
        try:
            c = self.controller.counts()
            if not c: self.counts_label.setText("Sin proyecto"); return
            t = f"<b>{c['name']}</b> — Schema v{c['schema']}<br><br>"
            t += f"Entidades: {c['entities']} | Relaciones: {c['relations']} | Candidates: {c['candidates']}<br>"
            t += f"Sesiones: {c['sessions']} | Campañas: {c['campaigns']}<br>"
            t += f"Secretos: {c['secrets']} | Pistas: {c['clues']}<br>"
            t += f"Facciones: {c['factions']} | Frentes: {c['fronts']} | Clocks: {c['clocks']}"
            self.counts_label.setText(t)
        except Exception: self.counts_label.setText("Error loading counts")

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "JSON (*.json)")
        if path:
            try: self.controller.open(path); self.refresh(); self.ctx.log("info", f"Opened {path}")
            except Exception as e: self.ctx.log("error", str(e))

    def _create(self):
        path, _ = QFileDialog.getSaveFileName(self, "Crear", "nuevo.json", "JSON (*.json)")
        if path:
            try: self.controller.create("Nuevo proyecto", path); self.controller.save(); self.refresh(); self.ctx.log("info", f"Created {path}")
            except Exception as e: self.ctx.log("error", str(e))
