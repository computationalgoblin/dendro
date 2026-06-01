"""ImportExportView — import baskets + controlled export (B27.3 bugbash)."""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.import_controller import ImportController
from packages.application.export_service import ExportService
from packages.application.entity_service import EntityService
from packages.application.session_service import SessionService
from packages.domain.result import Error


def _enum_text(value) -> str:
    return str(value.value) if isinstance(value, Enum) else str(value or "")


class ImportExportView(QWidget):
    def __init__(self, ctx: AppContext, controller):
        super().__init__()
        self.ctx = ctx
        self.controller = controller
        self.ic = ImportController(project_service=controller.ps)
        self.export = ExportService(
            project_service=controller.ps,
            entity_service=EntityService(controller.ps),
            session_service=SessionService(controller.ps),
        )
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        for label, handler in [
            ("Seleccionar TXT/PDF", self._pick),
            ("Aceptar candidate", self._accept),
            ("Rechazar candidate", self._reject),
            ("Refrescar", self.refresh),
            ("Export GM", lambda: self._export_all("gm")),
            ("Export Player", lambda: self._export_all("player")),
            ("Export Public", lambda: self._export_all("public")),
            ("Export entity/session/campaign", self._export_single),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            act.addWidget(btn)
        layout.addLayout(act)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Basket", "Source", "Segments", "Candidate", "Segment", "Type",
            "State", "Confidence", "Dup/Contr"
        ])
        self.table.itemSelectionChanged.connect(self._show_detail)
        layout.addWidget(self.table)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(220)
        layout.addWidget(self.detail)

    def _project(self):
        return self.controller.ps.active_project

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar", "", "Documentos (*.txt *.pdf)")
        if not path:
            return
        result = self.ic.import_document(path)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"Error: {result.error}")
        else:
            self.ctx.log("info", f"Import basket created: {result.value.id} ({Path(path).suffix.lower()})")
            self.refresh()

    def _basket_candidates(self, basket):
        """Return real B17 import candidates; keep defensive empty fallback."""
        return list(getattr(basket, "import_candidates", []) or [])

    def _rows(self):
        baskets = self.ic.list_baskets()
        if isinstance(baskets, Error):
            self.ctx.log("error", baskets.error)
            return []
        if hasattr(baskets, "value"):
            baskets = baskets.value
        rows = []
        for basket in baskets:
            for candidate in self._basket_candidates(basket):
                rows.append((basket, candidate))
        return rows

    def refresh(self):
        rows = self._rows()
        self.table.setRowCount(len(rows))
        for i, (basket, candidate) in enumerate(rows):
            basket_item = QTableWidgetItem(basket.id[:12])
            basket_item.setData(Qt.UserRole, basket.id)
            cand_item = QTableWidgetItem(candidate.id[:12])
            cand_item.setData(Qt.UserRole, candidate.id)
            segment_id = getattr(candidate, "segment_id", "") or ""
            review_state = getattr(candidate, "review_state", "")
            state_text = _enum_text(review_state)
            dup_count = len(getattr(candidate, "possible_duplicates", []) or [])
            contradiction_count = len(getattr(candidate, "possible_contradictions", []) or [])
            self.table.setItem(i, 0, basket_item)
            self.table.setItem(i, 1, QTableWidgetItem(str(getattr(basket, "source_id", "") or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(len(getattr(basket, "segments", []) or []))))
            self.table.setItem(i, 3, cand_item)
            self.table.setItem(i, 4, QTableWidgetItem(segment_id))
            self.table.setItem(i, 5, QTableWidgetItem(str(getattr(candidate, "candidate_type", "") or "")))
            self.table.setItem(i, 6, QTableWidgetItem(state_text))
            self.table.setItem(i, 7, QTableWidgetItem(f"{float(getattr(candidate, 'confidence', 0.0) or 0.0):.2f}"))
            self.table.setItem(i, 8, QTableWidgetItem(f"D:{dup_count} C:{contradiction_count}"))
        self.table.resizeColumnsToContents()

    def _selected_ids(self):
        row = self.table.currentRow()
        if row < 0:
            return None, None
        basket_id = self.table.item(row, 0).data(Qt.UserRole)
        candidate_id = self.table.item(row, 3).data(Qt.UserRole)
        return basket_id, candidate_id

    def _selected_candidate(self):
        basket_id, candidate_id = self._selected_ids()
        if not basket_id or not candidate_id:
            return None, None, None
        basket_result = self.ic.get_basket(basket_id)
        if isinstance(basket_result, Error):
            self.ctx.log("error", basket_result.error)
            return basket_id, candidate_id, None
        basket = basket_result.value
        for candidate in self._basket_candidates(basket):
            if candidate.id == candidate_id:
                return basket_id, candidate_id, candidate
        return basket_id, candidate_id, None

    def _show_detail(self):
        basket_id, candidate_id, candidate = self._selected_candidate()
        if not candidate:
            return
        review_state = getattr(candidate, "review_state", "")
        state_text = _enum_text(review_state)
        payload = getattr(candidate, "proposed_data", {}) or {}
        lines = [
            f"Basket: {basket_id}",
            f"Candidate: {candidate_id}",
            f"Type: {getattr(candidate, 'candidate_type', '')}",
            f"State: {state_text}",
            f"Source segment: {getattr(candidate, 'segment_id', '')}",
            f"Confidence: {getattr(candidate, 'confidence', '')}",
            f"Duplicates: {getattr(candidate, 'possible_duplicates', [])}",
            f"Contradictions: {getattr(candidate, 'possible_contradictions', [])}",
            "Payload:",
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        ]
        self.detail.setPlainText("\n".join(lines))

    def _accept(self):
        basket_id, candidate_id, _ = self._selected_candidate()
        if not basket_id or not candidate_id:
            self.ctx.log("error", "Selecciona un import candidate")
            return
        result = self.ic.accept(basket_id, candidate_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"Error: {result.error}")
        else:
            self.ctx.log("info", f"Import candidate accepted: {candidate_id}")
            self.refresh()

    def _reject(self):
        basket_id, candidate_id, _ = self._selected_candidate()
        if not basket_id or not candidate_id:
            self.ctx.log("error", "Selecciona un import candidate")
            return
        result = self.ic.reject(basket_id, candidate_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"Error: {result.error}")
        else:
            self.ctx.log("info", f"Import candidate rejected: {candidate_id}")
            self.refresh()

    def _export_all(self, audience):
        result = self.export.export_all(audience)
        if isinstance(result, Error):
            self.detail.setPlainText(f"Error: {result.error}")
        else:
            self.detail.setPlainText(str(result.value))

    def _export_single(self):
        kind, ok = QInputDialog.getItem(self, "Exportar", "Tipo:", ["entity", "session", "campaign"], 0, False)
        if not ok:
            return
        audience, ok = QInputDialog.getItem(self, "Exportar", "Audiencia:", ["gm", "player", "public"], 0, False)
        if not ok:
            return
        project = self._project()
        if project is None:
            self.detail.setPlainText("No active project")
            return
        if kind == "entity":
            options = [f"{entity.name} ({entity.id})" for entity in project.entities]
            item, ok = QInputDialog.getItem(self, "Entidad", "Selecciona:", options, 0, False)
            if not ok or not item:
                return
            entity_id = item[item.rfind("(") + 1 : -1]
            result = self.export.export_entity_profile(entity_id, audience)
        elif kind == "session":
            options = [f"{session.name} ({session.id})" for session in project.sessions]
            item, ok = QInputDialog.getItem(self, "Sesión", "Selecciona:", options, 0, False)
            if not ok or not item:
                return
            session_id = item[item.rfind("(") + 1 : -1]
            result = self.export.export_session_player_summary(session_id)
        else:
            options = [f"{campaign.name} ({campaign.id})" for campaign in project.campaigns]
            item, ok = QInputDialog.getItem(self, "Campaña", "Selecciona:", options, 0, False)
            if not ok or not item:
                return
            campaign_id = item[item.rfind("(") + 1 : -1]
            result = self.export.export_campaign_report(campaign_id, audience)
        if isinstance(result, Error):
            self.detail.setPlainText(f"Error: {result.error}")
        else:
            self.detail.setPlainText(str(result.value))
