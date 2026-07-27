"""Product workspaces for the B27.5 Desktop UX shell.

These wrappers reorganize existing connected views into three product spaces
without deleting functionality. Technical CRUD screens are kept behind advanced
mode while normal mode starts from clean cards/overviews.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.app_trace import _apptrace
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
)
from hosts.DesktopHostPySide.widgets.filter_popover import FilterPopover
from hosts.DesktopHostPySide.controllers.ghost_controller import GhostController
from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView
from hosts.DesktopHostPySide.widgets.play.play_view import PlayView
from hosts.DesktopHostPySide.widgets.foco.watering_authorize import (
    request_watering_authorization,
)
from hosts.DesktopHostPySide.widgets.foco.watering_batch import WateringBatchWorker
from hosts.DesktopHostPySide.widgets.foco.watering_panel import WateringPanel
from hosts.DesktopHostPySide.widgets.milestone_labels import milestone_temporal_label
from pathlib import Path

from packages.application.history_service import HistoryService
from packages.domain.source_history import HistoryEventType
from packages.application.image_asset_service import assets_root_for
from packages.application.watering_attention import thirsty_queue, waterable_queue
from packages.application.structural_analysis_service import StructuralAnalysisService
from packages.application.watering_service import WateringService
from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    ChronoCanvasView,
    MilestoneQuickCreatePanel,
)
from hosts.DesktopHostPySide.controllers.era_controller import EraController
from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.settings_panels import _human_error as _human_ai_error
from hosts.DesktopHostPySide.widgets.design_system import (
    BusyIndicator,
    Card,
    ElidedLabel,
    EmptyState,
    SectionHeader,
    enum_human,
    human_ref,
    pulse_feedback,
    GOLD,
    GOLD_DEEP,
    GOLD_PRESS,
    GOLD_SOFT,
    GOLD_TINT,
    INK,
    INK_INVERSE,
    INK_SOFT,
    INK_STRONG,
    INK_MUTED,
    INK_OLIVE,
    LINE,
    POPUP_BG,
    RADIUS_CAPSULE,
    SURFACE,
    SURFACE_HI,
    TYPE_CAPTION_PX,
)
from packages.domain.result import Error
from packages.application.ai_jobs import (
    AIJobService,
    AIJobType,
)
from packages.infrastructure.openai_compatible_provider import get_provider
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


class RingPanel(_SimpleFormPanel):
    """BETA2-CLEANUP-PANELES: panel ÚNICO y minimalista para crear y editar un
    anillo (world layer). Reemplaza a los dos paneles legado
    (``LayerQuickCreatePanel`` crear + ``RingEditPanel`` editar).

    Campos: Nombre, Orden y Descripción.
    - ``ring_id=None`` → modo crear (``controller.create``).
    - ``ring_id`` dado → modo editar (prefill vía ``controller.get`` +
      ``controller.update``).

    Al editar, el orden se escribe también en ``metadata.causal_rank`` (la
    concéntrica ordena los anillos por rango causal), preservando el
    comportamiento del antiguo ``RingEditPanel``.
    """

    def __init__(self, controller, on_saved, *, ring_id: str | None = None):
        editing = bool(ring_id)
        super().__init__(
            "Editar anillo" if editing else "Nuevo anillo",
            "Un estrato del mundo: nómbralo y ordénalo del núcleo al borde.",
        )
        self.controller = controller
        self.on_saved = on_saved
        self.ring_id = str(ring_id or "")

        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre del anillo")
        self.order = BotanicalSpinBox()
        self.order.setRange(1, 999)
        self.order.setToolTip("Rango causal: ordena los anillos del núcleo al borde")
        self.description = QTextEdit()
        self.description.setPlaceholderText("Qué representa este anillo")
        self.description.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Orden", self.order)
        form.addRow("Descripción", self.description)
        self.layout.addLayout(form)
        self.status = self.add_status()

        row = QHBoxLayout()
        save = QPushButton("Guardar anillo" if editing else "Crear anillo")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

        if editing:
            self._load()
        else:
            self.order.setValue(self._next_order())

    def _next_order(self) -> int:
        try:
            layers = self.controller.list_all()
        except Exception:  # noqa: BLE001
            return 1
        orders = [int(getattr(wl, "order", 0) or 0) for wl in (layers or [])]
        return (max(orders) + 1) if orders else 1

    def _load(self) -> None:
        current = self.controller.get(self.ring_id) if hasattr(self.controller, "get") else None
        layer = getattr(current, "value", None)
        if layer is None:
            self.status.setText("Anillo no encontrado")
            return
        self.name.setText(str(getattr(layer, "name", "")))
        meta = getattr(layer, "metadata", {}) or {}
        rank = str(meta.get("causal_rank", "") or getattr(layer, "order", 1))
        try:
            self.order.setValue(int(rank))
        except (TypeError, ValueError):
            self.order.setValue(int(getattr(layer, "order", 1) or 1))
        self.description.setPlainText(str(getattr(layer, "description", "") or ""))

    def _save(self) -> None:
        name = self.name.text().strip()
        if not name:
            self.status.setText("El nombre no puede estar vacío")
            return
        order = int(self.order.value())
        description = self.description.toPlainText().strip()
        if self.ring_id:
            result = self.controller.update(
                self.ring_id,
                {
                    "name": name,
                    "order": order,
                    "description": description,
                    "metadata": {"causal_rank": str(order)},
                },
            )
        else:
            result = self.controller.create(
                {"name": name, "description": description, "order": order}
            )
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        layer = getattr(result, "value", None)
        if self.ring_id:
            self.status.setText("Anillo actualizado")
        else:
            self.status.setText(f"Anillo creado: {getattr(layer, 'name', 'sin nombre')}")
        self.on_saved()


# BETA2-CAL: se retiraron los antiguos paneles de crear/editar UNA era por años
# absolutos en aislado (eran un modelo paralelo). Ahora todas las eras se crean y editan
# encadenadas por duración en el editor de calendario unificado (ChronologyConfigPanel →
# CalendarEditor). El present_year se sigue editando en el pill temporal vía era_controller.


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


class _PlayPrefetchWorker(QThread):
    """PLAY-08: analiza el hito siguiente SIN mutar la sesión (prefetch).

    El resultado viaja con el epoch de canon con el que se lanzó; el receptor
    lo descarta si el canon cambió entre el lanzamiento y la llegada (los
    QThread no se cancelan de forma fiable, así que se invalida por epoch).
    """

    finishedOk = Signal(str, int, object)  # milestone_id, epoch, dict resultado
    failed = Signal(str)

    def __init__(self, controller, session_id: str, milestone_id: str, epoch: int):
        super().__init__()
        self.controller = controller
        self.session_id = session_id
        self.milestone_id = milestone_id
        self.epoch = epoch

    def run(self):
        try:
            res = self.controller.analyze_at(self.session_id, self.milestone_id)
            if isinstance(res, Error):
                self.failed.emit(res.error)
                return
            self.finishedOk.emit(self.milestone_id, self.epoch, res.value)
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            self.failed.emit(str(exc))


class _StatusLabel(QLabel):
    """QLabel que avisa a un callback cuando cambia su texto.

    BETA2-WIKI-10: el indicador de estado de IA vivía dentro de la command bar (ahora
    retirada). Al moverlo a un floater propio necesitamos mostrar/ocultar el contenedor
    cuando el texto aparece/desaparece SIN tener que tocar los ~15 puntos de llamada a
    setText repartidos por el workspace; este QLabel lo centraliza."""

    def __init__(self, on_change=None, parent=None):
        super().__init__("", parent)
        self._on_change = on_change

    def setText(self, text):  # noqa: N802 (API Qt)
        super().setText(text)
        cb = self._on_change
        if cb is not None:
            try:
                cb()
            except Exception:  # noqa: BLE001 — el feedback nunca debe romper el flujo
                pass


# BETA2-WIKI-13: métricas cuyas Sugerencias corren un análisis de intención (feedback).
_INTENT_METRICS_UI = frozenset({"arraigo", "iluminada"})


class _SuggestionPrepWorker(QThread):
    """BETA2-WIKI-13: prepara una Sugerencia FUERA del hilo de UI.

    Encadena la navegación de la wiki (WIKI-08) y, para arraigo/iluminada, el análisis de
    intención (WIKI-13) vía ``WateringService.compose_generation`` — hasta dos llamadas IA
    que no deben congelar la UI. Emite el payload compuesto ({job_type/prompt/context_scope/
    plan_summary}) o ``None`` (best-effort: la sugerencia sigue con el payload base)."""

    done = Signal(object)  # dict payload de compose_generation o None

    def __init__(self, watering_service, entity_id: str, metric: str, peticion: str):
        super().__init__()
        self.svc = watering_service
        self.entity_id = entity_id
        self.metric = metric
        self.peticion = peticion

    def run(self):
        try:
            res = self.svc.compose_generation(self.entity_id, self.metric, self.peticion)
            payload = getattr(res, "value", None) if not isinstance(res, Error) else None
            self.done.emit(payload)
        except Exception:  # pragma: no cover - defensive thread boundary
            self.done.emit(None)


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
                f"border-radius: 10px; padding: 8px; color: {INK_INVERSE}; font-weight: 700; }}"
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
    """BETA1-L02b: barra de búsqueda flotante ligera sobre el lienzo (Ctrl+B,
    BETA2-UI2-10 — mismo atajo que la paleta del Foco). No abre el drawer. Al
    teclear, el workspace busca (entidades del grafo + hitos de la cronología)
    y salta EN VIVO a la mejor coincidencia. Esc cierra; Enter confirma y
    cierra; clic en un resultado navega a él.

    Sigue siendo un overlay hijo (NO Qt.Popup): el salto en vivo mueve el foco
    entre vistas y un Popup se autocerraría. Estética alineada con Popover."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__(workspace)
        self.workspace = workspace
        # BETA1-L02c: ancho FIJO → añadir resultados no cambia el ancho ni reencuadra
        # horizontalmente la barra (antes el campo "saltaba" al teclear).
        self.setFixedWidth(420)
        self.setStyleSheet(
            f"QFrame {{ background: {POPUP_BG}; border: 1px solid {GOLD_SOFT}; border-radius: 12px; }}"
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
            f"font-size: {TYPE_CAPTION_PX}px; color: {self.MUTED}; background: transparent; "
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
            f"border-radius: 8px; padding: 4px 10px; color: {self.MUTED}; "
            f"font-size: {TYPE_CAPTION_PX}px; }} "
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
        entity_controller,
        relation_controller,
        candidate_controller,
        source_controller=None,
        layer_controller=None,
    ):
        super().__init__()
        self.ctx = ctx
        # BETA2-UX-02: la Creación recibe los controllers directamente. Antes se
        # inyectaban 5 vistas-tabla legacy inalcanzables solo para extraer sus
        # controllers; esas vistas se eliminaron.
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.candidate_controller = candidate_controller
        self.source_controller = source_controller
        self.layer_controller = layer_controller
        self.prompt_trace_store = (
            getattr(self.ctx, "ai_prompt_trace_store", None) or AIPromptDebugTraceStore.default()
        )
        self.ctx.ai_prompt_trace_store = self.prompt_trace_store
        # Resolve the configured provider (real if NARRATIVE_AI_* is set) instead
        # of the simulated default, so the command bar uses the user's provider.
        # BETA2-WIKI-11: el RAG léxico queda RETIRADO del pipeline. El AIJobService ya
        # no recibe rag_service (el contexto lo decide la navegación de la wiki); se
        # conserva project_provider para las inyecciones deterministas + la wiki.
        self.ai_job_service = AIJobService(
            provider=get_provider(),
            project_provider=self._get_active_project,
            prompt_trace_store=self.prompt_trace_store,
        )
        self._ai_workers = {}
        self._wiki_nav_workers: set = set()  # BETA2-WIKI-08: workers de navegación en curso
        # Semillas (Fase A): notificaciones palpitantes abajo-derecha + campana zen.
        self._zen_bell = ZenBell()
        self._seed_notifications = SeedNotificationLayer(self)
        # SEM04: el workspace ancla la capa ENCIMA del cluster de botones derecho,
        # con z-order por encima, para que no solape los botones ni pierda los clics.
        self._seed_notifications.set_reflow_callback(self._position_seed_layer)
        self._seed_notifications.reviewRequested.connect(self._open_candidate_review)
        # BETA2-JARDIN-03: badge «💧 N» — cada clic recorre las sedientas en
        # Foco. El recómputo va con debounce: el autosave toca la revisión del
        # proyecto en cada guardado y statuses_for recorre todo el jardín.
        self._seed_notifications.thirstyRequested.connect(self._on_thirsty_requested)
        # UI2-04: clic primario del badge de riego — regar TODAS las sedientas
        # (reutiliza la autorización visible + lote secuencial existentes).
        self._seed_notifications.waterAllRequested.connect(self._on_foco_water)
        # BETA2-FOCO-34: aviso «revisar en Cultivo» tras regar → enfoca + abre Cultivo.
        self._seed_notifications.cultivoReviewRequested.connect(self._on_cultivo_review)
        # BETA2-FOCO-35: clic en «Regando x/y» → popover de detalle del lote.
        self._seed_notifications.waterProgressRequested.connect(self._open_watering_progress)
        self._thirsty_debounce = QTimer(self)
        self._thirsty_debounce.setSingleShot(True)
        self._thirsty_debounce.setInterval(400)
        self._thirsty_debounce.timeout.connect(self._refresh_thirsty_badge)
        # BETA2-STRUCT-02: mismo patrón derive-on-read para los ajustes estructurales.
        self._structural_debounce = QTimer(self)
        self._structural_debounce.setSingleShot(True)
        self._structural_debounce.setInterval(400)
        self._structural_debounce.timeout.connect(self._refresh_structural_badge)
        self._float_structure = None
        self._active_layer_id = ""
        self._advanced_mode = bool(ctx.advanced_mode)
        project_controller = getattr(ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is not None:
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
        # CRON: sesión de recorrido en curso (id); su cara es la vista Play.
        self._walk_session_id: str | None = None
        self._walk_step_worker = None
        # PLAY-12: token de INTENTO de paso — «Reintentar» lo incrementa y el
        # resultado del intento viejo se descarta en la guarda (los QThread no
        # se cancelan de forma fiable). No confundir con _play_epoch (canon).
        self._walk_step_token = 0
        self._walk_workers: set = set()  # mantiene vivos los QThread del recorrido
        self._walk_analyzing = False  # guarda determinista contra pasos solapados
        self._walk_step_candidate_ids: list[str] = []
        # CRON: perro guardián — PLAY-12: ya no «cancela»; a los 60 s avisa de
        # que la IA tarda (aviso + Reintentar) y se sigue esperando.
        self._walk_watchdog: QTimer | None = None
        self._walk_watchdog_ms = 60000

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
        # BETA2-CLEANUP-PANELES: el clic simple ya NO abre el cajón de detalle
        # (retirado); la edición vive en el Foco (doble clic / "Editar" → Foco).
        # BETA2-FOCO-14: doble click en el Mapa (solo lectura) → entrar a Foco.
        self.graph.entityFocusRequested.connect(self._on_map_entity_to_foco)
        self.graph.candidateClicked.connect(self._open_candidate_review)  # SEM04
        self.graph.relationSelected.connect(self._open_relation_panel)
        self.graph.relationCreateRequested.connect(self._open_relation_create_panel)
        self.graph.relationCreateRejected.connect(self._on_relation_create_rejected)
        self.graph.graphSelectionChanged.connect(self._on_graph_selection_changed)
        self.graph.nodeAssignToTreeRequested.connect(self._assign_node_to_tree)
        self.graph.ringSelected.connect(self._on_ring_selected)
        self.graph.ringFocused.connect(self._on_ring_focused)
        self.graph.ringFocusCleared.connect(self._on_ring_focus_cleared)
        # BETA2-UI2-10: embudo del pill temporal → popover de filtros; año
        # presente editable → persistencia vía era_controller (solo aquí).
        self.graph.filterRequested.connect(self._open_filter_popover)
        self.graph.presentYearEdited.connect(self._on_present_year_edited)
        # BETA1-B01: context-menu intents -> existing creation/deletion routes
        self.graph.contextCreateEntityRequested.connect(self._create_entity_on_graph)
        self.graph.contextCreateTreeRequested.connect(self._create_tree_on_graph)
        self.graph.contextCreateEntityInTreeRequested.connect(self._create_entity_in_tree)
        self.graph.contextCreateSubtreeRequested.connect(self._create_subtree_in_tree)
        self.graph.contextDeleteRequested.connect(self._delete_selected)
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
        # BETA2-SUB-02: clic en una entidad de la cronología → Modo Foco
        # (descripción) de esa entidad, como el doble-clic del Mapa. Antes abría
        # el panel Node/Tree en el drawer (patrón antiguo).
        self.chrono.entityActivated.connect(self._on_map_entity_to_foco)
        self.chrono.milestoneActivated.connect(self._on_chrono_milestone)
        self.chrono.walkRequested.connect(self._start_or_continue_walk)  # CRON
        self.chrono.lifespanEdited.connect(self._on_lifespan_edited)  # BETA1-UX2C
        self.chrono.milestoneCreateRequested.connect(
            self._on_chrono_create_milestone
        )  # BETA1-HITO-MULTI
        self.chrono.eraActivated.connect(self._open_era_edit_panel)  # BETA1-HITO-MULTI
        # BETA2-UI2-10: "Crear era…" desde el menú contextual de la Cronología.
        self.chrono.eraCreateRequested.connect(self._open_era_create_panel)
        # BETA2-FOCO-33: embudo de filtros de la Cronología (réplica del Mapa).
        self.chrono.filterRequested.connect(self._open_chrono_filter_popover)
        self.chrono.milestoneEntityLinkRequested.connect(
            self._on_chrono_link_entity
        )  # BETA1-HITO-MULTI
        layout.addWidget(self.chrono, 1)

        # BETA2-UI2-10: Ctrl+B abre la búsqueda flotante unificada en Mapa y
        # Cronología (mismo atajo que la paleta del Foco). Los shortcuts van
        # anclados a graph/chrono — NUNCA al workspace: FocoView es hijo y ya
        # tiene su propio Ctrl+B con WidgetWithChildrenShortcut; dos matches
        # en el mismo ámbito serían ambiguos y ninguno dispararía.
        for host in (self.graph, self.chrono):
            shortcut = QShortcut(QKeySequence("Ctrl+B"), host)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self._open_search_overlay)

        # BETA2-FOCO: Modo Foco — escritorio causal centrado en una entidad.
        # Es la vista PRINCIPAL de Creación; el grafo (Mapa) y la cronología
        # pasan a ser vistas globales de orientación/revisión del jardín.
        _foco_ps = getattr(getattr(self.ctx, "project_controller", None), "ps", None)
        # BETA2-PLAY-18: provider de observaciones del recorrido para el Cuaderno
        # de Cultivo (solo lectura del historial filtrado por entidad + origen).
        _foco_history = HistoryService(_foco_ps) if _foco_ps is not None else None
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
            history_provider=(
                (
                    lambda eid: _foco_history.get_history(
                        entity_id=eid, event_type=HistoryEventType.OBSERVACION_RECORRIDO
                    )
                )
                if _foco_history is not None
                else None
            ),
        )
        self.foco.setVisible(False)
        self.foco.openInMapRequested.connect(self._foco_open_in_map)
        self.foco.openInChronoRequested.connect(self._foco_open_in_chrono)
        # FOCO-10: la banda local reutiliza los slots de la cronología global.
        self.foco.lifespanEdited.connect(self._on_lifespan_edited)
        # FOCO-25: desde la banda local el hito nace vinculado a la entidad en foco.
        self.foco.milestoneCreateRequested.connect(self._on_foco_create_milestone)
        # FOCO-26: rango dibujado en la banda ⇒ hito con inicio y fin.
        self.foco.milestoneRangeCreateRequested.connect(self._on_foco_create_milestone_range)
        # BETA2-MEM: Memoria narrativa viva. Servicio determinista (CRUD) + servicio
        # IA (update_memory). Regar v2 (MEM-07) actualiza Memoria en el mismo flujo.
        from packages.application.memory_ai_service import MemoryAIService
        from packages.application.narrative_impact_service import NarrativeImpactService
        from packages.application.narrative_memory_service import NarrativeMemoryService
        from packages.application.suggestion_intent_service import SuggestionIntentService
        from packages.application.wiki_navigator import WikiNavigator

        self.memory_service = (
            NarrativeMemoryService(_foco_ps, HistoryService(_foco_ps))
            if _foco_ps is not None
            else None
        )
        self.memory_ai_service = (
            MemoryAIService(_foco_ps, self.ai_job_service, memory_service=self.memory_service)
            if _foco_ps is not None
            else None
        )
        # BETA2-WIKI: motor de impacto (propaga Falta regar al Regar) + navegador de la
        # wiki (las Sugerencias navegan el índice para armar contexto coherente).
        self.impact_service = (
            NarrativeImpactService(_foco_ps, memory_service=self.memory_service)
            if _foco_ps is not None
            else None
        )
        # BETA2-STRUCT: detector estructural determinista (coste IA cero). Propone
        # reubicaciones de anillo por potencial de propagación causal; deriva en lectura
        # (como el badge de sed). La IA solo enriquece la justificación al abrir.
        self.structural_service = (
            StructuralAnalysisService(
                _foco_ps,
                impact_service=self.impact_service,
                ai_job_service=self.ai_job_service,
            )
            if _foco_ps is not None
            else None
        )
        self.wiki_navigator = (
            WikiNavigator(
                _foco_ps, ai_job_service=self.ai_job_service, memory_service=self.memory_service
            )
            if _foco_ps is not None
            else None
        )
        # BETA2-WIKI-13: análisis de intención previo para Sugerencias de arraigo/iluminada
        # (decide el mix de output; nutrida/calidad siguen fijas por métrica).
        self.suggestion_intent_service = (
            SuggestionIntentService(_foco_ps, ai_job_service=self.ai_job_service)
            if _foco_ps is not None
            else None
        )
        # BETA2-WIKI-09: el recorrido cronológico (Play/walk) también navega la wiki.
        if self.chronology_walk_controller is not None and self.wiki_navigator is not None:
            self.chronology_walk_controller.svc.navigator = self.wiki_navigator
        # FOCO-12: riego — servicio real + drawer dedicado + autorización SIEMPRE.
        self.watering_service = (
            WateringService(
                _foco_ps,
                ai_job_service=self.ai_job_service,
                history_service=HistoryService(_foco_ps),
                memory_ai_service=self.memory_ai_service,  # MEM-07: Regar v2
                impact_service=self.impact_service,  # WIKI-06: propaga Falta regar
                navigator=self.wiki_navigator,  # WIKI-08: Sugerencias navegan la wiki
                intent_service=self.suggestion_intent_service,  # WIKI-13: análisis de intención
                memory_service=self.memory_service,  # WIKI-13: frescura riego⇄página unificada
            )
            if _foco_ps is not None
            else None
        )
        self.foco.watering_service = self.watering_service
        # BETA2-MEM-09: la pestaña Cultivo del Foco muestra el estado de Memoria.
        self.foco.memory_service = self.memory_service
        # BETA2-JARDIN-01: el Mapa muestra SIEMPRE el estado de riego (sin
        # lente conmutable). El provider lee watering_service perezosamente.
        self.graph.set_garden_status_provider(self._garden_status_map)
        self._watering_panel: WateringPanel | None = None
        self._watering_worker: WateringBatchWorker | None = None
        # BETA2-FOCO-35: estado del lote de riego para el popover de progreso
        # (id → "pending"/"watering"/"done"/"error").
        self._batch_state: dict[str, str] = {}
        self._batch_total = 0
        # BETA2-FOCO-39: popover de progreso vivo (se refresca en cada paso).
        self._watering_progress_popover = None
        self.foco.waterRequested.connect(self._on_foco_water)
        self.foco.dryRequested.connect(self._on_foco_dry)
        self.foco.cultivateRequested.connect(self._on_foco_cultivate)
        # FOCO-26: «Sugerir X» desde el Cuaderno de cultivo del editor.
        self.foco.suggestRequested.connect(self._on_foco_suggest)
        self.foco.entityCentered.connect(self._sync_watering_panel_entity)
        # FOCO-13: semillas de la entidad enfocada germinan en zona/drawer; el
        # resto conserva su chip pulsante (nada se pierde, nada se duplica).
        self.foco.seedReviewRequested.connect(self._open_candidate_review)
        self.foco.entityCentered.connect(lambda _eid: self._rehydrate_seed_notifications())
        # FOCO-19: las mutaciones hechas en Foco marcan el Mapa como obsoleto;
        # al entrar a "concentric" se reconstruye (antes la entidad nueva no
        # aparecía hasta un refresh completo).
        self._graph_stale = False
        self.foco.dataChanged.connect(self._mark_graph_stale)
        # BETA2-CLEANUP-PANELES: panel de anillo (unificado) abierto desde el Foco
        # — click en el banner (editar) y botón «Crear anillo» del rail (crear).
        # Reutiliza los mismos handlers que el Mapa (RingPanel en el cajón).
        self.foco.ringEditRequested.connect(self._open_ring_edit_panel)
        self.foco.ringCreateRequested.connect(self._open_ring_create_panel)
        # SHIP-02: el CTA del estado vacío de Foco usa el mismo flujo que el del Mapa.
        self.foco.createFirstRequested.connect(self._create_entity_on_graph)
        self.foco.deleteRequested.connect(self._delete_entity_from_foco)
        layout.addWidget(self.foco, 1)

        # BETA2-PLAY: modo Play — la creación cronológica como experiencia
        # inmersiva (escena por hito). Cuarto estado de vista, fuera de la
        # píldora de modos; se entra desde la configuración del recorrido.
        self.play = PlayView(project_provider=self._get_active_project)
        self.play.setVisible(False)
        self.play.exitRequested.connect(self._exit_play)
        # PLAY-04: el ciclo del recorrido reusa los handlers existentes del walk.
        self.play.continueRequested.connect(self._advance_walk)
        self.play.stopRequested.connect(self._stop_walk)
        # PLAY-05: los desvíos causales piden escenas deterministas al servicio.
        self.play.set_scene_getter(self._play_scene_for)
        # PLAY-06: la escena es editable; el canon lo escribe el controller.
        self.play.editCommitted.connect(self._on_play_edit)
        # PLAY-07: aplazar problemas duros / aplicar candidatos del paso.
        self.play.deferRequested.connect(self._defer_walk)
        self.play.applyRequested.connect(self._on_walk_apply)
        # PLAY-12: reintento del análisis (descarta el intento en vuelo).
        self.play.retryRequested.connect(self._retry_walk_step)
        # PLAY-17: revisión de una propuesta en el preview del panel real.
        self.play.set_preview_factory(self._build_proposal_preview)
        # PLAY-08: prefetch del paso N+1 — cache por hito + epoch de canon.
        self._play_prefetch_cache: dict[str, dict] = {}
        self._play_prefetch_worker: _PlayPrefetchWorker | None = None
        self._play_epoch = 0
        self._play_adopt_step = False  # el prefetch en vuelo ES el paso actual
        self._play_step_queued = False  # paso pendiente hasta que muera un prefetch rancio
        layout.addWidget(self.play, 1)
        self._active_view = "concentric"  # el arranque fuerza "foco" al final de _build_ui

        # BETA2-WIKI-10: la command bar (Acción×Ámbito + texto libre) queda RETIRADA de la
        # UI. La única vía creativa de IA con prompt libre es Sugerir (petición en Foco).
        # El atributo se conserva en None: varios consumidores (floater de estado) lo miran.
        self._command_bar = None

        # BETA2-UI2-10: el cluster flotante izquierdo desapareció — la búsqueda
        # es Ctrl+B (sin botón) y los filtros viven en el embudo del pill
        # temporal. La Lente Jardín ya se retiró en BETA2-JARDIN-01.
        # UX29: el guardar usa el MISMO formato de píldora que el alternador central
        # (icono + texto), abajo-derecha, en vez de un círculo dorado que no se veía.
        self._float_right = self._build_save_pill()
        # BETA2-WIKI-10: indicador de estado de IA SIEMPRE presente (el que había vivía
        # dentro de la command bar retirada). Sin él, `_job_status_label`/`_busy_indicator`
        # no existían y Sugerencias/riego reventaban al referenciarlos (Sugerir se caía en
        # silencio, sin feedback). Solo se crea cuando NO hay command bar (mutuamente
        # excluyentes: la command bar trae los suyos).
        self._float_status = None
        if self._command_bar is None:
            self._float_status = self._build_status_floater()
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
        self._float_focus_label = ElidedLabel("")
        self._float_focus_label.setMaximumWidth(260)
        self._float_focus_label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: 11px; font-weight: 600; background: transparent; border: none;"
        )
        focus_layout.addWidget(self._float_focus_label)
        # BETA1-L02b: saltar al anillo contiguo se hace por teclado ([ / ]); sin botones.
        focus_exit = QPushButton("Salir")
        focus_exit.setIcon(icons.icon("close", color=INK_INVERSE, size=13))
        focus_exit.setIconSize(QSize(13, 13))
        focus_exit.setToolTip("Salir del anillo / volver a mostrar todo el grafo (Esc)")
        focus_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        focus_exit.setFixedHeight(24)
        focus_exit.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; border: none; border-radius: 12px; "
            f"color: {INK_INVERSE}; font-size: 11px; font-weight: 700; padding: 0 12px; }} "
            f"QPushButton:hover {{ background: {GOLD_DEEP}; }}"
        )
        focus_exit.clicked.connect(self.clear_focus_scope)
        focus_layout.addWidget(focus_exit)
        self._float_focus.setVisible(False)

        # BETA1-L02b: barra de búsqueda flotante ligera (Ctrl+B). No abre el
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
        # BETA2-WIKI-11: los botones IA ocultos de la toolbar (sugerir hoja/rama/
        # relación, coherencia, tareas, resumen) se han eliminado con sus handlers.
        # BETA2-UI2-10: sin botones "Buscar" (Ctrl+B) ni "Filtro" (embudo del
        # pill temporal, con badge de activos).
        icon_btn("Anillos", "Selector de anillos: recorrer las capas", self._open_ring_panel)
        # BETA2-UI2-10: la gestión de anillos/eras es contextual — clic derecho
        # en un anillo del Mapa (editar/crear/eliminar) y clic en la banda de
        # era de la Cronología (editar) o su menú contextual (crear).
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
            f"QFrame {{ background: {GOLD_DEEP}; border: 1px solid {GOLD_DEEP}; "
            f"border-radius: {RADIUS_CAPSULE}px; }}"
        )
        row = QHBoxLayout(pill)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(0)
        self._save_btn = QPushButton("  Guardar")
        self._save_btn.setIcon(icons.icon("save", color=INK_INVERSE, size=15))
        self._save_btn.setIconSize(QSize(15, 15))
        self._save_btn.setToolTip("Guardar el proyecto")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setFixedHeight(32)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 16px; "
            f"color: {INK_INVERSE}; font-size: 13px; font-weight: 700; padding: 0 16px; }} "
            f"QPushButton:hover {{ background: {GOLD}; color: {INK_INVERSE}; }} "
            f"QPushButton:pressed {{ background: {GOLD_PRESS}; }}"
        )
        self._save_btn.clicked.connect(self._save_project_from_canvas)
        row.addWidget(self._save_btn)
        pill.adjustSize()
        pill.raise_()
        return pill

    def _build_status_floater(self) -> QFrame:
        """BETA2-WIKI-10: floater de estado de IA (punto de actividad + texto),
        SIEMPRE disponible e independiente de la command bar retirada.

        Crea `self._busy_indicator` y `self._job_status_label` (un `_StatusLabel` que
        muestra/oculta este floater al cambiar el texto). Antes vivían en la command
        bar y su ausencia rompía Sugerencias/riego. Anclado abajo-centro sobre el
        lienzo; invisible mientras no haya texto."""
        floater = QFrame(self)
        floater.setObjectName("aiStatusFloater")
        floater.setStyleSheet(
            f"QFrame#aiStatusFloater {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: {RADIUS_CAPSULE}px; }}"
        )
        row = QHBoxLayout(floater)
        row.setContentsMargins(14, 6, 16, 6)
        row.setSpacing(8)
        self._busy_indicator = BusyIndicator(diameter=16)
        self._busy_indicator.set_period_ms(self.ctx.animation_duration(900))
        self._busy_indicator.setToolTip("Dendro está trabajando…")
        row.addWidget(self._busy_indicator)
        self._job_status_label = _StatusLabel(on_change=self._sync_status_floater, parent=floater)
        self._job_status_label.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 12px; font-weight: 600; "
            f"background: transparent; border: none;"
        )
        self._job_status_label.setToolTip(
            "Estado de las tareas IA. Todo resultado queda pendiente de revisión."
        )
        row.addWidget(self._job_status_label)
        floater.setVisible(False)
        return floater

    def _sync_status_floater(self) -> None:
        """Muestra el floater de estado solo cuando hay texto y lo recoloca abajo-centro.

        Lo invoca `_StatusLabel.setText` (cualquier punto que ponga estado de IA) y
        también `_position_floats` al redimensionar. Fail-soft en construcción temprana."""
        floater = getattr(self, "_float_status", None)
        label = getattr(self, "_job_status_label", None)
        if floater is None or label is None:
            return
        has_text = bool(label.text().strip())
        floater.setVisible(has_text)
        if has_text:
            floater.adjustSize()
            floater.move(
                max(12, (self.width() - floater.width()) // 2),
                max(12, self.height() - floater.height() - 22),
            )
            floater.raise_()

    def _schedule_status_clear(self, delay_ms: int = 6000) -> None:
        """BETA2-WIKI-13: borra el estado flotante tras un rato si NADIE lo pisó.

        Los mensajes terminales (resultado/error de un job) se quedaban fijos abajo-centro.
        Se limpia solo si el texto sigue siendo el mismo (un job posterior lo respeta)."""
        label = getattr(self, "_job_status_label", None)
        if label is None:
            return
        current = label.text()
        if not current.strip():
            return

        def _maybe_clear() -> None:
            lbl = getattr(self, "_job_status_label", None)
            try:
                if lbl is not None and lbl.text() == current:
                    lbl.setText("")
            except RuntimeError:  # widget Qt ya destruido
                pass

        QTimer.singleShot(delay_ms, _maybe_clear)

    def _build_view_toggle(self) -> QFrame:
        """BETA2-FOCO: barra superior de modos — Foco | Mapa | Cronología.

        Sustituye a la píldora binaria BETA1-G04. Foco es el modo principal;
        Mapa (grafo concéntrico) y Cronología quedan como vistas globales.
        Se ancla arriba-centro (spec: "barra superior de modos")."""
        pill = QFrame(self)
        pill.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: {RADIUS_CAPSULE}px; }}"
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
            panel.reviewRequested.connect(self._open_candidate_review)  # FOCO-13
            self._watering_panel = panel
        return self._watering_panel

    def _open_watering_drawer(self, entity_id: str = "") -> None:
        panel = self._ensure_watering_panel()
        if panel is None or self.ctx.drawer is None:
            return
        panel.set_entity(entity_id or self.foco.current_entity_id())
        self.ctx.drawer.set_content(panel, title="Riego")
        self.ctx.drawer.open()

    @_qt_safe_slot
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
            self.ctx.notify(result.error, "error")
            return
        self.ctx.request_save_silent()
        self.foco._refresh_tool_context()
        # FOCO-26: el estado vive en el Cuaderno de cultivo del editor — secar
        # ya no abre el drawer (que queda para el riego por lotes).
        self.foco.refresh_cultivation()
        self.graph.refresh_garden_status()  # JARDIN-01: la secada se apaga en el Mapa
        self._request_thirsty_refresh()

    def _on_foco_cultivate(self, entity_id: str) -> None:
        """Cultivar: sin IA; la entidad vuelve al ciclo como Falta regar."""
        if self.watering_service is None or not entity_id:
            return
        result = self.watering_service.resume(entity_id)
        if isinstance(result, Error):
            self.ctx.notify(result.error, "error")
            return
        self.ctx.request_save_silent()
        self.foco._refresh_tool_context()
        # FOCO-26: refresco en sitio (Cuaderno), sin drawer.
        self.foco.refresh_cultivation()
        self.graph.refresh_garden_status()  # JARDIN-01: vuelve al ciclo en el Mapa
        self._request_thirsty_refresh()

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
            self._warn_ai_unconfigured("regar")
            return
        scope = service.entities_in_scope({"selection": ids})
        eligible = getattr(scope, "value", None) or []
        if not eligible:
            self.ctx.log("info", "Nada que regar: la selección no tiene entidades elegibles.")
            return
        estimate = getattr(service.estimate(eligible), "value", None)
        if estimate is None:
            self.ctx.notify("No se pudo estimar el coste del riego.", "error")
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
        ids = [str(entity_id) for entity_id in entity_ids if entity_id]
        worker = WateringBatchWorker(self.watering_service, ids)
        worker.entityStarted.connect(self._on_watering_entity_started)  # UI2-05
        worker.entityDone.connect(self._on_watering_entity_done)
        worker.progressChanged.connect(self._on_watering_progress)
        worker.finishedOk.connect(self._on_watering_finished)
        worker.finished.connect(lambda: setattr(self, "_watering_worker", None))
        self._watering_worker = worker
        track_worker(worker)  # apagado ordenado al cerrar la app (AUDIT-02)
        # BETA2-FOCO-35: el lote ya NO abre el drawer «Riego» por-entidad (era
        # confuso —mostraba UNA entidad— y su borrado al navegar colgaba el lote).
        # El progreso se sigue en el badge «Regando x/y» → popover de detalle.
        self._batch_state = {eid: "pending" for eid in ids}
        self._batch_total = len(ids)
        self._seed_notifications.set_watering_progress(0, len(ids))  # UI2-04
        worker.start()

    def _cancel_watering_batch(self) -> None:
        worker = self._watering_worker
        if worker is not None:
            worker.request_cancel()
            self.ctx.log("info", "Riego: cancelando entre pasos (los parciales se conservan).")

    def _batch_progress_entries(self) -> tuple[list[dict], int]:
        """BETA2-FOCO-35/39: (entradas, hechas) del lote para el popover de
        progreso — nombre + estado + resumen del último informe por entidad."""
        project = self._get_active_project()
        service = self.watering_service
        reports = {}
        if service is not None and self._batch_state:
            reports = getattr(service.statuses_for(list(self._batch_state)), "value", None) or {}
        entries: list[dict] = []
        done = 0
        for entity_id, status in self._batch_state.items():
            if status in ("done", "error"):
                done += 1
            entity = project.entity_by_id(entity_id) if project is not None else None
            name = str(getattr(entity, "name", "") or "") or entity_id
            report = reports.get(entity_id)
            latest = getattr(report, "latest", None) if report is not None else None
            summary = str(getattr(latest, "summary", "") or "")[:60] if latest is not None else ""
            entries.append({"name": name, "status": status, "summary": summary})
        return entries, done

    def _open_watering_progress(self) -> None:
        """BETA2-FOCO-35/39: popover de detalle del lote anclado al badge «Regando
        x/y». Se REFRESCA EN VIVO por los slots del worker mientras siga abierto
        (antes era un snapshot: quedaba congelado si el usuario lo dejaba abierto)."""
        if not self._batch_state:
            return
        from hosts.DesktopHostPySide.widgets.foco.watering_progress_popover import (
            WateringProgressPopover,
        )

        entries, done = self._batch_progress_entries()
        self._watering_progress_popover = WateringProgressPopover(
            entries, done, self._batch_total, parent=self
        )
        # WS-K: el botón «Cancelar riego» del popover corta el lote en curso.
        self._watering_progress_popover.cancelRequested.connect(self._cancel_watering_batch)
        self._watering_progress_popover.open_above(self._seed_notifications.progress_anchor())

    def _refresh_watering_progress_popover(self, *, finished: bool = False) -> None:
        """BETA2-FOCO-39: si el popover sigue vivo y visible, lo actualiza en sitio
        (sin reabrirlo) para que el detalle siga el avance del lote."""
        popover = getattr(self, "_watering_progress_popover", None)
        if popover is None or not _qt_alive(popover) or not popover.isVisible():
            return
        entries, done = self._batch_progress_entries()
        total = self._batch_total or len(entries)
        popover.update_progress(entries, done, total, finished=finished)

    def _run_batch_cosmetics(self, *thunks) -> None:
        """BETA2-FOCO-39: ejecuta refrescos cosméticos del lote AISLADOS — un fallo
        (pulso de una rama sin ``set_watering_pulse``, canvas efímero) se registra
        pero NO aborta el resto ni cuelga el lote. Lo esencial (estado, avisos,
        badge, popover) ya corrió antes de llamar aquí."""
        for thunk in thunks:
            try:
                thunk()
            except Exception as exc:  # noqa: BLE001 — un cosmético caído no cuelga el lote
                self.ctx.log("warning", f"Riego: refresco parcial omitido ({exc})")

    def _refresh_focused_cultivation(self, entity_id: str) -> None:
        """FOCO-26: si la regada es la enfocada, refresca su Cuaderno in situ."""
        if entity_id == self.foco.current_entity_id():
            self.foco._refresh_tool_context()
            self.foco.refresh_cultivation()

    @_qt_safe_slot
    def _on_watering_entity_started(self, entity_id: str) -> None:
        """UI2-05: feedback vivo — el nodo pulsa en el Mapa y el Foco lo señala."""
        self._batch_state[entity_id] = "watering"
        self._refresh_watering_progress_popover()
        self._run_batch_cosmetics(
            lambda: self.graph.set_watering_active(entity_id),
            lambda: self.foco.set_watering_active(entity_id),
        )

    @_qt_safe_slot
    def _on_watering_entity_done(self, entity_id: str, ok: bool, error: str) -> None:
        # BETA2-FOCO-39: lo ESENCIAL primero (estado del lote, aviso, popover) y
        # los cosméticos DESPUÉS y AISLADOS. Antes, un cosmético que reventaba
        # (p. ej. el pulso de una rama en el Mapa) abortaba el slot ANTES del aviso
        # y dejaba el lote sin avisos y el badge congelado.
        self._batch_state[entity_id] = "done" if ok else "error"
        if ok:
            self._raise_cultivo_aviso(entity_id)  # FOCO-34/36: aviso agregado
        else:
            self.ctx.log("error", f"Riego fallido ({entity_id}): {error}")
        self._refresh_watering_progress_popover()
        self._run_batch_cosmetics(
            lambda: self.graph.set_watering_active(""),  # UI2-05: apagar el pulso
            lambda: self.foco.set_watering_active(""),
            self.ctx.request_save_silent,  # parciales persistidos (hilo UI)
            self.graph.refresh_garden_status,  # JARDIN-01: la regada revive en el Mapa
            self._request_thirsty_refresh,
            lambda: self._refresh_focused_cultivation(entity_id),
        )

    @_qt_safe_slot
    def _on_watering_progress(self, done: int, total: int) -> None:
        self._seed_notifications.set_watering_progress(done, total)  # UI2-04 (esencial)
        self._refresh_watering_progress_popover()
        self._run_batch_cosmetics(
            lambda: self._job_status_label.setText(f"Regando {done}/{total}…"),
        )

    @_qt_safe_slot
    def _on_watering_finished(self) -> None:
        # BETA2-FOCO-39: ESENCIAL primero — refresco final del popover y RESET del
        # badge/lote SIEMPRE, aunque un refresco del Mapa/Foco lance. Antes el reset
        # iba al final tras cosméticos que podían reventar → badge congelado en x/y.
        self._refresh_watering_progress_popover(finished=True)  # usa _batch_state aún vivo
        self._seed_notifications.set_watering_progress(0, 0)  # UI2-04: restaura el badge
        self._batch_state = {}
        self._batch_total = 0
        self.ctx.log("info", "Riego completado: diagnósticos persistidos.")
        self._run_batch_cosmetics(
            lambda: self.graph.set_watering_active(""),  # por si se canceló con pulso
            lambda: self.foco.set_watering_active(""),
            self.foco.refresh_cultivation,  # FOCO-26: informe vigente al Cuaderno
            self.graph.refresh_garden_status,  # JARDIN-01: estado final al Mapa
            self._request_thirsty_refresh,
            lambda: self._job_status_label.setText(""),
        )

    def _raise_cultivo_aviso(self, entity_id: str) -> None:
        """BETA2-FOCO-34: aviso «revisar en Cultivo» por una entidad regada."""
        layer = getattr(self, "_seed_notifications", None)
        if layer is None or not entity_id:
            return
        project = self._get_active_project()
        entity = project.entity_by_id(entity_id) if project is not None else None
        name = str(getattr(entity, "name", "") or "") if entity is not None else ""
        label = (
            f"{name} actualizada en Cultivo — revisar"
            if name
            else "Entidad actualizada en Cultivo — revisar"
        )
        layer.add(entity_id, label, kind="cultivo")

    def _on_cultivo_review(self, entity_id: str) -> None:
        """BETA2-FOCO-34: clic en el aviso → Foco sobre la entidad + pestaña Cultivo."""
        if not entity_id:
            return
        self.set_active_view("foco")
        foco = getattr(self, "foco", None)
        if foco is None:
            return
        foco.center_entity(entity_id)
        open_cultivo = getattr(foco, "open_cultivo_tab", None)
        if callable(open_cultivo):
            open_cultivo()

    def _on_foco_suggest(self, metric: str) -> None:
        """Sugerir X (BETA2-WIKI-08): petición del usuario + navegación de la wiki.

        La única vía creativa de IA que acepta prompt libre. Un campo opcional de
        petición/matiz encabeza el prompt; antes de generar, la wiki se navega (en un
        hilo) para armar contexto coherente. Resultado: Semillas revisables.
        """
        service = self.watering_service
        entity_id = self.foco.current_entity_id()
        if service is None or not entity_id:
            return
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            self._warn_ai_unconfigured("pedir sugerencias")
            return
        from PySide6.QtWidgets import QInputDialog

        # SHIP-07: el título mostraba la clave interna ("nutrida"/"iluminada"); usa
        # la etiqueta legible que coincide con el botón ("Sugerir nutrición").
        metric_label = {
            "arraigo": "arraigo",
            "nutrida": "nutrición",
            "iluminada": "iluminación",
            "calidad": "calidad narrativa",
        }.get(metric, metric)
        peticion, ok = QInputDialog.getMultiLineText(
            self,
            f"Sugerir {metric_label}",
            "Petición o matiz (opcional). Déjalo vacío para una sugerencia guiada solo "
            "por las métricas del jardín:",
        )
        if not ok:
            return
        request = service.build_suggestion_request(entity_id, metric, str(peticion).strip())
        if isinstance(request, Error):
            self.ctx.notify(request.error, "error")
            return
        payload = request.value
        lines = [
            f"Entidad afectada: {payload['entity_name']}.",
            "Se navegará la wiki para traer el contexto relevante (páginas + canon).",
            f"Tokens de entrada estimados: ~{payload['estimated_input_tokens']}.",
            "Resultado esperado: semillas revisables para reparar la métrica. "
            "Nada se integra al canon sin tu aceptación.",
        ]
        # BETA2-WIKI-13: arraigo/iluminada analizan la petición para decidir el mix a crear.
        if str(metric).lower() in _INTENT_METRICS_UI:
            lines.insert(
                1,
                "Se analizará tu petición para decidir qué proponer (hojas, ramas, "
                "relaciones, hitos o ediciones).",
            )
        request_watering_authorization(
            getattr(self.ctx, "modal_overlay", None),
            title=f"Sugerir {metric}",
            lines=lines,
            cost_class=str(payload["cost_class"]),
            confirm_text="Autorizar y sugerir",
            on_confirm=lambda: self._launch_suggestion(payload, entity_id, metric),
        )

    def _launch_suggestion(self, payload: dict, entity_id: str, metric: str) -> None:
        """WIKI-08/13: prepara la Sugerencia en un hilo (navega la wiki + análisis de
        intención para arraigo/iluminada) y lanza la generación con el resultado.

        El plan viaja de vuelta como feedback (``plan_summary``) al indicador de estado."""
        svc = self.watering_service
        if svc is None:
            return
        analyzing = str(metric).lower() in _INTENT_METRICS_UI
        # Feedback inmediato: preparar puede tardar (hasta dos llamadas IA).
        self._job_status_label.setText(
            "Analizando la petición…" if analyzing else "Navegando la wiki…"
        )

        def _launch(prepared: dict) -> None:
            summary = str(prepared.get("plan_summary") or "").strip()
            status = f"Sugerir {metric} · {summary}" if summary else f"Sugerir {metric}…"
            self._launch_toolbar_ai_job(
                prepared["prompt"],
                status,
                prepared["job_type"],
                scope_override=prepared.get("context_scope"),
            )

        worker = _SuggestionPrepWorker(svc, entity_id, metric, payload.get("peticion", ""))

        def _on_prep(prepared: object) -> None:
            # Best-effort: si la preparación falló, cae al payload base de la autorización.
            use = prepared if isinstance(prepared, dict) and prepared.get("prompt") else payload
            _launch(use)

        worker.done.connect(_on_prep)
        worker.finished.connect(lambda: self._wiki_nav_workers.discard(worker))
        self._wiki_nav_workers.add(worker)
        track_worker(worker)
        worker.start()

    # ------------------------------------------------------------------
    # FOCO-14: Mapa solo lectura, Lente Jardín y riego por lotes desde el Mapa
    # ------------------------------------------------------------------

    def _on_map_entity_to_foco(self, entity_id: str) -> None:
        """Doble click en el Mapa → Foco con esa entidad como centro."""
        if not entity_id:
            return
        self.set_active_view("foco")
        foco_widget = getattr(self, "foco", None)
        if foco_widget is not None:
            foco_widget.center_entity(entity_id)

    def _focus_new_entity(self, entity_id: str) -> None:
        """BETA2-CLEANUP-PANELES: tras crear hoja/rama desde el Mapa, entrar en
        Modo Foco sobre la nueva entidad y abrir su editor Ficha. La edición ya
        no vive en el cajón derecho (retirado); vive en el Foco."""
        if not entity_id:
            return
        self.set_active_view("foco")
        foco_widget = getattr(self, "foco", None)
        if foco_widget is None:
            return
        foco_widget.center_entity(entity_id)
        open_editor = getattr(foco_widget, "open_editor", None)
        if callable(open_editor):
            open_editor()

    def _garden_status_map(self, entity_ids: list) -> dict:
        service = self.watering_service
        if service is None:
            return {}
        result = service.statuses_for(list(entity_ids))
        return getattr(result, "value", None) or {}

    # ------------------------------------------------------------------
    # BETA2-JARDIN-03: badge global «💧 N» y recorrido de sedientas
    # ------------------------------------------------------------------

    def _request_thirsty_refresh(self) -> None:
        """Recomputa el badge con debounce (~400 ms): nunca por evento crudo."""
        timer = getattr(self, "_thirsty_debounce", None)
        if timer is not None:
            timer.start()
        # BETA2-STRUCT-02: los ajustes estructurales comparten la misma cadencia.
        struct_timer = getattr(self, "_structural_debounce", None)
        if struct_timer is not None:
            struct_timer.start()

    @_qt_safe_slot
    def _refresh_thirsty_badge(self) -> None:
        layer = getattr(self, "_seed_notifications", None)
        if layer is None:
            return
        project = self._get_active_project()
        service = self.watering_service
        if project is None or service is None:
            layer.set_waterable([], [])
            return
        reports = getattr(service.statuses_for(None), "value", None) or {}
        # BETA2-FOCO-34: sedientas para el recorrido + regables (incl. regadas)
        # para que el badge no desaparezca y permita «Regar de nuevo».
        layer.set_waterable(thirsty_queue(project, reports), waterable_queue(project, reports))

    def _on_thirsty_requested(self, entity_id: str) -> None:
        """Clic en «💧»: Foco sobre la sedienta (recorrido, la más antigua 1º)."""
        if not entity_id:
            return
        self.set_active_view("foco")
        foco_widget = getattr(self, "foco", None)
        if foco_widget is not None:
            foco_widget.center_entity(entity_id)

    # ------------------------------------------------------------------
    # BETA2-STRUCT: ajustes estructurales (reubicación de anillos)
    # ------------------------------------------------------------------

    def _ensure_structure_badge(self):
        """Píldora ambiental «⚙ N ajustes estructurales» (perezosa, abre el panel)."""
        badge = getattr(self, "_float_structure", None)
        if badge is not None:
            return badge
        badge = QPushButton("", self)
        badge.setObjectName("structureBadge")
        badge.setToolTip("Revisar reubicaciones de anillo propuestas por potencial causal")
        try:
            badge.setCursor(Qt.PointingHandCursor)
        except Exception:  # noqa: BLE001 — el cursor no es crítico
            pass
        badge.clicked.connect(self._open_structure_panel)
        badge.hide()
        self._float_structure = badge
        return badge

    @_qt_safe_slot
    def _refresh_structural_badge(self) -> None:
        """Recomputa el contador determinista (coste IA cero) y actualiza la píldora.

        BETA2-STRUCT-08: entrada FIJA — la píldora está SIEMPRE visible con un proyecto
        cargado (aunque haya 0 ajustes), para que la función sea descubrible y el panel
        accesible; el texto refleja si hay o no propuestas.
        """
        svc = getattr(self, "structural_service", None)
        project = self._get_active_project()
        available = svc is not None and project is not None
        count = 0
        if available:
            try:
                count = svc.count()
            except Exception:  # noqa: BLE001 — el badge nunca rompe el flujo
                count = 0
        badge = self._ensure_structure_badge()
        if badge is None:
            return
        if not available:
            badge.setVisible(False)
            return
        if count > 0:
            texto = "1 ajuste estructural" if count == 1 else f"{count} ajustes estructurales"
            badge.setText(f"⚙ {texto}")
            badge.setProperty("hasItems", True)
        else:
            badge.setText("⚙ Estructura")
            badge.setProperty("hasItems", False)
        badge.setVisible(True)
        badge.adjustSize()
        self._position_floats()

    def _open_structure_panel(self) -> None:
        """Abre el panel de proyecto «Ajustes estructurales»."""
        svc = getattr(self, "structural_service", None)
        if svc is None:
            return
        from hosts.DesktopHostPySide.widgets.structure_review_panel import StructureReviewPanel

        panel = StructureReviewPanel(
            svc,
            on_accept=self._accept_structural_finding,
            on_close=self._close_structure_panel,
            log=self.ctx.log,
        )
        modal = getattr(self.ctx, "modal_overlay", None)
        if modal is not None:
            modal.open_widget(panel)
            return
        drawer = getattr(self.ctx, "drawer", None)
        if drawer is not None:
            drawer.set_content(panel, title="Ajustes estructurales")
            drawer.open()

    def _close_structure_panel(self) -> None:
        """Cierra el panel de ajustes estructurales (modal o cajón)."""
        modal = getattr(self.ctx, "modal_overlay", None)
        if modal is not None and getattr(modal, "is_open", False):
            try:
                modal.dismiss()
            except Exception:  # noqa: BLE001 — cerrar el modal no es crítico
                pass
        drawer = getattr(self.ctx, "drawer", None)
        if drawer is not None:
            try:
                drawer.close()
            except Exception:  # noqa: BLE001 — cerrar el cajón no es crítico
                pass

    def _accept_structural_finding(self, finding) -> None:
        """Materializa el hallazgo como Candidato y lo acepta por el pipeline existente."""
        svc = getattr(self, "structural_service", None)
        project = self._get_active_project()
        controller = getattr(self, "candidate_controller", None)
        if svc is None or project is None or controller is None:
            return
        candidate = svc.as_candidate(finding)
        project.candidates.append(candidate)
        result = controller.accept(candidate.id)
        if isinstance(result, Error):
            self.ctx.notify(getattr(result, "error", "No se pudo aplicar el ajuste"), "error")
            return
        # PERSISTIR: aceptar movió la entidad de anillo en memoria; hay que guardar
        # (como riego/sugerencias). Sin esto el cambio se perdía y "no pasaba nada".
        save = getattr(self.ctx, "request_save_silent", None)
        if callable(save):
            save()
        notify = getattr(self.ctx, "notify", None)
        if callable(notify):
            notify("Ajuste estructural aplicado", "success")
        # Reconstruye Mapa y Cronología COMPLETOS y AL INSTANTE, sin expulsar de la
        # vista actual (fix smoke): un ring_move reubica el nodo a otro anillo y un
        # ring_create/merge cambia/reordena las bandas. Se fuerza `full=True` porque
        # el atajo incremental dejaría el nodo en su anillo viejo; y la Cronología se
        # reconstruye aunque no esté activa (antes solo se rehacía si era la vista
        # visible, así que quedaba obsoleta). No se llama a `refresh()` porque este
        # arrastra `set_active_view("foco")` y sacaba al usuario del Mapa/Cronología.
        proj = self._get_active_project()
        try:
            if getattr(self, "graph", None) is not None:
                self.graph.refresh(full=True)
                self._graph_stale = False
        except (RuntimeError, TypeError):
            pass
        try:
            if getattr(self, "chrono", None) is not None:
                self.chrono.set_project(proj)
        except (RuntimeError, AttributeError):
            pass
        self._request_thirsty_refresh()
        self._refresh_structural_badge()

    # UI2-22: el drawer «Entidad (Mapa)» (_open_map_summary) se eliminó — era un
    # menú obsoleto que aparecía al clicar cualquier nodo del Mapa. Ahora el clic
    # simple solo selecciona y el doble clic abre en el Foco; el riego per-entidad/
    # anillo/grafo sigue en el badge global 💧, el rail del Foco y el clic derecho.

    # ------------------------------------------------------------------
    # FOCO-13: Semillas en Foco — germinación por zonas y chips no-visibles
    # ------------------------------------------------------------------

    def _pending_foco_candidates(self) -> list:
        """Candidatos PENDIENTES cuyo foco_hint apunta a la entidad enfocada."""
        controller = self.candidate_controller
        foco_widget = getattr(self, "foco", None)
        center = foco_widget.current_entity_id() if foco_widget is not None else ""
        if controller is None or not center:
            return []
        matched = []
        for cand in controller.list_all():
            state = getattr(cand, "state", None)
            if str(getattr(state, "value", state)) != "pendiente":
                continue
            metadata = getattr(cand, "metadata", None) or {}
            hint = (metadata.get("context_scope") or {}).get("foco_hint") or {}
            if str(hint.get("center_entity_id") or "") == center:
                matched.append(cand)
        return matched

    def _foco_visible_candidate_ids(self) -> set:
        """Ids de Semillas visibles en Foco AHORA (zona o tarjeta del drawer)."""
        if getattr(self, "_active_view", "") != "foco":
            return set()
        return {str(getattr(cand, "id", "")) for cand in self._pending_foco_candidates()}

    def _sync_foco_seeds(self) -> set:
        """Germina en su zona las Semillas de la entidad enfocada; las de
        edición textual van como tarjetas al drawer de riego. Devuelve los ids
        visibles (sus chips pulsantes no se duplican)."""
        foco_widget = getattr(self, "foco", None)
        if getattr(self, "_active_view", "") != "foco" or foco_widget is None:
            return set()
        zone_seeds: list[tuple] = []
        cards: list = []
        for cand in self._pending_foco_candidates():
            metadata = getattr(cand, "metadata", None) or {}
            hint = (metadata.get("context_scope") or {}).get("foco_hint") or {}
            zone = str(hint.get("zone") or "entorno")
            if zone == "drawer":
                cards.append(cand)
            else:
                zone_seeds.append(
                    (str(cand.id), zone, str(getattr(cand, "title", "") or "Semilla"))
                )
        foco_widget.canvas.sync_seeds(zone_seeds)
        panel = self._ensure_watering_panel()
        if panel is not None:
            panel.set_text_cards(cards)
        return {cid for cid, _zone, _title in zone_seeds} | {
            str(getattr(cand, "id", "")) for cand in cards
        }

    def _walk_bar_clicked(self) -> None:
        """CRON: botón de barra. Continúa el recorrido activo o, si no hay, lo
        inicia por el PRINCIPIO de la cronología (el hito más temprano)."""
        ctrl = self.chronology_walk_controller
        if ctrl is None:
            self.ctx.notify("Recorrido cronológico no disponible", "error")
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

    @_qt_safe_slot
    def _mark_graph_stale(self):
        # FOCO-19: mutación fuera del Mapa → reconstruir al volver a entrar.
        self._graph_stale = True
        self._request_thirsty_refresh()  # JARDIN-03: editar puede dar sed

    def view_toggle_widget(self) -> QWidget:
        """FOCO-28: la píldora de modos, para reparentarla al banner superior
        (main_window._wrap_space). Sigue siendo dueña de ``_mode_buttons``, así
        que ``_update_mode_pill`` mantiene el resaltado sin recablear."""
        return self._float_view_toggle

    # FOCO-28: orden del ciclo de modos con Tab/Shift+Tab (Play queda fuera).
    _MODE_CYCLE = ("foco", "concentric", "chrono")
    # Tipos de campo donde Tab conserva su recorrido nativo (no cambia de modo).
    _TAB_FIELD_TYPES = (
        QLineEdit,
        QTextEdit,
        QPlainTextEdit,
        QComboBox,
        QAbstractSpinBox,
        QAbstractItemView,
    )

    def _cycle_mode(self, delta: int) -> None:
        """FOCO-28: avanza/retrocede por los modos de Creación."""
        order = self._MODE_CYCLE
        current = self._active_view if self._active_view in order else order[0]
        self.set_active_view(order[(order.index(current) + delta) % len(order)])

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        """FOCO-28: Tab/Shift+Tab cambian de modo en toda la Creación. Se respeta
        el recorrido nativo de Tab dentro de campos (line/text/combo/spin/listas)
        y de diálogos ajenos al workspace."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if (
                key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and self.isVisible()
                and self._active_view in self._MODE_CYCLE
            ):
                fw = QApplication.focusWidget()
                blocked = fw is not None and (
                    not self.isAncestorOf(fw) or isinstance(fw, self._TAB_FIELD_TYPES)
                )
                if not blocked:
                    self._cycle_mode(1 if key == Qt.Key.Key_Tab else -1)
                    return True
        return super().eventFilter(obj, event)

    def set_active_view(self, view: str):
        """BETA2-FOCO: tres modos — "foco" (escritorio causal, PRINCIPAL) |
        "concentric" (Mapa global) | "chrono" (Cronología global).

        El arranque de la Creación entra SIEMPRE en foco; la vista activa ya no
        se persiste (BETA2-UX-02: escritura QSettings vestigial eliminada)."""
        view = str(view)
        if view not in ("foco", "concentric", "chrono", "play"):
            view = "foco"
        self._active_view = view
        chrono_on = view == "chrono"
        foco_on = view == "foco"
        play_on = view == "play"  # BETA2-PLAY: recorrido inmersivo (sin píldora)
        if chrono_on:
            self.chrono.set_project(self._get_active_project())
            self.chrono.fit_all()
        self.chrono.setVisible(chrono_on)
        # BETA2-UX-08: gutter «Sin ubicar» de la cronología (hitos sin año/fecha,
        # invisibles en la línea) — absorbe lo único que la vista-lista aportaba.
        self._refresh_chrono_gutter(chrono_on)
        # FOCO-19: si Foco mutó datos, el Mapa se reconstruye al entrar (la
        # cronología ya lo hace siempre vía set_project unas líneas arriba).
        if view == "concentric" and getattr(self, "_graph_stale", False):
            self.graph.refresh()
            self._graph_stale = False
        self.graph.setVisible(view == "concentric")
        foco_widget = getattr(self, "foco", None)
        if foco_widget is not None:
            # FOCO-26: mostrar ANTES de refrescar — el layout determinista del
            # lienzo lee el tamaño del viewport; refrescar oculto lo calculaba
            # con geometría rancia y el Foco aparecía descolocado al cambiar
            # desde el Mapa hasta un resize manual.
            foco_widget.setVisible(foco_on)
            if foco_on:
                foco_widget.refresh()
        # BETA2-PLAY: la vista inmersiva ocupa todo el workspace.
        play_widget = getattr(self, "play", None)
        if play_widget is not None:
            play_widget.setVisible(play_on)
        walk_btn = getattr(self, "_walk_toggle_btn", None)
        if walk_btn is not None:
            walk_btn.setVisible(chrono_on)  # CRON: entrada al recorrido solo en cronológica
        self._update_mode_pill(view)
        # UX25: transición suave (velo) solo entre las vistas de lienzo global.
        if view in ("concentric", "chrono"):
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
        # FOCO-13: la visibilidad de las Semillas depende de la vista — los
        # chips pulsantes se recalculan al cambiar de modo (idempotente).
        QTimer.singleShot(0, self._rehydrate_seed_notifications)

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
            self.ctx.notify("No se pudo abrir el detalle del hito", "error")
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
            # BETA2-SUB-01: doble-clic en un subhito → abre su propio panel.
            on_open_milestone=self._open_milestone_detail_panel,
        )
        drawer.set_content(panel, title="Hito")
        drawer.open()

    # ── CRON: Modo Creación Cronológica ──────────────────────────────────
    def _start_or_continue_walk(self, hito_id: str) -> None:
        """CRON: desde el grafo cronológico. Si hay un recorrido activo, lo
        reabre/continúa; si no, abre la configuración para iniciar uno nuevo."""
        ctrl = self.chronology_walk_controller
        if ctrl is None:
            self.ctx.notify("Recorrido cronológico no disponible", "error")
            return
        active = ctrl.active()
        if not isinstance(active, Error):
            # PLAY-04: hay un recorrido en curso → se reabre en la vista
            # inmersiva y se re-analiza el hito actual para repoblar la escena.
            self._walk_session_id = active.value.id
            ctrl.resume(active.value.id)
            self._open_play_view()
            self._run_walk_step()
            self.ctx.log("info", "Recorrido cronológico reanudado.")
            return
        self.start_chronology_walk(str(hito_id or ""))

    def start_chronology_walk(self, hito_id: str) -> None:
        """Abre el panel de configuración del recorrido para el hito dado."""
        drawer = getattr(self.ctx, "drawer", None)
        if self.chronology_walk_controller is None or drawer is None:
            self.ctx.notify("No se pudo iniciar el recorrido cronológico", "error")
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
            self.ctx.notify(res.error, "error")
            return
        self._walk_session_id = res.value.id
        self._open_play_view()
        self._run_walk_step()

    # ── BETA2-PLAY: vista inmersiva del recorrido ─────────────────────────
    def _open_play_view(self) -> None:
        """Entra en el modo Play y muestra la escena del hito actual."""
        drawer = getattr(self.ctx, "drawer", None)
        if drawer is not None:
            drawer.close()  # la config vivía en el cajón; la escena es a pantalla completa
        self.set_active_view("play")
        self._refresh_play_scene()

    @_qt_safe_slot
    def _exit_play(self) -> None:
        """Sale de Play sin terminar el recorrido (queda reanudable)."""
        self.set_active_view("chrono")

    def _play_scene_for(self, milestone_id: str | None = None) -> dict | None:
        """Escena determinista de un hito para Play (None si no es posible)."""
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return None
        res = ctrl.scene(sid, milestone_id)
        if isinstance(res, Error):
            self.ctx.log("warning", res.error)
            return None
        return res.value

    def _on_play_edit(self, milestone_id: str, patch: dict) -> None:
        """PLAY-06: edición inline de la escena → CausalMilestoneService."""
        if self._milestone_ctrl is None or not milestone_id:
            return
        res = self._milestone_ctrl.update(str(milestone_id), dict(patch or {}))
        if isinstance(res, Error):
            self.ctx.log("error", res.error)
            self._refresh_play_scene()  # revierte el eco local de la vista
            return
        self._mark_graph_stale()
        self._invalidate_play_prefetch()  # PLAY-08: la edición cambia canon
        self._refresh_play_scene()

    def _refresh_play_scene(self, milestone_id: str | None = None) -> None:
        """Alimenta la escena de Play con datos deterministas (sin IA)."""
        play = getattr(self, "play", None)
        if play is None:
            return
        scene = self._play_scene_for(milestone_id)
        if scene is None:
            return
        controller = getattr(self.ctx, "project_controller", None)
        current_path = getattr(controller, "current_path", None)
        play.set_assets_root(assets_root_for(Path(current_path)) if current_path else None)
        play.show_scene(scene)

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
        # PLAY-08: si el análisis del hito actual ya llegó por prefetch, se
        # pliega al instante (commit_step) y no se lanza ningún hilo.
        active = ctrl.active()
        mid_now = (
            str(getattr(active.value, "current_milestone_id", "") or "")
            if not isinstance(active, Error)
            else ""
        )
        if self._active_view == "play" and mid_now:
            cached = self._play_prefetch_cache.pop(mid_now, None)
            if cached is not None:
                committed = ctrl.commit(sid, mid_now, cached)
                if not isinstance(committed, Error):
                    self._clear_walk_step_seeds()
                    self._walk_step_candidate_ids = []
                    self._refresh_play_scene()
                    self._on_walk_step_done(committed.value)
                    return
            prefetching = self._play_prefetch_worker
            if _qt_alive(prefetching) and prefetching.isRunning():
                self._refresh_play_scene()
                self.play.set_busy(True)
                if (
                    prefetching.milestone_id == mid_now
                    and prefetching.epoch == self._play_epoch
                ):
                    # El prefetch en vuelo ES este paso: se adopta su resultado.
                    self._walk_analyzing = True
                    self._play_adopt_step = True
                    self._start_walk_watchdog()
                else:
                    # Prefetch rancio en vuelo: NUNCA dos análisis vivos — el
                    # paso se relanza cuando ese hilo termine (epoch lo descarta).
                    self._play_step_queued = True
                return
        self._walk_analyzing = True
        # Semillas transitorias: limpia las del paso anterior antes de analizar el nuevo.
        self._clear_walk_step_seeds()
        self._walk_step_candidate_ids = []
        # Hito actual (antes de analizar): la cámara se enfoca y emite un PULSO
        # sostenido desde su posición mientras la IA trabaja.
        if mid_now:
            try:
                self.chrono.start_walk_pulse(mid_now)
            except Exception:  # noqa: BLE001 — la animación no es crítica
                pass
        # PLAY-04: en la vista inmersiva, la escena del hito actual se muestra
        # ya (datos deterministas) mientras la IA analiza en segundo plano.
        if self._active_view == "play":
            self._refresh_play_scene()
            self.play.set_busy(True)
        # Análisis en hilo aparte para no congelar la UI durante la llamada al modelo.
        # PLAY-12: cada intento captura su token; un resultado con token viejo
        # (el usuario reintentó) muere en la guarda de _on_walk_step_done/_failed.
        self._walk_step_token += 1
        worker = _WalkStepWorker(ctrl, sid)
        worker.finishedOk.connect(
            lambda result, token=self._walk_step_token: self._on_walk_step_done(result, token)
        )
        worker.failed.connect(
            lambda error, token=self._walk_step_token: self._on_walk_step_failed(error, token)
        )
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
        """PLAY-12: la llamada tarda — avisar SIN cancelar (decisión del smoke).

        El worker sigue vivo y su resultado sigue siendo bienvenido (nada de
        mensajes contradictorios); el usuario puede seguir esperando o pulsar
        «Reintentar», que descarta el intento en vuelo por token.
        """
        self._walk_watchdog = None
        if not self._walk_analyzing:
            return
        self.ctx.log("info", "El análisis del hito está tardando más de lo normal.")
        if self._active_view == "play":
            self.play.show_waiting_notice(
                "La IA está tardando más de lo normal; puedes seguir esperando o reintentar."
            )

    @_qt_safe_slot
    def _on_walk_step_done(self, result, token=None) -> None:
        # PLAY-12: intento descartado por «Reintentar» — el resultado tardío
        # de un token viejo no debe pisar el estado del intento vigente.
        if token is not None and token != self._walk_step_token:
            return
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
        # PLAY-04: la escena inmersiva pliega el análisis (congela ante duros).
        if self._active_view == "play":
            self.play.show_analysis(result)
            # PLAY-07: los candidatos del paso son tarjetas aceptar/rechazar.
            self.play.set_changes(self._build_step_changes(self._walk_step_candidate_ids))
            # PLAY-08: mientras se lee esta escena, la siguiente ya se analiza.
            self._maybe_prefetch_next()
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
            elif isinstance(pd.get("edit_fields"), dict) and pd.get("edit_fields"):
                # PLAY-17: propuesta de edición multi-campo → revisable en el
                # preview del panel real. Se resuelve el objetivo para montarlo.
                edit_kind = str(pd.get("edit_kind") or "entity_edits")
                target_id, target_name = self._resolve_edit_target(project, pd)
                changes.append(
                    {
                        "candidate_id": cid,
                        "kind": "edit",
                        "apply": "flat",
                        "reviewable": bool(target_id),
                        "edit_kind": edit_kind,
                        "target_id": target_id,
                        "target_name": target_name,
                        "edit_fields": dict(pd.get("edit_fields") or {}),
                        "header": str(getattr(cand, "title", None) or "Editar canon"),
                        "fields": [],
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

    @staticmethod
    def _resolve_edit_target(project, pd: dict) -> tuple[str, str]:
        """PLAY-17: (id, nombre) del objetivo de una edición multi-campo.

        Los hitos se resuelven por id estable primero (renombrados no rompen);
        las entidades por nombre. id vacío ⇒ no montable en preview.
        """
        kind = str(pd.get("edit_kind") or "entity_edits")
        name = str(pd.get("edit_target_name") or "").strip()
        if kind == "milestone_edits":
            tid = str(pd.get("edit_target_id") or "").strip()
            for m in getattr(project, "causal_milestones", []) or []:
                if tid and str(getattr(m, "id", "")) == tid:
                    return str(m.id), str(getattr(m, "title", ""))
            low = name.lower()
            for m in getattr(project, "causal_milestones", []) or []:
                if str(getattr(m, "title", "")).strip().lower() == low:
                    return str(m.id), str(getattr(m, "title", ""))
            return "", name
        low = name.lower()
        for e in getattr(project, "entities", []) or []:
            if str(getattr(e, "name", "")).strip().lower() == low:
                return str(e.id), str(getattr(e, "name", ""))
        return "", name

    def _build_proposal_preview(self, descriptor: dict):
        """PLAY-17: monta el panel de edición REAL en modo preview.

        Devuelve ``(widget, get_payload)``: el panel con el patch de la IA
        aplicado y un callable que da el diff editado. La UI no escribe canon —
        el guardado del panel queda neutralizado (``on_preview_save`` no-op) y
        el diff se lee bajo demanda al aceptar.
        """
        edit_kind = str(descriptor.get("edit_kind") or "entity_edits")
        target_id = str(descriptor.get("target_id") or "")
        patch = dict(descriptor.get("edit_fields") or {})
        if not target_id:
            return None
        if edit_kind == "milestone_edits":
            from hosts.DesktopHostPySide.widgets.milestone_detail_panel import (
                MilestoneDetailPanel,
            )

            if self._milestone_ctrl is None:
                return None
            panel = MilestoneDetailPanel(
                self.ctx,
                self._milestone_ctrl,
                target_id,
                project_getter=self._get_active_project,
                preview_patch=patch,
                on_preview_save=lambda _payload: None,
            )
            return panel, panel.preview_payload
        from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

        panel = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            target_id,
            variant="foco",
            preview_patch=patch,
            on_preview_save=lambda _payload: None,
        )
        panel.refresh()  # NodeDetailPanel no auto-carga en __init__
        return panel, panel.preview_payload

    @_qt_safe_slot
    def _on_walk_apply(self, items: list) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        # No aplicar mientras un análisis sigue vivo (evita mutar el proyecto desde
        # el hilo de UI a la vez que el worker lo toca).
        if self._walk_analyzing:
            self.ctx.log("info", "Espera a que termine el análisis para aplicar.")
            return
        res = ctrl.apply_step(sid, list(items or []))
        if isinstance(res, Error):
            self.ctx.notify(res.error, "error")
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
        # PLAY-07: aplicar resuelve el paso → la escena se descongela y refleja
        # el canon nuevo (refresh primero; mark_applied repone el estado del ciclo).
        self._invalidate_play_prefetch()  # PLAY-08: aplicar cambia canon
        if self._active_view == "play":
            self._refresh_play_scene()
            self.play.mark_applied(len(applied))
            self._maybe_prefetch_next()  # re-anticipa el siguiente con el canon nuevo
        # Aplicar SÍ cambia canon → refresco completo (grafo + cronología).
        self._refresh_after_walk()

    @_qt_safe_slot
    def _on_walk_step_failed(self, error: str, token=None) -> None:
        if token is not None and token != self._walk_step_token:
            return  # PLAY-12: fallo de un intento ya descartado
        self._walk_analyzing = False
        self._stop_walk_watchdog()
        try:
            self.chrono.stop_walk_pulse()
        except Exception:  # noqa: BLE001
            pass
        self.ctx.log("error", str(error))
        # PLAY-04: sin proveedor/fallo, la escena sigue legible y navegable.
        if self._active_view == "play":
            # WS-K: error HUMANIZADO (401/403/timeout/…) como el resto de la app, no el
            # string crudo del proveedor en medio de la escena inmersiva.
            self.play.show_error(_human_ai_error(str(error)))
            if (
                self.ai_job_service is not None
                and self.ai_job_service.provider_unconfigured()
                and not getattr(self, "_ai_config_hint_shown", False)
            ):
                self._ai_config_hint_shown = True
                self._show_ai_config_help()

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
        controller = self.candidate_controller
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
            # PLAY-04: el bloqueo por problema duro es un estado visible, no silencio.
            if self._active_view == "play":
                self.play.show_error(res.error)
            return
        session = res.value
        status = str(getattr(getattr(session, "status", ""), "value", "") or "")
        if status == "completed":
            self._open_walk_report(sid)
            return
        self._run_walk_step()

    # ── PLAY-08: prefetch del paso N+1 ────────────────────────────────────
    def _invalidate_play_prefetch(self) -> None:
        """El canon cambió: todo análisis anticipado (cacheado o en vuelo) es
        rancio. Aplazar o avanzar NO invalidan (no tocan canon)."""
        self._play_epoch += 1
        self._play_prefetch_cache.clear()

    def _maybe_prefetch_next(self) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if self._active_view != "play" or ctrl is None or not sid:
            return
        if self._walk_analyzing:
            return  # regla (a): nunca dos análisis vivos
        worker = self._play_prefetch_worker
        if _qt_alive(worker) and worker.isRunning():
            return
        scene = self._play_scene_for(None)
        next_mid = str((scene or {}).get("next_milestone_id") or "")
        if not next_mid or next_mid in self._play_prefetch_cache:
            return
        worker = _PlayPrefetchWorker(ctrl, sid, next_mid, self._play_epoch)
        worker.finishedOk.connect(self._on_prefetch_done)
        worker.failed.connect(self._on_prefetch_failed)
        worker.finished.connect(self._on_prefetch_worker_stopped)
        self._play_prefetch_worker = worker
        self._walk_workers.add(worker)  # keep-alive hasta que termine
        track_worker(worker)  # apagado ordenado al cerrar la app
        worker.start()

    @_qt_safe_slot
    def _on_prefetch_done(self, milestone_id, epoch, result) -> None:
        milestone_id = str(milestone_id)
        if int(epoch) != self._play_epoch:
            # Canon cambiado en vuelo: resultado rancio. Si era el paso adoptado,
            # se relanza el análisis con el canon vigente.
            if self._play_adopt_step:
                self._play_adopt_step = False
                self._walk_analyzing = False
                self._stop_walk_watchdog()
                self._run_walk_step()
            return
        if self._play_adopt_step:
            self._play_adopt_step = False
            ctrl = self.chronology_walk_controller
            sid = self._walk_session_id
            if ctrl is None or not sid:
                self._walk_analyzing = False
                return
            committed = ctrl.commit(sid, milestone_id, dict(result or {}))
            if isinstance(committed, Error):
                self._on_walk_step_failed(committed.error)
                return
            self._clear_walk_step_seeds()
            self._walk_step_candidate_ids = []
            self._on_walk_step_done(committed.value)
            return
        self._play_prefetch_cache[milestone_id] = dict(result or {})

    @_qt_safe_slot
    def _on_prefetch_failed(self, error: str) -> None:
        if self._play_adopt_step:
            self._play_adopt_step = False
            self._on_walk_step_failed(str(error))
            return
        # El prefetch es mejor-esfuerzo: al llegar de verdad, análisis normal.
        self.ctx.log("info", f"Prefetch del siguiente hito falló: {error}")

    @_qt_safe_slot
    def _on_prefetch_worker_stopped(self) -> None:
        worker = self._play_prefetch_worker
        if worker is not None and (not _qt_alive(worker) or not worker.isRunning()):
            self._play_prefetch_worker = None
        self._walk_workers = {w for w in self._walk_workers if _qt_alive(w) and w.isRunning()}
        if self._play_step_queued:
            self._play_step_queued = False
            if not self._walk_analyzing:
                self._run_walk_step()

    @_qt_safe_slot
    def _retry_walk_step(self) -> None:
        """PLAY-12: descarta el análisis en vuelo (token) y relanza el paso."""
        self._walk_step_token += 1  # el resultado del intento viejo muere en la guarda
        self._walk_analyzing = False
        self._play_adopt_step = False
        self._stop_walk_watchdog()
        self._run_walk_step()

    def _defer_walk(self) -> None:
        """PLAY-07: aplazar los problemas del hito actual (PLAY-02 en el servicio)."""
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        res = ctrl.defer(sid)
        if isinstance(res, Error):
            self.ctx.log("warning", res.error)
            if self._active_view == "play":
                self.play.show_error(res.error)
            return
        self.ctx.log("info", "Problemas aplazados; reaparecerán en el informe final.")
        if self._active_view == "play":
            self.play.mark_deferred()

    def _decide_walk(self, decision: str) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        res = ctrl.decide(sid, str(decision))
        if isinstance(res, Error):
            self.ctx.notify(res.error, "error")
            return
        self.ctx.log("info", "Decisión registrada; puedes avanzar.")

    def _stop_walk(self) -> None:
        ctrl = self.chronology_walk_controller
        sid = self._walk_session_id
        if ctrl is None or not sid:
            return
        res = ctrl.stop(sid)
        if isinstance(res, Error):
            self.ctx.notify(res.error, "error")
            return
        self._open_walk_report(sid)

    def _open_walk_report(self, session_id: str) -> None:
        ctrl = self.chronology_walk_controller
        if ctrl is None:
            return
        project = self._get_active_project()
        report = None
        for rep in getattr(project, "chronology_walk_reports", []) or []:
            if str(getattr(rep, "session_id", "")) == str(session_id):
                report = rep
        if report is None:
            return
        # Cierre del recorrido: retira las semillas del último paso y el resalte.
        self._clear_walk_step_seeds()
        self._walk_step_candidate_ids = []
        self._walk_session_id = None
        self._walk_analyzing = False
        self._stop_walk_watchdog()
        self._play_prefetch_cache.clear()
        try:
            self.chrono.clear_walk_highlight()
        except Exception:  # noqa: BLE001
            pass
        # PLAY-09/10: el informe SIEMPRE es el epílogo inmersivo de Play; el
        # botón «Volver al lienzo» (exitRequested) devuelve a la Cronología.
        if getattr(self, "_active_view", "") != "play":
            self.set_active_view("play")
        self.play.show_epilogue(report, project)

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
        # PLAY-13: dentro de Play, JAMÁS el refresco completo — `refresh()`
        # fuerza la vista Foco y expulsaba al usuario del recorrido al aplicar.
        # Mismo contrato que la edición inline (PLAY-06): grafo marcado stale
        # (se reconstruye al salir de Play) + refresco ligero de la cronología.
        if getattr(self, "_active_view", "") == "play":
            self._mark_graph_stale()
            self._refresh_chrono_only()
            return
        # Refresco COMPLETO (tras aplicar: canon cambió). Incluye grafo, semillas
        # y cronología; re-enfoca el hito actual para mantener el contexto.
        try:
            self._on_suggestion_changed()
        except Exception:  # noqa: BLE001
            pass
        self._refresh_chrono_only()

    def _on_chrono_create_milestone(
        self,
        default_year: int,
        era_name: str,
        extra_payload: dict | None = None,
        default_end_year: int | None = None,
    ) -> None:
        """BETA1-HITO-MULTI: clic derecho sobre una era en la cronología →
        muestra el panel de creación como overlay DENTRO de la app (ModalOverlay,
        no una ventana del SO). Al confirmar, crea el hito por el controller.
        ``extra_payload`` se fusiona al payload confirmado (FOCO-25: vincular);
        ``default_end_year`` precarga el fin (FOCO-26: rango dibujado en banda)."""
        if self._milestone_ctrl is None:
            return
        extra = dict(extra_payload or {})
        chrono_meta = {}
        chron = getattr(self._get_active_project(), "project_chronology", None)
        cal = getattr(chron, "metadata", None)
        if isinstance(cal, dict):
            chrono_meta = cal
        panel = MilestoneQuickCreatePanel(
            default_year=int(default_year),
            calendar_meta=chrono_meta,
            era_name=str(era_name or ""),
            default_end_year=default_end_year,
        )
        overlay = getattr(self.window(), "modal_overlay", None)
        if overlay is None:  # respaldo defensivo: crea con el año sugerido
            self._create_milestone_from_payload(
                {"title": "Nuevo hito", "year": int(default_year), **extra}
            )
            return
        panel.cancelled.connect(overlay.dismiss)
        panel.submitted.connect(
            lambda payload: (
                overlay.dismiss(),
                self._create_milestone_from_payload({**payload, **extra}),
            )
        )
        overlay.open_widget(panel)

    def _on_foco_create_milestone(self, default_year: int, era_name: str) -> None:
        """FOCO-25: un hito creado desde la banda local del Foco nace VINCULADO
        a la entidad en foco (affected_entity_ids) — antes se creaba suelto y
        ``list_for_leaf`` no lo devolvía, así que jamás aparecía en la banda."""
        foco = getattr(self, "foco", None)
        center_id = str(foco.current_entity_id() or "") if foco is not None else ""
        self._on_chrono_create_milestone(
            default_year,
            era_name,
            extra_payload={"affected_entity_ids": [center_id]} if center_id else None,
        )

    def _on_foco_create_milestone_range(self, start_year: int, end_year: int) -> None:
        """FOCO-26: rango dibujado en la banda local ⇒ hito con inicio y fin,
        vinculado a la entidad en foco."""
        foco = getattr(self, "foco", None)
        center_id = str(foco.current_entity_id() or "") if foco is not None else ""
        self._on_chrono_create_milestone(
            start_year,
            "",
            extra_payload={"affected_entity_ids": [center_id]} if center_id else None,
            default_end_year=int(end_year),
        )

    @_qt_safe_slot
    def _create_milestone_from_payload(self, payload: dict) -> None:
        """Crea el hito por el controller (la UI nunca escribe persistencia
        directa), lo hace germinar y refresca. Nace como candidato revisable."""
        if self._milestone_ctrl is None:
            return
        result = self._milestone_ctrl.create_manual(dict(payload or {}))
        if isinstance(result, Error):
            self.ctx.notify(result.error, "error")
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
                # BETA2-FOCO-27: si el hito se creó desde el editor del Foco
                # («+ hito» en la cronología editable), ábrelo en el cajón inferior
                # para editarlo al momento.
                foco = getattr(self, "foco", None)
                if (
                    foco is not None
                    and callable(getattr(foco, "is_editor_open", None))
                    and foco.is_editor_open()
                ):
                    foco.open_milestone_editable(milestone_id)

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
            self.ctx.notify(result.error, "error")
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
            self.ctx.notify(result.error, "error")
            return
        # BETA1-UX2D (crash): refresh() reconstruye la escena cronológica
        # (scene.clear()). Esta señal se emite DENTRO del mouseReleaseEvent de la
        # cronología, así que borrar aquí los items —incluido el que Qt está
        # entregando el evento— es un use-after-free (la línea "desaparece" y al
        # volver a la vista crashea). Se difiere al siguiente ciclo del event loop,
        # cuando el evento ya se ha desenrollado por completo.
        _qt_safe_timer(self, 0, self.refresh)

    @_qt_safe_slot
    def _build_chrono_gutter(self) -> QFrame:
        # BETA2-UX-08: overlay lateral con los hitos «Sin ubicar» de la
        # cronología. Clic → panel de detalle del hito (misma ruta que el lienzo).
        frame = QFrame(self)
        frame.setObjectName("chronoUnplacedGutter")
        frame.setStyleSheet(
            f"QFrame#chronoUnplacedGutter {{ background: {SURFACE_HI}; "
            f"border: 1px solid {LINE}; border-radius: 12px; }}"
        )
        frame.setFixedWidth(214)
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(6)
        self._chrono_gutter_count = QLabel("Sin ubicar")
        self._chrono_gutter_count.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        v.addWidget(self._chrono_gutter_count)
        hint = QLabel("Hitos sin año ni fecha — no aparecen en la línea.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {INK_MUTED}; font-size: {TYPE_CAPTION_PX}px; "
            f"background: transparent; border: none;"
        )
        v.addWidget(hint)
        self._chrono_gutter_list = QListWidget()
        self._chrono_gutter_list.setMaximumHeight(220)
        self._chrono_gutter_list.itemClicked.connect(
            lambda it: self._open_milestone_detail_panel(
                str(it.data(Qt.ItemDataRole.UserRole) or "")
            )
        )
        v.addWidget(self._chrono_gutter_list)
        return frame

    def _refresh_chrono_gutter(self, chrono_on: bool) -> None:
        """BETA2-UX-08: puebla/oculta el gutter «Sin ubicar». Solo visible en
        cronología y si hay hitos sin ubicación temporal."""
        gutter = getattr(self, "_chrono_gutter", None)
        if not chrono_on or self._milestone_ctrl is None:
            if gutter is not None:
                gutter.setVisible(False)
            return
        try:
            hitos = list(self._milestone_ctrl.list_all() or [])
        except Exception:  # noqa: BLE001
            hitos = []
        unplaced = [h for h in hitos if milestone_temporal_label(h) == "Sin ubicar"]
        if gutter is None:
            gutter = self._build_chrono_gutter()
            self._chrono_gutter = gutter
        self._chrono_gutter_list.clear()
        for hito in unplaced:
            item = QListWidgetItem(str(getattr(hito, "title", "") or "Hito sin título"))
            item.setData(Qt.ItemDataRole.UserRole, str(getattr(hito, "id", "")))
            self._chrono_gutter_list.addItem(item)
        self._chrono_gutter_count.setText(f"Sin ubicar · {len(unplaced)}")
        gutter.setVisible(bool(unplaced))
        if unplaced:
            self._position_floats()

    def _position_floats(self):
        """Coloca los clusters flotantes y el breadcrumb de foco arriba a la
        izquierda."""
        # R6: raised and static — aligned with the chronology toggle, no sway.
        # BETA2-WIKI-10: la command bar se retiró (era el ancla de `top`). Antes esta
        # función hacía `return` si no existía y dejaba la píldora Guardar/💧 y la
        # leyenda del jardín en (0,0) — arriba-izquierda. Sin command bar, `top` se
        # ancla abajo-derecha (como el resto de floats del Mapa).
        top = max(58, self.height() - 62)
        # BETA2-UX-08: gutter «Sin ubicar» arriba-derecha, bajo la píldora de modos.
        gutter = getattr(self, "_chrono_gutter", None)
        if gutter is not None and gutter.isVisible():
            gutter.adjustSize()
            gutter.move(self.width() - gutter.width() - 18, 58)
            gutter.raise_()
        right = getattr(self, "_float_right", None)
        if right is not None:
            right.adjustSize()
            right.move(self.width() - right.width() - 18, top)
            right.raise_()
        # BETA2-FOCO-28: la barra de modos ya NO flota aquí — vive en el banner
        # superior (main_window._wrap_space la reparenta). El Mapa recupera el
        # borde superior para su barra temporal (sin píldora que esquivar).
        graph = getattr(self, "graph", None)
        if graph is not None and hasattr(graph, "set_time_bar_top_inset"):
            graph.set_time_bar_top_inset(10)
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
        # BETA2-STRUCT-02: píldora de ajustes estructurales, abajo-izquierda.
        struct = getattr(self, "_float_structure", None)
        if struct is not None and struct.isVisible():
            struct.adjustSize()
            struct.move(18, max(58, self.height() - struct.height() - 16))
            struct.raise_()
        # SEM04: la capa de semillas se ancla encima del cluster derecho.
        self._position_seed_layer()
        # BETA2-WIKI-10: recoloca el floater de estado de IA (abajo-centro) al redimensionar.
        self._sync_status_floater()

    @_qt_safe_slot
    def _position_seed_layer(self):
        """SEM04: ancla las notificaciones de semilla JUSTO ENCIMA del cluster
        de botones derecho (con z-order por encima), para que no los solapen ni
        intercepten sus clics."""
        layer = getattr(self, "_seed_notifications", None)
        if layer is None or (not layer.notifications and not layer.thirsty_ids):
            self._update_garden_legend_inset()
            return
        layer.adjustSize()
        right = getattr(self, "_float_right", None)
        margin = 18
        if right is not None:
            x = right.x() + right.width() - layer.width()
            y = right.y() - layer.height() - 10
        else:
            top = self.height() - 134
            x = self.width() - layer.width() - margin
            y = top - layer.height() - 10
        layer.move(max(0, x), max(0, y))
        layer.reanchor()  # show + raise por encima de los clusters
        self._update_garden_legend_inset()

    def _update_garden_legend_inset(self):
        """UI2-02: reserva hueco bajo la leyenda del jardín (esquina inferior
        derecha del Mapa) para que quede apilada ENCIMA de las píldoras 🌱/💧
        y del cluster derecho sin solaparlos."""
        graph = getattr(self, "graph", None)
        if graph is None or not hasattr(graph, "set_garden_legend_bottom_inset"):
            return
        tops: list[int] = []
        right = getattr(self, "_float_right", None)
        if right is not None and right.isVisible():
            tops.append(right.y())
        layer = getattr(self, "_seed_notifications", None)
        if layer is not None and layer.isVisible():
            tops.append(layer.y())
        if not tops:
            graph.set_garden_legend_bottom_inset(0)
            return
        inset = max(0, graph.geometry().bottom() - min(tops)) + 10
        graph.set_garden_legend_bottom_inset(inset)

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._position_floats()
        # FOCO-28: filtro de app para Tab/Shift+Tab de modos (los lienzos toman el
        # foco, así que un QShortcut de widget no bastaría). Se retira en hideEvent.
        if not getattr(self, "_tab_filter_installed", False):
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
                self._tab_filter_installed = True

    def hideEvent(self, event):  # noqa: N802 (Qt API)
        # FOCO-28: retira el filtro de Tab al ocultar la Creación (simétrico a
        # showEvent), para no interceptar Tab desde otras superficies (Home).
        if getattr(self, "_tab_filter_installed", False):
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._tab_filter_installed = False
        super().hideEvent(event)

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
            self.ctx.notify("No hay proyecto que guardar", "error")
            return
        result = pc.save()
        if hasattr(result, "error"):
            self.ctx.notify(f"Error guardando: {result.error}", "error")
        else:
            self.ctx.log("info", "Proyecto guardado")

    # Alto fijo de la command bar inferior. Lo usa MainWindow para reservar ese
    # margen al fondo y que los cajones overlay terminen JUSTO encima de la barra
    # (en vez de taparla). Constante compartida → sin número mágico duplicado.
    COMMAND_BAR_HEIGHT = 68

    def _project_service(self):
        """Resolve the active ProjectService (used to build narrative context)."""
        project_controller = getattr(self.ctx, "project_controller", None)
        return getattr(project_controller, "ps", None)

    def _load_project_budget_default(self) -> None:
        """PA02: el budget tuner arranca en Auto (presupuesto por tier de la
        tarea), así que ya no se fuerza el default del proyecto al cambiar de
        proyecto. Se conserva como hook no-op por compatibilidad de llamadas."""
        return

    # B38 persistent layer drawer

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
            self.ctx.notify("La vista de anillos requiere Worldbuilding activado", "error")
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
            self.ctx.notify("Abre o crea un proyecto para usar la vista concéntrica", "error")
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

    def _launch_toolbar_ai_job(
        self,
        prompt: str,
        status_text: str,
        job_type: "AIJobType | str",
        scope_override: dict | None = None,
    ) -> bool:
        project = self._get_active_project()
        if project is None:
            self.ctx.notify("No hay proyecto activo", "error")
            return False
        # BETA2-WIKI-11: `_current_context_scope` se eliminó con la command bar; los
        # callers vivos (Sugerencias) SIEMPRE pasan scope_override.
        scope = dict(scope_override) if scope_override is not None else {}
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
        # SHIP-07: el visor de prompts RAG es una herramienta de DEPURACIÓN. En la
        # beta el store está deshabilitado por defecto, así que no salta al
        # navegador una pestaña técnica «Dendro RAG Prompt Debug» en cada
        # Sugerencia. Un dev lo reactiva con un store enabled=True.
        if store is None or not getattr(store, "enabled", False):
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
        self._schedule_status_clear()  # WIKI-13: no dejar el resultado fijo abajo-centro
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
        controller = self.candidate_controller
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
            label = str(getattr(candidate, "title", "") or "Semilla")
            # FOCO-13: si la Semilla pertenece a la entidad enfocada (foco_hint),
            # germina en su zona/drawer y NO duplica chip pulsante.
            hint = ((data.get("metadata") or {}).get("context_scope") or {}).get("foco_hint") or {}
            visible_in_foco = (
                getattr(self, "_active_view", "") == "foco"
                and getattr(self, "foco", None) is not None
                and str(hint.get("center_entity_id") or "") == self.foco.current_entity_id()
            )
            if not visible_in_foco:
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
        self._sync_foco_seeds()  # FOCO-13: germinación espacial en el lienzo de Foco
        return created_ids

    @_qt_safe_slot
    def _on_ai_job_failed(self, job_id: str, error: str):
        self._stop_edit_germination(job_id)  # UX5: cesa el latido de germinación
        # SHIP-01: al usuario le llega el error humanizado (401/403/timeout/…); el
        # crudo se conserva en ctx.log para depurar.
        friendly = _human_ai_error(error)
        self._job_status_label.setText(f"⚠ {friendly}")
        self._job_status_label.setStyleSheet("color: #C0392B; font-size: 11px; font-weight: 700;")
        pulse_feedback(self._job_status_label)
        self._schedule_status_clear(9000)  # WIKI-13: el error también se limpia (más tarde)
        self.ctx.log("error", f"Job IA fallido {job_id}: {error}")
        self._sync_jobs_indicator()
        self._refresh_ai_jobs_panel_if_open()
        # SEM04: la semilla germinante se marchita al fallar el job.
        self.graph.wither_seed(job_id)
        # PA-Semillas: notificación de error (se descarta al pulsarla).
        self._seed_notifications.add(f"error:{job_id}", friendly, kind="error")
        # K02/fila32: si el fallo es por falta de proveedor IA, ofrecer instrucciones
        # accionables (una vez por sesión, no en cada intento).
        if self.ai_job_service.provider_unconfigured() and not getattr(
            self, "_ai_config_hint_shown", False
        ):
            self._ai_config_hint_shown = True
            self._show_ai_config_help()
        # Clear error styling after 8 seconds so it doesn't persist forever
        QTimer.singleShot(8000, self._reset_job_status_style)

    def _warn_ai_unconfigured(self, accion: str) -> None:
        """SHIP-01: aviso VISIBLE al pedir una función de IA sin proveedor.

        Antes esto iba solo a ctx.log, cuyo panel está oculto: el botón parecía
        muerto. Ahora: toast de error + diálogo accionable con acceso a Ajustes."""
        self.ctx.notify(f"IA no configurada: no se puede {accion}.", kind="error")
        self._show_ai_config_help()

    def _show_ai_config_help(self) -> None:
        """SHIP-01: ayuda accionable para configurar un proveedor de IA in-app.
        Dendro funciona sin IA; estas funciones quedan inactivas hasta configurarla."""
        box = QMessageBox(self)
        box.setWindowTitle("Configura la IA")
        box.setText(
            "No hay un proveedor de IA configurado, así que Dendro no generará contenido.\n\n"
            "En Ajustes de IA elige un proveedor compatible con OpenAI (URL, modelo y "
            "API key) y pulsa «Probar conexión». El cambio se aplica al momento, sin "
            "reiniciar.\n\n"
            "Dendro funciona sin IA; solo regar, sugerencias y Play la necesitan."
        )
        open_settings = getattr(self.ctx, "open_ai_settings", None)
        open_btn = None
        if callable(open_settings):
            open_btn = box.addButton("Abrir Ajustes de IA", QMessageBox.AcceptRole)
        box.addButton("Cerrar", QMessageBox.RejectRole)
        box.exec()
        if open_btn is not None and box.clickedButton() is open_btn:
            open_settings()

    @_qt_safe_slot
    def _reset_job_status_style(self):
        self._job_status_label.setStyleSheet(
            f"color: {INK_OLIVE}; font-size: 11px; background: transparent; border: none;"
        )
        # Only reset text if it's still showing an error
        current = self._job_status_label.text()
        if current.startswith(("Error:", "⚠")):
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

    def _refresh_ai_jobs_panel_if_open(self):
        # BETA2-WIKI-11: el panel «Tareas IA» (AIJobsPanel) se eliminó con la
        # superficie IA legada. Hook no-op: el pipeline compartido de jobs lo
        # sigue invocando en sus transiciones de estado.
        return

    def _sync_jobs_indicator(self):
        # BETA2-WIKI-11: el botón «Tareas» de la toolbar se eliminó con la
        # superficie IA legada. Hook no-op invocado por el pipeline compartido.
        return

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
        # PLAY-10: durante un recorrido, la notificación de un candidato del
        # paso actual reabre la vista Play (tarjetas del paso + aplicación
        # atómica), no el panel por-candidato suelto (evita aceptación
        # desordenada).
        if self._walk_session_id and str(candidate_id) in (self._walk_step_candidate_ids or []):
            self._open_play_view()
            return
        candidate = self._find_candidate(candidate_id)
        controller = self.candidate_controller
        if candidate is None or controller is None:
            self.ctx.notify("No se pudo abrir la revisión de la semilla", "error")
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
            self.ctx.notify("No se pudo abrir la revisión de la semilla", "error")

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
        controller = self.candidate_controller
        cs = getattr(controller, "cs", None) if controller else None
        # Mismo proyecto e idénticos servicios que usa la aceptación de candidatos:
        # entidades, relaciones e hitos quedan en la misma instancia de proyecto.
        project = getattr(controller, "ps", None).active_project if controller else None
        entity_service = getattr(cs, "entity_service", None) if cs else None
        relation_service = getattr(cs, "relation_service", None) if cs else None
        if project is None or entity_service is None or relation_service is None:
            self.ctx.notify("No se pudo aplicar la reparación (servicios no disponibles)", "error")
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
            self.ctx.notify("No se aplicó ninguna reparación", "error")
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
        # FOCO-13: la semilla del lienzo de Foco sigue la misma decisión.
        foco_widget = getattr(self, "foco", None)
        if foco_widget is not None:
            if accepted:
                foco_widget.canvas.bloom_seed(candidate_id)
            else:
                foco_widget.canvas.wither_seed(candidate_id)
        # UX17: confirmación visible que sobrevive al cierre del cajón (toast).
        notify = getattr(self.ctx, "notify", None)
        if callable(notify):
            if accepted:
                notify("Semilla integrada al canon", "success")
            else:
                notify("Semilla descartada", "info")
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
                # FOCO-13: aceptar una Semilla MANTIENE el foco original; el
                # vecindario se reconstruye y lo aceptado aparece en su zona.
                if (
                    getattr(self, "_active_view", "") == "foco"
                    and getattr(self, "foco", None) is not None
                    and self.foco.current_entity_id()
                ):
                    self.foco.center_entity(self.foco.current_entity_id())
                    self._sync_foco_seeds()
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

    def _open_filter_popover(self):
        """BETA2-UI2-10: popover de filtros anclado al embudo del pill temporal.

        Se construye fresco en cada apertura (combos al día con el proyecto) y
        restaura el estado activo del canvas. Referencia viva para que Qt no lo
        recoja mientras está abierto (patrón FocoView._popover).
        """
        _apptrace("WS open_filter_popover")
        popover = FilterPopover(
            project_provider=self._get_active_project,
            initial_state=self.graph.canvas.get_filter_state(),
            on_apply=self.apply_creation_filter,
            on_clear=self.clear_creation_filters,
            parent=self,
        )
        self._filter_popover = popover
        popover.open_below(self.graph.filter_anchor())

    def _on_present_year_edited(self, year: int):
        """BETA2-UI2-10: año presente tecleado en el pill → persiste vía
        era_controller (la UI del pill solo emite; portado del antiguo
        CreationFilterPanel._apply_present_year)."""
        controller = getattr(self, "era_controller", None)
        if controller is None:
            return
        result = controller.set_present_year(int(year))
        if isinstance(result, Error):
            _apptrace(f"WS present_year_edit error={result.error}")
            return
        self.refresh()

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
        # BETA2-UI2-10: el indicador es el badge del embudo del pill temporal.
        self.graph.set_filter_badge_count(self.graph.active_filter_count())

    def apply_creation_filter(self, filter_state: VisualFilterState):
        self.graph.apply_visual_filter(filter_state)
        self._sync_filter_indicator()

    def clear_creation_filters(self):
        self.graph.clear_visual_filters()
        self._sync_filter_indicator()

    # BETA2-FOCO-33: filtros de la Cronología (réplica del Mapa, campos aplicables).
    def _open_chrono_filter_popover(self):
        # BETA2-FOCO-38: la Cronología solo filtra por Tipo y Anillo.
        snap = self.chrono.filter_snapshot()
        initial = VisualFilterState(
            entity_types=tuple(snap["entity_types"]),
            layer_ids=tuple(snap["ring_ids"]),
        )
        popover = FilterPopover(
            project_provider=self._get_active_project,
            initial_state=initial,
            on_apply=self._apply_chrono_filter,
            on_clear=self._clear_chrono_filter,
            mode="chrono",
            parent=self,
        )
        self._chrono_filter_popover = popover
        popover.open_below(self.chrono.filter_anchor())

    def _apply_chrono_filter(self, filter_state: VisualFilterState):
        # BETA2-FOCO-38: solo Tipo (entity_types) y Anillo (layer_ids).
        self.chrono.apply_scope_filter(
            entity_types=filter_state.entity_types,
            ring_ids=filter_state.layer_ids,
        )
        self.chrono.set_filter_badge_count(self.chrono.active_filter_count())

    def _clear_chrono_filter(self):
        self.chrono.clear_scope_filter()
        self.chrono.set_filter_badge_count(self.chrono.active_filter_count())

    def focus_search_result(self, result: GraphSearchResult) -> bool:
        if result.item_kind == "relation":
            return self.graph.focus_relation(result.item_id)
        if result.item_kind == "tree":
            return self.graph.focus_tree(result.item_id)
        return self.graph.focus_node(result.item_id)

    # ── BETA1-L02b / BETA2-UI2-10: barra de búsqueda flotante (Ctrl+B) ───────

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

    def _delete_entity_from_foco(self, entity_id: str) -> None:
        """WS-E: borrar la entidad en foco con confirmación (misma ruta que la Mapa).

        Antes solo se podía borrar desde el Mapa; en la vista principal de Creación
        (Foco) no había forma de eliminar una entidad mal creada.
        """
        if not entity_id or self.entity_controller is None:
            return
        project = self._get_active_project()
        entity = project.entity_by_id(entity_id) if project is not None else None
        name = str(getattr(entity, "name", "") or "") or entity_id
        confirm = QMessageBox.question(
            self,
            "Eliminar entidad",
            f"¿Eliminar «{name}»? Se quitarán también sus relaciones.\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        result = self.entity_controller.delete(entity_id)
        if isinstance(result, Error):
            self.ctx.notify(f"No se pudo eliminar: {result.error}", "error")
            return
        self.ctx.log("info", f"Entidad eliminada desde Foco: {name}")
        self.refresh()

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
            self.ctx.notify(f"Errores al eliminar: {'; '.join(errors)}", "error")
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

    def _open_utility(self, view, title: str | None = None):
        """Open a utility view in the right drawer."""
        drawer = self.ctx.drawer
        if drawer is None or view is None:
            return
        resolved_title = title or _utility_title(view)
        drawer.set_content(view, title=resolved_title)
        drawer.open()

    def _create_entity_on_graph(self) -> str:
        """Create a new entity, add node to graph center, open detail panel.

        Returns the new entity id ("" on failure) so callers like the
        BETA1-B01 context-menu composition can chain existing routes.
        """
        if self.entity_controller is None:
            self.ctx.notify("No se pudo crear hoja: servicio no disponible", "error")
            return ""
        result = self.entity_controller.create(
            self._with_active_ring_payload(
                {
                    "name": "Nueva hoja",
                    "entity_type": "nota",
                    "brief_description": "",
                    "canon_state": "canonico",
                    "custom_metadata": {"_visual_draft": True},
                }
            )
        )
        if isinstance(result, Error):
            self.ctx.notify(f"Error creando hoja: {result.error}", "error")
            return ""
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Hoja creada")
        self.refresh()
        # BETA1-B02: reveal without zooming - focus_entity did a fitInView
        # that yanked the camera on every contextual creation.
        self.graph.canvas.reveal_entity(entity_id)
        # BETA2-CLEANUP-PANELES: la edición vive en el Foco (no en el cajón).
        self._focus_new_entity(entity_id)
        return entity_id

    def _create_entity_with_payload(self, data: dict, *, open_panel: bool = True) -> str:
        if self.entity_controller is None:
            self.ctx.notify("No se pudo crear hoja: servicio no disponible", "error")
            return ""
        result = self.entity_controller.create(data)
        if isinstance(result, Error):
            self.ctx.notify(f"Error creando hoja: {result.error}", "error")
            return ""
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Hoja creada")
        self.refresh()
        self.graph.canvas.reveal_entity(entity_id)
        if open_panel:
            self._focus_new_entity(entity_id)
        return entity_id

    def _create_tree_on_graph(self) -> str:
        """Create a new contenedor entity and open tree detail panel.

        Returns the new entity id ("" on failure); see _create_entity_on_graph.
        """
        if self.entity_controller is None:
            self.ctx.notify("No se pudo crear rama: servicio no disponible", "error")
            return ""
        result = self.entity_controller.create(
            self._with_active_ring_payload(
                {
                    "name": "Nueva rama",
                    "entity_type": "contenedor",
                    "brief_description": "",
                    "canon_state": "canonico",
                    "custom_metadata": {"_visual_draft": True},
                }
            )
        )
        if isinstance(result, Error):
            self.ctx.notify(f"Error creando rama: {result.error}", "error")
            return ""
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Rama creada")
        self.refresh()
        # BETA1-B02: reveal without zooming - focus_entity did a fitInView
        self.graph.canvas.reveal_entity(entity_id)
        # BETA2-CLEANUP-PANELES: la edición de ramas vive en el Foco.
        self._focus_new_entity(entity_id)
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
                "canon_state": "canonico",
                "custom_metadata": {"_visual_draft": True},
            },
        )
        entity_id = self._create_entity_with_payload(payload, open_panel=False)
        if entity_id and tree_id:
            self._assign_node_to_tree(entity_id, tree_id)
            self._focus_new_entity(entity_id)

    def _create_subtree_in_tree(self, tree_id: str):
        """BETA1-B01 'Crear subrama': create tree + assign to parent tree."""
        payload = self._payload_in_tree_ring(
            tree_id,
            {
                "name": "Nueva rama",
                "entity_type": "contenedor",
                "brief_description": "",
                "canon_state": "canonico",
                "custom_metadata": {"_visual_draft": True},
            },
        )
        if self.entity_controller is None:
            self.ctx.notify("No se pudo crear rama: servicio no disponible", "error")
            return
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self.ctx.notify(f"Error creando rama: {result.error}", "error")
            return
        entity_id = getattr(result.value, "id", "")
        self.ctx.log("info", "Rama creada")
        self.refresh()
        self.graph.canvas.reveal_entity(entity_id)
        if entity_id and tree_id:
            self._assign_node_to_tree(entity_id, tree_id)
            self._focus_new_entity(entity_id)

    def _assign_node_to_tree(self, entity_id: str, tree_id: str):
        """Assign entity (or container) to a container tree. Removes old 'contiene' first."""
        if self.relation_controller is None:
            self.ctx.notify("No se pudo asignar a la rama: servicio no disponible", "error")
            return
        # Check for cycle
        if entity_id == tree_id:
            self.ctx.notify("Una rama no puede contenerse a sí misma", "error")
            return
        # Check for nesting cycle: tree_id must not be inside entity_id
        if self._is_nested_in(tree_id, entity_id):
            self.ctx.notify("Anidamiento cíclico: la rama destino ya pertenece al origen", "error")
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
            self.ctx.notify(f"Error asignando a la rama: {result.error}", "error")
            return
        self._sync_entity_to_tree_ring(entity_id, tree_id)
        self.ctx.log("info", "Hoja asignada a la rama")
        self.refresh()

    def _open_ring_create_panel(self):
        """BETA2-CLEANUP-PANELES: 'Crear anillo' → RingPanel unificado (crear)."""
        if self.layer_controller is None or self.ctx.drawer is None:
            self.ctx.notify("No se pudo crear anillo: servicio no disponible", "error")
            return
        panel = RingPanel(self.layer_controller, self.refresh)
        self.ctx.drawer.set_content(panel, title="Nuevo anillo")
        self.ctx.drawer.open()

    def _open_ring_edit_panel(self, ring_id: str):
        """BETA2-CLEANUP-PANELES: 'Editar anillo' → RingPanel unificado (editar)."""
        if self.layer_controller is None or self.ctx.drawer is None:
            self.ctx.notify("No se pudo editar anillo: servicio no disponible", "error")
            return
        panel = RingPanel(self.layer_controller, self.refresh, ring_id=ring_id)
        self.ctx.drawer.set_content(panel, title="Editar anillo")
        self.ctx.drawer.open()

    def _open_era_create_panel(self):
        """BETA2-CAL: 'Crear era…' abre el editor de calendario unificado (las eras se
        crean por duración encadenada, no por años absolutos sueltos)."""
        self._open_calendar_editor("Nueva era")

    def _open_era_edit_panel(self, era_id: str):  # noqa: ARG002 - firma estable del signal
        """BETA2-CAL: cualquier era se edita en el editor de calendario unificado.

        Ya no existe un editor de una-era que escriba años absolutos directos (evitaba
        el modelo paralelo): todas las eras se definen encadenadas por duración en un
        único sitio. El clic en cualquier banda abre la configuración del calendario.
        """
        self._open_calendar_editor("Calendario y eras")

    def _open_calendar_editor(self, title: str) -> None:
        if self._chronology_ctrl is None:
            self.ctx.log(
                "info",
                "Las eras de este proyecto se definen en la configuración del calendario",
            )
            return
        from hosts.DesktopHostPySide.widgets.calendar_editor_dialog import (
            CalendarEditorDialog,
        )

        # BETA2-CAL-06: el calendario se edita en un diálogo ancho centrado (la
        # timeline y las rejillas de meses/semana se recortaban en el cajón).
        dialog = CalendarEditorDialog(
            self._chronology_ctrl, on_saved=self.refresh, parent=self
        )
        dialog.setWindowTitle(title)
        dialog.exec()

    def _delete_ring(self, ring_id: str):
        """BETA1-B03: 'Eliminar anillo' - soft delete (hide_layer) after
        confirmation. Entities keep their layer ids: they show as 'Sin
        clasificar' and the ring can be restored from the layers view."""
        if self.layer_controller is None:
            self.ctx.notify("No se pudo eliminar anillo: servicio no disponible", "error")
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
            self.ctx.notify(f"Error eliminando anillo: {result.error}", "error")
            return
        self.ctx.log("info", f"Anillo eliminado: {name}")
        self.refresh()

    def _assign_node_to_ring(self, entity_id: str, ring_id: str):
        """BETA1-B03 'Mover a anillo': replace the entity's world-layer
        membership via the existing EntityController.update route (CRUD-U).
        Non-ring layer ids (if any) are preserved; only world-layer ids are
        swapped for the chosen ring."""
        if self.entity_controller is None:
            self.ctx.notify("No se pudo mover al anillo: servicio no disponible", "error")
            return
        entity = self._entity_by_id(entity_id)
        if entity is None:
            self.ctx.notify("No se pudo mover al anillo: elemento no encontrado", "error")
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
            self.ctx.notify(f"Error moviendo al anillo: {result.error}", "error")
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
            self.ctx.notify("No se pudo extraer de la rama: servicio no disponible", "error")
            return
        self._remove_tree_membership(entity_id)
        self.ctx.log("info", "Elemento extraído de la rama")
        self.refresh()

    # BETA2-CLEANUP-PANELES: retirados _on_node_converted_to_branch y
    # _open_tree_panel — la edición de ramas vive en el Foco (NodeDetailPanel
    # variant="foco"); la conversión hoja→rama se hace desde el selector de
    # tipo de la Ficha en el Foco.

    # Existing workspace methods (preserved)

    def _open_hito_panel(self):
        """Open the causal milestone creation/review drawer (B41-T03)."""
        drawer = self.ctx.drawer
        if self._milestone_ctrl is None or drawer is None:
            self.ctx.notify("No se pudo abrir hitos: servicio no disponible", "error")
            return
        panel = CausalMilestonePanel(self._milestone_ctrl, on_created=self.refresh)
        drawer.set_content(panel, title="Hitos causales")
        drawer.open()

    def _open_milestone_chronology_view(
        self, target_kind: str = "", target_id: str = "", hito_id: str = ""
    ):
        """BETA2-UX-08: la cronología unificada vive en el lienzo lateral (modo
        «chrono»). «Ver hitos» entra en ese modo; si se pide un hito concreto se
        abre su panel de detalle. La vista-lista (MilestoneChronologyView) se
        retiró; sus hitos «Sin ubicar» viven ahora en el gutter del lienzo."""
        self.set_active_view("chrono")
        hid = str(hito_id or "")
        if hid:
            self._open_milestone_detail_panel(hid)

    def _create_hito_from_selection(self):
        """Create a hito from current graph selection (B41-T04).

        Reads the current selection from the graph canvas, builds a prefill
        dict with affected entity/relation/layer ids, and opens the
        CausalMilestonePanel pre-populated.
        """
        drawer = self.ctx.drawer
        if self._milestone_ctrl is None or drawer is None:
            self.ctx.notify(
                "No se pudo crear hito desde selección: servicio no disponible", "error"
            )
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
        """Re-resuelve el proveedor IA tras cambios de ajustes/proveedor.

        BETA2-WIKI-11: el AIContextController (acciones IA contextuales) se
        eliminó; solo queda refrescar el proveedor del AIJobService compartido
        y el controller de cronología del proyecto activo."""
        if getattr(self, "ai_job_service", None) is not None:
            self.ai_job_service.set_provider(get_provider())
        project_controller = getattr(self.ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is None:
            self._chronology_ctrl = None
        else:
            self._chronology_ctrl = ProjectChronologyController(project_service)

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
        # BETA2-IMG: la carpeta de assets (retratos) sigue a la ruta actual del
        # proyecto — se refija en cada refresh (abrir/crear/guardar-como).
        current = getattr(self.ctx.project_controller, "current_path", None)
        assets_root = assets_root_for(Path(current)) if current else None
        try:
            self.graph.set_assets_root(assets_root)
        except RuntimeError:
            pass
        # BETA2-HOVER-03: la cronología resuelve retratos para su tarjeta flotante
        # de hover (misma carpeta de assets que el Mapa/Foco).
        try:
            self.chrono.set_assets_root(assets_root)
        except (RuntimeError, AttributeError):
            pass
        # BETA2-UX-02: las vistas-tabla legacy se eliminaron; solo el grafo se
        # refresca aquí (Foco/Cronología se reconstruyen en sus propias rutas).
        for widget in [self.graph]:
            try:
                if widget is not None and hasattr(widget, "refresh"):
                    widget.refresh()
            except RuntimeError:
                continue
        # FOCO-19: el refresh completo acaba de reconstruir el grafo.
        self._graph_stale = False
        # BETA1-G04: la cronológica se reconstruye solo si está activa
        if getattr(self, "_active_view", "concentric") == "chrono" and hasattr(self, "chrono"):
            self.chrono.set_project(self._get_active_project())
        # BETA2-FOCO: refrescar la Creación con proyecto activo entra en Foco
        # (vista principal), centrando la última entidad trabajada.
        # PLAY-13: salvo en pleno recorrido — un refresh entrante (autosave de
        # un panel, guardado del proyecto) no debe expulsar al usuario de Play.
        if (
            getattr(self, "foco", None) is not None
            and self._get_active_project() is not None
            and self._active_view != "play"
        ):
            self.set_active_view("foco")
        self._load_project_budget_default()
        self._rehydrate_seed_notifications()  # SEM02: semillas pendientes al recargar

    @_qt_safe_slot
    def _rehydrate_seed_notifications(self):
        # SEM02/SEM04: al cargar/refrescar un proyecto, reconstruye las
        # notificaciones (esquina) Y las semillas-candidato (en el grafo) de los
        # candidatos pendientes de revisión (idempotente).
        layer = getattr(self, "_seed_notifications", None)
        controller = self.candidate_controller
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
            # FOCO-13: chips pulsantes SOLO para lo NO visible en la vista actual;
            # las semillas de la entidad enfocada germinan en su zona/drawer.
            if not layer.has(cid) and cid not in self._foco_visible_candidate_ids():
                label = str(getattr(cand, "title", "") or "Semilla")
                layer.add(cid, label)
        self.graph.rehydrate_candidate_seeds(pending_ids)  # SEM04: semillas en el grafo
        self._sync_foco_seeds()  # FOCO-13: rehidratación espacial en Foco (idempotente)
        self._request_thirsty_refresh()  # JARDIN-03: badge «💧 N» al día

    def open_graph(self):
        """Graph is always visible - this is now a no-op."""
        pass

    def open_entity_create(self):
        drawer = self.ctx.drawer
        if self.entity_controller is None or drawer is None:
            self.ctx.notify("No se pudo crear hoja: servicio no disponible", "error")
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
            self.ctx.notify("No se pudo crear fuente: servicio no disponible", "error")
            return
        panel = SourceQuickCreatePanel(self.source_controller, on_created=self.refresh)
        drawer.set_content(panel, title="Nueva fuente")
        drawer.open()

    def open_layer_create(self):
        drawer = self.ctx.drawer
        if self.layer_controller is None or drawer is None:
            self.ctx.notify("No se pudo crear anillo: servicio no disponible", "error")
            return
        panel = RingPanel(self.layer_controller, self.refresh)
        drawer.set_content(panel, title="Nuevo anillo")
        drawer.open()

    # BETA2-CLEANUP-PANELES: retirados _open_node_panel y _open_node_panel_editor
    # (cajón «Nodo»/«Rama», obsoleto). Toda la edición de entidades vive en el
    # Modo Foco (ver _focus_new_entity y _on_map_entity_to_foco). NodeDetailPanel
    # sigue vivo, pero solo como pestaña Ficha del Foco (variant="foco").

    def _open_relation_panel(self, relation_id: str, *, is_new: bool = False):
        if self.relation_controller is None or self.ctx.drawer is None:
            self.ctx.notify("No se pudo abrir el panel de relación", "error")
            return
        # BETA1-F05: diagnóstico — si la construcción del panel falla, que
        # se vea el motivo en vez de un click que "no hace nada".
        try:
            self._open_relation_panel_impl(relation_id, is_new=is_new)
        except Exception as exc:  # noqa: BLE001
            import traceback

            _apptrace("relation_panel_error " + traceback.format_exc(limit=4))
            self.ctx.notify(f"El panel de relación falló al construirse: {exc}", "error")

    def _open_relation_panel_impl(self, relation_id: str, *, is_new: bool = False):
        panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            on_saved=self.refresh,
            # BETA2-WIKI-10: la barra IA del panel de relación (generar/refinar sugerencia
            # de texto) y la sugerencia de hito quedan RETIRADAS de la UI.
            ai_controller=None,
            entity_controller=self.entity_controller,
            milestone_controller=self._milestone_ctrl,
            is_new=is_new,
            on_focus_neighborhood=lambda rid=relation_id: self.focus_neighborhood(
                rid, kind="relation"
            ),
            on_open_milestones=self._open_milestone_chronology_view,
            on_suggest_milestone=None,
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
            self.ctx.notify(message, "error")

    def _open_relation_create_panel(self, source_id: str, target_id: str):
        controller = self.relation_controller
        if controller is None or self.ctx.drawer is None:
            self.ctx.notify("No se pudo crear relación: servicio no disponible", "error")
            return
        if source_id == target_id:
            self.ctx.notify("No se puede crear una relación sobre la misma entidad", "error")
            return
        # BETA1-B03: 'contiene' is structural, not narrative - it must not
        # block creating a real relation between a branch and its content.
        if self._relation_exists(source_id, target_id, ignore_structural=True):
            self.ctx.notify("Ya existe una relación entre esas entidades", "error")
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
            self.ctx.notify(result.error, "error")
            return
        relation = result.value
        relation_id = getattr(relation, "id", "")
        self.ctx.log("info", "Relación provisional creada")
        self.refresh()
        if relation_id:
            self._open_relation_panel(relation_id, is_new=True)
