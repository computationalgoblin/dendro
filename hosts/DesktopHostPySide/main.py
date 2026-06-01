"""DesktopHost minimum — PySide6 window for project create/open/save with counts (B27.0-T03)."""
from __future__ import annotations
import sys, os
from pathlib import Path

try:
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                    QHBoxLayout, QPushButton, QLabel, QTextEdit, QFileDialog, QMessageBox)
    from PySide6.QtCore import Qt
except ImportError:
    print("PySide6 not installed. Run: pip install narrative-architect[desktop]")
    print("Or: pip install PySide6>=6.7.0")
    sys.exit(1)

from packages.application.project_service import ProjectService
from packages.persistence.store import ProjectStore

class ProjectController:
    def __init__(self):
        self.store = ProjectStore()
        self.ps = ProjectService(store=self.store)
        self.current_path = None

    def open(self, path: str):
        result = self.ps.open(Path(path))
        if hasattr(result, 'error'):
            raise ValueError(f"Cannot open project: {result.error}")
        self.current_path = path

    def create(self, name: str, path: str):
        self.ps.create(name=name)
        self.current_path = path

    def save(self):
        if self.current_path:
            self.ps.save(Path(self.current_path))

    @property
    def project(self):
        return self.ps.active_project

    def counts(self) -> dict:
        p = self.project
        if p is None: return {}
        return {
            "name": p.name, "schema": getattr(p, 'schema_version', '?'),
            "entities": len(getattr(p, 'entities', [])),
            "relations": len(getattr(p, 'relations', [])),
            "candidates": len(getattr(p, 'candidates', [])),
            "sessions": len(getattr(p, 'sessions', [])),
            "campaigns": len(getattr(p, 'campaigns', [])),
            "secrets": len(getattr(p, 'secrets', [])),
            "factions": len(getattr(p, 'factions', [])),
            "clues": len(getattr(p, 'clues', [])),
            "fronts": len(getattr(p, 'fronts', [])),
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Narrative Architect — Desktop Host")
        self.setMinimumSize(500, 400)
        self.controller = ProjectController()
        self._build()
        self._refresh()

    def _build(self):
        cw = QWidget(); self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)

        btns = QHBoxLayout()
        self.btn_open = QPushButton("Abrir proyecto"); self.btn_open.clicked.connect(self._open)
        self.btn_create = QPushButton("Crear proyecto"); self.btn_create.clicked.connect(self._create)
        self.btn_save = QPushButton("Guardar"); self.btn_save.clicked.connect(self._save)
        btns.addWidget(self.btn_open); btns.addWidget(self.btn_create); btns.addWidget(self.btn_save)
        layout.addLayout(btns)

        self.counts_label = QLabel("Sin proyecto cargado"); layout.addWidget(self.counts_label)

        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(150)
        layout.addWidget(self.log)

    def _refresh(self):
        try:
            c = self.controller.counts()
            if not c:
                self.counts_label.setText("Sin proyecto cargado")
                return
            text = f"Proyecto: {c['name']}\nSchema: v{c['schema']}\n"
            text += f"Entidades: {c['entities']} | Relaciones: {c['relations']} | Candidates: {c['candidates']}\n"
            text += f"Sesiones: {c['sessions']} | Campañas: {c['campaigns']} | Secretos: {c['secrets']}\n"
            text += f"Facciones: {c['factions']} | Pistas: {c['clues']} | Frentes: {c['fronts']}"
            self.counts_label.setText(text)
            if self.controller.current_path:
                self.setWindowTitle(f"Narrative Architect — {self.controller.current_path}")
            self._log(f"Refreshed: {c['name']} (schema v{c['schema']})")
        except Exception as e:
            self._log(f"Error: {e}")

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", "JSON Files (*.json);;All Files (*)")
        if path:
            try:
                self.controller.open(path)
                self._refresh()
                self._log(f"Opened: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _create(self):
        name = "NuevoProyecto"
        path, _ = QFileDialog.getSaveFileName(self, "Crear proyecto", "nuevo_proyecto.json", "JSON Files (*.json)")
        if path:
            try:
                self.controller.create(name, path)
                self.controller.save()
                self._refresh()
                self._log(f"Created: {name} at {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _save(self):
        try:
            self.controller.save()
            self._log("Saved")
        except Exception as e:
            self._log(f"Save error: {e}")

    def _log(self, msg):
        self.log.append(msg)

def main():
    app = QApplication(sys.argv)
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
