"""ImportExportView — visual import cards + advanced export/debug (B27.5-T07)."""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.import_controller import ImportController
from hosts.DesktopHostPySide.widgets.design_system import (
    AdvancedSection,
    Badge,
    Card,
    EmptyState,
    SectionHeader,
    enum_human,
    make_scroll_area,
)
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerForm
from packages.application.export_service import ExportService
from packages.domain.result import Error


def _enum_text(value) -> str:
    return str(value.value) if isinstance(value, Enum) else str(value or "")


def _candidate_title(candidate) -> str:
    payload = getattr(candidate, "proposed_data", {}) or {}
    name = payload.get("name") or payload.get("title") or getattr(candidate, "title", "") or "Propuesta sin nombre"
    ctype = enum_human(getattr(candidate, "candidate_type", "candidato"))
    return f"Posible {ctype.lower()}: {name}"


def _source_excerpt(candidate) -> str:
    payload = getattr(candidate, "proposed_data", {}) or {}
    for key in ["brief", "description", "text", "summary", "content"]:
        value = payload.get(key)
        if value:
            text = str(value).replace("\n", " ").strip()
            return text[:220] + ("…" if len(text) > 220 else "")
    return "Sin extracto visible. Activa Modo avanzado para ver datos técnicos."


class ImportExportView(QWidget):
    def __init__(self, ctx: AppContext, controller, export_service: ExportService | None = None):
        super().__init__()
        self.ctx = ctx
        self.controller = controller
        self.ic = ImportController(project_service=controller.ps)
        self.export = export_service
        self.selected_basket_id: str | None = None
        self.selected_candidate_id: str | None = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(SectionHeader(
            "Importación documental",
            "Revisa candidatos como tarjetas. IDs, segmentos y JSON quedan en Datos técnicos."
        ))

        act = QHBoxLayout()
        for label, handler, primary in [
            ("Seleccionar TXT/PDF", self._pick, True),
            ("Aceptar", self._accept, False),
            ("Rechazar", self._reject, False),
            ("Refrescar", self.refresh, False),
        ]:
            btn = QPushButton(label)
            if primary:
                btn.setObjectName("primaryButton")
            btn.clicked.connect(handler)
            act.addWidget(btn)
        act.addStretch()
        layout.addLayout(act)

        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setSpacing(12)
        layout.addWidget(make_scroll_area(self.cards_container), stretch=1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(150)
        layout.addWidget(self.detail)

        self.advanced = AdvancedSection("Datos técnicos / export")
        layout.addWidget(self.advanced)
        adv_actions = QHBoxLayout()
        for label, handler in [
            ("Exportar GM", lambda: self._export_all("gm")),
            ("Exportar jugadores", lambda: self._export_all("player")),
            ("Exportar público", lambda: self._export_all("public")),
            ("Exportar elemento", self._export_single),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            adv_actions.addWidget(btn)
        self.advanced.body_layout.addLayout(adv_actions)
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Basket", "Source", "Segments", "Candidate", "Segment", "Type",
            "State", "Confidence", "Dup/Contr"
        ])
        self.table.itemSelectionChanged.connect(self._show_detail_from_table)
        self.advanced.body_layout.addWidget(self.table)
        self.set_advanced_mode(self.ctx.advanced_mode)

    def set_advanced_mode(self, enabled: bool):
        self.advanced.setVisible(bool(enabled))
        if not enabled and self.detail.toPlainText().startswith("Datos técnicos"):
            self.detail.clear()

    def _project(self):
        return self.controller.ps.active_project

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar", "", "Documentos (*.txt *.pdf)")
        if not path:
            return
        result = self.ic.import_document(path)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"No se pudo importar el documento: {result.error}")
        else:
            self.ctx.log("info", f"Import basket created: {result.value.id} ({Path(path).suffix.lower()})")
            self.detail.setPlainText("Documento importado. Revisa las tarjetas de candidatos detectados.")
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
            candidates = self._basket_candidates(basket)
            if not candidates:
                rows.append((basket, None))
            for candidate in candidates:
                rows.append((basket, candidate))
        return rows

    def _clear_cards(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh(self):
        rows = self._rows()
        self._refresh_cards(rows)
        self._refresh_table(rows)

    def _refresh_cards(self, rows):
        self._clear_cards()
        if not rows:
            self.cards_grid.addWidget(EmptyState(
                "Sin importaciones",
                "Selecciona un TXT/PDF para detectar candidatos narrativos."
            ), 0, 0)
            return
        visible_idx = 0
        for basket, candidate in rows:
            if candidate is None:
                card = Card("Documento importado", "No hay candidatos detectados todavía.")
                card.add_text("La importación existe y se refresca usando el campo real de candidatos.", muted=True)
                self.cards_grid.addWidget(card, visible_idx // 2, visible_idx % 2)
                visible_idx += 1
                continue
            card = Card(_candidate_title(candidate), _source_excerpt(candidate))
            state_text = enum_human(getattr(candidate, "review_state", "pendiente"))
            confidence = float(getattr(candidate, "confidence", 0.0) or 0.0)
            row = card.add_row()
            row.addWidget(Badge(state_text, "info"))
            row.addWidget(Badge(f"Confianza {confidence:.0%}", "success" if confidence >= 0.7 else "warning"))
            row.addStretch()
            actions = card.add_row()
            btn_select = QPushButton("Ver")
            btn_select.clicked.connect(lambda _=False, b=basket.id, c=candidate.id: self._select_card(b, c))
            btn_accept = QPushButton("Aceptar")
            btn_accept.clicked.connect(lambda _=False, b=basket.id, c=candidate.id: self._accept_ids(b, c))
            btn_reject = QPushButton("Descartar")
            btn_reject.clicked.connect(lambda _=False, b=basket.id, c=candidate.id: self._reject_ids(b, c))
            for btn in [btn_select, btn_accept, btn_reject]:
                actions.addWidget(btn)
            actions.addStretch()
            self.cards_grid.addWidget(card, visible_idx // 2, visible_idx % 2)
            visible_idx += 1

    def _refresh_table(self, rows):
        real_rows = [(b, c) for b, c in rows if c is not None]
        self.table.setRowCount(len(real_rows))
        for i, (basket, candidate) in enumerate(real_rows):
            basket_item = QTableWidgetItem(basket.id[:12])
            basket_item.setData(Qt.ItemDataRole.UserRole, basket.id)
            cand_item = QTableWidgetItem(candidate.id[:12])
            cand_item.setData(Qt.ItemDataRole.UserRole, candidate.id)
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
            self.table.setItem(i, 5, QTableWidgetItem(enum_human(getattr(candidate, "candidate_type", ""))))
            self.table.setItem(i, 6, QTableWidgetItem(state_text))
            self.table.setItem(i, 7, QTableWidgetItem(f"{float(getattr(candidate, 'confidence', 0.0) or 0.0):.2f}"))
            self.table.setItem(i, 8, QTableWidgetItem(f"D:{dup_count} C:{contradiction_count}"))
        self.table.resizeColumnsToContents()

    def _select_card(self, basket_id: str, candidate_id: str):
        self.selected_basket_id = basket_id
        self.selected_candidate_id = candidate_id
        _, _, candidate = self._selected_candidate()
        if candidate:
            self._show_clean_detail(candidate)

    def _selected_ids(self):
        if self.selected_basket_id and self.selected_candidate_id:
            return self.selected_basket_id, self.selected_candidate_id
        row = self.table.currentRow()
        if row < 0:
            return None, None
        basket_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        candidate_id = self.table.item(row, 3).data(Qt.ItemDataRole.UserRole)
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

    def _show_clean_detail(self, candidate):
        lines = [
            _candidate_title(candidate),
            "",
            _source_excerpt(candidate),
            "",
            f"Estado: {enum_human(getattr(candidate, 'review_state', 'pendiente'))}",
            f"Confianza: {float(getattr(candidate, 'confidence', 0.0) or 0.0):.0%}",
            "",
            "Usa Aceptar o Descartar. Los datos técnicos están ocultos salvo en Modo avanzado.",
        ]
        self.detail.setPlainText("\n".join(lines))

    def _show_detail(self):
        """Backward-compatible hook used by desktop contract tests."""
        self._show_detail_from_table()

    def _show_detail_from_table(self):
        basket_id, candidate_id, candidate = self._selected_candidate()
        if not candidate:
            return
        if not self.ctx.advanced_mode:
            self._show_clean_detail(candidate)
            return
        review_state = getattr(candidate, "review_state", "")
        state_text = _enum_text(review_state)
        payload = getattr(candidate, "proposed_data", {}) or {}
        lines = [
            "Datos técnicos — Modo avanzado",
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
            self.ctx.log("error", "Selecciona un candidato")
            return
        self._accept_ids(basket_id, candidate_id)

    def _reject(self):
        basket_id, candidate_id, _ = self._selected_candidate()
        if not basket_id or not candidate_id:
            self.ctx.log("error", "Selecciona un candidato")
            return
        self._reject_ids(basket_id, candidate_id)

    def _accept_ids(self, basket_id: str, candidate_id: str):
        self.selected_basket_id = basket_id
        self.selected_candidate_id = candidate_id
        result = self.ic.accept(basket_id, candidate_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"No se pudo aceptar: {result.error}")
        else:
            self.ctx.log("info", "Candidato de importación aceptado")
            self.detail.setPlainText("Candidato aceptado.")
            self.refresh()

    def _reject_ids(self, basket_id: str, candidate_id: str):
        self.selected_basket_id = basket_id
        self.selected_candidate_id = candidate_id
        result = self.ic.reject(basket_id, candidate_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"No se pudo descartar: {result.error}")
        else:
            self.ctx.log("info", "Candidato de importación descartado")
            self.detail.setPlainText("Candidato descartado.")
            self.refresh()

    def _export_all(self, audience):
        if self.export is None:
            self.detail.setPlainText("Exportación no disponible en este contexto.")
            return
        result = self.export.export_all(audience)
        if isinstance(result, Error):
            self.detail.setPlainText(f"Error: {result.error}")
        else:
            self.detail.setPlainText(str(result.value))

    def _export_single(self):
        project = self._project()
        drawer = self.ctx.drawer
        if project is None:
            self.detail.setPlainText("No hay proyecto activo")
            return
        if self.export is None:
            self.detail.setPlainText("Exportación no disponible en este contexto.")
            return
        if drawer is None:
            return

        view = self

        class _ExportSingleForm(DrawerForm):
            def __init__(self, ctx):
                super().__init__(ctx, title="Exportar elemento")
                self.kind = QComboBox()
                self.kind.addItems(["entity", "session", "campaign"])
                self.audience = QComboBox()
                self.audience.addItems(["gm", "player", "public"])
                self.item = QComboBox()
                self.kind.currentTextChanged.connect(self._reload_items)
                self.form_layout.addRow("Tipo:", self.kind)
                self.form_layout.addRow("Audiencia:", self.audience)
                self.form_layout.addRow("Elemento:", self.item)
                self._reload_items()

            def _reload_items(self):
                self.item.clear()
                kind = self.kind.currentText()
                if kind == "entity":
                    for entity in project.entities:
                        self.item.addItem(entity.name, entity.id)
                elif kind == "session":
                    for session in project.sessions:
                        self.item.addItem(session.name, session.id)
                else:
                    for campaign in project.campaigns:
                        self.item.addItem(campaign.name, campaign.id)

            def _on_accept(self):
                kind = self.kind.currentText()
                audience = self.audience.currentText()
                item_id = self.item.currentData()
                if not item_id:
                    view.detail.setPlainText("No hay elemento seleccionable")
                    self._close_drawer()
                    return
                if kind == "entity":
                    result = view.export.export_entity_profile(item_id, audience)
                elif kind == "session":
                    result = view.export.export_session_player_summary(item_id)
                else:
                    result = view.export.export_campaign_report(item_id, audience)
                if isinstance(result, Error):
                    view.detail.setPlainText(f"Error: {result.error}")
                else:
                    view.detail.setPlainText(str(result.value))
                self._close_drawer()

        form = _ExportSingleForm(self.ctx)
        drawer.set_content(form, title="Exportar elemento")
        drawer.open()
