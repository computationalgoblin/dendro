"""CandidateView — inbox with accept/reject and B31 technical visibility."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.candidate_controller import CandidateController
from hosts.DesktopHostPySide.widgets.technical_visibility import set_columns_visible
from packages.domain.result import Error


class CandidateView(QWidget):
    def __init__(self, ctx: AppContext, cc: CandidateController):
        super().__init__()
        self.ctx = ctx
        self.cc = cc
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_refresh = QPushButton("Refrescar")
        btn_refresh.clicked.connect(self.refresh)
        act.addWidget(btn_refresh)
        layout.addLayout(act)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Título", "Tipo", "Estado", "Origen"])
        self.table.itemSelectionChanged.connect(self._show_detail)
        layout.addWidget(self.table)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(140)
        layout.addWidget(self.detail)

        btns = QHBoxLayout()
        btn_accept = QPushButton("Aceptar")
        btn_accept.clicked.connect(self._accept)
        btns.addWidget(btn_accept)
        btn_reject = QPushButton("Rechazar")
        btn_reject.clicked.connect(self._reject)
        btns.addWidget(btn_reject)
        layout.addLayout(btns)
        self.set_advanced_mode(self.ctx.advanced_mode)

    def set_advanced_mode(self, enabled: bool):
        set_columns_visible(self.table, [0, 4], bool(enabled))
        if not enabled and self.detail.toPlainText().startswith("Datos técnicos"):
            self.detail.clear()

    def refresh(self):
        cands = self.cc.list_all()
        self.table.setRowCount(len(cands))
        for i, candidate in enumerate(cands):
            id_item = QTableWidgetItem(candidate.id[:12])
            id_item.setData(Qt.ItemDataRole.UserRole, candidate.id)
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, QTableWidgetItem(candidate.title))
            self.table.setItem(i, 2, QTableWidgetItem(candidate.candidate_type.value))
            self.table.setItem(i, 3, QTableWidgetItem(candidate.state.value))
            self.table.setItem(i, 4, QTableWidgetItem(candidate.source or ""))
        self.table.resizeColumnsToContents()
        self.set_advanced_mode(self.ctx.advanced_mode)

    def _selected_candidate_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _show_detail(self):
        candidate_id = self._selected_candidate_id()
        if not candidate_id:
            return
        for candidate in self.cc.list_all():
            if candidate.id == candidate_id:
                self.ctx.selected_candidate_id = candidate.id
                if self.ctx.advanced_mode:
                    data = str(candidate.proposed_data) if candidate.proposed_data else "(sin datos)"
                    self.detail.setText(
                        "Datos técnicos — Modo avanzado\n"
                        f"Title: {candidate.title}\n"
                        f"Type: {candidate.candidate_type.value}\n"
                        f"State: {candidate.state.value}\n"
                        f"Source: {candidate.source or '?'}\n"
                        f"Source ID: {candidate.source_id or '?'}\n"
                        f"Confidence: {candidate.confidence}\n"
                        f"Metadata: {candidate.metadata}\n\n"
                        f"Data: {data}"
                    )
                else:
                    self.detail.setText(
                        f"{candidate.title}\n"
                        f"Tipo: {candidate.candidate_type.value}\n"
                        f"Estado: {candidate.state.value}\n"
                        f"Confianza: {candidate.confidence:.0%}\n\n"
                        "Aceptar convierte este candidato mediante el servicio correspondiente."
                    )
                break

    def _accept(self):
        if self.ctx.selected_candidate_id:
            result = self.cc.accept(self.ctx.selected_candidate_id)
            self.ctx.log("info" if not isinstance(result, Error) else "error", "Accepted" if not isinstance(result, Error) else result.error)
            self.refresh()

    def _reject(self):
        if self.ctx.selected_candidate_id:
            self.cc.reject(self.ctx.selected_candidate_id)
            self.ctx.log("info", "Rejected")
            self.refresh()
