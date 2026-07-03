"""Product workspaces for the B27.5 Desktop UX shell.

These wrappers reorganize existing connected views into three product spaces
without deleting functionality. Technical CRUD screens are kept behind advanced
mode while normal mode starts from clean cards/overviews.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, QStringListModel, Qt, QThread, QTimer, QUrl, Signal
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
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.controllers.ai_context_controller import AIContextController
from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
    CausalMilestoneController,
)
from hosts.DesktopHostPySide.controllers.chronology_walk_controller import ChronologyWalkController
from hosts.DesktopHostPySide.controllers.project_chronology_controller import (
    ProjectChronologyController,
)
from hosts.DesktopHostPySide.widgets.graph_canvas import (
    GraphCanvasWidget,
    GraphSearchResult,
    VisualFilterState,
    relation_family,
)
from hosts.DesktopHostPySide.controllers.ghost_controller import GhostController
from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView
from hosts.DesktopHostPySide.widgets.foco.watering_authorize import (
    request_watering_authorization,
)
from hosts.DesktopHostPySide.widgets.foco.watering_batch import WateringBatchWorker
from hosts.DesktopHostPySide.widgets.foco.watering_panel import WateringPanel
from packages.application.history_service import HistoryService
from packages.application.watering_service import WateringService
from hosts.DesktopHostPySide.widgets.milestone_chronology_view import MilestoneChronologyView
from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    ChronoCanvasView,
    MilestoneQuickCreatePanel,
)
from hosts.DesktopHostPySide.controllers.era_controller import EraController
from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
from hosts.DesktopHostPySide.widgets.coherence_panel import CoherencePanel
from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    BusyIndicator,
    Card,
    EmptyState,
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
    INK_OLIVE,
    INPUT_BG,
    LINE,
    LINE_STRONG,
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
from packages.application.command_expansion import (
    example_for_command,
    order_context_by_causality,
    plan_command_jobs,
)
from packages.infrastructure.openai_compatible_provider import get_provider
from packages.application.ai_request_gateway import ModelParams
from packages.application.context_budget import (
    DEFAULT_TIER,
    INTENT_TO_TIER,
    TIER_INPUT_TOKENS,
    TIER_OUTPUT_TOKENS,
)
from hosts.DesktopHostPySide.widgets.radial_tuner import RadialTuner
from hosts.DesktopHostPySide.widgets.stepper import BotanicalSpinBox
from hosts.DesktopHostPySide.widgets.seed_notifications import SeedNotificationLayer
from hosts.DesktopHostPySide.widgets.seed_audio import ZenBell
from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
    CandidateReviewPanel,
    analysis_report_text,
)
from hosts.DesktopHostPySide.widgets.repair_review_panel import RepairReviewPanel
from hosts.DesktopHostPySide.widgets.qt_lifecycle import (
    _qt_alive,
    _qt_safe_slot,
    _qt_safe_timer,
    track_worker,
)
from packages.application import coherence_repair
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

    def __init__(
        self,
        *,
        display_name: str,
        count_label: str,
        causal_rank: object,
        state: str,
        on_enter=None,
        on_global=None,
    ):
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
        super().__init__(
            "Nueva fuente", "Registra una referencia legible para trazabilidad narrativa."
        )
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
        result = self.controller.create(
            {
                "name": self.name.text().strip(),
                "reference": self.reference.text().strip(),
                "fragment": self.fragment.toPlainText().strip(),
                "source_type": "entrada_manual",
            }
        )
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
        result = self.controller.create(
            {
                "name": self.name.text().strip(),
                "description": self.description.toPlainText().strip(),
            }
        )
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        layer = result.value
        self.status.setText(f"Anillo creado: {getattr(layer, 'name', 'sin nombre')}")
        self.on_created()


class RingEditPanel(QWidget):
    """BETA1-B03 / BETA1-UX: editor de anillo (world layer).

    Reescrito para compartir la MISMA estética que el detalle de entidad
    (NodeDetailPanel): cabecera grande + insignia, fila de identidad compacta,
    descripción breve y un CUERPO editorial amplio como protagonista del panel.
    El orden escribe metadata.causal_rank porque la concéntrica ordena los
    anillos por rango causal, no por el campo `order` plano.
    """

    _BG = "#F8F6ED"
    _TITLE = "#5C5A3E"
    _LABEL = "#6F6A42"
    _MUTED = "#7C806E"

    def __init__(self, controller, ring_id: str, on_saved):
        super().__init__()
        self.controller = controller
        self.ring_id = ring_id
        self.on_saved = on_saved

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # Estilos editoriales compartidos con el detalle de entidad.
        field_ss = (
            f"QLineEdit {{ background: {INPUT_BG}; border: 1px solid {LINE}; "
            f"border-radius: 10px; padding: 8px 10px; font-size: 14px; color: {INK}; }} "
            f"QLineEdit:hover {{ border-color: {LINE_STRONG}; }} "
            f"QLineEdit:focus {{ border: 2px solid {GOLD}; background: #FFFFFF; padding: 7px 9px; }}"
        )
        body_ss = (
            f"QTextEdit {{ background: {INPUT_BG}; border: 1px solid {LINE}; "
            f"border-radius: 12px; padding: 10px; font-size: 13px; color: {INK}; }} "
            f"QTextEdit:hover {{ border-color: {LINE_STRONG}; }} "
            f"QTextEdit:focus {{ border: 2px solid {GOLD}; background: #FFFFFF; padding: 9px; }}"
        )
        label_ss = f"color: {self._LABEL}; background: transparent; font-weight: 600;"

        # — Cabecera: título grande + insignia (igual que NodeDetailPanel) —
        head = QHBoxLayout()
        self.title = QLabel("Anillo")
        self.title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {self._TITLE}; "
            f"font-family: Georgia, 'Courier New', serif; background: transparent;"
        )
        self.title.setWordWrap(True)
        head.addWidget(self.title, 1)
        head.addWidget(Badge("Estrato", "info"))
        root.addLayout(head)

        self.summary = QLabel("Corona concéntrica del mundo · no modifica canon")
        self.summary.setStyleSheet(f"color: {self._MUTED}; background: transparent;")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        # — Fila de identidad: Nombre (protagonista) + Orden —
        ident = QHBoxLayout()
        ident.setSpacing(10)
        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_lbl = QLabel("Nombre")
        name_lbl.setStyleSheet(label_ss)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre del estrato")
        self.name.setStyleSheet(field_ss)
        name_col.addWidget(name_lbl)
        name_col.addWidget(self.name)
        ident.addLayout(name_col, 3)
        order_col = QVBoxLayout()
        order_col.setSpacing(4)
        order_lbl = QLabel("Orden")
        order_lbl.setToolTip("Rango causal: ordena los anillos del núcleo al borde")
        order_lbl.setStyleSheet(label_ss)
        self.order = BotanicalSpinBox()
        self.order.setRange(1, 999)
        self.order.setMinimumHeight(38)
        order_col.addWidget(order_lbl)
        order_col.addWidget(self.order)
        ident.addLayout(order_col, 1)
        root.addLayout(ident)

        # — Descripción breve —
        brief_lbl = QLabel("Descripción breve")
        brief_lbl.setStyleSheet(label_ss)
        root.addWidget(brief_lbl)
        self.brief = QLineEdit()
        self.brief.setPlaceholderText("Una línea que resuma el estrato…")
        self.brief.setStyleSheet(field_ss)
        root.addWidget(self.brief)

        # — Cuerpo: protagonista del panel (amplio, como en el detalle) —
        body_lbl = QLabel("Descripción")
        body_lbl.setStyleSheet(label_ss)
        root.addWidget(body_lbl)
        self.description = QTextEdit()
        self.description.setPlaceholderText(
            "¿Qué representa esta capa del mundo? Su materia, su tono, qué la "
            "distingue de los anillos vecinos…"
        )
        self.description.setMinimumHeight(280)
        self.description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.description.setStyleSheet(body_ss)
        root.addWidget(self.description, 1)

        # — Carga de datos —
        current = controller.get(ring_id) if hasattr(controller, "get") else None
        layer = getattr(current, "value", None)
        if layer is not None:
            self.title.setText(str(getattr(layer, "name", "") or "Anillo"))
            self.name.setText(str(getattr(layer, "name", "")))
            meta = getattr(layer, "metadata", {}) or {}
            rank = str(meta.get("causal_rank", "") or getattr(layer, "order", 1))
            try:
                self.order.setValue(int(rank))
            except (TypeError, ValueError):
                self.order.setValue(int(getattr(layer, "order", 1) or 1))
            self.brief.setText(str(meta.get("brief", "")))
            self.description.setPlainText(str(getattr(layer, "description", "") or ""))

        self.status = QLabel("")
        self.status.setObjectName("mutedLabel")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        # — Acciones —
        row = QHBoxLayout()
        row.addStretch(1)
        save = QPushButton("Guardar anillo")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addWidget(save)
        root.addLayout(row)

        # Fondo cálido del panel, SCOPED al objectName para no sangrar a los hijos.
        self.setObjectName("ringEditPanel")
        self.setStyleSheet(f"QWidget#ringEditPanel {{ background: {self._BG}; }}")

    def _save(self):
        name = self.name.text().strip()
        if not name:
            self.status.setText("El nombre no puede estar vacio")
            return
        order = int(self.order.value())
        result = self.controller.update(
            self.ring_id,
            {
                "name": name,
                "order": order,
                "description": self.description.toPlainText().strip(),
                "metadata": {"causal_rank": str(order), "brief": self.brief.text().strip()},
            },
        )
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
        self.start = BotanicalSpinBox()
        self.start.setRange(-999999999, 999999999)
        self.open_ended = QCheckBox("Era abierta (sin año final)")
        self.open_ended.setChecked(True)
        self.end = BotanicalSpinBox()
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
        super().__init__(
            "Nueva era", "Un estrato temporal del mundo (los años pueden ser negativos)."
        )
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


class NarrativeWorkbench(QWidget):
    """Normal-mode clean entry points for creation work."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__()
        self.workspace = workspace
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(
            SectionHeader(
                "Taller narrativo",
                "Crea y organiza sin tablas técnicas; los detalles avanzados quedan detrás del modo avanzado.",
            )
        )
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)
        actions = [
            (
                "Hoja",
                "Crear personaje, lugar, objeto o concepto.",
                "Nueva hoja",
                self.workspace.open_entity_create,
            ),
            (
                "Relaciones",
                "Conecta nodos visualmente desde el grafo.",
                "Ir al grafo",
                self.workspace.open_graph,
            ),
            (
                "Fuentes",
                "Guarda referencias legibles.",
                "Nueva fuente",
                self.workspace.open_source_create,
            ),
            (
                "Anillos",
                "Organiza el worldbuilding por estratos.",
                "Nuevo anillo",
                self.workspace.open_layer_create,
            ),
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
        layout.addWidget(
            EmptyState(
                "Modo normal activo",
                "IDs, JSON, tablas técnicas y metadatos quedan en Avanzado. La funcionalidad sigue disponible con lenguaje narrativo.",
            )
        )
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
        super().__init__(
            "Tareas IA", "Jobs de Dendro en segundo plano. Ninguno canoniza automáticamente."
        )
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
            self.jobs_layout.addWidget(
                EmptyState("Sin tareas IA", "Lanza una petición desde la command bar.")
            )
            return
        for job in reversed(jobs):
            card = Card(self._job_title(job), self._job_description(job))
            rag_label = QLabel(self._job_rag_status(job))
            rag_label.setObjectName("mutedLabel")
            rag_label.setWordWrap(True)
            rag_label.setStyleSheet(
                "font-size: 11px; color: #6F6A42; background: transparent; border: none;"
            )
            card.layout.addWidget(rag_label)
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(int(max(0.0, min(1.0, float(getattr(job, "progress", 0.0)))) * 100))
            card.layout.addWidget(progress)
            # SEM03: sin «Ver resultado» (los candidatos germinan como semillas);
            # se mantiene «Cancelar» para tareas en curso.
            row = QHBoxLayout()
            cancel = QPushButton("Cancelar")
            cancel.setEnabled(
                getattr(job, "cancellable", True)
                and str(getattr(job, "status", ""))
                not in {
                    "AIJobStatus.READY_FOR_REVIEW",
                    "AIJobStatus.FAILED",
                    "AIJobStatus.CANCELLED",
                }
            )
            cancel.clicked.connect(lambda _, jid=getattr(job, "id", ""): self._cancel(jid))
            row.addStretch(1)
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
        active = status in {
            "queued",
            "building_context",
            "planning",
            "waiting_for_model",
            "running",
            "postprocessing",
        }
        plan = getattr(job, "plan", {}) or {}
        context = plan.get("context", {}) if isinstance(plan, dict) else {}
        pack = context.get("rag_context_pack", {}) if isinstance(context, dict) else {}
        if not isinstance(pack, dict) or not pack:
            return "RAG: preparando contexto" if active else "RAG: sin contexto registrado"

        warnings = [str(item) for item in (pack.get("warnings") or []) if str(item)]
        items = pack.get("items") if isinstance(pack.get("items"), list) else []
        tokens = int(pack.get("tokens_estimated", 0) or 0)
        if warnings and not items:
            return f"RAG: {'; '.join(warnings)}"
        truncated = " · truncado" if pack.get("truncated") else ""
        warning_text = f" · aviso: {'; '.join(warnings)}" if warnings else ""
        return f"RAG: contexto listo ({len(items)} items, {tokens} tokens){truncated}{warning_text}"

    def _cancel(self, job_id: str):
        result = self.workspace.ai_job_service.cancel_job(job_id)
        if isinstance(result, Error):
            self.workspace.ctx.log("warning", result.error)
        self.workspace._sync_jobs_indicator()
        self.refresh()


# SEM04: tipos de job que NO germinan una semilla en el grafo. Solo los que NO
# producen un candidato revisable: texto inline (se queda en el panel) y la
# reparación de coherencia (abre su propio panel de cambios). Los análisis
# (coherence/review) SÍ germinan: su informe es un candidato-semilla que orbita
# en el anillo activo mientras corre el job y al terminar (como freeform_planning).
_NO_SEED_JOB_TYPES = {"improve_text", "generate_text", "repair_coherence"}

# UX5: jobs de edición → las entidades seleccionadas germinan mientras corre el job.
_EDIT_JOB_TYPES = {"edit_entities", "edit_relation", "edit_ring", "edit_milestone"}


class _AIJobWorker(QThread):
    """Run an AI job outside the UI thread."""

    statusChanged = Signal(str, str, str, float)  # SEM04: + job_id para germinación
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
        self.statusChanged.emit(self.job_id, job.status.value, job.message, float(job.progress))
        return job

    def run(self):
        try:
            self._emit_job()
            result = self.service.execute_job(
                self.job_id, progress_callback=lambda _job: self._emit_job()
            )
            job = self._emit_job()
            if isinstance(result, Error):
                self.failed.emit(self.job_id, result.error)
                return
            if job is None:
                return
            self.finishedOk.emit(self.job_id)
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            self.failed.emit(self.job_id, str(exc))


class _WalkStepWorker(QThread):
    """CRON: analiza un paso del recorrido fuera del hilo de UI.

    La llamada al modelo bloquea; ejecutarla aquí permite que la UI muestre el
    pulso/cámara de «analizando» sin congelarse.
    """

    finishedOk = Signal(object)  # dict resultado de analyze_step
    failed = Signal(str)

    def __init__(self, controller, session_id: str):
        super().__init__()
        self.controller = controller
        self.session_id = session_id

    def run(self):
        try:
            res = self.controller.analyze(self.session_id)
            if isinstance(res, Error):
                self.failed.emit(res.error)
                return
            self.finishedOk.emit(res.value)
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            self.failed.emit(str(exc))


class _ContextPreviewWorker(QThread):
    """UX3: calcula la vista previa de contexto fuera del hilo de UI.

    El cálculo hace retrieval real (RAG), así que puede tardar; se ejecuta en un
    hilo para no congelar la barra mientras se muestra «Calculando contexto…»."""

    ready = Signal(dict)
    failed = Signal(str)

    def __init__(self, service: AIJobService, job_type, prompt: str, scope: dict):
        super().__init__()
        self.service = service
        self.job_type = job_type
        self.prompt = prompt
        self.scope = scope

    def run(self):
        try:
            result = self.service.preview_context(
                self.job_type, self.prompt, context_scope=self.scope, explicit=True
            )
            if isinstance(result, Error):
                self.failed.emit(result.error)
                return
            self.ready.emit(dict(result.value))
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            self.failed.emit(str(exc))


class CreationSearchPanel(_SimpleFormPanel):
    """B37-T01 clean graph search panel inside the right drawer."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__(
            "Buscar en Creación", "Encuentra nodos, árboles o relaciones sin tablas técnicas."
        )
        self.workspace = workspace
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar por nombre, tipo, descripción, rama, relación o anillo"
        )
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
        collapsed_hint = (
            "\nDentro de árbol colapsado: se expandirá la ruta al enfocar."
            if result.is_inside_collapsed_tree
            else ""
        )
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
            self.status.setText(
                "No se pudo enfocar. Puede estar oculto por filtros activos; limpia filtros e inténtalo de nuevo."
            )


class CreationRingPanel(_SimpleFormPanel):
    """BETA1-L02: selector de anillos. Lista los anillos de dentro a fuera
    (orden causal) con su recuento; clic = enmarcar y enfocar ese anillo
    atenuando el resto. El anillo activo se resalta → indica 'dónde estoy'."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__("Anillos del mundo", "Salta a una capa y recórrelas de dentro a fuera.")
        self.workspace = workspace
        self._buttons: dict[str, QPushButton] = {}
        self.status = self.add_status()
        # Volver al panorama (quitar foco)
        all_btn = QPushButton("Ver todo el grafo")
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.setStyleSheet(
            f"QPushButton {{ text-align: left; background: {SURFACE_HI}; border: 1px solid {LINE}; "
            f"border-radius: 10px; padding: 8px; color: {INK_SOFT}; font-weight: 600; }} "
            f"QPushButton:hover {{ border-color: {GOLD}; }}"
        )
        all_btn.clicked.connect(self._show_all)
        self.layout.addWidget(all_btn)
        self.rings_layout = QVBoxLayout()
        self.rings_layout.setSpacing(6)
        self.layout.addLayout(self.rings_layout)
        self.layout.addStretch(1)
        self._populate()

    def _populate(self):
        while self.rings_layout.count():
            item = self.rings_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._buttons.clear()
        summaries = self.workspace.graph.ring_summaries()
        if not summaries:
            self.status.setText("Aún no hay anillos. Crea capas de mundo para organizarlo.")
            return
        self.status.setText(
            f"{len(summaries)} anillos, de dentro a fuera. Selecciona uno para enfocarlo."
        )
        for summary in summaries:
            button = QPushButton(f"{summary['name']}  ·  {summary['count']}")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, rid=summary["ring_id"]: self._focus_ring(rid))
            self._buttons[summary["ring_id"]] = button
            self.rings_layout.addWidget(button)
        self.refresh_highlight()

    def _ring_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ text-align: left; background: {GOLD}; border: none; "
                f"border-radius: 10px; padding: 8px; color: #FCF8EC; font-weight: 700; }}"
            )
        return (
            "QPushButton { text-align: left; background: #F8F5EA; border: 1px solid #D8D2BF; "
            "border-radius: 10px; padding: 8px; color: #4F4D38; } "
            "QPushButton:hover { background: #FFFDF6; border-color: #AFA77A; }"
        )

    def refresh_highlight(self):
        focused = self.workspace.graph.focused_ring_id()
        for ring_id, button in self._buttons.items():
            button.setStyleSheet(self._ring_style(ring_id == focused))

    def _focus_ring(self, ring_id: str):
        self.workspace.focus_ring_scope(ring_id)
        self.refresh_highlight()

    def _show_all(self):
        self.workspace.clear_focus_scope()
        self.refresh_highlight()


# BETA1-L02c: retardo (ms) antes de saltar a la mejor coincidencia mientras se
# escribe en la barra flotante. Permite teclear seguido sin perder el foco.
_SEARCH_DEBOUNCE_MS = 280


class _SearchLineEdit(QLineEdit):
    """BETA1-L02b: campo de la barra flotante. Escape cierra la barra; el resto
    de teclas se comportan como un QLineEdit normal (Enter usa returnPressed)."""

    escapePressed = Signal()

    def keyPressEvent(self, event):  # noqa: N802 (Qt API)
        if event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _FloatingSearchBar(QFrame):
    """BETA1-L02b: barra de búsqueda flotante ligera sobre el lienzo (tecla 'd').
    No abre el drawer. Al teclear, el workspace busca (entidades del grafo + hitos
    de la cronología) y salta EN VIVO a la mejor coincidencia. Esc cierra; Enter
    confirma y cierra; clic en un resultado navega a él."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__(workspace)
        self.workspace = workspace
        # BETA1-L02c: ancho FIJO → añadir resultados no cambia el ancho ni reencuadra
        # horizontalmente la barra (antes el campo "saltaba" al teclear).
        self.setFixedWidth(420)
        self.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: 1px solid {LINE}; border-radius: 12px; }}"
        )
        col = QVBoxLayout(self)
        col.setContentsMargins(10, 8, 10, 8)
        col.setSpacing(6)
        self.search = _SearchLineEdit()
        self.search.setPlaceholderText("Ir a… (entidad o hito) — Esc para cerrar")
        self.search.setStyleSheet(
            f"QLineEdit {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 9px; "
            f"padding: 6px 10px; color: {INK}; }} QLineEdit:focus {{ border-color: {GOLD}; }}"
        )
        self.search.textChanged.connect(self._on_text)
        self.search.returnPressed.connect(self.workspace._close_search_overlay)
        self.search.escapePressed.connect(self.workspace._close_search_overlay)
        col.addWidget(self.search)
        self.results_layout = QVBoxLayout()
        self.results_layout.setSpacing(4)
        col.addLayout(self.results_layout)
        self.adjustSize()

    def focus_input(self):
        self.search.setFocus()
        self.search.selectAll()

    def _on_text(self, text: str):
        self.workspace._on_search_overlay_text(text)

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_results(self, items: list[dict]):
        # BETA1-L02c: solo crece/mengua en alto (ancho fijo); NO reposiciona la barra
        # ni roba el foco del campo mientras se escribe.
        self._clear_results()
        for item in items:
            self.results_layout.addWidget(self._result_button(item))
        self.adjustSize()

    def _result_button(self, item: dict) -> QPushButton:
        tag = "Hito" if item["kind"] == "milestone" else (item.get("type_label") or "")
        label = f"{item['title']}   ·  {tag}" if tag else item["title"]
        button = QPushButton(label)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # BETA1-L02c: nunca roba el foco
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton {{ text-align: left; background: {SURFACE}; border: 1px solid {LINE}; "
            f"border-radius: 8px; padding: 6px 8px; color: {INK_SOFT}; }} "
            f"QPushButton:hover {{ border-color: {GOLD}; color: {GOLD_DEEP}; }}"
        )
        button.clicked.connect(lambda _=False, it=item: self.workspace._navigate_search_item(it))
        return button


class CreationFilterPanel(_SimpleFormPanel):
    """B37-T02 visual filters. Ephemeral: never writes project/canon."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__(
            "Filtros visuales", "Reduce la vista sin modificar el proyecto ni el canon."
        )
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
        for combo in (
            self.entity_type,
            self.relation_type,
            self.relation_family,
            self.tree,
            self.layer,
            self.canon,
        ):
            combo.addItem("- Cualquiera -", "")
        for label, value in (
            ("Pertenencia estructural", "estructural"),
            ("Narrativa", "narrativa"),
            ("Causal", "causal"),
            ("Coherencia/incidencias", "coherencia"),
        ):
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
        for widget in (
            self.entity_type,
            self.relation_type,
            self.relation_family,
            self.tree,
            self.layer,
            self.canon,
        ):
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
            name.setStyleSheet(
                "color: #504B2E; font-size: 12px; background: transparent; border: none;"
            )
            row.addWidget(name, 1)
            edit = QPushButton("Editar")
            edit.setFixedHeight(24)
            edit.setToolTip("Nombre y orden del anillo")
            edit.clicked.connect(
                lambda _=False, rid=str(getattr(ring, "id", "")): (
                    self.workspace._open_ring_edit_panel(rid)
                )
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
        return (
            bool(getattr(project, "worldbuilding_active", False)) if project is not None else False
        )

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
            name.setStyleSheet(
                "color: #504B2E; font-size: 12px; background: transparent; border: none;"
            )
            row.addWidget(name, 1)
            end = getattr(era, "end_year", None)
            span = QLabel(f"{getattr(era, 'start_year', 0)} → {end if end is not None else '…'}")
            span.setStyleSheet(
                "color: #7C806E; font-size: 11px; background: transparent; border: none;"
            )
            row.addWidget(span)
            edit = QPushButton("Editar")
            edit.setFixedHeight(24)
            edit.setToolTip("Nombre y límites de la era")
            edit.clicked.connect(
                lambda _=False, eid=str(getattr(era, "id", "")): (
                    self.workspace._open_era_edit_panel(eid)
                )
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
        present_label.setStyleSheet(
            "color: #504B2E; font-size: 12px; background: transparent; border: none;"
        )
        present_row.addWidget(present_label, 1)
        self.present_year_spin = BotanicalSpinBox()
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
            kind = str(
                getattr(
                    getattr(entity, "entity_type", None),
                    "value",
                    getattr(entity, "entity_type", ""),
                )
                or ""
            )
            self._add_unique(self.entity_type, enum_human(kind), kind, seen_entity)
            canon = str(
                getattr(
                    getattr(entity, "canon_state", None),
                    "value",
                    getattr(entity, "canon_state", ""),
                )
                or ""
            )
            self._add_unique(self.canon, enum_human(canon), canon, seen_canon)
            if kind.lower() == "contenedor":
                self.tree.addItem(
                    str(getattr(entity, "name", "Rama")), str(getattr(entity, "id", ""))
                )
        seen_rel: set[str] = set()
        for relation in relations:
            kind = str(
                getattr(
                    getattr(relation, "relation_type", None),
                    "value",
                    getattr(relation, "relation_type", ""),
                )
                or ""
            )
            self._add_unique(self.relation_type, enum_human(kind), kind, seen_rel)
        for layer in list(getattr(project, "world_layers", []) or []):
            if getattr(layer, "is_visible", True):
                self.layer.addItem(
                    str(getattr(layer, "name", "Anillo")), str(getattr(layer, "id", ""))
                )

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
        self._type.addItems(
            [
                "origen",
                "fundacion",
                "ruptura",
                "guerra",
                "pacto",
                "traicion",
                "descubrimiento",
                "catastrofe",
                "reforma",
                "prohibicion",
                "revelacion",
                "migracion",
                "ascenso",
                "caida",
                "transformacion",
                "consecuencia",
                "estado_actual",
            ]
        )
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
        result = self.controller.create_manual(
            {
                "title": title,
                "milestone_type": self._type.currentText(),
                "description": self._desc.toPlainText().strip(),
                "rationale": self._rationale.toPlainText().strip(),
                **self._prefill,
            }
        )
        if isinstance(result, Error):
            self._status.setText(result.error)
            return
        self._status.setText(f"Hito creado: {title}")
        self._refresh_cards()
        if self.on_created:
            self.on_created()


class CreationWorkspace(QWidget):
    """Creation space: graph-first immersive experience."""

    def __init__(
        self,
        ctx: AppContext,
        *,
        corpus_view,
        relation_view,
        candidate_view,
        source_view=None,
        layer_view=None,
    ):
        super().__init__()
        self.ctx = ctx
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
        self.prompt_trace_store = (
            getattr(self.ctx, "ai_prompt_trace_store", None) or AIPromptDebugTraceStore.default()
        )
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
        # Semillas (Fase A): notificaciones palpitantes abajo-derecha + campana zen.
        self._zen_bell = ZenBell()
        self._seed_notifications = SeedNotificationLayer(self)
        # SEM04: el workspace ancla la capa ENCIMA del cluster de botones derecho,
        # con z-order por encima, para que no solape los botones ni pierda los clics.
        self._seed_notifications.set_reflow_callback(self._position_seed_layer)
        self._seed_notifications.reviewRequested.connect(self._open_candidate_review)
        self._active_layer_id = ""
        self._advanced_mode = bool(ctx.advanced_mode)
        project_controller = getattr(ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is not None:
            self.ai_context_controller = AIContextController(
                project_service, ai_job_service=self.ai_job_service
            )
            self._milestone_ctrl = CausalMilestoneController(project_service)
            self._chronology_ctrl = ProjectChronologyController(project_service)
            self.era_controller = EraController(project_service)  # BETA1-G03
            # CRON: recorrido cronológico (Modo Creación Cronológica).
            self.chronology_walk_controller = ChronologyWalkController(
                project_service, self.ai_job_service
            )
        else:
            self._milestone_ctrl = None
            self._chronology_ctrl = None
            self.era_controller = None
            self.chronology_walk_controller = None
        # CRON: sesión de recorrido en curso (id) y su panel runner.
        self._walk_session_id: str | None = None
        self._walk_runner = None
        self._walk_step_worker = None
        self._walk_workers: set = set()  # mantiene vivos los QThread del recorrido
        self._walk_analyzing = False  # guarda determinista contra pasos solapados
        self._walk_step_candidate_ids: list[str] = []
        # CRON: perro guardián — si la llamada al modelo se cuelga, recupera la UI
        # (no deja los botones deshabilitados para siempre = "congelada").
        self._walk_watchdog: QTimer | None = None
        self._walk_watchdog_ms = 120000

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
        self.graph.candidateClicked.connect(self._open_candidate_review)  # SEM04
        self.graph.relationSelected.connect(self._open_relation_panel)
        self.graph.relationCreateRequested.connect(self._open_relation_create_panel)
        self.graph.relationCreateRejected.connect(self._on_relation_create_rejected)
        self.graph.graphSelectionChanged.connect(self._on_graph_selection_changed)
        self.graph.nodeAssignToTreeRequested.connect(self._assign_node_to_tree)
        self.graph.ringSelected.connect(self._on_ring_selected)
        self.graph.ringFocused.connect(self._on_ring_focused)
        self.graph.ringFocusCleared.connect(self._on_ring_focus_cleared)
        self.graph.searchRequested.connect(self._open_search_overlay)  # BETA1-L02b ('d')
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
        self.chrono.walkRequested.connect(self._start_or_continue_walk)  # CRON
        self.chrono.lifespanEdited.connect(self._on_lifespan_edited)  # BETA1-UX2C
        self.chrono.milestoneCreateRequested.connect(
            self._on_chrono_create_milestone
        )  # BETA1-HITO-MULTI
        self.chrono.eraActivated.connect(self._open_era_edit_panel)  # BETA1-HITO-MULTI
        self.chrono.milestoneEntityLinkRequested.connect(
            self._on_chrono_link_entity
        )  # BETA1-HITO-MULTI
        layout.addWidget(self.chrono, 1)

        # BETA2-FOCO: Modo Foco — escritorio causal centrado en una entidad.
        # Es la vista PRINCIPAL de Creación; el grafo (Mapa) y la cronología
        # pasan a ser vistas globales de orientación/revisión del jardín.
        _foco_ps = getattr(getattr(self.ctx, "project_controller", None), "ps", None)
        self.foco = FocoView(
            project_provider=self._get_active_project,
            last_entity_getter=(
                (lambda: getattr(_foco_ps.get_last_worked_entity(), "value", ""))
                if _foco_ps is not None
                else None
            ),
            last_entity_setter=(
                _foco_ps.set_last_worked_entity if _foco_ps is not None else None
            ),
            ctx=self.ctx,
            entity_controller=self.entity_controller,
            relation_controller=self.relation_controller,
            milestone_controller=self._milestone_ctrl,
            # FOCO-11: fantasmas por controller (mismos métodos que GhostService).
            ghost_service=(GhostController(_foco_ps) if _foco_ps is not None else None),
        )
        self.foco.setVisible(False)
        self.foco.openInMapRequested.connect(self._foco_open_in_map)
        self.foco.openInChronoRequested.connect(self._foco_open_in_chrono)
        # FOCO-10: la banda local reutiliza los slots de la cronología global.
        self.foco.lifespanEdited.connect(self._on_lifespan_edited)
        self.foco.milestoneCreateRequested.connect(self._on_chrono_create_milestone)
        # FOCO-12: riego — servicio real + drawer dedicado + autorización SIEMPRE.
        self.watering_service = (
            WateringService(
                _foco_ps,
                ai_job_service=self.ai_job_service,
                history_service=HistoryService(_foco_ps),
            )
            if _foco_ps is not None
            else None
        )
        self.foco.watering_service = self.watering_service
        self._watering_panel: WateringPanel | None = None
        self._watering_worker: WateringBatchWorker | None = None
        self.foco.waterRequested.connect(self._on_foco_water)
        self.foco.dryRequested.connect(self._on_foco_dry)
        self.foco.cultivateRequested.connect(self._on_foco_cultivate)
        self.foco.entityCentered.connect(self._sync_watering_panel_entity)
        layout.addWidget(self.foco, 1)
        self._active_view = "concentric"  # el arranque fuerza "foco" al final de _build_ui

        # Command bar area replaces the old bottom button toolbar.
        self._command_bar = self._build_command_bar()
        command_bar = self._command_bar
        layout.addWidget(command_bar)

        # BETA1-F02 (revisión): clusters flotantes a ambos lados, sobre la
        # command bar. Símbolos monocromos, minimalistas, con leve vaivén.
        self._float_left = self._build_float_cluster(
            [
                ("search", "Buscar y enfocar elementos", self._open_search_panel),
                ("filter", "Filtros, anillos y eras", self._open_filter_panel),
            ]
        )
        # UX29: el guardar usa el MISMO formato de píldora que el alternador central
        # (icono + texto), abajo-derecha, en vez de un círculo dorado que no se veía.
        self._float_right = self._build_save_pill()
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
        self._float_focus_label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: 11px; font-weight: 600; background: transparent; border: none;"
        )
        focus_layout.addWidget(self._float_focus_label)
        # BETA1-L02b: saltar al anillo contiguo se hace por teclado ([ / ]); sin botones.
        focus_exit = QPushButton("Salir")
        focus_exit.setIcon(icons.icon("close", color="#FCF8EC", size=13))
        focus_exit.setIconSize(QSize(13, 13))
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

        # BETA1-L02b: barra de búsqueda flotante ligera (tecla 'd'). No abre el
        # drawer: aparece sobre el lienzo y salta EN VIVO a la mejor coincidencia
        # mientras se escribe (entidades del grafo + hitos de la cronología).
        # Esc la cierra y devuelve el foco al lienzo.
        self._float_search = _FloatingSearchBar(self)
        self._float_search.setVisible(False)
        # BETA1-L02c: debounce del salto en vivo (escribir seguido sin perder foco).
        self._search_pending_item: dict | None = None
        self._search_nav_timer = QTimer(self)
        self._search_nav_timer.setSingleShot(True)
        self._search_nav_timer.timeout.connect(self._fire_search_nav)

        # Left layer drawer is persistent: explicit button toggles it.
        self._layer_flyout = _LayerEdgeFlyout(self)
        self._layer_flyout.setVisible(False)

        self.setMouseTracking(True)
        self.graph.setMouseTracking(True)

        # BETA2-FOCO: al abrir la Creación se entra SIEMPRE en Foco (decisión de
        # producto: Foco es la vista principal y carga la última entidad
        # trabajada). La clave QSettings 'creation/active_view' se conserva —
        # set_active_view la sigue escribiendo — pero ya no decide la vista
        # inicial (antes BETA1-G04 restauraba grafo/cronología desde ahí).
        self.set_active_view("foco")

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
        self._coherence_btn = icon_btn(
            "!",
            "Selecciona nodos o relaciones para analizar coherencia",
            self._open_coherence_panel,
            enabled=False,
        )
        icon_btn("Buscar", "Buscar y enfocar elementos", self._open_search_panel)
        icon_btn("Anillos", "Selector de anillos: recorrer las capas", self._open_ring_panel)
        self._filter_btn = icon_btn("Filtro", "Filtros visuales", self._open_filter_panel)
        self._jobs_btn = icon_btn("Tareas", "Tareas IA en segundo plano", self._open_ai_jobs_panel)
        self._jobs_btn.setStyleSheet(text_btn_style)
        self._jobs_btn.setFixedWidth(74)
        self._suggest_branch_btn = icon_btn("Rama IA", "Sugerir rama con IA", self._suggest_branch)
        self._suggest_branch_btn.setStyleSheet(text_btn_style)
        self._suggest_branch_btn.setFixedWidth(74)
        self._suggest_relation_btn = icon_btn(
            "Rel IA",
            "Selecciona nodos para sugerir relaciones con IA",
            self._suggest_relation,
            enabled=False,
        )
        self._suggest_relation_btn.setStyleSheet(disabled_style)
        self._suggest_relation_btn.setFixedWidth(66)
        self._summary_btn = icon_btn(
            "Resumen",
            "Selecciona elementos para resumir con IA",
            self._summarize_selection,
            enabled=False,
        )
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

    def _build_save_pill(self) -> QFrame:
        """UX29: píldora de Guardar con el MISMO formato que el alternador central
        (SURFACE_HI + borde oro, icono + texto), anclada abajo-derecha."""
        pill = QFrame(self)
        # UX33: marrón (como el resto de acciones), no la píldora clara.
        pill.setStyleSheet(
            f"QFrame {{ background: {GOLD_DEEP}; border: 1px solid {GOLD_DEEP}; border-radius: 19px; }}"
        )
        row = QHBoxLayout(pill)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(0)
        self._save_btn = QPushButton("  Guardar")
        self._save_btn.setIcon(icons.icon("save", color="#FCF8EC", size=15))
        self._save_btn.setIconSize(QSize(15, 15))
        self._save_btn.setToolTip("Guardar el proyecto")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setFixedHeight(32)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 16px; "
            f"color: #FCF8EC; font-size: 13px; font-weight: 700; padding: 0 16px; }} "
            f"QPushButton:hover {{ background: {GOLD}; color: #FCF8EC; }} "
            f"QPushButton:pressed {{ background: #5E5427; }}"
        )
        self._save_btn.clicked.connect(self._save_project_from_canvas)
        row.addWidget(self._save_btn)
        pill.adjustSize()
        pill.raise_()
        return pill

    def _build_view_toggle(self) -> QFrame:
        """BETA2-FOCO: barra superior de modos — Foco | Mapa | Cronología.

        Sustituye a la píldora binaria BETA1-G04. Foco es el modo principal;
        Mapa (grafo concéntrico) y Cronología quedan como vistas globales.
        Se ancla arriba-centro (spec: "barra superior de modos")."""
        pill = QFrame(self)
        pill.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: 1px solid {GOLD_SOFT}; border-radius: 19px; }}"
        )
        row = QHBoxLayout(pill)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(0)

        def _mode_button(label: str, icon_name: str, tooltip: str, mode: str) -> QPushButton:
            button = QPushButton(f"  {label}")
            button.setIcon(icons.icon(icon_name, color=INK_SOFT, size=15))
            button.setIconSize(QSize(15, 15))
            button.setToolTip(tooltip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(32)
            button.clicked.connect(lambda _=False, m=mode: self.set_active_view(m))
            row.addWidget(button)
            return button

        self._mode_buttons = {
            "foco": _mode_button(
                "Foco",
                "creation",
                "Escritorio de la entidad en foco: crear, editar y cultivar",
                "foco",
            ),
            "concentric": _mode_button(
                "Mapa",
                "worldbuilding",
                "Vista global del canon y del jardín (anillos)",
                "concentric",
            ),
            "chrono": _mode_button(
                "Cronología",
                "chronology",
                "Ver el mundo en el tiempo: eras, vidas e hitos",
                "chrono",
            ),
        }
        self._update_mode_pill(getattr(self, "_active_view", "foco"))
        # CRON: botón para iniciar/continuar el recorrido; visible solo en cronológica.
        self._walk_toggle_btn = QPushButton("  Creación cronológica")
        self._walk_toggle_btn.setToolTip(
            "Iniciar o continuar el recorrido guiado hito por hito (o clic derecho en un hito)"
        )
        self._walk_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._walk_toggle_btn.setFixedHeight(32)
        self._walk_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-left: 1px solid {GOLD_SOFT}; "
            f"color: {INK_SOFT}; font-size: 13px; font-weight: 600; padding: 0 16px; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; color: {INK_STRONG}; }} "
            f"QPushButton:pressed {{ background: {GOLD_SOFT}; }}"
        )
        self._walk_toggle_btn.clicked.connect(self._walk_bar_clicked)
        self._walk_toggle_btn.setVisible(False)
        row.addWidget(self._walk_toggle_btn)
        pill.adjustSize()
        pill.raise_()
        return pill

    def _update_mode_pill(self, view: str) -> None:
        """BETA2-FOCO: resalta el modo activo en la barra superior."""
        buttons = getattr(self, "_mode_buttons", None)
        if not buttons:
            return
        active_style = (
            f"QPushButton {{ background: {GOLD_TINT}; border: none; border-radius: 16px; "
            f"color: {INK_STRONG}; font-size: 13px; font-weight: 700; padding: 0 16px; }}"
        )
        idle_style = (
            f"QPushButton {{ background: transparent; border: none; border-radius: 16px; "
            f"color: {INK_SOFT}; font-size: 13px; font-weight: 600; padding: 0 16px; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; color: {INK_STRONG}; }} "
            f"QPushButton:pressed {{ background: {GOLD_SOFT}; }}"
        )
        for mode, button in buttons.items():
            button.setStyleSheet(active_style if mode == view else idle_style)

    def _foco_open_in_map(self, entity_id: str) -> None:
        """BETA2-FOCO: 'ver esta entidad en Mapa' — vista global + enfoque."""
        self.set_active_view("concentric")
        focus = getattr(self.graph, "focus_node", None)
        if callable(focus):
            try:
                focus(entity_id)
            except Exception:  # noqa: BLE001 - enfocar es best-effort
                pass

    def _foco_open_in_chrono(self, entity_id: str) -> None:
        """BETA2-FOCO: 'ver esta entidad en Cronología global'."""
        self.set_active_view("chrono")
        focus = getattr(self.chrono, "focus_entity", None)
        if callable(focus):
            try:
                focus(entity_id)
            except Exception:  # noqa: BLE001 - enfocar es best-effort
                pass

    # ------------------------------------------------------------------
    # FOCO-12: riego desde la UI — drawer dedicado, autorización y lote
    # ------------------------------------------------------------------

    def _ensure_watering_panel(self) -> "WateringPanel | None":
        if self.watering_service is None:
            return None
        if self._watering_panel is None:
            panel = WateringPanel(self.watering_service)
            panel.waterRequested.connect(
                lambda: self._on_foco_water(
                    [self.foco.current_entity_id()] if self.foco.current_entity_id() else []
                )
            )
            panel.pauseToggled.connect(self._on_watering_pause_toggled)
            panel.suggestRequested.connect(self._on_foco_suggest)
            panel.cancelBatchRequested.connect(self._cancel_watering_batch)
            self._watering_panel = panel
        return self._watering_panel

    def _open_watering_drawer(self, entity_id: str = "") -> None:
        panel = self._ensure_watering_panel()
        if panel is None or self.ctx.drawer is None:
            return
        panel.set_entity(entity_id or self.foco.current_entity_id())
        self.ctx.drawer.set_content(panel, title="Riego")
        self.ctx.drawer.open()

    def _sync_watering_panel_entity(self, entity_id: str) -> None:
        panel = self._watering_panel
        if panel is not None and panel.isVisible():
            panel.set_entity(entity_id)

    def _on_foco_dry(self, entity_id: str) -> None:
        """Secar: sin IA, con historial; conserva/silencia la lectura previa."""
        if self.watering_service is None or not entity_id:
            return
        result = self.watering_service.pause(entity_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        self.ctx.request_save_silent()
        self.foco._refresh_tool_context()
        self._open_watering_drawer(entity_id)

    def _on_foco_cultivate(self, entity_id: str) -> None:
        """Cultivar: sin IA; la entidad vuelve al ciclo como Falta regar."""
        if self.watering_service is None or not entity_id:
            return
        result = self.watering_service.resume(entity_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        self.ctx.request_save_silent()
        self.foco._refresh_tool_context()
        self._open_watering_drawer(entity_id)

    def _on_watering_pause_toggled(self, pause: bool) -> None:
        panel = self._watering_panel
        entity_id = panel.entity_id() if panel is not None else self.foco.current_entity_id()
        if pause:
            self._on_foco_dry(entity_id)
        else:
            self._on_foco_cultivate(entity_id)

    def _on_foco_water(self, entity_ids: list) -> None:
        """Regar entidad/selección: SIEMPRE pasa por la autorización visible."""
        service = self.watering_service
        ids = [str(entity_id) for entity_id in (entity_ids or []) if entity_id]
        if service is None or not ids:
            return
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            self.ctx.log(
                "error",
                "IA no configurada: define el proveedor en Ajustes de IA para poder regar.",
            )
            return
        scope = service.entities_in_scope({"selection": ids})
        eligible = getattr(scope, "value", None) or []
        if not eligible:
            self.ctx.log("info", "Nada que regar: la selección no tiene entidades elegibles.")
            return
        estimate = getattr(service.estimate(eligible), "value", None)
        if estimate is None:
            self.ctx.log("error", "No se pudo estimar el coste del riego.")
            return
        project = self._get_active_project()
        names = [
            getattr(project.entity_by_id(entity_id), "name", entity_id)
            for entity_id in eligible[:6]
        ]
        extra = f" (+{len(eligible) - 6} más)" if len(eligible) > 6 else ""
        lines = [
            f"Entidades afectadas ({estimate.entity_count}): {', '.join(names)}{extra}",
            "Se enviará contexto COMPACTO por entidad: ficha, Raíces/Entorno/Brotes, "
            "hitos vinculados y última lectura (los fantasmas van marcados como intención).",
            f"Tokens de entrada estimados: ~{estimate.estimated_input_tokens}.",
            "Resultado esperado: diagnóstico persistente por entidad (métricas + informe). "
            "NO crea Semillas ni modifica canon.",
        ]
        request_watering_authorization(
            getattr(self.ctx, "modal_overlay", None),
            title=("Regar 1 entidad" if len(eligible) == 1 else f"Regar {len(eligible)} entidades"),
            lines=lines,
            cost_class=estimate.cost_class,
            confirm_text="Autorizar y regar",
            on_confirm=lambda: self._run_watering_batch(eligible),
        )

    def _run_watering_batch(self, entity_ids: list) -> None:
        if self.watering_service is None or not entity_ids:
            return
        worker = WateringBatchWorker(self.watering_service, list(entity_ids))
        worker.entityDone.connect(self._on_watering_entity_done)
        worker.progressChanged.connect(self._on_watering_progress)
        worker.finishedOk.connect(self._on_watering_finished)
        worker.finished.connect(lambda: setattr(self, "_watering_worker", None))
        self._watering_worker = worker
        track_worker(worker)  # apagado ordenado al cerrar la app (AUDIT-02)
        panel = self._ensure_watering_panel()
        if panel is not None:
            panel.set_batch_running(True, f"Regando 0/{len(entity_ids)}…")
        self._open_watering_drawer(str(entity_ids[0]))
        worker.start()

    def _cancel_watering_batch(self) -> None:
        worker = self._watering_worker
        if worker is not None:
            worker.request_cancel()
            self.ctx.log("info", "Riego: cancelando entre pasos (los parciales se conservan).")

    def _on_watering_entity_done(self, entity_id: str, ok: bool, error: str) -> None:
        # Parciales SIEMPRE persistidos (guardado silencioso desde el hilo UI).
        self.ctx.request_save_silent()
        if not ok:
            self.ctx.log("error", f"Riego fallido ({entity_id}): {error}")
        if entity_id == self.foco.current_entity_id():
            self.foco._refresh_tool_context()
        if self._watering_panel is not None:
            self._watering_panel.refresh()

    def _on_watering_progress(self, done: int, total: int) -> None:
        if self._watering_panel is not None:
            self._watering_panel.set_batch_running(True, f"Regando {done}/{total}…")
        self._job_status_label.setText(f"Regando {done}/{total}…")

    def _on_watering_finished(self) -> None:
        if self._watering_panel is not None:
            self._watering_panel.set_batch_running(False)
            self._watering_panel.refresh()
        self._job_status_label.setText("")
        self.ctx.log("info", "Riego completado: diagnósticos persistidos.")

    def _on_foco_suggest(self, metric: str) -> None:
        """Sugerir X: autorización visible → pipeline estándar de jobs (Semillas)."""
        service = self.watering_service
        entity_id = self.foco.current_entity_id()
        if service is None or not entity_id:
            return
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            self.ctx.log(
                "error",
                "IA no configurada: define el proveedor en Ajustes de IA para pedir sugerencias.",
            )
            return
        request = service.build_suggestion_request(entity_id, metric)
        if isinstance(request, Error):
            self.ctx.log("error", request.error)
            return
        payload = request.value
        lines = [
            f"Entidad afectada: {payload['entity_name']}.",
            "Se enviará su contexto compacto (ficha + zonas + hitos + última lectura).",
            f"Tokens de entrada estimados: ~{payload['estimated_input_tokens']}.",
            "Resultado esperado: Semillas (candidatos revisables) para reparar la métrica. "
            "Nada se integra al canon sin tu aceptación.",
        ]
        request_watering_authorization(
            getattr(self.ctx, "modal_overlay", None),
            title=f"Sugerir {metric}",
            lines=lines,
            cost_class=str(payload["cost_class"]),
            confirm_text="Autorizar y sugerir",
            on_confirm=lambda: self._launch_toolbar_ai_job(
                payload["prompt"],
                f"Sugerir {metric}…",
                payload["job_type"],
                scope_override=payload["context_scope"],
            ),
        )

    def _walk_bar_clicked(self) -> None:
        """CRON: botón de barra. Continúa el recorrido activo o, si no hay, lo
        inicia por el PRINCIPIO de la cronología (el hito más temprano)."""
        ctrl = self.chronology_walk_controller
        if ctrl is None:
            self.ctx.log("error", "Recorrido cronológico no disponible")
            return
        if not isinstance(ctrl.active(), Error):
            self._start_or_continue_walk("")
            return
        hid = self._first_chronological_milestone_id()
        if not hid:
            self.ctx.log("info", "Crea un hito para iniciar el recorrido cronológico.")
            return
        self.start_chronology_walk(hid)

    def _first_chronological_milestone_id(self) -> str:
        """CRON: id del hito MÁS TEMPRANO (año asc; los no datados al final)."""
        if self._milestone_ctrl is None:
            return ""
        hitos = list(self._milestone_ctrl.list_all() or [])
        if not hitos:
            return ""

        def _key(h):
            year = getattr(h, "year", None)
            has_year = isinstance(year, int) and not isinstance(year, bool)
            try:
                tiebreak = float((getattr(h, "metadata", None) or {}).get("sort_index", 0) or 0)
            except (TypeError, ValueError):
                tiebreak = 0.0
            return (0 if has_year else 1, float(year) if has_year else 0.0, tiebreak)

        return str(getattr(sorted(hitos, key=_key)[0], "id", ""))

    def _toggle_chrono_view(self):
        self.set_active_view(
            "chrono" if getattr(self, "_active_view", "concentric") != "chrono" else "concentric"
        )

    def _play_view_transition(self, chrono_on: bool) -> None:
        """UX31: revela la vista entrante con un velo de pergamino que se desvanece
        DENTRO del viewport (drawForeground), porque el viewport GPU pinta por encima
        de cualquier overlay hermano (UX25 no se veía por eso).

        Respeta la intensidad de animación (modo 'sin animación' → no-op) y falla en
        silencio: el pulido nunca rompe el cambio de vista."""
        try:
            duration = self.ctx.animation_duration(220)
            if duration <= 0:
                return  # animaciones desactivadas: corte directo
            target = self.chrono if chrono_on else self.graph
            play_reveal = getattr(target, "play_reveal", None)
            if callable(play_reveal):
                # UX33: diferir un tick para que la vista entrante (sobre todo el
                # viewport GPU del grafo) esté realizada antes de iniciar el revelado;
                # si no, al pasar a grafo el primer frame no pintaba el velo.
                QTimer.singleShot(0, lambda: play_reveal(duration_ms=duration))
        except Exception:  # noqa: BLE001 - el pulido nunca rompe el cambio de vista
            pass

    def set_active_view(self, view: str):
        """BETA2-FOCO: tres modos — "foco" (escritorio causal, PRINCIPAL) |
        "concentric" (Mapa global) | "chrono" (Cronología global).

        La elección se sigue persistiendo en QSettings 'creation/active_view'
        (compat), pero el arranque de la Creación entra SIEMPRE en foco."""
        view = str(view)
        if view not in ("foco", "concentric", "chrono"):
            view = "foco"
        self._active_view = view
        chrono_on = view == "chrono"
        foco_on = view == "foco"
        if chrono_on:
            self.chrono.set_project(self._get_active_project())
            self.chrono.fit_all()
        self.chrono.setVisible(chrono_on)
        self.graph.setVisible(view == "concentric")
        foco_widget = getattr(self, "foco", None)
        if foco_widget is not None:
            if foco_on:
                foco_widget.refresh()
            foco_widget.setVisible(foco_on)
        # Command bar visible en Foco y Mapa; oculta en Cronología (decisión de producto).
        bar = getattr(self, "_command_bar", None)
        if bar is not None:
            bar.setVisible(view != "chrono")
        walk_btn = getattr(self, "_walk_toggle_btn", None)
        if walk_btn is not None:
            walk_btn.setVisible(chrono_on)  # CRON: entrada al recorrido solo en cronológica
        self._update_mode_pill(view)
        # UX25: transición suave (velo) solo entre las vistas de lienzo global.
        if not foco_on:
            self._play_view_transition(chrono_on)
        # BETA1-UX8: alternar vista reflowa el área central; reposiciona los
        # floats (migas/clusters/barra de modos) diferido para que no queden en
        # coordenadas viejas tras el cambio de visibilidad.
        QTimer.singleShot(0, self._position_floats)
        # BETA1-L02c: al entrar en la concéntrica, el lienzo reclama el foco de
        # teclado para que los atajos (1…0, F, [ ], d) respondan sin clicar antes.
        if view == "concentric":
            QTimer.singleShot(0, self.graph.focus_canvas)
        elif foco_on and foco_widget is not None:
            # En Foco, las flechas navegan por las zonas: el lienzo toma el foco.
            QTimer.singleShot(0, foco_widget.canvas.setFocus)
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
        # BETA1-HITO-MULTI: clic en un hito → su PANEL DE DETALLE enfocado (no el
        # menú de cronología con el calendario).
        self._open_milestone_detail_panel(hid)

    def _open_milestone_detail_panel(self, hito_id: str) -> None:
        """BETA1-HITO-MULTI: panel de detalle de UN hito en el drawer derecho,
        equivalente al de entidades pero con campos propios del hito."""
        drawer = getattr(self.ctx, "drawer", None)
        if self._milestone_ctrl is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir el detalle del hito")
            return
        from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

        panel = MilestoneDetailPanel(
            self.ctx,
            self._milestone_ctrl,
            str(hito_id or ""),
            on_saved=self.refresh,
            entity_controller=self.entity_controller,
            relation_controller=self.relation_controller,
            chronology_controller=self._chronology_ctrl,
            project_getter=self._get_active_project,
            on_start_walk=(
                self.start_chronology_walk if self.chronology_walk_controller is not None else None
            ),
        )
        drawer.set_content(panel, title="Hito")
        drawer.open()

    # ── CRON: Modo Creación Cronológica ──────────────────────────────────
    def _start_or_continue_walk(self, hito_id: str) -> None:
        """CRON: desde el grafo cronológico. Si hay un recorrido activo, lo
        reabre/continúa; si no, abre la configuración para iniciar uno nuevo."""
        ctrl = self.chronology_walk_controller
        if ctrl is None:
            self.ctx.log("error", "Recorrido cronológico no disponible")
            return
        active = ctrl.active()
        if not isinstance(active, Error):
            # Hay un recorrido en curso → reabrir su ventana única y continuar.
            self._walk_session_id = active.value.id
            ctrl.resume(active.value.id)
            # Si el runner fue destruido al cerrar el cajón, se recrea y se
            # re-analiza el hito actual para repoblar la ventana.
            if not _qt_alive(self._walk_runner):
                self._walk_runner = None
                self._open_walk_runner()
                self._run_walk_step()
            else:
                self._focus_walk_runner()
            self.ctx.log("info", "Recorrido cronológico reanudado.")
            return
        self.start_chronology_walk(str(hito_id or ""))

    def start_chronology_walk(self, hito_id: str) -> None:
        """Abre el panel de configuración del recorrido para el hito dado."""
        drawer = getattr(self.ctx, "drawer", None)
        if self.chronology_walk_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo iniciar el recorrido cronológico")
            return
        from hosts.DesktopHostPySide.widgets.chronology_walk_config_panel import (
            ChronologyWalkConfigPanel,
        )

        title = ""
        for hito in self._milestone_ctrl.list_all() if self._milestone_ctrl else []:
            if str(getattr(hito, "id", "")) == str(hito_id):
                title = str(getattr(hito, "title", ""))
                break
        panel = ChronologyWalkConfigPanel(str(hito_id), start_title=title)
        panel.submitted.connect(self._on_walk_config_submitted)
        panel.cancelled.connect(lambda: drawer.close())
        drawer.set_content(panel, title="Creación cronológica")
        drawer.open()

    @_qt_safe_slot
    def _on_walk_config_submitted(self, cfg: dict) -> None:
        ctrl = self.chronology_walk_controller
        if ctrl is None:
            return
        res = ctrl.start(
            cfg.get("start_milestone_id", ""),
            cfg.get("direction"),
            cfg.get("mode"),
            cfg.get("depth"),
            cfg.get("aggressiveness"),
        )
        if isinstance(res, Error):
            self.ctx.log("error", res.error)
            return
        self._walk_session_id = res.value.id
        self._open_walk_runner()
        self._run_walk_step()

    def _open_walk_runner(self) -> None:
        drawer = getattr(self.ctx, "drawer", None)
        if drawer is None:
            return
        from hosts.DesktopHostPySide.widgets.chronology_walk_runner_panel import (
            ChronologyWalkRunnerPanel,
        )

        runner = ChronologyWalkRunnerPanel()
        runner.advanceRequested.connect(self._advance_walk)
        runner.stopRequested.connect(self._stop_walk)
        runner.decisionRequested.connect(self._decide_walk)
        runner.applyRequested.connect(self._on_walk_apply)
        # Si Qt destruye el runner (al cerrar/reemplazar el cajón), olvida la
        # referencia para que la re-entrada lo recree en vez de usar uno muerto.
        runner.destroyed.connect(self._on_walk_runner_destroyed)
        self._walk_runner = runner
        drawer.set_content(runner, title="Recorrido cronológico")
        drawer.open()

    def _on_walk_runner_destroyed(self, *_args) -> None:
        self._walk_runner = None

    def _focus_walk_runner(self) -> bool:
        """CRON: reabre/enfoca la ventana única del paso. True si el runner vive."""
        runner = self._walk_runner
        drawer = getattr(self.ctx, "drawer", None)
        if not _qt_alive(runner) or drawer is None:
            self._walk_runner = None
            return False
        drawer.set_content(runner, title="Recorrido cronológico")
        drawer.open()
        return True

    @_qt_safe_slot
    def _run_walk_step(self) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        # Guarda DETERMINISTA: no solapar análisis (flag, no isRunning() frágil).
        if self._walk_analyzing:
            self.ctx.log("info", "Análisis en curso; espera a que termine.")
            return
        self._walk_analyzing = True
        # Semillas transitorias: limpia las del paso anterior antes de analizar el nuevo.
        self._clear_walk_step_seeds()
        self._walk_step_candidate_ids = []
        # Hito actual (antes de analizar): la cámara se enfoca y emite un PULSO
        # sostenido desde su posición mientras la IA trabaja.
        active = ctrl.active()
        if not isinstance(active, Error):
            mid = str(getattr(active.value, "current_milestone_id", "") or "")
            if mid:
                try:
                    self.chrono.start_walk_pulse(mid)
                except Exception:  # noqa: BLE001 — la animación no es crítica
                    pass
        if _qt_alive(self._walk_runner):
            self._walk_runner.set_busy(True)
        # Análisis en hilo aparte para no congelar la UI durante la llamada al modelo.
        worker = _WalkStepWorker(ctrl, sid)
        worker.finishedOk.connect(self._on_walk_step_done)
        worker.failed.connect(self._on_walk_step_failed)
        worker.finished.connect(self._on_walk_worker_stopped)
        self._walk_step_worker = worker
        self._walk_workers.add(worker)  # keep-alive hasta que termine
        track_worker(worker)  # apagado ordenado al cerrar la app
        self._start_walk_watchdog()
        worker.start()

    def _start_walk_watchdog(self) -> None:
        """Arranca/reinicia el perro guardián del paso (single-shot)."""
        self._stop_walk_watchdog()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_walk_watchdog_timeout)
        timer.start(self._walk_watchdog_ms)
        self._walk_watchdog = timer

    def _stop_walk_watchdog(self) -> None:
        timer = self._walk_watchdog
        self._walk_watchdog = None
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:  # noqa: BLE001
                pass

    @_qt_safe_slot
    def _on_walk_watchdog_timeout(self) -> None:
        """La llamada al modelo no respondió a tiempo: recupera la UI sin colgar."""
        self._walk_watchdog = None
        if not self._walk_analyzing:
            return
        self._walk_analyzing = False
        try:
            self.chrono.stop_walk_pulse()
        except Exception:  # noqa: BLE001
            pass
        self.ctx.log(
            "warning",
            "El análisis del hito tardó demasiado y se canceló; pulsa 'Avanzar' o reinténtalo.",
        )
        if _qt_alive(self._walk_runner):
            self._walk_runner.set_busy(False)
            self._walk_runner.set_status(
                "El análisis tardó demasiado y se canceló. Reinténtalo o pulsa 'Avanzar'."
            )

    @_qt_safe_slot
    def _on_walk_step_done(self, result) -> None:
        self._walk_analyzing = False
        self._stop_walk_watchdog()
        try:
            self.chrono.stop_walk_pulse()
        except Exception:  # noqa: BLE001
            pass
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        result = dict(result or {})
        # Cámara: deja el hito centrado y resaltado (ya sin pulso).
        milestone_id = str((result.get("walk") or {}).get("milestone_id") or "")
        if milestone_id:
            try:
                self.chrono.center_on_milestone(milestone_id)
            except Exception:  # noqa: BLE001 — la cámara no es crítica
                pass
        # Stagea candidatos/diffs y los liga a la sesión.
        created = self._stage_walk_candidates(result)
        if created:
            ctrl.attach_candidates(sid, created)
            self._walk_step_candidate_ids = list(created)
        else:
            self._walk_step_candidate_ids = []
        if _qt_alive(self._walk_runner):
            self._walk_runner.set_busy(False)
            self._walk_runner.show_step(result)
            # Ventana única: tarjetas editables de TODOS los cambios del paso.
            self._walk_runner.set_changes(self._build_step_changes(self._walk_step_candidate_ids))
        # El análisis NO cambia canon (solo stagea): refresco LIGERO (solo cronología),
        # no el rebuild completo del grafo (evita congelación por paso).
        self._refresh_chrono_only()

    def _build_step_changes(self, candidate_ids: list[str]) -> list[dict]:
        """Descriptores editables (uno por candidato) para la ventana del paso."""
        project = self._get_active_project()
        by_id = {c.id: c for c in getattr(project, "candidates", []) or []}
        changes: list[dict] = []
        for cid in candidate_ids or []:
            cand = by_id.get(cid)
            if cand is None:
                continue
            pd = dict(getattr(cand, "proposed_data", None) or {})
            ctype = str(getattr(getattr(cand, "candidate_type", None), "value", "") or "")
            if ctype == "entidad":
                changes.append(
                    {
                        "candidate_id": cid,
                        "kind": "entity",
                        "apply": "flat",
                        "header": f"Nueva entidad: {pd.get('name', '')}",
                        "fields": [
                            {"key": "name", "label": "Nombre", "value": pd.get("name", "")},
                            {
                                "key": "brief_description",
                                "label": "Descripción",
                                "value": pd.get("brief_description", ""),
                                "multiline": True,
                            },
                        ],
                    }
                )
            elif ctype == "relacion":
                changes.append(
                    {
                        "candidate_id": cid,
                        "kind": "relation",
                        "apply": "flat",
                        "header": f"Relación: {pd.get('source_name', '?')} → {pd.get('target_name', '?')}",
                        "fields": [
                            {
                                "key": "relation_type",
                                "label": "Tipo",
                                "value": pd.get("relation_type", ""),
                            },
                            {
                                "key": "description",
                                "label": "Descripción",
                                "value": pd.get("description", ""),
                                "multiline": True,
                            },
                        ],
                    }
                )
            elif pd.get("kind") == "causal_milestone":
                m = dict(pd.get("milestone") or {})
                changes.append(
                    {
                        "candidate_id": cid,
                        "kind": "milestone",
                        "apply": "milestone",
                        "base": m,
                        "header": f"Nuevo hito: {m.get('title', '')}",
                        "fields": [
                            {"key": "title", "label": "Título", "value": m.get("title", "")},
                            {
                                "key": "year",
                                "label": "Año",
                                "value": "" if m.get("year") is None else str(m.get("year")),
                            },
                            {
                                "key": "rationale",
                                "label": "Cuerpo",
                                "value": m.get("rationale", ""),
                                "multiline": True,
                            },
                        ],
                    }
                )
            elif pd.get("edit_proposed_value"):
                changes.append(
                    {
                        "candidate_id": cid,
                        "kind": "edit",
                        "apply": "flat",
                        "header": str(getattr(cand, "title", None) or "Editar canon"),
                        "before": self._canon_before(project, pd),
                        "fields": [
                            {
                                "key": "edit_proposed_value",
                                "label": "Nuevo valor",
                                "value": pd.get("edit_proposed_value", ""),
                                "multiline": True,
                            },
                        ],
                    }
                )
            else:
                changes.append(
                    {
                        "candidate_id": cid,
                        "kind": "report",
                        "header": str(getattr(cand, "title", None) or "Lectura / informe"),
                        "before": str(pd.get("report") or ""),
                        "fields": [],
                    }
                )
        return changes

    @staticmethod
    def _canon_before(project, pd: dict) -> str:
        """Valor actual del canon para un diff de edición (mejor esfuerzo)."""
        kind = str(pd.get("edit_kind") or "entity_edits")
        target = str(pd.get("edit_target_name") or "").strip().lower()
        if kind in ("entity_edits", "entity"):
            for e in getattr(project, "entities", []) or []:
                if str(getattr(e, "name", "")).strip().lower() == target:
                    return str(getattr(e, "brief_description", "") or getattr(e, "body", "") or "")
        if kind == "milestone_edits":
            for m in getattr(project, "causal_milestones", []) or []:
                if str(getattr(m, "title", "")).strip().lower() == target:
                    return str(getattr(m, "description", "") or getattr(m, "rationale", "") or "")
        return ""

    @_qt_safe_slot
    def _on_walk_apply(self, items: list) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        # No aplicar mientras un análisis sigue vivo (evita mutar el proyecto desde
        # el hilo de UI a la vez que el worker lo toca).
        if self._walk_analyzing:
            if _qt_alive(self._walk_runner):
                self._walk_runner.set_status("Espera a que termine el análisis para aplicar.")
            return
        res = ctrl.apply_step(sid, list(items or []))
        if isinstance(res, Error):
            self.ctx.log("error", res.error)
            return
        applied = res.value.get("applied") or []
        failed = res.value.get("failed") or []
        # Semillas transitorias por paso: aplicar resuelve el paso → se retiran TODAS
        # las del paso (aplicadas + las que el usuario dejó sin marcar).
        self._clear_walk_step_seeds()
        if applied:
            self._zen_bell.play_one()
        for fail in failed:
            self.ctx.log("warning", f"No se pudo aplicar: {fail.get('error', '')}")
        if _qt_alive(self._walk_runner):
            self._walk_runner.mark_applied(len(applied))
        # Aplicar SÍ cambia canon → refresco completo (grafo + cronología).
        self._refresh_after_walk()

    @_qt_safe_slot
    def _on_walk_step_failed(self, error: str) -> None:
        self._walk_analyzing = False
        self._stop_walk_watchdog()
        try:
            self.chrono.stop_walk_pulse()
        except Exception:  # noqa: BLE001
            pass
        self.ctx.log("error", str(error))
        if _qt_alive(self._walk_runner):
            self._walk_runner.set_busy(False)

    @_qt_safe_slot
    def _on_walk_worker_stopped(self) -> None:
        # Descarta los workers ya terminados del conjunto keep-alive.
        self._walk_workers = {w for w in self._walk_workers if _qt_alive(w) and w.isRunning()}
        worker = getattr(self, "_walk_step_worker", None)
        if worker is not None and (not _qt_alive(worker) or not worker.isRunning()):
            self._walk_step_worker = None

    def _stage_walk_candidates(self, result: dict) -> list[str]:
        """Crea los candidatos/diffs del paso para la VENTANA ÚNICA.

        Durante un recorrido NO se crean semillas doradas (decisión del usuario):
        la revisión/aplicación es solo por la ventana única (atómica). Se marcan
        con ``walk_session_id`` para que la rehidratación no genere semillas.
        """
        controller = getattr(self.candidate_view, "cc", None)
        candidates = (result or {}).get("candidates") or []
        created: list[str] = []
        if controller is None:
            return created
        for data in candidates:
            data = dict(data)
            meta = dict(data.get("metadata") or {})
            meta["walk_session_id"] = str(self._walk_session_id or "")
            data["metadata"] = meta
            res = controller.create(data)
            if isinstance(res, Error):
                self.ctx.log("error", res.error)
                continue
            candidate = getattr(res, "value", None)
            cid = str(getattr(candidate, "id", "") or "")
            if not cid:
                continue
            created.append(cid)  # solo va a la ventana única, sin semilla dorada
        if created:
            self._zen_bell.play_one()  # campana = "cambios listos para revisar"
        return created

    def _clear_walk_step_seeds(self) -> None:
        """CRON: retira las semillas del paso actual (transitorias por paso)."""
        for cid in self._walk_step_candidate_ids or []:
            try:
                self._seed_notifications.remove(str(cid))
            except Exception:  # noqa: BLE001
                pass

    def _advance_walk(self) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        if self._walk_analyzing:
            self.ctx.log("info", "Análisis en curso; espera a que termine.")
            return
        res = ctrl.advance(sid)
        if isinstance(res, Error):
            self.ctx.log("warning", res.error)
            if _qt_alive(self._walk_runner):
                self._walk_runner.set_status(res.error)
            return
        session = res.value
        status = str(getattr(getattr(session, "status", ""), "value", "") or "")
        if status == "completed":
            self._open_walk_report(sid)
            return
        self._run_walk_step()

    def _decide_walk(self, decision: str) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        res = ctrl.decide(sid, str(decision))
        if isinstance(res, Error):
            self.ctx.log("warning", res.error)
            return
        self.ctx.log("info", "Decisión registrada; puedes avanzar.")

    def _stop_walk(self) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        res = ctrl.stop(sid)
        if isinstance(res, Error):
            self.ctx.log("warning", res.error)
            return
        self._open_walk_report(sid)

    def _open_walk_report(self, session_id: str) -> None:
        ctrl = self.chronology_walk_controller
        drawer = getattr(self.ctx, "drawer", None)
        if ctrl is None or drawer is None:
            return
        project = self._get_active_project()
        report = None
        for rep in getattr(project, "chronology_walk_reports", []) or []:
            if str(getattr(rep, "session_id", "")) == str(session_id):
                report = rep
        if report is None:
            return
        from hosts.DesktopHostPySide.widgets.chronology_walk_report_view import (
            ChronologyWalkReportView,
        )

        view = ChronologyWalkReportView()
        view.show_report(report)
        view.closed.connect(lambda: drawer.close())
        # Cierre del recorrido: retira las semillas del último paso y el resalte.
        self._clear_walk_step_seeds()
        self._walk_step_candidate_ids = []
        self._walk_session_id = None
        self._walk_runner = None
        self._walk_analyzing = False
        self._stop_walk_watchdog()
        try:
            self.chrono.clear_walk_highlight()
        except Exception:  # noqa: BLE001
            pass
        drawer.set_content(view, title="Informe de recorrido")
        drawer.open()

    @_qt_safe_slot
    def _refresh_chrono_only(self) -> None:
        """CRON: refresco LIGERO tras un análisis (no cambia canon): reconstruye
        solo el grafo cronológico y re-enfoca el hito actual. Evita el rebuild
        completo del grafo concéntrico por cada paso (causa de congelación)."""
        try:
            self.chrono.set_project(self._get_active_project())
            if self._walk_session_id and self.chronology_walk_controller is not None:
                active = self.chronology_walk_controller.active()
                if not isinstance(active, Error):
                    mid = str(getattr(active.value, "current_milestone_id", "") or "")
                    if mid:
                        self.chrono.center_on_milestone(mid)
        except Exception:  # noqa: BLE001 — el refresco no es crítico
            pass

    @_qt_safe_slot
    def _refresh_after_walk(self) -> None:
        # Refresco COMPLETO (tras aplicar: canon cambió). Incluye grafo, semillas
        # y cronología; re-enfoca el hito actual para mantener el contexto.
        try:
            self._on_suggestion_changed()
        except Exception:  # noqa: BLE001
            pass
        self._refresh_chrono_only()

    def _open_panel_for_entity(self, entity_id: str):
        """BETA1-G04: doble click en una cabeza de línea de vida → su panel
        editorial (hoja u rama), coherente con la vista concéntrica."""
        project = self._get_active_project()
        for entity in getattr(project, "entities", []) or []:
            if str(getattr(entity, "id", "")) != str(entity_id):
                continue
            kind = str(
                getattr(
                    getattr(entity, "entity_type", None),
                    "value",
                    getattr(entity, "entity_type", ""),
                )
                or ""
            ).lower()
            if kind == "contenedor":
                self._open_tree_panel(entity_id)
            else:
                self._open_node_panel(entity_id)
            return

    def _on_chrono_create_milestone(self, default_year: int, era_name: str) -> None:
        """BETA1-HITO-MULTI: clic derecho sobre una era en la cronología →
        muestra el panel de creación como overlay DENTRO de la app (ModalOverlay,
        no una ventana del SO). Al confirmar, crea el hito por el controller."""
        if self._milestone_ctrl is None:
            return
        chrono_meta = {}
        chron = getattr(self._get_active_project(), "project_chronology", None)
        cal = getattr(chron, "metadata", None)
        if isinstance(cal, dict):
            chrono_meta = cal
        panel = MilestoneQuickCreatePanel(
            default_year=int(default_year),
            calendar_meta=chrono_meta,
            era_name=str(era_name or ""),
        )
        overlay = getattr(self.window(), "modal_overlay", None)
        if overlay is None:  # respaldo defensivo: crea con el año sugerido
            self._create_milestone_from_payload({"title": "Nuevo hito", "year": int(default_year)})
            return
        panel.cancelled.connect(overlay.dismiss)
        panel.submitted.connect(
            lambda payload: (overlay.dismiss(), self._create_milestone_from_payload(payload))
        )
        overlay.open_widget(panel)

    @_qt_safe_slot
    def _create_milestone_from_payload(self, payload: dict) -> None:
        """Crea el hito por el controller (la UI nunca escribe persistencia
        directa), lo hace germinar y refresca. Nace como candidato revisable."""
        if self._milestone_ctrl is None:
            return
        result = self._milestone_ctrl.create_manual(dict(payload or {}))
        if isinstance(result, Error):
            self.ctx.log("warning", result.error)
            return
        created = getattr(result, "value", None)
        milestone_id = str(getattr(created, "id", "") or "")

        # Diferido: refrescar reconstruye la escena cronológica (scene.clear());
        # hacerlo en el mismo ciclo del clic sería un use-after-free. Germina al
        # siguiente ciclo del event loop.
        def _after():
            self.refresh()
            if milestone_id:
                chrono = getattr(self, "chrono", None)
                if chrono is not None and hasattr(chrono, "bloom_milestone"):
                    chrono.bloom_milestone(milestone_id)

        _qt_safe_timer(self, 0, _after)

    def _on_chrono_link_entity(self, milestone_id: str, entity_id: str) -> None:
        """BETA1-HITO-MULTI: clic en un cruce 'fantasma' → vincula la entidad al
        hito (la añade a affected_entity_ids) por el controller, germina y
        refresca. Desvincular se hace desde el panel de edición del hito."""
        if self._milestone_ctrl is None or not milestone_id or not entity_id:
            return
        hito = next(
            (
                h
                for h in self._milestone_ctrl.list_all()
                if str(getattr(h, "id", "")) == str(milestone_id)
            ),
            None,
        )
        if hito is None:
            return
        affected = [str(v) for v in (getattr(hito, "affected_entity_ids", []) or []) if str(v)]
        if str(entity_id) in affected:
            return  # ya vinculada
        affected.append(str(entity_id))
        result = self._milestone_ctrl.update(str(milestone_id), {"affected_entity_ids": affected})
        if isinstance(result, Error):
            self.ctx.log("warning", result.error)
            return

        def _after():
            self.refresh()
            chrono = getattr(self, "chrono", None)
            if chrono is not None and hasattr(chrono, "bloom_milestone"):
                chrono.bloom_milestone(str(milestone_id))

        _qt_safe_timer(self, 0, _after)

    def _on_lifespan_edited(self, entity_id: str, birth_year: int, death_year) -> None:
        """BETA1-UX2C: el usuario estiró el nodo en la cronología. Persistimos el
        nuevo lapso por el controller (la UI nunca escribe persistencia directa) y
        refrescamos para que el panel de detalle muestre el lapso derivado."""
        controller = getattr(self, "entity_controller", None)
        if controller is None:
            return
        payload = {
            "birth_year": int(birth_year),
            "death_year": None if death_year is None else int(death_year),
        }
        result = controller.update(str(entity_id), payload)
        if isinstance(result, Error):
            self.ctx.log("warning", result.error)
            return
        # BETA1-UX2D (crash): refresh() reconstruye la escena cronológica
        # (scene.clear()). Esta señal se emite DENTRO del mouseReleaseEvent de la
        # cronología, así que borrar aquí los items —incluido el que Qt está
        # entregando el evento— es un use-after-free (la línea "desaparece" y al
        # volver a la vista crashea). Se difiere al siguiente ciclo del event loop,
        # cuando el evento ya se ha desenrollado por completo.
        _qt_safe_timer(self, 0, self.refresh)

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
        for icon_name, tip, callback in actions:
            button = QPushButton()
            button.setToolTip(tip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(40, 40)
            button.setStyleSheet(
                f"QPushButton {{ background: {GOLD}; border: none; border-radius: 20px; }} "
                f"QPushButton:hover {{ background: {GOLD_DEEP}; }} "
                f"QPushButton:pressed {{ background: #5E5427; }}"
            )
            icons.set_button_icon(button, icon_name, color="#FCF8EC", size=19)
            button.clicked.connect(callback)
            row.addWidget(button)
        cluster.adjustSize()
        cluster.raise_()
        return cluster

    @_qt_safe_slot
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
        # BETA2-FOCO: barra superior de modos (Foco | Mapa | Cronología),
        # anclada arriba-centro (spec "barra superior"; antes flotaba junto a
        # la command bar como alternador binario).
        toggle = getattr(self, "_float_view_toggle", None)
        if toggle is not None:
            toggle.adjustSize()
            toggle.move((self.width() - toggle.width()) // 2, 14)
            toggle.raise_()
        focus = getattr(self, "_float_focus", None)
        if focus is not None and focus.isVisible():
            focus.adjustSize()
            focus.move(18, 14)
            focus.raise_()
        # BETA1-L02b: barra de búsqueda flotante, centrada arriba.
        search = getattr(self, "_float_search", None)
        if search is not None and search.isVisible():
            search.adjustSize()
            search.move((self.width() - search.width()) // 2, 14)
            search.raise_()
        # SEM04: la capa de semillas se ancla encima del cluster derecho.
        self._position_seed_layer()

    @_qt_safe_slot
    def _position_seed_layer(self):
        """SEM04: ancla las notificaciones de semilla JUSTO ENCIMA del cluster
        de botones derecho (con z-order por encima), para que no los solapen ni
        intercepten sus clics."""
        layer = getattr(self, "_seed_notifications", None)
        if layer is None or not layer.notifications:
            return
        layer.adjustSize()
        right = getattr(self, "_float_right", None)
        margin = 18
        if right is not None:
            x = right.x() + right.width() - layer.width()
            y = right.y() - layer.height() - 10
        else:
            bar = getattr(self, "_command_bar", None)
            top = (bar.y() - 66) if bar is not None else (self.height() - 134)
            x = self.width() - layer.width() - margin
            y = top - layer.height() - 10
        layer.move(max(0, x), max(0, y))
        layer.reanchor()  # show + raise por encima de los clusters

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._position_floats()
        # UX3: onboarding de 1ª vez del flujo IA (diferido para que haya geometría;
        # Qt omite el callback si el widget se destruye antes de dispararse).
        QTimer.singleShot(0, self._maybe_show_ai_coachmark)

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

    # Alto fijo de la command bar inferior. Lo usa MainWindow para reservar ese
    # margen al fondo y que los cajones overlay terminen JUSTO encima de la barra
    # (en vez de taparla). Constante compartida → sin número mágico duplicado.
    COMMAND_BAR_HEIGHT = 68

    def _build_command_bar(self) -> QWidget:
        """Bottom B38 contextual AI command bar. Creates jobs, never mutates canon."""
        bar = QFrame()
        bar.setObjectName("aiCommandBar")
        bar.setStyleSheet(
            f"QFrame#aiCommandBar {{ background: {SURFACE_HI}; border-top: 1px solid {LINE}; }}"
        )
        bar.setFixedHeight(self.COMMAND_BAR_HEIGHT)
        # BETA1-UX2B: la barra siempre ocupa todo el ancho (no encoge al cerrar un
        # drawer). Márgenes laterales más contenidos para dar aire al campo.
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # BETA1-G08: separación por borde + superficie sólida (sin efecto
        # gráfico, que cacheaba el render y ocultaba botones al actualizar).
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(44, 11, 44, 11)
        layout.setSpacing(10)

        prompt_label = QLabel("Dendro")
        prompt_label.setStyleSheet(
            f"color: {GOLD_DEEP}; font-size: 12px; font-weight: 700; letter-spacing: 0.4px; "
            f"background: transparent; border: none; padding-right: 4px;"
        )
        prompt_label.setToolTip(
            "Las respuestas IA son candidatas revisables; no cambian canon automáticamente."
        )
        layout.addWidget(prompt_label)

        # BETA1-UX2B: botón "?" que explica el sistema de prompts (no es intuitivo).
        self._prompt_help_btn = QPushButton("?")
        self._prompt_help_btn.setObjectName("promptHelpBtn")
        self._prompt_help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prompt_help_btn.setFixedSize(22, 22)
        self._prompt_help_btn.setToolTip("Cómo funcionan los prompts de Dendro")
        self._prompt_help_btn.setStyleSheet(
            f"QPushButton#promptHelpBtn {{ background: {GOLD_TINT}; color: {GOLD_DEEP}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 11px; font-size: 12px; "
            f"font-weight: 700; }} "
            f"QPushButton#promptHelpBtn:hover {{ background: {GOLD_SOFT}; color: {INK_STRONG}; }}"
        )
        self._prompt_help_btn.clicked.connect(self._open_prompt_help)
        layout.addWidget(self._prompt_help_btn)

        # Deterministic intent: two selectors replace the keyword classifier.
        # Selector 1 (Acción) drives Selector 2 (Ámbito).
        self._build_intent_selectors()
        layout.addWidget(self._action_selector)
        layout.addWidget(self._scope_selector)
        # UX3: caption "Cuántas" bajo el stepper para que se entienda qué controla.
        self._count_spin_box = self._captioned_tuner(self._count_spin, "Cuántas")
        layout.addWidget(self._count_spin_box)
        layout.addWidget(self._captioned_tuner(self._temp_tuner, "Creatividad"))
        layout.addWidget(self._captioned_tuner(self._tokens_tuner, "Longitud respuesta"))
        layout.addWidget(self._captioned_tuner(self._budget_tuner, "Contexto"))

        self._command_input = QLineEdit()
        self._command_input.setObjectName("aiCommandInput")
        self._command_input.setPlaceholderText(
            "Describe qué quieres… usa @ para referenciar una entidad o hito"
        )
        self._command_input.setToolTip(
            "La acción y el ámbito los eliges en los dos selectores de la izquierda.\n"
            "Escribe @ para referenciar una entidad o hito existente (máx 2) — aparece un autocompletado.\n"
            "Editar usa hasta 6 elementos seleccionados; Crear relación, hasta 6 pares.\n"
            "Crear con una rama seleccionada inserta la entidad dentro de ella; @ solo referencia (no inserta)."
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
        # BETA1-UX2B: mínimo razonable para que el campo NO colapse (la barra se
        # veía "enana") cuando se abre el drawer derecho y el ancho disponible baja.
        self._command_input.setMinimumWidth(200)
        layout.addWidget(self._command_input, 1)

        # UX3: vista previa del contexto antes de enviar (editable, no-modal).
        self._command_preview_btn = QPushButton("Vista previa")
        self._command_preview_btn.setToolTip(
            "Ver y ajustar qué contexto recibirá la IA antes de crear"
        )
        self._command_preview_btn.setStyleSheet(
            f"QPushButton {{ background: {SURFACE_HI}; color: {GOLD_DEEP}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 18px; min-width: 64px; "
            f"min-height: 36px; font-size: 12px; font-weight: 700; padding: 0 12px; }} "
            f"QPushButton:hover {{ background: {GOLD_SOFT}; color: {INK_STRONG}; }}"
        )
        self._command_preview_btn.clicked.connect(self._open_context_preview)
        layout.addWidget(self._command_preview_btn)

        # UX11: indicador de actividad orgánico, visible mientras hay trabajo de IA
        # en vuelo o se calcula la vista previa (puntos sin metáfora de semilla).
        self._busy_indicator = BusyIndicator(diameter=18)
        self._busy_indicator.set_period_ms(self.ctx.animation_duration(900))
        self._busy_indicator.setToolTip("Dendro está trabajando…")
        layout.addWidget(self._busy_indicator)

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

        self._job_status_label = QLabel("")
        self._job_status_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        self._job_status_label.setToolTip(
            "Estado de las tareas IA. Todo resultado queda pendiente de revisión."
        )
        # BETA1-UX2B: el label ya no muestra texto persistente ("Sin tareas IA…")
        # ni reserva 190px; queda vacío en reposo y solo muestra avisos transitorios.
        layout.addWidget(self._job_status_label)
        return bar

    def _open_prompt_help(self) -> None:
        """BETA1-UX2B: popover que explica, de un vistazo, cómo se usan los
        prompts (no es intuitivo). Se cierra al hacer clic fuera (Qt.Popup)."""
        pop = QFrame(self, Qt.WindowType.Popup)
        pop.setObjectName("promptHelpPopover")
        pop.setStyleSheet(
            f"QFrame#promptHelpPopover {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 12px; }}"
        )
        col = QVBoxLayout(pop)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(8)
        title = QLabel("Cómo funcionan los prompts de Dendro")
        title.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 14px; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        col.addWidget(title)
        body = QLabel(
            "<b>1 · Acción × Ámbito.</b> Elige en los dos selectores QUÉ hace la IA "
            "(Crear, Editar, Analizar, Explicar, Expandir) y SOBRE QUÉ (Hoja, Rama, "
            "Relación, Anillo, Hito). Si la acción no usa ámbito, el 2º selector se oculta.<br>"
            "<b>2 · Tu texto.</b> Describe el matiz que quieres. Escribe <b>@</b> para "
            "referenciar una entidad o hito existente (hasta 2).<br>"
            "<b>3 · Selección.</b> Editar/Analizar usan lo que tengas seleccionado en el "
            "grafo (hasta 6 elementos). Al <b>crear una rama</b>, las entidades seleccionadas "
            "se <b>insertan dentro de ella</b> como miembros; al <b>crear una entidad</b> con "
            "una <b>rama seleccionada</b>, la entidad nace <b>dentro de esa rama</b>. Para solo "
            "<b>referenciar</b> algo sin insertarlo, usa <b>@</b>.<br>"
            "<b>4 · Diales.</b> Creatividad, longitud y contexto van en <i>Auto</i> "
            "(recomendado de la tarea). Arrástralos o haz clic para fijar un número exacto; "
            "doble clic vuelve a Auto.<br>"
            "<b>Importante:</b> toda salida es un <b>candidato revisable</b> que germina como "
            "semilla — nunca cambia el canon por sí sola."
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setMaximumWidth(440)
        body.setStyleSheet(f"color: {INK}; font-size: 12px; background: transparent; border: none;")
        col.addWidget(body)
        # Ejemplo en vivo para la celda Acción×Ámbito seleccionada ahora mismo.
        example = example_for_command(
            self._action_selector.currentData(), self._scope_selector.currentData()
        )
        hint = QLabel(f"Ejemplo para lo que tienes elegido:<br><i>«{example}»</i>")
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setMaximumWidth(440)
        hint.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        col.addWidget(hint)
        pop.adjustSize()
        btn = self._prompt_help_btn
        top_left = btn.mapToGlobal(btn.rect().topLeft())
        pop.move(top_left.x(), top_left.y() - pop.height() - 8)
        pop.show()
        self._prompt_help_popover = pop  # mantener referencia viva

    # -- UX3: coachmark de 1ª vez (onboarding ligero del flujo IA) -----------

    _AI_COACHMARK_KEY = "creation/ai_coachmark_seen"

    def _ai_coachmark_pending(self) -> bool:
        """True si el onboarding del flujo IA aún no se ha mostrado nunca."""
        try:
            seen = QSettings("Dendro", "DesktopHost").value(
                self._AI_COACHMARK_KEY, False, type=bool
            )
            return not bool(seen)
        except Exception:  # pragma: no cover - defensive (settings backend)
            return False

    def _mark_ai_coachmark_seen(self) -> None:
        try:
            QSettings("Dendro", "DesktopHost").setValue(self._AI_COACHMARK_KEY, True)
        except Exception:  # pragma: no cover - defensive
            pass

    def _ai_coachmark_steps(self) -> list[tuple[QWidget, str]]:
        """Pasos (widget ancla, texto) del onboarding, en orden."""
        return [
            (
                self._action_selector,
                "1 / 3 · Elige QUÉ hace la IA y SOBRE QUÉ con estos dos selectores.",
            ),
            (
                self._command_input,
                "2 / 3 · Describe el matiz. Escribe @ para referenciar una entidad o hito.",
            ),
            (
                self._command_preview_btn,
                "3 / 3 · Pulsa «Vista previa» para ver y ajustar el contexto antes de crear. "
                "Todo resultado es un candidato revisable.",
            ),
        ]

    @_qt_safe_slot
    def _maybe_show_ai_coachmark(self) -> None:
        if getattr(self, "_ai_coachmark_shown", False):
            return
        if not self.isVisible() or not self._ai_coachmark_pending():
            return
        self._ai_coachmark_shown = True
        self._show_ai_coachmark_step(0)

    def _show_ai_coachmark_step(self, index: int) -> None:
        steps = self._ai_coachmark_steps()
        if index >= len(steps):
            self._mark_ai_coachmark_seen()
            return
        anchor, text = steps[index]
        last = index == len(steps) - 1
        pop = QFrame(self, Qt.WindowType.Popup)
        pop.setObjectName("aiCoachmark")
        pop.setStyleSheet(
            f"QFrame#aiCoachmark {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 12px; }}"
        )
        col = QVBoxLayout(pop)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(10)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(320)
        label.setStyleSheet(
            f"color: {INK}; font-size: 12px; background: transparent; border: none;"
        )
        col.addWidget(label)
        btn = QPushButton("Entendido" if last else "Siguiente")
        btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; color: #FCF8EC; border: none; "
            f"border-radius: 14px; min-height: 28px; padding: 0 14px; "
            f"font-size: 12px; font-weight: 700; }} "
            f"QPushButton:hover {{ background: {GOLD_DEEP}; }}"
        )

        def _advance():
            pop.close()
            self._show_ai_coachmark_step(index + 1)

        btn.clicked.connect(_advance)
        col.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        pop.adjustSize()
        top_left = anchor.mapToGlobal(anchor.rect().topLeft())
        pop.move(top_left.x(), top_left.y() - pop.height() - 10)
        pop.show()
        self._ai_coachmark_popover = pop  # referencia viva del paso actual

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
            CommandAction.CREAR: (
                "Crea elementos nuevos del ámbito elegido. Hoja/Rama: hasta 3 "
                "sugerencias; Relación: 1 job por par (máx 6); Anillo: plantilla "
                "causal (sin selección)."
            ),
            CommandAction.EDITAR: (
                "Modifica descripción y cuerpo de lo seleccionado (máx 6). "
                "Referencia otra entidad o hito con @ (máx 2)."
            ),
            CommandAction.ANALIZAR: (
                "Analiza la coherencia de la selección o de todo el proyecto. "
                "Si excede 6 entidades, se trocea en análisis consecutivos."
            ),
            CommandAction.EXPLICAR: (
                "Razonamiento deductivo: crea hitos/entidades que expliquen la "
                "selección; con @ modifica el texto de las entidades referenciadas."
            ),
            CommandAction.EXPANDIR: "Inverso de Explicar: expande el worldbuilding a partir de la selección.",
        }
        self._action_tips = action_tips  # reusado por _populate_action_selector

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
        count = BotanicalSpinBox()
        count.setObjectName("aiSuggestionCount")
        count.setRange(1, 3)
        count.setValue(1)
        count.setPrefix("× ")
        count.setToolTip("Número de sugerencias a generar (máx 3)")
        count.setStyleSheet(
            f"QSpinBox {{ background: {SURFACE}; border: 1px solid {LINE}; "
            f"border-radius: 16px; padding: 5px 8px; font-size: 12px; color: {INK}; min-width: 96px; }} "
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
        tokens_tuner = RadialTuner(
            minimum=256, maximum=24000, value=2000, is_integer=True, auto=True
        )
        tokens_tuner.setToolTip(
            "LONGITUD DE RESPUESTA — cuántos tokens puede generar la IA (el largo "
            "de su respuesta).\n"
            "Auto = el máximo por defecto de esta tarea (número mostrado).\n"
            "Arrastra ↑/↓ para forzar; doble clic = volver a Auto.\n"
            "Más alto = respuestas más largas; más bajo = más cortas y rápidas."
        )
        budget_tuner = RadialTuner(
            minimum=2000, maximum=600000, value=24000, is_integer=True, auto=True
        )
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
        self._populate_action_selector()
        action.currentIndexChanged.connect(lambda _=0: self._refresh_scope_selector())
        scope.currentIndexChanged.connect(lambda _=0: self._on_function_changed())
        self._refresh_scope_selector()

    def _on_function_changed(self) -> None:
        self._update_count_visibility()
        self._update_scope_enabled()
        self._update_command_placeholder()
        self._sync_tuner_recommendations()

    def _update_command_placeholder(self) -> None:
        """Descubribilidad: el placeholder del input muestra un ejemplo de orden
        para la celda Acción×Ámbito actual (fuente única en command_expansion)."""
        field = getattr(self, "_command_input", None)
        if field is None:
            return
        action_value = self._action_selector.currentData()
        scope_value = self._scope_selector.currentData()
        example = example_for_command(action_value, scope_value)
        field.setPlaceholderText(f"Ej.: {example}  ·  usa @ para referenciar")

    def _update_scope_enabled(self) -> None:
        """BETA1-UX2B: el 2º selector (Ámbito) se OCULTA cuando la acción no lo
        usa (Analizar/Explicar/Expandir lo deciden por la selección, no por el
        ámbito), en vez de quedarse visible pero gris —que confundía—. También
        se oculta si la acción solo admite un ámbito (o ninguno)."""
        scope = getattr(self, "_scope_selector", None)
        if scope is None:
            return
        action_value = self._action_selector.currentData()
        scope_driven = action_value in (
            CommandAction.ANALIZAR.value,
            CommandAction.EXPLICAR.value,
            CommandAction.EXPANDIR.value,
        )
        try:
            scopes = valid_scopes_for_action(action_value)
        except ValueError:
            scopes = list(CommandScope)
        show = (not scope_driven) and len(scopes) > 1
        scope.setVisible(show)
        if show:
            scope.setToolTip("Sobre qué actúa la IA")

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

    def _populate_action_selector(self) -> None:
        """Rellena el selector de Acción con todas las acciones disponibles."""
        combo = getattr(self, "_action_selector", None)
        if combo is None:
            return
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        tips = getattr(self, "_action_tips", {})
        for act in CommandAction:
            idx = combo.count()
            combo.addItem(ACTION_LABELS[act], act.value)
            combo.setItemData(idx, tips.get(act, ""), Qt.ItemDataRole.ToolTipRole)
        if previous is not None:
            j = combo.findData(previous)
            if j >= 0:
                combo.setCurrentIndex(j)
        combo.blockSignals(False)

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
        # UX3: ocultar el contenedor con caption (no solo el stepper) para que la
        # etiqueta "Cuántas" no quede suelta cuando no aplica.
        box = getattr(self, "_count_spin_box", None)
        (box or spin).setVisible(visible)

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
            entities.append(
                {
                    "id": eid,
                    "name": str(getattr(e, "name", "")),
                    "display_type": str(getattr(e, "display_type", "") or ""),
                    "entity_type": _enum_value(e, "entity_type"),
                    "layer_ids": [str(x) for x in (getattr(e, "layer_ids", []) or [])],
                }
            )
        relations = []
        for r in getattr(project, "relations", []) or []:
            s, t = str(getattr(r, "source_id", "")), str(getattr(r, "target_id", ""))
            if s in selected and t in selected:
                relations.append(
                    {
                        "id": str(getattr(r, "id", "")),
                        "source_id": s,
                        "target_id": t,
                        "relation_type": _enum_value(r, "relation_type"),
                    }
                )
        ring_ids = {lid for ent in entities for lid in ent["layer_ids"]}
        rings = []
        for ring in getattr(project, "world_layers", []) or []:
            rid = str(getattr(ring, "id", ""))
            if rid in ring_ids:
                rings.append(
                    {
                        "id": rid,
                        "name": str(getattr(ring, "name", "")),
                        "order": int(getattr(ring, "order", 0) or 0),
                    }
                )
        milestones = []
        ctrl = getattr(self, "_milestone_ctrl", None)
        if ctrl is not None:
            try:
                for m in ctrl.list_all():
                    affected = {str(x) for x in (getattr(m, "affected_entity_ids", []) or [])}
                    layers = {str(x) for x in (getattr(m, "layer_ids", []) or [])}
                    if (affected & selected) or (layers & ring_ids):
                        milestones.append(
                            {
                                "id": str(getattr(m, "id", "")),
                                "title": str(getattr(m, "title", "")),
                                "layer_ids": list(layers),
                                "affected_entity_ids": list(affected),
                            }
                        )
            except Exception:
                pass
        return order_context_by_causality(
            entities=entities,
            relations=relations,
            rings=rings,
            milestones=milestones,
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
        fragment = before[at + 1 :]
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
        self.ctx.log(
            "info",
            "Para crear relación: arrastra desde un nodo o árbol hacia otro elemento del grafo.",
        )

    def _toggle_layer_drawer(self):
        _apptrace("WS toggle_layer_drawer")
        """Persistent explicit drawer: stays open until user toggles it again."""
        project = self._get_active_project()
        active = bool(project and getattr(project, "worldbuilding_active", False))
        if not active:
            self.ctx.log(
                "warning", "Activa Worldbuilding en el proyecto para usar anillos causales"
            )
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
        current = (
            str(getattr(canvas, "_layout_mode_active", "free")) if canvas is not None else "free"
        )
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
        layer_ids = tuple(
            getattr(
                getattr(self.graph, "canvas", None), "_visual_filter", VisualFilterState()
            ).layer_ids
        )
        focused_ring_id = (
            self.graph.focused_ring_id() if hasattr(self.graph, "focused_ring_id") else ""
        )
        # UX5c-fix: el anillo activo para crear/coherenciar entidades es el SELECCIONADO
        # (clic simple) o el enfocado (doble clic) — `active_ring_id()` ya resuelve esa
        # precedencia (override de menú > foco > selección). Antes el scope solo miraba
        # el ENFOCADO, así que una entidad creada sobre un anillo meramente seleccionado
        # nacía «sin anillo» y sin contexto temático del anillo (incoherente).
        active_ring_id = (
            self.graph.active_ring_id() if hasattr(self.graph, "active_ring_id") else ""
        )
        selected_entity_ids = self.graph.selected_entity_ids() if hasattr(self, "graph") else []
        selected_relation_ids = self.graph.selected_relation_ids() if hasattr(self, "graph") else []
        # Validate both ids still exist; a deleted/unfocused ring → empty, so it never
        # leaks into the payload nor the RAG query. focus_label sigue reflejando solo el
        # anillo ENFOCADO (breadcrumb de zoom), no la selección.
        ring_ids = (
            {str(getattr(wl, "id", "")) for wl in (getattr(project, "world_layers", []) or [])}
            if project is not None
            else set()
        )
        if active_ring_id and str(active_ring_id) not in ring_ids:
            active_ring_id = ""  # stale active ring on a layer that no longer exists
        focus_label = ""
        if focused_ring_id and str(focused_ring_id) in ring_ids:
            canvas = getattr(self.graph, "canvas", None)
            namer = getattr(canvas, "_ring_display_name", None)
            name = namer(focused_ring_id) if callable(namer) else ""
            focus_label = f"Anillo: {name}" if name else "Anillo enfocado"
        elif focused_ring_id:
            focused_ring_id = ""  # stale focus on a ring that no longer exists
        creative_brief = {}
        if project is not None:
            # PA04: la config por rama se eliminó; solo viaja el perfil creativo global.
            from packages.application.creative_context import project_creative_brief

            creative_brief = project_creative_brief(project)
        return {
            "project_id": str(getattr(project, "id", "")) if project is not None else "",
            "worldbuilding_active": bool(getattr(project, "worldbuilding_active", False))
            if project is not None
            else False,
            "selected_entity_ids": selected_entity_ids,
            "selected_relation_ids": selected_relation_ids,
            # F3.6: hitos activados en la vista cronológica persisten junto a la
            # selección del grafo y el prompt (command bar compartida).
            "selected_milestone_ids": list(getattr(self, "_chrono_context_hito_ids", []) or []),
            "active_layer_ids": list(layer_ids),
            "active_ring_id": active_ring_id,
            "focused_ring_id": focused_ring_id,
            "focus_label": focus_label,
            "visual_filters_active": self.graph.active_filter_count()
            if hasattr(self, "graph")
            else 0,
            "creative_brief": creative_brief,
            "creative_context": [],
            "branch_creative_context": [],
        }

    def _build_submit_scope_and_plan(self, prompt: str):
        """Arma el context_scope base (selección + tuners + packs) y el plan de
        jobs determinista. Único origen compartido por crear y previsualizar, para
        que la vista previa refleje exactamente lo que se enviará."""
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
            active_ring_id=str(
                base_scope.get("focused_ring_id") or base_scope.get("active_ring_id") or ""
            ),
        )
        return base_scope, plan

    def _submit_ai_command(self, *, exclusions: dict | None = None):
        _apptrace(f"WS submit_ai_command prompt={self._command_input.text().strip()[:60]}")
        prompt = self._command_input.text().strip()
        if not prompt:
            self._job_status_label.setText("Escribe una orden para Dendro")
            return
        # Deterministic expansion: the two selectors + selection + params decide
        # the job(s) — no keyword classification. plan_command_jobs handles the
        # per-cell behaviour (fan-out, ring-template guard, batching, count, @).
        base_scope, plan = self._build_submit_scope_and_plan(prompt)
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
            # UX3: exclusiones elegidas en la vista previa viajan con el job; el
            # ensamblador las aplica al ejecutar (misma fuente que la preview).
            if exclusions and (exclusions.get("sections") or exclusions.get("item_ids")):
                scope["preview_exclusions"] = exclusions
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
        self._job_status_label.setText(
            f"{n} jobs creados: {label}" if n > 1 else f"Job creado: {label}"
        )
        pulse_feedback(self._job_status_label)
        self._sync_jobs_indicator()
        self.ctx.log(
            "info",
            f"{n} job(s) IA creado(s): resultado revisable, sin cambios automáticos en canon",
        )
        self._open_prompt_trace_page()
        for jid in created_ids:
            self._start_ai_job_worker(jid)

    def _open_context_preview(self):
        """UX3: calcula y muestra la vista previa editable del contexto del primer
        job planificado. No crea ningún job; el cálculo va en un hilo ligero."""
        prompt = self._command_input.text().strip()
        if not prompt:
            self._job_status_label.setText("Escribe una orden para previsualizar")
            return
        base_scope, plan = self._build_submit_scope_and_plan(prompt)
        if plan.error:
            self._job_status_label.setText(plan.error)
            self.ctx.log("error", plan.error)
            return
        planned = plan.jobs[0]
        scope = dict(base_scope)
        scope.update(planned.context_overrides)
        self._enrich_mentions_in_scope(scope, self._get_active_project())
        self._job_status_label.setText("Calculando contexto…")
        if not hasattr(self, "_preview_workers"):
            self._preview_workers = set()
        worker = _ContextPreviewWorker(self.ai_job_service, planned.job_type, planned.prompt, scope)
        worker.ready.connect(self._on_context_preview_ready)
        worker.failed.connect(self._on_context_preview_failed)
        worker.finished.connect(
            lambda w=worker: self._preview_workers.discard(w) if _qt_alive(self) else None
        )
        worker.finished.connect(self._refresh_busy_indicator)
        self._preview_workers.add(worker)
        track_worker(worker)  # apagado ordenado al cerrar la app
        worker.start()
        self._refresh_busy_indicator()  # UX11: actividad visible al calcular preview

    def _on_context_preview_ready(self, preview: dict):
        from hosts.DesktopHostPySide.widgets.context_preview_panel import ContextPreviewPanel

        self._job_status_label.setText("")
        panel = ContextPreviewPanel(
            preview,
            on_apply=self._submit_with_preview_overrides,
            on_refresh=self._open_context_preview,
        )
        drawer = self.ctx.drawer
        if drawer is not None:
            drawer.set_content(panel, title="Vista previa de contexto")
            drawer.open()

    def _on_context_preview_failed(self, error: str):
        self._job_status_label.setText(f"No se pudo previsualizar: {error}")
        self.ctx.log("error", f"Vista previa de contexto fallida: {error}")

    def _submit_with_preview_overrides(self, excluded_sections: list, excluded_item_ids: list):
        """Crea el job aplicando las exclusiones marcadas en la vista previa."""
        exclusions = {
            "sections": list(excluded_sections or []),
            "item_ids": list(excluded_item_ids or []),
        }
        if self.ctx.drawer is not None:
            self.ctx.drawer.close()
        self._submit_ai_command(exclusions=exclusions)

    def _launch_toolbar_ai_job(
        self,
        prompt: str,
        status_text: str,
        job_type: "AIJobType | str",
        scope_override: dict | None = None,
    ) -> bool:
        project = self._get_active_project()
        if project is None:
            self.ctx.log("error", "No hay proyecto activo")
            return False
        scope = (
            dict(scope_override) if scope_override is not None else self._current_context_scope()
        )
        # Toolbar quick-actions carry an explicit intent; never classify text.
        result = self.ai_job_service.create_job(
            job_type, prompt, context_scope=scope, explicit=True
        )
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
        track_worker(worker)  # apagado ordenado al cerrar la app
        self._refresh_busy_indicator()  # UX11: actividad visible mientras corre
        # SEM04: planta una semilla germinante en el grafo si el job creará
        # candidatos (no para reportes ni jobs de texto inline).
        job_res = self.ai_job_service.get_job(job_id)
        if not isinstance(job_res, Error):
            jt = str(getattr(getattr(job_res.value, "type", ""), "value", "") or "")
            scope = getattr(job_res.value, "context_scope", {}) or {}
            if jt and jt not in _NO_SEED_JOB_TYPES:
                # SEM04: la semilla nace en la banda del anillo donde se crea
                # (mismo orden de precedencia que ai_jobs._first_active_layer).
                ring_id = (
                    scope.get("active_ring_id")
                    or scope.get("focused_ring_id")
                    or (scope.get("active_layer_ids") or [""])[0]
                )
                self.graph.plant_seed(job_id, str(ring_id or ""))
            # UX5: germina cada entidad seleccionada mientras corre el job de edición.
            if jt in _EDIT_JOB_TYPES:
                ids = [str(x) for x in (scope.get("selected_entity_ids") or []) if x]
                if ids:
                    if not hasattr(self, "_edit_germ_jobs"):
                        self._edit_germ_jobs = {}
                    self._edit_germ_jobs[job_id] = ids
                    try:
                        self.graph.start_node_germination(ids)
                    except Exception:  # noqa: BLE001 — la animación no es crítica
                        pass
        worker.start()

    def _stop_edit_germination(self, job_id: str) -> None:
        """UX5: detiene el latido de germinación de las entidades de un job de edición."""
        ids = getattr(self, "_edit_germ_jobs", {}).pop(job_id, None)
        if ids:
            try:
                self.graph.stop_node_germination(ids)
            except Exception:  # noqa: BLE001 — la animación no es crítica
                pass

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

    @_qt_safe_slot
    def _on_ai_job_status(self, job_id: str, status: str, message: str, progress: float):
        percent = int(max(0.0, min(1.0, progress)) * 100)
        self._job_status_label.setStyleSheet(
            "color: #6F6A42; font-size: 11px; background: transparent; border: none;"
        )
        self._job_status_label.setText(f"Dendro: {message} ({percent}%)")
        self._sync_jobs_indicator()
        self._refresh_ai_jobs_panel_if_open()
        self.graph.advance_seed(job_id, progress)  # SEM04: la semilla germina por fases

    @_qt_safe_slot
    def _on_ai_job_finished(self, job_id: str):
        result = self.ai_job_service.get_job(job_id)
        if isinstance(result, Error):
            self._job_status_label.setText(result.error)
            return
        job = result.value
        self._stop_edit_germination(job_id)  # UX5: cesa el latido de germinación
        self._job_status_label.setStyleSheet(
            "color: #58744A; font-size: 11px; background: transparent; border: none;"
        )
        self._job_status_label.setText(job.message or "Resultado listo")
        pulse_feedback(self._job_status_label)
        self._sync_jobs_indicator()
        self._refresh_ai_jobs_panel_if_open()
        # UX8: una reparación de coherencia NO crea semillas: abre el panel de cambios
        # concretos (antes→después) para revisar y aplicar a canon.
        jt = str(getattr(getattr(job, "type", ""), "value", "") or "")
        if jt == "repair_coherence":
            analysis_cid = getattr(self, "_repair_source_cid", {}).pop(job_id, "")
            self._open_repair_review(job, analysis_cid)
            return
        # PA-Semillas: auto-stage de candidatos + notificación palpitante por cada
        # uno + arpegio zen. Sin panel intermedio "Resultado IA".
        self._auto_stage_and_notify(job)

    @_qt_safe_slot
    def _auto_stage_and_notify(self, job):
        """Crea los candidatos del job, divide la semilla del grafo en N y notifica."""
        controller = getattr(self.candidate_view, "cc", None)
        result = getattr(job, "result", {}) or {}
        candidates = result.get("candidates") or []
        job_id = str(getattr(job, "id", "") or "")
        if controller is None or not candidates:
            # Jobs sin candidatos estructurales (reportes de coherencia/review):
            # la semilla se marchita; se informa por el log.
            if job_id:
                self.graph.wither_seed(job_id)
            self.ctx.log("info", job.message or "Resultado IA listo (sin candidatos)")
            return []
        created_ids: list[str] = []
        ring_ids: dict[str, str] = {}
        for data in candidates:
            res = controller.create(dict(data))
            if isinstance(res, Error):
                self.ctx.log("error", res.error)
                continue
            candidate = getattr(res, "value", None)
            cid = str(getattr(candidate, "id", "") or "")
            if not cid:
                continue
            label = str(getattr(candidate, "title", "") or "Candidato")
            self._seed_notifications.add(cid, label)
            created_ids.append(cid)
            # SEM04: anillo concreto del candidato (su layer) para colocar la
            # semilla-candidato en la banda correcta al dividir.
            layer = data.get("layer_id") or (data.get("layer_ids") or [""])[0]
            if layer:
                ring_ids[cid] = str(layer)
        if created_ids:
            # UX3: garantiza la última etapa (pre-floración) antes de partir, por si
            # el job terminó sin emitir un progreso final cercano a 1.0.
            if job_id:
                self.graph.advance_seed(job_id, 1.0)
            # SEM04: la semilla germinante se divide en N semillas-candidato en el
            # grafo (cada una en la banda de su anillo) + UNA campana suave.
            self.graph.split_seed(job_id, created_ids, ring_ids)
            self._zen_bell.play_one()
            self._on_suggestion_changed()
        elif job_id:
            self.graph.wither_seed(job_id)
        return created_ids

    @_qt_safe_slot
    def _on_ai_job_failed(self, job_id: str, error: str):
        self._stop_edit_germination(job_id)  # UX5: cesa el latido de germinación
        self._job_status_label.setText(f"Error: {error}")
        self._job_status_label.setStyleSheet("color: #C0392B; font-size: 11px; font-weight: 700;")
        pulse_feedback(self._job_status_label)
        self.ctx.log("error", f"Job IA fallido {job_id}: {error}")
        self._sync_jobs_indicator()
        self._refresh_ai_jobs_panel_if_open()
        # SEM04: la semilla germinante se marchita al fallar el job.
        self.graph.wither_seed(job_id)
        # PA-Semillas: notificación de error (se descarta al pulsarla).
        self._seed_notifications.add(f"error:{job_id}", f"Job fallido: {error}", kind="error")
        # K02/fila32: si el fallo es por falta de proveedor IA, ofrecer instrucciones
        # accionables (una vez por sesión, no en cada intento).
        if self.ai_job_service.provider_unconfigured() and not getattr(
            self, "_ai_config_hint_shown", False
        ):
            self._ai_config_hint_shown = True
            self._show_ai_config_help()
        # Clear error styling after 8 seconds so it doesn't persist forever
        QTimer.singleShot(8000, self._reset_job_status_style)

    def _show_ai_config_help(self) -> None:
        """fila 32: instrucciones accionables para configurar un proveedor de IA.
        Dendro funciona sin IA; estas funciones quedan inactivas hasta configurarla."""
        QMessageBox.information(
            self,
            "Configura la IA",
            "No hay un proveedor de IA configurado, así que Dendro no generará contenido.\n\n"
            "Define estas variables de entorno antes de abrir la app:\n"
            "  • NARRATIVE_AI_PROVIDER  (p. ej. openai)\n"
            "  • NARRATIVE_AI_BASE_URL  (URL del endpoint compatible)\n"
            "  • NARRATIVE_AI_API_KEY   (tu clave)\n"
            "  • NARRATIVE_AI_MODEL     (nombre del modelo)\n\n"
            "Opcional: NARRATIVE_AI_TIMEOUT (segundos).\n"
            "Dendro funciona sin IA; estas funciones quedan inactivas hasta configurarla.",
        )

    @_qt_safe_slot
    def _reset_job_status_style(self):
        self._job_status_label.setStyleSheet(
            f"color: {INK_OLIVE}; font-size: 11px; background: transparent; border: none;"
        )
        # Only reset text if it's still showing an error
        current = self._job_status_label.text()
        if current.startswith("Error:"):
            self._job_status_label.setText("")

    @_qt_safe_slot
    def _on_ai_worker_stopped(self):
        self._ai_workers = {
            jid: worker for jid, worker in self._ai_workers.items() if worker.isRunning()
        }
        self._sync_jobs_indicator()
        self._refresh_busy_indicator()

    @_qt_safe_slot
    def _refresh_busy_indicator(self):
        """UX11: muestra el indicador de actividad mientras hay trabajo de IA en
        vuelo (jobs o cálculo de vista previa); lo oculta cuando no queda nada.
        Fail-soft: la barra puede no existir aún (tests) o haberse destruido."""
        indicator = getattr(self, "_busy_indicator", None)
        if indicator is None:
            return
        busy = bool(getattr(self, "_ai_workers", None)) or bool(
            getattr(self, "_preview_workers", None)
        )
        try:
            if busy:
                indicator.start()
            else:
                indicator.stop()
        except RuntimeError:  # widget Qt ya destruido
            self._busy_indicator = None

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

    def _sync_jobs_indicator(self):
        btn = getattr(self, "_jobs_btn", None)
        if btn is None:
            return
        jobs = self.ai_job_service.list_jobs()
        active = [
            j
            for j in jobs
            if getattr(getattr(j, "status", ""), "value", getattr(j, "status", ""))
            in {
                "queued",
                "building_context",
                "planning",
                "waiting_for_model",
                "running",
                "postprocessing",
            }
        ]
        ready = [
            j
            for j in jobs
            if getattr(getattr(j, "status", ""), "value", getattr(j, "status", ""))
            == "ready_for_review"
        ]
        total = len(active) + len(ready)
        btn.setText(f"Tareas {total}" if total else "Tareas")

    # ── PA-Semillas: revisión por-candidato desde la notificación ──────────

    def _find_candidate(self, candidate_id: str):
        project = self._get_active_project()
        if project is None:
            return None
        for candidate in getattr(project, "candidates", []) or []:
            if str(getattr(candidate, "id", "")) == str(candidate_id):
                return candidate
        return None

    def _open_candidate_review(self, candidate_id: str):
        # CRON: durante un recorrido, la notificación de un candidato del paso
        # actual reabre la VENTANA ÚNICA (diffs editables + aplicación atómica),
        # no el panel por-candidato suelto (evita aceptación desordenada).
        if (
            self._walk_session_id
            and str(candidate_id) in (self._walk_step_candidate_ids or [])
            and self._focus_walk_runner()
        ):
            return
        candidate = self._find_candidate(candidate_id)
        controller = getattr(self.candidate_view, "cc", None)
        if candidate is None or controller is None:
            self.ctx.log("warning", "No se pudo abrir la revisión de la semilla")
            return
        panel = CandidateReviewPanel(
            candidate,
            controller,
            on_decision=self._on_candidate_decision,
            on_close=self._close_candidate_review,
            on_repair=self._repair_canon_from_analysis,
            log=self.ctx.log,
        )
        # SEM04-fix: el panel de revisión se abre CENTRADO (modal). Fallback al
        # cajón lateral si no hay modal_overlay disponible.
        modal = getattr(self.ctx, "modal_overlay", None)
        if modal is not None:
            modal.open_widget(panel)
            return
        drawer = self.ctx.drawer
        if drawer is not None:
            drawer.set_content(panel, title="Revisar semilla")
            drawer.open()
        else:
            self.ctx.log("warning", "No se pudo abrir la revisión de la semilla")

    def _close_candidate_review(self):
        # SEM04: cerrar la revisión SIN decidir — la semilla sigue pendiente, sin
        # bloom ni wither. Solo se cierra el modal (o el cajón, si era el fallback).
        modal = getattr(self.ctx, "modal_overlay", None)
        if modal is not None and getattr(modal, "is_open", False):
            try:
                modal.dismiss()
            except Exception:  # noqa: BLE001 — cerrar el modal no es crítico
                pass
        drawer = self.ctx.drawer
        if drawer is not None:
            try:
                drawer.close()
            except Exception:  # noqa: BLE001 — cerrar el cajón no es crítico
                pass

    def _repair_canon_from_analysis(self, analysis_cid: str):
        """UX8: lanza un job IA de REPARACIÓN a partir del informe de coherencia.

        El job devuelve cambios CONCRETOS (valores finales sobre canon), no
        sugerencias literales. Al terminar, `_on_ai_job_finished` abre el panel de
        reparación (antes→después). Si no hay proveedor IA, el job falla con un
        mensaje claro y no se produce nada (decisión: fallar claramente).
        """
        candidate = self._find_candidate(analysis_cid)
        if candidate is None:
            return
        proposed = dict(getattr(candidate, "proposed_data", {}) or {})
        scope = dict((getattr(candidate, "metadata", None) or {}).get("context_scope") or {})
        report = analysis_report_text(proposed) or str(proposed.get("report") or "")
        prompt = (
            "Repara las incoherencias del siguiente informe con cambios concretos "
            "sobre el canon actual:\n\n" + report
        )
        result = self.ai_job_service.create_job(
            AIJobType.REPAIR_COHERENCE, prompt, context_scope=scope, explicit=True
        )
        if isinstance(result, Error):
            self._job_status_label.setText(result.error)
            self.ctx.log("error", result.error)
            return
        job = result.value
        # Recordar el informe de origen para consumirlo cuando se apliquen cambios.
        if not hasattr(self, "_repair_source_cid"):
            self._repair_source_cid = {}
        self._repair_source_cid[job.id] = analysis_cid
        self._close_candidate_review()
        self._job_status_label.setText("Dendro: preparando reparación…")
        pulse_feedback(self._job_status_label)
        self._sync_jobs_indicator()
        self._start_ai_job_worker(job.id)

    def _open_repair_review(self, job, analysis_cid: str):
        """UX8: abre el panel de cambios concretos resueltos contra el canon actual."""
        project = self._get_active_project()
        result = getattr(job, "result", {}) or {}
        raw_changes = result.get("repair_changes") or []
        if project is None or not raw_changes:
            self.ctx.log("info", "La reparación no propuso cambios concretos sobre el canon")
            self._job_status_label.setText("Reparación sin cambios aplicables")
            return
        resolved = coherence_repair.resolve_repair_changes(raw_changes, project)
        panel = RepairReviewPanel(
            resolved,
            on_apply=lambda changes: self._apply_repair_changes(changes, analysis_cid),
            on_cancel=self._close_candidate_review,
            log=self.ctx.log,
        )
        modal = getattr(self.ctx, "modal_overlay", None)
        if modal is not None:
            modal.open_widget(panel)
            return
        drawer = self.ctx.drawer
        if drawer is not None:
            drawer.set_content(panel, title="Reparar coherencia")
            drawer.open()

    def _apply_repair_changes(self, changes: list, analysis_cid: str):
        """Aplica los cambios seleccionados a canon vía servicios (acción humana)."""
        controller = getattr(self.candidate_view, "cc", None)
        cs = getattr(controller, "cs", None) if controller else None
        # Mismo proyecto e idénticos servicios que usa la aceptación de candidatos:
        # entidades, relaciones e hitos quedan en la misma instancia de proyecto.
        project = getattr(controller, "ps", None).active_project if controller else None
        entity_service = getattr(cs, "entity_service", None) if cs else None
        relation_service = getattr(cs, "relation_service", None) if cs else None
        if project is None or entity_service is None or relation_service is None:
            self.ctx.log("error", "No se pudo aplicar la reparación (servicios no disponibles)")
            return
        applied = 0
        for change in changes:
            res = coherence_repair.apply_resolved_change(
                change,
                project=project,
                entity_service=entity_service,
                relation_service=relation_service,
            )
            if isinstance(res, Error):
                self.ctx.log("error", res.error)
                continue
            applied += 1
        if applied:
            # Consume el informe de origen (analítico: aceptar no toca canon).
            if controller is not None:
                controller.accept(analysis_cid)
            self._seed_notifications.remove(analysis_cid, withered=False)
            self._zen_bell.play_one()
            self.ctx.log("info", f"{applied} reparación(es) aplicada(s) al canon")
            # Persiste por la misma ruta que el resto del host y reconstruye el
            # grafo/cronología con el canon reparado (igual que aceptar un candidato).
            self._save_project_from_canvas()
        else:
            self.ctx.log("warning", "No se aplicó ninguna reparación")
        self._close_candidate_review()
        self._on_suggestion_changed()
        self._rehydrate_seed_notifications()

    @_qt_safe_slot
    def _on_candidate_decision(self, candidate_id: str, decision: str):
        # SEM02/UX33: la decisión florece (accept) o marchita (reject) la SEMILLA en su
        # posición viva; ya no se vuelve a florecer el nodo recién creado en otro punto.
        accepted = decision in ("accept", "edit_accept", "partial_accept")
        self._seed_notifications.remove(candidate_id, withered=not accepted)
        # SEM04: la semilla-candidato del grafo florece (accept) o se marchita (reject).
        if accepted:
            self.graph.bloom_seed(candidate_id)
        else:
            self.graph.wither_seed(candidate_id)
        # UX17: confirmación visible que sobrevive al cierre del cajón (toast).
        notify = getattr(self.ctx, "notify", None)
        if callable(notify):
            if accepted:
                notify("Candidato integrado al canon", "success")
            else:
                notify("Candidato descartado", "info")
        # SEM04-fix: cerrar el modal centrado (o el cajón, si era el fallback).
        modal = getattr(self.ctx, "modal_overlay", None)
        if modal is not None and getattr(modal, "is_open", False):
            try:
                modal.dismiss()
            except Exception:  # noqa: BLE001 — cerrar el modal no es crítico
                pass
        drawer = self.ctx.drawer
        if drawer is not None:
            try:
                drawer.close()
            except Exception:  # noqa: BLE001 — cerrar el drawer no es crítico
                pass
        # UX32: deja que el bloom (accept) / marchitado (reject) se vea DESDE la
        # posición viva de la semilla antes de reconstruir el grafo (que la retiraría).
        # El retraso = duración de la animación; con animación desactivada (o sin
        # contexto real, p. ej. tests) es inmediato y síncrono.
        anim = getattr(self.ctx, "animation_duration", None)
        delay = max(0, anim(360)) if callable(anim) else 0

        def _after_bloom():
            try:
                # UX33: la celebración ocurre SOLO en la semilla (bloom_seed/wither_seed,
                # ya disparados arriba en su posición viva). NO se vuelve a florecer el
                # nodo recién creado (era una segunda floración en otro punto).
                self._on_suggestion_changed()  # reconstruye el grafo/cronología con lo nuevo
            except Exception:  # noqa: BLE001 — el diferido nunca rompe el flujo
                pass

        if delay <= 0:
            _after_bloom()  # síncrono: sin animación, sin esperar al event loop
        else:
            QTimer.singleShot(delay, _after_bloom)

    @_qt_safe_slot
    def _germinate(self, meta: dict):
        # SEM03: dispara el glow de germinación según la familia del candidato.
        entity_id = str(meta.get("created_entity_id") or "")
        relation_id = str(meta.get("created_relation_id") or "")
        ring_id = str(meta.get("created_ring_id") or "")
        milestone_id = str(meta.get("created_milestone_id") or "")
        if entity_id and hasattr(self.graph, "bloom_node"):
            self.graph.bloom_node(entity_id)
        if relation_id and hasattr(self.graph, "bloom_relation"):
            self.graph.bloom_relation(relation_id)
        if ring_id and hasattr(self.graph, "bloom_ring"):
            self.graph.bloom_ring(ring_id)
        if milestone_id:
            chrono = getattr(self, "chrono", None)
            if chrono is not None and hasattr(chrono, "bloom_milestone"):
                chrono.bloom_milestone(milestone_id)
        # UX5: al aceptar una EDICIÓN, florece el elemento editado (no nace nada
        # nuevo, pero el usuario debe ver qué cambió en canon).
        edited_entity = str(meta.get("edited_entity_id") or "")
        if edited_entity and hasattr(self.graph, "bloom_node"):
            self.graph.bloom_node(edited_entity)
        edited_relation = str(meta.get("edited_relation_id") or "")
        if edited_relation and hasattr(self.graph, "bloom_relation"):
            self.graph.bloom_relation(edited_relation)
        edited_ring = str(meta.get("edited_ring_id") or "")
        if edited_ring and hasattr(self.graph, "bloom_ring"):
            self.graph.bloom_ring(edited_ring)
        edited_milestone = str(meta.get("edited_milestone_id") or "")
        if edited_milestone:
            chrono = getattr(self, "chrono", None)
            if chrono is not None and hasattr(chrono, "bloom_milestone"):
                chrono.bloom_milestone(edited_milestone)

    def resizeEvent(self, event):  # noqa: N802 (Qt API)
        # SEM04: antes había DOS resizeEvent en esta clase; el segundo ocultaba al
        # primero, así que _position_floats no corría al redimensionar (los clusters
        # y las semillas no se recolocaban). Unificados aquí.
        super().resizeEvent(event)
        self._position_floats()
        if hasattr(self, "_layer_flyout"):
            h = self.height() - 48 - 62  # top toolbar + command bar
            self._layer_flyout.setGeometry(0, 48, 260, max(h, 220))

    def _activate_layers_view(self):
        project = self._get_active_project()
        if project is None or not bool(getattr(project, "worldbuilding_active", False)):
            self.ctx.log(
                "warning", "La vista Anillos solo está disponible con Worldbuilding activado"
            )
            return
        self.ctx.log("info", "Vista Anillos causales activa")
        if hasattr(self.graph, "set_worldbuilding_active"):
            self.graph.set_worldbuilding_active(True)
        else:
            self.refresh()
        if hasattr(self, "_layer_flyout"):
            self._layer_flyout.update_toggle_state(True)
        # BETA1-UX8: activar capas reflowa el canvas (bandas); reposiciona floats.
        QTimer.singleShot(0, self._position_floats)

    def _deactivate_layers_view(self):
        """Switch back from layers band view to normal graph view."""
        if hasattr(self.graph, "set_worldbuilding_active"):
            self.graph.set_worldbuilding_active(False)
        else:
            self.refresh()
        if hasattr(self, "_layer_flyout"):
            self._layer_flyout.update_toggle_state(False)
        # BETA1-UX8: desactivar capas reflowa el canvas; reposiciona floats.
        QTimer.singleShot(0, self._position_floats)

    def _apply_layer_filter(self, layer_id: str):
        _apptrace(f"WS apply_layer_filter layer={layer_id[:40]}")
        """Filter the graph to show only nodes/edges in the selected causal layer."""
        from hosts.DesktopHostPySide.widgets.graph_canvas import VisualFilterState

        self.graph.canvas.apply_visual_filter(VisualFilterState(layer_ids=(layer_id,)))

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

    def _open_ring_panel(self):
        _apptrace("WS open_ring_panel")

        def _build():
            self._ring_panel = CreationRingPanel(self)
            return self._ring_panel

        self._toggle_float_panel("rings", _build, "Anillos")

    def _refresh_ring_panel(self):
        """Actualiza el resaltado del panel de anillos si está abierto (el foco
        pudo cambiar por teclado [/] o por los botones del breadcrumb)."""
        panel = getattr(self, "_ring_panel", None)
        if panel is not None:
            try:
                panel.refresh_highlight()
            except RuntimeError:
                self._ring_panel = None  # panel destruido al cerrar el drawer

    def _on_suggestion_changed(self):
        # SEM03: las semillas germinantes (notificaciones) sustituyen al
        # indicador/bandeja legacy; basta con refrescar.
        self.refresh()

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

    # ── BETA1-L02b: barra de búsqueda flotante (tecla 'd') ───────────────────

    def _open_search_overlay(self):
        """Muestra la barra de búsqueda flotante y le da el foco (no abre el drawer)."""
        bar = getattr(self, "_float_search", None)
        if bar is None:
            return
        bar.setVisible(True)
        self._position_floats()
        bar.focus_input()

    def _close_search_overlay(self):
        """Oculta la barra, cancela el salto pendiente y devuelve el foco al lienzo."""
        timer = getattr(self, "_search_nav_timer", None)
        if timer is not None:
            timer.stop()
        self._search_pending_item = None
        bar = getattr(self, "_float_search", None)
        if bar is not None:
            bar.setVisible(False)
        self.graph.focus_canvas()  # BETA1-L02c: foco a la vista interna, no al wrapper

    def _on_search_overlay_text(self, query: str):
        """BETA1-L02c: al teclear, refresca la lista al instante PERO difiere el salto
        (debounce). Así se puede escribir seguido sin que la navegación robe el foco;
        el enfoque ocurre tras una breve pausa."""
        items = self._unified_search(query)
        bar = getattr(self, "_float_search", None)
        if bar is not None:
            bar.set_results(items)
        self._search_pending_item = items[0] if items else None
        timer = getattr(self, "_search_nav_timer", None)
        if timer is not None:
            timer.start(_SEARCH_DEBOUNCE_MS)  # reinicia la cuenta en cada pulsación

    def _fire_search_nav(self):
        """BETA1-L02c: dispara el salto a la mejor coincidencia tras el debounce y
        devuelve el foco al campo (la navegación puede cambiar de vista y moverlo)."""
        item = getattr(self, "_search_pending_item", None)
        if item is not None:
            self._navigate_search_item(item)
        bar = getattr(self, "_float_search", None)
        if bar is not None and bar.isVisible():
            QTimer.singleShot(0, bar.search.setFocus)

    def _unified_search(self, query: str) -> list[dict]:
        """Búsqueda unificada para la barra flotante: entidades/ramas/relaciones/
        anillos del grafo (graph.search) + hitos de la cronología (filtrados por
        título). Devuelve una lista corta de dicts rankeados (coincidencia por
        prefijo de título primero). Datos efímeros derivados; nunca canon."""
        q = (query or "").strip()
        if not q:
            return []
        ql = q.lower()
        items: list[dict] = []
        for result in self.graph.search(q):
            items.append(
                {
                    "kind": "graph",
                    "id": result.item_id,
                    "title": result.title,
                    "type_label": result.type_label or result.category,
                    "payload": result,
                }
            )
        ctrl = getattr(self, "_milestone_ctrl", None)
        if ctrl is not None:
            for milestone in ctrl.list_all() or []:
                title = str(getattr(milestone, "title", "") or "")
                if ql in title.lower():
                    mtype = getattr(milestone, "milestone_type", None)
                    items.append(
                        {
                            "kind": "milestone",
                            "id": getattr(milestone, "id", ""),
                            "title": title,
                            "type_label": str(getattr(mtype, "value", "") or "Hito"),
                            "payload": milestone,
                        }
                    )

        def _rank(item: dict) -> tuple:
            title = item["title"].lower()
            return (not title.startswith(ql), len(title), title)

        items.sort(key=_rank)
        return items[:8]

    def _navigate_search_item(self, item: dict) -> bool:
        """Navega a un resultado de la barra. Grafo → asegura la vista concéntrica
        y enfoca (centra la cámara). Hito → cambia a cronología y lo centra. Solo
        cambia de vista si hace falta (evita parpadeo al teclear)."""
        if not item:
            return False
        if item["kind"] == "milestone":
            chrono = getattr(self, "chrono", None)
            if chrono is None:
                return False
            mid = item["id"]
            switching = getattr(self, "_active_view", "concentric") != "chrono"
            if switching:
                self.set_active_view("chrono")
            ok = self._center_chrono_milestone(mid)
            # BETA1-L02c: si la cronología ACABA de hacerse visible, su viewport aún
            # no tiene el tamaño final → el centrado síncrono no cae sobre el hito.
            # Re-centramos en el próximo ciclo, cuando el layout ya está hecho.
            if switching:
                QTimer.singleShot(0, lambda: self._center_chrono_milestone(mid))
            return ok
        if getattr(self, "_active_view", "concentric") != "concentric":
            self.set_active_view("concentric")
        return self.focus_search_result(item["payload"])

    def _center_chrono_milestone(self, milestone_id: str) -> bool:
        """BETA1-L02c: centra (y resalta) un hito en la cronología. Helper para poder
        re-centrar de forma diferida tras cambiar de vista."""
        chrono = getattr(self, "chrono", None)
        if chrono is None:
            return False
        return bool(chrono.center_on_milestone(milestone_id))

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
        self._refresh_ring_panel()  # BETA1-L02: resalta el anillo activo en el selector
        self.ctx.log("info", f"Vista enfocada de anillo activa: {display_name}")

    def _on_ring_focus_cleared(self):
        # BETA1-L02: se salió del foco de anillo → oculta breadcrumb y refresca panel.
        self._set_focus_breadcrumb("", active=False)
        self._refresh_ring_panel()

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
            name = str(
                getattr(
                    getattr(self.graph, "canvas", None), "_ring_display_name", lambda rid: "Anillo"
                )(ring_id)
            )
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
            self._set_focus_breadcrumb(
                f"Mostrando árbol: {self._entity_name(tree_id)}", active=True
            )
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
            button.setStyleSheet(
                self._toolbar_btn_style if has_selection else self._toolbar_disabled_style
            )
            button.setToolTip(
                f"Analizar coherencia: {n_e} nodo(s), {n_r} relacion(es)"
                if has_selection
                else "Selecciona nodos o relaciones para analizar coherencia"
            )

        for attr, base in (
            ("_suggest_entity_btn", "Sugerir hoja"),
            ("_suggest_branch_btn", "Sugerir rama"),
        ):
            btn = getattr(self, attr, None)
            if btn is not None and btn.isEnabled():
                btn.setToolTip(
                    f"{base} con IA (contexto: {n_e} nodo(s), {n_r} relacion(es) seleccionado(s))"
                    if has_selection
                    else f"{base} con IA (contexto: todo el proyecto)"
                )
        # D04 explicit enablement for actions born disabled.
        branch_btn = getattr(self, "_suggest_branch_btn", None)
        if branch_btn is not None:
            branch_btn.setToolTip(
                f"Sugerir rama con IA (contexto: {n_e} nodo(s), {n_r} relacion(es))"
                if has_selection
                else "Sugerir rama con IA (contexto: foco/anillo actual)"
            )
        relation_btn = getattr(self, "_suggest_relation_btn", None)
        if relation_btn is not None:
            can_suggest_relation = n_e >= 2 or n_r > 0
            relation_btn.setEnabled(can_suggest_relation)
            relation_btn.setStyleSheet(
                self._toolbar_btn_style if can_suggest_relation else self._toolbar_disabled_style
            )
            relation_btn.setToolTip(
                f"Sugerir relaciones con IA (contexto: {n_e} nodo(s), {n_r} relacion(es))"
                if can_suggest_relation
                else "Selecciona al menos dos hojas o una relacion para sugerir relaciones"
            )
        summary_btn = getattr(self, "_summary_btn", None)
        if summary_btn is not None:
            summary_btn.setEnabled(has_selection)
            summary_btn.setStyleSheet(
                self._toolbar_btn_style if has_selection else self._toolbar_disabled_style
            )
            summary_btn.setToolTip(
                f"Resumir seleccion con IA ({n_e} nodo(s), {n_r} relacion(es))"
                if has_selection
                else "Selecciona elementos para resumir con IA"
            )

        # Delete button: enabled when something is selected
        del_btn = getattr(self, "_delete_btn", None)
        if del_btn is not None:
            del_btn.setEnabled(has_selection)
            del_btn.setStyleSheet(
                self._toolbar_btn_style if has_selection else self._toolbar_disabled_style
            )
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
        self._launch_toolbar_ai_job(
            prompt,
            f"IA contextual sobre seleccion ({selection_hint})...",
            job_type_for_action(action),
        )

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
            self.ctx.log(
                "info", "Selecciona uno o varios nodos/relaciones para analizar coherencia"
            )
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
        track_worker(self._suggest_worker)  # apagado ordenado al cerrar la app
        self._suggest_worker.start()
        self.ctx.log("info", f"Consultando IA para sugerir hojas (contexto: {context_label})...")

    def _suggest_relation(self):
        """Ask AI to suggest missing relations. Uses graph selection as context if available."""
        sel_e = self.graph.selected_entity_ids()
        sel_r = self.graph.selected_relation_ids()
        if len(sel_e) < 2 and not sel_r:
            self.ctx.log(
                "info",
                "Selecciona al menos dos hojas o una relacion para sugerir relaciones con IA",
            )
            return
        prompt = (
            "Sugiere relaciones candidatas entre los elementos seleccionados. "
            "Usa endpoints reales del contexto si existen; si no, usa nombres. "
            "Devuelve solo candidatos de relacion revisables, sin modificar canon."
        )
        self._launch_toolbar_ai_job(
            prompt, "Sugiriendo relaciones IA...", AIJobType.SUGGEST_RELATIONS
        )
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
        self._suggest_rel_worker.finished.connect(
            lambda: self._on_suggest_done(
                "relación", "_suggest_relation_btn", "_suggest_rel_worker"
            )
        )
        track_worker(self._suggest_rel_worker)  # apagado ordenado al cerrar la app
        self._suggest_rel_worker.start()
        self.ctx.log(
            "info", f"Consultando IA para sugerir relaciones (contexto: {context_label})..."
        )

    @_qt_safe_slot
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
        # SEM03: refresh() rehidrata los nuevos candidatos como semillas
        # germinantes (notificaciones); ya no se abre la bandeja legacy.
        self.refresh()

    def _create_entity_on_graph(self) -> str:
        """Create a new entity, add node to graph center, open detail panel.

        Returns the new entity id ("" on failure) so callers like the
        BETA1-B01 context-menu composition can chain existing routes.
        """
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo crear hoja: servicio no disponible")
            return ""
        result = self.entity_controller.create(
            self._with_active_ring_payload(
                {
                    "name": "Nueva hoja",
                    "entity_type": "nota",
                    "brief_description": "",
                    "canon_state": "borrador",
                    "custom_metadata": {"_visual_draft": True},
                }
            )
        )
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
        result = self.entity_controller.create(
            self._with_active_ring_payload(
                {
                    "name": "Nueva rama",
                    "entity_type": "contenedor",
                    "brief_description": "",
                    "canon_state": "borrador",
                    "custom_metadata": {"_visual_draft": True},
                }
            )
        )
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
        payload = self._payload_in_tree_ring(
            tree_id,
            {
                "name": "Nueva hoja",
                "entity_type": "nota",
                "brief_description": "",
                "canon_state": "borrador",
                "custom_metadata": {"_visual_draft": True},
            },
        )
        entity_id = self._create_entity_with_payload(payload, open_panel=False)
        if entity_id and tree_id:
            self._assign_node_to_tree(entity_id, tree_id)
            self._open_node_panel(entity_id, is_new=True)

    def _create_subtree_in_tree(self, tree_id: str):
        """BETA1-B01 'Crear subrama': create tree + assign to parent tree."""
        payload = self._payload_in_tree_ring(
            tree_id,
            {
                "name": "Nueva rama",
                "entity_type": "contenedor",
                "brief_description": "",
                "canon_state": "borrador",
                "custom_metadata": {"_visual_draft": True},
            },
        )
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
        """BETA1-G03: 'Editar era' — nombre y límites via EraController.

        Las eras de CALENDARIO COMPLETO se derivan del calendario (viven en
        metadata.era_lengths) y NO tienen una Era de dominio que editar: su
        era_id llega vacío. Editarlas = abrir la configuración del calendario,
        que es donde se definen. (Antes el clic moría: EraEditPanel con id vacío
        no encontraba nada y, como esas bandas cubren todo el lienzo, el lienzo
        entero quedaba 'muerto' al clic — BETA1-UX8.)"""
        if self.ctx.drawer is None:
            return
        if not str(era_id or "").strip():
            if self._chronology_ctrl is None:
                self.ctx.log(
                    "info",
                    "Las eras de este proyecto se definen en la configuración del calendario",
                )
                return
            from hosts.DesktopHostPySide.widgets.chronology_config_panel import (
                ChronologyConfigPanel,
            )

            panel = ChronologyConfigPanel(
                self._chronology_ctrl, on_saved=self.refresh, compact=True
            )
            self.ctx.drawer.set_content(panel, title="Calendario y eras")
            self.ctx.drawer.open()
            return
        if self.era_controller is None:
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
        world_ids = {
            str(getattr(layer, "id", "")) for layer in (getattr(project, "world_layers", []) or [])
        }
        existing = [str(value) for value in (getattr(entity, "layer_ids", []) or []) if value]
        new_layer_ids = [ring_id] + [
            lid for lid in existing if lid not in world_ids and lid != ring_id
        ]
        result = self.entity_controller.update(entity_id, {"layer_ids": new_layer_ids})
        if isinstance(result, Error):
            self.ctx.log("error", f"Error moviendo al anillo: {result.error}")
            return
        for child_id in self._contained_descendant_ids(entity_id):
            child = self._entity_by_id(child_id)
            if child is None:
                continue
            child_existing = [
                str(value) for value in (getattr(child, "layer_ids", []) or []) if value
            ]
            child_layer_ids = [ring_id] + [
                lid for lid in child_existing if lid not in world_ids and lid != ring_id
            ]
            child_result = self.entity_controller.update(child_id, {"layer_ids": child_layer_ids})
            if isinstance(child_result, Error):
                self.ctx.log(
                    "error", f"Error moviendo contenido de rama al anillo: {child_result.error}"
                )
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

    def _open_milestone_chronology_view(
        self, target_kind: str = "", target_id: str = "", hito_id: str = ""
    ):
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
            endpoints = (
                [
                    str(getattr(relation, "source_id", "") or ""),
                    str(getattr(relation, "target_id", "") or ""),
                ]
                if relation is not None
                else []
            )
            scope["selected_entity_ids"] = [entity_id for entity_id in endpoints if entity_id]
        prompt = (
            "Sugiere un hito causal relacionado con la seleccion actual. "
            "Devuelve el resultado como candidato revisable, sin modificar canon. "
            "Incluye titulo, descripcion, justificacion, clave temporal narrativa y orden relativo si procede."
        )
        return self._launch_toolbar_ai_job(
            prompt,
            "Sugiriendo hito relacionado...",
            AIJobType.PROPOSE_MILESTONES,
            scope_override=scope,
        )

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
            self.ctx.log(
                "warning", "Selecciona hojas, relaciones o anillos para crear un hito explicativo"
            )
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
            self.ai_context_controller = AIContextController(
                project_service, ai_job_service=self.ai_job_service
            )
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
        for widget in [
            self.graph,
            self.corpus_view,
            self.relation_view,
            self.candidate_view,
            self.source_view,
            self.layer_view,
        ]:
            try:
                if widget is not None and hasattr(widget, "refresh"):
                    widget.refresh()
            except RuntimeError:
                continue
        # BETA1-G04: la cronológica se reconstruye solo si está activa
        if getattr(self, "_active_view", "concentric") == "chrono" and hasattr(self, "chrono"):
            self.chrono.set_project(self._get_active_project())
        # BETA2-FOCO: refrescar la Creación con proyecto activo entra en Foco
        # (vista principal), centrando la última entidad trabajada.
        if getattr(self, "foco", None) is not None and self._get_active_project() is not None:
            self.set_active_view("foco")
        self._load_project_budget_default()
        self._rehydrate_seed_notifications()  # SEM02: semillas pendientes al recargar

    @_qt_safe_slot
    def _rehydrate_seed_notifications(self):
        # SEM02/SEM04: al cargar/refrescar un proyecto, reconstruye las
        # notificaciones (esquina) Y las semillas-candidato (en el grafo) de los
        # candidatos pendientes de revisión (idempotente).
        layer = getattr(self, "_seed_notifications", None)
        controller = getattr(self.candidate_view, "cc", None)
        if layer is None or controller is None:
            return
        active_walk = str(getattr(self, "_walk_session_id", None) or "")
        pending_ids: list[str] = []
        for cand in controller.list_all():
            # SEM04-fix: solo germinan las verdaderamente PENDIENTES. POSPUESTO/
            # ARCHIVADO/FUSIONADO/REQUIERE_REVISION ya no aparecen como semillas.
            state = getattr(cand, "state", None)
            if str(getattr(state, "value", state)) != "pendiente":
                continue
            # CRON: los candidatos del recorrido activo NO germinan como semillas
            # (se revisan solo en la ventana única); evita el camino que rompe.
            cand_meta = getattr(cand, "metadata", None) or {}
            if active_walk and str(cand_meta.get("walk_session_id") or "") == active_walk:
                continue
            cid = str(getattr(cand, "id", "") or "")
            if not cid:
                continue
            pending_ids.append(cid)
            if not layer.has(cid):
                label = str(getattr(cand, "title", "") or "Candidato")
                layer.add(cid, label)
        self.graph.rehydrate_candidate_seeds(pending_ids)  # SEM04: semillas en el grafo

    def open_graph(self):
        """Graph is always visible - this is now a no-op."""
        pass

    def open_entity_create(self):
        drawer = self.ctx.drawer
        if self.entity_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear hoja: servicio no disponible")
            return
        ring_id = self._active_creation_ring_id()
        ring = (
            self.graph.ring_visual_by_id(ring_id)
            if ring_id and hasattr(self.graph, "ring_visual_by_id")
            else None
        )
        panel = EntityQuickCreatePanel(
            self.entity_controller,
            on_created=self.refresh,
            layer_id=ring_id,
            layer_name=str(getattr(ring, "display_name", "") or ""),
        )
        drawer.set_content(panel, title="Nueva hoja")
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
            etype = str(
                getattr(
                    getattr(entity, "entity_type", ""), "value", getattr(entity, "entity_type", "")
                )
            )
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
            on_focus_neighborhood=lambda rid=relation_id: self.focus_neighborhood(
                rid, kind="relation"
            ),
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
        kind = getattr(
            getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "entidad")
        )
        return human_ref(getattr(entity, "name", "Sin nombre"), enum_human(str(kind)))

    def _world_layer_ids(self) -> set[str]:
        pc = self.ctx.project_controller
        project = pc.ps.active_project if pc else None
        return {
            str(getattr(layer, "id", ""))
            for layer in (getattr(project, "world_layers", []) or [])
            if getattr(layer, "id", "")
        }

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
        new_layer_ids = [ring_id] + [
            lid for lid in existing if lid not in world_ids and lid != ring_id
        ]
        self.entity_controller.update(entity_id, {"layer_ids": new_layer_ids})

    def _contained_descendant_ids(self, tree_id: str) -> list[str]:
        if self.relation_controller is None:
            return []
        children_by_parent: dict[str, list[str]] = {}
        for rel in self.relation_controller.list_all():
            if self._rtype_value(rel) == "contiene":
                children_by_parent.setdefault(str(getattr(rel, "source_id", "")), []).append(
                    str(getattr(rel, "target_id", ""))
                )
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

    def _relation_exists(
        self, source_id: str, target_id: str, *, ignore_structural: bool = False
    ) -> bool:
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

    def __init__(
        self,
        ai_controller,
        action: str,
        entity_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
    ):
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
