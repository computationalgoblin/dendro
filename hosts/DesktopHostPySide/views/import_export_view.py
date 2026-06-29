"""ImportExportView — visual import cards + advanced export/debug (B27.5-T07)."""
from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.import_controller import ImportController
from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    Card,
    EmptyState,
    FlowLayout,
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
        # UX33: los jobs ya NO cuelgan de la vista. Corren en el runner persistente
        # (ctx.import_jobs); la vista solo dispara y escucha sus señales. Conexión con
        # métodos ligados → Qt las auto-desconecta al destruirse la vista.
        self.jobs = getattr(ctx, "import_jobs", None)
        self._active_job_basket: str | None = None
        if self.jobs is not None:
            self.jobs.scaffoldingDone.connect(self._on_runner_scaffolding_done)
            self.jobs.extractionStarted.connect(self._on_runner_extraction_started)
            self.jobs.extractionProgress.connect(self._on_runner_extraction_progress)
            self.jobs.extractionDone.connect(self._on_runner_extraction_done)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(SectionHeader(
            "Importación documental",
            "Revisa semillas como tarjetas. IDs, segmentos y JSON quedan en Datos técnicos."
        ))

        # FlowLayout: en el cajón estrecho (≤680px, sin scroll horizontal) una fila
        # plana de combo + 7 botones se recorta; aquí envuelve a la siguiente línea.
        act = FlowLayout(spacing=8)
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

        filter_row = FlowLayout(spacing=8)
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

        # UX33: la vista se reconstruye en cada apertura del cajón. Refrescar AQUÍ
        # (no solo en showEvent, que no llega de forma fiable al montarse dentro del
        # cajón animado) garantiza que al reabrir se vea el estado actual: la
        # propuesta de andamiaje pendiente de aceptar/rechazar, los candidatos ya
        # extraídos, o el progreso de un job en curso.
        self._safe_refresh()

    def set_advanced_mode(self, enabled: bool):
        # El desplegable de datos técnicos / export se retiró: el modo avanzado ya
        # no añade nada en esta vista. Se conserva el método por compatibilidad de
        # API (lo invoca el host al alternar el modo).
        return None

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

        # Canon (I22): primero la IA propone el ANDAMIAJE del mundo (Fase 1). El
        # usuario lo revisa y aplica en bloque; aplicarlo dispara la extracción de
        # entidades (Fase 2), ya datadas contra el marco.
        if n_segs == 0:
            self.detail.setPlainText("El documento importado no tiene texto extraíble.")
            return
        self._start_scaffolding(basket.id)

    # ── Andamiaje y extracción (UX33: corren en ctx.import_jobs) ─────────

    def _start_scaffolding(self, basket_id: str):
        if self.jobs is None:
            self.detail.setPlainText("El servicio de importación no está disponible.")
            return
        if self.jobs.is_running(basket_id):
            self.detail.setPlainText("Ya hay un análisis IA en curso para este documento.")
            return
        self._set_extraction_busy(True)
        self.progress_bar.setRange(0, 0)  # indeterminado: una sola llamada IA
        self.progress_label.setText("Proponiendo el andamiaje del mundo…")
        self.detail.setPlainText(
            "La IA propone el andamiaje (calendario, anillos e hitos) antes de extraer "
            "entidades. Revísalo y aplícalo para situar las entidades en el mundo."
        )
        self._active_job_basket = basket_id
        self.jobs.start_scaffolding(basket_id)

    def _start_extraction(self, basket_id: str):
        if self.jobs is None:
            self.detail.setPlainText("El servicio de importación no está disponible.")
            return
        if self.jobs.is_running(basket_id):
            self.detail.setPlainText("Ya hay un análisis IA en curso para este documento.")
            return
        self._set_extraction_busy(True)
        self.progress_bar.setRange(0, 1)
        self.detail.setPlainText("Analizando documento con IA…")
        self._active_job_basket = basket_id
        self.jobs.start_extraction(basket_id)

    # ── Señales del runner (UX33) ────────────────────────────────────────

    def _on_runner_scaffolding_done(self, _basket_id: str, ok: bool, error: str):
        self._set_extraction_busy(False)
        if ok:
            self.detail.setPlainText(
                "Andamiaje propuesto. Revísalo y pulsa «Aplicar» para situar las entidades; "
                "la extracción arrancará tras aplicarlo."
            )
        else:
            self.ctx.log("error", f"Andamiaje IA: {error}")
            self.detail.setPlainText(f"No se pudo proponer el andamiaje: {error}")
        self._safe_refresh()

    def _on_runner_extraction_started(self, basket_id: str):
        self._active_job_basket = basket_id
        self._set_extraction_busy(True)
        self.progress_bar.setRange(0, 1)
        self.progress_label.setText("Analizando documento con IA…")

    def _on_runner_extraction_progress(self, _basket_id: str, done: int, total: int, label: str):
        self._set_extraction_busy(True)
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(done)
        shown = min(done + 1, total) if total else 0
        self.progress_label.setText(f"Analizando {shown}/{total} · {label}")

    def _on_runner_extraction_done(self, basket_id: str, count: int, error: str):
        self._set_extraction_busy(False)
        if error:
            # I24: error de arranque (proveedor no configurado). Los fallos a media
            # extracción ya NO llegan por aquí: la extracción devuelve parcial y el
            # desenlace vive en la metadata del basket (ver abajo).
            self.ctx.log("error", f"Extracción IA: {error}")
            self.detail.setPlainText(f"No se pudo analizar con IA: {error}")
            self._safe_refresh()
            return
        basket = self._basket_by_id(basket_id)
        meta = self._extraction_meta(basket) if basket else {}
        if meta.get("aborted"):
            pending = int(meta.get("pending_sections") or 0)
            self.detail.setPlainText(
                f"Análisis interrumpido: {meta.get('abort_reason', '')}\n"
                f"Progreso guardado: {count} candidato(s). Usa «Reanudar análisis IA» "
                f"({pending} pendientes) cuando el proveedor esté disponible."
            )
        elif int(meta.get("skipped_sections") or 0):
            self.detail.setPlainText(
                f"Análisis IA completado (parcial): {count} candidato(s); "
                f"{meta['skipped_sections']} sección(es) omitida(s) por el filtro del proveedor "
                "(revísalas en «Dudas y conflictos»)."
            )
        else:
            self.detail.setPlainText(
                f"Análisis IA completado: {count} candidato(s) para revisar."
            )
        self._safe_refresh()

    def _cancel_extraction(self):
        if self.jobs is not None and self._active_job_basket:
            self.jobs.cancel_extraction(self._active_job_basket)
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

    def showEvent(self, event):  # noqa: N802 (Qt API)
        # UX33: la vista se recrea cada vez que se abre el cajón. Al mostrarse,
        # refresca para reflejar el estado ACTUAL del proyecto activo: candidatos
        # ya extraídos, propuesta de andamiaje pendiente de aceptar, o un job en
        # curso (progreso). Sin esto, al reabrir no se veía ni el progreso ni la
        # propuesta (que el usuario debe poder aceptar/rechazar).
        super().showEvent(event)
        self._safe_refresh()

    def refresh(self):
        rows = self._rows()
        self._update_summary(rows)
        self._refresh_cards(self._filtered_rows(rows))
        self._reflect_running_jobs(rows)

    def _reflect_running_jobs(self, rows):
        """UX33: al (re)abrir, refleja si hay un job en curso en el runner.

        Como el job vive fuera de la vista, una vista recién montada puede
        encontrarse una extracción ya en marcha: muestra la barra de progreso
        (indeterminada) en vez de aparentar que no pasa nada."""
        if self.jobs is None:
            return
        running = next(
            (getattr(b, "id", "") for b, _ in rows if self.jobs.is_running(getattr(b, "id", ""))),
            None,
        )
        if running:
            self._active_job_basket = running
            self._set_extraction_busy(True)
            self.progress_bar.setRange(0, 0)  # indeterminado: no conocemos el avance
            kind = self.jobs.running_kind(running)
            self.progress_label.setText(
                "Proponiendo el andamiaje…" if kind == "scaffolding"
                else "Analizando documento con IA…"
            )

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
        seen_resume: set[str] = set()
        for basket, candidate in rows:
            bid = getattr(basket, "id", "")
            if bid not in seen_config and self._has_config_suggestion(basket):
                seen_config.add(bid)
                if grid_col:
                    grid_col = 0
                    grid_row += 1
                self.cards_grid.addWidget(self._make_config_card(basket), grid_row, 0, 1, _CARDS_COLUMNS)
                grid_row += 1
            # I24: si la extracción quedó a medias (interrumpida o con secciones
            # pendientes), ofrecer reanudarla sin repetir lo ya hecho.
            if bid not in seen_resume and self._needs_resume(basket):
                seen_resume.add(bid)
                if grid_col:
                    grid_col = 0
                    grid_row += 1
                self.cards_grid.addWidget(self._make_resume_card(basket), grid_row, 0, 1, _CARDS_COLUMNS)
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
            row = card.add_flow_row()
            row.addWidget(Badge(group, "neutral"))
            row.addWidget(Badge(state_text, "info"))
            row.addWidget(Badge(f"Confianza {confidence:.0%}", "success" if confidence >= 0.7 else "warning"))
            if payload.get("presentation_kind") == "enrich_existing":
                target = self._enrich_target_name(payload)
                if len(target) > 24:
                    target = target[:23] + "…"
                row.addWidget(Badge(f"Enriquece a {target}", "gold"))
            source = _source_reference_text(candidate)
            if source:
                card.add_text(f"Fuente: {source}", muted=True)
            actions = card.add_flow_row()
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
            self.cards_grid.addWidget(card, grid_row, grid_col)
            grid_col += 1
            if grid_col >= _CARDS_COLUMNS:
                grid_col = 0
                grid_row += 1

    def _select_card(self, basket_id: str, candidate_id: str):
        self.selected_basket_id = basket_id
        self.selected_candidate_id = candidate_id
        _, _, candidate = self._selected_candidate()
        if candidate:
            self._show_clean_detail(candidate)

    def _selected_ids(self):
        if self.selected_basket_id and self.selected_candidate_id:
            return self.selected_basket_id, self.selected_candidate_id
        return None, None

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
            "Usa Revisar, Aceptar o Descartar.",
        ]
        self.detail.setPlainText("\n".join(lines))

    def _show_detail(self):
        """Muestra el resumen legible del candidato seleccionado (sin tabla)."""
        _basket_id, _candidate_id, candidate = self._selected_candidate()
        if candidate:
            self._show_clean_detail(candidate)

    def _accept(self):
        basket_id, candidate_id, _ = self._selected_candidate()
        if not basket_id or not candidate_id:
            self.ctx.log("error", "Selecciona un candidato")
            return
        self._accept_ids(basket_id, candidate_id)

    @staticmethod
    def _is_relation_candidate(candidate) -> bool:
        """True si el candidato crea una relación (debe aplicarse DESPUÉS de las
        entidades/ramas: I23, las relaciones ``contiene`` resuelven sus extremos por
        nombre contra canon, así que la rama/entidad debe existir ya)."""
        ctype = str(getattr(candidate, "candidate_type", "") or "").lower()
        kind = str((getattr(candidate, "proposed_data", {}) or {}).get("kind") or "").lower()
        return ctype == "relacion" or kind == "relation"

    def _accept_filtered(self):
        rows = [(b, c) for b, c in self._filtered_rows(self._rows()) if c is not None]
        # I23: aceptar primero entidades/ramas y después las relaciones, para que la
        # `contiene` encuentre ya en canon a la rama y al miembro (resolución por nombre).
        rows.sort(key=lambda bc: self._is_relation_candidate(bc[1]))
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

    @staticmethod
    def _extraction_meta(basket) -> dict:
        meta = (getattr(basket, "metadata", {}) or {}).get("ai_extraction")
        return meta if isinstance(meta, dict) else {}

    def _needs_resume(self, basket) -> bool:
        """I24: True si la extracción quedó interrumpida o con secciones pendientes."""
        meta = self._extraction_meta(basket)
        if not meta:
            return False
        return bool(meta.get("aborted")) or int(meta.get("pending_sections") or 0) > 0

    def _make_resume_card(self, basket):
        meta = self._extraction_meta(basket)
        pending = int(meta.get("pending_sections") or 0)
        aborted = bool(meta.get("aborted"))
        reason = str(meta.get("abort_reason") or "").strip()
        subtitle = (
            f"La extracción se interrumpió ({reason[:80]})." if aborted
            else "Quedaron secciones por analizar."
        )
        card = Card("⏸ Análisis IA incompleto", subtitle)
        card.add_text(
            f"{pending} sección(es) pendiente(s). Reanuda cuando el proveedor esté "
            "disponible: continúa donde se quedó, sin repetir lo ya analizado.",
            muted=True,
        )
        actions = card.add_flow_row()
        bid = getattr(basket, "id", "")
        resume_btn = QPushButton(f"Reanudar análisis IA ({pending} pendientes)")
        resume_btn.setObjectName("primaryButton")
        resume_btn.clicked.connect(lambda _=False, b=bid: self._start_extraction(b))
        actions.addWidget(resume_btn)
        return card

    def _make_config_card(self, basket):
        proposal = self._config_suggestion(basket) or {}
        chron = proposal.get("chronology") or {}
        n_eras = len([e for e in (chron.get("eras") or []) if isinstance(e, dict)])
        n_ent = len([p for p in (proposal.get("entity_temporal") or []) if isinstance(p, dict)])
        wl = proposal.get("world_layers") or {}
        n_rings = len(wl.get("activate_default_layer_ids") or []) + len(wl.get("custom_layers") or [])
        n_milestones = len([m for m in (proposal.get("milestones") or []) if isinstance(m, dict)])
        mode_label = {
            "none": "sin calendario", "vague_periods": "periodos vagos",
            "full_calendar": "calendario completo",
        }.get(str(chron.get("mode") or ""), "calendario")
        card = Card(
            "⚙ Andamiaje propuesto del documento",
            f"Calendario ({mode_label}) · {n_eras} era(s) · {n_rings} anillo(s) · "
            f"{n_milestones} hito(s) · {n_ent} entidad(es) ubicada(s).",
        )
        card.add_text(
            "La IA propone el andamiaje del mundo (calendario, anillos e hitos) a partir del "
            "documento. Revísalo y aplícalo en bloque; al aplicarlo se extraen las entidades.",
            muted=True,
        )
        actions = card.add_flow_row()
        bid = getattr(basket, "id", "")
        review_btn = QPushButton("Revisar")
        review_btn.clicked.connect(lambda _=False, b=bid: self._open_config_panel(b))
        accept_btn = QPushButton("Aplicar")
        accept_btn.clicked.connect(lambda _=False, b=bid: self._accept_config(b))
        discard_btn = QPushButton("Descartar")
        discard_btn.clicked.connect(lambda _=False, b=bid: self._discard_config(b))
        for btn in (review_btn, accept_btn, discard_btn):
            actions.addWidget(btn)
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

        # IMPORTANTE: ``set_content(panel)`` DESTRUYE esta vista (el cajón no apila
        # contenido). El callback corre más tarde, cuando ``self`` ya está borrado,
        # así que NO debe tocar ``self``: capturamos lo necesario en locales.
        ctx = self.ctx
        reopen = getattr(ctx, "reopen_import", None)

        def _on_decision(decision):
            drawer = ctx.drawer
            if decision == "accept":
                # Andamiaje aplicado desde el panel → arrancar Fase 2 (corre en el
                # runner persistente) y cerrar el cajón: el usuario sigue trabajando
                # y un toast avisa al terminar (UX33).
                jobs = getattr(ctx, "import_jobs", None)
                if jobs is not None:
                    jobs.start_extraction(basket_id)
                if drawer is not None and hasattr(drawer, "close"):
                    drawer.close()
                return
            # close/discard: VOLVER al menú de importación (no dejar al usuario sin
            # forma de aceptar/descartar un andamiaje aún pendiente). Reabrir monta
            # una vista fresca que refleja el estado actual (tarjeta de andamiaje si
            # sigue pendiente; candidatos si se descartó).
            if callable(reopen):
                reopen()
            elif drawer is not None and hasattr(drawer, "close"):
                drawer.close()

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
            # Fase 2 gateada: la extracción corre en el runner persistente, así que
            # podemos cerrar el cajón y seguir trabajando; un toast avisará al acabar.
            self._start_extraction(basket_id)
            drawer = self.ctx.drawer
            if drawer is not None and hasattr(drawer, "close"):
                drawer.close()

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
