"""ImportExportView — visual import cards + advanced export/debug (B27.5-T07)."""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
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
    kind = _candidate_kind(candidate)
    name = payload.get("name") or payload.get("title") or payload.get("ring_name") or getattr(candidate, "title", "") or "Propuesta sin nombre"
    labels = {
        "entity": "Hoja",
        "branch": "Rama",
        "relation": "Relacion",
        "milestone": "Hito",
        "merge_suggestion": "Sugerencia de fusion",
        "import_issue": "Duda o conflicto",
        "ring_suggestion": "Sugerencia de anillo",
    }
    return f"{labels.get(kind, enum_human(getattr(candidate, 'candidate_type', 'candidato')))}: {name}"


def _candidate_kind(candidate) -> str:
    payload = getattr(candidate, "proposed_data", {}) or {}
    kind = str(payload.get("kind") or "").strip().lower()
    if kind:
        return kind
    ctype = str(getattr(candidate, "candidate_type", "") or "")
    if ctype == "relacion":
        return "relation"
    if ctype == "incidencia":
        return "import_issue"
    if ctype == "fusion":
        return "merge_suggestion"
    return "entity"


def _candidate_group(candidate) -> str:
    return {
        "entity": "Entidades",
        "branch": "Ramas",
        "relation": "Relaciones",
        "milestone": "Hitos",
        "merge_suggestion": "Fusiones",
        "import_issue": "Dudas y conflictos",
        "ring_suggestion": "Anillos",
    }.get(_candidate_kind(candidate), "Otros")


# Tarjetas de candidatos en UNA columna: a media anchura (2 col) el contenido
# (badges + 4 acciones + extracto) se perdía hacia la derecha. Full width cabe.
_CARDS_COLUMNS = 1

# Estados de revisión ya decididos: sus candidatos no se muestran en el menú de
# tarjetas (aceptar/rechazar/fusionar los retira de la cola pendiente).
_DECIDED_REVIEW_STATES = {"aceptado", "rechazado", "fusionado"}

# Orden de campos donde la IA deja el contenido legible del candidato. Unificado
# con candidate_review_panel para que la tarjeta muestre lo mismo que el panel.
_EXCERPT_FIELDS = [
    "summary", "body", "extended_description", "brief", "brief_description",
    "description", "text", "content", "message", "evidence",
]


def _is_pending_candidate(candidate) -> bool:
    """True si el candidato sigue pendiente de decisión (se muestra en tarjetas)."""
    state = _enum_text(getattr(candidate, "review_state", "")).strip().lower()
    return state not in _DECIDED_REVIEW_STATES


def _source_excerpt(candidate) -> str:
    payload = getattr(candidate, "proposed_data", {}) or {}
    for key in _EXCERPT_FIELDS:
        value = payload.get(key)
        if value:
            text = str(value).replace("\n", " ").strip()
            if text:
                return text[:220] + ("…" if len(text) > 220 else "")
    return "Sin extracto visible. Activa Modo avanzado para ver datos técnicos."


def _source_reference_text(candidate) -> str:
    payload = getattr(candidate, "proposed_data", {}) or {}
    refs = payload.get("source_references") or payload.get("affected_source_references") or []
    if refs and isinstance(refs, list) and isinstance(refs[0], dict):
        ref = refs[0]
        section = ref.get("section_path") or ref.get("source_name") or "Fuente importada"
        quote = str(ref.get("quote_excerpt") or "").replace("\n", " ").strip()
        if quote:
            return f"{section}: {quote[:180]}" + ("..." if len(quote) > 180 else "")
        return str(section)
    return _source_excerpt(candidate)


def _candidate_visible_text(candidate) -> str:
    payload = getattr(candidate, "proposed_data", {}) or {}
    fields = [
        payload.get("summary"),
        payload.get("brief_description"),
        payload.get("description"),
        payload.get("body"),
        payload.get("message"),
        payload.get("evidence"),
    ]
    return next((str(value).strip() for value in fields if str(value or "").strip()), "")


class _ImportExtractionWorker(QThread):
    """Ejecuta la extracción IA de candidatos en segundo plano (I17).

    Emite ``progress(done, total, label)`` por segmento y ``finishedOk(list)`` /
    ``failed(str)`` al terminar. ``cancel()`` corta entre segmentos.
    """

    progress = Signal(int, int, str)
    finishedOk = Signal(list)
    failed = Signal(str)

    def __init__(self, controller, basket_id: str, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._basket_id = basket_id
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            result = self._controller.extract_ai_candidates(
                self._basket_id,
                progress_callback=lambda done, total, label: self.progress.emit(
                    int(done), int(total), str(label)
                ),
                should_cancel=lambda: self._cancel,
            )
        except Exception as exc:  # noqa: BLE001 — frontera de hilo
            self.failed.emit(str(exc))
            return
        if isinstance(result, Error):
            self.failed.emit(str(result.error))
        else:
            self.finishedOk.emit(list(getattr(result, "value", None) or []))


class ImportExportView(QWidget):
    def __init__(self, ctx: AppContext, controller, export_service: ExportService | None = None):
        super().__init__()
        self.setWindowTitle("Importación documental")
        self.ctx = ctx
        self.controller = controller
        self.ic = ImportController(project_service=controller.ps)
        self.export = export_service
        self.selected_basket_id: str | None = None
        self.selected_candidate_id: str | None = None
        self.kind_filter: QComboBox | None = None
        self.progress_row: QWidget | None = None
        self._extraction_worker: _ImportExtractionWorker | None = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(SectionHeader(
            "Importación documental",
            "Revisa semillas como tarjetas. IDs, segmentos y JSON quedan en Datos técnicos."
        ))

        act = QHBoxLayout()
        act.addWidget(QLabel("Modo:"))
        self.mode_selector = QComboBox()
        for label, value in [
            ("Canon (extraer)", "canon"),
            ("Contexto (referencia)", "contexto"),
        ]:
            self.mode_selector.addItem(label, value)
        self.mode_selector.setToolTip(
            "Canon: la IA extrae candidatos revisables para pasar a canon.\n"
            "Contexto: el documento alimenta a la IA como material de referencia, sin volverse canon."
        )
        act.addWidget(self.mode_selector)
        for label, handler, primary in [
            ("Seleccionar TXT/MD/PDF", self._pick, True),
            ("Analizar duplicados", self._analyze_duplicates, False),
            ("Aceptar visibles", self._accept_filtered, False),
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

        # Fila de progreso de la extracción IA (oculta salvo durante el análisis).
        self.progress_row = QWidget()
        progress_layout = QHBoxLayout(self.progress_row)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("mutedLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(220)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self._cancel_extraction)
        progress_layout.addWidget(self.progress_label, stretch=1)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(cancel_btn)
        self.progress_row.setVisible(False)
        layout.addWidget(self.progress_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Vista:"))
        self.kind_filter = QComboBox()
        for label, value in [
            ("Todos", "all"),
            ("Entidades", "entity"),
            ("Ramas", "branch"),
            ("Relaciones", "relation"),
            ("Hitos", "milestone"),
            ("Fusiones", "merge_suggestion"),
            ("Dudas", "import_issue"),
        ]:
            self.kind_filter.addItem(label, value)
        self.kind_filter.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.kind_filter)
        filter_row.addStretch()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        filter_row.addWidget(self.summary_label)
        layout.addLayout(filter_row)

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
        path, _ = QFileDialog.getOpenFileName(self, "Importar", "", "Documentos (*.txt *.md *.markdown *.pdf)")
        if not path:
            return
        mode = self.mode_selector.currentData() if self.mode_selector is not None else "canon"
        # Blindaje: una excepción dentro de este slot de Qt (import o refresco)
        # cerraría toda la app. La contenemos y la mostramos como error visible.
        try:
            result = self.ic.import_document(path, mode=mode or "canon")
        except Exception as exc:  # noqa: BLE001 — contención de slot Qt
            self.ctx.log("error", f"Error importando documento: {exc!r}")
            self.detail.setPlainText(f"No se pudo importar el documento: {exc}")
            return
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"No se pudo importar el documento: {result.error}")
            return

        basket = result.value
        self.ctx.log("info", f"Import basket created: {basket.id} ({mode})")
        n_segs = len(getattr(basket, "segments", []) or [])
        try:
            self.refresh()
        except Exception as exc:  # noqa: BLE001 — contención de slot Qt
            self.ctx.log("error", f"Error refrescando la vista de importación: {exc!r}")

        if mode == "contexto":
            self.detail.setPlainText(
                "Documento importado como MATERIAL DE REFERENCIA (modo contexto).\n"
                f"Segmentos indexables: {n_segs}.\n"
                "La IA podrá consultarlo como contexto; nunca se convierte en canon ni "
                "genera tarjetas de candidatos. Aparece abajo como tarjeta de referencia."
            )
            return

        # Canon: la extracción rica corre en IA, en segundo plano (no congela UI).
        if n_segs == 0:
            self.detail.setPlainText("El documento importado no tiene texto extraíble.")
            return
        self._start_extraction(basket.id)

    # ── Extracción IA en segundo plano (I17) ─────────────────────────────

    def _start_extraction(self, basket_id: str):
        worker = getattr(self, "_extraction_worker", None)
        if worker is not None and worker.isRunning():
            self.detail.setPlainText("Ya hay un análisis IA en curso.")
            return
        self._set_extraction_busy(True)
        self.detail.setPlainText("Analizando documento con IA…")
        worker = _ImportExtractionWorker(self.ic, basket_id, self)
        self._extraction_worker = worker
        worker.progress.connect(self._on_extract_progress)
        worker.finishedOk.connect(self._on_extract_done)
        worker.failed.connect(self._on_extract_failed)
        worker.start()

    def _on_extract_progress(self, done: int, total: int, label: str):
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(done)
        shown = min(done + 1, total) if total else 0
        self.progress_label.setText(f"Analizando {shown}/{total} · {label}")

    def _on_extract_done(self, candidates: list):
        self._set_extraction_busy(False)
        self.detail.setPlainText(
            f"Análisis IA completado: {len(candidates)} candidato(s) para revisar."
        )
        self._safe_refresh()

    def _on_extract_failed(self, error: str):
        self._set_extraction_busy(False)
        self.ctx.log("error", f"Extracción IA: {error}")
        self.detail.setPlainText(f"No se pudo analizar con IA: {error}")
        self._safe_refresh()

    def _cancel_extraction(self):
        worker = getattr(self, "_extraction_worker", None)
        if worker is not None and worker.isRunning():
            worker.cancel()
            self.progress_label.setText("Cancelando…")

    def _set_extraction_busy(self, busy: bool):
        if self.progress_row is not None:
            self.progress_row.setVisible(busy)
        if not busy:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
            self.progress_label.setText("")

    def _safe_refresh(self):
        try:
            self.refresh()
        except Exception as exc:  # noqa: BLE001 — contención de slot Qt
            self.ctx.log("error", f"Error refrescando importación: {exc!r}")

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

    def _filtered_rows(self, rows):
        # Solo candidatos pendientes de decisión (los aceptados/rechazados/fusionados
        # salen de la cola); se conservan las filas placeholder (c is None).
        rows = [(b, c) for b, c in rows if c is None or _is_pending_candidate(c)]
        if self.kind_filter is None:
            return rows
        selected = self.kind_filter.currentData() or "all"
        if selected == "all":
            return rows
        return [(b, c) for b, c in rows if c is None or _candidate_kind(c) == selected]

    def _clear_cards(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh(self):
        rows = self._rows()
        self._update_summary(rows)
        self._refresh_cards(self._filtered_rows(rows))
        self._refresh_table(rows)

    def _update_summary(self, rows):
        baskets = {getattr(b, "id", "") for b, _ in rows}
        counts: dict[str, int] = {}
        for _, candidate in rows:
            if candidate is None:
                continue
            counts[_candidate_group(candidate)] = counts.get(_candidate_group(candidate), 0) + 1
        parts = [f"{label}: {count}" for label, count in sorted(counts.items())]
        self.summary_label.setText(f"{len(baskets)} batch(es) · " + (" · ".join(parts) if parts else "sin candidatos"))

    def _refresh_cards(self, rows):
        self._clear_cards()
        if not rows:
            self.cards_grid.addWidget(EmptyState(
                "Sin importaciones",
                "Selecciona un TXT, Markdown o PDF para detectar candidatos narrativos."
            ), 0, 0)
            return
        grid_row = 0
        grid_col = 0
        last_group = ""
        seen_config: set[str] = set()
        for basket, candidate in rows:
            bid = getattr(basket, "id", "")
            if bid not in seen_config and self._has_config_suggestion(basket):
                seen_config.add(bid)
                if grid_col:
                    grid_col = 0
                    grid_row += 1
                self.cards_grid.addWidget(self._make_config_card(basket), grid_row, 0, 1, _CARDS_COLUMNS)
                grid_row += 1
            if candidate is None:
                if str(getattr(basket, "import_mode", "canon")) == "contexto":
                    n_segs = len(getattr(basket, "segments", []) or [])
                    file_name = (getattr(basket, "metadata", {}) or {}).get("file_name", "documento")
                    card = Card(
                        f"📑 Referencia: {file_name}",
                        f"Material de contexto para la IA · {n_segs} segmento(s).",
                    )
                    card.add_text(
                        "No genera canon ni candidatos. Consultable por la IA como apoyo.",
                        muted=True,
                    )
                    summary = (getattr(basket, "metadata", {}) or {}).get("context_summary")
                    if isinstance(summary, dict) and summary.get("summary"):
                        card.add_text(f"Resumen IA: {summary['summary']}", muted=True)
                else:
                    card = Card("Documento importado", "No hay candidatos detectados todavía.")
                    card.add_text(
                        "La importación existe; usa «Extraer con IA» para detectar candidatos.",
                        muted=True,
                    )
                self.cards_grid.addWidget(card, grid_row, grid_col)
                grid_col += 1
                if grid_col >= _CARDS_COLUMNS:
                    grid_col = 0
                    grid_row += 1
                continue
            group = _candidate_group(candidate)
            if group != last_group:
                if grid_col:
                    grid_col = 0
                    grid_row += 1
                heading = QLabel(group)
                heading.setObjectName("sectionTitle")
                self.cards_grid.addWidget(heading, grid_row, 0, 1, 2)
                grid_row += 1
                last_group = group
            card = Card(_candidate_title(candidate), _source_excerpt(candidate))
            state_text = enum_human(getattr(candidate, "review_state", "pendiente"))
            confidence = float(getattr(candidate, "confidence", 0.0) or 0.0)
            payload = getattr(candidate, "proposed_data", {}) or {}
            row = card.add_row()
            row.addWidget(Badge(group, "neutral"))
            row.addWidget(Badge(state_text, "info"))
            row.addWidget(Badge(f"Confianza {confidence:.0%}", "success" if confidence >= 0.7 else "warning"))
            if payload.get("presentation_kind") == "enrich_existing":
                target = self._enrich_target_name(payload)
                if len(target) > 24:
                    target = target[:23] + "…"
                row.addWidget(Badge(f"Enriquece a {target}", "gold"))
            row.addStretch()
            source = _source_reference_text(candidate)
            if source:
                card.add_text(f"Fuente: {source}", muted=True)
            actions = card.add_row()
            btn_select = QPushButton("Ver")
            btn_select.clicked.connect(lambda _=False, b=basket.id, c=candidate.id: self._select_card(b, c))
            btn_edit = QPushButton("Revisar")
            btn_edit.clicked.connect(lambda _=False, b=basket.id, c=candidate.id: self._edit_ids(b, c))
            btn_accept = QPushButton("Aceptar")
            btn_accept.clicked.connect(lambda _=False, b=basket.id, c=candidate.id: self._accept_ids(b, c))
            btn_reject = QPushButton("Descartar")
            btn_reject.clicked.connect(lambda _=False, b=basket.id, c=candidate.id: self._reject_ids(b, c))
            for btn in [btn_select, btn_edit, btn_accept, btn_reject]:
                actions.addWidget(btn)
            actions.addStretch()
            self.cards_grid.addWidget(card, grid_row, grid_col)
            grid_col += 1
            if grid_col >= _CARDS_COLUMNS:
                grid_col = 0
                grid_row += 1

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
        visible_text = _candidate_visible_text(candidate)
        source = _source_reference_text(candidate)
        lines = [
            _candidate_title(candidate),
            "",
            visible_text or _source_excerpt(candidate),
            "",
            f"Tipo: {_candidate_group(candidate)}",
            f"Estado: {enum_human(getattr(candidate, 'review_state', 'pendiente'))}",
            f"Confianza: {float(getattr(candidate, 'confidence', 0.0) or 0.0):.0%}",
            "",
            f"Fuente: {source}",
            "",
            "Usa Editar, Aceptar o Descartar. Los datos técnicos están ocultos salvo en Modo avanzado.",
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

    def _accept_filtered(self):
        rows = [(b, c) for b, c in self._filtered_rows(self._rows()) if c is not None]
        accepted = 0
        errors = []
        for basket, candidate in rows:
            result = self._apply_accept(basket.id, candidate.id)
            if isinstance(result, Error):
                errors.append(result.error)
            else:
                accepted += 1
        self.detail.setPlainText(
            f"Semillas aceptadas: {accepted}" + (f"\nErrores: {len(errors)}" if errors else "")
        )
        self.refresh()

    def _reject(self):
        basket_id, candidate_id, _ = self._selected_candidate()
        if not basket_id or not candidate_id:
            self.ctx.log("error", "Selecciona un candidato")
            return
        self._reject_ids(basket_id, candidate_id)

    def _accept_ids(self, basket_id: str, candidate_id: str):
        self.selected_basket_id = basket_id
        self.selected_candidate_id = candidate_id
        result = self._apply_accept(basket_id, candidate_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"No se pudo aceptar: {result.error}")
        else:
            self.ctx.log("info", "Candidato de importación aceptado")
            self.detail.setPlainText("Candidato aceptado.")
            self.refresh()

    def _apply_accept(self, basket_id: str, candidate_id: str):
        if hasattr(self.ic, "apply_to_canon"):
            return self.ic.apply_to_canon(basket_id, candidate_id)
        return self.ic.accept(basket_id, candidate_id)

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

    def _edit_ids(self, basket_id: str, candidate_id: str):
        self.selected_basket_id = basket_id
        self.selected_candidate_id = candidate_id
        _, _, candidate = self._selected_candidate()
        if candidate is None:
            self.detail.setPlainText("No hay candidato seleccionable.")
            return
        if self.ctx.drawer is None:
            self.detail.setPlainText("Revisión disponible desde el panel lateral.")
            return
        self._open_review_panel(basket_id, candidate_id, candidate)

    def _open_review_panel(self, basket_id: str, candidate_id: str, candidate):
        """Abre la ficha de detalle editable del candidato (I18) en el drawer."""
        from hosts.DesktopHostPySide.widgets.import_candidate_review_panel import (
            ImportCandidateReviewPanel,
        )

        def _on_decision(_cid, _decision):
            drawer = self.ctx.drawer
            if drawer is not None and hasattr(drawer, "close"):
                drawer.close()
            self._safe_refresh()

        panel = ImportCandidateReviewPanel(
            candidate,
            self.ic,
            self._project(),
            basket_id=basket_id,
            on_decision=_on_decision,
        )
        self.ctx.drawer.set_content(panel, title="Revisar candidato")
        self.ctx.drawer.open()

    # ── I13: propuesta de configuración del proyecto ──────────────────────

    @staticmethod
    def _config_suggestion(basket):
        proposal = (getattr(basket, "metadata", {}) or {}).get("project_config_suggestion")
        return proposal if isinstance(proposal, dict) else None

    def _has_config_suggestion(self, basket) -> bool:
        proposal = self._config_suggestion(basket)
        return bool(proposal) and not proposal.get("applied")

    def _make_config_card(self, basket):
        proposal = self._config_suggestion(basket) or {}
        chron = proposal.get("chronology") or {}
        n_eras = len([e for e in (chron.get("eras") or []) if isinstance(e, dict)])
        n_ent = len([p for p in (proposal.get("entity_temporal") or []) if isinstance(p, dict)])
        mode_label = {
            "none": "sin calendario", "vague_periods": "periodos vagos",
            "full_calendar": "calendario completo",
        }.get(str(chron.get("mode") or ""), "calendario")
        card = Card(
            "⚙ Configuración propuesta del documento",
            f"Calendario ({mode_label}) · {n_eras} era(s) · {n_ent} entidad(es) ubicada(s).",
        )
        card.add_text(
            "La IA propone esta configuración a partir del documento. Revísala antes de aplicarla.",
            muted=True,
        )
        actions = card.add_row()
        bid = getattr(basket, "id", "")
        review_btn = QPushButton("Revisar")
        review_btn.clicked.connect(lambda _=False, b=bid: self._open_config_panel(b))
        accept_btn = QPushButton("Aplicar")
        accept_btn.clicked.connect(lambda _=False, b=bid: self._accept_config(b))
        discard_btn = QPushButton("Descartar")
        discard_btn.clicked.connect(lambda _=False, b=bid: self._discard_config(b))
        for btn in (review_btn, accept_btn, discard_btn):
            actions.addWidget(btn)
        actions.addStretch()
        return card

    def _basket_by_id(self, basket_id: str):
        baskets = self.ic.list_baskets()
        if hasattr(baskets, "value"):
            baskets = baskets.value
        if isinstance(baskets, Error):
            return None
        return next((b for b in baskets or [] if getattr(b, "id", "") == basket_id), None)

    def _open_config_panel(self, basket_id: str):
        basket = self._basket_by_id(basket_id)
        proposal = self._config_suggestion(basket) if basket else None
        if proposal is None:
            self.detail.setPlainText("No hay propuesta de configuración.")
            return
        if self.ctx.drawer is None:
            self.detail.setPlainText("Revisión disponible desde el panel lateral.")
            return
        from hosts.DesktopHostPySide.widgets.import_project_config_panel import (
            ImportProjectConfigPanel,
        )

        def _on_decision(_decision):
            drawer = self.ctx.drawer
            if drawer is not None and hasattr(drawer, "close"):
                drawer.close()
            self._safe_refresh()

        panel = ImportProjectConfigPanel(
            proposal, self.ic, basket_id=basket_id, on_decision=_on_decision
        )
        self.ctx.drawer.set_content(panel, title="Configuración propuesta")
        self.ctx.drawer.open()

    def _accept_config(self, basket_id: str):
        result = self.ic.apply_project_config_suggestion(basket_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"No se pudo aplicar la configuración: {result.error}")
        else:
            self.ctx.log("info", "Configuración de proyecto aplicada")
            self.detail.setPlainText("Configuración aplicada al proyecto.")
            self._safe_refresh()

    def _discard_config(self, basket_id: str):
        result = self.ic.discard_project_config_suggestion(basket_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", "Propuesta de configuración descartada")
            self._safe_refresh()

    def _enrich_target_name(self, payload: dict) -> str:
        target_id = payload.get("enrich_target_id")
        for entity in getattr(self._project(), "entities", []) or []:
            if getattr(entity, "id", "") == target_id:
                return str(getattr(entity, "name", "") or target_id)
        return str(target_id or "?")

    def _save_candidate_edit(self, basket_id: str, candidate_id: str, data: dict):
        result = self.ic.edit(basket_id, candidate_id, data)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            self.detail.setPlainText(f"No se pudo editar: {result.error}")
            return result
        self.ctx.log("info", "Candidato de importacion editado")
        self.detail.setPlainText("Candidato editado.")
        self.refresh()
        return result

    def _open_edit_form(self, basket_id: str, candidate_id: str, candidate):
        view = self
        payload = getattr(candidate, "proposed_data", {}) or {}

        class _ImportCandidateEditForm(DrawerForm):
            def __init__(self, ctx):
                super().__init__(ctx, title="Editar candidato")
                self.name = QLineEdit(str(payload.get("name") or payload.get("title") or ""))
                self.kind = QComboBox()
                for label, value in [
                    ("Hoja", "entity"),
                    ("Rama", "branch"),
                    ("Relacion", "relation"),
                    ("Hito", "milestone"),
                    ("Duda/conflicto", "import_issue"),
                ]:
                    self.kind.addItem(label, value)
                idx = self.kind.findData(_candidate_kind(candidate))
                if idx >= 0:
                    self.kind.setCurrentIndex(idx)
                self.entity_type = QLineEdit(str(payload.get("entity_type") or payload.get("branch_type") or ""))
                self.ring = QLineEdit(str(payload.get("suggested_ring_name") or payload.get("suggested_ring_id") or ""))
                self.branch = QLineEdit(str(payload.get("suggested_branch_name") or payload.get("suggested_branch_id") or ""))
                self.body = QTextEdit(str(payload.get("body") or payload.get("description") or payload.get("summary") or ""))
                self.form_layout.addRow("Nombre/titulo:", self.name)
                self.form_layout.addRow("Tipo:", self.kind)
                self.form_layout.addRow("Subtipo:", self.entity_type)
                self.form_layout.addRow("Anillo sugerido:", self.ring)
                self.form_layout.addRow("Rama sugerida:", self.branch)
                self.form_layout.addRow("Texto:", self.body)

            def _on_accept(self):
                data = {
                    "name": self.name.text().strip(),
                    "kind": self.kind.currentData(),
                    "entity_type": self.entity_type.text().strip(),
                    "suggested_ring_name": self.ring.text().strip(),
                    "suggested_branch_name": self.branch.text().strip(),
                    "body": self.body.toPlainText().strip(),
                }
                view._save_candidate_edit(basket_id, candidate_id, data)
                self._close_drawer()

        form = _ImportCandidateEditForm(self.ctx)
        self.ctx.drawer.set_content(form, title="Editar candidato")
        self.ctx.drawer.open()

    def _analyze_duplicates(self):
        basket_ids = []
        for basket, _ in self._rows():
            if basket.id not in basket_ids:
                basket_ids.append(basket.id)
        total = 0
        for basket_id in basket_ids:
            if hasattr(self.ic, "analyze_duplicates"):
                result = self.ic.analyze_duplicates(basket_id)
                if isinstance(result, Error):
                    self.ctx.log("error", result.error)
                    self.detail.setPlainText(f"No se pudo analizar duplicados: {result.error}")
                    return
                total += len(result.value if hasattr(result, "value") else result)
        self.detail.setPlainText(f"Semillas de fusión detectadas: {total}")
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
                self.kind.addItems(["entity"])
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

            def _on_accept(self):
                kind = self.kind.currentText()
                audience = self.audience.currentText()
                item_id = self.item.currentData()
                if not item_id:
                    view.detail.setPlainText("No hay elemento seleccionable")
                    self._close_drawer()
                    return
                result = view.export.export_entity_profile(item_id, audience)
                if isinstance(result, Error):
                    view.detail.setPlainText(f"Error: {result.error}")
                else:
                    view.detail.setPlainText(str(result.value))
                self._close_drawer()

        form = _ExportSingleForm(self.ctx)
        drawer.set_content(form, title="Exportar elemento")
        drawer.open()
