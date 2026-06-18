"""Product workspaces for the B27.5 Desktop UX shell.

These wrappers reorganize existing connected views into three product spaces
without deleting functionality. Technical CRUD screens are kept behind advanced
mode while normal mode starts from clean cards/overviews.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, QStringListModel, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
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
from hosts.DesktopHostPySide.controllers.project_chronology_controller import ProjectChronologyController
from hosts.DesktopHostPySide.widgets.entity_card import EntityCard
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget, GraphSearchResult, VisualFilterState, relation_family
from hosts.DesktopHostPySide.widgets.milestone_chronology_view import MilestoneChronologyView
from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView
from hosts.DesktopHostPySide.controllers.era_controller import EraController
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
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK,
    INK_SOFT,
    INK_STRONG,
    INK_MUTED,
    LINE,
    SURFACE,
    SURFACE_HI,
)
from packages.domain.result import Error
from packages.domain.world_layer import default_world_layers
from packages.application.ai_jobs import (
    AIJobService,
    AIJobType,
    CommandAction,
    CommandScope,
    ACTION_LABELS,
    SCOPE_LABELS,
    valid_scopes_for_action,
    job_type_for_command,
    job_type_for_action,
)
from packages.application.command_expansion import order_context_by_causality, plan_command_jobs
from packages.infrastructure.openai_compatible_provider import get_provider
from packages.application.ai_request_gateway import ModelParams
from packages.application.context_budget import (
    DEFAULT_TIER,
    INTENT_TO_TIER,
    TIER_INPUT_TOKENS,
    TIER_OUTPUT_TOKENS,
)
from hosts.DesktopHostPySide.widgets.radial_tuner import RadialTuner
from packages.application.ai_prompt_debug import AIPromptDebugTraceStore
from packages.application.rag_service import RAGService


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


def _utility_title(view) -> str:
    try:
        raw_title = getattr(view, "windowTitle", "")
        title = raw_title() if callable(raw_title) else raw_title
    except RuntimeError:
        title = ""
    return str(title or "Herramienta")


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
        super().__init__("Nueva hoja", "Crea una pieza narrativa sin ver campos tecnicos.")
        self.controller = controller
        self.on_created = on_created
        self.layer_id = str(layer_id or "")
        self.layer_name = str(layer_name or "")
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre visible")
        self.kind = QComboBox()
        # BETA1-H04: Hoja visible = elemento individual no contenedor.
        # La UI normal solo ofrece los tipos aprobados para BETA1.
        self.kind.addItems(["personaje", "objeto", "nota"])
        self.description = QTextEdit()
        self.description.setPlaceholderText("Descripcion breve")
        self.description.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Tipo", self.kind)
        if self.layer_id:
            form.addRow("Anillo", QLabel(self.layer_name or self.layer_id))
        form.addRow("Descripcion", self.description)
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
        self.name.setPlaceholderText("Nombre del anillo")
        self.description = QTextEdit()
        self.description.setPlaceholderText("Qué representa este anillo")
        self.description.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Descripcion", self.description)
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
    """BETA1-B03: edit a ring (world layer) - name and order.

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
            self.status.setText("El nombre no puede estar vacio")
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


class _EraFormMixin:
    """BETA1-G03: campos comunes de los paneles de era."""

    def _build_era_form(self):
        form = QFormLayout()
        self.name = QLineEdit()
        self.start = QSpinBox()
        self.start.setRange(-999999999, 999999999)
        self.open_ended = QCheckBox("Era abierta (sin año final)")
        self.open_ended.setChecked(True)
        self.end = QSpinBox()
        self.end.setRange(-999999999, 999999999)
        self.end.setEnabled(False)
        self.open_ended.toggled.connect(lambda on: self.end.setEnabled(not on))
        form.addRow("Nombre", self.name)
        form.addRow("Año inicial", self.start)
        form.addRow("", self.open_ended)
        form.addRow("Año final", self.end)
        self.layout.addLayout(form)

    def _era_payload(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "start_year": int(self.start.value()),
            "end_year": None if self.open_ended.isChecked() else int(self.end.value()),
        }


class EraQuickCreatePanel(_SimpleFormPanel, _EraFormMixin):
    """BETA1-G03: crear era desde el panel de filtros (patrón Anillos)."""

    def __init__(self, controller, on_created):
        super().__init__("Nueva era", "Un estrato temporal del mundo (los años pueden ser negativos).")
        self.controller = controller
        self.on_created = on_created
        self._build_era_form()
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Crear era")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        payload = self._era_payload()
        if not payload["name"]:
            self.status.setText("El nombre no puede estar vacio")
            return
        result = self.controller.create(payload)
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.status.setText("Era creada")
        self.on_created()


class EraEditPanel(_SimpleFormPanel, _EraFormMixin):
    """BETA1-G03: editar/eliminar una era."""

    def __init__(self, controller, era_id: str, on_saved):
        super().__init__("Editar era", "Nombre y límites del estrato temporal.")
        self.controller = controller
        self.era_id = era_id
        self.on_saved = on_saved
        self._build_era_form()
        current = controller.get(era_id) if hasattr(controller, "get") else None
        era = getattr(current, "value", None)
        if era is not None:
            self.name.setText(str(getattr(era, "name", "")))
            self.start.setValue(int(getattr(era, "start_year", 0) or 0))
            end = getattr(era, "end_year", None)
            self.open_ended.setChecked(end is None)
            if end is not None:
                self.end.setValue(int(end))
        self.status = self.add_status()
        row = QHBoxLayout()
        delete = QPushButton("Eliminar era")
        delete.clicked.connect(self._delete)
        row.addWidget(delete)
        row.addStretch(1)
        save = QPushButton("Guardar era")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        payload = self._era_payload()
        if not payload["name"]:
            self.status.setText("El nombre no puede estar vacio")
            return
        result = self.controller.update(self.era_id, payload)
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.status.setText("Era actualizada")
        self.on_saved()

    def _delete(self):
        result = self.controller.delete(self.era_id)
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.status.setText("Era eliminada")
        self.on_saved()


class CandidateReviewPanel(_SimpleFormPanel):
    def __init__(self, controller, on_changed):
        super().__init__("Semillas", "Revisa propuestas como tarjetas, sin tabla técnica.")
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
    """Unified seed inbox with type, origin, summary and focus action."""

    def __init__(self, controller, on_changed, on_focus=None):
        super().__init__("Bandeja de semillas", "Propuestas generadas por coherencia, worldbuilding e importación.")
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


class AICenterPanel(_SimpleFormPanel):
    """BETA1-F03: Centro IA — jobs + sugerencias en una bandeja editorial.

    Flujo: lanzas tareas (command bar o menú contextual) → las ves resolverse
    aquí (feedback vivo, refresco suave) → las propuestas aparecen debajo y
    se pueden previsualizar, editar, aceptar o descartar. Nada canoniza sin
    confirmación. Sin tablas técnicas, sin JSON, sin IDs."""

    _STATE_LABELS = {
        "queued": "En cola",
        "running": "Trabajando…",
        "ready_for_review": "Listo para revisar",
        "applied": "Aplicado",
        "failed": "Error",
        "cancelled": "Cancelado",
    }

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__(
            "Centro IA",
            "Tareas en curso y propuestas revisables. Nada cambia el canon sin tu confirmación.",
        )
        self.workspace = workspace
        self._editing_candidate_id = ""
        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(10)
        self.layout.addWidget(make_scroll_area(body), 1)
        # Feedback vivo: refresco suave mientras el panel está visible
        self._timer = QTimer(self)
        self._timer.setInterval(900)
        self._timer.timeout.connect(self._tick)
        self.refresh()

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):  # noqa: N802 (Qt API)
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        # refresco completo solo si hay jobs activos (barato y tranquilo)
        jobs = self._jobs()
        if any(self._job_state(job) in ("queued", "running") for job in jobs):
            self.refresh()

    # ── datos ────────────────────────────────────────────────────────────

    def _jobs(self) -> list:
        try:
            return list(self.workspace.ai_job_service.list_jobs())
        except Exception:  # noqa: BLE001
            return []

    def _candidates(self) -> list:
        controller = getattr(self.workspace.candidate_view, "cc", None)
        if controller is None:
            return []
        try:
            return [
                c for c in controller.list_all()
                if str(getattr(getattr(c, "state", ""), "value", getattr(c, "state", ""))).lower()
                in ("", "pending", "proposed", "candidatestate.pending")
                or "pend" in str(getattr(c, "state", "")).lower()
            ]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _job_state(job) -> str:
        raw = str(getattr(getattr(job, "status", ""), "value", getattr(job, "status", ""))).lower()
        return raw.split(".")[-1]

    # ── render ───────────────────────────────────────────────────────────

    def refresh(self):
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        jobs = self._jobs()
        candidates = self._candidates()

        active = [j for j in jobs if self._job_state(j) in ("queued", "running")]
        finished = [j for j in jobs if self._job_state(j) not in ("queued", "running")]

        if active:
            self._section_label("En curso")
            for job in reversed(active):
                self._job_card(job, live=True)
        if finished:
            self._section_label("Tareas recientes")
            for job in list(reversed(finished))[:5]:
                self._job_card(job, live=False)
        if candidates:
            self._section_label("Propuestas para revisar")
            for candidate in candidates:
                self._candidate_card(candidate)
        if not jobs and not candidates:
            self._body_layout.addWidget(EmptyState(
                "Silencio creativo",
                "Pide algo en la barra inferior o desde el menú contextual del grafo;\n"
                "las tareas y propuestas aparecerán aquí.",
            ))
        self._body_layout.addStretch(1)

    def _section_label(self, text: str):
        label = QLabel(text)
        label.setStyleSheet(
            "color: #6F6A42; font-size: 11px; font-weight: 700; letter-spacing: 1px; "
            "text-transform: uppercase; background: transparent; border: none; padding-top: 4px;"
        )
        self._body_layout.addWidget(label)

    def _job_card(self, job, *, live: bool):
        title = str(getattr(job, "title", "") or getattr(job, "prompt", "") or "Tarea IA")
        if len(title) > 70:
            title = title[:67] + "…"
        state = self._job_state(job)
        state_label = self._STATE_LABELS.get(state, state or "—")
        card = Card(title, state_label)
        if live:
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setTextVisible(False)
            progress.setFixedHeight(6)
            progress.setValue(int(max(0.0, min(1.0, float(getattr(job, "progress", 0.0)))) * 100))
            card.layout.addWidget(progress)
        elif state == "failed":
            reason = QLabel(str(getattr(job, "error", "") or "La tarea no pudo completarse."))
            reason.setObjectName("mutedLabel")
            reason.setWordWrap(True)
            card.layout.addWidget(reason)
        elif state == "ready_for_review":
            row = QHBoxLayout()
            row.addStretch(1)
            view = QPushButton("Ver resultado")
            view.clicked.connect(lambda _=False, jid=str(getattr(job, "id", "")): self.workspace._open_ai_job_result_by_id(jid))
            row.addWidget(view)
            card.layout.addLayout(row)
        self._body_layout.addWidget(card)

    def _candidate_card(self, candidate):
        cid = str(getattr(candidate, "id", ""))
        proposed = dict(getattr(candidate, "proposed_data", {}) or {})
        title = (
            str(proposed.get("name", "")) or str(getattr(candidate, "title", ""))
            or str(getattr(candidate, "name", "")) or "Propuesta"
        )
        kind = str(getattr(getattr(candidate, "candidate_type", ""), "value", getattr(candidate, "candidate_type", ""))).replace("_", " ")
        summary = (
            str(proposed.get("brief_description", "")) or str(proposed.get("description", ""))
            or str(getattr(candidate, "summary", "")) or ""
        )
        subtitle = " · ".join(part for part in (kind, summary[:90]) if part) or "Pendiente de revisión"
        card = Card(title, subtitle)

        if self._editing_candidate_id == cid:
            # Edición inline antes de aceptar: nombre + descripción
            name_edit = QLineEdit(title)
            desc_edit = QTextEdit()
            desc_edit.setPlainText(summary)
            desc_edit.setMaximumHeight(110)
            card.layout.addWidget(name_edit)
            card.layout.addWidget(desc_edit)
            row = QHBoxLayout()
            row.addStretch(1)
            save = QPushButton("Guardar y aceptar")
            save.setObjectName("primaryButton")
            cancel = QPushButton("Cancelar")

            def _save(_=False, c=candidate, n=name_edit, d=desc_edit):
                data = dict(getattr(c, "proposed_data", {}) or {})
                if n.text().strip():
                    data["name"] = n.text().strip()
                text = d.toPlainText().strip()
                if "brief_description" in data or "name" in data:
                    data["brief_description"] = text
                else:
                    data["description"] = text
                try:
                    c.proposed_data = data
                except Exception:  # noqa: BLE001 — si el modelo es inmutable, aceptar sin editar
                    pass
                self._editing_candidate_id = ""
                self._accept(cid)

            save.clicked.connect(_save)
            cancel.clicked.connect(lambda: (setattr(self, "_editing_candidate_id", ""), self.refresh()))
            row.addWidget(cancel)
            row.addWidget(save)
            card.layout.addLayout(row)
        else:
            if summary and len(summary) > 90:
                preview = QLabel(summary[:400] + ("…" if len(summary) > 400 else ""))
                preview.setObjectName("mutedLabel")
                preview.setWordWrap(True)
                card.layout.addWidget(preview)
            row = QHBoxLayout()
            row.addStretch(1)
            edit = QPushButton("Editar")
            edit.setToolTip("Ajustar la propuesta antes de aceptarla")
            edit.clicked.connect(lambda _=False, c=cid: (setattr(self, "_editing_candidate_id", c), self.refresh()))
            accept = QPushButton("Aceptar")
            accept.setObjectName("primaryButton")
            accept.clicked.connect(lambda _=False, c=cid: self._accept(c))
            reject = QPushButton("Descartar")
            reject.clicked.connect(lambda _=False, c=cid: self._reject(c))
            row.addWidget(edit)
            row.addWidget(reject)
            row.addWidget(accept)
            card.layout.addLayout(row)
        self._body_layout.addWidget(card)

    # ── acciones ─────────────────────────────────────────────────────────

    def _accept(self, candidate_id: str):
        controller = getattr(self.workspace.candidate_view, "cc", None)
        if controller is None:
            return
        result = controller.accept(candidate_id)
        if isinstance(result, Error):
            self.workspace.ctx.log("error", f"No se pudo aceptar: {result.error}")
        else:
            self.workspace.ctx.log("info", "Propuesta aceptada")
            self.workspace.refresh()
        self.refresh()

    def _reject(self, candidate_id: str):
        controller = getattr(self.workspace.candidate_view, "cc", None)
        if controller is None:
            return
        result = controller.reject(candidate_id)
        if isinstance(result, Error):
            self.workspace.ctx.log("error", f"No se pudo descartar: {result.error}")
        else:
            self.workspace.ctx.log("info", "Propuesta descartada")
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
            ("Semillas", "Revisa propuestas como tarjetas.", "Revisar", self.workspace.open_candidates_clean),
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
        """Anillos son parte visible de BETA1 aunque el proyecto no active worldbuilding."""
        if self._layer_card_data:
            card, row, col = self._layer_card_data
            card.setVisible(True)
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
            rag_label = QLabel(self._job_rag_status(job))
            rag_label.setObjectName("mutedLabel")
            rag_label.setWordWrap(True)
            rag_label.setStyleSheet("font-size: 11px; color: #6F6A42; background: transparent; border: none;")
            card.layout.addWidget(rag_label)
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

    def _job_rag_status(self, job) -> str:
        status = str(getattr(getattr(job, "status", ""), "value", getattr(job, "status", "")))
        active = status in {"queued", "building_context", "planning", "waiting_for_model", "running", "postprocessing"}
        plan = getattr(job, "plan", {}) or {}
        context = plan.get("context", {}) if isinstance(plan, dict) else {}
        pack = context.get("rag_context_pack", {}) if isinstance(context, dict) else {}
        if not isinstance(pack, dict) or not pack:
            return "RAG: preparando contexto" if active else "RAG: sin contexto registrado"

        warnings = [str(item) for item in (pack.get("warnings") or []) if str(item)]
        items = pack.get("items") if isinstance(pack.get("items"), list) else []
        tokens = int(pack.get("tokens_estimated", 0) or 0)
        if warnings and not items:
            return f"RAG: {warnings[0]}"
        truncated = " · truncado" if pack.get("truncated") else ""
        warning_text = f" · aviso: {warnings[0]}" if warnings else ""
        return f"RAG: contexto listo ({len(items)} items, {tokens} tokens){truncated}{warning_text}"

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
        self.show_relations = QCheckBox("Mostrar relaciones")
        self.show_relations.setChecked(True)
        for combo in (self.entity_type, self.relation_type, self.relation_family, self.tree, self.layer, self.canon):
            combo.addItem("- Cualquiera -", "")
        for label, value in (("Pertenencia estructural", "estructural"), ("Narrativa", "narrativa"), ("Causal", "causal"), ("Coherencia/incidencias", "coherencia")):
            self.relation_family.addItem(label, value)
        self._populate()
        form.addRow("Tipo", self.entity_type)
        form.addRow("Tipo relación", self.relation_type)
        form.addRow("Familia relación", self.relation_family)
        form.addRow("Rama", self.tree)
        form.addRow("Anillo", self.layer)
        form.addRow("Estado", self.canon)
        form.addRow("Relaciones", self.show_relations)
        self.layout.addLayout(form)
        for widget in (self.entity_type, self.relation_type, self.relation_family, self.tree, self.layer, self.canon):
            widget.currentIndexChanged.connect(self._apply)
        self.show_relations.toggled.connect(self._apply)
        row = QHBoxLayout()
        clear = QPushButton("Limpiar filtros")
        clear.clicked.connect(self._clear)
        row.addStretch(1)
        row.addWidget(clear)
        self.layout.addLayout(row)
        # BETA1-F02/F03 (revisión): el menú de anillos vive INTEGRADO aquí —
        # lista con edición directa + creación. Más ordenado que un panel
        # técnico aparte.
        self._build_rings_section()
        # BETA1-G03: las eras y el año presente viven aquí (patrón Anillos).
        # El tiempo aplica SIEMPRE — sin gate de worldbuilding.
        self._build_eras_section()
        self.layout.addStretch(1)
        self._sync_status()

    def _build_rings_section(self):
        header = QLabel("Anillos")
        header.setStyleSheet(
            "color: #6F6A42; font-size: 11px; font-weight: 700; letter-spacing: 1px; "
            "text-transform: uppercase; background: transparent; border: none; padding-top: 8px;"
        )
        self.layout.addWidget(header)
        controller = getattr(self.workspace, "layer_controller", None)
        rings = []
        if controller is not None:
            try:
                rings = list(controller.list_all())
            except Exception:  # noqa: BLE001
                rings = []
        for ring in rings:
            row = QHBoxLayout()
            name = QLabel(str(getattr(ring, "name", "Anillo")))
            name.setStyleSheet("color: #504B2E; font-size: 12px; background: transparent; border: none;")
            row.addWidget(name, 1)
            edit = QPushButton("Editar")
            edit.setFixedHeight(24)
            edit.setToolTip("Nombre y orden del anillo")
            edit.clicked.connect(
                lambda _=False, rid=str(getattr(ring, "id", "")): self.workspace._open_ring_edit_panel(rid)
            )
            row.addWidget(edit)
            self.layout.addLayout(row)
        actions = QHBoxLayout()
        new_btn = QPushButton("Nuevo anillo")
        new_btn.clicked.connect(self.workspace._open_ring_create_panel)
        actions.addWidget(new_btn)
        flyout_btn = QPushButton("Vista de anillos")
        flyout_btn.setToolTip("Chips de anillos sobre el grafo (filtrado rápido)")
        flyout_btn.clicked.connect(self.workspace._toggle_layer_drawer)
        actions.addWidget(flyout_btn)
        actions.addStretch(1)
        self.layout.addLayout(actions)

    def _worldbuilding_active(self) -> bool:
        project = self.workspace._get_active_project()
        return bool(getattr(project, "worldbuilding_active", False)) if project is not None else False

    def _build_eras_section(self):
        """BETA1-G03: CRUD de eras + año presente del mundo."""
        controller = getattr(self.workspace, "era_controller", None)
        if controller is None:
            return
        header = QLabel("Eras")
        header.setStyleSheet(
            "color: #6F6A42; font-size: 11px; font-weight: 700; letter-spacing: 1px; "
            "text-transform: uppercase; background: transparent; border: none; padding-top: 8px;"
        )
        self.layout.addWidget(header)
        try:
            eras = list(controller.list_all() or [])
        except Exception:  # noqa: BLE001
            eras = []
        for era in eras:
            row = QHBoxLayout()
            name = QLabel(str(getattr(era, "name", "Era")))
            name.setStyleSheet("color: #504B2E; font-size: 12px; background: transparent; border: none;")
            row.addWidget(name, 1)
            end = getattr(era, "end_year", None)
            span = QLabel(f"{getattr(era, 'start_year', 0)} → {end if end is not None else '…'}")
            span.setStyleSheet("color: #7C806E; font-size: 11px; background: transparent; border: none;")
            row.addWidget(span)
            edit = QPushButton("Editar")
            edit.setFixedHeight(24)
            edit.setToolTip("Nombre y límites de la era")
            edit.clicked.connect(
                lambda _=False, eid=str(getattr(era, "id", "")): self.workspace._open_era_edit_panel(eid)
            )
            row.addWidget(edit)
            self.layout.addLayout(row)
        actions = QHBoxLayout()
        new_btn = QPushButton("Nueva era")
        new_btn.clicked.connect(self.workspace._open_era_create_panel)
        actions.addWidget(new_btn)
        actions.addStretch(1)
        self.layout.addLayout(actions)
        present_row = QHBoxLayout()
        present_label = QLabel("Año presente")
        present_label.setStyleSheet("color: #504B2E; font-size: 12px; background: transparent; border: none;")
        present_row.addWidget(present_label, 1)
        self.present_year_spin = QSpinBox()
        self.present_year_spin.setRange(-999999999, 999999999)
        try:
            self.present_year_spin.setValue(int(controller.present_year()))
        except Exception:  # noqa: BLE001
            self.present_year_spin.setValue(0)
        self.present_year_spin.editingFinished.connect(self._apply_present_year)
        present_row.addWidget(self.present_year_spin)
        self.layout.addLayout(present_row)

    def _apply_present_year(self):
        controller = getattr(self.workspace, "era_controller", None)
        if controller is None:
            return
        result = controller.set_present_year(int(self.present_year_spin.value()))
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.status.setText("Año presente actualizado")
        self.workspace.refresh()

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
            if kind.lower() == "contenedor":
                self.tree.addItem(str(getattr(entity, "name", "Rama")), str(getattr(entity, "id", "")))
        seen_rel: set[str] = set()
        for relation in relations:
            kind = str(getattr(getattr(relation, "relation_type", None), "value", getattr(relation, "relation_type", "")) or "")
            self._add_unique(self.relation_type, enum_human(kind), kind, seen_rel)
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
            layer_ids=one(self.layer),
            canon_states=one(self.canon),
            visibility_states=(),
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
        self.show_relations.setChecked(True)
        self.workspace.clear_creation_filters()
        self._sync_status()

    def _sync_status(self):
        count = self.workspace.graph.active_filter_count()
        self.status.setText(f"{count} filtro(s) activo(s)." if count else "Sin filtros activos.")



# Left-edge layer flyout

class _LayerEdgeFlyout(QFrame):
    """Persistent left drawer for anillos.

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
    All mutations go through CausalMilestoneController -> CausalMilestoneService.
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
                 import_export_view, source_view=None, layer_view=None):
        super().__init__()
        self.ctx = ctx
        self.import_export_view = import_export_view
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
        self.rag_service = getattr(self.ctx, "rag_service", None) or RAGService()
        self.ctx.rag_service = self.rag_service
        self.prompt_trace_store = getattr(self.ctx, "ai_prompt_trace_store", None) or AIPromptDebugTraceStore.default()
        self.ctx.ai_prompt_trace_store = self.prompt_trace_store
        # Resolve the configured provider (real if NARRATIVE_AI_* is set) instead
        # of the simulated default, so the command bar uses the user's provider.
        self.ai_job_service = AIJobService(
            provider=get_provider(),
            rag_service=self.rag_service,
            project_provider=self._get_active_project,
            prompt_trace_store=self.prompt_trace_store,
        )
        self._ai_workers = {}
        self._active_layer_id = ""
        self._advanced_mode = bool(ctx.advanced_mode)
        project_controller = getattr(ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is not None:
            self.ai_context_controller = AIContextController(project_service, ai_job_service=self.ai_job_service)
            self._milestone_ctrl = CausalMilestoneController(project_service)
            self._chronology_ctrl = ProjectChronologyController(project_service)
            self.era_controller = EraController(project_service)  # BETA1-G03
        else:
            self._milestone_ctrl = None
            self._chronology_ctrl = None
            self.era_controller = None

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

        # BETA1-F02 (revisión): la barra superior DESAPARECE del modo normal.
        # Se sigue construyendo (oculta, fuera del layout) porque varios
        # flujos legacy/D06 referencian sus botones; las acciones visibles
        # viven ahora en clusters flotantes junto a la command bar.
        self._top_toolbar = self._build_top_toolbar()
        self._top_toolbar.setVisible(False)

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
        # BETA1-B01: context-menu intents -> existing creation/deletion routes
        self.graph.contextCreateEntityRequested.connect(self._create_entity_on_graph)
        self.graph.contextCreateTreeRequested.connect(self._create_tree_on_graph)
        self.graph.contextCreateEntityInTreeRequested.connect(self._create_entity_in_tree)
        self.graph.contextCreateSubtreeRequested.connect(self._create_subtree_in_tree)
        self.graph.contextDeleteRequested.connect(self._delete_selected)
        self.graph.contextAIActionRequested.connect(self._run_context_ai_action)
        # BETA1-B02: Escape closes the contextual drawer after the canvas has
        # cancelled modes and cleared the selection
        self.graph.escapePressed.connect(self._on_canvas_escape)
        # BETA1-B03: 'Mover a anillo' -> EntityController.update (layer_ids)
        self.graph.nodeAssignToRingRequested.connect(self._assign_node_to_ring)
        # BETA1-B03: ring CRUD -> LayerController
        self.graph.ringCreateRequested.connect(self._open_ring_create_panel)
        self.graph.ringEditRequested.connect(self._open_ring_edit_panel)
        self.graph.ringDeleteRequested.connect(self._delete_ring)
        # BETA1-B03: drag-out extraction -> remove 'contiene' membership
        self.graph.nodeExtractFromTreeRequested.connect(self._extract_node_from_tree)
        layout.addWidget(self.graph, 1)

        # BETA1-G04: vista cronológica — el mismo árbol mirado desde el lado.
        # Complementaria a la concéntrica; SIN física (layout determinista).
        self.chrono = ChronoCanvasView()
        self.chrono.set_atmosphere_context(self.ctx)  # BETA1-G08: respeta movimiento reducido
        self.chrono.setVisible(False)
        self.chrono.entityActivated.connect(self._open_panel_for_entity)
        self.chrono.milestoneActivated.connect(self._on_chrono_milestone)
        layout.addWidget(self.chrono, 1)
        self._active_view = "concentric"

        # Command bar area replaces the old bottom button toolbar.
        self._command_bar = self._build_command_bar()
        command_bar = self._command_bar
        layout.addWidget(command_bar)

        # BETA1-F02 (revisión): clusters flotantes a ambos lados, sobre la
        # command bar. Símbolos monocromos, minimalistas, con leve vaivén.
        self._float_left = self._build_float_cluster([
            ("⌕", "Buscar y enfocar elementos", self._open_search_panel),
            ("◎", "Filtros, anillos y eras", self._open_filter_panel),
        ])
        self._float_right = self._build_float_cluster([
            ("✶", "Centro IA — tareas y propuestas", self._open_ai_center),
            ("⤓", "Guardar proyecto", self._save_project_from_canvas),
        ])
        # BETA1-G04: ◷ deja de abrir el panel de cronología — es el alternador
        # de vista (concéntrica ↔ cronológica), en posición central prominente.
        # El detalle H03 sigue accesible: doble click en un hito de la vista.
        self._float_view_toggle = self._build_view_toggle()
        # Breadcrumb flotante de foco (sustituye al de la barra retirada)
        self._float_focus = QFrame(self)
        self._float_focus.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: 1px solid {LINE}; border-radius: 12px; }}"
        )
        focus_layout = QHBoxLayout(self._float_focus)
        focus_layout.setContentsMargins(12, 4, 8, 4)
        focus_layout.setSpacing(6)
        self._float_focus_label = QLabel("")
        self._float_focus_label.setStyleSheet(f"color: {INK_SOFT}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        focus_layout.addWidget(self._float_focus_label)
        focus_exit = QPushButton("✕  Salir")
        focus_exit.setToolTip("Salir del anillo / volver a mostrar todo el grafo (Esc)")
        focus_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        focus_exit.setFixedHeight(24)
        focus_exit.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; border: none; border-radius: 12px; "
            f"color: #FCF8EC; font-size: 11px; font-weight: 700; padding: 0 12px; }} "
            f"QPushButton:hover {{ background: {GOLD_DEEP}; }}"
        )
        focus_exit.clicked.connect(self.clear_focus_scope)
        focus_layout.addWidget(focus_exit)
        self._float_focus.setVisible(False)

        # Left layer drawer is persistent: explicit button toggles it.
        self._layer_flyout = _LayerEdgeFlyout(self)
        self._layer_flyout.setVisible(False)

        self.setMouseTracking(True)
        self.graph.setMouseTracking(True)

        # BETA1-G04: restaura la vista activa (preferencia persistida)
        try:
            saved_view = str(QSettings("Dendro", "DesktopHost").value("creation/active_view", "concentric"))
        except Exception:  # noqa: BLE001
            saved_view = "concentric"
        if saved_view == "chrono":
            self.set_active_view("chrono")

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

        # BETA1-F02: crear hoja/rama/relación viven SOLO en los menús
        # contextuales del canvas (B01) — sin duplicados permanentes en barra.
        self._suggest_entity_btn = icon_btn("IA", "Sugerir hoja con IA", self._suggest_node)
        self._coherence_btn = icon_btn("!", "Selecciona nodos o relaciones para analizar coherencia", self._open_coherence_panel, enabled=False)
        icon_btn("Buscar", "Buscar y enfocar elementos", self._open_search_panel)
        self._filter_btn = icon_btn("Filtro", "Filtros visuales", self._open_filter_panel)
        self._suggestion_btn = icon_btn("Sem", "Bandeja de semillas", self._open_suggestion_inbox)
        self._jobs_btn = icon_btn("Tareas", "Tareas IA en segundo plano", self._open_ai_jobs_panel)
        self._jobs_btn.setStyleSheet(text_btn_style)
        self._jobs_btn.setFixedWidth(74)
        self._suggest_branch_btn = icon_btn("Rama IA", "Sugerir rama con IA", self._suggest_branch)
        self._suggest_branch_btn.setStyleSheet(text_btn_style)
        self._suggest_branch_btn.setFixedWidth(74)
        self._suggest_relation_btn = icon_btn("Rel IA", "Selecciona nodos para sugerir relaciones con IA", self._suggest_relation, enabled=False)
        self._suggest_relation_btn.setStyleSheet(disabled_style)
        self._suggest_relation_btn.setFixedWidth(66)
        self._summary_btn = icon_btn("Resumen", "Selecciona elementos para resumir con IA", self._summarize_selection, enabled=False)
        self._summary_btn.setStyleSheet(disabled_style)
        self._summary_btn.setFixedWidth(78)
        for ai_button in (
            self._suggest_entity_btn,
            self._coherence_btn,
            self._jobs_btn,
            self._suggest_branch_btn,
            self._suggest_relation_btn,
            self._summary_btn,
        ):
            ai_button.setVisible(False)
        self._suggestion_count = 0
        # BETA1-F02: la gestión de anillos se integra en el panel de filtros
        # (_open_filter_panel ofrece "Gestionar anillos"); sin botón fijo.
        # BETA1-F02: hitos/cronología fuera del modo normal — deuda Fase F
        # (pendiente de decisión visual). Vista y rutas intactas en código.

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

        # BETA1-F02: barra mínima. Eliminados del modo normal: importar
        # documento (→ Home/proyecto), vista por bandas (desaparece),
        # toggle concéntrica (modo asumido; B05 la activa por defecto),
        # Encajar/Centrar (navegación natural: zoom/pan + Space+drag),
        # papelera (Suprimir + menú contextual cubren el borrado).
        # BETA1-C05: la física está SIEMPRE activa — sin toggle de usuario.

        self._save_btn = QPushButton("Guardar")
        self._save_btn.setToolTip("Guardar proyecto")
        self._save_btn.setStyleSheet(text_btn_style)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._save_project_from_canvas)
        layout.addWidget(self._save_btn)

        return bar

    def _build_view_toggle(self) -> QFrame:
        """BETA1-G04: píldora central que alterna entre las dos vistas
        principales del árbol — desde arriba (anillos) y desde el lado
        (tiempo). Misma estética calmada que los clusters."""
        pill = QFrame(self)
        pill.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: 1px solid {GOLD_SOFT}; border-radius: 19px; }}"
        )
        row = QHBoxLayout(pill)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(0)
        self._view_toggle_btn = QPushButton("◷  Cronología")
        self._view_toggle_btn.setToolTip("Ver el mundo en el tiempo: eras, vidas e hitos")
        self._view_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_toggle_btn.setFixedHeight(32)
        self._view_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 16px; "
            f"color: {INK_SOFT}; font-size: 13px; font-weight: 600; padding: 0 16px; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; color: {INK_STRONG}; }} "
            f"QPushButton:pressed {{ background: {GOLD_SOFT}; }}"
        )
        self._view_toggle_btn.clicked.connect(self._toggle_chrono_view)
        row.addWidget(self._view_toggle_btn)
        pill.adjustSize()
        pill.raise_()
        return pill

    def _toggle_chrono_view(self):
        self.set_active_view("chrono" if getattr(self, "_active_view", "concentric") != "chrono" else "concentric")

    def set_active_view(self, view: str):
        """BETA1-G04: alterna concéntrica ↔ cronológica y persiste la elección."""
        view = "chrono" if str(view) == "chrono" else "concentric"
        self._active_view = view
        chrono_on = view == "chrono"
        if chrono_on:
            self.chrono.set_project(self._get_active_project())
            self.chrono.fit_all()
        self.chrono.setVisible(chrono_on)
        self.graph.setVisible(not chrono_on)
        button = getattr(self, "_view_toggle_btn", None)
        if button is not None:
            button.setText("◉  Grafo" if chrono_on else "◷  Cronología")
            button.setToolTip(
                "Volver a la vista concéntrica (el estado del mundo)"
                if chrono_on
                else "Ver el mundo en el tiempo: eras, vidas e hitos"
            )
        try:
            QSettings("Dendro", "DesktopHost").setValue("creation/active_view", view)
        except Exception:  # noqa: BLE001
            pass

    def _on_chrono_milestone(self, hito_id: str) -> None:
        """F3.6: activating a milestone in the chronology view marks it for
        context (combined with the graph selection + persisted command-bar text)
        and opens its detail. The command bar is a shared widget, so its prompt
        and the graph selection already survive the concéntrica↔cronológica
        toggle; this adds the hito side."""
        hid = str(hito_id or "")
        if hid:
            ids = getattr(self, "_chrono_context_hito_ids", None)
            if ids is None:
                ids = []
                self._chrono_context_hito_ids = ids
            if hid not in ids:
                ids.append(hid)
        self._open_milestone_chronology_view(hito_id=hid)

    def _open_panel_for_entity(self, entity_id: str):
        """BETA1-G04: doble click en una cabeza de línea de vida → su panel
        editorial (hoja u rama), coherente con la vista concéntrica."""
        project = self._get_active_project()
        for entity in getattr(project, "entities", []) or []:
            if str(getattr(entity, "id", "")) != str(entity_id):
                continue
            kind = str(getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "")) or "").lower()
            if kind == "contenedor":
                self._open_tree_panel(entity_id)
            else:
                self._open_node_panel(entity_id)
            return

    def _build_float_cluster(self, actions: list[tuple[str, str, object]]) -> QFrame:
        """BETA1-F02: cluster flotante de iconos monocromos sobre la command
        bar. Estética común: redondos, sin color, calmados."""
        cluster = QFrame(self)
        # R4: transparent holder — the buttons themselves are GOLD pills (like
        # "Crear"), so no surrounding frame to clip them.
        cluster.setStyleSheet("QFrame { background: transparent; border: none; }")
        row = QHBoxLayout(cluster)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for glyph, tip, callback in actions:
            button = QPushButton(glyph)
            button.setToolTip(tip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(40, 40)
            button.setStyleSheet(
                f"QPushButton {{ background: {GOLD}; border: none; border-radius: 20px; "
                f"color: #FCF8EC; font-size: 18px; font-weight: 700; }} "
                f"QPushButton:hover {{ background: {GOLD_DEEP}; }} "
                f"QPushButton:pressed {{ background: #5E5427; }}"
            )
            button.clicked.connect(callback)
            row.addWidget(button)
        cluster.adjustSize()
        cluster.raise_()
        return cluster

    def _position_floats(self):
        """Coloca los clusters a ambos lados de la command bar y el
        breadcrumb de foco arriba a la izquierda."""
        bar = getattr(self, "_command_bar", None)
        if bar is None:
            return
        # R6: raised and static — aligned with the chronology toggle, no sway.
        top = bar.y() - 66
        left = getattr(self, "_float_left", None)
        if left is not None:
            left.adjustSize()
            left.move(18, top)
            left.raise_()
        right = getattr(self, "_float_right", None)
        if right is not None:
            right.adjustSize()
            right.move(self.width() - right.width() - 18, top)
            right.raise_()
        # BETA1-G04: alternador de vista, centrado y prominente
        toggle = getattr(self, "_float_view_toggle", None)
        if toggle is not None:
            toggle.adjustSize()
            toggle.move((self.width() - toggle.width()) // 2, top)
            toggle.raise_()
        focus = getattr(self, "_float_focus", None)
        if focus is not None and focus.isVisible():
            focus.adjustSize()
            focus.move(18, 14)
            focus.raise_()

    def resizeEvent(self, event):  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._position_floats()

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._position_floats()

    def _toggle_float_panel(self, key: str, build_panel, title: str) -> None:
        """R5: a float button opens its drawer panel, or closes it if that same
        panel is already showing — no need for the corner ✕."""
        drawer = self.ctx.drawer
        if drawer is None:
            return
        if drawer.isVisible() and getattr(self, "_active_float_panel", None) == key:
            drawer.close()
            self._active_float_panel = None
            return
        drawer.set_content(build_panel(), title=title)
        drawer.open()
        self._active_float_panel = key

    def _open_ai_center(self):
        """BETA1-F03: acceso único a jobs + sugerencias (Centro IA)."""
        self._toggle_float_panel("ai_center", lambda: AICenterPanel(self), "Centro IA")

    def _save_project_from_canvas(self):
        """BETA1-F02: guardado discreto desde el canvas, por la misma ruta
        que el Home (ctx.request_save → MainWindow._save: gestiona recientes
        y estado). Fallback directo por controlador si no hay hook."""
        request_save = getattr(self.ctx, "request_save", None)
        if callable(request_save):
            request_save()
            return
        pc = getattr(self.ctx, "project_controller", None)
        if pc is None:
            self.ctx.log("error", "No hay proyecto que guardar")
            return
        result = pc.save()
        if hasattr(result, "error"):
            self.ctx.log("error", f"Error guardando: {result.error}")
        else:
            self.ctx.log("info", "Proyecto guardado")

    def _build_command_bar(self) -> QWidget:
        """Bottom B38 contextual AI command bar. Creates jobs, never mutates canon."""
        bar = QFrame()
        bar.setObjectName("aiCommandBar")
        bar.setStyleSheet(
            f"QFrame#aiCommandBar {{ background: {SURFACE_HI}; "
            f"border-top: 1px solid {LINE}; }}"
        )
        bar.setFixedHeight(68)
        # BETA1-G08: separación por borde + superficie sólida (sin efecto
        # gráfico, que cacheaba el render y ocultaba botones al actualizar).
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(72, 11, 72, 11)
        layout.setSpacing(10)

        prompt_label = QLabel("Dendro")
        prompt_label.setStyleSheet(
            f"color: {GOLD_DEEP}; font-size: 12px; font-weight: 700; letter-spacing: 0.4px; "
            f"background: transparent; border: none; padding-right: 4px;"
        )
        prompt_label.setToolTip("Las respuestas IA son candidatas revisables; no cambian canon automáticamente.")
        layout.addWidget(prompt_label)

        # Deterministic intent: two selectors replace the keyword classifier.
        # Selector 1 (Acción) drives Selector 2 (Ámbito).
        self._build_intent_selectors()
        layout.addWidget(self._action_selector)
        layout.addWidget(self._scope_selector)
        layout.addWidget(self._count_spin)
        layout.addWidget(self._captioned_tuner(self._temp_tuner, "Creatividad"))
        layout.addWidget(self._captioned_tuner(self._tokens_tuner, "Longitud respuesta"))
        layout.addWidget(self._captioned_tuner(self._budget_tuner, "Contexto"))

        self._command_input = QLineEdit()
        self._command_input.setObjectName("aiCommandInput")
        self._command_input.setPlaceholderText("Describe qué quieres… usa @ para referenciar una entidad o hito")
        self._command_input.setToolTip(
            "La acción y el ámbito los eliges en los dos selectores de la izquierda.\n"
            "Escribe @ para referenciar una entidad o hito existente (máx 2) — aparece un autocompletado.\n"
            "Editar usa hasta 6 elementos seleccionados; Crear relación, hasta 6 pares."
        )
        self._command_input.setStyleSheet(
            f"QLineEdit#aiCommandInput {{ background: #FFFFFF; "
            f"border: 1px solid {LINE}; border-radius: 20px; padding: 9px 16px; "
            f"font-size: 13px; color: {INK}; }} "
            f"QLineEdit#aiCommandInput:hover {{ border-color: {GOLD_SOFT}; }} "
            f"QLineEdit#aiCommandInput:focus {{ border: 2px solid {GOLD}; padding: 8px 15px; background: #FFFFFF; }}"
        )
        self._command_input.returnPressed.connect(self._submit_ai_command)
        self._setup_mention_autocomplete()
        layout.addWidget(self._command_input, 1)

        self._command_submit_btn = QPushButton("Crear")
        self._command_submit_btn.setToolTip("Crear una tarea IA revisable")
        self._command_submit_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; color: #FCF8EC; border: none; "
            f"border-radius: 18px; min-width: 64px; min-height: 36px; font-size: 12px; font-weight: 700; }} "
            f"QPushButton:hover {{ background: {GOLD_DEEP}; }} "
            f"QPushButton:pressed {{ background: #5E5427; padding-top: 2px; }}"
        )
        self._command_submit_btn.clicked.connect(self._submit_ai_command)
        layout.addWidget(self._command_submit_btn)

        self._job_status_label = QLabel("Sin tareas IA activas")
        self._job_status_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; min-width: 190px; "
            f"background: transparent; border: none;"
        )
        self._job_status_label.setToolTip("Estado de las tareas IA. Todo resultado queda pendiente de revisión.")
        layout.addWidget(self._job_status_label)
        return bar

    def _build_intent_selectors(self) -> None:
        """Build the two command-bar selectors that resolve the AIJobType.

        Selector 1 (Acción) drives Selector 2 (Ámbito): changing the action
        repopulates the valid scopes through valid_scopes_for_action, the single
        source of truth shared with the application layer.
        """
        combo_style = (
            f"QComboBox {{ background: {SURFACE}; border: 1px solid {LINE}; "
            f"border-radius: 16px; padding: 6px 12px; font-size: 12px; color: {INK}; }} "
            f"QComboBox:hover {{ border-color: {GOLD_SOFT}; }} "
            f"QComboBox:focus {{ border: 1px solid {GOLD}; }} "
            f"QComboBox::drop-down {{ border: none; width: 18px; }}"
        )
        action = QComboBox()
        action.setObjectName("aiActionSelector")
        action.setToolTip("Qué quieres que haga la IA (pasa el ratón por cada opción)")
        action.setStyleSheet(combo_style)
        action_tips = {
            CommandAction.CREAR: ("Crea elementos nuevos del ámbito elegido. Hoja/Rama: hasta 3 "
                                  "sugerencias; Relación: 1 job por par (máx 6); Anillo: plantilla "
                                  "causal (sin selección)."),
            CommandAction.EDITAR: ("Modifica descripción y cuerpo de lo seleccionado (máx 6). "
                                   "Referencia otra entidad o hito con @ (máx 2)."),
            CommandAction.ANALIZAR: ("Analiza la coherencia de la selección o de todo el proyecto. "
                                     "Si excede 6 entidades, se trocea en análisis consecutivos."),
            CommandAction.EXPLICAR: ("Razonamiento deductivo: crea hitos/entidades que expliquen la "
                                     "selección; con @ modifica el texto de las entidades referenciadas."),
            CommandAction.EXPANDIR: "Inverso de Explicar: expande el worldbuilding a partir de la selección.",
        }
        for i, act in enumerate(CommandAction):
            action.addItem(ACTION_LABELS[act], act.value)
            action.setItemData(i, action_tips.get(act, ""), Qt.ItemDataRole.ToolTipRole)

        scope = QComboBox()
        scope.setObjectName("aiScopeSelector")
        scope.setToolTip("Sobre qué actúa la IA")
        scope.setStyleSheet(combo_style)
        self._scope_tips = {
            CommandScope.HOJA: "Personajes, objetos, lugares… (nodos hoja).",
            CommandScope.RAMA: "Agrupaciones: facción, cultura, religión, institución, trama…",
            CommandScope.RELACION: "Vínculos entre entidades.",
            CommandScope.ANILLO: "Estrato causal / capa de worldbuilding.",
            CommandScope.HITO: "Acontecimiento causal en la cronología.",
        }

        # F2.5: number of suggestions (Crear Hoja/Rama, max 3). Hidden otherwise.
        count = QSpinBox()
        count.setObjectName("aiSuggestionCount")
        count.setRange(1, 3)
        count.setValue(1)
        count.setPrefix("× ")
        count.setToolTip("Número de sugerencias a generar (máx 3)")
        count.setStyleSheet(
            f"QSpinBox {{ background: {SURFACE}; border: 1px solid {LINE}; "
            f"border-radius: 16px; padding: 5px 8px; font-size: 12px; color: {INK}; max-width: 56px; }} "
            f"QSpinBox:hover {{ border-color: {GOLD_SOFT}; }}"
        )

        # PA02: tres tuners en modo AUTO por defecto. En Auto muestran el valor
        # por defecto de la tarea (hint) y NO envían override: manda el tier/intent.
        # Al arrastrar pasan a manual; doble clic vuelve a Auto. Topes = máximos de
        # tier (entrada hasta 600k, salida hasta 24k) para tareas que soportan más.
        temp_tuner = RadialTuner(minimum=0.0, maximum=1.0, value=0.7, is_integer=False, auto=True)
        temp_tuner.setToolTip(
            "CREATIVIDAD (temperatura del modelo).\n"
            "Auto = usa la recomendada para esta tarea (número mostrado).\n"
            "Arrastra ↑/↓ para forzar un valor; doble clic = volver a Auto.\n"
            "Abajo = preciso y consistente; arriba = más creativo y variado."
        )
        tokens_tuner = RadialTuner(minimum=256, maximum=24000, value=2000, is_integer=True, auto=True)
        tokens_tuner.setToolTip(
            "LONGITUD DE RESPUESTA — cuántos tokens puede generar la IA (el largo "
            "de su respuesta).\n"
            "Auto = el máximo por defecto de esta tarea (número mostrado).\n"
            "Arrastra ↑/↓ para forzar; doble clic = volver a Auto.\n"
            "Más alto = respuestas más largas; más bajo = más cortas y rápidas."
        )
        budget_tuner = RadialTuner(minimum=2000, maximum=600000, value=24000, is_integer=True, auto=True)
        budget_tuner.setToolTip(
            "CONTEXTO — presupuesto TOTAL de contexto del prompt (tokens).\n"
            "Se reserva primero lo fijo (config creativa, canon, tu petición) y el "
            "resto se reparte por secciones según la tarea; a más presupuesto, se "
            "recupera e incluye MÁS contexto del proyecto.\n"
            "Auto = el presupuesto por defecto de esta tarea (número mostrado).\n"
            "Arrastra ↑/↓ para forzar; doble clic = volver a Auto."
        )

        self._action_selector = action
        self._scope_selector = scope
        self._count_spin = count
        self._temp_tuner = temp_tuner
        self._tokens_tuner = tokens_tuner
        self._budget_tuner = budget_tuner
        action.currentIndexChanged.connect(lambda _=0: self._refresh_scope_selector())
        scope.currentIndexChanged.connect(lambda _=0: self._on_function_changed())
        self._refresh_scope_selector()

    def _on_function_changed(self) -> None:
        self._update_count_visibility()
        self._update_scope_enabled()
        self._sync_tuner_recommendations()

    def _update_scope_enabled(self) -> None:
        """R3: the Ámbito selector is moot for Analizar/Explicar/Expandir (every
        scope maps to the same job), so disable it for those actions."""
        scope = getattr(self, "_scope_selector", None)
        if scope is None:
            return
        action_value = self._action_selector.currentData()
        scope_driven = action_value in (
            CommandAction.ANALIZAR.value,
            CommandAction.EXPLICAR.value,
            CommandAction.EXPANDIR.value,
        )
        scope.setEnabled(not scope_driven)
        scope.setToolTip(
            "Esta acción no depende del ámbito (lo decide tu selección)."
            if scope_driven else "Sobre qué actúa la IA"
        )

    def _captioned_tuner(self, tuner, caption: str):
        """Envuelve un tuner con una etiqueta visible debajo (qué controla)."""
        box = QWidget(self)
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        v.addWidget(tuner, alignment=Qt.AlignmentFlag.AlignHCenter)
        label = QLabel(caption, box)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label.setStyleSheet(
            f"font-size: 9px; color: {INK_MUTED}; background: transparent; border: none;"
        )
        v.addWidget(label)
        return box

    def _sync_tuner_recommendations(self) -> None:
        """PA02: muestra el default por tarea como HINT y ajusta topes por tier.

        No fuerza valores: los tuners siguen en Auto (sin override) salvo que el
        usuario los haya tocado. Así el presupuesto real lo deciden los tiers.
        """
        if getattr(self, "_temp_tuner", None) is None:
            return
        try:
            job_type = self._selected_command_job_type()
        except ValueError:
            return
        intent = job_type.value
        params = ModelParams.from_intent(intent)
        tier = INTENT_TO_TIER.get(intent, DEFAULT_TIER)
        self._temp_tuner.set_hint(params.temperature)
        self._tokens_tuner.set_hint(TIER_OUTPUT_TOKENS[tier])
        self._budget_tuner.set_hint(TIER_INPUT_TOKENS[tier])

    def _refresh_scope_selector(self) -> None:
        """Repopulate the scope selector with the scopes valid for the action."""
        action_value = self._action_selector.currentData()
        try:
            scopes = valid_scopes_for_action(action_value)
        except ValueError:
            scopes = list(CommandScope)
        previous = self._scope_selector.currentData()
        self._scope_selector.blockSignals(True)
        self._scope_selector.clear()
        tips = getattr(self, "_scope_tips", {})
        for i, sc in enumerate(scopes):
            self._scope_selector.addItem(SCOPE_LABELS[sc], sc.value)
            self._scope_selector.setItemData(i, tips.get(sc, ""), Qt.ItemDataRole.ToolTipRole)
        if previous is not None:
            idx = self._scope_selector.findData(previous)
            if idx >= 0:
                self._scope_selector.setCurrentIndex(idx)
        self._scope_selector.blockSignals(False)
        self._on_function_changed()

    def _update_count_visibility(self) -> None:
        """Show the suggestion-count stepper only for Crear Hoja/Rama."""
        spin = getattr(self, "_count_spin", None)
        if spin is None:
            return
        action_value = self._action_selector.currentData()
        scope_value = self._scope_selector.currentData()
        visible = action_value == CommandAction.CREAR.value and scope_value in (
            CommandScope.HOJA.value,
            CommandScope.RAMA.value,
        )
        spin.setVisible(visible)

    def _known_mention_targets(self) -> list[tuple[str, str, str]]:
        """(id, name, type) of entities + milestones, for @mention resolution."""
        targets: list[tuple[str, str, str]] = []
        project = self._get_active_project()
        if project is not None:
            for e in getattr(project, "entities", []) or []:
                name = str(getattr(e, "name", "") or "").strip()
                if name:
                    targets.append((str(getattr(e, "id", "")), name, "entity"))
        ctrl = getattr(self, "_milestone_ctrl", None)
        if ctrl is not None:
            try:
                for m in ctrl.list_all():
                    title = str(getattr(m, "title", "") or "").strip()
                    if title:
                        targets.append((str(getattr(m, "id", "")), title, "milestone"))
            except Exception:
                pass
        return targets

    def _causal_context_pack(self, scope: dict) -> dict:
        """Causal-ordered context (Anillos→Ramas→Hojas) from the current selection.

        Built only when there is a selection — a whole-project pack would bloat
        the prompt. Feeds order_context_by_causality so the model reads the most
        causally-upstream context first.
        """
        project = self._get_active_project()
        if project is None:
            return {}
        selected = {str(x) for x in (scope.get("selected_entity_ids") or [])}
        if not selected:
            return {}

        def _enum_value(obj, attr):
            raw = getattr(obj, attr, "")
            return str(getattr(raw, "value", raw) or "")

        entities = []
        for e in getattr(project, "entities", []) or []:
            eid = str(getattr(e, "id", ""))
            if eid not in selected:
                continue
            entities.append({
                "id": eid,
                "name": str(getattr(e, "name", "")),
                "display_type": str(getattr(e, "display_type", "") or ""),
                "entity_type": _enum_value(e, "entity_type"),
                "layer_ids": [str(x) for x in (getattr(e, "layer_ids", []) or [])],
            })
        relations = []
        for r in getattr(project, "relations", []) or []:
            s, t = str(getattr(r, "source_id", "")), str(getattr(r, "target_id", ""))
            if s in selected and t in selected:
                relations.append({
                    "id": str(getattr(r, "id", "")), "source_id": s, "target_id": t,
                    "relation_type": _enum_value(r, "relation_type"),
                })
        ring_ids = {lid for ent in entities for lid in ent["layer_ids"]}
        rings = []
        for ring in getattr(project, "world_layers", []) or []:
            rid = str(getattr(ring, "id", ""))
            if rid in ring_ids:
                rings.append({
                    "id": rid, "name": str(getattr(ring, "name", "")),
                    "order": int(getattr(ring, "order", 0) or 0),
                })
        milestones = []
        ctrl = getattr(self, "_milestone_ctrl", None)
        if ctrl is not None:
            try:
                for m in ctrl.list_all():
                    affected = {str(x) for x in (getattr(m, "affected_entity_ids", []) or [])}
                    layers = {str(x) for x in (getattr(m, "layer_ids", []) or [])}
                    if (affected & selected) or (layers & ring_ids):
                        milestones.append({
                            "id": str(getattr(m, "id", "")), "title": str(getattr(m, "title", "")),
                            "layer_ids": list(layers), "affected_entity_ids": list(affected),
                        })
            except Exception:
                pass
        return order_context_by_causality(
            entities=entities, relations=relations, rings=rings, milestones=milestones,
        )

    def _project_service(self):
        """Resolve the active ProjectService (used to build narrative context)."""
        project_controller = getattr(self.ctx, "project_controller", None)
        return getattr(project_controller, "ps", None)

    def _load_project_budget_default(self) -> None:
        """PA02: el budget tuner arranca en Auto (presupuesto por tier de la
        tarea), así que ya no se fuerza el default del proyecto al cambiar de
        proyecto. Se conserva como hook no-op por compatibilidad de llamadas."""
        return

    def _neighborhood_pack(self, scope: dict) -> dict:
        """Vecindario por saltos desde la selección (CONO). Vacío si no hay selección."""
        project = self._get_active_project()
        if project is None:
            return {}
        selected = [str(x) for x in (scope.get("selected_entity_ids") or []) if x]
        if not selected:
            return {}
        project_service = self._project_service()
        if project_service is None:
            return {}
        from packages.application.narrative_context_builder import NarrativeContextBuilder
        builder = NarrativeContextBuilder(project_service)
        return builder.build_neighborhood_pack(selected, audience="gm", max_hops=2)

    def _enrich_mentions_in_scope(self, scope: dict, project) -> None:
        """Añade brief (mini-ficha) a cada mención resuelta, in-place."""
        mentions = scope.get("mentions")
        if not isinstance(mentions, dict) or project is None:
            return
        refs = mentions.get("refs") or []
        if not refs:
            return
        index = {}
        for e in getattr(project, "entities", []) or []:
            index[str(getattr(e, "id", ""))] = e
        milestones = {}
        ctrl = getattr(self, "_milestone_ctrl", None)
        if ctrl is not None:
            try:
                for m in ctrl.list_all():
                    milestones[str(getattr(m, "id", ""))] = m
            except Exception:
                pass
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rid = str(ref.get("ref_id") or "")
            target = index.get(rid) or milestones.get(rid)
            if target is None:
                continue
            ref["brief"] = {
                "name": str(getattr(target, "name", "") or ""),
                "type": str(getattr(getattr(target, "entity_type", ""), "value", "milestone")),
                "layer_ids": [str(x) for x in (getattr(target, "layer_ids", []) or [])],
                "brief_description": str(getattr(target, "brief_description", "") or "")[:400],
            }


    # F2.9: @mention autocomplete in the command input ---------------------

    def _setup_mention_autocomplete(self) -> None:
        """Popup completer that suggests entity/milestone names after '@'."""
        self._mention_model = QStringListModel(self)
        completer = QCompleter(self._mention_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setWidget(self._command_input)
        completer.activated[str].connect(self._insert_mention_completion)
        self._mention_completer = completer
        self._command_input.textEdited.connect(self._on_command_text_edited)

    def _current_mention_fragment(self) -> tuple[int, str] | None:
        """(@-index, text-after-@) for the mention being typed at the cursor."""
        text = self._command_input.text()
        cursor = self._command_input.cursorPosition()
        before = text[:cursor]
        at = before.rfind("@")
        if at < 0:
            return None
        fragment = before[at + 1:]
        # A mention ends at a hard delimiter; past it we are no longer in a token.
        if any(ch in fragment for ch in (",", "@", "\n", ";")):
            return None
        return at, fragment

    def _on_command_text_edited(self, _text: str) -> None:
        completer = getattr(self, "_mention_completer", None)
        if completer is None:
            return
        frag = self._current_mention_fragment()
        if frag is None:
            completer.popup().hide()
            return
        _at, fragment = frag
        names = sorted({name for _id, name, _t in self._known_mention_targets()})
        self._mention_model.setStringList(names)
        completer.setCompletionPrefix(fragment)
        if completer.completionCount() == 0:
            completer.popup().hide()
            return
        rect = self._command_input.cursorRect()
        rect.setWidth(completer.popup().sizeHintForColumn(0) + 24)
        completer.complete(rect)

    def _insert_mention_completion(self, choice: str) -> None:
        frag = self._current_mention_fragment()
        if frag is None:
            return
        at, _fragment = frag
        text = self._command_input.text()
        cursor = self._command_input.cursorPosition()
        new_text = f"{text[:at]}@{choice} {text[cursor:]}"
        self._command_input.setText(new_text)
        self._command_input.setCursorPosition(at + 1 + len(choice) + 1)

    def _selected_command_job_type(self) -> AIJobType:
        """Resolve the two selectors to a deterministic AIJobType."""
        return job_type_for_command(
            self._action_selector.currentData(),
            self._scope_selector.currentData(),
        )

    # B38 persistent layer drawer and command bar

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
        # focus_label must reflect the ACTUAL focused ring, not a stale selection
        # breadcrumb. Validate it still exists; a deleted/unfocused ring → empty,
        # so it never leaks into the payload nor the RAG query.
        focus_label = ""
        if focused_ring_id and project is not None:
            rings = getattr(project, "world_layers", []) or []
            if any(str(getattr(wl, "id", "")) == str(focused_ring_id) for wl in rings):
                canvas = getattr(self.graph, "canvas", None)
                namer = getattr(canvas, "_ring_display_name", None)
                name = namer(focused_ring_id) if callable(namer) else ""
                focus_label = f"Anillo: {name}" if name else "Anillo enfocado"
            else:
                focused_ring_id = ""  # stale focus on a ring that no longer exists
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
            # F3.6: hitos activados en la vista cronológica persisten junto a la
            # selección del grafo y el prompt (command bar compartida).
            "selected_milestone_ids": list(getattr(self, "_chrono_context_hito_ids", []) or []),
            "active_layer_ids": list(layer_ids),
            "active_ring_id": focused_ring_id,
            "focused_ring_id": focused_ring_id,
            "focus_label": focus_label,
            "visual_filters_active": self.graph.active_filter_count() if hasattr(self, "graph") else 0,
            "creative_brief": creative_brief,
            "creative_context": creative_context,
            "branch_creative_context": branch_context,
        }

    def _submit_ai_command(self):
        _apptrace(f"WS submit_ai_command prompt={self._command_input.text().strip()[:60]}")
        prompt = self._command_input.text().strip()
        if not prompt:
            self._job_status_label.setText("Escribe una orden para Dendro")
            return
        # Deterministic expansion: the two selectors + selection + params decide
        # the job(s) — no keyword classification. plan_command_jobs handles the
        # per-cell behaviour (fan-out, ring-template guard, batching, count, @).
        base_scope = self._current_context_scope()
        # PA02: solo se envía override si el tuner NO está en Auto. En Auto manda
        # el default por tarea (temperatura del intent; tokens/contexto del tier).
        if not self._temp_tuner.is_auto:
            base_scope["model_temperature"] = self._temp_tuner.value()
        if not self._tokens_tuner.is_auto:
            base_scope["model_max_tokens"] = int(self._tokens_tuner.value())
        causal = self._causal_context_pack(base_scope)
        if causal:
            base_scope["contexto_causal"] = causal
        vecindario = self._neighborhood_pack(base_scope)
        if vecindario:
            base_scope["vecindario"] = vecindario
        if getattr(self, "_budget_tuner", None) is not None and not self._budget_tuner.is_auto:
            base_scope["prompt_budget_tokens"] = int(self._budget_tuner.value())
        plan = plan_command_jobs(
            self._action_selector.currentData(),
            self._scope_selector.currentData(),
            prompt,
            selected_entity_ids=base_scope.get("selected_entity_ids") or [],
            selected_relation_ids=base_scope.get("selected_relation_ids") or [],
            known_mentions=self._known_mention_targets(),
            suggestion_count=self._count_spin.value(),
            active_ring_id=str(base_scope.get("focused_ring_id") or base_scope.get("active_ring_id") or ""),
        )
        if plan.error:
            self._job_status_label.setText(plan.error)
            self.ctx.log("error", plan.error)
            return
        for warning in plan.warnings:
            self.ctx.log("warning", warning)

        created_ids: list[str] = []
        for planned in plan.jobs:
            scope = dict(base_scope)
            scope.update(planned.context_overrides)
            self._enrich_mentions_in_scope(scope, self._get_active_project())
            result = self.ai_job_service.create_job(
                planned.job_type, planned.prompt, context_scope=scope, explicit=True
            )
            if isinstance(result, Error):
                self._job_status_label.setText(result.error)
                self.ctx.log("error", result.error)
                continue
            created_ids.append(result.value.id)
        if not created_ids:
            return

        self._command_input.clear()
        label = plan.jobs[0].job_type.value.replace("_", " ")
        n = len(created_ids)
        self._job_status_label.setText(f"{n} jobs creados: {label}" if n > 1 else f"Job creado: {label}")
        pulse_feedback(self._job_status_label)
        self._sync_jobs_indicator()
        self.ctx.log("info", f"{n} job(s) IA creado(s): resultado revisable, sin cambios automáticos en canon")
        self._open_prompt_trace_page()
        for jid in created_ids:
            self._start_ai_job_worker(jid)

    def _launch_toolbar_ai_job(self, prompt: str, status_text: str, job_type: "AIJobType | str", scope_override: dict | None = None) -> bool:
        project = self._get_active_project()
        if project is None:
            self.ctx.log("error", "No hay proyecto activo")
            return False
        scope = dict(scope_override) if scope_override is not None else self._current_context_scope()
        # Toolbar quick-actions carry an explicit intent; never classify text.
        result = self.ai_job_service.create_job(job_type, prompt, context_scope=scope, explicit=True)
        if isinstance(result, Error):
            self._job_status_label.setText(result.error)
            self.ctx.log("error", result.error)
            return False
        job = result.value
        self._job_status_label.setText(status_text)
        pulse_feedback(self._job_status_label)
        self._sync_jobs_indicator()
        self.ctx.log("info", "Job IA creado desde accion visible: resultado revisable")
        self._open_prompt_trace_page()
        self._start_ai_job_worker(job.id)
        return True

    def _start_ai_job_worker(self, job_id: str):
        worker = _AIJobWorker(self.ai_job_service, job_id)
        worker.statusChanged.connect(self._on_ai_job_status)
        worker.finishedOk.connect(self._on_ai_job_finished)
        worker.failed.connect(self._on_ai_job_failed)
        worker.finished.connect(self._on_ai_worker_stopped)
        self._ai_workers[job_id] = worker
        worker.start()

    def _open_prompt_trace_page(self):
        store = getattr(self, "prompt_trace_store", None)
        if store is None:
            return
        try:
            path = store.write_page().resolve()
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as exc:
            self.ctx.log("warning", f"No se pudo abrir visor de prompts RAG: {exc}")
            return
        if opened:
            self.ctx.log("info", f"Visor temporal de prompts RAG abierto: {path}")
        else:
            self.ctx.log("warning", f"Visor de prompts RAG escrito, pero no se pudo abrir: {path}")

    def _on_ai_job_status(self, status: str, message: str, progress: float):
        percent = int(max(0.0, min(1.0, progress)) * 100)
        self._job_status_label.setStyleSheet(
            "color: #6F6A42; font-size: 11px; min-width: 190px; "
            "background: transparent; border: none;"
        )
        self._job_status_label.setText(f"Dendro: {message} ({percent}%)")
        self._sync_jobs_indicator()
        self._refresh_ai_jobs_panel_if_open()

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
        self._refresh_ai_jobs_panel_if_open()
        self._open_ai_job_result(job)

    def _on_ai_job_failed(self, job_id: str, error: str):
        self._job_status_label.setText(f"Error: {error}")
        self._job_status_label.setStyleSheet("color: #C0392B; font-size: 11px; min-width: 190px; font-weight: 700;")
        pulse_feedback(self._job_status_label)
        self.ctx.log("error", f"Job IA fallido {job_id}: {error}")
        self._sync_jobs_indicator()
        self._refresh_ai_jobs_panel_if_open()
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
        self._ai_jobs_panel = panel
        drawer.set_content(panel, title="Tareas IA")
        drawer.open()

    def _refresh_ai_jobs_panel_if_open(self):
        panel = getattr(self, "_ai_jobs_panel", None)
        if panel is not None and hasattr(panel, "refresh"):
            try:
                panel.refresh()
            except RuntimeError:
                self._ai_jobs_panel = None

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
        self._toggle_float_panel("search", lambda: CreationSearchPanel(self), "Buscar")

    def _open_filter_panel(self):
        _apptrace("WS open_filter_panel")
        self._toggle_float_panel("filter", lambda: CreationFilterPanel(self), "Filtros")

    def _open_suggestion_inbox(self):
        drawer = self.ctx.drawer
        controller = getattr(self.candidate_view, "cc", None)
        if controller is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir la bandeja de sugerencias")
            return
        panel = SuggestionInboxPanel(controller, on_changed=self._on_suggestion_changed, on_focus=self._focus_suggestion_entity)
        drawer.set_content(panel, title="Semillas")
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
            btn.setText(f"Sugerencias {count}")
        else:
            btn.setText("Sugerencias")

    def _sync_filter_indicator(self):
        btn = getattr(self, "_filter_btn", None)
        if btn is None:
            return
        count = self.graph.active_filter_count()
        if count:
            btn.setText(f"Filtros {count}")
            btn.setToolTip(f"Filtros visuales ({count} activo(s))")
        else:
            btn.setText("Filtros")
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
        # BETA1-F02 (revisión): breadcrumb flotante — solo aparece cuando
        # hay un foco activo; en reposo, cero ruido.
        if hasattr(self, "_float_focus"):
            self._float_focus_label.setText(text)
            self._float_focus.setVisible(bool(active))
            self._position_floats()

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
        # BETA1-G-fix: el panel de anillo YA NO emerge en cada click (misma
        # filosofía que hojas/relaciones: click = seleccionar). Entrar al
        # anillo = doble click; editarlo = menú contextual / filtros.
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

    # Utility openers

    def _on_graph_selection_changed(self, entity_ids: list[str], relation_ids: list[str]):
        has_selection = bool(entity_ids or relation_ids)
        n_e = len(entity_ids)
        n_r = len(relation_ids)

        button = getattr(self, "_coherence_btn", None)
        if button is not None:
            button.setEnabled(has_selection)
            button.setStyleSheet(self._toolbar_btn_style if has_selection else self._toolbar_disabled_style)
            button.setToolTip(
                f"Analizar coherencia: {n_e} nodo(s), {n_r} relacion(es)"
                if has_selection else
                "Selecciona nodos o relaciones para analizar coherencia"
            )

        for attr, base in (
            ("_suggest_entity_btn", "Sugerir hoja"),
            ("_suggest_branch_btn", "Sugerir rama"),
        ):
            btn = getattr(self, attr, None)
            if btn is not None and btn.isEnabled():
                btn.setToolTip(
                    f"{base} con IA (contexto: {n_e} nodo(s), {n_r} relacion(es) seleccionado(s))"
                    if has_selection else
                    f"{base} con IA (contexto: todo el proyecto)"
                )
        # D04 explicit enablement for actions born disabled.
        branch_btn = getattr(self, "_suggest_branch_btn", None)
        if branch_btn is not None:
            branch_btn.setToolTip(
                f"Sugerir rama con IA (contexto: {n_e} nodo(s), {n_r} relacion(es))"
                if has_selection else
                "Sugerir rama con IA (contexto: foco/anillo actual)"
            )
        relation_btn = getattr(self, "_suggest_relation_btn", None)
        if relation_btn is not None:
            can_suggest_relation = n_e >= 2 or n_r > 0
            relation_btn.setEnabled(can_suggest_relation)
            relation_btn.setStyleSheet(self._toolbar_btn_style if can_suggest_relation else self._toolbar_disabled_style)
            relation_btn.setToolTip(
                f"Sugerir relaciones con IA (contexto: {n_e} nodo(s), {n_r} relacion(es))"
                if can_suggest_relation else
                "Selecciona al menos dos hojas o una relacion para sugerir relaciones"
            )
        summary_btn = getattr(self, "_summary_btn", None)
        if summary_btn is not None:
            summary_btn.setEnabled(has_selection)
            summary_btn.setStyleSheet(self._toolbar_btn_style if has_selection else self._toolbar_disabled_style)
            summary_btn.setToolTip(
                f"Resumir seleccion con IA ({n_e} nodo(s), {n_r} relacion(es))"
                if has_selection else
                "Selecciona elementos para resumir con IA"
            )

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

    def _run_context_ai_action(self, action: str):
        entity_ids = self.graph.selected_entity_ids()
        relation_ids = self.graph.selected_relation_ids()
        if not (entity_ids or relation_ids):
            self.ctx.log("info", "Selecciona hojas, ramas o relaciones para usar IA contextual")
            return
        selection_hint = f"{len(entity_ids)} elemento(s), {len(relation_ids)} relacion(es)"
        prompts = {
            "suggest_nodes": (
                "A partir de la seleccion actual del grafo, sugiere hojas/nodos candidatos que completen "
                "el contexto narrativo. Devuelve solo candidatos revisables; no modifiques canon."
            ),
            "suggest_branches": (
                "A partir de la seleccion actual del grafo, sugiere ramas candidatas para agrupar, explicar "
                "o expandir estos elementos. Devuelve solo candidatos revisables; no modifiques canon."
            ),
            "suggest_relations": (
                "A partir de la seleccion actual del grafo, sugiere relaciones candidatas entre hojas, ramas "
                "y relaciones relevantes. Usa endpoints reales del contexto cuando existan. No modifiques canon."
            ),
            "analyze_coherence": (
                "Analiza la coherencia narrativa de la seleccion actual del grafo. Detecta tensiones, huecos, "
                "contradicciones y oportunidades. Devuelve un informe revisable; no modifiques canon."
            ),
        }
        prompt = prompts.get(action)
        if not prompt:
            self.ctx.log("warning", f"Accion IA contextual desconocida: {action}")
            return
        self._launch_toolbar_ai_job(prompt, f"IA contextual sobre seleccion ({selection_hint})...", job_type_for_action(action))

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
            return
        # Otherwise, Escape exits a focused ring/tree/neighborhood scope.
        focused = self.graph.focused_ring_id() if hasattr(self.graph, "focused_ring_id") else ""
        breadcrumb = getattr(self, "_float_focus", None)
        if focused or (breadcrumb is not None and breadcrumb.isVisible()):
            self.clear_focus_scope()

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

    def _open_utility(self, view, title: str | None = None):
        """Open a utility view in the right drawer."""
        drawer = self.ctx.drawer
        if drawer is None or view is None:
            return
        resolved_title = title or _utility_title(view)
        drawer.set_content(view, title=resolved_title)
        drawer.open()

    # Suggest node / relation via AI

    def _suggest_branch(self):
        """Suggest 1-2 branch candidates from the current creation context."""
        prompt = (
            "Sugiere 1-2 ramas candidatas para el contexto actual de Creacion. "
            "Una rama debe ser un grupo, sistema, faccion, cultura, institucion, trama u organizacion. "
            "Devuelve solo candidatos revisables; no modifiques canon."
        )
        self._launch_toolbar_ai_job(prompt, "Sugiriendo ramas IA...", AIJobType.GENERATE_TREE)

    def _summarize_selection(self):
        """Summarize the current graph selection as a reviewable AI report."""
        entity_ids = self.graph.selected_entity_ids()
        relation_ids = self.graph.selected_relation_ids()
        if not (entity_ids or relation_ids):
            self.ctx.log("info", "Selecciona elementos para resumir con IA")
            return
        prompt = (
            "Resume la seleccion actual del grafo de forma narrativa. "
            "Incluye entidades, relaciones, huecos y preguntas abiertas. "
            "Devuelve un informe revisable, no cambios de canon."
        )
        self._launch_toolbar_ai_job(prompt, "Resumiendo seleccion IA...", AIJobType.REVIEW_GRAPH)

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

        self._suggest_entity_btn = icon_btn("IA", "Sugerir hoja con IA", self._suggest_node)
        if btn:
            btn.setEnabled(False)
            btn.setToolTip("Consultando IA...")

        self._suggest_worker = _SuggestWorker(
            self.ai_context_controller,
            action="suggest_missing_nodes",
            entity_ids=entity_ids,
            relation_ids=relation_ids,
        )
        self._suggest_entity_btn = icon_btn("IA", "Sugerir hoja con IA", self._suggest_node)
        self._suggest_worker.start()
        self.ctx.log("info", f"Consultando IA para sugerir hojas (contexto: {context_label})...")

    def _suggest_relation(self):
        """Ask AI to suggest missing relations. Uses graph selection as context if available."""
        sel_e = self.graph.selected_entity_ids()
        sel_r = self.graph.selected_relation_ids()
        if len(sel_e) < 2 and not sel_r:
            self.ctx.log("info", "Selecciona al menos dos hojas o una relacion para sugerir relaciones con IA")
            return
        prompt = (
            "Sugiere relaciones candidatas entre los elementos seleccionados. "
            "Usa endpoints reales del contexto si existen; si no, usa nombres. "
            "Devuelve solo candidatos de relacion revisables, sin modificar canon."
        )
        self._launch_toolbar_ai_job(prompt, "Sugiriendo relaciones IA...", AIJobType.SUGGEST_RELATIONS)
        return

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
        # BETA1-B02: reveal without zooming - focus_entity did a fitInView
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
        # BETA1-B02: reveal without zooming - focus_entity did a fitInView
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
        """BETA1-B03: 'Crear anillo...' - reuses the existing layer panel."""
        if self.layer_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo crear anillo: servicio no disponible")
            return
        panel = LayerQuickCreatePanel(self.layer_controller, on_created=self.refresh)
        self.ctx.drawer.set_content(panel, title="Nuevo anillo")
        self.ctx.drawer.open()

    def _open_ring_edit_panel(self, ring_id: str):
        """BETA1-B03: 'Editar anillo...' - name and order via LayerController."""
        if self.layer_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo editar anillo: servicio no disponible")
            return
        panel = RingEditPanel(self.layer_controller, ring_id, on_saved=self.refresh)
        self.ctx.drawer.set_content(panel, title="Editar anillo")
        self.ctx.drawer.open()

    def _open_era_create_panel(self):
        """BETA1-G03: 'Nueva era' desde el panel de filtros."""
        if self.era_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo crear era: servicio no disponible")
            return
        panel = EraQuickCreatePanel(self.era_controller, on_created=self.refresh)
        self.ctx.drawer.set_content(panel, title="Nueva era")
        self.ctx.drawer.open()

    def _open_era_edit_panel(self, era_id: str):
        """BETA1-G03: 'Editar era' — nombre y límites via EraController."""
        if self.era_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo editar era: servicio no disponible")
            return
        panel = EraEditPanel(self.era_controller, era_id, on_saved=self.refresh)
        self.ctx.drawer.set_content(panel, title="Editar era")
        self.ctx.drawer.open()

    def _delete_ring(self, ring_id: str):
        """BETA1-B03: 'Eliminar anillo' - soft delete (hide_layer) after
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
            f"Eliminar el anillo {name}?\n"
            "Sus elementos pasaran a 'Sin clasificar' (el anillo puede restaurarse).",
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
            milestone_controller=self._milestone_ctrl,
            on_open_milestones=self._open_milestone_chronology_view,
            on_suggest_milestone=self._suggest_related_milestone,
        )
        self.ctx.drawer.set_content(panel, title="Rama")
        self.ctx.drawer.open()

    # Existing workspace methods (preserved)

    def _open_hito_panel(self):
        """Open the causal milestone creation/review drawer (B41-T03)."""
        drawer = self.ctx.drawer
        if self._milestone_ctrl is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir hitos: servicio no disponible")
            return
        panel = CausalMilestonePanel(self._milestone_ctrl, on_created=self.refresh)
        drawer.set_content(panel, title="Hitos causales")
        drawer.open()

    def _open_milestone_chronology_view(self, target_kind: str = "", target_id: str = "", hito_id: str = ""):
        """Open the H03 milestone chronology view without touching the graph."""
        drawer = self.ctx.drawer
        if self._milestone_ctrl is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir cronologia: servicio no disponible")
            return
        target_kind = str(target_kind or "")
        target_id = str(target_id or "")
        panel = MilestoneChronologyView(
            self._milestone_ctrl,
            project_getter=self._get_active_project,
            entity_controller=self.entity_controller,
            relation_controller=self.relation_controller,
            layer_controller=self.layer_controller,
            chronology_controller=self._chronology_ctrl,
            on_saved=self.refresh,
            initial_entity_id=target_id if target_kind in {"entity", "branch"} else "",
            initial_relation_id=target_id if target_kind == "relation" else "",
            initial_hito_id=str(hito_id or ""),
        )
        drawer.set_content(panel, title="Cronologia")
        drawer.open()

    def _suggest_related_milestone(self, target_kind: str, target_id: str) -> bool:
        """Launch a reviewable AI job anchored to one existing detail-panel target."""
        target_kind = str(target_kind or "entity")
        target_id = str(target_id or "")
        if not target_id:
            self.ctx.log("warning", "Selecciona un elemento para sugerir un hito relacionado")
            return False
        scope = self._current_context_scope()
        scope["selected_entity_ids"] = []
        scope["selected_relation_ids"] = []
        scope["h05_target_kind"] = target_kind
        scope["h05_target_id"] = target_id
        if target_kind in {"entity", "branch"}:
            scope["selected_entity_ids"] = [target_id]
        elif target_kind == "relation":
            scope["selected_relation_ids"] = [target_id]
            relation = self._relation_by_id(target_id)
            endpoints = [
                str(getattr(relation, "source_id", "") or ""),
                str(getattr(relation, "target_id", "") or ""),
            ] if relation is not None else []
            scope["selected_entity_ids"] = [entity_id for entity_id in endpoints if entity_id]
        prompt = (
            "Sugiere un hito causal relacionado con la seleccion actual. "
            "Devuelve el resultado como candidato revisable, sin modificar canon. "
            "Incluye titulo, descripcion, justificacion, clave temporal narrativa y orden relativo si procede."
        )
        return self._launch_toolbar_ai_job(prompt, "Sugiriendo hito relacionado...", AIJobType.PROPOSE_MILESTONES, scope_override=scope)

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
        # Re-resolve the provider so a real provider configured at runtime takes
        # effect on the shared command-bar service (and the context actions).
        if getattr(self, "ai_job_service", None) is not None:
            self.ai_job_service.set_provider(get_provider())
        project_controller = getattr(self.ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is None:
            self.ai_context_controller = None
            self._chronology_ctrl = None
        else:
            self.ai_context_controller = AIContextController(project_service, ai_job_service=self.ai_job_service)
            self._chronology_ctrl = ProjectChronologyController(project_service)
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
        """Keep anillos controls available; worldbuilding is not a visibility gate in BETA1-H04."""
        if hasattr(self, "_layers_view_btn"):
            self._layers_view_btn.setVisible(True)
        if hasattr(self, "_layers_toggle_btn"):
            self._layers_toggle_btn.setVisible(True)
            self._layers_toggle_btn.setEnabled(True)
            self._layers_toggle_btn.setToolTip("Abrir/cerrar panel de anillos causales")
        # Worldbuilding availability does not own the Creation layout. The
        # default layout remains concentric even for projects without template
        # layers; explicit view toggles are handled by their own toolbar routes.

    def refresh(self):
        for widget in [self.graph, self.import_export_view,
                       self.corpus_view, self.relation_view, self.candidate_view,
                       self.source_view, self.layer_view]:
            try:
                if widget is not None and hasattr(widget, "refresh"):
                    widget.refresh()
            except RuntimeError:
                continue
        # BETA1-G04: la cronológica se reconstruye solo si está activa
        if getattr(self, "_active_view", "concentric") == "chrono" and hasattr(self, "chrono"):
            self.chrono.set_project(self._get_active_project())
        self._load_project_budget_default()

    def open_graph(self):
        """Graph is always visible - this is now a no-op."""
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
            milestone_controller=self._milestone_ctrl,
            is_new=is_new,
            on_focus_neighborhood=lambda eid=entity_id: self.focus_neighborhood(eid, kind="entity"),
            on_convert_to_branch=self._on_node_converted_to_branch,
            on_open_milestones=self._open_milestone_chronology_view,
            on_suggest_milestone=self._suggest_related_milestone,
        )
        self.ctx.drawer.set_content(panel, title="Nodo")
        self.ctx.drawer.open()

    def _open_relation_panel(self, relation_id: str, *, is_new: bool = False):
        if self.relation_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de relación")
            return
        # BETA1-F05: diagnóstico — si la construcción del panel falla, que
        # se vea el motivo en vez de un click que "no hace nada".
        try:
            self._open_relation_panel_impl(relation_id, is_new=is_new)
        except Exception as exc:  # noqa: BLE001
            import traceback
            _apptrace("relation_panel_error " + traceback.format_exc(limit=4))
            self.ctx.log("error", f"El panel de relación falló al construirse: {exc}")

    def _open_relation_panel_impl(self, relation_id: str, *, is_new: bool = False):
        panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
            entity_controller=self.entity_controller,
            milestone_controller=self._milestone_ctrl,
            is_new=is_new,
            on_focus_neighborhood=lambda rid=relation_id: self.focus_neighborhood(rid, kind="relation"),
            on_open_milestones=self._open_milestone_chronology_view,
            on_suggest_milestone=self._suggest_related_milestone,
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

    def _relation_by_id(self, relation_id: str):
        pc = self.ctx.project_controller
        project = pc.ps.active_project if pc else None
        if project is None:
            return None
        for relation in getattr(project, "relations", []) or []:
            if getattr(relation, "id", None) == relation_id:
                return relation
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
        relation does not count - a branch must be able to hold narrative
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
        # BETA1-B03: 'contiene' is structural, not narrative - it must not
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


class _SuggestWorker(QThread):
    """Background worker for AI suggestions (nodes or relations) - keeps UI responsive."""

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
