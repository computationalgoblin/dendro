"""Product workspaces for the B27.5 Desktop UX shell.

These wrappers reorganize existing connected views into three product spaces
without deleting functionality. Technical CRUD screens are kept behind advanced
mode while normal mode starts from clean cards/overviews.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.controllers.ai_context_controller import AIContextController
from hosts.DesktopHostPySide.controllers.causal_milestone_controller import CausalMilestoneController
from hosts.DesktopHostPySide.widgets.entity_card import EntityCard
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget, GraphSearchResult, VisualFilterState, relation_family
from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
from hosts.DesktopHostPySide.widgets.coherence_panel import CoherencePanel
from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    Card,
    EmptyState,
    ICON_GLYPHS,
    SectionHeader,
    enum_human,
    human_ref,
    make_scroll_area,
    pulse_feedback,
)
from packages.domain.result import Error
from packages.domain.world_layer import default_world_layers
from packages.application.ai_jobs import AIJobService, classify_ai_job_intent


class _SimpleFormPanel(QWidget):
    """Small drawer form used by normal-mode creation paths."""

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 18)
        self.layout.setSpacing(12)
        self.layout.addWidget(SectionHeader(title, subtitle))

    def add_status(self) -> QLabel:
        label = QLabel("")
        label.setObjectName("mutedLabel")
        label.setWordWrap(True)
        self.layout.addWidget(label)
        return label


class RingInfoPanel(_SimpleFormPanel):
    """B44 non-canonical ring info/actions panel."""

    def __init__(self, *, display_name: str, count_label: str, causal_rank: object, state: str, on_enter=None, on_global=None):
        super().__init__("Anillo", "Vista calculada; no modifica canon")
        self.layout.addWidget(QLabel(f"<b>{display_name}</b>"))
        details = QLabel(
            f"Rango causal: {causal_rank if causal_rank is not None else 'Sin clasificar'}\n"
            f"Contenido: {count_label or 'sin elementos'}\n"
            f"Estado: {state or 'normal'}"
        )
        details.setWordWrap(True)
        details.setStyleSheet("color: #5F5A3D; background: transparent; line-height: 1.35;")
        self.layout.addWidget(details)

        row = QHBoxLayout()
        enter_btn = QPushButton("Entrar en anillo")
        enter_btn.setToolTip("Trabajar solo con el contenido visual de este anillo")
        if on_enter is not None:
            enter_btn.clicked.connect(on_enter)
        row.addWidget(enter_btn)
        global_btn = QPushButton("Vista global")
        global_btn.setToolTip("Volver a mostrar todo el grafo")
        if on_global is not None:
            global_btn.clicked.connect(on_global)
        row.addWidget(global_btn)
        self.layout.addLayout(row)
        self.layout.addStretch(1)


class EntityQuickCreatePanel(_SimpleFormPanel):
    def __init__(self, controller, on_created, *, layer_id: str = "", layer_name: str = ""):
        super().__init__("Nueva hoja", "Crea una pieza narrativa sin ver campos técnicos.")
        self.controller = controller
        self.on_created = on_created
        self.layer_id = str(layer_id or "")
        self.layer_name = str(layer_name or "")
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre visible")
        self.kind = QComboBox()
        self.kind.addItems(["personaje", "localizacion", "objeto", "evento", "faccion", "secreto", "pista", "trama", "nota"])
        self.description = QTextEdit()
        self.description.setPlaceholderText("Descripción breve")
        self.description.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Tipo", self.kind)
        if self.layer_id:
            form.addRow("Anillo", QLabel(self.layer_name or self.layer_id))
        form.addRow("Descripción", self.description)
        self.layout.addLayout(form)
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Crear hoja")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        _apptrace(f"WS entity_quick_create name={self.name.text().strip()[:60]}")
        data = {
            "name": self.name.text().strip(),
            "entity_type": self.kind.currentText(),
            "brief_description": self.description.toPlainText().strip(),
        }
        if self.layer_id:
            data["layer_ids"] = [self.layer_id]
        result = self.controller.create(data)
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        entity = result.value
        self.status.setText(f"Hoja creada: {getattr(entity, 'name', 'sin nombre')}")
        self.on_created()


class SourceQuickCreatePanel(_SimpleFormPanel):
    def __init__(self, controller, on_created):
        super().__init__("Nueva fuente", "Registra una referencia legible para trazabilidad narrativa.")
        self.controller = controller
        self.on_created = on_created
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre de la referencia")
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("URL, libro, nota o archivo")
        self.fragment = QTextEdit()
        self.fragment.setPlaceholderText("Fragmento o contexto")
        self.fragment.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Referencia", self.reference)
        form.addRow("Fragmento", self.fragment)
        self.layout.addLayout(form)
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Crear fuente")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        result = self.controller.create({
            "name": self.name.text().strip(),
            "reference": self.reference.text().strip(),
            "fragment": self.fragment.toPlainText().strip(),
            "source_type": "entrada_manual",
        })
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        source = result.value
        self.status.setText(f"Fuente creada: {getattr(source, 'name', 'sin nombre')}")
        self.on_created()


class LayerQuickCreatePanel(_SimpleFormPanel):
    def __init__(self, controller, on_created):
        super().__init__("Nuevo anillo", "Organiza el worldbuilding como estratos visuales.")
        self.controller = controller
        self.on_created = on_created
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre de la capa")
        self.description = QTextEdit()
        self.description.setPlaceholderText("Qué representa esta capa")
        self.description.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Descripción", self.description)
        self.layout.addLayout(form)
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Crear anillo")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        result = self.controller.create({
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
        })
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        layer = result.value
        self.status.setText(f"Anillo creado: {getattr(layer, 'name', 'sin nombre')}")
        self.on_created()


class RingEditPanel(_SimpleFormPanel):
    """BETA1-B03: edit a ring (world layer) — name and order.

    Order also writes metadata.causal_rank because the concentric view sorts
    rings by causal rank, not by the plain order field."""

    def __init__(self, controller, ring_id: str, on_saved):
        super().__init__("Editar anillo", "Nombre y orden del estrato.")
        self.controller = controller
        self.ring_id = ring_id
        self.on_saved = on_saved
        form = QFormLayout()
        self.name = QLineEdit()
        self.order = QSpinBox()
        self.order.setRange(1, 999)
        current = controller.get(ring_id) if hasattr(controller, "get") else None
        layer = getattr(current, "value", None)
        if layer is not None:
            self.name.setText(str(getattr(layer, "name", "")))
            rank = str(getattr(layer, "metadata", {}).get("causal_rank", "") or getattr(layer, "order", 1))
            try:
                self.order.setValue(int(rank))
            except (TypeError, ValueError):
                self.order.setValue(int(getattr(layer, "order", 1) or 1))
        form.addRow("Nombre", self.name)
        form.addRow("Orden (rango causal)", self.order)
        self.layout.addLayout(form)
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Guardar anillo")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        name = self.name.text().strip()
        if not name:
            self.status.setText("El nombre no puede estar vacío")
            return
        order = int(self.order.value())
        result = self.controller.update(self.ring_id, {
            "name": name,
            "order": order,
            "metadata": {"causal_rank": str(order)},
        })
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.status.setText("Anillo actualizado")
        self.on_saved()


class CandidateReviewPanel(_SimpleFormPanel):
    def __init__(self, controller, on_changed):
        super().__init__("Sugerencias", "Revisa candidatos como tarjetas, sin tabla técnica.")
        self.controller = controller
        self.on_changed = on_changed
        self.cards = QWidget()
        self.cards_layout = QVBoxLayout(self.cards)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.layout.addWidget(make_scroll_area(self.cards), 1)
        self.refresh()

    def refresh(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        candidates = self.controller.list_all()
        if not candidates:
            self.cards_layout.addWidget(EmptyState("Sin sugerencias", "Cuando la IA proponga candidatos aparecerán aquí."))
            return
        for candidate in candidates:
            title = getattr(candidate, "title", "") or getattr(candidate, "name", "Sugerencia")
            desc = getattr(candidate, "description", "") or getattr(candidate, "summary", "") or "Revisión pendiente"
            card = Card(title, desc)
            row = QHBoxLayout()
            accept = QPushButton("Aceptar")
            reject = QPushButton("Rechazar")
            accept.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._accept(cid))
            reject.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._reject(cid))
            row.addStretch(1)
            row.addWidget(accept)
            row.addWidget(reject)
            card.layout.addLayout(row)
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

    def _accept(self, candidate_id: str):
        _apptrace(f"WS candidate_review_accept id={candidate_id[:40]}")
        result = self.controller.accept(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()

    def _reject(self, candidate_id: str):
        _apptrace(f"WS candidate_review_reject id={candidate_id[:40]}")
        result = self.controller.reject(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()


class SuggestionInboxPanel(_SimpleFormPanel):
    """Unified suggestion inbox with type, origin, summary and focus action."""

    def __init__(self, controller, on_changed, on_focus=None):
        super().__init__("Bandeja de sugerencias", "Candidatos IA generados por coherencia, worldbuilding e importación.")
        self.controller = controller
        self.on_changed = on_changed
        self.on_focus = on_focus
        self.cards = QWidget()
        self.cards_layout = QVBoxLayout(self.cards)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.layout.addWidget(make_scroll_area(self.cards), 1)
        self.refresh()

    def refresh(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        candidates = self.controller.list_all()
        if not candidates:
            self.cards_layout.addWidget(EmptyState("Sin sugerencias", "Cuando la IA proponga candidatos aparecerán aquí."))
            return
        for candidate in candidates:
            title = getattr(candidate, "title", "") or getattr(candidate, "name", "Sugerencia")
            cand_type = str(getattr(getattr(candidate, "candidate_type", ""), "value", ""))
            origin = getattr(candidate, "source", "") or ""
            state = str(getattr(getattr(candidate, "state", ""), "value", ""))
            confidence = getattr(candidate, "confidence", 0)
            summary = getattr(candidate, "summary", "") or getattr(candidate, "description", "") or ""
            if not summary and cand_type:
                summary = f"Candidato de tipo {cand_type}"
            # Card subtitle
            subtitle_parts = []
            if cand_type:
                subtitle_parts.append(cand_type)
            if origin:
                subtitle_parts.append(origin)
            if state:
                subtitle_parts.append(state)
            if confidence:
                subtitle_parts.append(f"{confidence:.0%}")
            subtitle = " · ".join(subtitle_parts) if subtitle_parts else summary or "Pendiente de revisión"
            card = Card(title, subtitle)
            row = QHBoxLayout()
            focus_btn = QPushButton("Enfocar")
            focus_btn.setToolTip("Ir al elemento relacionado en el grafo")
            focus_btn.setEnabled(bool(self.on_focus))
            focus_btn.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._focus(cid))
            accept = QPushButton("Aceptar")
            reject = QPushButton("Descartar")
            accept.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._accept(cid))
            reject.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._reject(cid))
            row.addStretch(1)
            row.addWidget(focus_btn)
            row.addWidget(accept)
            row.addWidget(reject)
            card.layout.addLayout(row)
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

    def _focus(self, candidate_id: str):
        if self.on_focus is None:
            return
        candidates = self.controller.list_all()
        for c in candidates:
            if getattr(c, "id", "") == candidate_id:
                proposed = getattr(c, "proposed_data", {}) or {}
                entity_id = proposed.get("entity_id") or proposed.get("source_id") or proposed.get("target_id") or ""
                if entity_id:
                    self.on_focus(entity_id)
                else:
                    from hosts.DesktopHostPySide.app_context import AppContext
                    pass  # no entity to focus
                break

    def _accept(self, candidate_id: str):
        _apptrace(f"WS suggestion_accept id={candidate_id[:40]}")
        result = self.controller.accept(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()

    def _reject(self, candidate_id: str):
        _apptrace(f"WS suggestion_reject id={candidate_id[:40]}")
        result = self.controller.reject(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()


class NarrativeWorkbench(QWidget):
    """Normal-mode clean entry points for creation work."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__()
        self.workspace = workspace
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(SectionHeader(
            "Taller narrativo",
            "Crea y organiza sin tablas técnicas; los detalles avanzados quedan detrás del modo avanzado."
        ))
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)
        actions = [
            ("Hoja", "Crear personaje, lugar, objeto o concepto.", "Nueva hoja", self.workspace.open_entity_create),
            ("Relaciones", "Conecta nodos visualmente desde el grafo.", "Ir al grafo", self.workspace.open_graph),
            ("Sugerencias", "Revisa candidatos como tarjetas.", "Revisar", self.workspace.open_candidates_clean),
            ("Fuentes", "Guarda referencias legibles.", "Nueva fuente", self.workspace.open_source_create),
            ("Anillos", "Organiza el worldbuilding por estratos.", "Nuevo anillo", self.workspace.open_layer_create),
        ]
        self._cards: dict[str, tuple[QWidget, int, int]] = {}
        for idx, (title, desc, button, callback) in enumerate(actions):
            card = Card(title, desc)
            btn = QPushButton(button)
            if idx == 0:
                btn.setObjectName("primaryButton")
            btn.clicked.connect(callback)
            card.layout.addWidget(btn)
            row, col = idx // 2, idx % 2
            self._cards[title] = (card, row, col)
            grid.addWidget(card, row, col)
        layout.addWidget(grid_host)

        # Store layer card data for worldbuilding visibility control
        self._layer_card_data = self._cards.get("Anillos")

        # Worldbuilding layer chips section
        self._layer_section = QWidget()
        layer_section_layout = QVBoxLayout(self._layer_section)
        layer_section_layout.setContentsMargins(0, 8, 0, 0)
        layer_section_layout.setSpacing(6)

        layer_header = QLabel("Anillos de worldbuilding")
        layer_header.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #7A733D; background: transparent; border: none;"
        )
        layer_section_layout.addWidget(layer_header)

        self._layer_chips_container = QWidget()
        self._chips_layout = QHBoxLayout(self._layer_chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(8)
        layer_section_layout.addWidget(self._layer_chips_container)

        self._layer_empty = QLabel("Worldbuilding activo. Aún no hay anillos.")
        self._layer_empty.setStyleSheet(
            "font-size: 11px; color: #8C8A74; background: transparent; border: none; font-style: italic;"
        )
        layer_section_layout.addWidget(self._layer_empty)

        layout.addWidget(self._layer_section)
        self._layer_section.setVisible(False)  # hidden by default

        # Check worldbuilding on init
        project = self._get_active_project()
        if project:
            wb = getattr(project, "worldbuilding_active", False)
            self.set_worldbuilding_active(wb)
        else:
            self.set_worldbuilding_active(False)
        layout.addWidget(EmptyState(
            "Modo normal activo",
            "IDs, JSON, tablas técnicas y metadatos quedan en Avanzado. La funcionalidad sigue disponible con lenguaje narrativo."
        ))
        layout.addStretch(1)

    def _get_active_project(self):
        pc = getattr(self.workspace.ctx, "project_controller", None)
        if pc:
            return getattr(pc.ps, "active_project", None)
        return None

    def set_worldbuilding_active(self, active: bool):
        """Show/hide the Capas card based on worldbuilding status."""
        if self._layer_card_data:
            card, row, col = self._layer_card_data
            card.setVisible(active)
        self.refresh_layers()

    def refresh_layers(self):
        """Update layer chips based on current project layers."""
        project = self._get_active_project()
        if project is None or not getattr(project, "worldbuilding_active", False):
            self._layer_section.setVisible(False)
            return

        self._layer_section.setVisible(True)

        # Clear existing chips
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Get layers from controller
        layers = []
        if self.workspace.layer_controller:
            try:
                layers = self.workspace.layer_controller.list_all() or []
            except Exception:
                layers = []

        if not layers:
            self._layer_empty.setVisible(True)
            self._layer_chips_container.setVisible(False)
            return

        self._layer_empty.setVisible(False)
        self._layer_chips_container.setVisible(True)

        for layer in layers[:8]:  # max 8 chips
            name = getattr(layer, "name", getattr(layer, "title", "Anillo"))
            chip = QLabel(f"  {name}  ")
            chip.setStyleSheet(
                "background: #E8E5D4; border: 1px solid #C9C5B1; border-radius: 10px; "
                "padding: 3px 10px; font-size: 11px; color: #6E705E; "
                "font-family: Georgia, 'Courier New', serif;"
            )
            self._chips_layout.addWidget(chip)
        self._chips_layout.addStretch(1)



class AIJobsPanel(_SimpleFormPanel):
    """Visible queue/list for command-bar AI jobs."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__("Tareas IA", "Jobs de Dendro en segundo plano. Ninguno canoniza automáticamente.")
        self.workspace = workspace
        self.jobs_layout = QVBoxLayout()
        self.jobs_layout.setSpacing(10)
        self.layout.addLayout(self.jobs_layout)
        self.layout.addStretch(1)
        self.refresh()

    def refresh(self):
        while self.jobs_layout.count():
            item = self.jobs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        jobs = self.workspace.ai_job_service.list_jobs()
        if not jobs:
            self.jobs_layout.addWidget(EmptyState("Sin tareas IA", "Lanza una petición desde la command bar."))
            return
        for job in reversed(jobs):
            card = Card(self._job_title(job), self._job_description(job))
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(int(max(0.0, min(1.0, float(getattr(job, "progress", 0.0)))) * 100))
            card.layout.addWidget(progress)
            row = QHBoxLayout()
            view = QPushButton("Ver resultado")
            view.setEnabled(str(getattr(job, "status", "")) == "AIJobStatus.READY_FOR_REVIEW" or getattr(job, "status", "") == "ready_for_review")
            view.clicked.connect(lambda _, jid=getattr(job, "id", ""): self.workspace._open_ai_job_result_by_id(jid))
            cancel = QPushButton("Cancelar")
            cancel.setEnabled(getattr(job, "cancellable", True) and str(getattr(job, "status", "")) not in {"AIJobStatus.READY_FOR_REVIEW", "AIJobStatus.FAILED", "AIJobStatus.CANCELLED"})
            cancel.clicked.connect(lambda _, jid=getattr(job, "id", ""): self._cancel(jid))
            row.addStretch(1)
            row.addWidget(view)
            row.addWidget(cancel)
            card.layout.addLayout(row)
            self.jobs_layout.addWidget(card)

    def _job_title(self, job) -> str:
        prompt = str(getattr(job, "prompt", "") or "Tarea IA").replace("\n", " ")
        return prompt[:80]

    def _job_description(self, job) -> str:
        status = getattr(getattr(job, "status", ""), "value", getattr(job, "status", ""))
        job_type = getattr(getattr(job, "type", ""), "value", getattr(job, "type", ""))
        message = getattr(job, "message", "") or ""
        error = getattr(job, "error", "") or ""
        if error:
            message = f"{message}: {error}"
        return f"{str(job_type).replace('_', ' ')} · {status} · {message}"

    def _cancel(self, job_id: str):
        result = self.workspace.ai_job_service.cancel_job(job_id)
        if isinstance(result, Error):
            self.workspace.ctx.log("warning", result.error)
        self.workspace._sync_jobs_indicator()
        self.refresh()

class AIJobResultPanel(_SimpleFormPanel):
    """Review panel for a completed command-bar job.

    This panel summarizes the result and lets the user push structural output to
    the existing suggestion inbox.  It never applies canon changes directly.
    """

    def __init__(self, job, candidate_controller, on_candidates_created):
        super().__init__("Resultado de Dendro", "Revisa el resultado antes de aceptar cualquier cambio.")
        self.job = job
        self.candidate_controller = candidate_controller
        self.on_candidates_created = on_candidates_created
        result = getattr(job, "result", {}) or {}

        self.layout.addWidget(Badge(str(getattr(job, "type", "")).replace("AIJobType.", "").replace("_", " ")))
        report = QTextEdit()
        report.setReadOnly(True)
        report.setMinimumHeight(160)
        report.setPlainText(str(result.get("report") or result.get("summary") or "Resultado listo para revisión."))
        self.layout.addWidget(report)

        count = len(result.get("candidates") or [])
        self.status = self.add_status()
        self.status.setText(f"{count} candidato(s) revisable(s). Nada se ha canonizado.")

        row = QHBoxLayout()
        send = QPushButton("Enviar a sugerencias")
        send.setObjectName("primaryButton")
        send.clicked.connect(self._send_candidates)
        row.addStretch(1)
        row.addWidget(send)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _send_candidates(self):
        candidates = (getattr(self.job, "result", {}) or {}).get("candidates") or []
        if not candidates:
            self.status.setText("Este job no produjo candidatos estructurales.")
            return
        created = 0
        for data in candidates:
            result = self.candidate_controller.create(dict(data))
            if isinstance(result, Error):
                self.status.setText(result.error)
                return
            created += 1
        self.status.setText(f"{created} candidato(s) enviados a la bandeja de sugerencias.")
        self.on_candidates_created()


class _AIJobWorker(QThread):
    """Run an AI job outside the UI thread."""

    statusChanged = Signal(str, str, float)
    finishedOk = Signal(str)
    failed = Signal(str, str)

    def __init__(self, service: AIJobService, job_id: str):
        super().__init__()
        self.service = service
        self.job_id = job_id

    def _emit_job(self):
        result = self.service.get_job(self.job_id)
        if isinstance(result, Error):
            self.failed.emit(self.job_id, result.error)
            return None
        job = result.value
        self.statusChanged.emit(job.status.value, job.message, float(job.progress))
        return job

    def run(self):
        try:
            self._emit_job()
            result = self.service.execute_job(self.job_id, progress_callback=lambda _job: self._emit_job())
            job = self._emit_job()
            if isinstance(result, Error):
                self.failed.emit(self.job_id, result.error)
                return
            if job is None:
                return
            self.finishedOk.emit(self.job_id)
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            self.failed.emit(self.job_id, str(exc))


class CreationSearchPanel(_SimpleFormPanel):
    """B37-T01 clean graph search panel inside the right drawer."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__("Buscar en Creación", "Encuentra nodos, árboles o relaciones sin tablas técnicas.")
        self.workspace = workspace
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, tipo, descripción, rama, relación o anillo")
        self.search.textChanged.connect(self._run_search)
        self.layout.addWidget(self.search)
        self.status = self.add_status()
        self.results_layout = QVBoxLayout()
        self.results_layout.setSpacing(6)
        self.layout.addLayout(self.results_layout)
        self.layout.addStretch(1)
        self._run_search("")

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _run_search(self, text: str):
        _apptrace(f"WS run_search query={text[:60]}")
        self._clear_results()
        query = (text or "").strip()
        if not query:
            self.status.setText("Escribe para buscar en el grafo actual.")
            return
        results = self.workspace.graph.search(query)
        if not results:
            self.status.setText("Sin resultados.")
            return
        self.status.setText(f"{len(results)} resultado(s). Selecciona uno para enfocarlo.")
        for result in results:
            self.results_layout.addWidget(self._result_button(result))

    def _result_button(self, result: GraphSearchResult) -> QPushButton:
        title, details, summary = result.display_lines()
        collapsed_hint = "\nDentro de árbol colapsado: se expandirá la ruta al enfocar." if result.is_inside_collapsed_tree else ""
        button = QPushButton(f"{title}\n{details}{collapsed_hint}\n{summary}".strip())
        button.setStyleSheet(
            "QPushButton { text-align: left; background: #F8F5EA; border: 1px solid #D8D2BF; "
            "border-radius: 10px; padding: 8px; color: #4F4D38; } "
            "QPushButton:hover { background: #FFFDF6; border-color: #AFA77A; }"
        )
        button.clicked.connect(lambda _=False, r=result: self._focus_result(r))
        return button

    def _focus_result(self, result: GraphSearchResult):
        ok = self.workspace.focus_search_result(result)
        if ok:
            self.status.setText(f"Enfocado: {result.title}")
        else:
            self.status.setText("No se pudo enfocar. Puede estar oculto por filtros activos; limpia filtros e inténtalo de nuevo.")


class CreationFilterPanel(_SimpleFormPanel):
    """B37-T02 visual filters. Ephemeral: never writes project/canon."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__("Filtros visuales", "Reduce la vista sin modificar el proyecto ni el canon.")
        self.workspace = workspace
        self.status = self.add_status()
        form = QFormLayout()
        self.entity_type = QComboBox()
        self.relation_type = QComboBox()
        self.relation_family = QComboBox()
        self.tree = QComboBox()
        self.layer = QComboBox()
        self.canon = QComboBox()
        self.visibility = QComboBox()
        self.show_relations = QCheckBox("Mostrar relaciones")
        self.show_relations.setChecked(True)
        for combo in (self.entity_type, self.relation_type, self.relation_family, self.tree, self.layer, self.canon, self.visibility):
            combo.addItem("— Cualquiera —", "")
        for label, value in (("Pertenencia estructural", "estructural"), ("Narrativa", "narrativa"), ("Causal", "causal"), ("Coherencia/incidencias", "coherencia")):
            self.relation_family.addItem(label, value)
        self._populate()
        form.addRow("Tipo", self.entity_type)
        form.addRow("Tipo relación", self.relation_type)
        form.addRow("Familia relación", self.relation_family)
        form.addRow("Rama", self.tree)
        if self._worldbuilding_active():
            form.addRow("Anillo", self.layer)
        form.addRow("Estado", self.canon)
        form.addRow("Visibilidad", self.visibility)
        form.addRow("Relaciones", self.show_relations)
        self.layout.addLayout(form)
        for widget in (self.entity_type, self.relation_type, self.relation_family, self.tree, self.layer, self.canon, self.visibility):
            widget.currentIndexChanged.connect(self._apply)
        self.show_relations.toggled.connect(self._apply)
        row = QHBoxLayout()
        clear = QPushButton("Limpiar filtros")
        clear.clicked.connect(self._clear)
        row.addStretch(1)
        row.addWidget(clear)
        self.layout.addLayout(row)
        self.layout.addStretch(1)
        self._sync_status()

    def _worldbuilding_active(self) -> bool:
        project = self.workspace._get_active_project()
        return bool(getattr(project, "worldbuilding_active", False)) if project is not None else False

    def _add_unique(self, combo: QComboBox, label: str, value: str, seen: set[str]):
        value = str(value or "").lower()
        if not value or value in seen:
            return
        seen.add(value)
        combo.addItem(label, value)

    def _populate(self):
        project = self.workspace._get_active_project()
        entities = list(getattr(project, "entities", []) or []) if project is not None else []
        relations = list(getattr(project, "relations", []) or []) if project is not None else []
        seen_entity: set[str] = set()
        seen_canon: set[str] = set()
        seen_vis: set[str] = set()
        for entity in entities:
            kind = str(getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "")) or "")
            self._add_unique(self.entity_type, enum_human(kind), kind, seen_entity)
            canon = str(getattr(getattr(entity, "canon_state", None), "value", getattr(entity, "canon_state", "")) or "")
            self._add_unique(self.canon, enum_human(canon), canon, seen_canon)
            visibility = str(getattr(getattr(entity, "visibility_state", None), "value", getattr(entity, "visibility_state", "")) or "")
            self._add_unique(self.visibility, enum_human(visibility), visibility, seen_vis)
            if kind.lower() == "contenedor":
                self.tree.addItem(str(getattr(entity, "name", "Rama")), str(getattr(entity, "id", "")))
        seen_rel: set[str] = set()
        for relation in relations:
            kind = str(getattr(getattr(relation, "relation_type", None), "value", getattr(relation, "relation_type", "")) or "")
            self._add_unique(self.relation_type, enum_human(kind), kind, seen_rel)
        if self._worldbuilding_active():
            for layer in list(getattr(project, "world_layers", []) or []):
                if getattr(layer, "is_visible", True):
                    self.layer.addItem(str(getattr(layer, "name", "Anillo")), str(getattr(layer, "id", "")))

    def _state(self) -> VisualFilterState:
        def one(combo: QComboBox) -> tuple[str, ...]:
            value = str(combo.currentData() or "")
            return (value,) if value else ()
        return VisualFilterState(
            entity_types=one(self.entity_type),
            relation_types=one(self.relation_type),
            relation_families=one(self.relation_family),
            tree_id=str(self.tree.currentData() or ""),
            layer_ids=one(self.layer) if self._worldbuilding_active() else (),
            canon_states=one(self.canon),
            visibility_states=one(self.visibility),
            show_relations=bool(self.show_relations.isChecked()),
        )

    def _apply(self):
        _apptrace("WS filter_apply")
        self.workspace.apply_creation_filter(self._state())
        self._sync_status()

    def _clear(self):
        _apptrace("WS filter_clear")
        self.entity_type.setCurrentIndex(0)
        self.relation_type.setCurrentIndex(0)
        self.relation_family.setCurrentIndex(0)
        self.tree.setCurrentIndex(0)
        self.layer.setCurrentIndex(0)
        self.canon.setCurrentIndex(0)
        self.visibility.setCurrentIndex(0)
        self.show_relations.setChecked(True)
        self.workspace.clear_creation_filters()
        self._sync_status()

    def _sync_status(self):
        count = self.workspace.graph.active_filter_count()
        self.status.setText(f"{count} filtro(s) activo(s)." if count else "Sin filtros activos.")



# ── Left-edge layer flyout ──────────────────────────────────────────────

class _LayerEdgeFlyout(QFrame):
    """Persistent left drawer for causal layers when Worldbuilding is ON.

    B38 replaces fragile hover reveal with an explicit top-bar button.
    The drawer stays open until the user toggles it closed.
    """

    LAYER_BG = "rgba(248,246,237,0.96)"
    LAYER_BORDER = "#D8D6C8"
    CHIP_BG = "rgba(255,255,255,0.55)"
    CHIP_ACTIVE_BG = "rgba(175,167,122,0.22)"
    CHIP_HOVER_BG = "rgba(255,255,255,0.80)"
    TEXT_COLOR = "#6F6A42"
    TEXT_ACTIVE = "#504B2E"
    MUTED = "#8C8A74"

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__(workspace)
        self._workspace = workspace
        self.setObjectName("layerEdgeFlyout")
        self.setFixedWidth(240)
        self.setStyleSheet(
            f"QFrame#layerEdgeFlyout {{ background: {self.LAYER_BG}; "
            f"border-right: 2px solid {self.LAYER_BORDER}; "
            f"border-top: 1px solid {self.LAYER_BORDER}; "
            f"border-bottom: 1px solid {self.LAYER_BORDER}; "
            f"border-radius: 0 10px 10px 0; }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Header
        header = QLabel("Anillos causales")
        header.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {self.TEXT_ACTIVE}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(header)

        hint = QLabel("Clic para enfocar anillo · contador visible")
        hint.setStyleSheet(
            f"font-size: 10px; color: {self.MUTED}; background: transparent; "
            f"border: none; font-style: italic;"
        )
        layout.addWidget(hint)

        # Toggle layers mode button
        self._toggle_btn = QPushButton("Vista por bandas")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: {self.CHIP_BG}; border: 1px solid {self.LAYER_BORDER}; "
            f"border-radius: 8px; padding: 5px 10px; color: {self.TEXT_COLOR}; font-size: 11px; }} "
            f"QPushButton:checked {{ background: {self.CHIP_ACTIVE_BG}; border-color: #AFA77A; }} "
            f"QPushButton:hover {{ background: {self.CHIP_HOVER_BG}; }}"
        )
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_layers_mode)
        layout.addWidget(self._toggle_btn)

        # Scroll area for layer chips
        self._chips_widget = QWidget()
        self._chips_layout = QVBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(0, 4, 0, 0)
        self._chips_layout.setSpacing(4)
        self._chips_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._chips_widget)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }} "
            f"QScrollBar:vertical {{ width: 4px; background: transparent; }} "
            f"QScrollBar::handle:vertical {{ background: {self.LAYER_BORDER}; border-radius: 2px; }}"
        )
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

        # Clear filter button
        self._clear_btn = QPushButton("Quitar filtro")
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {self.LAYER_BORDER}; "
            f"border-radius: 8px; padding: 4px 10px; color: {self.MUTED}; font-size: 10px; }} "
            f"QPushButton:hover {{ background: {self.CHIP_HOVER_BG}; color: {self.TEXT_COLOR}; }}"
        )
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_layer_filter)
        layout.addWidget(self._clear_btn)

        # State
        self._active_layer_id: str | None = None
        self._layer_chips: dict[str, QPushButton] = {}

        # Initially hidden
        self.setVisible(False)
        self._layers_loaded = False

    def _layer_counts(self) -> dict[str, int]:
        """Count visible project elements per layer without exposing IDs."""
        project = self._workspace._get_active_project()
        counts: dict[str, int] = {}
        if project is None:
            return counts
        collections = [
            getattr(project, "entities", None),
            getattr(project, "relations", None),
        ]
        for collection in collections:
            if collection is None:
                continue
            values = collection.values() if hasattr(collection, "values") else collection
            for item in values or []:
                for lid in getattr(item, "layer_ids", []) or []:
                    if lid:
                        counts[str(lid)] = counts.get(str(lid), 0) + 1
        return counts

    def populate_layers(self):
        """Fill chip list from project layers only.

        Default causal layers are a selectable template, never a visual fallback
        for an empty project.
        """
        # Clear existing
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._layer_chips.clear()

        project = self._workspace._get_active_project()
        layers = list(getattr(project, "world_layers", []) or []) if project is not None else []

        # Sort by order
        layers = sorted(layers, key=lambda l: getattr(l, "order", 99))
        counts = self._layer_counts()

        for layer in layers:
            lid = str(getattr(layer, "id", ""))
            name = str(getattr(layer, "name", ""))
            if not lid or not name:
                continue
            total = counts.get(lid, 0)
            chip = QPushButton(f"{name}  ·  {total}")
            chip.setCheckable(True)
            chip.setProperty("layer_id", lid)
            chip.setStyleSheet(
                f"QPushButton {{ background: {self.CHIP_BG}; border: 1px solid {self.LAYER_BORDER}; "
                f"border-radius: 6px; padding: 4px 8px; color: {self.TEXT_COLOR}; "
                f"font-size: 11px; text-align: left; }} "
                f"QPushButton:checked {{ background: {self.CHIP_ACTIVE_BG}; "
                f"border-color: #AFA77A; color: {self.TEXT_ACTIVE}; font-weight: bold; }} "
                f"QPushButton:hover {{ background: {self.CHIP_HOVER_BG}; }}"
            )
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda checked, _lid=lid: self._on_chip_clicked(_lid))
            # Insert before the stretch
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
            self._layer_chips[lid] = chip

        self._layers_loaded = True

    def _on_chip_clicked(self, layer_id: str):
        """Toggle layer filter on chip click."""
        if self._active_layer_id == layer_id:
            # Deselect
            self._clear_layer_filter()
            return
        # Activate this layer
        self._active_layer_id = layer_id
        for lid, chip in self._layer_chips.items():
            chip.setChecked(lid == layer_id)
        # Apply visual filter
        self._workspace._apply_layer_filter(layer_id)

    def _clear_layer_filter(self):
        """Remove layer filter."""
        self._active_layer_id = None
        for chip in self._layer_chips.values():
            chip.setChecked(False)
        self._workspace._clear_layer_filter()

    def _toggle_layers_mode(self, checked: bool):
        """Toggle the band-based layers view."""
        if checked:
            self._workspace._activate_layers_view()
        else:
            self._workspace._deactivate_layers_view()

    def show_flyout(self):
        """Show the flyout if worldbuilding is active."""
        project = self._workspace._get_active_project()
        if not project or not getattr(project, "worldbuilding_active", False):
            return
        if not self._layers_loaded:
            self.populate_layers()
        self.setVisible(True)
        self.raise_()

    def hide_flyout(self):
        """Hide the flyout."""
        self.setVisible(False)

    def update_toggle_state(self, layers_active: bool):
        """Sync the toggle button with the current layers mode."""
        self._toggle_btn.setChecked(layers_active)


class CausalMilestonePanel(_SimpleFormPanel):
    """Drawer panel for creating and reviewing causal milestones (B41-T03).

    Uses cards, not tables. No IDs or JSON shown to the user.
    All mutations go through CausalMilestoneController → CausalMilestoneService.
    """

    def __init__(self, controller, on_created=None, prefill: dict | None = None):
        super().__init__("Hito causal", "Evento histórico que explica el estado actual del mundo.")
        self.controller = controller
        self.on_created = on_created
        self._prefill = prefill or {}
        form = QFormLayout()
        self._title = QLineEdit()
        self._title.setPlaceholderText("Nombre del hito")
        self._type = QComboBox()
        self._type.addItems([
            "origen", "fundacion", "ruptura", "guerra", "pacto",
            "traicion", "descubrimiento", "catastrofe", "reforma",
            "prohibicion", "revelacion", "migracion", "ascenso",
            "caida", "transformacion", "consecuencia", "estado_actual",
        ])
        self._desc = QTextEdit()
        self._desc.setPlaceholderText("Descripción del hito")
        self._desc.setMinimumHeight(80)
        self._rationale = QTextEdit()
        self._rationale.setPlaceholderText("Por qué este hito es importante (opcional)")
        self._rationale.setMaximumHeight(60)
        form.addRow("Nombre", self._title)
        form.addRow("Tipo", self._type)
        form.addRow("Descripción", self._desc)
        form.addRow("Razón", self._rationale)
        self.layout.addLayout(form)
        self._status = self.add_status()

        # Cards for existing milestones
        self._cards_container = QVBoxLayout()
        self._cards_container.setSpacing(6)
        self.layout.addLayout(self._cards_container)
        self._refresh_cards()

        row = QHBoxLayout()
        save = QPushButton("Crear hito")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _refresh_cards(self):
        while self._cards_container.count():
            item = self._cards_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        hitos = self.controller.list_all()
        for hito in hitos:
            card = Card(
                title=getattr(hito, "title", "Sin nombre"),
                subtitle=str(getattr(getattr(hito, "milestone_type", ""), "value", "")),
            )
            desc = getattr(hito, "description", "")
            if desc:
                card.add_text(desc, muted=True)
            self._cards_container.addWidget(card)

    def _save(self):
        title = self._title.text().strip()
        if not title:
            self._status.setText("El nombre es obligatorio")
            return
        result = self.controller.create_manual({
            "title": title,
            "milestone_type": self._type.currentText(),
            "description": self._desc.toPlainText().strip(),
            "rationale": self._rationale.toPlainText().strip(),
            **self._prefill,
        })
        if isinstance(result, Error):
            self._status.setText(result.error)
            return
        self._status.setText(f"Hito creado: {title}")
        self._refresh_cards()
        if self.on_created:
            self.on_created()


class CreationWorkspace(QWidget):
    """Creation space: graph-first immersive experience."""

    def __init__(self, ctx: AppContext, *, corpus_view, relation_view, candidate_view,
                 import_export_view, writing_view, timeline_view, framework_view,
                 source_view=None, layer_view=None):
        super().__init__()
        self.ctx = ctx
        self.import_export_view = import_export_view
        self.writing_view = writing_view
        self.timeline_view = timeline_view
        self.framework_view = framework_view
        self.corpus_view = corpus_view
        self.relation_view = relation_view
        self.candidate_view = candidate_view
        self.source_view = source_view
        self.layer_view = layer_view
        self.source_controller = getattr(source_view, "ctrl", None)
        self.layer_controller = getattr(layer_view, "ctrl", None)
        self.entity_controller = getattr(corpus_view, "ec", None)
        self.relation_controller = getattr(relation_view, "rc", None)
        self.ai_context_controller = None
        self.ai_job_service = AIJobService()
        self._ai_workers = {}
        self._active_layer_id = ""
        self._advanced_mode = bool(ctx.advanced_mode)
        project_controller = getattr(ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is not None:
            self.ai_context_controller = AIContextController(project_service)
            self._milestone_ctrl = CausalMilestoneController(project_service)
        else:
            self._milestone_ctrl = None

        self._build_ui()

        # Apply worldbuilding visibility based on current project
        project = self._get_active_project()
        if project:
            wb = getattr(project, "worldbuilding_active", False)
            self.set_worldbuilding_active(wb)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Persistent top toolbar: creative graph actions left, utilities right.
        self._top_toolbar = self._build_top_toolbar()
        self._top_toolbar.setFixedHeight(48)
        self._top_toolbar.setVisible(True)
        layout.addWidget(self._top_toolbar)

        # Graph canvas (takes all space)
        self.graph = GraphCanvasWidget(self.ctx)
        self.graph.set_ai_controller(self.ai_context_controller)
        self.graph.entitySelected.connect(self._open_node_panel)
        self.graph.relationSelected.connect(self._open_relation_panel)
        self.graph.relationCreateRequested.connect(self._open_relation_create_panel)
        self.graph.relationCreateRejected.connect(self._on_relation_create_rejected)
        self.graph.graphSelectionChanged.connect(self._on_graph_selection_changed)
        self.graph.nodeAssignToTreeRequested.connect(self._assign_node_to_tree)
        self.graph.ringSelected.connect(self._on_ring_selected)
        self.graph.ringFocused.connect(self._on_ring_focused)
        # BETA1-B01: context-menu intents → existing creation/deletion routes
        self.graph.contextCreateEntityRequested.connect(self._create_entity_on_graph)
        self.graph.contextCreateTreeRequested.connect(self._create_tree_on_graph)
        self.graph.contextCreateEntityInTreeRequested.connect(self._create_entity_in_tree)
        self.graph.contextCreateSubtreeRequested.connect(self._create_subtree_in_tree)
        self.graph.contextDeleteRequested.connect(self._delete_selected)
        # BETA1-B02: Escape closes the contextual drawer after the canvas has
        # cancelled modes and cleared the selection
        self.graph.escapePressed.connect(self._on_canvas_escape)
        # BETA1-B03: 'Mover a anillo' → EntityController.update (layer_ids)
        self.graph.nodeAssignToRingRequested.connect(self._assign_node_to_ring)
        # BETA1-B03: ring CRUD → LayerController
        self.graph.ringCreateRequested.connect(self._open_ring_create_panel)
        self.graph.ringEditRequested.connect(self._open_ring_edit_panel)
        self.graph.ringDeleteRequested.connect(self._delete_ring)
        # BETA1-B03: drag-out extraction → remove 'contiene' membership
        self.graph.nodeExtractFromTreeRequested.connect(self._extract_node_from_tree)
        layout.addWidget(self.graph, 1)

        # Command bar area replaces the old bottom button toolbar.
        command_bar = self._build_command_bar()
        layout.addWidget(command_bar)

        # Left layer drawer is persistent: explicit button toggles it.
        self._layer_flyout = _LayerEdgeFlyout(self)
        self._layer_flyout.setVisible(False)

        self.setMouseTracking(True)
        self.graph.setMouseTracking(True)

    def _build_top_toolbar(self) -> QWidget:
        """Persistent B38 toolbar: creative actions left, utilities right."""
        bar = QFrame()
        bar.setObjectName("topUtilsBar")
        bar.setStyleSheet(
            "QFrame#topUtilsBar { background: rgba(238,236,221,0.96); "
            "border-bottom: 1px solid #D8D6C8; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(6)

        btn_style = (
            "QPushButton { background: rgba(255,255,255,0.48); border: 1px solid #D8D6C8; "
            "border-radius: 15px; padding: 4px; color: #6F6A42; font-size: 16px; "
            "min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; } "
            "QPushButton:hover { background: #F8F5EA; border: 1px solid #AFA77A; color: #504B2E; }"
        )
        disabled_style = (
            "QPushButton { background: rgba(255,255,255,0.25); border: 1px solid #E0DDD0; "
            "border-radius: 15px; padding: 4px; color: #B8B5A8; font-size: 16px; "
            "min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; } "
        )
        text_btn_style = (
            "QPushButton { background: transparent; border: 1px solid #D0CCB8; "
            "border-radius: 12px; padding: 4px 12px; color: #6F6A42; font-size: 12px; } "
            "QPushButton:hover { background: #F8F5EA; }"
        )
        self._toolbar_btn_style = btn_style
        self._toolbar_disabled_style = disabled_style

        def icon_btn(text: str, tip: str, callback, *, enabled: bool = True) -> QPushButton:
            button = QPushButton(text)
            button.setToolTip(tip)
            button.setStyleSheet(btn_style if enabled else disabled_style)
            button.setEnabled(enabled)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(callback)
            layout.addWidget(button)
            return button

        # Left: primary creative graph actions.
        icon_btn(ICON_GLYPHS["add"], "Crear hoja", self._create_entity_on_graph)
        icon_btn("⊞", "Crear rama", self._create_tree_on_graph)
        self._connect_mode_btn = icon_btn("↔", "Crear relación / modo conexión", self._start_relation_mode)
        self._suggest_entity_btn = icon_btn("✨", "Sugerir hoja con IA", self._suggest_node)
        self._coherence_btn = icon_btn("⚠", "Selecciona nodos o relaciones para analizar coherencia", self._open_coherence_panel, enabled=False)
        icon_btn("⌕", "Buscar y enfocar elementos", self._open_search_panel)
        self._filter_btn = icon_btn("◌", "Filtros visuales", self._open_filter_panel)
        self._suggestion_btn = icon_btn("⊹", "Bandeja de sugerencias", self._open_suggestion_inbox)
        self._jobs_btn = icon_btn("Tareas", "Tareas IA en segundo plano", self._open_ai_jobs_panel)
        self._jobs_btn.setStyleSheet(text_btn_style)
        self._jobs_btn.setFixedWidth(74)
        self._suggestion_count = 0
        self._layers_toggle_btn = icon_btn("Anillos", "Abrir/cerrar panel de anillos causales", self._toggle_layer_drawer)
        self._layers_toggle_btn.setStyleSheet(text_btn_style)
        self._layers_toggle_btn.setFixedWidth(72)

        self._milestone_btn = QPushButton("Crear hito")
        self._milestone_btn.setToolTip("Crear un hito causal/histórico")
        self._milestone_btn.setStyleSheet(text_btn_style)
        self._milestone_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._milestone_btn.clicked.connect(self._open_hito_panel)
        layout.addWidget(self._milestone_btn)

        self._hito_from_sel_btn = QPushButton("Hito desde selección")
        self._hito_from_sel_btn.setToolTip("Crear hito explicativo desde la selección actual")
        self._hito_from_sel_btn.setStyleSheet(text_btn_style)
        self._hito_from_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hito_from_sel_btn.clicked.connect(self._create_hito_from_selection)
        layout.addWidget(self._hito_from_sel_btn)

        self._global_focus_btn = QPushButton("Vista global")
        self._global_focus_btn.setToolTip("Volver a mostrar todo el grafo")
        self._global_focus_btn.setStyleSheet(text_btn_style)
        self._global_focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._global_focus_btn.clicked.connect(self.clear_focus_scope)
        self._global_focus_btn.setVisible(False)
        layout.addWidget(self._global_focus_btn)

        self._focus_label = QLabel("Mostrando todo")
        self._focus_label.setStyleSheet("color: #6F6A42; font-size: 11px; padding: 0 8px;")
        layout.addWidget(self._focus_label)

        layout.addStretch(1)

        # Right: secondary management / view tools.
        import_btn = QPushButton("Importar documento")
        import_btn.setStyleSheet(text_btn_style)
        import_btn.clicked.connect(lambda: self._open_utility(self.import_export_view))
        layout.addWidget(import_btn)

        self._layers_view_btn = QPushButton("Vista libre/anillos")
        self._layers_view_btn.setToolTip("Alternar vista por bandas causales")
        self._layers_view_btn.setStyleSheet(text_btn_style)
        self._layers_view_btn.clicked.connect(self._toggle_layers_view_from_toolbar)
        layout.addWidget(self._layers_view_btn)

        self._concentric_view_btn = QPushButton("Concéntrica")
        self._concentric_view_btn.setToolTip("Mostrar anillos causales como coronas concéntricas calculadas")
        self._concentric_view_btn.setStyleSheet(text_btn_style)
        self._concentric_view_btn.clicked.connect(self._toggle_concentric_view_from_toolbar)
        layout.addWidget(self._concentric_view_btn)

        fit_btn = QPushButton("Encajar")
        fit_btn.setToolTip("Encajar todo el grafo en pantalla")
        fit_btn.setStyleSheet(text_btn_style)
        fit_btn.clicked.connect(self.fit_all)
        layout.addWidget(fit_btn)

        reset_btn = QPushButton("Centrar")
        reset_btn.setToolTip("Centrar la vista y restaurar zoom")
        reset_btn.setStyleSheet(text_btn_style)
        reset_btn.clicked.connect(self.reset_view)
        layout.addWidget(reset_btn)

        delete_btn = QPushButton("🗑")
        delete_btn.setToolTip("Selecciona algo para eliminar")
        delete_btn.setStyleSheet(disabled_style)
        delete_btn.setEnabled(False)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(self._delete_selected)
        self._delete_btn = delete_btn
        layout.addWidget(delete_btn)

        return bar

    def _build_command_bar(self) -> QWidget:
        """Bottom B38 contextual AI command bar. Creates jobs, never mutates canon."""
        bar = QFrame()
        bar.setObjectName("aiCommandBar")
        bar.setStyleSheet(
            "QFrame#aiCommandBar { background: rgba(250,248,240,0.97); "
            "border-top: 1px solid #D8D6C8; }"
        )
        bar.setFixedHeight(66)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(72, 10, 72, 10)
        layout.setSpacing(10)

        prompt_label = QLabel("Dendro")
        prompt_label.setStyleSheet(
            "color: #6F6A42; font-size: 12px; font-weight: 700; "
            "background: transparent; border: none; padding-right: 4px;"
        )
        prompt_label.setToolTip("Las respuestas IA son candidatas revisables; no cambian canon automáticamente.")
        layout.addWidget(prompt_label)

        self._command_input = QLineEdit()
        self._command_input.setObjectName("aiCommandInput")
        self._command_input.setPlaceholderText("Pide una acción revisable: sugerir personaje, detectar contradicción, expandir causa…")
        self._command_input.setStyleSheet(
            "QLineEdit#aiCommandInput { background: rgba(255,255,255,0.90); "
            "border: 1px solid #D0CCB8; border-radius: 20px; padding: 9px 16px; "
            "font-size: 13px; color: #504B2E; } "
            "QLineEdit#aiCommandInput:focus { border: 2px solid #AFA77A; padding: 8px 15px; background: #FFFFFF; }"
        )
        self._command_input.returnPressed.connect(self._submit_ai_command)
        layout.addWidget(self._command_input, 1)

        self._command_submit_btn = QPushButton("Crear")
        self._command_submit_btn.setToolTip("Crear una tarea IA revisable")
        self._command_submit_btn.setStyleSheet(
            "QPushButton { background: #6F6A42; color: #F8F5EA; border: none; "
            "border-radius: 18px; min-width: 62px; min-height: 36px; font-size: 12px; font-weight: 700; } "
            "QPushButton:hover { background: #504B2E; } "
            "QPushButton:pressed { background: #403B24; padding-top: 2px; }"
        )
        self._command_submit_btn.clicked.connect(self._submit_ai_command)
        layout.addWidget(self._command_submit_btn)

        self._job_status_label = QLabel("Sin tareas IA activas")
        self._job_status_label.setStyleSheet(
            "color: #6F6A42; font-size: 11px; min-width: 190px; "
            "background: transparent; border: none;"
        )
        self._job_status_label.setToolTip("Estado de las tareas IA. Todo resultado queda pendiente de revisión.")
        layout.addWidget(self._job_status_label)
        return bar

    # ── B38 persistent layer drawer and command bar ───────────────────────

    def _start_relation_mode(self):
        """Guide the existing drag-to-connect relation flow; no parallel mode."""
        self.ctx.log("info", "Para crear relación: arrastra desde un nodo o árbol hacia otro elemento del grafo.")

    def _toggle_layer_drawer(self):
        _apptrace("WS toggle_layer_drawer")
        """Persistent explicit drawer: stays open until user toggles it again."""
        project = self._get_active_project()
        active = bool(project and getattr(project, "worldbuilding_active", False))
        if not active:
            self.ctx.log("warning", "Activa Worldbuilding en el proyecto para usar anillos causales")
            return
        if self._layer_flyout.isVisible():
            self._layer_flyout.hide_flyout()
        else:
            self._layer_flyout.show_flyout()

    def _toggle_layers_view_from_toolbar(self):
        _apptrace("WS toggle_layers_view")
        project = self._get_active_project()
        active = bool(project and getattr(project, "worldbuilding_active", False))
        if not active:
            self.ctx.log("warning", "La vista de anillos requiere Worldbuilding activado")
            return
        layer_mode = bool(getattr(getattr(self.graph, "canvas", None), "_layer_mode_active", False))
        if layer_mode:
            self._deactivate_layers_view()
        else:
            self._activate_layers_view()

    def _toggle_concentric_view_from_toolbar(self):
        _apptrace("WS toggle_concentric_view")
        """Toggle B44 calculated concentric rings layout."""
        project = self._get_active_project()
        self.ctx.log(
            "info",
            "B44TRACE workspace_toggle_concentric_enter "
            f"project={project is not None} entities={len(getattr(project, 'entities', []) or []) if project is not None else 'na'} "
            f"project_layers={len(getattr(project, 'world_layers', []) or []) if project is not None else 'na'} "
            f"ctx_layout={getattr(self.ctx, 'creation_layout_mode', '')!r}",
        )
        if project is None:
            self.ctx.log("warning", "Abre o crea un proyecto para usar la vista concéntrica")
            return
        canvas = getattr(self.graph, "canvas", None)
        current = str(getattr(canvas, "_layout_mode_active", "free")) if canvas is not None else "free"
        self.ctx.log(
            "info",
            "B44TRACE workspace_toggle_concentric_current "
            f"canvas_exists={canvas is not None} canvas_layout={current!r} widget_layout={getattr(self.graph, '_layout_mode', '')!r} "
            f"canvas_visible={self.graph.canvas.isVisible() if hasattr(self.graph, 'canvas') else 'na'} "
            f"empty_visible={self.graph.empty.isVisible() if hasattr(self.graph, 'empty') else 'na'}",
        )
        if current == "concentric_rings":
            if hasattr(self.graph, "set_layout_mode"):
                self.graph.set_layout_mode("free")
            else:
                self.graph.set_worldbuilding_active(False)
            self.ctx.log("info", "Vista libre activa")
            return
        if hasattr(self.graph, "set_layout_mode"):
            self.graph.set_layout_mode("concentric_rings")
        else:
            self.graph.set_worldbuilding_active(True)
        self.ctx.log(
            "info",
            "B44TRACE workspace_toggle_concentric_after "
            f"widget_layout={getattr(self.graph, '_layout_mode', '')!r} "
            f"canvas_layout={getattr(getattr(self.graph, 'canvas', None), '_layout_mode_active', '')!r} "
            f"canvas_visible={self.graph.canvas.isVisible() if hasattr(self.graph, 'canvas') else 'na'} "
            f"empty_visible={self.graph.empty.isVisible() if hasattr(self.graph, 'empty') else 'na'} "
            f"ring_items={len(getattr(getattr(self.graph, 'canvas', None), '_ring_items', {}))}",
        )
        if hasattr(self, "_layer_flyout"):
            self._layer_flyout.update_toggle_state(False)
        self.ctx.log("info", "Vista concéntrica de anillos activa")

    def _current_context_scope(self) -> dict:
        project = self._get_active_project()
        layer_ids = tuple(getattr(getattr(self.graph, "canvas", None), "_visual_filter", VisualFilterState()).layer_ids)
        focused_ring_id = self.graph.focused_ring_id() if hasattr(self.graph, "focused_ring_id") else ""
        selected_entity_ids = self.graph.selected_entity_ids() if hasattr(self, "graph") else []
        selected_relation_ids = self.graph.selected_relation_ids() if hasattr(self, "graph") else []
        creative_brief = {}
        creative_context = []
        if project is not None:
            from packages.application.creative_context import (
                project_creative_brief,
                selected_entity_creative_context,
                selected_branch_creative_context,
            )
            creative_brief = project_creative_brief(project)
            creative_context = selected_entity_creative_context(project, selected_entity_ids)
            branch_context = selected_branch_creative_context(project, selected_entity_ids)
        else:
            branch_context = []
        return {
            "project_id": str(getattr(project, "id", "")) if project is not None else "",
            "worldbuilding_active": bool(getattr(project, "worldbuilding_active", False)) if project is not None else False,
            "selected_entity_ids": selected_entity_ids,
            "selected_relation_ids": selected_relation_ids,
            "active_layer_ids": list(layer_ids),
            "active_ring_id": focused_ring_id,
            "focused_ring_id": focused_ring_id,
            "focus_label": self._focus_label.text() if hasattr(self, "_focus_label") else "Global",
            "visual_filters_active": self.graph.active_filter_count() if hasattr(self, "graph") else 0,
            "creative_brief": creative_brief,
            "creative_context": creative_context,
            "branch_creative_context": branch_context,
        }

    def _apply_command_scope_hints(self, prompt: str, scope: dict) -> tuple[str, dict] | None:
        """B44 debt: understand lightweight ring scope phrases without deep NLP."""
        lowered = prompt.lower()
        ring_phrases = ("en este anillo", "dentro del anillo actual", "en el anillo actual")
        if not any(phrase in lowered for phrase in ring_phrases):
            return prompt, scope
        focused_ring_id = str(scope.get("focused_ring_id") or scope.get("active_ring_id") or "")
        if not focused_ring_id:
            self._job_status_label.setText("Entra primero en un anillo para usar “en este anillo”")
            self.ctx.log("warning", "Comando IA con scope de anillo sin anillo enfocado")
            return None
        scoped = dict(scope)
        scoped["command_scope"] = "focused_ring"
        scoped["active_ring_id"] = focused_ring_id
        scoped["focused_ring_id"] = focused_ring_id
        return prompt, scoped

    def _submit_ai_command(self):
        _apptrace(f"WS submit_ai_command prompt={self._command_input.text().strip()[:60]}")
        prompt = self._command_input.text().strip()
        if not prompt:
            self._job_status_label.setText("Escribe una orden para Dendro")
            return
        scope = self._current_context_scope()
        scoped_command = self._apply_command_scope_hints(prompt, scope)
        if scoped_command is None:
            return
        prompt, scope = scoped_command
        job_type = classify_ai_job_intent(prompt, worldbuilding_active=bool(scope.get("worldbuilding_active")))
        result = self.ai_job_service.create_job(job_type, prompt, context_scope=scope)
        if isinstance(result, Error):
            self._job_status_label.setText(result.error)
            self.ctx.log("error", result.error)
            return
        job = result.value
        self._command_input.clear()
        self._job_status_label.setText(f"Job creado: {job.type.value.replace('_', ' ')}")
        pulse_feedback(self._job_status_label)
        self._sync_jobs_indicator()
        self.ctx.log("info", "Job IA creado: resultado revisable, sin cambios automáticos en canon")
        self._start_ai_job_worker(job.id)

    def _start_ai_job_worker(self, job_id: str):
        worker = _AIJobWorker(self.ai_job_service, job_id)
        worker.statusChanged.connect(self._on_ai_job_status)
        worker.finishedOk.connect(self._on_ai_job_finished)
        worker.failed.connect(self._on_ai_job_failed)
        worker.finished.connect(self._on_ai_worker_stopped)
        self._ai_workers[job_id] = worker
        worker.start()

    def _on_ai_job_status(self, status: str, message: str, progress: float):
        percent = int(max(0.0, min(1.0, progress)) * 100)
        self._job_status_label.setStyleSheet(
            "color: #6F6A42; font-size: 11px; min-width: 190px; "
            "background: transparent; border: none;"
        )
        self._job_status_label.setText(f"Dendro: {message} ({percent}%)")
        self._sync_jobs_indicator()

    def _on_ai_job_finished(self, job_id: str):
        result = self.ai_job_service.get_job(job_id)
        if isinstance(result, Error):
            self._job_status_label.setText(result.error)
            return
        job = result.value
        self._job_status_label.setStyleSheet(
            "color: #58744A; font-size: 11px; min-width: 190px; "
            "background: transparent; border: none;"
        )
        self._job_status_label.setText(job.message or "Resultado listo")
        pulse_feedback(self._job_status_label)
        self._sync_jobs_indicator()
        self._open_ai_job_result(job)

    def _on_ai_job_failed(self, job_id: str, error: str):
        self._job_status_label.setText(f"Error: {error}")
        self._job_status_label.setStyleSheet("color: #C0392B; font-size: 11px; min-width: 190px; font-weight: 700;")
        pulse_feedback(self._job_status_label)
        self.ctx.log("error", f"Job IA fallido {job_id}: {error}")
        self._sync_jobs_indicator()
        # Clear error styling after 8 seconds so it doesn't persist forever
        QTimer.singleShot(8000, self._reset_job_status_style)

    def _reset_job_status_style(self):
        self._job_status_label.setStyleSheet(
            "color: #6F6A42; font-size: 11px; min-width: 190px; "
            "background: transparent; border: none;"
        )
        # Only reset text if it's still showing an error
        current = self._job_status_label.text()
        if current.startswith("Error:"):
            self._job_status_label.setText("Sin tareas IA activas")

    def _on_ai_worker_stopped(self):
        self._ai_workers = {jid: worker for jid, worker in self._ai_workers.items() if worker.isRunning()}
        self._sync_jobs_indicator()

    def _open_ai_jobs_panel(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        panel = AIJobsPanel(self)
        drawer.set_content(panel, title="Tareas IA")
        drawer.open()

    def _open_ai_job_result_by_id(self, job_id: str):
        result = self.ai_job_service.get_job(job_id)
        if isinstance(result, Error):
            self.ctx.log("warning", result.error)
            return
        self._open_ai_job_result(result.value)

    def _sync_jobs_indicator(self):
        btn = getattr(self, "_jobs_btn", None)
        if btn is None:
            return
        jobs = self.ai_job_service.list_jobs()
        active = [j for j in jobs if getattr(getattr(j, "status", ""), "value", getattr(j, "status", "")) in {"queued", "building_context", "planning", "waiting_for_model", "running", "postprocessing"}]
        ready = [j for j in jobs if getattr(getattr(j, "status", ""), "value", getattr(j, "status", "")) == "ready_for_review"]
        total = len(active) + len(ready)
        btn.setText(f"Tareas {total}" if total else "Tareas")

    def _open_ai_job_result(self, job):
        drawer = self.ctx.drawer
        controller = getattr(self.candidate_view, "cc", None)
        if drawer is None or controller is None:
            self.ctx.log("warning", "Resultado IA listo, pero no se pudo abrir el panel de revisión")
            return
        panel = AIJobResultPanel(job, controller, on_candidates_created=self._on_job_candidates_created)
        drawer.set_content(panel, title="Resultado IA")
        drawer.open()

    def _on_job_candidates_created(self):
        self._on_suggestion_changed()
        self._open_suggestion_inbox()

    def resizeEvent(self, event):
        """Position persistent layer drawer along the left edge."""
        super().resizeEvent(event)
        if hasattr(self, "_layer_flyout"):
            h = self.height() - 48 - 62  # top toolbar + command bar
            self._layer_flyout.setGeometry(0, 48, 260, max(h, 220))

    def _activate_layers_view(self):
        project = self._get_active_project()
        if project is None or not bool(getattr(project, "worldbuilding_active", False)):
            self.ctx.log("warning", "La vista Anillos solo está disponible con Worldbuilding activado")
            return
        self.ctx.log("info", "Vista Anillos causales activa")
        if hasattr(self.graph, "set_worldbuilding_active"):
            self.graph.set_worldbuilding_active(True)
        else:
            self.refresh()
        if hasattr(self, "_layer_flyout"):
            self._layer_flyout.update_toggle_state(True)

    def _deactivate_layers_view(self):
        """Switch back from layers band view to normal graph view."""
        if hasattr(self.graph, "set_worldbuilding_active"):
            self.graph.set_worldbuilding_active(False)
        else:
            self.refresh()
        if hasattr(self, "_layer_flyout"):
            self._layer_flyout.update_toggle_state(False)

    def _apply_layer_filter(self, layer_id: str):
        _apptrace(f"WS apply_layer_filter layer={layer_id[:40]}")
        """Filter the graph to show only nodes/edges in the selected causal layer."""
        from hosts.DesktopHostPySide.widgets.graph_canvas import VisualFilterState
        self.graph.canvas.apply_visual_filter(
            VisualFilterState(layer_ids=(layer_id,))
        )

    def _clear_layer_filter(self):
        _apptrace("WS clear_layer_filter")
        """Remove layer filter and show all nodes."""
        if hasattr(self.graph, "canvas") and hasattr(self.graph.canvas, "clear_visual_filters"):
            self.graph.canvas.clear_visual_filters()

    def _open_search_panel(self):
        _apptrace("WS open_search_panel")
        drawer = self.ctx.drawer
        if drawer is None:
            return
        panel = CreationSearchPanel(self)
        drawer.set_content(panel, title="Buscar")
        drawer.open()

    def _open_filter_panel(self):
        _apptrace("WS open_filter_panel")
        drawer = self.ctx.drawer
        if drawer is None:
            return
        panel = CreationFilterPanel(self)
        drawer.set_content(panel, title="Filtros")
        drawer.open()

    def _open_suggestion_inbox(self):
        drawer = self.ctx.drawer
        controller = getattr(self.candidate_view, "cc", None)
        if controller is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir la bandeja de sugerencias")
            return
        panel = SuggestionInboxPanel(controller, on_changed=self._on_suggestion_changed, on_focus=self._focus_suggestion_entity)
        drawer.set_content(panel, title="Sugerencias")
        drawer.open()

    def _on_suggestion_changed(self):
        self.refresh()
        self._sync_suggestion_indicator()

    def _focus_suggestion_entity(self, entity_id: str):
        if hasattr(self.graph, "focus_node"):
            self.graph.focus_node(entity_id)
            self._open_node_panel(entity_id)

    def _sync_suggestion_indicator(self):
        btn = getattr(self, "_suggestion_btn", None)
        if btn is None:
            return
        controller = getattr(self.candidate_view, "cc", None)
        if controller is None:
            return
        count = len(controller.list_all())
        self._suggestion_count = count
        if count > 0:
            btn.setText(f"💡 {count}")
        else:
            btn.setText("💡")

    def _sync_filter_indicator(self):
        btn = getattr(self, "_filter_btn", None)
        if btn is None:
            return
        count = self.graph.active_filter_count()
        if count:
            btn.setText(f"◫{count}")
            btn.setToolTip(f"Filtros visuales ({count} activo(s))")
        else:
            btn.setText("◫")
            btn.setToolTip("Filtros visuales")

    def apply_creation_filter(self, filter_state: VisualFilterState):
        self.graph.apply_visual_filter(filter_state)
        self._sync_filter_indicator()

    def clear_creation_filters(self):
        self.graph.clear_visual_filters()
        self._sync_filter_indicator()

    def focus_search_result(self, result: GraphSearchResult) -> bool:
        if result.item_kind == "relation":
            return self.graph.focus_relation(result.item_id)
        if result.item_kind == "tree":
            return self.graph.focus_tree(result.item_id)
        return self.graph.focus_node(result.item_id)

    def _set_focus_breadcrumb(self, text: str, *, active: bool):
        if hasattr(self, "_focus_label"):
            self._focus_label.setText(text)
        if hasattr(self, "_global_focus_btn"):
            self._global_focus_btn.setVisible(active)

    def _entity_name(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        return str(getattr(entity, "name", entity_id)) if entity is not None else "Elemento"

    def _on_ring_selected(self, ring_id: str, display_name: str):
        _apptrace(f"WS ring_selected ring={ring_id[:40]} name={display_name[:40]}")
        self.ctx.log(
            "info",
            "B44TRACE workspace_ring_selected "
            f"ring_id={ring_id!r} display={display_name!r} "
            f"active_ring={self.graph.active_ring_id() if hasattr(self.graph, 'active_ring_id') else ''!r} "
            f"focused={self.graph.focused_ring_id() if hasattr(self.graph, 'focused_ring_id') else ''!r}",
        )
        self._set_focus_breadcrumb(f"Anillo seleccionado: {display_name}", active=True)
        ring = self.graph.ring_visual_by_id(ring_id) if hasattr(self.graph, "ring_visual_by_id") else None
        drawer = self.ctx.drawer
        if drawer is not None and ring is not None:
            panel = RingInfoPanel(
                display_name=ring.display_name,
                count_label=ring.count_label,
                causal_rank=ring.causal_rank,
                state=ring.state,
                on_enter=lambda _checked=False, rid=ring_id: self.focus_ring_scope(rid),
                on_global=lambda _checked=False: self.clear_focus_scope(),
            )
            drawer.set_content(panel, title=f"Anillo: {ring.display_name}")
            drawer.open()
        self.ctx.log("info", f"Anillo seleccionado: {display_name}")

    def _on_ring_focused(self, ring_id: str, display_name: str):
        _apptrace(f"WS ring_focused ring={ring_id[:40]} name={display_name[:40]}")
        self.ctx.log(
            "info",
            "B44TRACE workspace_ring_focused_signal "
            f"ring_id={ring_id!r} display={display_name!r} "
            f"active_ring={self.graph.active_ring_id() if hasattr(self.graph, 'active_ring_id') else ''!r} "
            f"focused={self.graph.focused_ring_id() if hasattr(self.graph, 'focused_ring_id') else ''!r}",
        )
        self._set_focus_breadcrumb(f"Global > Anillo: {display_name}", active=True)
        self._sync_filter_indicator()
        self.ctx.log("info", f"Vista enfocada de anillo activa: {display_name}")

    def focus_ring_scope(self, ring_id: str) -> bool:
        self.ctx.log("info", f"B44TRACE workspace_focus_ring_call ring_id={ring_id!r}")
        ok = self.graph.focus_ring_scope(ring_id)
        self.ctx.log(
            "info",
            "B44TRACE workspace_focus_ring_result "
            f"ok={ok} active_ring={self.graph.active_ring_id() if hasattr(self.graph, 'active_ring_id') else ''!r} "
            f"focused={self.graph.focused_ring_id() if hasattr(self.graph, 'focused_ring_id') else ''!r} "
            f"filters={self.graph.active_filter_count() if hasattr(self.graph, 'active_filter_count') else 'na'}",
        )
        if ok:
            name = str(getattr(getattr(self.graph, "canvas", None), "_ring_display_name", lambda rid: "Anillo")(ring_id))
            self._set_focus_breadcrumb(f"Global > Anillo: {name}", active=True)
            self._sync_filter_indicator()
        return ok

    def _active_creation_ring_id(self) -> str:
        ring_id = self.graph.active_ring_id() if hasattr(self.graph, "active_ring_id") else ""
        if ring_id == "__unclassified__":
            return ""
        return str(ring_id or "")

    def _with_active_ring_payload(self, data: dict) -> dict:
        _apptrace(f"WS with_active_ring_payload ring={self._active_creation_ring_id()[:40]}")
        ring_id = self._active_creation_ring_id()
        ctx = getattr(self, "ctx", None)
        if ctx is not None and hasattr(ctx, "log"):
            ctx.log(
                "info",
                "B44TRACE workspace_active_ring_payload "
                f"ring_id={ring_id!r} input_layer_ids={data.get('layer_ids', [])!r} "
                f"graph_active={self.graph.active_ring_id() if hasattr(self.graph, 'active_ring_id') else ''!r} "
                f"focused={self.graph.focused_ring_id() if hasattr(self.graph, 'focused_ring_id') else ''!r}",
            )
        if ring_id:
            merged = dict(data)
            existing = [str(value) for value in (merged.get("layer_ids") or []) if value]
            if ring_id not in existing:
                existing.insert(0, ring_id)
            merged["layer_ids"] = existing
            return merged
        return data

    def focus_tree_scope(self, tree_id: str) -> bool:
        ok = self.graph.focus_tree_scope(tree_id)
        if ok:
            self._set_focus_breadcrumb(f"Mostrando árbol: {self._entity_name(tree_id)}", active=True)
            self.ctx.log("info", "Vista enfocada de árbol activa")
        return ok

    def focus_neighborhood(self, item_id: str, *, kind: str = "entity") -> bool:
        ok = self.graph.focus_neighborhood(item_id)
        if ok:
            label = self._entity_name(item_id) if kind != "relation" else "Relación seleccionada"
            self._set_focus_breadcrumb(f"Mostrando vecindad: {label}", active=True)
            self.ctx.log("info", "Vista enfocada de vecindad activa")
        return ok

    def clear_focus_scope(self):
        self.graph.clear_focus_scope()
        self._set_focus_breadcrumb("Mostrando todo", active=False)
        self._sync_filter_indicator()
        self.ctx.log("info", "Vista global restaurada")

    def fit_all(self):
        _apptrace("WS fit_all")
        self.graph.fit_all()
        self.ctx.log("info", "Grafo encajado en pantalla")

    def reset_view(self):
        _apptrace("WS reset_view")
        self.graph.reset_view()
        self.ctx.log("info", "Vista centrada")

    def center_selection(self):
        if not self.graph.center_selection():
            self.ctx.log("info", "No hay selección que centrar")

    # ── Utility openers ────────────────────────────────────────────────────

    def _on_graph_selection_changed(self, entity_ids: list[str], relation_ids: list[str]):
        has_selection = bool(entity_ids or relation_ids)
        n_e = len(entity_ids)
        n_r = len(relation_ids)

        # Coherence button
        button = getattr(self, "_coherence_btn", None)
        if button is not None:
            button.setEnabled(has_selection)
            button.setStyleSheet(self._toolbar_btn_style if has_selection else self._toolbar_disabled_style)
            if has_selection:
                button.setToolTip(f"Analizar coherencia: {n_e} nodo(s), {n_r} relación(es)")
            else:
                button.setToolTip("Selecciona nodos o relaciones para analizar coherencia")

        # Suggest entity / relation buttons: always enabled, but update tooltip with context info
        for attr, base in [("_suggest_entity_btn", "Sugerir hoja"), ("_suggest_relation_btn", "Sugerir relación")]:
            btn = getattr(self, attr, None)
            if btn is not None and btn.isEnabled():
                if has_selection:
                    btn.setToolTip(f"{base} con IA (contexto: {n_e} nodo(s), {n_r} relación(es) seleccionado(s))")
                else:
                    btn.setToolTip(f"{base} con IA (contexto: todo el proyecto)")

        # Delete button: enabled when something is selected
        del_btn = getattr(self, "_delete_btn", None)
        if del_btn is not None:
            del_btn.setEnabled(has_selection)
            del_btn.setStyleSheet(self._toolbar_btn_style if has_selection else self._toolbar_disabled_style)
            if has_selection:
                parts = []
                if n_e:
                    parts.append(f"{n_e} nodo(s)")
                if n_r:
                    parts.append(f"{n_r} relación(es)")
                del_btn.setToolTip(f"Eliminar: {', '.join(parts)}")
            else:
                del_btn.setToolTip("Selecciona algo para eliminar")

    def _delete_selected(self):
        """Delete selected entities and/or relations."""
        entity_ids = self.graph.selected_entity_ids()
        relation_ids = self.graph.selected_relation_ids()
        if not (entity_ids or relation_ids):
            return
        deleted = 0
        errors = []
        # Delete relations first (before cascade from entity delete removes them)
        if self.relation_controller is not None:
            for rid in relation_ids:
                result = self.relation_controller.delete(rid)
                if isinstance(result, Error):
                    errors.append(result.error)
                else:
                    deleted += 1
        # Delete entities (cascades to their relations)
        if self.entity_controller is not None:
            for eid in entity_ids:
                result = self.entity_controller.delete(eid)
                if isinstance(result, Error):
                    errors.append(result.error)
                else:
                    deleted += 1
        if errors:
            self.ctx.log("error", f"Errores al eliminar: {'; '.join(errors)}")
        if deleted > 0:
            self.ctx.log("info", f"Eliminado(s): {deleted} elemento(s)")
            # Close drawer if it shows a deleted entity/relation
            if hasattr(self, "ctx") and hasattr(self.ctx, "drawer"):
                self.ctx.drawer.close()
            self.refresh()

    def _on_canvas_escape(self):
        """BETA1-B02: Escape on the canvas closes the contextual drawer.

        The canvas has already cancelled transient modes and cleared its
        selection; here we only hide the detail surface using the existing
        drawer API (same call _delete_selected already uses)."""
        drawer = getattr(self.ctx, "drawer", None)
        if drawer is not None and drawer.isVisible():
            drawer.close()

    def _open_coherence_panel(self):
        entity_ids = self.graph.selected_entity_ids()
        relation_ids = self.graph.selected_relation_ids()
        if not (entity_ids or relation_ids):
            self.ctx.log("info", "Selecciona uno o varios nodos/relaciones para analizar coherencia")
            return
        if self.ai_context_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "IA contextual no disponible para coherencia")
            return
        panel = CoherencePanel(
            self.ctx,
            self.ai_context_controller,
            self.entity_controller,
            self.relation_controller,
            entity_ids=entity_ids,
            relation_ids=relation_ids,
            on_saved=self.refresh,
        )
        self.ctx.drawer.set_content(panel, title="Coherencia")
        self.ctx.drawer.open()

    def _open_utility(self, view):
        """Open a utility view in the right drawer."""
        drawer = self.ctx.drawer
        if drawer is None or view is None:
            return
        title = getattr(view, "windowTitle", "")
        if callable(title):
            title = title()
        if not title:
            title = "Herramienta"
        drawer.set_content(view, title=title)
        drawer.open()

    # ── Suggest node / relation via AI ─────────────────────────────────

    def _suggest_node(self):
        """Ask AI to suggest missing entities. Uses graph selection as context if available."""
        if self.ai_context_controller is None:
            self.ctx.log("error", "IA no configurada. Verifica proveedor en Ajustes.")
            return
        project = self._get_active_project()
        if project is None:
            self.ctx.log("error", "No hay proyecto activo")
            return

        # Selection takes priority; fall back to all entities
        sel_e = self.graph.selected_entity_ids()
        sel_r = self.graph.selected_relation_ids()
        if sel_e:
            entity_ids = sel_e
            relation_ids = sel_r
            context_label = f"{len(sel_e)} nodo(s) seleccionado(s)"
        else:
            entity_ids = [getattr(e, "id", "") for e in getattr(project, "entities", []) or []]
            relation_ids = []
            context_label = "todo el proyecto"

        btn = getattr(self, "_suggest_entity_btn", None)
        if btn:
            btn.setEnabled(False)
            btn.setToolTip("Consultando IA...")

        self._suggest_worker = _SuggestWorker(
            self.ai_context_controller,
            action="suggest_missing_nodes",
            entity_ids=entity_ids,
            relation_ids=relation_ids,
        )
        self._suggest_worker.finished.connect(lambda: self._on_suggest_done("nodo", "_suggest_entity_btn", "_suggest_worker"))
        self._suggest_worker.start()
        self.ctx.log("info", f"Consultando IA para sugerir hojas (contexto: {context_label})...")

    def _suggest_relation(self):
        """Ask AI to suggest missing relations. Uses graph selection as context if available."""
        if self.ai_context_controller is None:
            self.ctx.log("error", "IA no configurada. Verifica proveedor en Ajustes.")
            return
        project = self._get_active_project()
        if project is None:
            self.ctx.log("error", "No hay proyecto activo")
            return

        sel_e = self.graph.selected_entity_ids()
        sel_r = self.graph.selected_relation_ids()
        if sel_e:
            entity_ids = sel_e
            relation_ids = sel_r
            context_label = f"{len(sel_e)} nodo(s) seleccionado(s)"
        else:
            entity_ids = [getattr(e, "id", "") for e in getattr(project, "entities", []) or []]
            relation_ids = []
            context_label = "todo el proyecto"

        btn = getattr(self, "_suggest_relation_btn", None)
        if btn:
            btn.setEnabled(False)
            btn.setToolTip("Consultando IA...")

        self._suggest_rel_worker = _SuggestWorker(
            self.ai_context_controller,
            action="suggest_missing_relations",
            entity_ids=entity_ids,
            relation_ids=relation_ids,
        )
        self._suggest_rel_worker.finished.connect(lambda: self._on_suggest_done("relación", "_suggest_relation_btn", "_suggest_rel_worker"))
        self._suggest_rel_worker.start()
        self.ctx.log("info", f"Consultando IA para sugerir relaciones (contexto: {context_label})...")

    def _on_suggest_done(self, kind: str, btn_attr: str, worker_attr: str):
        """Handle AI suggestion result (works for both nodes and relations)."""
        btn = getattr(self, btn_attr, None)
        if btn:
            btn.setEnabled(True)
            tooltip_base = "Sugerir hoja" if kind == "nodo" else "Sugerir relación"
            btn.setToolTip(f"{tooltip_base} con IA (selecciona nodos como contexto)")

        worker = getattr(self, worker_attr, None)
        if worker is None:
            return
        result = worker.result
        setattr(self, worker_attr, None)

        if result is None:
            self.ctx.log("error", f"La sugerencia IA de {kind} falló sin resultado")
            return
        if isinstance(result, Error):
            self.ctx.log("error", f"Error IA: {result.error}")
            return

        value = result.value
        candidate_count = len(getattr(value, "candidates", []) or [])
        preview_count = len(getattr(value, "previews", []) or [])

        if candidate_count == 0 and preview_count == 0:
            raw = getattr(value, "raw_text", "") or ""
            if raw:
                self.ctx.log("info", f"IA: {raw[:200]}")
            else:
                self.ctx.log("info", f"La IA no generó sugerencias de {kind}")
            return

        self.ctx.log("info", f"IA sugirió {candidate_count} candidato(s) de {kind}")
        self.refresh()
        self.open_candidates_clean()

    def _create_entity_on_graph(self) -> str:
        """Create a new entity, add node to graph center, open detail panel.

        Returns the new entity id ("" on failure) so callers like the
        BETA1-B01 context-menu composition can chain existing routes.
        """
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo crear hoja: servicio no disponible")
            return ""
        result = self.entity_controller.create(self._with_active_ring_payload({
            "name": "Nueva hoja",
            "entity_type": "nota",
            "brief_description": "",
            "canon_state": "borrador",
            "custom_metadata": {"_visual_draft": True},
        }))
        if isinstance(result, Error):
            self.ctx.log("error", f"Error creando hoja: {result.error}")
            return ""
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Hoja creada en modo borrador")
        self.refresh()
        # BETA1-B02: reveal without zooming — focus_entity did a fitInView
        # that yanked the camera on every contextual creation.
        self.graph.canvas.reveal_entity(entity_id)
        # Open detail panel for editing
        self._open_node_panel(entity_id, is_new=True)
        return entity_id

    def _create_entity_with_payload(self, data: dict, *, open_panel: bool = True) -> str:
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo crear hoja: servicio no disponible")
            return ""
        result = self.entity_controller.create(data)
        if isinstance(result, Error):
            self.ctx.log("error", f"Error creando hoja: {result.error}")
            return ""
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Hoja creada en modo borrador")
        self.refresh()
        self.graph.canvas.reveal_entity(entity_id)
        if open_panel:
            self._open_node_panel(entity_id, is_new=True)
        return entity_id

    def _create_tree_on_graph(self) -> str:
        """Create a new contenedor entity and open tree detail panel.

        Returns the new entity id ("" on failure); see _create_entity_on_graph.
        """
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo crear rama: servicio no disponible")
            return ""
        result = self.entity_controller.create(self._with_active_ring_payload({
            "name": "Nueva rama",
            "entity_type": "contenedor",
            "brief_description": "",
            "canon_state": "borrador",
            "custom_metadata": {"_visual_draft": True},
        }))
        if isinstance(result, Error):
            self.ctx.log("error", f"Error creando rama: {result.error}")
            return ""
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Rama creada en modo borrador")
        self.refresh()
        # BETA1-B02: reveal without zooming (see _create_entity_on_graph)
        self.graph.canvas.reveal_entity(entity_id)
        self._open_tree_panel(entity_id, is_new=True)
        return entity_id

    def _create_entity_in_tree(self, tree_id: str):
        """BETA1-B01 'Crear hoja dentro': composition of two existing routes
        (create entity + assign to tree). No new persistence logic."""
        payload = self._payload_in_tree_ring(tree_id, {
            "name": "Nueva hoja",
            "entity_type": "nota",
            "brief_description": "",
            "canon_state": "borrador",
            "custom_metadata": {"_visual_draft": True},
        })
        entity_id = self._create_entity_with_payload(payload, open_panel=False)
        if entity_id and tree_id:
            self._assign_node_to_tree(entity_id, tree_id)
            self._open_node_panel(entity_id, is_new=True)

    def _create_subtree_in_tree(self, tree_id: str):
        """BETA1-B01 'Crear subrama': create tree + assign to parent tree."""
        payload = self._payload_in_tree_ring(tree_id, {
            "name": "Nueva rama",
            "entity_type": "contenedor",
            "brief_description": "",
            "canon_state": "borrador",
            "custom_metadata": {"_visual_draft": True},
        })
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo crear rama: servicio no disponible")
            return
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self.ctx.log("error", f"Error creando rama: {result.error}")
            return
        entity_id = getattr(result.value, "id", "")
        self.ctx.log("info", "Rama creada en modo borrador")
        self.refresh()
        self.graph.canvas.reveal_entity(entity_id)
        if entity_id and tree_id:
            self._assign_node_to_tree(entity_id, tree_id)
            self._open_tree_panel(entity_id, is_new=True)

    def _assign_node_to_tree(self, entity_id: str, tree_id: str):
        """Assign entity (or container) to a container tree. Removes old 'contiene' first."""
        if self.relation_controller is None:
            self.ctx.log("error", "No se pudo asignar a la rama: servicio no disponible")
            return
        # Check for cycle
        if entity_id == tree_id:
            self.ctx.log("error", "Una rama no puede contenerse a sí misma")
            return
        # Check for nesting cycle: tree_id must not be inside entity_id
        if self._is_nested_in(tree_id, entity_id):
            self.ctx.log("error", "Anidamiento cíclico: la rama destino ya pertenece al origen")
            return
        # Remove any existing 'contiene' relation pointing to this entity
        self._remove_tree_membership(entity_id)
        # Check if already in this tree
        if self._relation_exists(tree_id, entity_id):
            self.ctx.log("info", "Esta hoja ya pertenece a la rama")
            return
        result = self.relation_controller.create(
            tree_id,
            entity_id,
            "contiene",
            "Pertenencia semántica (rama)",
        )
        if isinstance(result, Error):
            self.ctx.log("error", f"Error asignando a la rama: {result.error}")
            return
        self._sync_entity_to_tree_ring(entity_id, tree_id)
        self.ctx.log("info", "Hoja asignada a la rama")
        self.refresh()

    def _open_ring_create_panel(self):
        """BETA1-B03: 'Crear anillo…' — reuses the existing layer panel."""
        if self.layer_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo crear anillo: servicio no disponible")
            return
        panel = LayerQuickCreatePanel(self.layer_controller, on_created=self.refresh)
        self.ctx.drawer.set_content(panel, title="Nuevo anillo")
        self.ctx.drawer.open()

    def _open_ring_edit_panel(self, ring_id: str):
        """BETA1-B03: 'Editar anillo…' — name and order via LayerController."""
        if self.layer_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo editar anillo: servicio no disponible")
            return
        panel = RingEditPanel(self.layer_controller, ring_id, on_saved=self.refresh)
        self.ctx.drawer.set_content(panel, title="Editar anillo")
        self.ctx.drawer.open()

    def _delete_ring(self, ring_id: str):
        """BETA1-B03: 'Eliminar anillo' — soft delete (hide_layer) after
        confirmation. Entities keep their layer ids: they show as 'Sin
        clasificar' and the ring can be restored from the layers view."""
        if self.layer_controller is None:
            self.ctx.log("error", "No se pudo eliminar anillo: servicio no disponible")
            return
        ring = self.layer_controller.get(ring_id) if hasattr(self.layer_controller, "get") else None
        name = str(getattr(getattr(ring, "value", None), "name", ring_id))
        answer = QMessageBox.question(
            self,
            "Eliminar anillo",
            f"¿Eliminar el anillo «{name}»?\n"
            "Sus elementos pasarán a 'Sin clasificar' (el anillo puede restaurarse).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = self.layer_controller.hide(ring_id)
        if isinstance(result, Error):
            self.ctx.log("error", f"Error eliminando anillo: {result.error}")
            return
        self.ctx.log("info", f"Anillo eliminado: {name}")
        self.refresh()

    def _assign_node_to_ring(self, entity_id: str, ring_id: str):
        """BETA1-B03 'Mover a anillo': replace the entity's world-layer
        membership via the existing EntityController.update route (CRUD-U).
        Non-ring layer ids (if any) are preserved; only world-layer ids are
        swapped for the chosen ring."""
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo mover al anillo: servicio no disponible")
            return
        entity = self._entity_by_id(entity_id)
        if entity is None:
            self.ctx.log("error", "No se pudo mover al anillo: elemento no encontrado")
            return
        pc = self.ctx.project_controller
        project = pc.ps.active_project if pc else None
        world_ids = {str(getattr(layer, "id", "")) for layer in (getattr(project, "world_layers", []) or [])}
        existing = [str(value) for value in (getattr(entity, "layer_ids", []) or []) if value]
        new_layer_ids = [ring_id] + [lid for lid in existing if lid not in world_ids and lid != ring_id]
        result = self.entity_controller.update(entity_id, {"layer_ids": new_layer_ids})
        if isinstance(result, Error):
            self.ctx.log("error", f"Error moviendo al anillo: {result.error}")
            return
        for child_id in self._contained_descendant_ids(entity_id):
            child = self._entity_by_id(child_id)
            if child is None:
                continue
            child_existing = [str(value) for value in (getattr(child, "layer_ids", []) or []) if value]
            child_layer_ids = [ring_id] + [lid for lid in child_existing if lid not in world_ids and lid != ring_id]
            child_result = self.entity_controller.update(child_id, {"layer_ids": child_layer_ids})
            if isinstance(child_result, Error):
                self.ctx.log("error", f"Error moviendo contenido de rama al anillo: {child_result.error}")
                return
        self.ctx.log("info", "Elemento movido al anillo")
        self.refresh()

    def _extract_node_from_tree(self, entity_id: str):
        """BETA1-B03: dragging an item out of its container removes its
        'contiene' membership via the existing route. The item stays in the
        project (and in its ring), it just stops belonging to the branch."""
        if self.relation_controller is None:
            self.ctx.log("error", "No se pudo extraer de la rama: servicio no disponible")
            return
        self._remove_tree_membership(entity_id)
        self.ctx.log("info", "Elemento extraído de la rama")
        self.refresh()

    def _on_node_converted_to_branch(self, entity_id: str):
        """Callback after a leaf entity is converted to branch (container/rama).
        Opens the tree detail panel so the user can configure the new branch."""
        self._open_tree_panel(entity_id)

    def _open_tree_panel(self, entity_id: str, *, is_new: bool = False):
        if self.entity_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de rama")
            return
        from hosts.DesktopHostPySide.widgets.tree_detail_panel import TreeDetailPanel
        panel = TreeDetailPanel(
            self.ctx,
            self.entity_controller,
            self.relation_controller,
            entity_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
            is_new=is_new,
            on_focus_tree=self.focus_tree_scope,
        )
        self.ctx.drawer.set_content(panel, title="Rama")
        self.ctx.drawer.open()

    # ── Existing workspace methods (preserved) ─────────────────────────────

    def _open_hito_panel(self):
        """Open the causal milestone creation/review drawer (B41-T03)."""
        drawer = self.ctx.drawer
        if self._milestone_ctrl is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir hitos: servicio no disponible")
            return
        panel = CausalMilestonePanel(self._milestone_ctrl, on_created=self.refresh)
        drawer.set_content(panel, title="Hitos causales")
        drawer.open()

    def _create_hito_from_selection(self):
        """Create a hito from current graph selection (B41-T04).

        Reads the current selection from the graph canvas, builds a prefill
        dict with affected entity/relation/layer ids, and opens the
        CausalMilestonePanel pre-populated.
        """
        drawer = self.ctx.drawer
        if self._milestone_ctrl is None or drawer is None:
            self.ctx.log("error", "No se pudo crear hito desde selección: servicio no disponible")
            return

        prefill: dict = {}
        # Gather selected entities
        sel_entity_ids = getattr(self.graph, "selected_entity_ids", lambda: [])()
        if sel_entity_ids:
            prefill["affected_entity_ids"] = list(sel_entity_ids)
        # Gather selected relations
        sel_relation_ids = getattr(self.graph, "selected_relation_ids", lambda: [])()
        if sel_relation_ids:
            prefill["caused_relation_ids"] = list(sel_relation_ids)
        # Active layer if applicable
        if self._active_layer_id:
            prefill.setdefault("layer_ids", [self._active_layer_id])

        if not prefill:
            self.ctx.log("warning", "Selecciona hojas, relaciones o anillos para crear un hito explicativo")
            return

        panel = CausalMilestonePanel(
            self._milestone_ctrl,
            on_created=self.refresh,
            prefill=prefill,
        )
        drawer.set_content(panel, title="Hito desde selección")
        drawer.open()

    def refresh_ai_controller(self):
        """Rebuild contextual AI controller after provider/settings changes."""
        project_controller = getattr(self.ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is None:
            self.ai_context_controller = None
        else:
            self.ai_context_controller = AIContextController(project_service)
        if hasattr(self, "graph"):
            self.graph.set_ai_controller(self.ai_context_controller)

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        if hasattr(self.graph, "set_advanced_mode"):
            self.graph.set_advanced_mode(enabled)

    def _get_active_project(self):
        pc = getattr(self.ctx, "project_controller", None)
        if pc:
            return getattr(pc.ps, "active_project", None)
        return None

    def set_worldbuilding_active(self, active: bool):
        """Show/hide worldbuilding-related UI elements without forcing layer view."""
        active = bool(active)
        if hasattr(self, "_layers_view_btn"):
            self._layers_view_btn.setVisible(active)
        if hasattr(self, "_layers_toggle_btn"):
            self._layers_toggle_btn.setVisible(active)
            self._layers_toggle_btn.setEnabled(active)
            self._layers_toggle_btn.setToolTip(
                "Abrir/cerrar panel de anillos causales" if active else "Activa Worldbuilding para usar capas causales"
            )
        if not active and hasattr(self, "_layer_flyout"):
            self._layer_flyout.hide_flyout()
        # Worldbuilding availability does not own the Creation layout. The
        # default layout remains concentric even for projects without template
        # layers; explicit view toggles are handled by their own toolbar routes.

    def refresh(self):
        for widget in [self.graph, self.import_export_view, self.writing_view, self.timeline_view,
                       self.framework_view, self.corpus_view, self.relation_view, self.candidate_view,
                       self.source_view, self.layer_view]:
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()

    def open_graph(self):
        """Graph is always visible — this is now a no-op."""
        pass

    def open_entity_create(self):
        drawer = self.ctx.drawer
        if self.entity_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear hoja: servicio no disponible")
            return
        ring_id = self._active_creation_ring_id()
        ring = self.graph.ring_visual_by_id(ring_id) if ring_id and hasattr(self.graph, "ring_visual_by_id") else None
        panel = EntityQuickCreatePanel(
            self.entity_controller,
            on_created=self.refresh,
            layer_id=ring_id,
            layer_name=str(getattr(ring, "display_name", "") or ""),
        )
        drawer.set_content(panel, title="Nueva hoja")
        drawer.open()

    def open_candidates_clean(self):
        drawer = self.ctx.drawer
        controller = getattr(self.candidate_view, "cc", None)
        if controller is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir sugerencias: servicio no disponible")
            return
        panel = CandidateReviewPanel(controller, on_changed=self.refresh)
        drawer.set_content(panel, title="Sugerencias")
        drawer.open()

    def open_source_create(self):
        drawer = self.ctx.drawer
        if self.source_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear fuente: servicio no disponible")
            return
        panel = SourceQuickCreatePanel(self.source_controller, on_created=self.refresh)
        drawer.set_content(panel, title="Nueva fuente")
        drawer.open()

    def open_layer_create(self):
        drawer = self.ctx.drawer
        if self.layer_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear anillo: servicio no disponible")
            return
        panel = LayerQuickCreatePanel(self.layer_controller, on_created=self.refresh)
        drawer.set_content(panel, title="Nuevo anillo")
        drawer.open()

    def _open_node_panel(self, entity_id: str, *, is_new: bool = False):
        if self.entity_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de nodo")
            return
        # Route contenedor entities to tree detail panel
        entity = self._entity_by_id(entity_id)
        if entity is not None:
            etype = str(getattr(getattr(entity, "entity_type", ""), "value", getattr(entity, "entity_type", "")))
            if etype == "contenedor":
                self._open_tree_panel(entity_id)
                return
        panel = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            entity_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
            relation_controller=self.relation_controller,
            is_new=is_new,
            on_focus_neighborhood=lambda eid=entity_id: self.focus_neighborhood(eid, kind="entity"),
            on_convert_to_branch=self._on_node_converted_to_branch,
        )
        self.ctx.drawer.set_content(panel, title="Nodo")
        self.ctx.drawer.open()

    def _open_relation_panel(self, relation_id: str, *, is_new: bool = False):
        if self.relation_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de relación")
            return
        panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
            entity_controller=self.entity_controller,
            is_new=is_new,
            on_focus_neighborhood=lambda rid=relation_id: self.focus_neighborhood(rid, kind="relation"),
        )
        self.ctx.drawer.set_content(panel, title="Relación")
        self.ctx.drawer.open()

    def _entity_by_id(self, entity_id: str):
        pc = self.ctx.project_controller
        project = pc.ps.active_project if pc else None
        if project is None:
            return None
        for entity in getattr(project, "entities", []) or []:
            if getattr(entity, "id", None) == entity_id:
                return entity
        return None

    def _entity_label(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return "Elemento no encontrado"
        kind = getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "entidad"))
        return human_ref(getattr(entity, "name", "Sin nombre"), enum_human(str(kind)))

    def _world_layer_ids(self) -> set[str]:
        pc = self.ctx.project_controller
        project = pc.ps.active_project if pc else None
        return {str(getattr(layer, "id", "")) for layer in (getattr(project, "world_layers", []) or []) if getattr(layer, "id", "")}

    def _entity_ring_id(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return ""
        world_ids = self._world_layer_ids()
        for value in getattr(entity, "layer_ids", []) or []:
            layer_id = str(value)
            if layer_id and (not world_ids or layer_id in world_ids):
                return layer_id
        return ""

    def _payload_in_tree_ring(self, tree_id: str, data: dict) -> dict:
        ring_id = self._entity_ring_id(tree_id)
        if not ring_id:
            return self._with_active_ring_payload(data)
        merged = dict(data)
        existing = [str(value) for value in (merged.get("layer_ids") or []) if value]
        if ring_id not in existing:
            existing.insert(0, ring_id)
        merged["layer_ids"] = existing
        return merged

    def _sync_entity_to_tree_ring(self, entity_id: str, tree_id: str) -> None:
        if self.entity_controller is None:
            return
        ring_id = self._entity_ring_id(tree_id)
        if not ring_id:
            return
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return
        world_ids = self._world_layer_ids()
        existing = [str(value) for value in (getattr(entity, "layer_ids", []) or []) if value]
        new_layer_ids = [ring_id] + [lid for lid in existing if lid not in world_ids and lid != ring_id]
        self.entity_controller.update(entity_id, {"layer_ids": new_layer_ids})

    def _contained_descendant_ids(self, tree_id: str) -> list[str]:
        if self.relation_controller is None:
            return []
        children_by_parent: dict[str, list[str]] = {}
        for rel in self.relation_controller.list_all():
            if self._rtype_value(rel) == "contiene":
                children_by_parent.setdefault(str(getattr(rel, "source_id", "")), []).append(str(getattr(rel, "target_id", "")))
        ordered: list[str] = []
        seen: set[str] = set()

        def visit(parent_id: str):
            for child_id in children_by_parent.get(parent_id, []):
                if not child_id or child_id in seen:
                    continue
                seen.add(child_id)
                ordered.append(child_id)
                visit(child_id)

        visit(tree_id)
        return ordered

    def _relation_exists(self, source_id: str, target_id: str, *, ignore_structural: bool = False) -> bool:
        """True if a relation exists between the pair (either direction).

        BETA1-B03: with ignore_structural=True the structural 'contiene'
        relation doesn't count — a branch must be able to hold narrative
        relations with its own content and nested branches."""
        if self.relation_controller is None:
            return False
        for relation in self.relation_controller.list_all():
            if ignore_structural and self._rtype_value(relation) == "contiene":
                continue
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if (src, tgt) == (source_id, target_id) or (src, tgt) == (target_id, source_id):
                return True
        return False

    @staticmethod
    def _rtype_value(rel) -> str:
        """Extract relation_type value as lowercase string, handling enum and str."""
        rtype = getattr(rel, "relation_type", "")
        if hasattr(rtype, "value"):
            return str(rtype.value).lower()
        return str(rtype).lower()

    def _remove_tree_membership(self, entity_id: str):
        """Remove any existing 'contiene' relation where entity_id is the target."""
        if self.relation_controller is None:
            return
        to_delete = []
        for rel in self.relation_controller.list_all():
            if self._rtype_value(rel) == "contiene" and getattr(rel, "target_id", "") == entity_id:
                to_delete.append(rel.id)
        for rid in to_delete:
            self.relation_controller.delete(rid)

    def _is_nested_in(self, entity_id: str, ancestor_id: str, visited: set | None = None) -> bool:
        """Check if entity_id is transitively contained inside ancestor_id."""
        if visited is None:
            visited = set()
        if entity_id in visited:
            return False
        visited.add(entity_id)
        if self.relation_controller is None:
            return False
        for rel in self.relation_controller.list_all():
            if self._rtype_value(rel) == "contiene" and getattr(rel, "target_id", "") == entity_id:
                parent = getattr(rel, "source_id", "")
                if parent == ancestor_id:
                    return True
                if self._is_nested_in(parent, ancestor_id, visited):
                    return True
        return False

    def _on_relation_create_rejected(self, message: str):
        if message and message != "Relación cancelada":
            self.ctx.log("warning", message)

    def _open_relation_create_panel(self, source_id: str, target_id: str):
        controller = self.relation_controller
        if controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo crear relación: servicio no disponible")
            return
        if source_id == target_id:
            self.ctx.log("warning", "No se puede crear una relación sobre la misma entidad")
            return
        # BETA1-B03: 'contiene' is structural, not narrative — it must not
        # block creating a real relation between a branch and its content.
        if self._relation_exists(source_id, target_id, ignore_structural=True):
            self.ctx.log("warning", "Ya existe una relación entre esas entidades")
            return
        result = controller.create(
            source_id,
            target_id,
            "esta_relacionado_con",
            {
                "description": "",
                "custom_metadata": {
                    "_visual_draft": True,
                    "_edge_color": "#A4AEC0",
                },
            },
        )
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        relation = result.value
        relation_id = getattr(relation, "id", "")
        self.ctx.log("info", "Relación provisional creada")
        self.refresh()
        if relation_id:
            self._open_relation_panel(relation_id, is_new=True)


class GalleryWorkspace(QWidget):
    """Immersive gallery of narrative material."""

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(22, 22, 22, 22)
        self.grid.setSpacing(14)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Galería",
            "Explora tu material narrativo en tarjetas limpias, sin datos técnicos en modo normal."
        ))
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, tipo o descripción…")
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search, 2)
        self.kind_filter = QComboBox()
        self.kind_filter.addItems(["Todo", "Entidades", "Campañas", "Sesiones", "Facciones", "Secretos/Pistas"])
        self.kind_filter.currentTextChanged.connect(self.refresh)
        filters.addWidget(self.kind_filter)
        self.group_filter = QComboBox()
        self.group_filter.addItems(["Sin agrupar", "Agrupar por tipo", "Agrupar por estado"])
        self.group_filter.currentTextChanged.connect(self.refresh)
        filters.addWidget(self.group_filter)
        self.toggle_filters = QPushButton("Filtros")
        self.toggle_filters.clicked.connect(self._toggle_filters)
        filters.addWidget(self.toggle_filters)
        header_layout.addLayout(filters)
        self.filters_hint = QLabel("Secretos y pistas solo se muestran para perfil GM. IDs y JSON permanecen ocultos en modo normal.")
        self.filters_hint.setObjectName("mutedLabel")
        self.filters_hint.setWordWrap(True)
        self.filters_hint.hide()
        header_layout.addWidget(self.filters_hint)
        layout.addWidget(header)
        layout.addWidget(make_scroll_area(self.container), 1)

    def _clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _toggle_filters(self):
        self.filters_hint.setVisible(not self.filters_hint.isVisible())

    def _is_gm(self) -> bool:
        return str(getattr(self.ctx, "current_audience", "gm") or "gm").lower() == "gm"

    def _entity_relations(self, project, entity_id: str) -> str:
        names = []
        for relation in getattr(project, "relations", []) or []:
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if entity_id not in {src, tgt}:
                continue
            other_id = tgt if src == entity_id else src
            for entity in getattr(project, "entities", []) or []:
                if getattr(entity, "id", "") == other_id:
                    names.append(getattr(entity, "name", "Entidad"))
                    break
            if len(names) >= 2:
                break
        return "Relaciones: " + ", ".join(names) if names else "Sin relaciones destacadas"

    def _items(self, project) -> list[dict]:
        items: list[dict] = []
        for entity in getattr(project, "entities", []) or []:
            kind_key = str(getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "entidad")))
            visibility = str(getattr(getattr(entity, "visibility_state", None), "value", getattr(entity, "visibility_state", "")))
            if not self._is_gm() and visibility in {"secreto_mundo", "privado_gm", "oculto"}:
                continue
            canon = str(getattr(getattr(entity, "canon_state", None), "value", getattr(entity, "canon_state", "")))
            items.append({
                "id": getattr(entity, "id", ""),
                "source": entity,
                "source_type": "entity",
                "title": getattr(entity, "name", "Sin nombre"),
                "kind": enum_human(kind_key),
                "kind_key": kind_key,
                "subtitle": getattr(entity, "brief_description", "") or getattr(entity, "brief", "") or getattr(entity, "description", ""),
                "symbol": "◆",
                "badges": [(enum_human(canon or "canon"), "success"), (enum_human(visibility or "visible"), "info")],
                "relation_summary": self._entity_relations(project, getattr(entity, "id", "")),
                "group_type": enum_human(kind_key),
                "group_state": enum_human(canon or "canon"),
            })
        for campaign in getattr(project, "campaigns", []) or []:
            items.append({
                "id": getattr(campaign, "id", ""),
                "source": campaign,
                "source_type": "campaign",
                "title": getattr(campaign, "name", "Sin campaña"),
                "kind": "Campaña",
                "kind_key": "campaña",
                "subtitle": getattr(campaign, "description", "") or "Campaña narrativa",
                "symbol": "◎",
                "badges": [("Campaña", "info")],
                "relation_summary": f"Sesiones: {len(getattr(campaign, 'session_ids', []) or [])}",
                "group_type": "Campaña",
                "group_state": "Campaña",
            })
        for faction in getattr(project, "factions", []) or []:
            items.append({
                "id": getattr(faction, "id", ""),
                "source": faction,
                "source_type": "faction",
                "title": getattr(faction, "name", "Sin facción"),
                "kind": "Facción",
                "kind_key": "faccion",
                "subtitle": getattr(faction, "description", "") or "Facción del mundo",
                "symbol": "◈",
                "badges": [("Facción", "warning")],
                "relation_summary": f"Aliados/enemigos: {len(getattr(faction, 'ally_faction_ids', []) or [])}/{len(getattr(faction, 'enemy_faction_ids', []) or [])}",
                "group_type": "Facción",
                "group_state": "Facción",
            })
        for session in getattr(project, "sessions", []) or []:
            items.append({
                "id": getattr(session, "id", ""),
                "source": session,
                "source_type": "session",
                "title": getattr(session, "title", "") or getattr(session, "name", "Sesión"),
                "kind": "Sesión",
                "kind_key": "sesión",
                "subtitle": getattr(session, "context_summary", "") or getattr(session, "summary", "") or "Sesión preparada",
                "symbol": "◌",
                "badges": [("Sesión", "info")],
                "relation_summary": f"Escenas: {len(getattr(session, 'scenes', []) or [])}",
                "group_type": "Sesión",
                "group_state": "Sesión",
            })
        if self._is_gm():
            for secret in getattr(project, "secrets", []) or []:
                items.append({
                    "id": getattr(secret, "id", ""),
                    "source": secret,
                    "source_type": "secret",
                    "title": getattr(secret, "title", "") or "Secreto",
                    "kind": "Secreto",
                    "kind_key": "secreto",
                    "subtitle": getattr(secret, "content", "") or getattr(secret, "description", "") or "Secreto narrativo",
                    "symbol": "✦",
                    "badges": [("GM", "danger")],
                    "relation_summary": "Visible solo para dirección",
                    "group_type": "Secretos/Pistas",
                    "group_state": "GM",
                })
            for clue in getattr(project, "clues", []) or []:
                items.append({
                    "id": getattr(clue, "id", ""),
                    "source": clue,
                    "source_type": "clue",
                    "title": getattr(clue, "title", "") or "Pista",
                    "kind": "Pista",
                    "kind_key": "pista",
                    "subtitle": getattr(clue, "content", "") or getattr(clue, "description", "") or "Pista narrativa",
                    "symbol": "✧",
                    "badges": [("GM", "success")],
                    "relation_summary": "Revelación controlada",
                    "group_type": "Secretos/Pistas",
                    "group_state": "GM",
                })
        return items

    def _filtered_items(self, items: list[dict]) -> list[dict]:
        text = self.search.text().strip().lower()
        kind_filter = self.kind_filter.currentText()
        def matches(item: dict) -> bool:
            haystack = " ".join(str(item.get(key, "")) for key in ["title", "kind", "subtitle", "relation_summary"]).lower()
            if text and text not in haystack:
                return False
            source_type = item.get("source_type")
            if kind_filter == "Entidades" and source_type != "entity":
                return False
            if kind_filter == "Campañas" and source_type != "campaign":
                return False
            if kind_filter == "Sesiones" and source_type != "session":
                return False
            if kind_filter == "Facciones" and source_type != "faction":
                return False
            if kind_filter == "Secretos/Pistas" and source_type not in {"secret", "clue"}:
                return False
            return True
        return [item for item in items if matches(item)]

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.grid.addWidget(EmptyState("Galería", "Abre un proyecto para ver tus elementos como tarjetas."), 0, 0)
            return
        items = self._filtered_items(self._items(project))
        if not items:
            self.grid.addWidget(EmptyState("Sin elementos", "Crea contenido o ajusta búsqueda/filtros para poblar esta galería."), 0, 0)
            return
        group_mode = self.group_filter.currentText()
        row = 0
        col = 0
        current_group = None
        for item in sorted(items, key=lambda x: (x.get("group_type", ""), x.get("title", ""))):
            group = ""
            if group_mode == "Agrupar por tipo":
                group = str(item.get("group_type") or item.get("kind") or "Elementos")
            elif group_mode == "Agrupar por estado":
                group = str(item.get("group_state") or "Estado")
            if group and group != current_group:
                current_group = group
                col = 0
                if row > 0:
                    row += 1
                self.grid.addWidget(SectionHeader(group, ""), row, 0, 1, 3)
                row += 1
            card = EntityCard(item)
            card.clicked.connect(self._open_detail)
            self.grid.addWidget(card, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

    def _open_detail(self, item: dict):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de galería")
            return
        detail = QWidget()
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        layout.addWidget(SectionHeader(str(item.get("title") or "Detalle"), str(item.get("kind") or "Elemento")))
        layout.addWidget(QLabel(str(item.get("subtitle") or "Sin descripción breve")))
        layout.addWidget(QLabel(str(item.get("relation_summary") or "")))
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {item.get('id', '')}\nTipo fuente: {item.get('source_type', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(detail, title="Detalle")
        self.ctx.drawer.open()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()


class SessionWorkspace(QTabWidget):
    """Session space divided into Campaña, Preparación and En vivo/Post."""

    def __init__(self, ctx: AppContext, *, campaign_view, faction_view, session_view,
                 live_post_view, secrets_view, issues_view=None):
        super().__init__()
        self.ctx = ctx
        self.overview = SessionOverview(ctx)
        self.preparation = SessionPreparationWorkspace(ctx)
        self.campaign_view = campaign_view
        self.faction_view = faction_view
        self.session_view = session_view
        self.live_post_view = live_post_view
        self.secrets_view = secrets_view
        self.issues_view = issues_view
        self.addTab(self.overview, "Resumen")
        self.addTab(self.preparation, "Preparación")
        self.addTab(self.campaign_view, "Campaña")
        self.technical_session_index = self.addTab(self.session_view, "Preparación técnica")
        self.addTab(self.faction_view, "Facciones/Frentes")
        self.addTab(self.secrets_view, "Secretos/Pistas")
        self.addTab(self.live_post_view, "En vivo/Post")
        if self.issues_view is not None:
            self.addTab(self.issues_view, "Incidencias")
        self.set_advanced_mode(bool(ctx.advanced_mode))

    def refresh(self):
        for widget in [self.overview, self.preparation, self.campaign_view, self.session_view, self.faction_view,
                       self.secrets_view, self.live_post_view, self.issues_view]:
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()

    def set_advanced_mode(self, enabled: bool):
        if hasattr(self.overview, "set_advanced_mode"):
            self.overview.set_advanced_mode(enabled)
        if hasattr(self.preparation, "set_advanced_mode"):
            self.preparation.set_advanced_mode(enabled)
        self.setTabVisible(self.technical_session_index, bool(enabled))


class SessionPreparationWorkspace(QWidget):
    """Immersive preparation view: scenes, secrets and clues without live/post execution."""

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.selected_session_id: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Preparación",
            "Escenas, secretos y pistas de la próxima sesión. Sin modo live ni mutaciones de canon."
        ))
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Sesión:"))
        self.session_selector = QComboBox()
        self.session_selector.currentIndexChanged.connect(self._session_changed)
        controls.addWidget(self.session_selector, 1)
        self.summary_label = QLabel("Sin sesión")
        self.summary_label.setObjectName("mutedLabel")
        controls.addWidget(self.summary_label)
        header_layout.addLayout(controls)
        root.addWidget(header)

        self.container = QWidget()
        self.cards = QVBoxLayout(self.container)
        self.cards.setContentsMargins(22, 22, 22, 22)
        self.cards.setSpacing(14)
        root.addWidget(make_scroll_area(self.container), 1)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _is_gm(self) -> bool:
        return str(getattr(self.ctx, "current_audience", "gm") or "gm").lower() == "gm"

    def _clear(self):
        while self.cards.count():
            item = self.cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _session_changed(self):
        self.selected_session_id = self.session_selector.currentData()
        self.refresh()

    def _sessions(self, project):
        sessions = list(getattr(project, "sessions", []) or [])
        return sorted(sessions, key=lambda s: (getattr(s, "session_number", 0), getattr(s, "name", "")))

    def _selected_session(self, project):
        sessions = self._sessions(project)
        if not sessions:
            return None
        if self.selected_session_id:
            for session in sessions:
                if getattr(session, "id", "") == self.selected_session_id:
                    return session
        self.selected_session_id = getattr(sessions[0], "id", "")
        return sessions[0]

    def _populate_selector(self, project):
        sessions = self._sessions(project)
        current = self.selected_session_id
        self.session_selector.blockSignals(True)
        self.session_selector.clear()
        for session in sessions:
            number = getattr(session, "session_number", 0)
            label = getattr(session, "name", "Sesión")
            if number:
                label = f"#{number} · {label}"
            self.session_selector.addItem(label, getattr(session, "id", ""))
        if current:
            idx = self.session_selector.findData(current)
            if idx >= 0:
                self.session_selector.setCurrentIndex(idx)
        self.session_selector.blockSignals(False)

    def _detail(self, title: str, subtitle: str, obj, rows: list[tuple[str, str]]):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de preparación")
            return
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        layout.addWidget(SectionHeader(title, subtitle))
        for label, value in rows:
            line = QHBoxLayout()
            left = QLabel(label)
            left.setObjectName("mutedLabel")
            line.addWidget(left)
            right = QLabel(value or "—")
            right.setWordWrap(True)
            line.addWidget(right, 1)
            layout.addLayout(line)
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {getattr(obj, 'id', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(panel, title="Preparación")
        self.ctx.drawer.open()

    def _scene_card(self, scene, kind: str):
        title = getattr(scene, "name", "Escena")
        subtitle = getattr(scene, "description", "") or getattr(scene, "notes", "") or "Escena preparada"
        card = Card(title, subtitle)
        row = card.add_row()
        scene_type = enum_human(str(getattr(getattr(scene, "scene_type", None), "value", getattr(scene, "scene_type", kind))))
        row.addWidget(Badge(scene_type, "info" if kind == "prevista" else "warning"))
        row.addWidget(Badge(f"Orden {getattr(scene, 'order', 0)}", "success"))
        row.addStretch()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._detail(title, "Escena", scene, [
            ("Tipo", scene_type),
            ("Descripción", getattr(scene, "description", "") or "—"),
            ("Notas", getattr(scene, "notes", "") or "—"),
            ("NPCs", str(len(getattr(scene, "npc_ids", []) or []))),
        ]))
        row.addWidget(btn)
        return card

    def _secret_card(self, secret):
        state = enum_human(str(getattr(getattr(secret, "revelation_state", None), "value", getattr(secret, "revelation_state", "oculto"))))
        title = "Secreto" if not self._is_gm() else (getattr(secret, "content", "")[:80] or "Secreto")
        subtitle = "Oculto para jugadores" if not self._is_gm() else getattr(secret, "content", "")
        card = Card(title, subtitle)
        row = card.add_row()
        row.addWidget(Badge(state, "danger" if "oculto" in state.lower() else "success"))
        row.addWidget(Badge(f"Importancia {getattr(secret, 'importance', 3)}", "warning"))
        row.addStretch()
        if self._is_gm():
            btn = QPushButton("Detalle")
            btn.clicked.connect(lambda: self._detail("Secreto", state, secret, [
                ("Contenido", getattr(secret, "content", "") or "—"),
                ("Consecuencias", ", ".join(getattr(secret, "revelation_consequences", []) or []) or "—"),
                ("Pistas asociadas", str(len(getattr(secret, "associated_clue_ids", []) or []))),
            ]))
            row.addWidget(btn)
        return card

    def _clue_card(self, clue):
        state_raw = str(getattr(getattr(clue, "delivery_state", None), "value", getattr(clue, "delivery_state", "pendiente")))
        state = enum_human(state_raw)
        form = enum_human(str(getattr(getattr(clue, "delivery_form", None), "value", getattr(clue, "delivery_form", "pista"))))
        card = Card(form, getattr(clue, "content", "") or "Pista preparada")
        row = card.add_row()
        row.addWidget(Badge(state, "success" if state_raw == "entregada" else "warning"))
        row.addWidget(Badge(f"Claridad {getattr(clue, 'clarity', 3)}", "info"))
        row.addStretch()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._detail("Pista", state, clue, [
            ("Contenido", getattr(clue, "content", "") or "—"),
            ("Interpretación probable", getattr(clue, "probable_interpretation", "") or "—"),
            ("Riesgo de pérdida", str(getattr(clue, "loss_risk", 3))),
        ]))
        row.addWidget(btn)
        return card

    def _session_clues(self, project, session):
        ids = set(getattr(session, "available_clue_ids", []) or [])
        session_id = getattr(session, "id", "")
        clues = []
        for clue in getattr(project, "clues", []) or []:
            if getattr(clue, "id", "") in ids or session_id in (getattr(clue, "planned_session_ids", []) or []) or getattr(clue, "delivered_session_id", None) == session_id:
                clues.append(clue)
        return clues

    def _session_secrets(self, project, session):
        ids = set(getattr(session, "revealable_secret_ids", []) or [])
        session_id = getattr(session, "id", "")
        secrets = []
        for secret in getattr(project, "secrets", []) or []:
            if getattr(secret, "id", "") in ids or session_id in (getattr(secret, "planned_revelation_session_ids", []) or []) or getattr(secret, "actual_revelation_session_id", None) == session_id:
                secrets.append(secret)
        return secrets

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.session_selector.clear()
            self.summary_label.setText("Sin proyecto")
            self.cards.addWidget(EmptyState("Sin proyecto", "Abre un proyecto para preparar sesión."))
            self.cards.addStretch()
            return
        self._populate_selector(project)
        session = self._selected_session(project)
        if session is None:
            self.summary_label.setText("Sin sesiones")
            self.cards.addWidget(EmptyState("Sin sesiones", "Crea una sesión para preparar escenas, pistas y secretos."))
            self.cards.addStretch()
            return
        state = enum_human(str(getattr(getattr(session, "state", None), "value", getattr(session, "state", "preparacion"))))
        self.summary_label.setText(state)
        summary = Card(getattr(session, "name", "Sesión"), getattr(session, "context_summary", "") or getattr(session, "player_safe_summary", "") or "Preparación de sesión")
        row = summary.add_row()
        row.addWidget(Badge(state, "info"))
        row.addWidget(Badge(f"Escenas {len(getattr(session, 'planned_scenes', []) or []) + len(getattr(session, 'optional_scenes', []) or [])}", "success"))
        row.addWidget(Badge(f"Pistas {len(self._session_clues(project, session))}", "warning"))
        row.addStretch()
        self.cards.addWidget(summary)

        self.cards.addWidget(SectionHeader("Escenas preparadas", "Navegación de escenas previstas y opcionales."))
        scenes = list(getattr(session, "planned_scenes", []) or []) + list(getattr(session, "optional_scenes", []) or [])
        scenes = sorted(scenes, key=lambda s: getattr(s, "order", 0))
        if scenes:
            for scene in scenes:
                kind = str(getattr(getattr(scene, "scene_type", None), "value", getattr(scene, "scene_type", "prevista")))
                self.cards.addWidget(self._scene_card(scene, kind))
        else:
            self.cards.addWidget(EmptyState("Sin escenas", "Añade escenas previstas u opcionales en la vista técnica o servicios existentes."))

        self.cards.addWidget(SectionHeader("Pistas", "Pendientes y entregadas para esta sesión."))
        clues = self._session_clues(project, session)
        if clues:
            for clue in clues:
                self.cards.addWidget(self._clue_card(clue))
        else:
            self.cards.addWidget(EmptyState("Sin pistas", "No hay pistas planificadas para esta sesión."))

        self.cards.addWidget(SectionHeader("Secretos", "Respeta visibilidad: contenido completo solo para GM."))
        secrets = self._session_secrets(project, session)
        if secrets:
            for secret in secrets:
                self.cards.addWidget(self._secret_card(secret))
        else:
            self.cards.addWidget(EmptyState("Sin secretos", "No hay secretos revelables planificados."))

        self.cards.addWidget(SectionHeader("Checklist", "Objetivos, continuidad y preguntas abiertas."))
        checklist = []
        if self._is_gm():
            checklist.extend(getattr(session, "gm_objectives", []) or [])
            checklist.extend(getattr(session, "continuity_checklist", []) or [])
            checklist.extend(getattr(session, "open_questions", []) or [])
        else:
            checklist.extend(getattr(session, "player_known_objectives", []) or [])
        if checklist:
            for item in checklist[:12]:
                self.cards.addWidget(Card("•", str(item)))
        else:
            self.cards.addWidget(EmptyState("Sin checklist", "No hay elementos de preparación pendientes."))
        self.cards.addStretch()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()


class SessionOverview(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.selected_campaign_id: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Sesión",
            "Estado de campaña para dirigir: relojes, frentes y facciones en una sola superficie tranquila."
        ))
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Campaña:"))
        self.campaign_selector = QComboBox()
        self.campaign_selector.currentIndexChanged.connect(self._campaign_changed)
        controls.addWidget(self.campaign_selector, 1)
        self.status_label = QLabel("Sin campaña")
        self.status_label.setObjectName("mutedLabel")
        controls.addWidget(self.status_label)
        header_layout.addLayout(controls)
        root.addWidget(header)

        self.container = QWidget()
        self.layout_cards = QVBoxLayout(self.container)
        self.layout_cards.setContentsMargins(22, 22, 22, 22)
        self.layout_cards.setSpacing(14)
        root.addWidget(make_scroll_area(self.container), 1)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _clear(self):
        while self.layout_cards.count():
            item = self.layout_cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _campaign_changed(self):
        self.selected_campaign_id = self.campaign_selector.currentData()
        self.refresh()

    def _campaigns(self, project):
        return list(getattr(project, "campaigns", []) or [])

    def _selected_campaign(self, project):
        campaigns = self._campaigns(project)
        if not campaigns:
            return None
        if self.selected_campaign_id:
            for campaign in campaigns:
                if getattr(campaign, "id", "") == self.selected_campaign_id:
                    return campaign
        self.selected_campaign_id = getattr(campaigns[0], "id", "")
        return campaigns[0]

    def _populate_campaign_selector(self, project):
        campaigns = self._campaigns(project)
        current = self.selected_campaign_id
        self.campaign_selector.blockSignals(True)
        self.campaign_selector.clear()
        for campaign in campaigns:
            self.campaign_selector.addItem(getattr(campaign, "name", "Campaña"), getattr(campaign, "id", ""))
        if current:
            idx = self.campaign_selector.findData(current)
            if idx >= 0:
                self.campaign_selector.setCurrentIndex(idx)
        self.campaign_selector.blockSignals(False)

    def _clocks_for_campaign(self, project, campaign):
        ids = set(getattr(campaign, "clock_ids", []) or [])
        clocks = list(getattr(project, "campaign_clocks", []) or [])
        return [clock for clock in clocks if not ids or getattr(clock, "id", "") in ids]

    def _fronts_for_campaign(self, project, campaign):
        campaign_clock_ids = set(getattr(campaign, "clock_ids", []) or [])
        campaign_sessions = set(getattr(campaign, "session_ids", []) or [])
        fronts = []
        for front in getattr(project, "fronts", []) or []:
            if getattr(front, "clock_id", None) in campaign_clock_ids:
                fronts.append(front)
                continue
            if campaign_sessions and set(getattr(front, "session_ids", []) or []) & campaign_sessions:
                fronts.append(front)
        return fronts or list(getattr(project, "fronts", []) or [])

    def _factions_for_campaign(self, project, campaign):
        active_entities = set(getattr(campaign, "active_faction_entity_ids", []) or [])
        factions = []
        for faction in getattr(project, "factions", []) or []:
            if not active_entities or getattr(faction, "entity_id", "") in active_entities or getattr(faction, "id", "") in active_entities:
                factions.append(faction)
        return factions

    def _progress_card(self, clock):
        current = max(0, int(getattr(clock, "current_value", 0) or 0))
        max_value = max(1, int(getattr(clock, "max_value", 1) or 1))
        card = Card(getattr(clock, "name", "Clock"), getattr(clock, "description", "") or "Reloj de campaña")
        row = card.add_row()
        row.addWidget(Badge(enum_human(str(getattr(getattr(clock, "state", None), "value", getattr(clock, "state", "activo")))), "warning"))
        row.addStretch()
        bar = QProgressBar()
        bar.setRange(0, max_value)
        bar.setValue(min(current, max_value))
        bar.setFormat(f"{current}/{max_value}")
        card.layout().addWidget(bar)
        btn_row = card.add_row()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._open_detail("Clock", clock, [
            ("Estado", enum_human(str(getattr(getattr(clock, "state", None), "value", getattr(clock, "state", ""))))),
            ("Progreso", f"{current}/{max_value}"),
            ("Condiciones de avance", ", ".join(getattr(clock, "advance_conditions", []) or []) or "—"),
        ]))
        btn_row.addStretch()
        btn_row.addWidget(btn)
        return card

    def _simple_card(self, title: str, subtitle: str, badge: str, tone: str, obj, details: list[tuple[str, str]]):
        card = Card(title, subtitle or "Sin descripción")
        row = card.add_row()
        row.addWidget(Badge(badge, tone))
        row.addStretch()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._open_detail(badge, obj, details))
        row.addWidget(btn)
        return card

    def _open_detail(self, title: str, obj, details: list[tuple[str, str]]):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de sesión")
            return
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        name = getattr(obj, "name", title)
        layout.addWidget(SectionHeader(str(name), title))
        description = getattr(obj, "description", "") or getattr(obj, "relation_with_pcs", "") or "Sin descripción"
        desc = QLabel(str(description))
        desc.setWordWrap(True)
        layout.addWidget(desc)
        for label, value in details:
            row = QHBoxLayout()
            left = QLabel(label)
            left.setObjectName("mutedLabel")
            row.addWidget(left)
            value_label = QLabel(value or "—")
            value_label.setWordWrap(True)
            row.addWidget(value_label, 1)
            layout.addLayout(row)
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {getattr(obj, 'id', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(panel, title="Sesión")
        self.ctx.drawer.open()

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.campaign_selector.clear()
            self.status_label.setText("Sin proyecto")
            self.layout_cards.addWidget(EmptyState("Sin proyecto", "Abre un proyecto desde Configuración."))
            self.layout_cards.addStretch()
            return
        self._populate_campaign_selector(project)
        campaign = self._selected_campaign(project)
        if campaign is None:
            self.status_label.setText("Sin campañas")
            self.layout_cards.addWidget(EmptyState("Sin campañas", "Crea una campaña para preparar sesiones."))
            self.layout_cards.addStretch()
            return
        self.status_label.setText(enum_human(str(getattr(getattr(campaign, "state", None), "value", getattr(campaign, "state", "activa")))))
        summary = Card(getattr(campaign, "name", "Campaña"), getattr(campaign, "description", "") or "Campaña activa")
        row = summary.add_row()
        for label, value, tone in [
            ("Sistema", getattr(campaign, "game_system", "") or "—", "info"),
            ("Tono", getattr(campaign, "tone", "") or "—", "info"),
            ("Sesiones", str(len(getattr(campaign, "session_ids", []) or [])), "success"),
            ("Jugadores", str(len(getattr(campaign, "players", []) or [])), "success"),
        ]:
            row.addWidget(Badge(f"{label}: {value}", tone))
        row.addStretch()
        detail_row = summary.add_row()
        detail_btn = QPushButton("Detalle campaña")
        detail_btn.clicked.connect(lambda: self._open_detail("Campaña", campaign, [
            ("Sistema", getattr(campaign, "game_system", "") or "—"),
            ("Tono", getattr(campaign, "tone", "") or "—"),
            ("Género", getattr(campaign, "genre", "") or "—"),
        ]))
        detail_row.addStretch()
        detail_row.addWidget(detail_btn)
        self.layout_cards.addWidget(summary)

        clocks = self._clocks_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Clocks", "Progreso visual de amenazas, frentes y cuenta atrás."))
        if clocks:
            for clock in clocks:
                self.layout_cards.addWidget(self._progress_card(clock))
        else:
            self.layout_cards.addWidget(EmptyState("Sin clocks", "No hay relojes asociados a esta campaña."))

        fronts = self._fronts_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Frentes activos", "Procesos dinámicos y amenazas de la campaña."))
        if fronts:
            for front in fronts:
                stage = getattr(front, "current_stage_index", 0)
                stages = getattr(front, "stages", []) or []
                subtitle = getattr(front, "description", "") or (stages[stage].description if stages and stage < len(stages) else "Frente narrativo")
                self.layout_cards.addWidget(self._simple_card(
                    getattr(front, "name", "Frente"),
                    subtitle,
                    enum_human(str(getattr(getattr(front, "state", None), "value", getattr(front, "state", "latente")))),
                    "warning",
                    front,
                    [("Etapa", f"{stage + 1}/{len(stages) or 1}"), ("Tipo", enum_human(str(getattr(getattr(front, "front_type", None), "value", getattr(front, "front_type", "frente")))))]
                ))
        else:
            self.layout_cards.addWidget(EmptyState("Sin frentes", "No hay frentes activos para esta campaña."))

        factions = self._factions_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Facciones", "Actores activos y relaciones de presión."))
        if factions:
            for faction in factions:
                self.layout_cards.addWidget(self._simple_card(
                    getattr(faction, "name", "Facción"),
                    getattr(faction, "relation_with_pcs", "") or getattr(faction, "ideology", "") or "Facción activa",
                    enum_human(str(getattr(getattr(faction, "state", None), "value", getattr(faction, "state", "activa")))),
                    "info",
                    faction,
                    [("Aliados", str(len(getattr(faction, "ally_faction_ids", []) or []))), ("Enemigos", str(len(getattr(faction, "enemy_faction_ids", []) or []))), ("Recursos", ", ".join(getattr(faction, "resources", []) or []) or "—")]
                ))
        else:
            self.layout_cards.addWidget(EmptyState("Sin facciones", "No hay facciones activas vinculadas."))

        self.layout_cards.addWidget(SectionHeader("Siguientes zonas", "Preparación/escenas y Live/Post se completan en T10B/T10C."))
        self.layout_cards.addWidget(EmptyState("Preparación y Live/Post", "Placeholder deliberado de T10A; se implementa en los tickets siguientes."))
        self.layout_cards.addStretch()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()


class _SuggestWorker(QThread):
    """Background worker for AI suggestions (nodes or relations) — keeps UI responsive."""

    def __init__(self, ai_controller, action: str, entity_ids: list[str] | None = None, relation_ids: list[str] | None = None):
        super().__init__()
        self.ai_controller = ai_controller
        self.action = action
        self.entity_ids = entity_ids or []
        self.relation_ids = relation_ids or []
        self.result = None

    def run(self):
        try:
            self.result = self.ai_controller.graph_action(
                self.action,
                entity_ids=self.entity_ids,
                relation_ids=self.relation_ids,
            )
        except Exception as exc:
            from packages.domain.result import Error as _Err
            self.result = _Err(f"Worker exception: {exc}")
