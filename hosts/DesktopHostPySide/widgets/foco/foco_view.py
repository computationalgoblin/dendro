"""FocoView: composición del Modo Foco (BETA2-FOCO-08).

Vista PRINCIPAL de Creación: lienzo de zonas (FocoCanvas) + tarjeta central de
la entidad en foco superpuesta como widget real (patrón de overlays de la
casa). En este ticket la tarjeta es un resumen compacto; el formulario completo
con autosave llega en FOCO-09 y la sustituye en el mismo hueco.

Estado que NO se persiste: historial de foco (atrás) e ids resaltadas — solo en
memoria (decisión de producto). Lo ÚNICO persistido es la última entidad
trabajada, vía servicio de aplicación (``ProjectService.set_last_worked_entity``).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets import icons, portrait_cache
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_SOFT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    RADIUS_LG,
    SAGE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SURFACE_HI,
    TYPE_H1_PX,
    CapsuleTabBar,
    ElidedLabel,
    EmptyState,
    FlowLayout,
    enum_human,
)
from hosts.DesktopHostPySide.widgets.foco.containment_assistant import (
    ContainmentAssistantPanel,
)
from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import CultivationNotebook
from hosts.DesktopHostPySide.widgets.foco.cultivation_strip import CultivationStrip
from hosts.DesktopHostPySide.widgets.foco.entity_editor_overlay import EntityEditorOverlay
from hosts.DesktopHostPySide.widgets.foco.foco_bottom_sheet import FocoBottomSheet
from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoCanvas
from hosts.DesktopHostPySide.widgets.foco.foco_lifeline import FocoLifelineBand
from hosts.DesktopHostPySide.widgets.foco.foco_popover import (
    EntitySearchPopover,
    QuickCreatePopover,
)
from hosts.DesktopHostPySide.widgets.foco.foco_tool_rail import FocoToolRail
from hosts.DesktopHostPySide.widgets.foco.portrait_band import PortraitBand
from hosts.DesktopHostPySide.widgets.foco.relations_panel import FocoRelationsPanel
from packages.application.foco_rings import (
    branch_members,
    classify_ring_neighbors,
    direct_containments,
    ring_display_info,
    ring_id_for,
    ring_navigation,
)
from packages.application.foco_zones import classify_containers
from packages.application.image_asset_service import assets_root_for
from packages.application.portrait_crop import parse_crop
from packages.domain.entity_taxonomy import is_branch, is_branch_type
from packages.domain.result import Error

# Tipos de entidad que cuentan como "rama" para el popover Añadir a rama.
_BRANCH_TYPES = {
    "contenedor",
    "faccion",
    "cultura",
    "sistema_magico",
    "religion",
    "institucion",
    "trama",
}

# FOCO-25: teclas de navegación del lienzo (interceptadas a nivel de vista).
_NAV_KEYS = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down)

# Widgets donde las flechas tienen SU propio significado (editar texto, elegir
# en listas/combos/spins) — la navegación del Foco NO se los roba.
_ARROW_OWNERS = (
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QAbstractSpinBox,
    QComboBox,
    QAbstractItemView,
)


def _portrait_meta(entity: Any) -> dict:
    """BETA2-IMG: claves de retrato para los dicts de satélite del lienzo."""
    meta = dict(getattr(entity, "custom_metadata", {}) or {})
    stored = str(meta.get("_image_path", "") or "")
    raw_crop = meta.get("_image_crop")
    return {
        "image_path": stored,
        "image_crop": parse_crop(raw_crop).as_tuple() if raw_crop else None,
    }


_SHELF_THUMB = 54  # FOCO-30: lado del retrato de la miniatura de la estantería
_SHELF_H = 86  # alto de la banda de estantería (retrato + nombre)


class _ContentThumb(QFrame):
    """FOCO-30: miniatura clicable de un contenido de rama (retrato + nombre)."""

    clicked = Signal(str)

    def __init__(self, entity_id: str, name: str, pixmap, parent=None) -> None:
        super().__init__(parent)
        self._entity_id = entity_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        img = QLabel(self)
        img.setFixedSize(_SHELF_THUMB, _SHELF_THUMB)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet(
            f"border: 1px solid {LINE_SOFT}; border-radius: 8px; background: transparent;"
        )
        if pixmap is not None:
            img.setPixmap(pixmap)
        lay.addWidget(img, 0, Qt.AlignmentFlag.AlignHCenter)
        cap = ElidedLabel(name, self)
        cap.setFixedWidth(_SHELF_THUMB + 10)
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cap.setStyleSheet(
            f"color: {INK_SOFT}; font-size: 11px; border: none; background: transparent;"
        )
        lay.addWidget(cap, 0, Qt.AlignmentFlag.AlignHCenter)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._entity_id)
        super().mousePressEvent(event)


class FocoView(QWidget):
    """Escritorio causal: una entidad al centro, su jardín alrededor."""

    entityCentered = Signal(str)  # noqa: N815 — convención Qt de señales
    openInMapRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    openInChronoRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # FOCO-10: re-emisión de la banda local con las MISMAS firmas que la
    # cronología global — el workspace reutiliza sus slots de persistencia.
    lifespanEdited = Signal(str, int, object)  # noqa: N815 — convención Qt de señales
    milestoneCreateRequested = Signal(int, str)  # noqa: N815 — convención Qt de señales
    # FOCO-26: rango dibujado en la banda local ⇒ hito con inicio y fin.
    milestoneRangeCreateRequested = Signal(int, int)  # noqa: N815 — convención Qt
    # FOCO-11: el riego lo orquesta el workspace (autorización + drawer, FOCO-12).
    waterRequested = Signal(list)  # noqa: N815 — ids a regar (selección o centro)
    dryRequested = Signal(str)  # noqa: N815 — Secar (sin IA)
    cultivateRequested = Signal(str)  # noqa: N815 — Cultivar (sin IA)
    # FOCO-26: «Sugerir X» desde el Cuaderno de cultivo (métrica a reparar).
    suggestRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # FOCO-13: click en una Semilla de zona ⇒ revisión (flujo humano existente).
    seedReviewRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # FOCO-19: toda mutación hecha desde Foco (crear/relacionar/fantasma/
    # convertir/vincular/editar formulario) avisa al workspace para que el
    # Mapa se reconstruya al entrar (antes quedaba desactualizado).
    dataChanged = Signal()  # noqa: N815 — convención Qt de señales
    # BETA2-CLEANUP-PANELES: abrir el panel de anillo (unificado) desde el Foco.
    # ringEditRequested lleva el id del anillo actual (click en el banner);
    # ringCreateRequested no lleva argumento (botón «Crear anillo» del rail).
    ringEditRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    ringCreateRequested = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(
        self,
        *,
        project_provider: Callable[[], Any],
        last_entity_getter: Callable[[], str] | None = None,
        last_entity_setter: Callable[[str], Any] | None = None,
        ctx: Any = None,
        entity_controller: Any = None,
        relation_controller: Any = None,
        milestone_controller: Any = None,
        watering_service: Any = None,
        ghost_service: Any = None,
        history_provider: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_provider = project_provider
        # BETA2-PLAY-18: provider(entity_id) → observaciones del recorrido para
        # el Cuaderno de Cultivo (solo lectura; la UI no escribe historial).
        self.history_provider = history_provider
        self._last_entity_getter = last_entity_getter
        self._last_entity_setter = last_entity_setter
        # FOCO-09: con ctx + entity_controller el centro embebe el FORMULARIO
        # real (NodeDetailPanel variant="foco", autosave 800 ms); sin ellos se
        # muestra la tarjeta-resumen (tests/consumidores ligeros).
        self.ctx = ctx
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.milestone_controller = milestone_controller
        self.watering_service = watering_service
        self.ghost_service = ghost_service
        self._center_id = ""
        # UI2-05: entidad regándose AHORA (lote en curso) — tono transitorio.
        self._watering_active_id = ""
        self._form_panel: Any = None
        self._relations_panel: Any = None
        # UI2-06: pestaña activa recordada entre recentrados — cambiar de
        # entidad no te expulsa de la pestaña en la que trabajas.
        self._last_tab = "ficha"
        # UI2-09: dirección pendiente de la transición (unitaria) y animación
        # de deslizamiento de la tarjeta en curso (None = nada que animar).
        self._pending_transition: tuple[float, float] | None = None
        self._center_anim: QVariantAnimation | None = None
        # FOCO-23: modo dual (entidad ↔ relación ↔ entidad) en el centro.
        self._dual: dict | None = None
        self._dual_card: QFrame | None = None
        self._dual_close: QPushButton | None = None  # FOCO-30: ✕ del modo dual
        self._dual_panels: list[Any] = []
        # BETA2-FOCO-29: cronología editable bajo cada columna del dual (A, relación, B).
        self._dual_lifelines: list[Any] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.canvas = FocoCanvas(self)
        layout.addWidget(self.canvas, 1)
        # UI2-09: la atmósfera respeta el movimiento reducido del ctx.
        self.canvas.set_atmosphere_context(ctx)
        self.canvas.satelliteActivated.connect(self._on_satellite_activated)
        self.canvas.seedClicked.connect(self.seedReviewRequested)
        # BETA2-CLEANUP-PANELES: click en la píldora del anillo ⇒ editar ese anillo.
        self.canvas.ringBannerClicked.connect(self._on_ring_banner_clicked)
        # FOCO-25: Ctrl+B ⇒ paleta de búsqueda para saltar a cualquier entidad.
        self._search_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self._search_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._search_shortcut.activated.connect(self._open_search_palette)
        # FOCO-25: filtro de aplicación — las flechas navegan aunque el foco de
        # teclado esté en el formulario (no en el lienzo); ver _handle_nav_key.
        # Se instala SOLO mientras la vista está visible (show/hide): un filtro
        # de app por vista viva encarecería todos los eventos de la app.
        self._app_filter_installed = False

        # FOCO-11: rail izquierdo de herramientas (columna única de iconos).
        self.tool_rail = FocoToolRail(self)
        self.tool_rail.toolTriggered.connect(self._on_tool)
        self.canvas.selectionChanged.connect(lambda _ids: self._refresh_tool_context())
        self._popover: Any = None  # referencia viva del popover abierto

        self._center_card = self._build_center_card()
        # UI2-16: el editor a pantalla completa adopta las pestañas — la
        # edición vive ahí; la tarjeta central queda como display de lectura.
        self._editor_open = False
        self._editor_overlay = EntityEditorOverlay(self)
        self._editor_overlay.mount(self._tab_bar, self._tab_stack)
        self._editor_overlay.closeRequested.connect(self.close_editor)
        # UI2-17: las flechas de la cabecera navegan SIN salir del fullscreen.
        self._editor_overlay.navRequested.connect(self._on_editor_nav)
        # BETA2-FOCO-27: cajón inferior del editor — el panel editable del hito sube
        # desde el borde inferior del editor (hijo del overlay, por encima del velo).
        # BETA2-FOCO-29: el cajón inferior es hijo de la VISTA (no del overlay del
        # editor) para poder abrirse también sobre la tarjeta dual; se eleva por
        # encima del overlay del editor cuando corresponde (_position_overlays).
        self._bottom_sheet = FocoBottomSheet(self)
        self._bottom_sheet.hide()
        self._adjacent_card = self._build_adjacent_card()
        self._empty = EmptyState(
            "Crea tu primera entidad",
            "El jardín está vacío. Planta la primera entidad con la herramienta "
            "de creación y empieza a cultivarla.",
        )
        self._empty.setParent(self)
        self._empty.hide()

    # ------------------------------------------------------------------
    # Tarjeta central (resumen; FOCO-09 la sustituye por el formulario real)
    # ------------------------------------------------------------------

    def _build_center_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("focoCenterCard")
        # FOCO-26: el tono del editor refleja el estado de riego — una entidad
        # SECADA se ve con pergamino oscurecido y borde apagado.
        card.setProperty("wateringState", "")
        card.setStyleSheet(
            f"QFrame#focoCenterCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: {RADIUS_LG}px; }} "
            f'QFrame#focoCenterCard[wateringState="secada"] {{ background: #E9E2CE; '
            f"border: 1px solid {LINE_SOFT}; border-radius: {RADIUS_LG}px; }} "
            # UI2-05/21: mientras el lote riega ESTA entidad, la tarjeta vira a
            # savia — fondo con tinte SAGE + borde grueso (antes solo cambiaba el
            # borde 1px→2px, casi imperceptible).
            f'QFrame#focoCenterCard[wateringState="regando"] {{ background: #D7E0C8; '
            f"border: 2px solid {SAGE}; border-radius: {RADIUS_LG}px; }}"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        outer.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(14)
        outer.addLayout(row, 1)
        # FOCO-10: cronología LOCAL bajo el editor, mismo ancho que el formulario.
        self.lifeline = FocoLifelineBand(card)
        self.lifeline.lifespanEdited.connect(self._on_lifeline_span_edited)
        self.lifeline.milestoneCreateRequested.connect(self.milestoneCreateRequested)
        self.lifeline.milestoneRangeCreateRequested.connect(self.milestoneRangeCreateRequested)
        # BETA2-FOCO-27: clicar un hito abre distinto según el modo — panel compacto
        # de lectura a la derecha (descripción) o cajón inferior editable (edición).
        self.lifeline.milestoneActivated.connect(self._open_milestone_for_mode)
        # FOCO-25: arrastrar el rombo de un hito reubica su año (por controller).
        self.lifeline.milestoneYearEdited.connect(self._on_milestone_year_edited)
        # UI2-14: arrastrar el rombo de FIN fija/edita la duración del hito.
        self.lifeline.milestoneEndYearEdited.connect(self._on_milestone_end_year_edited)
        self.lifeline.hide()
        # BETA2-FOCO-27: la cronología vive en un slot propio para poder MUDARLA
        # entre la tarjeta de descripción (solo lectura) y el pie del editor
        # (editable) — mismo patrón de reparenting que la franja de cultivo.
        self._lifeline_slot = QVBoxLayout()
        self._lifeline_slot.setContentsMargins(0, 0, 0, 0)
        self._lifeline_slot.addWidget(self.lifeline)
        outer.addLayout(self._lifeline_slot)
        # En la tarjeta de descripción arranca en SOLO lectura (visualizar).
        self.lifeline.set_read_only(True)

        # UI2-06: la banda de retrato es de la TARJETA (no del formulario) —
        # visible a la izquierda en todas las pestañas, oculta sin imagen.
        self.portrait_band = PortraitBand(card)
        row.addWidget(self.portrait_band)
        column = QVBoxLayout()
        column.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(8)
        # FOCO-28: el botón «◀ volver» se retiró (navegación por ruleta/bandas).
        self._name_label = ElidedLabel("", card)
        self._name_label.setStyleSheet(
            f"color: {INK_STRONG}; font-family: Georgia, serif; "
            f"font-size: {TYPE_H1_PX}px; font-weight: 700; border: none; background: transparent;"
        )
        header.addWidget(self._name_label, 1)
        column.addLayout(header)
        self._type_label = QLabel("", card)
        self._type_label.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; border: none; background: transparent;"
        )
        column.addWidget(self._type_label)
        # BETA2-JARDIN-04: chip «siguiente paso» — la sugerencia más urgente
        # según el estado de riego del centro. Reusa los flujos existentes
        # (regar con autorización / Sugerir X del Cuaderno).
        # BETA2-FOCO-37: el chip verboso «Regar ahora» se retiró; los controles de
        # riego (Regar/Secar/Cultivar) viven como iconos en la franja de cultivo
        # (CultivationStrip, más abajo). «Sugerir X» vive en el Cuaderno.
        # UI2-06/16: pestañas Ficha | Relaciones | Cultivo — se crean como
        # atributos de la vista pero viven DENTRO del editor a pantalla
        # completa (EntityEditorOverlay las adopta en __init__). La tarjeta
        # central es un display de LECTURA.
        self._tab_bar = CapsuleTabBar()
        self._tab_bar.add_tab("ficha", "Ficha")
        self._tab_bar.add_tab("relaciones", "Relaciones")
        self._tab_bar.add_tab("cultivo", "Cultivo")
        self._tab_bar.tabChanged.connect(self._on_tab_changed)

        def _transparent_scroll() -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet(
                "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
            )
            return scroll

        # FOCO-09: hueco del formulario real (NodeDetailPanel) = pestaña Ficha.
        self._form_scroll = _transparent_scroll()
        self._relations_scroll = _transparent_scroll()
        self._cultivo_scroll = _transparent_scroll()
        self._tab_stack = QStackedWidget()
        self._tab_stack.addWidget(self._form_scroll)
        self._tab_stack.addWidget(self._relations_scroll)
        self._tab_stack.addWidget(self._cultivo_scroll)

        # UI2-16: resumen de metadatos de LECTURA (icono 12px + texto) — la
        # edición vive en los chips de la Ficha del editor fullscreen.
        self._meta_summary_box = QWidget(card)
        self._meta_summary = FlowLayout(spacing=10)
        self._meta_summary_box.setLayout(self._meta_summary)
        self._meta_summary_box.hide()
        column.addWidget(self._meta_summary_box)

        self._brief_label = QLabel("", card)
        self._brief_label.setWordWrap(True)
        self._brief_label.setStyleSheet(
            f"color: {INK_SOFT}; font-size: 12px; border: none; background: transparent;"
        )
        column.addWidget(self._brief_label, 1)
        # FOCO-30: estantería de contenidos — solo para ramas (miniaturas de lo que
        # contiene, clicables para entrar). Scroll horizontal si hay muchas.
        self._contents_shelf = QScrollArea(card)
        self._contents_shelf.setWidgetResizable(True)
        self._contents_shelf.setFrameShape(QFrame.Shape.NoFrame)
        self._contents_shelf.setFixedHeight(_SHELF_H)
        self._contents_shelf.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._contents_shelf.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._contents_shelf.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        shelf_inner = QWidget()
        self._contents_layout = QHBoxLayout(shelf_inner)
        self._contents_layout.setContentsMargins(2, 2, 2, 2)
        self._contents_layout.setSpacing(6)
        self._contents_layout.addStretch()
        self._contents_shelf.setWidget(shelf_inner)
        self._contents_shelf.hide()
        column.addWidget(self._contents_shelf)
        # UI2-08/16: franja de cultivo — pie de la tarjeta de lectura; al abrir
        # el editor se muda a su pie (helper _mount_strip).
        self._strip_slot = QVBoxLayout()
        self.cultivation_strip = CultivationStrip(card)
        # BETA2-FOCO-37: los iconos de la franja actúan sobre la entidad en foco.
        self.cultivation_strip.waterClicked.connect(
            lambda: self.waterRequested.emit([self._center_id] if self._center_id else [])
        )
        self.cultivation_strip.dryClicked.connect(
            lambda: self._center_id and self.dryRequested.emit(self._center_id)
        )
        self.cultivation_strip.cultivateClicked.connect(
            lambda: self._center_id and self.cultivateRequested.emit(self._center_id)
        )
        self._strip_slot.addWidget(self.cultivation_strip)
        column.addLayout(self._strip_slot)
        row.addLayout(column, 1)
        # UI2-16: ⛶ en la esquina superior izquierda — abre el editor inmersivo.
        self._expand_button = QToolButton(card)
        self._expand_button.setIcon(icons.icon("expand", color=INK_SOFT, size=16))
        self._expand_button.setIconSize(QSize(16, 16))
        self._expand_button.setToolTip("Editar a pantalla completa")
        self._expand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_button.setFixedSize(28, 28)
        self._expand_button.setStyleSheet(
            f"QToolButton {{ background: {SURFACE_HI}; border: 1px solid {LINE_SOFT}; "
            "border-radius: 14px; } "
            f"QToolButton:hover {{ border-color: {GOLD_SOFT}; }}"
        )
        self._expand_button.clicked.connect(self.open_editor)
        self._expand_button.move(10, 10)
        self._expand_button.hide()
        card.hide()
        return card

    # ── UI2-06: pestañas de la tarjeta ─────────────────────────────────────

    def _on_tab_changed(self, key: str) -> None:
        self._last_tab = str(key)
        self._apply_tab(key)
        self._refresh_next_step_chip()

    def _apply_tab(self, key: str) -> None:
        # UI2-16: el título de la tarjeta de LECTURA ya no depende de la
        # pestaña (las pestañas viven en el editor fullscreen, con su propia
        # cabecera); solo se sincroniza el stack.
        self._tab_stack.setCurrentIndex(
            {"ficha": 0, "relaciones": 1, "cultivo": 2}.get(str(key), 0)
        )

    def open_cultivo_tab(self) -> None:
        """BETA2-FOCO-34: abre el editor y su pestaña Cultivo (donde vive el
        Cuaderno de Cultivo) para revisar/regar de nuevo la entidad regada."""
        if not self._editor_open:
            self.open_editor()
        self._tab_bar.set_current("cultivo")

    def _set_card_portrait(self, source, crop) -> None:
        """Hook on_portrait del formulario: la Ficha resuelve, la banda pinta."""
        self.portrait_band.set_portrait(source, crop)

    def _refresh_portrait_band(self, entity: Any) -> None:
        meta = _portrait_meta(entity)
        stored = meta["image_path"]
        if not stored:
            self.portrait_band.set_portrait(None, None)
            return
        controller = getattr(self.ctx, "project_controller", None) if self.ctx else None
        current_path = getattr(controller, "current_path", None)
        assets_root = assets_root_for(Path(current_path)) if current_path else None
        resolved = portrait_cache.resolve_stored(assets_root, stored)
        self.portrait_band.set_portrait(resolved, meta["image_crop"])

    # ── UI2-16: tarjeta de lectura + editor a pantalla completa ────────────

    def _refresh_meta_summary(self, entity: Any) -> None:
        """Metadatos como LECTURA (icono 12px + texto) en la tarjeta central."""
        while self._meta_summary.count():
            item = self._meta_summary.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        def _pair(icon_name: str, text: str) -> None:
            if not text:
                return
            box = QWidget(self._meta_summary_box)
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            glyph = QLabel(box)
            glyph.setPixmap(icons.pixmap(icon_name, size=12, color=INK_MUTED))
            glyph.setFixedSize(14, 14)
            glyph.setStyleSheet("background: transparent; border: none;")
            row.addWidget(glyph)
            label = QLabel(text, box)
            label.setStyleSheet(
                f"color: {INK_SOFT}; font-size: 11px; background: transparent; border: none;"
            )
            row.addWidget(label)
            self._meta_summary.addWidget(box)

        type_value = getattr(entity.entity_type, "value", str(entity.entity_type))
        _pair("field_type", enum_human(type_value))
        project = self._project()
        if project is not None:
            ring_name, _pos, _total = ring_display_info(project, entity.id)
            _pair("rings", str(ring_name or ""))
        nature = getattr(entity, "temporal_nature", None)
        nature_value = getattr(nature, "value", nature)
        if nature_value:
            _pair("field_nature", enum_human(str(nature_value)))
        importance = getattr(entity, "narrative_importance", None)
        importance_value = getattr(importance, "value", importance)
        if importance_value:
            _pair("metric_relevancia", enum_human(str(importance_value)))

    def _editor_header_pixmap(self, entity: Any):
        meta = _portrait_meta(entity)
        stored = meta["image_path"]
        if not stored:
            return None
        controller = getattr(self.ctx, "project_controller", None) if self.ctx else None
        current_path = getattr(controller, "current_path", None)
        assets_root = assets_root_for(Path(current_path)) if current_path else None
        resolved = portrait_cache.resolve_stored(assets_root, stored)
        if resolved is None:
            return None
        return portrait_cache.portrait_pixmap(resolved, meta["image_crop"], 64)

    def _sync_editor_header(self, entity: Any) -> None:
        self._editor_overlay.set_header(entity.name, self._editor_header_pixmap(entity))

    def _mount_strip(self, slot) -> None:
        """La franja de cultivo vive en la tarjeta O en el pie del editor —
        un único punto de reparenting (el strip nunca se destruye)."""
        for owner in (self._strip_slot, self._editor_overlay.footer_slot):
            index = owner.indexOf(self.cultivation_strip)
            if index >= 0:
                owner.takeAt(index)
        slot.addWidget(self.cultivation_strip)

    def _mount_lifeline(self, slot) -> None:
        """BETA2-FOCO-27: la cronología vive en la tarjeta de descripción (solo
        lectura) O en el pie del editor (editable) — un único punto de reparenting
        (la banda nunca se destruye), espejo de _mount_strip."""
        for owner in (self._lifeline_slot, self._editor_overlay.footer_slot):
            index = owner.indexOf(self.lifeline)
            if index >= 0:
                owner.takeAt(index)
        slot.addWidget(self.lifeline)

    def open_editor(self) -> None:
        """UI2-16: edición inmersiva a pantalla completa (⛶ / doble clic)."""
        if self._editor_open or not self._form_capable() or not self._center_id:
            return
        project = self._project()
        entity = project.entity_by_id(self._center_id) if project is not None else None
        if entity is None:
            return
        self._editor_open = True
        # UI2-18: la tarjeta de lectura se oculta mientras el editor está abierto.
        self._center_card.hide()
        # BETA2-FOCO-27: la cronología EDITABLE se muda al pie del editor (encima de
        # la franja de cultivo); ahí se define el lapso y se gestionan los hitos.
        self._mount_lifeline(self._editor_overlay.footer_slot)
        self.lifeline.set_read_only(False)
        self._mount_strip(self._editor_overlay.footer_slot)
        self._refresh_lifeline(entity)
        self._sync_editor_header(entity)
        self._apply_watering_tone()
        self._editor_overlay.setGeometry(self.rect())
        self._editor_overlay.show()
        self._editor_overlay.raise_()
        self._tab_bar.set_current(self._last_tab)
        self._apply_tab(self._tab_bar.current())
        self._refresh_next_step_chip()
        self._refresh_editor_nav()
        self._editor_overlay.setFocus()

    def close_editor(self) -> None:
        if not self._editor_open:
            return
        # BETA2-FOCO-27: el cajón inferior del hito no sobrevive al cierre del editor.
        self._bottom_sheet.close_sheet()
        # UI2-19: volcar cualquier autoguardado pendiente para no perder lo último
        # escrito antes de leer el canon y refrescar la tarjeta.
        self._flush_form_autosave()
        self._editor_open = False
        self._editor_overlay.hide()
        self._mount_strip(self._strip_slot)
        # BETA2-FOCO-27: la cronología vuelve a la tarjeta de descripción en SOLO
        # lectura (visualizar; sin arrastrar el lapso ni crear hitos).
        self._mount_lifeline(self._lifeline_slot)
        self.lifeline.set_read_only(True)
        # UI2-18: al cerrar vuelve la tarjeta de lectura, por encima del lienzo.
        self._center_card.show()
        # UI2-19: la tarjeta refleja el canon recién guardado.
        project = self._project()
        entity = project.entity_by_id(self._center_id) if project and self._center_id else None
        if entity is not None:
            self._refresh_reading_card(entity)
        self._position_overlays()
        self._refresh_next_step_chip()
        self.canvas.setFocus()

    def _flush_form_autosave(self) -> None:
        """UI2-19: fuerza el autoguardado pendiente del formulario (si el
        temporizador de debounce está armado) para que un cambio recién escrito
        se persista y se propague de inmediato."""
        form = self._form_panel
        timer = getattr(form, "_autosave_timer", None) if form is not None else None
        if timer is not None and timer.isActive():
            timer.stop()
            form._autosave()

    def _on_editor_nav(self, key: int, shift: bool) -> None:
        """UI2-17: flechas de la cabecera del editor — mismo destino que el
        teclado (_arrow_target es puro; funciona con el lienzo tapado)."""
        target = self.canvas._arrow_target(Qt.Key(key), shift=bool(shift))
        if target:
            self._on_satellite_activated(target)

    def _refresh_editor_nav(self) -> None:
        """UI2-17: habilita/gris las flechas según los destinos reales."""
        if not self._editor_open:
            return
        self._editor_overlay.set_nav_enabled(
            bool(self.canvas._arrow_target(Qt.Key.Key_Left, shift=False)),
            bool(self.canvas._arrow_target(Qt.Key.Key_Right, shift=False)),
            bool(self.canvas._arrow_target(Qt.Key.Key_Up, shift=False)),
            bool(self.canvas._arrow_target(Qt.Key.Key_Down, shift=False)),
        )

    def _build_adjacent_card(self) -> QFrame:
        """Panel ADYACENTE al formulario (relación/hito) — decisión de producto:
        estos editores no van al drawer derecho (reservado al riego)."""
        card = QFrame(self)
        card.setObjectName("focoAdjacentCard")
        card.setStyleSheet(
            f"QFrame#focoAdjacentCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {LINE_SOFT}; border-radius: {RADIUS_LG}px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_MD)
        layout.setSpacing(6)
        header = QHBoxLayout()
        self._adjacent_title = ElidedLabel("", card)
        self._adjacent_title.setStyleSheet(
            f"color: {INK_STRONG}; font-weight: 700; font-size: 13px; "
            "border: none; background: transparent;"
        )
        header.addWidget(self._adjacent_title, 1)
        close_button = QPushButton("✕", card)
        close_button.setFixedSize(24, 24)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {LINE_SOFT}; border-radius: 12px; "
            f"background: transparent; color: {INK_SOFT}; }}"
        )
        close_button.clicked.connect(self.close_adjacent)
        header.addWidget(close_button, 0)
        layout.addLayout(header)
        self._adjacent_scroll = QScrollArea(card)
        self._adjacent_scroll.setWidgetResizable(True)
        self._adjacent_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._adjacent_scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        layout.addWidget(self._adjacent_scroll, 1)
        card.hide()
        return card

    def _position_overlays(self) -> None:
        # UI2-09: una recolocación explícita manda sobre el deslizamiento.
        if self._center_anim is not None:
            self._center_anim.stop()
            self._center_anim = None
        # UI2-16: el editor fullscreen cubre TODO el lienzo.
        if self._editor_open:
            self._editor_overlay.setGeometry(self.rect())
            self._editor_overlay.raise_()
            # BETA2-FOCO-27: el cajón inferior sigue el borde inferior del editor.
            self._bottom_sheet.reposition(self._editor_overlay.editor_card.geometry())
        hole = self.canvas.center_hole_rect()
        # Con formulario embebido la tarjeta usa TODO el hueco central; el
        # resumen compacto solo necesita la franja superior.
        card_height = (
            int(hole.height()) if self._form_panel is not None else int(min(hole.height(), 170))
        )
        self._center_card.setGeometry(int(hole.x()), int(hole.y()), int(hole.width()), card_height)
        # UI2-18: ⛶ en la esquina superior DERECHA de la tarjeta (hijo de la
        # tarjeta → coordenadas locales; ancho = el hueco central).
        self._expand_button.move(int(hole.width()) - self._expand_button.width() - 10, 10)
        self._center_card.raise_()
        self.tool_rail.adjustSize()
        self.tool_rail.move(12, max(12, (self.height() - self.tool_rail.height()) // 2))
        self.tool_rail.raise_()
        if not self._adjacent_card.isHidden():
            # PULIDO-02: mínimo 320 — a 260 los badges y el stepper «Año fin»
            # del panel de hito no tenían sitio ni envolviendo.
            adjacent_width = max(320, min(440, self.width() - int(hole.right()) - 24))
            # BETA2-FOCO-29: el read card del hito iguala la ALTURA de la tarjeta de
            # entidad (mismo `y` y mismo alto = `hole.height()`), no casi toda la
            # columna. El contenido de lectura es corto y encaja; el fallback de
            # relación tiene scroll propio.
            adjacent_height = int(hole.height())
            self._adjacent_card.setGeometry(
                int(hole.right()) + 10, int(hole.y()), adjacent_width, adjacent_height
            )
            self._adjacent_card.raise_()
        if self._empty.isVisible():
            self._empty.adjustSize()
            self._empty.move(
                (self.width() - self._empty.width()) // 2,
                (self.height() - self._empty.height()) // 2,
            )
            self._empty.raise_()
        # FOCO-23: la tarjeta dual ocupa un hueco central AMPLIADO.
        if self._dual_card is not None and not self._dual_card.isHidden():
            width = self.width()
            height = self.height()
            self._dual_card.setGeometry(
                int(width * 0.06),
                int(height * 0.12),
                int(width * 0.88),
                int(height * 0.76),
            )
            self._dual_card.raise_()
            # FOCO-30: ✕ en la esquina superior derecha de la tarjeta dual.
            if self._dual_close is not None:
                self._dual_close.move(
                    self._dual_card.width() - self._dual_close.width() - SPACE_MD, SPACE_SM
                )
                self._dual_close.raise_()
            # BETA2-FOCO-29: el cajón del hito sigue el borde inferior del dual.
            self._bottom_sheet.reposition(self._dual_card.geometry())
        # UI2-18: con el editor abierto, el overlay es SIEMPRE lo más alto —
        # ningún raise_ intermedio (tarjeta, dual, back) lo tapa.
        if self._editor_open:
            self._editor_overlay.raise_()
        # BETA2-FOCO-29: el cajón inferior del hito, si está abierto, queda por
        # encima de todo (overlay del editor o tarjeta dual).
        if not self._bottom_sheet.isHidden():
            self._bottom_sheet.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_overlays()

    # ------------------------------------------------------------------
    # Ciclo de foco
    # ------------------------------------------------------------------

    def _project(self) -> Any:
        provider = self._project_provider
        return provider() if callable(provider) else None

    def _chronology_context(self) -> tuple[list[Any], int | None]:
        """BETA2-CAL-08: eras (contexto) + año presente del proyecto para la banda.

        Usa las mismas funciones puras que la cronología global/grafo
        (``effective_eras``/``explicit_present_year``); si algo falla, degrada a
        sin-contexto (la banda sigue funcionando solo con lapso + hitos)."""
        project = self._project()
        if project is None:
            return ([], None)
        try:
            from hosts.DesktopHostPySide.widgets.chrono_canvas import (
                effective_eras,
                explicit_present_year,
            )

            return (list(effective_eras(project) or []), explicit_present_year(project))
        except Exception:
            return ([], None)

    def current_entity_id(self) -> str:
        return self._center_id

    def _on_ring_banner_clicked(self) -> None:
        """BETA2-CLEANUP-PANELES: click en la píldora «Anillo: …» ⇒ abre el panel
        de anillo (edición) del anillo actual. En «Sin anillo» no hace nada
        (para crear un anillo está el botón del rail izquierdo)."""
        project = self._project()
        if project is None or not self._center_id:
            return
        ring_id = ring_id_for(project, self._center_id)
        if ring_id:
            self.ringEditRequested.emit(ring_id)

    def refresh(self) -> None:
        """Entra/reentra en Foco: última entidad trabajada, o primera, o vacío."""
        project = self._project()
        if project is None or not getattr(project, "entities", None):
            self._center_id = ""
            self.close_editor()  # UI2-16: sin proyecto no hay edición inmersiva
            self.canvas.set_zones("", {})
            self._center_card.hide()
            self._empty.show()
            self._position_overlays()
            self._refresh_tool_context()
            return
        self._empty.hide()
        candidate = self._center_id
        if not candidate or project.entity_by_id(candidate) is None:
            candidate = ""
            if callable(self._last_entity_getter):
                candidate = str(self._last_entity_getter() or "")
            if not candidate or project.entity_by_id(candidate) is None:
                candidate = project.entities[0].id
        self.center_entity(candidate)

    def center_entity(self, entity_id: str) -> None:
        """Centra una entidad: reconstruye zonas y recuerda la última trabajada."""
        project = self._project()
        if project is None:
            return
        entity = project.entity_by_id(str(entity_id))
        if entity is None:
            self.refresh()
            return
        # FOCO-23: cualquier recentrado abandona el modo dual.
        if self._dual is not None:
            self._teardown_dual()
        self._center_id = entity.id
        if callable(self._last_entity_setter):
            # Best-effort: recordar el foco jamás debe romper el centrado.
            self._last_entity_setter(entity.id)

        self.close_adjacent()
        self._rebuild_canvas(project, entity)
        self._update_center_card(entity)
        # UI2-18: con el editor abierto la tarjeta de lectura queda oculta
        # (el overlay la cubre); nunca debe reaparecer al recentrar/navegar.
        self._center_card.setVisible(not self._editor_open)
        self._position_overlays()
        self._play_center_transition()  # UI2-09: ráfaga + deslizamiento
        self._refresh_tool_context()
        self.entityCentered.emit(entity.id)

    # ── UI2-09: transición al recentrar (viento + deslizamiento) ───────────

    def _on_satellite_activated(self, entity_id: str) -> None:
        """El viento acompaña la navegación: la dirección de la transición va
        del satélite activado hacia el centro (clic y flechas)."""
        self._pending_transition = self._transition_direction(str(entity_id))
        self.center_entity(entity_id)

    def _transition_direction(self, entity_id: str) -> tuple[float, float] | None:
        # FOCO-30: la posición puede venir de un chip de banda O de una tarjeta de
        # ruleta (rotación del anillo) — scene_pos_for cubre ambas.
        pos = self.canvas.scene_pos_for(entity_id)
        if pos is None:
            return None
        source = self.canvas.mapFromScene(pos)
        hole = self.canvas.center_hole_rect()
        dx = float(hole.x() + hole.width() / 2.0 - source.x())
        dy = float(hole.y() + hole.height() / 2.0 - source.y())
        norm = math.hypot(dx, dy)
        if norm <= 1e-6:
            return None
        return (dx / norm, dy / norm)

    def _transition_ms(self) -> int:
        """Gate de animación (patrón de la casa): 0 = sin movimiento."""
        if self.ctx is None:
            return 0
        try:
            return int(self.ctx.animation_duration(180))
        except Exception:  # noqa: BLE001 — la transición jamás rompe el centrado
            return 0

    def _play_center_transition(self) -> None:
        """Consume la dirección pendiente: ráfaga de hojas + la tarjeta entra
        deslizándose desde el lado del satélite (QVariantAnimation sobre pos,
        sin QGraphicsEffect). Con el gate cerrado, colocación instantánea."""
        hint = self._pending_transition
        self._pending_transition = None
        duration = self._transition_ms()
        if not hint or duration <= 0:
            return
        dx, dy = hint
        self.canvas._atmosphere.gust(dx, dy)
        final_pos = self._center_card.pos()
        start_pos = QPoint(final_pos.x() - int(dx * 28), final_pos.y() - int(dy * 28))
        if self._center_anim is not None:
            self._center_anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(start_pos)
        anim.setEndValue(final_pos)
        anim.setDuration(duration)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._center_card.move)
        anim.finished.connect(lambda: setattr(self, "_center_anim", None))
        self._center_anim = anim
        self._center_card.move(start_pos)
        anim.start()

    def _rebuild_canvas(self, project: Any, entity: Any) -> None:
        # FOCO-25: vecindario organizado por POSICIÓN DE ANILLO (foco_rings).
        zones = classify_ring_neighbors(project, entity.id)
        zones_payload: dict[str, list[dict]] = {}
        for zone in ("raices", "entorno", "brotes"):
            entries: list[dict] = []
            for neighbor in zones[zone]:
                payload = self._ring_neighbor_dict(project, neighbor, zone)
                if payload is not None:
                    entries.append(payload)
            zones_payload[zone] = entries
        branch_mates = [
            payload
            for neighbor in zones["branch_mates"]
            if (payload := self._ring_neighbor_dict(project, neighbor, "branch")) is not None
        ]
        # FOCO-22: la cadena de contención se dibuja como MARCO, no satélites.
        # FOCO-26: las CO-MADRES directas extra no se encadenan como ancestras
        # (render honesto): la primera es el marco y las demás se anotan en su
        # pestaña como «también en X».
        direct = direct_containments(project, entity.id)
        primary_id = direct[0][0] if direct else ""
        sibling_ids = {container_id for container_id, _rid in direct[1:]}
        also_in = " · ".join(
            str(getattr(project.entity_by_id(cid), "name", "") or "") for cid in sorted(sibling_ids)
        )
        containers_payload = []
        for container in classify_containers(project, entity.id):
            if container.entity_id in sibling_ids:
                continue  # co-madre extra: chip en la pestaña, no marco ancestro
            meta = {
                "entity_id": container.entity_id,
                "name": getattr(project.entity_by_id(container.entity_id), "name", ""),
                "is_ghost": container.is_ghost,
            }
            if container.entity_id == primary_id and also_in:
                meta["also_in"] = also_in
            containers_payload.append(meta)
        # FOCO-25: rotación por el anillo (←/→) y salto de anillo (Shift+↑/↓).
        nav = ring_navigation(project, entity.id)
        previews: dict[str, dict] = {}
        prev_preview = self._preview_dict(project, nav.prev, "← anterior")
        next_preview = self._preview_dict(project, nav.next, "siguiente →")
        if prev_preview is not None:
            previews["prev"] = prev_preview
        if next_preview is not None:
            previews["next"] = next_preview
        nav_targets = {
            "prev": nav.prev,
            "next": nav.next,
            "up": nav.up,
            "down": nav.down,
            "container": nav.container,
            "member": nav.member,
        }
        # BETA2-IMG: la raíz de assets sigue a la ruta del proyecto (retratos).
        current_path = getattr(getattr(self.ctx, "project_controller", None), "current_path", None)
        self.canvas.set_assets_root(assets_root_for(Path(current_path)) if current_path else None)
        self.canvas.set_zones(
            entity.id,
            zones_payload,
            containers=containers_payload,
            branch_mates=branch_mates,
            previews=previews,
            nav_targets=nav_targets,
        )
        # FOCO-26: píldora del anillo del centro (esquina de rotación).
        ring_name, position, total = ring_display_info(project, entity.id)
        self.canvas.set_ring_label(f"Anillo: {ring_name} ({position}/{total})")

    def _ring_neighbor_dict(self, project: Any, neighbor: Any, zone: str) -> dict | None:
        other = project.entity_by_id(neighbor.entity_id)
        if other is None:
            return None
        if zone == "branch":
            link_label = "misma rama"
        elif getattr(neighbor, "relation_id", ""):
            link_label = self._relation_label(project, neighbor.relation_id)
        elif zone == "raices":
            link_label = "anillo superior"
        elif zone == "brotes":
            link_label = "anillo inferior"
        else:
            link_label = "mismo anillo"
        entity_type = getattr(other.entity_type, "value", str(other.entity_type))
        ring_name, _pos, _total = ring_display_info(project, other.id)
        return {
            "entity_id": other.id,
            "name": other.name,
            "entity_type": entity_type,
            "is_ghost": neighbor.is_ghost,
            "zone": "entorno" if zone == "branch" else zone,
            "reason": zone,
            "ring_id": getattr(neighbor, "ring_id", ""),
            "rank": getattr(neighbor, "rank", None),
            "link_label": link_label,
            # FOCO-30: metadatos del despliegue por hover (retrato + tipo + anillo).
            "ring_name": str(ring_name or ""),
            "nature": "Rama" if is_branch_type(entity_type) else "Hoja",
            # BETA2-HOVER: descripción ENTERA (la tarjeta flotante la muestra completa).
            "brief": " ".join(str(getattr(other, "brief_description", "") or "").split()),
            **_portrait_meta(other),
        }

    def _preview_dict(self, project: Any, entity_id: str, label: str) -> dict | None:
        if not entity_id:
            return None
        other = project.entity_by_id(entity_id)
        if other is None:
            return None
        return {
            "entity_id": other.id,
            "name": other.name,
            "entity_type": getattr(other.entity_type, "value", str(other.entity_type)),
            "is_ghost": getattr(getattr(other, "canon_state", None), "value", "") == "fantasma",
            "zone": "entorno",
            "reason": "rotacion",
            "link_label": label,
            # FOCO-30: descripción para la tarjeta plegada de rotación (se recorta al pintar).
            "brief": " ".join(str(getattr(other, "brief_description", "") or "").split()),
            **_portrait_meta(other),
        }

    @staticmethod
    def _relation_label(project: Any, relation_id: str) -> str:
        """Texto corto del vínculo por el tipo de relación (o «pendiente»)."""
        if not relation_id:
            return ""
        for relation in getattr(project, "relations", []) or []:
            if relation.id == relation_id:
                kind = getattr(relation.relation_type, "value", str(relation.relation_type))
                label = enum_human(kind)
                ghost_rel = (
                    getattr(getattr(relation, "canon_state", None), "value", "") == "fantasma"
                )
                return f"{label} (pendiente)" if ghost_rel else label
        return ""

    def _form_capable(self) -> bool:
        return self.ctx is not None and self.entity_controller is not None

    def _refresh_lifeline(self, entity: Any) -> None:
        eras, present_year = self._chronology_context()
        self.lifeline.set_entity(
            entity,
            self._list_entity_milestones(entity.id),
            eras=eras,
            present_year=present_year,
        )
        self.lifeline.show()

    def _list_entity_milestones(self, entity_id: str) -> list[Any]:
        # El controller del host lo llama list_for_leaf; el servicio, list_hitos_for_leaf.
        lister = getattr(self.milestone_controller, "list_for_leaf", None) or getattr(
            self.milestone_controller, "list_hitos_for_leaf", None
        )
        if not callable(lister):
            return []
        result = lister(entity_id)
        value = getattr(result, "value", result)
        return value if isinstance(value, list) else []

    def _list_relation_milestones(self, relation_id: str) -> list[Any]:
        lister = getattr(self.milestone_controller, "list_for_relation", None)
        if not callable(lister):
            return []
        result = lister(relation_id)
        value = getattr(result, "value", result)
        return value if isinstance(value, list) else []

    def _relation_by_id(self, relation_id: str) -> Any:
        project = self._project()
        if project is None or not relation_id:
            return None
        for relation in getattr(project, "relations", []) or []:
            if str(getattr(relation, "id", "")) == str(relation_id):
                return relation
        return None

    def _on_lifeline_span_edited(self, entity_id: str, birth: int, death: Any) -> None:
        # Re-emite hacia el workspace (persistencia por EntityController) y
        # refresca el lienzo: el lapso puede recolocar hitos por zona.
        self.lifespanEdited.emit(entity_id, birth, death)
        self._on_form_saved()

    def _on_dual_entity_lifespan_edited(self, entity_id: str, birth: int, death: Any) -> None:
        """BETA2-FOCO-29: persiste el lapso de una entidad del DUAL por el
        controller SIN el refresco global diferido (que desmontaría el dual)."""
        controller = self.entity_controller
        if controller is None or not entity_id:
            return
        result = controller.update(
            str(entity_id),
            {"birth_year": int(birth), "death_year": None if death is None else int(death)},
        )
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.dataChanged.emit()

    def _on_relation_lifespan_edited(self, relation_id: str, birth: int, death: Any) -> None:
        """BETA2-FOCO-29: persiste el lapso de la RELACIÓN del dual por su
        controller (mismo payload birth/death que el panel de relación)."""
        controller = self.relation_controller
        if controller is None or not relation_id:
            return
        result = controller.update(
            str(relation_id),
            {"birth_year": int(birth), "death_year": None if death is None else int(death)},
        )
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.dataChanged.emit()

    def _refresh_dual_lifelines(self) -> None:
        """BETA2-FOCO-29: repuebla las 3 bandas del dual (A, relación, B)."""
        if not self._dual or len(self._dual_lifelines) != 3:
            return
        project = self._project()
        if project is None:
            return
        a = project.entity_by_id(self._dual.get("a", ""))
        b = project.entity_by_id(self._dual.get("b", ""))
        relation = self._relation_by_id(self._dual.get("relation", ""))
        band_a, band_rel, band_b = self._dual_lifelines
        for band, subject, is_rel in (
            (band_a, a, False),
            (band_rel, relation, True),
            (band_b, b, False),
        ):
            if band is None or subject is None:
                continue
            milestones = (
                self._list_relation_milestones(subject.id)
                if is_rel
                else self._list_entity_milestones(subject.id)
            )
            band.set_entity(subject, milestones)

    def _milestone_by_id(self, milestone_id: str) -> Any:
        project = self._project()
        if project is None or not milestone_id:
            return None
        for hito in getattr(project, "causal_milestones", []) or []:
            if str(getattr(hito, "id", "")) == str(milestone_id):
                return hito
        return None

    def _active_card_rect(self):
        """BETA2-FOCO-29: rect (coords de la vista) de la tarjeta activa sobre la
        que se despliega el cajón inferior del hito: editor, dual o lectura."""
        if self._editor_open:
            return self._editor_overlay.editor_card.geometry()
        if self._dual_card is not None:
            return self._dual_card.geometry()
        return self._center_card.geometry()

    def _build_milestone_panel(self, milestone_id: str) -> Any:
        """Panel COMPLETO editable del hito (mismo que la cronología global)."""
        from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

        return MilestoneDetailPanel(
            self.ctx,
            self.milestone_controller,
            milestone_id,
            entity_controller=self.entity_controller,
            on_saved=self._on_milestone_panel_saved,
        )

    def _on_milestone_panel_saved(self) -> None:
        """Tras guardar el hito en el cajón: refrescar la cronología del modo
        activo (banda única del editor/lectura o las bandas del dual)."""
        if self._dual is not None:
            self._refresh_dual_lifelines()
        else:
            self._refresh_lifeline_current()
        self.dataChanged.emit()

    def _open_milestone_for_mode(self, milestone_id: str) -> None:
        """BETA2-FOCO-27: clic en un hito — editable en el cajón inferior si el
        editor está abierto; solo lectura a la derecha en la descripción."""
        if self.ctx is None or self.milestone_controller is None or not milestone_id:
            return
        if self._editor_open or self._dual is not None:
            self._open_milestone_editable(milestone_id)
        else:
            self._open_milestone_read_card(milestone_id)

    def _open_milestone_read_card(self, milestone_id: str) -> None:
        """Descripción: tarjeta compacta de SOLO lectura a la derecha."""
        from hosts.DesktopHostPySide.widgets.foco.milestone_read_card import MilestoneReadCard
        from hosts.DesktopHostPySide.widgets.milestone_labels import milestone_temporal_label

        hito = self._milestone_by_id(milestone_id)
        if hito is None:
            return
        card = MilestoneReadCard(hito, temporal_label=milestone_temporal_label(hito))
        self.open_adjacent_widget(card, "Hito")

    def _open_milestone_editable(self, milestone_id: str) -> None:
        """Edición: cajón inferior con el panel completo editable del hito."""
        if not milestone_id:
            return
        panel = self._build_milestone_panel(milestone_id)
        self._bottom_sheet.set_content(panel, "Hito")
        self._bottom_sheet.open_over(self._active_card_rect())

    def open_milestone_editable(self, milestone_id: str) -> None:
        """Público (workspace): abrir un hito recién creado en el cajón inferior."""
        if self._editor_open:
            self._open_milestone_editable(milestone_id)

    def is_editor_open(self) -> bool:
        return self._editor_open

    def _refresh_lifeline_current(self) -> None:
        project = self._project()
        if project is None or not self._center_id:
            return
        entity = project.entity_by_id(self._center_id)
        if entity is not None:
            self._refresh_lifeline(entity)

    def refresh_lifeline(self) -> None:
        """FOCO-25: refresco público de la banda local (hitos recién creados)."""
        self._refresh_lifeline_current()

    def _on_milestone_year_edited(self, milestone_id: str, year: int) -> None:
        """FOCO-25: persiste el año arrastrado del hito por el controller.

        Actualiza también el espejo ``temporality.year`` — si no, un hito con
        temporalidad rica (duración = lapso) quedaría con el inicio antiguo.
        """
        updater = getattr(self.milestone_controller, "update", None)
        if not callable(updater) or not milestone_id:
            return
        payload: dict = {"year": int(year)}
        project = self._project()
        if project is not None:
            for milestone in getattr(project, "causal_milestones", []) or []:
                if str(getattr(milestone, "id", "")) != str(milestone_id):
                    continue
                temporality = getattr(milestone, "temporality", None)
                if temporality is not None and hasattr(temporality, "to_dict"):
                    payload["temporality"] = {**temporality.to_dict(), "year": int(year)}
                break
        result = updater(str(milestone_id), payload)
        if isinstance(result, Error):
            self._log_error(result.error)
        self._refresh_lifeline_current()
        self.dataChanged.emit()

    def _on_milestone_end_year_edited(self, milestone_id: str, end_year: int) -> None:
        """UI2-14: persistir el FIN de un hito arrastrado en la banda local.

        El dominio no tiene end_year: el fin es duración en años sobre la
        temporality (mismo payload que el panel de detalle del hito)."""
        controller = self.milestone_controller
        updater = getattr(controller, "update", None) if controller is not None else None
        if not callable(updater) or not milestone_id:
            return
        project = self._project()
        milestone = None
        for candidate in getattr(project, "causal_milestones", []) or []:
            if str(getattr(candidate, "id", "")) == str(milestone_id):
                milestone = candidate
                break
        if milestone is None or getattr(milestone, "year", None) is None:
            return
        year = int(milestone.year)
        temporality = getattr(milestone, "temporality", None)
        temporality_data = (
            temporality.to_dict()
            if temporality is not None and hasattr(temporality, "to_dict")
            else {}
        )
        temporality_data["year"] = year
        if int(end_year) > year:
            temporality_data["is_duration"] = True
            temporality_data["duration_value"] = int(end_year) - year
            temporality_data["duration_unit"] = "años"
        else:
            # Fin deshecho: el hito vuelve a ser puntual.
            temporality_data["is_duration"] = False
            temporality_data["duration_value"] = None
            temporality_data["duration_unit"] = None
        result = updater(str(milestone_id), {"year": year, "temporality": temporality_data})
        if isinstance(result, Error):
            self._log_error(result.error)
        self._refresh_lifeline_current()
        self.dataChanged.emit()

    def _apply_watering_tone(self) -> None:
        """FOCO-26: tono del editor según el estado de riego (secada = oscuro).
        UI2-05: si el lote está regando la entidad centrada, manda «regando»."""
        status = ""
        if self._watering_active_id and self._watering_active_id == self._center_id:
            status = "regando"
        else:
            service = self.watering_service
            if service is not None and self._center_id:
                report = getattr(service.status_of(self._center_id), "value", None)
                status = getattr(report, "status", "") or ""
        self._center_card.setProperty("wateringState", status)
        # Re-polish: los selectores por property no se reevalúan solos.
        style = self._center_card.style()
        style.unpolish(self._center_card)
        style.polish(self._center_card)
        # UI2-16: el editor fullscreen comparte el tono del estado de riego.
        overlay = getattr(self, "_editor_overlay", None)
        if overlay is not None:
            overlay.editor_card.setProperty("wateringState", status)
            card_style = overlay.editor_card.style()
            card_style.unpolish(overlay.editor_card)
            card_style.polish(overlay.editor_card)

    def _refresh_reading_card(self, entity: Any) -> None:
        """UI2-19: refresca los widgets de LECTURA de la tarjeta (cronología,
        tono de riego, retrato, nombre, breve, resumen de metadatos) SIN remontar
        el formulario ni tocar las pestañas. Lo llaman el autosave del editor
        (_on_form_saved) y el cierre del editor — así un cambio se ve al instante
        sin destruir el formulario que el usuario está escribiendo."""
        self._refresh_lifeline(entity)
        self._apply_watering_tone()
        self._refresh_portrait_band(entity)  # UI2-06: retrato siempre presente
        self._refresh_contents_shelf(entity)  # FOCO-30: estantería si es rama
        self._name_label.setText(entity.name)
        brief = " ".join(str(entity.brief_description or "").split())
        self._brief_label.setText(brief[:280] + ("…" if len(brief) > 280 else ""))
        if self._form_capable():
            self._refresh_meta_summary(entity)

    def _member_thumb_pixmap(self, entity: Any, assets_root):
        """FOCO-30: retrato cuadrado de un contenido (o glifo de tipo si no hay foto)."""
        from hosts.DesktopHostPySide.widgets import portrait_cache

        meta = _portrait_meta(entity)
        if meta["image_path"]:
            resolved = portrait_cache.resolve_stored(assets_root, meta["image_path"])
            pixmap = portrait_cache.portrait_pixmap(resolved, meta["image_crop"], _SHELF_THUMB)
            if pixmap is not None:
                return pixmap.scaled(
                    _SHELF_THUMB,
                    _SHELF_THUMB,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
        entity_type = getattr(entity.entity_type, "value", str(entity.entity_type))
        return icons.entity_glyph_pixmap(entity_type, size=_SHELF_THUMB - 18, color=INK_SOFT)

    def _refresh_contents_shelf(self, entity: Any) -> None:
        """FOCO-30: llena la estantería con las miniaturas de los contenidos de la
        rama enfocada (clic = entrar); se oculta para las hojas."""
        layout = getattr(self, "_contents_layout", None)
        if layout is None:
            return
        while layout.count() > 1:  # conserva el stretch final
            taken = layout.takeAt(0)
            widget = taken.widget() if taken is not None else None
            if widget is not None:
                widget.deleteLater()
        project = self._project()
        if project is None or not is_branch(entity):
            self._contents_shelf.hide()
            return
        members = branch_members(project, entity.id)
        if not members:
            self._contents_shelf.hide()
            return
        current_path = getattr(getattr(self.ctx, "project_controller", None), "current_path", None)
        assets_root = assets_root_for(Path(current_path)) if current_path else None
        for member_id in members:
            other = project.entity_by_id(member_id)
            if other is None:
                continue
            thumb = _ContentThumb(
                member_id, other.name, self._member_thumb_pixmap(other, assets_root)
            )
            thumb.clicked.connect(self.center_entity)
            layout.insertWidget(layout.count() - 1, thumb)
        self._contents_shelf.show()

    def _update_center_card(self, entity: Any) -> None:
        self._refresh_reading_card(entity)
        if self._form_capable():
            # UI2-18: al navegar con el editor abierto se conserva la pestaña que
            # el usuario está viendo (entidad 1 en «Relaciones» → entidad 2 en
            # «Relaciones»); con el editor cerrado se recuerda la última (_last_tab).
            keep_tab = self._tab_bar.current() if self._editor_open else self._last_tab
            self._mount_form(entity.id)
            # UI2-16: tarjeta de LECTURA — nombre, resumen de metadatos con
            # mini-iconos, breve y franja; la edición vive en el fullscreen.
            # (el resumen de metadatos ya lo refrescó _refresh_reading_card.)
            self._type_label.hide()
            # UI2-18: los widgets de LECTURA solo se muestran si el editor NO está
            # abierto — si no, reaparecerían por encima del overlay.
            if not self._editor_open:
                self._meta_summary_box.show()
                for widget in (self._name_label, self._brief_label):
                    widget.show()
                self._expand_button.show()
                self._expand_button.raise_()
            self._tab_bar.set_current(keep_tab)
            self._apply_tab(keep_tab)
            self._refresh_next_step_chip()
            if self._editor_open:
                self._sync_editor_header(entity)
                self._refresh_editor_nav()
            return
        self._meta_summary_box.hide()
        self._expand_button.hide()
        if self._editor_open:
            self.close_editor()
        for widget in (self._name_label, self._type_label, self._brief_label):
            widget.show()
        self._refresh_next_step_chip()  # PULIDO-03: en resumen el chip vuelve
        self._name_label.setText(entity.name)
        type_value = getattr(entity.entity_type, "value", str(entity.entity_type))
        canon_value = getattr(entity.canon_state, "value", str(entity.canon_state))
        suffix = " · fantasma (borrador interno)" if canon_value == "fantasma" else ""
        self._type_label.setText(f"{type_value}{suffix}")
        brief = " ".join(str(entity.brief_description or "").split())
        self._brief_label.setText(brief[:280] + ("…" if len(brief) > 280 else ""))

    def _mount_form(self, entity_id: str) -> None:
        """Instancia NUEVA del formulario por recentrado (patrón de la casa).

        FOCO-26: el scroll central monta [Cuaderno de cultivo + formulario] —
        el riego GUÍA desde el propio editor (informe vigente, siguiente paso,
        historial íntegro); el drawer queda para el riego por lotes.
        """
        from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

        if self._form_panel is not None:
            self._form_panel.deleteLater()
        self._form_panel = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            entity_id,
            variant="foco",
            relation_controller=self.relation_controller,
            milestone_controller=self.milestone_controller,
            on_saved=self._on_form_saved,
            # UI2-06: el retrato resuelto alimenta la banda de la TARJETA.
            on_portrait=self._set_card_portrait,
        )
        self._form_scroll.setWidget(self._form_panel)
        # UI2-06: pestaña Relaciones — lista viva de relaciones clicables
        # (mismo flujo adyacente/dual y mismo «+» del rail que antes).
        old_relations = self._relations_scroll.takeWidget()
        if old_relations is not None:
            old_relations.deleteLater()
        self._relations_panel = FocoRelationsPanel(
            self.ctx,
            entity_id,
            # UI2-13: una relación se abre en DUAL (dos entidades + relación).
            on_open_relation=self._open_relation_dual,
            on_create_relation=lambda: self._on_tool("create_relation"),
            # BETA2-FOCO-27: crear una entidad NUEVA ya relacionada (flujo del rail).
            on_create_related=lambda: self._on_tool("create_related"),
        )
        self._relations_scroll.setWidget(self._relations_panel)
        # UI2-06: pestaña Cultivo — el Cuaderno completo (métricas, informe,
        # historial), fuera del camino del texto.
        old_cultivo = self._cultivo_scroll.takeWidget()
        if old_cultivo is not None:
            old_cultivo.deleteLater()
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        self.notebook = CultivationNotebook(
            self.watering_service, container, history_provider=self.history_provider
        )
        self.notebook.waterRequested.connect(
            lambda: self.waterRequested.emit([self._center_id] if self._center_id else [])
        )
        self.notebook.suggestRequested.connect(self.suggestRequested)
        self.notebook.pauseToggled.connect(self._on_notebook_pause)
        self.notebook.set_entity(entity_id)
        # BETA2-MEM-09: la pestaña Cultivo muestra el estado de Memoria del elemento.
        mem_svc = getattr(self, "memory_service", None)
        if mem_svc is not None:
            from packages.domain.narrative_memory import MemoryTargetKind

            self.notebook.set_memory_provider(
                lambda eid: mem_svc.get_memory(MemoryTargetKind.ENTITY, eid).value if eid else None
            )
            self.notebook.memoryIssueAction.connect(self._on_memory_issue_action)
        self._refresh_next_step_chip()  # JARDIN-04: chip al día al recentrar
        container_layout.addWidget(self.notebook)
        container_layout.addStretch(1)
        self._cultivo_scroll.setWidget(container)

    def _on_memory_issue_action(self, entity_id: str, issue_id: str, status: str) -> None:
        """BETA2-MEM-09: aplica la acción de una incidencia de Memoria (vía servicio)."""
        mem_svc = getattr(self, "memory_service", None)
        if mem_svc is None or not entity_id:
            return
        from packages.domain.narrative_memory import MemoryTargetKind

        mem_svc.resolve_issue(
            MemoryTargetKind.ENTITY, entity_id, issue_id=issue_id, status=status
        )
        self.notebook.refresh_memory()

    def _on_notebook_pause(self, dry: bool) -> None:
        """Secar/Cultivar desde el Cuaderno — mismas rutas que el rail."""
        if not self._center_id:
            return
        if dry:
            self.dryRequested.emit(self._center_id)
        else:
            self.cultivateRequested.emit(self._center_id)

    def set_watering_active(self, entity_id: str) -> None:
        """UI2-05: el workspace marca qué entidad se está regando AHORA (""
        al terminar). Si coincide con el centro, la tarjeta lo señala y el
        Cuaderno deshabilita su botón Regar mientras dura.
        UI2-21: además, el lienzo hace latir en SAGE al satélite/marco regado —
        así desde el Foco se distingue SIEMPRE qué se riega (centrada o no)."""
        entity_id = str(entity_id or "")
        if entity_id == self._watering_active_id:
            return
        self._watering_active_id = entity_id
        self._apply_watering_tone()
        # UI2-21: pulso savia en el satélite/marco de rama del lienzo.
        self.canvas.set_watering_active(entity_id)
        running_center = bool(entity_id) and entity_id == self._center_id
        notebook = getattr(self, "notebook", None)
        if notebook is not None and hasattr(notebook, "set_watering_running"):
            try:
                notebook.set_watering_running(running_center)
            except RuntimeError:
                pass  # el widget pudo ser destruido por un recentrado
        # BETA2-FOCO-37: la franja también deshabilita «Regar» mientras se riega.
        strip = getattr(self, "cultivation_strip", None)
        if strip is not None and hasattr(strip, "set_watering_running"):
            try:
                strip.set_watering_running(running_center)
            except RuntimeError:
                pass

    def refresh_cultivation(self) -> None:
        """FOCO-26: refresco público del Cuaderno (tras regar/secar/cultivar)."""
        notebook = getattr(self, "notebook", None)
        if notebook is not None:
            try:
                notebook.refresh()
            except RuntimeError:
                pass  # el widget pudo ser destruido por un recentrado
        self._apply_watering_tone()
        self._refresh_next_step_chip()  # JARDIN-04: la urgencia pudo cambiar

    def _refresh_next_step_chip(self) -> None:
        """BETA2-JARDIN-04 + UI2-08 + FOCO-37: las micro-métricas y los controles
        de riego (Regar/Secar/Cultivar + punto palpitante) viven en la franja de
        cultivo del pie de la tarjeta — visibles en Ficha y Relaciones; en la
        pestaña Cultivo se ocultan porque ahí manda el Cuaderno."""
        strip = getattr(self, "cultivation_strip", None)
        if strip is None:
            return
        service = self.watering_service
        if service is None or not self._center_id:
            strip.hide()
            return
        # UI2-16: la franja vive en la tarjeta de lectura y en el pie del editor;
        # SOLO se oculta con el editor abierto en la pestaña Cultivo.
        if self._editor_open and self._tab_bar.current() == "cultivo":
            strip.hide()
            return
        report = getattr(service.status_of(self._center_id), "value", None)
        project = self._project()
        center = project.entity_by_id(self._center_id) if project is not None else None
        is_ghost = center is not None and self._canon_of(center) == "fantasma"
        strip.set_report(report, is_ghost=is_ghost)
        strip.show()

    def _on_form_saved(self, *args: Any) -> None:
        """Autosave del formulario: refresca el LIENZO (vecindario/estados) sin
        reconstruir el formulario — no se puede perder el cursor al escribir."""
        # FOCO-19: el nombre/tipo editados también se ven en el Mapa.
        self.dataChanged.emit()
        project = self._project()
        if project is None or not self._center_id:
            return
        entity = project.entity_by_id(self._center_id)
        if entity is not None:
            self._rebuild_canvas(project, entity)
            # UI2-19: la tarjeta de lectura refleja al instante lo editado
            # (nombre, breve, metadatos, retrato, cronología) sin remontar el
            # formulario — un cambio se ve de inmediato al guardar/cerrar.
            self._refresh_reading_card(entity)
            if self._relations_panel is not None:
                try:
                    self._relations_panel.refresh()
                except RuntimeError:
                    pass  # el widget pudo ser destruido por un recentrado

    # ------------------------------------------------------------------
    # Panel adyacente (relación / hito) — decisión 9: NO en el drawer derecho
    # ------------------------------------------------------------------

    def open_adjacent_widget(self, widget: QWidget, title: str) -> None:
        old = self._adjacent_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._adjacent_scroll.setWidget(widget)
        self._adjacent_title.setText(title)
        self._adjacent_card.show()
        self._position_overlays()

    def close_adjacent(self) -> None:
        if self._adjacent_card.isHidden():
            return
        old = self._adjacent_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._adjacent_card.hide()

    def _open_relation_adjacent(self, relation_id: str) -> None:
        if self.ctx is None or self.relation_controller is None or not relation_id:
            return
        from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

        panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            entity_controller=self.entity_controller,
            milestone_controller=self.milestone_controller,
            on_saved=self._on_form_saved,
        )
        self.open_adjacent_widget(panel, "Relación")

    def _open_relation_dual(self, relation_id: str) -> None:
        """UI2-13: una relación de la lista abre el modo DUAL (las dos
        entidades con la relación en medio). Fallback al panel adyacente si
        los extremos no se resuelven o no hay capacidad de formulario."""
        relation_id = str(relation_id or "")
        source_id, target_id = self._relation_endpoints(relation_id)
        other = target_id if source_id == self._center_id else source_id
        if not relation_id or not other or other == self._center_id or not self._form_capable():
            self._open_relation_adjacent(relation_id)
            return
        self.enter_dual(self._center_id, other, relation_id)

    # ------------------------------------------------------------------
    # FOCO-23: modo dual — dos entidades separadas por el panel de relación
    # ------------------------------------------------------------------

    def is_dual_active(self) -> bool:
        return self._dual is not None

    def _relation_between(self, a_id: str, b_id: str) -> str:
        project = self._project()
        for relation in getattr(project, "relations", []) or []:
            if {relation.source_id, relation.target_id} == {a_id, b_id}:
                return str(relation.id)
        return ""

    def _relation_endpoints(self, relation_id: str) -> tuple[str, str]:
        """UI2-13: inverso de _relation_between — extremos de una relación."""
        project = self._project()
        for relation in getattr(project, "relations", []) or []:
            if str(getattr(relation, "id", "")) == str(relation_id):
                return str(relation.source_id), str(relation.target_id)
        return "", ""

    def enter_dual(self, a_id: str, b_id: str, relation_id: str) -> None:
        """Abre el centro dual: formulario A | relación | formulario B.

        Se sale con DOBLE CLICK sobre una de las dos tarjetas de entidad (esa
        pasa a ser el foco único) o con Esc (vuelve a la central previa).
        """
        # UI2-16: el editor fullscreen nunca coexiste con el dual.
        if self._editor_open:
            self.close_editor()
        project = self._project()
        if (
            not self._form_capable()
            or self.relation_controller is None
            or project is None
            or project.entity_by_id(a_id) is None
            or project.entity_by_id(b_id) is None
            or not relation_id
        ):
            self.center_entity(b_id or a_id)
            return
        from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
        from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

        previous_center = self._center_id
        self._teardown_dual()
        self.close_adjacent()
        self._center_card.hide()
        self._dual = {"a": a_id, "b": b_id, "relation": relation_id, "previous": previous_center}

        card = QFrame(self)
        card.setObjectName("focoDualCard")
        card.setStyleSheet(
            f"QFrame#focoDualCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: {RADIUS_LG}px; }}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD)
        row.setSpacing(10)

        def _mount_column(widget: Any, stretch: int, band: Any | None) -> None:
            # BETA2-FOCO-29: cada columna = formulario (scroll) + cronología debajo.
            col = QVBoxLayout()
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(6)
            scroll = QScrollArea(card)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            scroll.setWidget(widget)
            col.addWidget(scroll, 1)
            if band is not None:
                col.addWidget(band)
            row.addLayout(col, stretch)

        def _dual_band(subject: Any, milestones: list[Any], on_span: Any) -> Any:
            # BETA2-FOCO-29: banda con LAPSO editable (sombra); los hitos se
            # visualizan y se editan clicándolos (panel completo en el cajón).
            band = FocoLifelineBand(card)
            band.set_read_only(False)
            band.set_lapso_editable_only(True)
            band.lifespanEdited.connect(on_span)
            band.milestoneActivated.connect(self._open_milestone_for_mode)
            eras, present_year = self._chronology_context()
            band.set_entity(subject, milestones, eras=eras, present_year=present_year)
            band.show()
            return band

        entity_a = project.entity_by_id(a_id)
        entity_b = project.entity_by_id(b_id)
        relation = self._relation_by_id(relation_id)
        panel_a = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            a_id,
            variant="foco",
            relation_controller=self.relation_controller,
            milestone_controller=self.milestone_controller,
            on_saved=self._on_form_saved,
        )
        relation_panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            entity_controller=self.entity_controller,
            milestone_controller=self.milestone_controller,
            on_saved=self._on_form_saved,
        )
        panel_b = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            b_id,
            variant="foco",
            relation_controller=self.relation_controller,
            milestone_controller=self.milestone_controller,
            on_saved=self._on_form_saved,
        )
        band_a = (
            _dual_band(
                entity_a, self._list_entity_milestones(a_id), self._on_dual_entity_lifespan_edited
            )
            if entity_a is not None
            else None
        )
        band_rel = (
            _dual_band(
                relation,
                self._list_relation_milestones(relation_id),
                self._on_relation_lifespan_edited,
            )
            if relation is not None
            else None
        )
        band_b = (
            _dual_band(
                entity_b, self._list_entity_milestones(b_id), self._on_dual_entity_lifespan_edited
            )
            if entity_b is not None
            else None
        )
        _mount_column(panel_a, 4, band_a)
        _mount_column(relation_panel, 3, band_rel)
        _mount_column(panel_b, 4, band_b)
        self._dual_panels = [panel_a, relation_panel, panel_b]
        self._dual_lifelines = [band_a, band_rel, band_b]
        # Salidas: doble click sobre una tarjeta de entidad / Esc.
        for widget in (card, panel_a, panel_b, relation_panel):
            widget.installEventFilter(self)

        # FOCO-30: ✕ para cerrar el dual (además de Esc, que ya funciona vía el
        # eventFilter de app). Hijo de la tarjeta, esquina superior derecha.
        self._dual_close = QPushButton("✕", card)
        self._dual_close.setFixedSize(24, 24)
        self._dual_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dual_close.setToolTip("Cerrar (Esc)")
        self._dual_close.setStyleSheet(
            f"QPushButton {{ border: 1px solid {LINE_SOFT}; border-radius: 12px; "
            f"background: {SURFACE_HI}; color: {INK_SOFT}; }} "
            f"QPushButton:hover {{ border-color: {GOLD_SOFT}; color: {INK_STRONG}; }}"
        )
        self._dual_close.clicked.connect(lambda: self.exit_dual())
        # El lienzo se despeja: sin satélites ni banda local mientras dura.
        self.canvas.set_zones(self._center_id or a_id, {})
        self.lifeline.hide()
        self._dual_card = card
        card.show()
        card.raise_()
        self._dual_close.raise_()
        self._position_overlays()

    def _teardown_dual(self) -> None:
        # BETA2-FOCO-29: el cajón inferior del hito no sobrevive al dual; las
        # bandas son hijas de la tarjeta dual y mueren con ella.
        self._bottom_sheet.close_sheet()
        if self._dual_card is not None:
            self._dual_card.hide()
            self._dual_card.deleteLater()
        self._dual_card = None
        self._dual_close = None  # FOCO-30: hijo de la tarjeta; muere con ella
        self._dual_panels = []
        self._dual_lifelines = []
        self._dual = None

    def exit_dual(self, focus_id: str = "") -> None:
        info = dict(self._dual or {})
        self._teardown_dual()
        target = focus_id or str(info.get("previous") or "") or self._center_id
        if target:
            self.center_entity(target)

    def showEvent(self, event: Any) -> None:  # noqa: N802 (API Qt)
        super().showEvent(event)
        app = QApplication.instance()
        if app is not None and not self._app_filter_installed:
            app.installEventFilter(self)
            self._app_filter_installed = True
        # FOCO-26 (defensivo): re-lanzar el layout con la geometría REAL en el
        # siguiente ciclo — si el refresh corrió con la vista oculta, el lienzo
        # y los overlays quedaban calculados con un viewport rancio.
        QTimer.singleShot(0, self._relayout_after_show)

    def _relayout_after_show(self) -> None:
        if not self.isVisible() or not self._center_id:
            return
        self.canvas._rebuild_scene()
        self._position_overlays()

    def hideEvent(self, event: Any) -> None:  # noqa: N802 (API Qt)
        super().hideEvent(event)
        app = QApplication.instance()
        if app is not None and self._app_filter_installed:
            app.removeEventFilter(self)
            self._app_filter_installed = False

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802 (API Qt)
        if self._dual is not None:
            if event.type() == QEvent.Type.MouseButtonDblClick:
                if len(self._dual_panels) == 3:
                    if obj is self._dual_panels[0]:
                        self.exit_dual(str(self._dual.get("a", "")))
                        return True
                    if obj is self._dual_panels[2]:
                        self.exit_dual(str(self._dual.get("b", "")))
                        return True
            elif (
                event.type() == QEvent.Type.KeyPress
                and getattr(event, "key", lambda: None)() == Qt.Key.Key_Escape
            ):
                self.exit_dual()
                return True
        elif (
            not self._editor_open
            and event.type() == QEvent.Type.MouseButtonDblClick
            and isinstance(obj, QWidget)
            and not isinstance(obj, QAbstractButton)
            and not isinstance(obj, FocoLifelineBand)
            and (obj is self._center_card or self._center_card.isAncestorOf(obj))
        ):
            # UI2-16: doble clic sobre la tarjeta de lectura = abrir el editor.
            self.open_editor()
            return True
        elif self._handle_nav_key(event):
            return True
        return super().eventFilter(obj, event)

    def _handle_nav_key(self, event: Any) -> bool:
        """FOCO-25: navegación por flechas SIN requerir foco en el lienzo.

        Filtro a nivel de aplicación: intercepta las flechas cuando el foco de
        teclado está en cualquier hijo del Foco que no sea un widget donde las
        flechas ya significan algo (texto, listas, combos, spins). Así el
        usuario navega aunque acabe de clicar el formulario o un botón.
        """
        if event.type() != QEvent.Type.KeyPress or not self._center_id or not self.isVisible():
            return False
        key = getattr(event, "key", lambda: None)()
        if key not in _NAV_KEYS:
            return False
        focus = QApplication.focusWidget()
        if focus is None or not (focus is self or self.isAncestorOf(focus)):
            return False
        if isinstance(focus, _ARROW_OWNERS):
            return False
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        target = self.canvas._arrow_target(key, shift=shift)
        if target:
            self._on_satellite_activated(target)  # UI2-09: con viento
        return True  # flecha de navegación: consumida aunque no haya destino

    # Accesos usados por la barra superior / rail (FOCO-11).
    def request_open_in_map(self) -> None:
        if self._center_id:
            self.openInMapRequested.emit(self._center_id)

    def request_open_in_chrono(self) -> None:
        if self._center_id:
            self.openInChronoRequested.emit(self._center_id)

    # ------------------------------------------------------------------
    # Rail de herramientas (FOCO-11): contexto de selección y acciones
    # ------------------------------------------------------------------

    @staticmethod
    def _canon_of(entity: Any) -> str:
        return str(getattr(getattr(entity, "canon_state", None), "value", "")).lower()

    def _selection_context(self) -> dict:
        project = self._project()
        center = (
            project.entity_by_id(self._center_id)
            if project is not None and self._center_id
            else None
        )
        selection = self.canvas.selected_ids()
        selection_has_ghost = False
        if project is not None:
            for selected_id in selection:
                other = project.entity_by_id(selected_id)
                if other is not None and self._canon_of(other) == "fantasma":
                    selection_has_ghost = True
                    break
        paused = list(getattr(project, "watering_paused_entity_ids", []) or [])
        return {
            "has_project": project is not None,
            "center_id": center.id if center is not None else "",
            "center_is_ghost": center is not None and self._canon_of(center) == "fantasma",
            "center_is_paused": center is not None and center.id in paused,
            # BETA2-FOCO-32: habilita «Crear entidad en la rama».
            "center_is_branch": center is not None and is_branch(center),
            "selection": selection,
            "selection_has_ghost": selection_has_ghost,
        }

    def _refresh_tool_context(self) -> None:
        self.tool_rail.set_selection_context(self._selection_context())

    def _log_error(self, message: str) -> None:
        log = getattr(self.ctx, "log", None)
        if callable(log):
            log("error", message)

    def _entities(self) -> list[Any]:
        project = self._project()
        return list(getattr(project, "entities", []) or []) if project is not None else []

    def _branch_candidates(self) -> list[Any]:
        return [
            entity
            for entity in self._entities()
            if str(getattr(getattr(entity, "entity_type", None), "value", "")).lower()
            in _BRANCH_TYPES
            and self._canon_of(entity) != "fantasma"
        ]

    def _ghost_target(self) -> str:
        """Fantasma sobre el que actúan Convertir/Vincular: el centro o la selección."""
        context = self._selection_context()
        if context["center_is_ghost"]:
            return context["center_id"]
        project = self._project()
        if project is not None:
            for selected_id in self.canvas.selected_ids():
                other = project.entity_by_id(selected_id)
                if other is not None and self._canon_of(other) == "fantasma":
                    return selected_id
        return ""

    def _recenter(self, entity_id: str | None = None) -> None:
        target = entity_id or self._center_id
        if target:
            self.center_entity(target)

    def _open_search_palette(self) -> None:
        """FOCO-25: paleta Ctrl+B para saltar a cualquier entidad, esté donde esté."""
        if self._project() is None:
            return
        self._popover = EntitySearchPopover(
            entities_provider=self._entities,
            on_pick=self.center_entity,
            placeholder="Ir a entidad…",
        )
        # Centrado bajo las píldoras de modo, DENTRO de la app (no en el borde).
        self._popover.open_below_top_center(self.canvas)
        self._popover.search_edit.setFocus()

    def _on_tool(self, tool_id: str) -> None:  # noqa: PLR0912 — dispatcher plano del rail
        anchor = self.tool_rail.anchor_for(tool_id)
        project = self._project()
        if project is None:
            return
        center_id = self._center_id
        if tool_id == "create_entity":
            self._popover = QuickCreatePopover(title="Nueva entidad", on_submit=self._create_entity)
            self._popover.open_next_to(anchor)
        elif tool_id == "create_ring":
            # BETA2-CLEANUP-PANELES: crear anillo desde el Foco. El panel de anillo
            # unificado se abre en el cajón del workspace (flota sobre el Foco).
            self.ringCreateRequested.emit()
        elif tool_id == "create_related" and center_id:
            self._popover = QuickCreatePopover(
                title="Nueva entidad relacionada", on_submit=self._create_related
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "create_branch" and center_id:
            self._popover = QuickCreatePopover(
                title="Nueva rama contenedora", on_submit=self._create_branch
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "ghost_node":
            self._popover = QuickCreatePopover(
                title="Nuevo nodo fantasma",
                submit_text="Crear fantasma",
                with_description=True,
                on_submit=self._create_ghost,
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "create_relation" and center_id:
            self._popover = EntitySearchPopover(
                entities_provider=self._entities,
                on_pick=self._relate_to,
                on_create_ghost=self._ghost_and_relate,
                exclude_ids={center_id},
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "ghost_relation" and center_id:
            self._popover = EntitySearchPopover(
                entities_provider=self._entities,
                on_pick=self._ghost_relate_to,
                on_create_ghost=self._ghost_and_relate,
                exclude_ids={center_id},
                placeholder="Vincular (pendiente) con…",
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "add_to_branch" and center_id:
            self._popover = EntitySearchPopover(
                entities_provider=self._branch_candidates,
                on_pick=self._add_to_branch,
                placeholder="Buscar rama…",
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "create_in_branch" and center_id:
            # BETA2-FOCO-32: crear una entidad DENTRO de la rama enfocada (el rail
            # solo habilita este tool cuando el centro es una rama).
            self._popover = QuickCreatePopover(
                title="Nueva entidad en la rama",
                with_description=True,
                on_submit=self._create_in_branch,
            )
            self._popover.open_next_to(anchor)
        elif tool_id == "ghost_convert":
            self._convert_ghost(self._ghost_target())
        elif tool_id == "ghost_link":
            ghost_id = self._ghost_target()
            if ghost_id:
                self._popover = EntitySearchPopover(
                    entities_provider=self._entities,
                    on_pick=lambda target_id, g=ghost_id: self._link_ghost(g, target_id),
                    exclude_ids={ghost_id},
                    only_real=True,
                    placeholder="Vincular fantasma con…",
                )
                self._popover.open_next_to(anchor)
        elif tool_id == "view_map":
            self.request_open_in_map()
        elif tool_id == "view_chrono":
            self.request_open_in_chrono()

    # -- acciones de creación/vinculación (todas vía controllers/servicios) --

    def _create_entity(self, payload: dict) -> None:
        if self.entity_controller is None:
            return
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.dataChanged.emit()
        self.center_entity(result.value.id)

    def _create_related(self, payload: dict) -> None:
        if self.entity_controller is None or self.relation_controller is None:
            return
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        relation = self.relation_controller.create(
            self._center_id, result.value.id, "esta_relacionado_con"
        )
        self.dataChanged.emit()
        if isinstance(relation, Error):
            self._log_error(relation.error)
            self._recenter()
            return
        # FOCO-23: modo dual — detallar ambas entidades y su relación.
        self.enter_dual(self._center_id, result.value.id, relation.value.id)

    def _create_branch(self, payload: dict) -> None:
        if self.entity_controller is None or self.relation_controller is None:
            return
        payload = dict(payload)
        payload["entity_type"] = "contenedor"
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        # FOCO-26: si el centro YA vive en otra rama, decide el asistente.
        self._contain_with_assistant(result.value.id)

    def _create_in_branch(self, payload: dict) -> None:
        # BETA2-FOCO-32: crea una entidad y la contiene en la rama enfocada
        # (CONTIENE rama→nueva, orientación inversa a create_branch). El foco
        # permanece en la rama para que la nueva aparezca en la estantería.
        if self.entity_controller is None or self.relation_controller is None:
            return
        branch_id = self._center_id
        if not branch_id:
            return
        result = self.entity_controller.create(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        relation = self.relation_controller.create(branch_id, result.value.id, "contiene")
        if isinstance(relation, Error):
            self._log_error(relation.error)
        self.dataChanged.emit()
        self.center_entity(branch_id)

    def _create_ghost(self, payload: dict) -> None:
        if self.ghost_service is None:
            return
        result = self.ghost_service.create_ghost(payload)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        # Nace vinculado (relación fantasma) al centro si lo hay → zona Entorno.
        if self._center_id:
            self.ghost_service.create_ghost_relation(self._center_id, result.value.id)
        self.dataChanged.emit()
        self._recenter()

    def _ghost_and_relate(self, name: str) -> None:
        """«No existe» en el popover de relación → fantasma + vínculo pendiente."""
        if self.ghost_service is None or not self._center_id:
            return
        result = self.ghost_service.create_ghost({"name": name})
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.ghost_service.create_ghost_relation(self._center_id, result.value.id)
        self.dataChanged.emit()
        self._recenter()

    def _relate_to(self, target_id: str) -> None:
        if self.relation_controller is None or not self._center_id:
            return
        result = self.relation_controller.create(self._center_id, target_id, "esta_relacionado_con")
        self.dataChanged.emit()
        if isinstance(result, Error):
            # Si el par YA está relacionado, se detalla la relación existente
            # en modo dual en vez de fallar en silencio.
            existing = self._relation_between(self._center_id, target_id)
            if existing:
                self.enter_dual(self._center_id, target_id, existing)
                return
            self._log_error(result.error)
            self._recenter()
            return
        # FOCO-23: modo dual también al vincular con una existente.
        self.enter_dual(self._center_id, target_id, result.value.id)

    def _ghost_relate_to(self, target_id: str) -> None:
        if self.ghost_service is None or not self._center_id:
            return
        result = self.ghost_service.create_ghost_relation(self._center_id, target_id)
        if isinstance(result, Error):
            self._log_error(result.error)
        self.dataChanged.emit()
        self._recenter()

    def _add_to_branch(self, branch_id: str) -> None:
        if self.relation_controller is None or not self._center_id:
            return
        # FOCO-26: si el centro YA vive en otra rama, decide el asistente.
        self._contain_with_assistant(branch_id)

    # -- Asistente de contención (FOCO-26) ------------------------------

    def _contain_with_assistant(self, branch_id: str) -> None:
        """Crea la contención rama→centro; si el centro ya estaba contenido por
        OTRA rama, abre el asistente visual mover/anidar (nunca en silencio)."""
        project = self._project()
        if project is None or not branch_id or not self._center_id:
            return
        existing = [
            (container_id, relation_id)
            for container_id, relation_id in direct_containments(project, self._center_id)
            if container_id != branch_id
        ]
        if not existing:
            self._containment_create(branch_id)
            return
        old_branch_id, old_relation_id = existing[0]
        overlay = getattr(self.window(), "modal_overlay", None)
        if overlay is None:
            # Respaldo defensivo sin overlay: mover (la opción menos ambigua).
            self._containment_move(branch_id, old_relation_id)
            return

        def _name(entity_id: str) -> str:
            entity = project.entity_by_id(entity_id)
            return str(getattr(entity, "name", "") or "")

        panel = ContainmentAssistantPanel(
            entity_name=_name(self._center_id),
            old_branch_name=_name(old_branch_id),
            new_branch_name=_name(branch_id),
        )
        panel.cancelled.connect(overlay.dismiss)
        panel.moveChosen.connect(
            lambda: (overlay.dismiss(), self._containment_move(branch_id, old_relation_id))
        )
        panel.nestChosen.connect(
            lambda: (
                overlay.dismiss(),
                self._containment_nest(branch_id, old_branch_id, old_relation_id),
            )
        )
        overlay.open_widget(panel)

    def _containment_create(self, branch_id: str) -> None:
        relation = self.relation_controller.create(branch_id, self._center_id, "contiene")
        if isinstance(relation, Error):
            self._log_error(relation.error)
        self.dataChanged.emit()
        self._recenter()

    def _containment_move(self, branch_id: str, old_relation_id: str) -> None:
        """Mover: la rama antigua deja de contener a la entidad."""
        result = self.relation_controller.delete(old_relation_id)
        if isinstance(result, Error):
            self._log_error(result.error)
        self._containment_create(branch_id)

    def _containment_nest(self, branch_id: str, old_branch_id: str, old_relation_id: str) -> None:
        """Anidar: antigua ⊃ nueva ⊃ entidad (la contención directa antigua se
        sustituye por la cadena)."""
        outer = self.relation_controller.create(old_branch_id, branch_id, "contiene")
        if isinstance(outer, Error):
            self._log_error(outer.error)
        result = self.relation_controller.delete(old_relation_id)
        if isinstance(result, Error):
            self._log_error(result.error)
        self._containment_create(branch_id)

    def _convert_ghost(self, ghost_id: str) -> None:
        if self.ghost_service is None or not ghost_id:
            return
        result = self.ghost_service.convert_to_entity(ghost_id)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.dataChanged.emit()
        if ghost_id != self._center_id:
            relation_id = self._relation_between(self._center_id, ghost_id)
            if relation_id:
                # FOCO-23: revisar la conversión en modo dual.
                self.enter_dual(self._center_id, ghost_id, relation_id)
                return
        self._recenter(ghost_id if ghost_id == self._center_id else None)

    def _link_ghost(self, ghost_id: str, target_id: str) -> None:
        if self.ghost_service is None:
            return
        result = self.ghost_service.link_to_existing(ghost_id, target_id)
        if isinstance(result, Error):
            self._log_error(result.error)
            return
        self.dataChanged.emit()
        # El fantasma desaparece: el foco pasa a la entidad real vinculada.
        if ghost_id == self._center_id:
            self.center_entity(target_id)
            return
        relation_id = self._relation_between(self._center_id, target_id)
        if relation_id:
            # FOCO-23: revisar el vínculo en modo dual.
            self.enter_dual(self._center_id, target_id, relation_id)
            return
        self._recenter()
