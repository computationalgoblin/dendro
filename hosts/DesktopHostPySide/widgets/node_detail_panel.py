"""Node detail panel — immersive entity editor for B31-CREATION-T01-B.

RightDrawer content opened from the graph when a node is selected. It reads and
updates entities through the UI controller.  Normal mode shows a warm, minimal
form with color picker, editable type, and non-blocking AI autocomplete.
Technical fields remain hidden unless advanced mode is active.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.widgets import icons, portrait_cache, portrait_flow
from hosts.DesktopHostPySide.widgets.field_help import glossary
from hosts.DesktopHostPySide.widgets.mention_support import attach_mention_support
from packages.application.structured_reference_service import (
    StructuredReferenceService,
    build_known_targets,
)
from packages.domain.narrative_memory import MemoryTargetKind
from hosts.DesktopHostPySide.widgets.design_system import (
    ENTITY_KIND_PALETTE,
    FONT_SERIF,
    GOLD,
    INK,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    INPUT_BG,
    LINE,
    LINE_SOFT,
    LINE_STRONG,
    SPACE_LG,
    SPACE_MD,
    SURFACE_HI,
    TYPE_H1_PX,
    Badge,
    FlowLayout,
    enum_human,
    meta_chip_style,
)
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from hosts.DesktopHostPySide.widgets.rigor_section import RigorSection
from packages.application.world_layer_causal import get_causal_rank, sort_layers_by_causal_rank
from packages.domain.entity import EntityType
from packages.domain.entity_taxonomy import (
    BEING_NATURES,
    OFFERED_ENTITY_TYPES,
    has_temporal_nature,
    is_branch_type,
)
from packages.application.temporal_dating import PENDING_NOTE
from packages.domain.result import Error
from packages.domain.temporal_models import TemporalPrecision
from packages.domain.temporal_span import TemporalSpan

# ---------------------------------------------------------------------------
# Warm palette constants
# ---------------------------------------------------------------------------
# BETA2-FOCO-20 (Editorial sereno): tokens del design system — los hexes
# cálidos locales duplicaban la paleta y desentonaban con la tarjeta de Foco.
_BG_DRAWER = SURFACE_HI
_TITLE_COLOR = INK_STRONG
_LABEL_COLOR = INK_SOFT
_MUTED_COLOR = INK_MUTED
_SUGGESTION_BG = INPUT_BG

# Default node colours per entity type (mirrors graph_canvas._NODE_COLORS).
# BETA1-UX04/UX07: paleta BOTÁNICA cálida (antes azules/lavandas frías que
# pintaban un swatch azul fuera de paleta en el editor). Debe coincidir con
# graph_canvas._NODE_COLORS.
# UI2-20: la ramitud (Rama/Hoja) se DERIVA del tipo vía is_branch_type
# (taxonomía + rol legado 'contenedor'); ya no hay set local de tipos de rama.

# UX15: paleta cálida por tipo centralizada en el design system (antes duplicada).
_NODE_COLORS: dict[str, str] = ENTITY_KIND_PALETTE

# ---------------------------------------------------------------------------
# Creative AI system prompt (Spanish, separate from help-chatbot prompt)
# ---------------------------------------------------------------------------
_ENTITY_AI_PROMPT_ES = (
    "Eres un asistente creativo dentro de Dendro. Debes mejorar o completar "
    "la descripción del elemento narrativo seleccionado. "
    "Respeta el género, tono, realismo y configuración del proyecto. "
    "No contradigas el canon existente. No crees relaciones ni entidades nuevas "
    "salvo que se pida explícitamente. "
    "Devuelve solo el texto sugerido. No uses formato JSON ni Entity/Name/Type. "
    "Responde en español."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _default_color_for_type(entity_type_str: str) -> str:
    """Return the default hex colour for *entity_type_str*, or a fallback."""
    return _NODE_COLORS.get((entity_type_str or "").lower(), "#8EA4C8")


def _is_undetermined(precision: Any) -> bool:
    """¿La precisión temporal está sin determinar (o ausente)? — FIX-12."""
    raw = _enum_value(precision, "").strip()
    return not raw or raw == TemporalPrecision.UNKNOWN.value


# BETA-AUDIT-02: subconjunto legible de VisibilityState para la Ficha. Los cuatro
# reservados coinciden EXACTAMENTE con los tokens que oculta a la IA
# packages/application/ai_privacy.py, para que la etiqueta no prometa de más.
_VISIBILITY_CHOICES: tuple[tuple[str, str], ...] = (
    ("visible_usuario", "Visible"),
    ("privado_autor", "Privada — solo para mí"),
    ("secreto_mundo", "Secreta en el mundo"),
    ("preparado_no_revelado", "Preparada, aún sin revelar"),
    ("no_exportable", "No exportable"),
)


def _meta_chip(icon_name: str, combo: QComboBox, tooltip: str) -> QWidget:
    """UI2-12: chip de metadato de la Ficha — icono SVG 14px + combo cápsula.

    El icono identifica QUÉ selecciona el chip (decisión de producto: icono +
    tooltip, sin labels de formulario); el tooltip explica el detalle."""
    wrapper = QWidget()
    row = QHBoxLayout(wrapper)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    glyph = QLabel(wrapper)
    glyph.setPixmap(icons.pixmap(icon_name, size=14, color=INK_MUTED))
    glyph.setFixedSize(16, 16)
    glyph.setStyleSheet("background: transparent; border: none;")
    row.addWidget(glyph)
    row.addWidget(combo)
    for widget in (wrapper, glyph, combo):
        widget.setToolTip(tooltip)
    return wrapper


# ---------------------------------------------------------------------------
# Non-blocking AI worker
# ---------------------------------------------------------------------------

class _NodeAIWorker(QThread):
    """Runs AI node action in a background thread; emits *finished* on completion."""

    finished = Signal(str, str)  # (text_or_empty, error_or_empty)

    def __init__(
        self,
        ai_controller,
        entity_id: str,
        prompt_hint: str,
        language: str = "es",
    ):
        super().__init__()
        self.ai_controller = ai_controller
        self.entity_id = entity_id
        self.prompt_hint = prompt_hint
        self.language = language

    def run(self):
        try:
            if not hasattr(self.ai_controller, "node_text_suggestion"):
                self.finished.emit("", "La acción IA de texto no está disponible en esta versión.")
                return
            result = self.ai_controller.node_text_suggestion(
                self.entity_id, prompt_hint=self.prompt_hint, language=self.language
            )
            if isinstance(result, Error):
                self.finished.emit("", result.error)
                return
            value = result.value
            raw_text = getattr(value, "raw_text", "")
            if raw_text:
                self.finished.emit(raw_text, "")
            else:
                # Build a readable summary from candidates/previews
                parts: list[str] = []
                for c in getattr(value, "candidates", []) or []:
                    title = getattr(c, "title", "")
                    data = getattr(c, "proposed_data", {}) or {}
                    name = data.get("name", "")
                    desc = data.get("extended_description", data.get("brief_description", ""))
                    parts.append(name or title or "")
                    if desc:
                        parts.append(desc)
                for p in getattr(value, "previews", []) or []:
                    rt = p.get("raw_text", "")
                    if rt:
                        parts.append(rt)
                self.finished.emit("\n\n".join(parts) if parts else "Sin sugerencia disponible.", "")
        except Exception as exc:
            self.finished.emit("", str(exc))


_REFINE_SYSTEM_PROMPT_ES = (
    "Eres un asistente de escritura integrado en Dendro. El usuario ha seleccionado "
    "un fragmento de una sugerencia anterior y quiere que lo modifiques. "
    "Debes devolver ÚNICAMENTE el fragmento reescrito que reemplazará al seleccionado. "
    "No repitas el resto del texto. No añadas explicaciones. No uses formato JSON. "
    "Respeta el tono, género, realismo y estilo del texto original. "
    "Responde en español."
)


class _NodeRefineWorker(QThread):
    """Runs a refine-AI action in background; emits finished(text, error)."""

    finished = Signal(str, str)  # (text_or_empty, error_or_empty)

    def __init__(
        self,
        ai_controller,
        full_text: str,
        selected_text: str,
        user_instruction: str,
        language: str = "es",
    ):
        super().__init__()
        self.ai_controller = ai_controller
        self.full_text = full_text
        self.selected_text = selected_text
        self.user_instruction = user_instruction
        self.language = language

    def run(self):
        try:
            lang = "en" if str(self.language).lower().startswith("en") else "es"
            system = (
                "You are a writing assistant inside Dendro. The user has selected "
                "a fragment of a previous suggestion and wants you to rewrite it. "
                "Return ONLY the rewritten fragment that will replace the selected one. "
                "Do not repeat the rest of the text. No explanations. No JSON. "
                "Respect the tone, genre, realism and style of the original text. "
                "Respond in English."
                if lang == "en" else _REFINE_SYSTEM_PROMPT_ES
            )
            user_msg = (
                f"Texto completo de la sugerencia:\n---\n{self.full_text}\n---\n\n"
                f"Fragmento seleccionado a reescribir:\n---\n{self.selected_text}\n---\n\n"
                f"Instrucción del usuario: {self.user_instruction or 'Mejora este fragmento manteniendo coherencia con el resto.'}"
            )
            text, error = self.ai_controller.chat(system, user_msg)
            if error:
                self.finished.emit("", str(error))
            elif text and text.strip():
                self.finished.emit(text.strip(), "")
            else:
                self.finished.emit("", "La IA no devolvió texto para el refinado.")
        except Exception as exc:
            self.finished.emit("", str(exc))


# ---------------------------------------------------------------------------
# NodeDetailPanel
# ---------------------------------------------------------------------------

class NodeDetailPanel(QWidget):
    """Contextual entity editor shown inside the global RightDrawer."""

    def __init__(
        self,
        ctx: AppContext,
        entity_controller,
        entity_id: str,
        *,
        on_saved=None,
        ai_controller=None,
        relation_controller=None,
        milestone_controller=None,
        is_new: bool = False,
        on_focus_neighborhood=None,
        on_convert_to_branch=None,
        on_open_milestones=None,
        on_suggest_milestone=None,
        variant: str = "drawer",
        on_open_relation=None,
        on_create_relation=None,
        on_portrait=None,
        preview_patch: dict | None = None,
        on_preview_save=None,
    ):
        super().__init__()
        self.ctx = ctx
        # PLAY-16: modo PREVIEW — la ficha real con un patch propuesto aplicado
        # encima del canon. SIN autosave; guardar emite el DIFF por callback
        # (on_preview_save) y JAMÁS escribe canon. preview_patch is not None ⇔ preview.
        self.preview_patch = dict(preview_patch) if preview_patch else None
        self.on_preview_save = on_preview_save
        self._preview_base: dict = {}
        self._preview_extra: dict = {}
        # UI2-06: variant="foco" es la pestaña FICHA de la tarjeta del Foco;
        # las relaciones viven en su propia pestaña (FocoRelationsPanel) y el
        # retrato en la banda de la tarjeta (PortraitBand).
        self.variant = str(variant or "drawer")
        self.on_open_relation = on_open_relation
        self.on_create_relation = on_create_relation
        # UI2-06: la tarjeta del Foco recibe el retrato resuelto por este hook
        # (banda lateral persistente entre pestañas); el panel solo notifica.
        self.on_portrait = on_portrait
        self._is_ghost = False
        self.entity_controller = entity_controller
        self.entity_id = entity_id
        self.on_saved = on_saved
        self.ai_controller = ai_controller
        self.relation_controller = relation_controller
        self.milestone_controller = milestone_controller
        self.on_focus_neighborhood = on_focus_neighborhood
        self.on_convert_to_branch = on_convert_to_branch
        self.on_open_milestones = on_open_milestones
        self.on_suggest_milestone = on_suggest_milestone
        self.is_new = bool(is_new)
        self._entity = None
        self._current_color: str = ""
        self._ai_worker: _NodeAIWorker | None = None
        self._refreshing: bool = False  # guard against auto-save during refresh
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(800)  # ms
        self._autosave_timer.timeout.connect(self._autosave)
        self._build()
        if self.variant == "foco":
            # BETA2-FOCO: en Foco la IA vive en el drawer de riego (Regar /
            # Sugerir X); el bloque IA inline se oculta ENTERO (FOCO-20: antes
            # quedaban el título «IA» y el aviso de no-disponible).
            for ai_widget in (
                getattr(self, "ai_card", None),
                getattr(self, "ai_prompt_edit", None),
                getattr(self, "ai_generate_btn", None),
                getattr(self, "suggestion_frame", None),
            ):
                if ai_widget is not None:
                    ai_widget.hide()
            # UI2-06: la identidad vive en la tarjeta (título fijo + nombre
            # editable protagonista) — el título/resumen del header duplicaban.
            self.title.hide()
            self.summary.hide()
        self._connect_autosave_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        # UI2-06: la banda de retrato ya NO vive aquí — es de la tarjeta del
        # Foco (PortraitBand en foco_view), visible en todas las pestañas. El
        # atributo queda en None para las rutas y tests que lo consultan.
        self.portrait_band = None
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)  # UX23: ritmo del scaffold
        root.setSpacing(SPACE_MD)

        # -- Header (FOCO-20: banda única imagen + título + tipo + menú ⋯) --
        head = QHBoxLayout()
        head.setSpacing(SPACE_MD)
        # Imagen integrada en la cabecera: miniatura fija; el botón pequeño
        # debajo importa/cambia (persistencia mínima en custom_metadata).
        image_column = QVBoxLayout()
        image_column.setSpacing(4)
        self.image_preview = QLabel()
        self.image_preview.setFixedSize(72, 72)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setScaledContents(True)
        self.image_preview.setStyleSheet(
            f"border: 1px dashed {LINE_SOFT}; border-radius: 12px; "
            "background: rgba(255,255,255,0.45);"
        )
        image_column.addWidget(self.image_preview, 0, Qt.AlignmentFlag.AlignTop)
        self.image_btn = QPushButton("Imagen…")
        self.image_btn.setFixedHeight(22)
        self.image_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_btn.setStyleSheet(
            f"QPushButton {{ border: none; background: transparent; color: {_MUTED_COLOR}; "
            f"font-size: 11px; text-align: center; }} "
            f"QPushButton:hover {{ color: {_TITLE_COLOR}; }}"
        )
        self.image_btn.clicked.connect(self._pick_image)
        image_column.addWidget(self.image_btn)
        image_column.addStretch(1)
        head.addLayout(image_column)

        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        self.title = QLabel("Hoja")
        # PULIDO-04: rol H1 del sistema (19px) — antes 20px fuera de escala.
        self.title.setStyleSheet(
            f"font-size: {TYPE_H1_PX}px; font-weight: 700; color: {_TITLE_COLOR}; "
            f"font-family: {FONT_SERIF}; background: transparent;"
        )
        self.title.setWordWrap(True)
        title_column.addWidget(self.title)
        self.summary = QLabel("")
        self.summary.setObjectName("mutedLabel")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
        title_column.addWidget(self.summary)
        title_column.addStretch(1)
        head.addLayout(title_column, 1)

        badge_column = QVBoxLayout()
        badge_column.setSpacing(4)
        # PULIDO-04: FlowLayout — el badge de tipo y el menú ⋯ envuelven en
        # paneles estrechos en vez de imponer un ancho mínimo sumado.
        badge_row = FlowLayout(spacing=6)
        self.type_badge = Badge("Hoja", "info")
        badge_row.addWidget(self.type_badge)
        # FOCO-20: acciones secundarias («Convertir en rama») en un menú ⋯
        # discreto — «Más opciones» desapareció del editor.
        self.more_menu_btn = QToolButton()
        self.more_menu_btn.setText("⋯")
        self.more_menu_btn.setToolTip("Acciones de la entidad")
        self.more_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu_btn.setStyleSheet(
            "QToolButton { border: none; background: transparent; "
            f"color: {_MUTED_COLOR}; font-size: 16px; padding: 0 4px; }} "
            f"QToolButton:hover {{ color: {_TITLE_COLOR}; }} "
            "QToolButton::menu-indicator { image: none; }"
        )
        self._more_menu = QMenu(self.more_menu_btn)
        self.more_menu_btn.setMenu(self._more_menu)
        # UI2-20: «Convertir en rama» es redundante — la ramitud se deriva del
        # tipo (elige un tipo de rama en el combo). El menú ⋯ queda oculto.
        self.more_menu_btn.hide()
        badge_row.addWidget(self.more_menu_btn)
        badge_column.addLayout(badge_row)
        badge_column.addStretch(1)
        head.addLayout(badge_column)
        root.addLayout(head)

        # BETA2-FOCO-16: badge de fantasma bajo la cabecera (se crea más abajo
        # junto al resto de widgets de estado y se monta aquí vía placeholder).
        self._ghost_badge_slot = QVBoxLayout()
        root.addLayout(self._ghost_badge_slot)

        # -- Form card --
        form_card = QFrame()
        form_card.setObjectName("formCard")
        form_card.setStyleSheet(
            f"QFrame#formCard {{ background: {_BG_DRAWER}; border: none; }}"
        )
        _label_ss = f"color: {_LABEL_COLOR}; background: transparent; font-weight: 600;"

        # Widgets de metadatos (comunes a ambos variants; solo cambia el montaje).
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre")
        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        # UI2-20: TODAS las entidades ofrecen TODOS los tipos (hoja + rama). La
        # ramitud se deriva del tipo elegido: un tipo de rama la hace rama
        # (marcador interno 'contenedor'), uno de hoja la hace hoja. Sigue
        # editable por los tipos personalizados.
        for item in OFFERED_ENTITY_TYPES:
            self.type_combo.addItem(enum_human(item.value), item.value)
        # BETA-AUDIT-06: elegir un tipo de rama convierte la entidad en rama, y eso
        # no se deducía de ninguna parte de la interfaz.
        self.type_combo.setToolTip(
            f"Qué es esta entidad. {glossary('hoja')}\n\n"
            f"Si eliges un tipo de rama, pasa a contener otras: {glossary('rama')}"
        )
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        # Legacy ref kept for older code paths; never shown as UI. If this
        # empty label is made visible without a layout, Qt opens it as a
        # top-level blank popout.
        self.layer_label = QLabel("", self)
        self.layer_label.hide()
        self.layer_combo = QComboBox()
        self.layer_combo.addItem("— Sin anillo —", "")
        self.layer_combo.setToolTip(f"Anillo — {glossary('anillo')}")
        # UX28/BETA2-UX-03: el color del nodo lo decide el TIPO de entidad
        # (paleta de Dendro); no hay selector manual de color.

        # BETA2-FOCO-27: el lapso de vida (origen → fin) se define en la cronología
        # del PIE del editor (arrastre de bordes + hitos); en la descripción es solo
        # lectura. Ya no hay texto muerto de "Lapso de vida" en el formulario.

        # BETA1-J07/J08: naturaleza temporal SOLO para seres (personaje/criatura).
        # Un eterno NO recibe nacimiento mortal; la IA la propone y el usuario manda.
        self.nature_combo = QComboBox()
        _NATURE_LABELS = {"mortal": "Mortal", "inmortal": "Inmortal", "eterno": "Eterno"}
        for _nat in BEING_NATURES:
            self.nature_combo.addItem(_NATURE_LABELS.get(_nat.value, _nat.value), _nat.value)
        self.nature_combo.setToolTip(
            "Cómo se relaciona el ser con el tiempo. Un ser eterno/inmortal no "
            "nace en un año mortal. Solo aplica a personajes y criaturas."
        )
        self.nature_label = QLabel("Naturaleza temporal")
        self.nature_label.setStyleSheet(_label_ss)

        # BETA-MULTIAGENT2-FIX-12 (G2-29): «Nació» y «Murió» en la FICHA. Hasta
        # aquí el único editor de fecha era un arrastre sobre una ventana de 0 a
        # 10 años en la cronología del Foco: quien escribía de este mundo entregó
        # sus nueve fichas con `birth_year: null` en un proyecto con seis hitos
        # fechados entre 1901 y 1985. Escriben el mismo `birth_year`/`death_year`
        # que el panel ya enviaba por pass-through (el servicio los acepta desde
        # BETA1-G02); la datación RICA (precisión, era, fecha del mundo, notas)
        # se conserva intacta — contrato BETA2-SHIP-07.
        self.birth_year_edit = QLineEdit()
        self.birth_year_edit.setPlaceholderText("año")
        self.birth_year_edit.setMaximumWidth(84)
        self.birth_year_edit.setToolTip(
            "Año diegético en que nace o empieza a existir. Vacío = sin datar. "
            "Se admiten años negativos (antes del año 0 de tu calendario)."
        )
        self.death_year_edit = QLineEdit()
        self.death_year_edit.setPlaceholderText("año")
        self.death_year_edit.setMaximumWidth(84)
        self.death_year_edit.setToolTip(
            "Año diegético en que muere o deja de existir. Vacío = sigue vigente."
        )
        # El validador impide teclear algo que no sea un año: sin él, un texto
        # ilegible se leería como «sin datar» y BORRARÍA el año ya guardado.
        for _edit in (self.birth_year_edit, self.death_year_edit):
            _edit.setValidator(QIntValidator(-999999, 999999, _edit))
        self.birth_year_label = QLabel("Nació")
        self.birth_year_label.setStyleSheet(_label_ss)
        self.death_year_label = QLabel("Murió")
        self.death_year_label.setStyleSheet(_label_ss)

        # FOCO-20: «Relevancia narrativa» visible en el formulario principal
        # (calibra el riego y la invalidación de 2º grado; antes estaba
        # enterrada en «Más opciones»). Se crea aquí y se conecta al autosave.
        self.importance_combo = QComboBox()
        for val in ("critico", "alto", "medio", "bajo", "menor"):
            self.importance_combo.addItem(enum_human(val), val)
        # BETA-AUDIT-06: la definición sale del glosario del jardín, para que
        # «Relevancia» signifique lo mismo aquí y en el Cuaderno de cultivo.
        self.importance_combo.setToolTip(
            f"Relevancia — {glossary('relevancia')} Calibra la exigencia del riego "
            "y qué cambios vecinos la invalidan."
        )

        # BETA-AUDIT-02: la visibilidad volvió a ser editable. BETA2-UX-03 la había
        # dejado en pass-through («ya no editable»), y eso dejaba SIN USO el borde de
        # redacción de WS-B: la app prometía en el README no compartir lo privado con
        # la IA, pero nada podía marcarse como privado.
        #
        # Se ofrecen 5 de los 14 estados del enum: los que el motor trata de verdad
        # como reservados (ai_privacy._WITHHELD_VISIBILITY_TOKENS) más el visible por
        # defecto. Los 14 crudos eran ilegibles para quien abre la app por primera vez.
        self.visibility_combo = QComboBox()
        for value, label in _VISIBILITY_CHOICES:
            self.visibility_combo.addItem(label, value)
        self.visibility_combo.setToolTip(
            "Quién puede ver esta entidad.\n\n"
            "Privada, Secreta, Preparada y No exportable se consideran RESERVADAS: su "
            "contenido no se envía a la IA (viaja como «[reservado]») y no sale en una "
            "exportación pública."
        )

        if self.variant == "foco":
            # UI2-07: la Ficha se lee como texto — nombre protagonista (serif,
            # sin marco hasta hover/focus) + UNA fila discreta de chips con los
            # MISMOS combos (autosave intacto); sin labels de formulario (los
            # tooltips ya explican cada chip).
            self.name_edit.setStyleSheet(
                f"QLineEdit {{ background: transparent; border: 1px solid transparent; "
                f"border-radius: 8px; padding: 2px 4px; color: {_TITLE_COLOR}; "
                f"font-family: {FONT_SERIF}; font-size: {TYPE_H1_PX}px; font-weight: 700; }} "
                f"QLineEdit:hover {{ border-color: {LINE_SOFT}; }} "
                f"QLineEdit:focus {{ border-color: {GOLD}; background: {INPUT_BG}; }}"
            )
            chip_ss = meta_chip_style()
            for combo in (
                self.type_combo,
                self.layer_combo,
                self.nature_combo,
                self.importance_combo,
            ):
                combo.setStyleSheet(chip_ss)
                combo.setFixedHeight(22)
            self.nature_label.hide()  # el chip se explica solo (icono + tooltip)
            chips_layout = QVBoxLayout(form_card)
            chips_layout.setContentsMargins(0, 4, 0, 4)
            chips_layout.setSpacing(6)
            chips_layout.addWidget(self.name_edit)
            # UI2-12: cada chip lleva su icono SVG identificador + tooltip.
            meta_row = FlowLayout(spacing=8)
            # BETA-AUDIT-06: los chips reusan el tooltip que ya define el combo
            # (tomado del glosario del jardín) en vez de repetir una frase propia
            # que decía dónde vive el dato pero no qué significa.
            meta_row.addWidget(
                _meta_chip("field_type", self.type_combo, self.type_combo.toolTip())
            )
            meta_row.addWidget(
                _meta_chip("rings", self.layer_combo, self.layer_combo.toolTip())
            )
            self._nature_chip_wrapper = _meta_chip(
                "field_nature",
                self.nature_combo,
                self.nature_combo.toolTip(),
            )
            meta_row.addWidget(self._nature_chip_wrapper)
            meta_row.addWidget(
                _meta_chip(
                    "metric_relevancia",
                    self.importance_combo,
                    self.importance_combo.toolTip(),
                )
            )
            meta_row.addWidget(
                _meta_chip(
                    "lock",
                    self.visibility_combo,
                    self.visibility_combo.toolTip(),
                )
            )
            chips_layout.addLayout(meta_row)
            # FIX-12: las dos casillas de fecha, en su propia fila bajo los chips
            # (una caja de texto no es un chip: se escribe, no se elige).
            chips_layout.addLayout(self._build_dating_row())
        else:
            form_layout = QFormLayout(form_card)
            form_layout.setContentsMargins(0, 4, 0, 4)
            form_layout.setSpacing(8)
            form_layout.labelAlignment = 0x0002  # Qt.AlignmentFlag.AlignRight
            # BETA1-F05 layout exacto: NOMBRE + TIPO + ANILLO en UNA fila fluida.
            first_row = QHBoxLayout()
            first_row.setSpacing(8)
            first_row.addWidget(self.name_edit, 3)
            first_row.addWidget(self.type_combo, 2)
            first_row.addWidget(self.layer_combo, 2)
            form_layout.addRow(first_row)
            form_layout.addRow(self.nature_label, self.nature_combo)
            importance_label = QLabel("Relevancia")
            importance_label.setStyleSheet(_label_ss)
            form_layout.addRow(importance_label, self.importance_combo)
            # FIX-12: «Nació» / «Murió» también en la variante de formulario.
            form_layout.addRow(self._build_dating_row())

        # Descripción breve: tras la imagen (montada fuera del form) — el
        # widget se crea aquí, se monta más abajo en el orden F05.
        self.brief_edit = QTextEdit()
        self.brief_edit.setMaximumHeight(72)
        self.brief_edit.setPlaceholderText("Descripción breve…")
        # BETA1-F05: viñetas protagonistas (breve y cuerpo).
        # FOCO-20 (Editorial sereno): serif editorial y cuerpo ≥14px — aquí se
        # pasa mucho tiempo escribiendo; la superficie debe ser inmersiva.
        _card_ss = (
            f"QTextEdit {{ background: {INPUT_BG}; border: 1px solid {LINE}; "
            f"border-radius: 12px; padding: 12px; font-size: 14px; color: {INK}; "
            f"font-family: {FONT_SERIF}; }} "
            f"QTextEdit:hover {{ border-color: {LINE_STRONG}; }} "
            f"QTextEdit:focus {{ border: 2px solid {GOLD}; background: #FFFFFF; padding: 11px; }}"
        )
        self.brief_edit.setStyleSheet(_card_ss)
        self._editorial_card_ss = _card_ss

        # BETA2-FOCO-16 (canon total): el estado canon ya no se edita — todo es
        # canon salvo fantasma; el combo desapareció del producto.
        # BETA2-FOCO: badge informativo de fantasma (no editable).
        self.ghost_state_label = QLabel("Fantasma — borrador interno, no canon")
        self.ghost_state_label.setStyleSheet(
            f"color: {_MUTED_COLOR}; font-style: italic; background: transparent;"
        )
        self.ghost_state_label.setVisible(False)
        self._ghost_badge_slot.addWidget(self.ghost_state_label)

        root.addWidget(form_card)

        # FOCO-20: la imagen vive integrada en la cabecera; la breve va
        # directamente tras el formulario.
        root.addWidget(self.brief_edit)

        # BETA1-F04: el CUERPO es el centro del panel — sin tope de altura,
        # con prioridad de espacio (~70-80% del panel).
        body_label = QLabel("CUERPO")
        body_label.setStyleSheet(
            f"color: {_MUTED_COLOR}; background: transparent; font-size: 11px; "
            "font-weight: 700; letter-spacing: 1px;"
        )
        root.addWidget(body_label)
        self.extended_edit = QTextEdit()
        self.extended_edit.setMinimumHeight(300)
        self.extended_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.extended_edit.setStyleSheet(self._editorial_card_ss)
        root.addWidget(self.extended_edit, 1)

        # BETA-MULTIAGENT2-FIX-11 (fase B): sección «Rigor» — certeza y datación
        # rica (precisión, fecha del mundo, periodo, nota, fuentes que se
        # contradicen). Nace PLEGADA: la Ficha de quien no la necesita no crece
        # ni un campo. El año entero sigue siendo el espejo autoritativo.
        self.rigor = RigorSection(expandida=bool(getattr(self.ctx, "advanced_mode", False)))
        self.rigor.changed.connect(self._schedule_autosave)
        # FIX-11 (fase B3): FUENTES de la entidad — crear, ENLAZAR y ver. El
        # servicio lo soportaba entero y no había ni una llamada en `hosts/`; el
        # único formulario que existía colgaba de una tarjeta muerta
        # (`NarrativeWorkbench`, jamás instanciada). Ahora cuelga de la Ficha.
        # OJO: no existe `entity.source_ids` — el enlace vive EN LA FUENTE y la
        # consulta inversa es `get_sources_for_entity`.
        sources_box = QWidget(self)
        sources_layout = QVBoxLayout(sources_box)
        sources_layout.setContentsMargins(0, 0, 0, 0)
        sources_layout.setSpacing(4)
        self.sources_label = QLabel("Sin fuentes enlazadas")
        self.sources_label.setWordWrap(True)
        self.sources_label.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
        sources_layout.addWidget(self.sources_label)
        self.add_source_btn = QPushButton("Añadir fuente…")
        self.add_source_btn.setToolTip(
            "Anota de dónde sale esto: referencia (signatura, página, enlace) y la "
            "cita literal si la tienes. Queda enlazada a este elemento."
        )
        self.add_source_btn.clicked.connect(self._open_source_dialog)
        sources_layout.addWidget(self.add_source_btn)
        self.rigor.add_row("Fuentes", sources_box)
        root.addWidget(self.rigor)

        # BETA2-MEM-03: @menciones estructuradas en la prosa (breve + cuerpo).
        self._mention_supports = {}
        try:
            provider = self._mention_targets_provider()
            self._mention_supports["brief_description"] = attach_mention_support(
                self.brief_edit, provider
            )
            self._mention_supports["extended_description"] = attach_mention_support(
                self.extended_edit, provider
            )
        except Exception:  # noqa: BLE001 — las @menciones nunca deben romper el editor
            self._mention_supports = {}

        # BETA2-UX-03: notas privadas/exportables, visibilidad y el resumen de
        # «Contexto» (relations_label/campaigns_label) eran widgets muertos (sin
        # montar). Se eliminaron; notas y visibilidad se PRESERVAN por
        # pass-through en el guardado. La lista viva de relaciones clicables la
        # construye _build_relations_section/_rebuild_relation_rows.

        # FOCO-20: los hitos ya NO viven en el formulario — se muestran y se
        # crean en la cronología local bajo el editor (FocoLifelineBand); el
        # atributo queda en None para las rutas que lo consultan.
        self.related_milestones_panel = None
        # UI2-20: ya no hay «Convertir en rama» — la ramitud se deriva del tipo
        # (elige un tipo de rama en el combo); el menú ⋯ queda oculto.

        # -- AI suggestion section --
        ai_card = QFrame()
        self.ai_card = ai_card  # FOCO-20: en foco se oculta el bloque ENTERO
        ai_card.setObjectName("aiCard")
        ai_card.setStyleSheet(
            f"QFrame#aiCard {{ background: transparent; border: none; }}"
        )
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setContentsMargins(0, 6, 0, 0)
        ai_layout.setSpacing(6)

        ai_title = QLabel("IA")
        ai_title.setStyleSheet(
            f"color: {_LABEL_COLOR}; font-weight: 700; font-size: 13px; background: transparent;"
        )
        ai_layout.addWidget(ai_title)

        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(6)
        self.ai_prompt_edit = QLineEdit()
        self.ai_prompt_edit.setPlaceholderText("Ej: Hazlo más oscuro, añade detalle histórico…")
        prompt_row.addWidget(self.ai_prompt_edit, 1)
        self.ai_generate_btn = QPushButton("Generar sugerencia")
        self.ai_generate_btn.setEnabled(self.ai_controller is not None)
        self.ai_generate_btn.setText("Consultar")
        self.ai_generate_btn.clicked.connect(self._start_ai_suggestion)
        prompt_row.addWidget(self.ai_generate_btn)
        ai_layout.addLayout(prompt_row)

        # BETA2-UX-03: el botón «Analizar coherencia» estaba oculto (las
        # acciones causales se invocan desde la command bar/menú contextual).
        # Eliminado.

        if self.ai_controller is None:
            no_ai_label = QLabel("IA contextual no disponible en esta sesión.")
            no_ai_label.setObjectName("mutedLabel")
            no_ai_label.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
            ai_layout.addWidget(no_ai_label)

        # Suggestion display area (hidden by default)
        self.suggestion_frame = QFrame()
        self.suggestion_frame.setObjectName("suggestionFrame")
        self.suggestion_frame.setStyleSheet(
            f"QFrame#suggestionFrame {{ "
            f"background: {_SUGGESTION_BG}; "
            f"border: 1px dashed #B8B5A2; border-radius: 10px; "
            f"padding: 6px; }}"
        )
        self.suggestion_frame.setVisible(False)

        sug_layout = QVBoxLayout(self.suggestion_frame)
        sug_layout.setContentsMargins(8, 6, 8, 6)
        sug_layout.setSpacing(4)

        sug_header = QHBoxLayout()
        sug_label = QLabel("Sugerencia IA")
        sug_label.setStyleSheet(
            f"color: {_LABEL_COLOR}; font-weight: 600; font-size: 12px; "
            f"background: transparent; font-style: italic;"
        )
        sug_header.addWidget(sug_label, 1)
        sug_layout.addLayout(sug_header)

        self.suggestion_text = QTextEdit()
        self.suggestion_text.setReadOnly(False)
        self.suggestion_text.setMaximumHeight(140)
        self.suggestion_text.setStyleSheet(
            f"background: transparent; border: none; color: #4F4D38; font-style: italic;"
        )
        sug_layout.addWidget(self.suggestion_text)

        sug_actions = QHBoxLayout()
        sug_actions.setSpacing(6)
        self.refine_btn = QPushButton("Refinar selección")
        self.refine_btn.setFixedHeight(28)
        self.refine_btn.setToolTip("Selecciona parte del texto y pulsa para re-generar solo esa parte")
        self.refine_btn.clicked.connect(self._refine_suggestion)
        self.accept_btn = QPushButton("Aceptar")
        self.accept_btn.setObjectName("primaryButton")
        self.accept_btn.setFixedHeight(28)
        self.accept_btn.clicked.connect(self._accept_suggestion)
        self.discard_btn = QPushButton("Descartar")
        self.discard_btn.setFixedHeight(28)
        self.discard_btn.clicked.connect(self._discard_suggestion)
        sug_actions.addStretch()
        sug_actions.addWidget(self.refine_btn)
        sug_actions.addWidget(self.accept_btn)
        sug_actions.addWidget(self.discard_btn)
        sug_layout.addLayout(sug_actions)

        ai_layout.addWidget(self.suggestion_frame)
        root.addWidget(ai_card)

        # BETA2-UX-03: caja «Datos técnicos» (sin montar, dato-no-UI) eliminada.

        # FOCO-20: «Más opciones» desapareció del editor — la Relevancia vive
        # en el formulario principal, los hitos en la cronología local y
        # «Convertir en rama» en el menú ⋯ de la cabecera.
        # UI2-06: la lista de RELACIONES tampoco vive ya aquí — es la pestaña
        # «Relaciones» de la tarjeta del Foco (FocoRelationsPanel).

        # -- Actions --
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.save)
        actions.addWidget(self.cancel_btn)
        actions.addStretch()
        actions.addWidget(self.save_btn)
        root.addLayout(actions)
        root.addStretch()

        # BETA1-UX08: fondo del panel SCOPED al objectName. Un stylesheet sin
        # selector sangra a los hijos e interfiere con el estilo central de los
        # botones (el primario disabled perdía contraste/etiqueta).
        self.setObjectName("nodeDetailPanel")
        self.setStyleSheet(f"QWidget#nodeDetailPanel {{ background: {_BG_DRAWER}; }}")

        self.set_advanced_mode(self.ctx.advanced_mode)

    # ------------------------------------------------------------------
    # Colour helpers
    # ------------------------------------------------------------------

    # ── BETA2-IMG: retrato de entidad (subir / buscar / encuadrar) ───────

    def _pick_image(self):
        """Menú de retrato: subir archivo, buscar en internet, reencuadrar o
        quitar. El flujo (editor de encuadre incluido) vive en portrait_flow."""
        portrait_flow.open_image_menu(self)

    def _show_image(self, path: str, crop=None):
        # FOCO-20: miniatura integrada en la cabecera — siempre visible; sin
        # imagen queda el marco punteado como placeholder. BETA2-IMG: la ruta
        # guardada es relativa al asset store (absoluta = legacy F04) y la
        # miniatura muestra el ENCUADRE elegido; en foco alimenta la banda de
        # la TARJETA vía on_portrait (UI2-06).
        resolved = portrait_flow.resolve_portrait_path(self.ctx, path)
        if callable(self.on_portrait):
            self.on_portrait(resolved, crop)
        if resolved is None:
            self.image_preview.clear()
            self.image_btn.setText("Imagen…")
            return
        pixmap = portrait_cache.portrait_pixmap(resolved, crop, 128)
        if pixmap is None:
            self.image_preview.clear()
            return
        self.image_preview.setPixmap(pixmap)
        self.image_btn.setText("Cambiar…")

    def _update_color_swatch(self, hex_color: str):
        # BETA2-UX-03: el color deriva del tipo; solo se conserva para el save.
        self._current_color = hex_color

    def _on_type_changed(self, _index: int = -1):
        """When type changes, update default color if no custom color was set."""
        type_val = self.type_combo.currentData() or self.type_combo.currentText().strip().lower()
        if not self._entity:
            return
        meta = getattr(self._entity, "custom_metadata", {}) or {}
        has_custom = bool(meta.get("_node_color"))
        if not has_custom:
            # UI2-20: una rama usa el color del contenedor (se guarda como tal).
            color_kind = "contenedor" if is_branch_type(type_val) else type_val
            self._update_color_swatch(_default_color_for_type(color_kind))
        self._update_nature_visibility()
        self._schedule_autosave()

    # ------------------------------------------------------------------
    # BETA-MULTIAGENT2-FIX-12 (G2-29): fechas de la entidad en la Ficha
    # ------------------------------------------------------------------

    def _build_dating_row(self) -> QHBoxLayout:
        """Fila «Nació [año]  ·  Murió [año]», idéntica en las dos variantes."""
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.birth_year_label)
        row.addWidget(self.birth_year_edit)
        row.addSpacing(10)
        row.addWidget(self.death_year_label)
        row.addWidget(self.death_year_edit)
        row.addStretch(1)
        return row

    def _parse_year_text(self, text: str, previo: int | None = None) -> int | None:
        """Año entero escrito por el usuario; vacío → ``None`` (sin datar).

        Un texto ilegible NO se interpreta como «sin datar»: se conserva el año
        que ya había. Borrar un año tiene que ser una decisión, no un descuido de
        teclado (el validador ya impide teclear letras; esto es el cinturón).
        """
        raw = str(text or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return previo

    def _sync_dating_row(self, entity) -> None:
        """Vuelca el espejo entero de la entidad en las dos casillas."""
        for edit, attr in (
            (self.birth_year_edit, "birth_year"),
            (self.death_year_edit, "death_year"),
        ):
            value = getattr(entity, attr, None)
            edit.blockSignals(True)
            edit.setText("" if value is None else str(int(value)))
            edit.blockSignals(False)

    def _update_nature_visibility(self):
        """BETA1-J08: el combo de naturaleza solo aparece para seres."""
        type_val = self.type_combo.currentData() or self.type_combo.currentText().strip().lower()
        try:
            is_being = has_temporal_nature(EntityType(type_val))
        except ValueError:
            is_being = False
        self.nature_combo.setVisible(is_being)
        # UI2-07/12: en la Ficha del Foco no hay labels de formulario — se
        # oculta el WRAPPER entero del chip (icono incluido; un icono huérfano
        # sin combo confunde) y el label permanece oculto siempre.
        if self.variant == "foco":
            wrapper = getattr(self, "_nature_chip_wrapper", None)
            if wrapper is not None:
                wrapper.setVisible(is_being)
        else:
            self.nature_label.setVisible(is_being)

    # ------------------------------------------------------------------
    # Auto-save (debounced)
    # ------------------------------------------------------------------

    def _connect_autosave_signals(self):
        """Connect all editable field signals to the debounced auto-save timer."""
        if self.preview_patch is not None:
            return  # PLAY-16: el preview no autoguarda — cero riesgo de escribir canon
        self.name_edit.textEdited.connect(self._schedule_autosave)
        self.brief_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.extended_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.importance_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.visibility_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.type_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.layer_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.nature_combo.currentIndexChanged.connect(self._schedule_autosave)
        # BETA-MULTIAGENT2-FIX-12 (G2-29): los años vuelven a ser editables aquí
        # (arrastrar el borde en una escala de 0 a 10 no sirve para escribir
        # 1901). `editingFinished` y no `textEdited`: no se autoguarda «1», «19»,
        # «190» mientras se teclea el año.
        self.birth_year_edit.editingFinished.connect(self._schedule_autosave)
        self.death_year_edit.editingFinished.connect(self._schedule_autosave)

    def _schedule_autosave(self):
        """Restart the debounce timer (800 ms of inactivity triggers save)."""
        if self._refreshing:
            return
        self._autosave_timer.start()

    def _schedule_autosave_if_active(self):
        """Wrapper for QTextEdit.textChanged — only schedules if not refreshing."""
        self._schedule_autosave()

    def _autosave(self):
        """Save entity silently (no refresh, no UI reset)."""
        if self._refreshing or self._entity is None:
            return
        self._do_save(refresh_after=False)

    # ------------------------------------------------------------------
    # AI suggestion (non-blocking)
    # ------------------------------------------------------------------

    def _build_ai_instruction(self, user_instruction: str) -> str:
        """Build the text-only AI instruction from the current, unsaved form state."""
        entity_name = self.name_edit.text().strip() or "Sin nombre"
        type_value = self.type_combo.currentData() or self.type_combo.currentText().strip() or "entidad"
        brief = self.brief_edit.toPlainText().strip()
        body = self.extended_edit.toPlainText().strip()
        # BETA2-UX-03: las notas ya no se editan aquí; se leen de la entidad.
        _ent = getattr(self, "_entity", None)
        private_notes = (getattr(_ent, "private_notes", "") or "") if _ent else ""
        exportable_notes = (getattr(_ent, "exportable_notes", "") or "") if _ent else ""
        instruction = (user_instruction or "").strip()
        layer_name = self.layer_combo.currentText() if self._worldbuilding_active() else "—"
        return (
            f"Nombre actual: {entity_name}\n"
            f"Tipo actual: {type_value}\n"
            f"Anillo causal actual: {layer_name}\n"
            f"Descripción breve actual del formulario:\n{brief or '—'}\n\n"
            f"Cuerpo actual del formulario:\n{body or '—'}\n\n"
            f"Notas actuales:\n{private_notes or exportable_notes or '—'}\n\n"
            f"Instrucción opcional del usuario: {instruction or '—'}"
        )

    def _start_ai_suggestion(self):
        _apptrace(f"UI node generate_ai_suggestion entity_id={self.entity_id!r}")
        if self.ai_controller is None:
            self._show_ai_error("IA contextual no disponible en esta sesión.")
            return
        if self._ai_worker is not None and self._ai_worker.isRunning():
            return
        try:
            prompt_hint = self._build_ai_instruction(self.ai_prompt_edit.text().strip())
        except Exception as exc:
            self._show_ai_error(f"No se pudo preparar la petición IA: {exc}")
            return
        self.ai_generate_btn.setEnabled(False)
        self.ai_generate_btn.setText("Generando…")
        self.suggestion_text.setPlainText("Generando sugerencia…")
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(False)

        self._ai_worker = _NodeAIWorker(
            self.ai_controller,
            self.entity_id,
            prompt_hint,
            getattr(self.ctx, "language", "es"),
        )
        self._ai_worker.finished.connect(self._on_ai_finished)
        track_worker(self._ai_worker)  # sobrevive al panel; se para al cerrar la app
        self._ai_worker.start()

    def _show_ai_error(self, message: str):
        has_ai = self.ai_controller is not None
        self.ai_generate_btn.setEnabled(has_ai)
        self.ai_generate_btn.setText("Generar sugerencia")
        self.refine_btn.setEnabled(True)
        self.suggestion_text.setPlainText(f"Error IA: {message}")
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(False)
        if self.ctx is not None:
            self.ctx.log("warning", f"IA: {message}")

    @_qt_safe_slot
    def _on_ai_finished(self, text: str, error: str):
        has_ai = self.ai_controller is not None
        self.ai_generate_btn.setEnabled(has_ai)
        self.ai_generate_btn.setText("Generar sugerencia")
        if error:
            self._show_ai_error(error)
            return
        self.accept_btn.setEnabled(True)
        self.refine_btn.setEnabled(True)
        if not text:
            self._show_ai_error("La IA no devolvió texto.")
            return
        self.suggestion_text.setPlainText(text)
        self.suggestion_frame.setVisible(True)

    def _refine_suggestion(self):
        """Take selected text from suggestion, send to AI for rework, replace in-place."""
        if self.ai_controller is None:
            self._show_ai_error("IA contextual no disponible en esta sesión.")
            return
        if self._ai_worker is not None and self._ai_worker.isRunning():
            return

        full_text = self.suggestion_text.toPlainText()
        cursor = self.suggestion_text.textCursor()
        selected = cursor.selectedText().strip()

        if not selected:
            self._show_ai_error("Selecciona primero el texto que quieres refinar.")
            return

        user_instruction = self.ai_prompt_edit.text().strip()
        self.refine_btn.setEnabled(False)
        self.accept_btn.setEnabled(False)
        self.ai_generate_btn.setEnabled(False)

        self._ai_worker = _NodeRefineWorker(
            self.ai_controller,
            full_text=full_text,
            selected_text=selected,
            user_instruction=user_instruction,
            language=getattr(self.ctx, "language", "es"),
        )
        # Store selection info for replacement
        self._refine_selection_start = cursor.selectionStart()
        self._refine_selection_end = cursor.selectionEnd()
        self._refine_full_text = full_text
        self._ai_worker.finished.connect(self._on_refine_finished)
        track_worker(self._ai_worker)  # sobrevive al panel; se para al cerrar la app
        self._ai_worker.start()

    @_qt_safe_slot
    def _on_refine_finished(self, text: str, error: str):
        self.ai_generate_btn.setEnabled(self.ai_controller is not None)
        self.refine_btn.setEnabled(True)
        self.accept_btn.setEnabled(True)
        if error:
            self._show_ai_error(f"Refinado: {error}")
            return
        if not text:
            self._show_ai_error("La IA no devolvió texto para el refinado.")
            return
        # Replace the selected portion with the new text
        full = getattr(self, "_refine_full_text", "")
        start = getattr(self, "_refine_selection_start", 0)
        end = getattr(self, "_refine_selection_end", 0)
        if full and start != end:
            new_full = full[:start] + text + full[end:]
            self.suggestion_text.setPlainText(new_full)
        else:
            # Fallback: just set the whole text
            self.suggestion_text.setPlainText(text)
        self.suggestion_frame.setVisible(True)

    def _accept_suggestion(self):
        _apptrace(f"UI node accept_suggestion entity_id={self.entity_id!r}")
        text = self.suggestion_text.toPlainText().strip()
        if text:
            # If the extended body is empty, put it there; otherwise append
            current = self.extended_edit.toPlainText().strip()
            if current:
                self.extended_edit.setPlainText(current + "\n\n" + text)
            else:
                self.extended_edit.setPlainText(text)
        self._discard_suggestion()

    def _discard_suggestion(self):
        _apptrace(f"UI node discard_suggestion entity_id={self.entity_id!r}")
        self.suggestion_frame.setVisible(False)
        self.suggestion_text.clear()

    # ------------------------------------------------------------------
    # Coherence analysis
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # B39: Convert to branch (Hoja → Rama)
    # ------------------------------------------------------------------

    def _convert_to_branch(self):
        """Convert this leaf entity into a branch (container/rama)."""
        _apptrace(f"UI node convert_to_branch entity_id={self.entity_id!r}")
        if self.ctx is None:
            return
        # Use EntityController.es (EntityService) directly
        entity_service = getattr(self.entity_controller, "es", None) if self.entity_controller else None
        if entity_service is None:
            self.ctx.notify("No se pudo convertir en rama: servicio no disponible", "error")
            return
        from packages.domain.result import Error
        result = entity_service.convert_to_branch(self.entity_id)
        if isinstance(result, Error):
            self.ctx.notify(f"Error convirtiendo en rama: {result.error}", "error")
            return
        self.ctx.log("info", "Hoja convertida en rama")
        # Refresh graph
        if self.on_saved is not None:
            self.on_saved()
        # Close current drawer and open tree panel via workspace callback
        if self.ctx.drawer is not None:
            self.ctx.drawer.close()
        if self.on_convert_to_branch is not None:
            self.on_convert_to_branch(self.entity_id)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def _cancel(self):
        """Cancel edits. New visual drafts are removed; saved entities are reloaded."""
        _apptrace(f"UI node cancel_edit entity_id={self.entity_id!r} is_new={self.is_new}")
        self._autosave_timer.stop()
        self._discard_suggestion()
        if self.is_new:
            result = self.entity_controller.delete(self.entity_id)
            if isinstance(result, Error):
                self.ctx.log("warning", result.error)
            elif self.on_saved is not None:
                self.on_saved()
            parent = self.parent()
            while parent is not None:
                if type(parent).__name__ == "RightDrawer":
                    parent.close()
                    return
                parent = parent.parent()
            return
        self.refresh()
        parent = self.parent()
        while parent is not None:
            # Close the RightDrawer if we can find it
            if type(parent).__name__ == "RightDrawer":
                parent.close()
                return
            parent = parent.parent()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    # BETA1-UX2C: lapso de vida (solo lectura) -------------------------

    def _sync_nature_combo(self, entity) -> None:
        """BETA1-J07: sincroniza el combo de naturaleza temporal con la entidad.

        BETA2-FOCO-27: el lapso de vida se define en la cronología del pie del
        editor (arrastre + hitos); ya no se pinta como texto en el formulario."""
        span = getattr(entity, "life_span", None)
        nature_value = getattr(getattr(span, "nature", None), "value", "mortal")
        self.nature_combo.blockSignals(True)
        idx = self.nature_combo.findData(nature_value)
        self.nature_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.nature_combo.blockSignals(False)
        self._update_nature_visibility()

    def _sync_visibility_combo(self, entity) -> None:
        """BETA-AUDIT-02: refleja la visibilidad de la entidad en el chip.

        El combo ofrece 5 de los 14 estados del enum por legibilidad. Si el proyecto
        trae uno de los otros 9 (creado por una versión anterior o por la CLI
        retirada), se añade al vuelo en vez de perderlo: guardar no debe degradar en
        silencio un estado que el usuario no eligió aquí.
        """
        actual = _enum_value(getattr(entity, "visibility_state", None), "visible_usuario")
        self.visibility_combo.blockSignals(True)
        try:
            idx = self.visibility_combo.findData(actual)
            if idx < 0:
                self.visibility_combo.addItem(enum_human(actual), actual)
                idx = self.visibility_combo.count() - 1
            self.visibility_combo.setCurrentIndex(idx)
        finally:
            self.visibility_combo.blockSignals(False)

    def _worldbuilding_active(self) -> bool:
        project = self._project()
        return bool(getattr(project, "worldbuilding_active", False)) if project is not None else False

    def _refresh_layer_combo(self, entity=None):
        current = ""
        if entity is not None:
            current = str((getattr(entity, "layer_ids", []) or [""])[0] or "")
        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        self.layer_combo.addItem("— Sin anillo —", "")
        project = self._project()
        layers = list(getattr(project, "world_layers", []) or []) if project is not None else []
        for layer in sort_layers_by_causal_rank(layers):
            if not getattr(layer, "is_visible", True):
                continue
            rank = get_causal_rank(layer)
            prefix = f"{rank}. " if rank is not None else ""
            self.layer_combo.addItem(prefix + str(getattr(layer, "name", "Capa")), str(getattr(layer, "id", "")))
        idx = self.layer_combo.findData(current)
        self.layer_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.layer_combo.blockSignals(False)
        self.layer_label.hide()
        self.layer_combo.setVisible(self._worldbuilding_active())

    def _entity_by_id(self, entity_id: str):
        project = self._project()
        if project is None:
            return None
        for entity in getattr(project, "entities", []) or []:
            if getattr(entity, "id", None) == entity_id:
                return entity
        return None

    def _set_combo_value(self, combo: QComboBox, value: str):
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findText(enum_human(value))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            # Value not found in combo — set as custom text
            combo.setEditText(str(value))

    # ------------------------------------------------------------------
    # Refresh / populate
    # ------------------------------------------------------------------

    def refresh(self):
        _apptrace(f"UI node set_entity entity_id={self.entity_id!r}")
        self._refreshing = True
        try:
            result = self.entity_controller.get(self.entity_id)
            if isinstance(result, Error):
                self.title.setText("Elemento no encontrado")
                self.summary.setText(result.error)
                self.save_btn.setEnabled(False)
                return
            entity = result.value
            # BETA1-F04/BETA2-IMG: retrato asociado (si lo hay), con encuadre
            metadata = dict(getattr(entity, "custom_metadata", {}) or {})
            self._show_image(str(metadata.get("_image_path", "")), metadata.get("_image_crop"))
            self._entity = entity
            kind = _enum_value(getattr(entity, "entity_type", None), "entidad")
            # UI2-20: una rama se guarda con el marcador interno 'contenedor'; el
            # combo y el resumen muestran su TIPO DE RAMA real (tree_type) para
            # poder re-tiparla. Una hoja muestra su propio tipo.
            display_kind = kind
            if kind.lower() == "contenedor":
                tree_kind = str(metadata.get("tree_type", "") or "").lower()
                if is_branch_type(tree_kind) and tree_kind != "contenedor":
                    display_kind = tree_kind
            self.title.setText(getattr(entity, "name", "Sin nombre") or "Sin nombre")
            # UI2-20: badge Rama/Hoja derivado del tipo (is_branch_type).
            self.type_badge.setText("Rama" if is_branch_type(kind) else "Hoja")
            canon_val = _enum_value(getattr(entity, "canon_state", None), "")
            # FOCO-20 + canon total: la línea resumen muestra el TIPO; el único
            # estado que existe de cara al usuario es «fantasma» (badge propio).
            self.summary.setText(enum_human(display_kind))
            self._refresh_layer_combo(entity)

            self.name_edit.setText(getattr(entity, "name", ""))
            self._set_combo_value(self.type_combo, display_kind)

            # BETA2-FOCO-27: se sincroniza la naturaleza temporal; el lapso RICO
            # sigue definiéndose en la cronología del pie del editor.
            self._sync_nature_combo(entity)
            # FIX-12 (G2-29): …pero el AÑO entero ya se escribe aquí.
            self._sync_dating_row(entity)
            self.brief_edit.setPlainText(getattr(entity, "brief_description", "") or "")
            self.extended_edit.setPlainText(getattr(entity, "extended_description", "") or "")

            # BETA2-FOCO-16 (canon total): el canon no se edita en el panel;
            # solo se refleja el badge de fantasma. El autosave jamás debe
            # des-fantasmar en silencio.
            self._is_ghost = canon_val.lower() == "fantasma"
            self.ghost_state_label.setVisible(self._is_ghost)
            self._set_combo_value(
                self.importance_combo,
                _enum_value(getattr(entity, "narrative_importance", None), "medio"),
            )
            self._sync_visibility_combo(entity)  # BETA-AUDIT-02
            # FIX-11 (fase B): certeza + datación rica del INICIO del lapso.
            span = getattr(entity, "life_span", None)
            self.rigor.load(
                certeza=getattr(entity, "certainty_level", None),
                temporalidad=getattr(span, "start", None) if span is not None else None,
            )
            self._refresh_sources()


            # Color
            meta = getattr(entity, "custom_metadata", {}) or {}
            stored_color = meta.get("_node_color")
            if stored_color:
                self._update_color_swatch(stored_color)
            else:
                self._update_color_swatch(_default_color_for_type(kind))

            if self.related_milestones_panel is not None:
                self.related_milestones_panel.refresh()
            self.set_advanced_mode(self.ctx.advanced_mode)

            # UI2-20: el menú ⋯ «Convertir en rama» desapareció — la ramitud se
            # deriva del tipo (elige un tipo de rama en el combo).
            # PLAY-16: en preview, el patch propuesto se aplica ENCIMA del canon
            # recién cargado y las acciones laterales se retiran.
            if self.preview_patch is not None:
                self._apply_preview_patch()
        finally:
            self._refreshing = False

    # ------------------------------------------------------------------
    # PLAY-16: modo preview (propuesta de la IA sobre la ficha real)
    # ------------------------------------------------------------------

    _PREVIEW_GOLD = "#BBAA66"  # GOLD_SOFT: resaltado de campos propuestos

    def _apply_preview_patch(self) -> None:
        patch = dict(self.preview_patch or {})
        # Snapshot del canon TAL COMO lo normaliza el guardado (diff coherente).
        self._preview_base = {
            "name": self.name_edit.text().strip(),
            "entity_type": self.type_combo.currentData()
            or self.type_combo.currentText().strip().lower(),
            "brief_description": self.brief_edit.toPlainText().strip(),
            "extended_description": self.extended_edit.toPlainText().strip(),
            "narrative_importance": self.importance_combo.currentData() or "medio",
            "temporal_nature": self.nature_combo.currentData(),
        }
        renderers = {
            "name": lambda v: self.name_edit.setText(str(v)),
            "entity_type": lambda v: self._set_combo_value(self.type_combo, str(v)),
            "brief_description": lambda v: self.brief_edit.setPlainText(str(v)),
            "extended_description": lambda v: self.extended_edit.setPlainText(str(v)),
            "narrative_importance": lambda v: self._set_combo_value(
                self.importance_combo, str(v)
            ),
            "temporal_nature": lambda v: self._set_combo_value(self.nature_combo, str(v)),
        }
        widgets = {
            "name": self.name_edit,
            "entity_type": self.type_combo,
            "brief_description": self.brief_edit,
            "extended_description": self.extended_edit,
            "narrative_importance": self.importance_combo,
            "temporal_nature": self.nature_combo,
        }
        self._preview_extra = {}
        for key, value in patch.items():
            render = renderers.get(key)
            if render is None:
                # El panel no renderiza este campo (años, tags, alias…): viaja
                # tal cual en el diff y la superficie de revisión lo lista.
                self._preview_extra[key] = value
                continue
            render(value)
            widget = widgets[key]
            canon = self._preview_base.get(key)
            widget.setStyleSheet(
                widget.styleSheet() + f" border: 2px solid {self._PREVIEW_GOLD};"
            )
            widget.setToolTip(f"Propuesta de la IA — canon actual: «{canon}»")
        # Acciones laterales fuera: el preview solo revisa, no navega ni guarda solo.
        for side in (getattr(self, "save_btn", None), getattr(self, "more_menu_btn", None)):
            if side is not None:
                side.setVisible(False)

    def preview_extra_fields(self) -> dict:
        """Campos propuestos que la ficha no renderiza (los lista el revisor)."""
        return dict(self._preview_extra)

    def preview_payload(self) -> dict:
        """PLAY-16: diff contra el canon (propuesto por la IA + retoques del
        usuario en los widgets) SIN escribir nada."""
        current = {
            "name": self.name_edit.text().strip(),
            "entity_type": self.type_combo.currentData()
            or self.type_combo.currentText().strip().lower(),
            "brief_description": self.brief_edit.toPlainText().strip(),
            "extended_description": self.extended_edit.toPlainText().strip(),
            "narrative_importance": self.importance_combo.currentData() or "medio",
            "temporal_nature": self.nature_combo.currentData(),
        }
        diff = {
            key: value
            for key, value in current.items()
            if value != self._preview_base.get(key)
        }
        diff.update(self._preview_extra)
        return diff

    # UI2-06: _refresh_context desapareció — la lista viva de relaciones es la
    # pestaña «Relaciones» de la tarjeta del Foco (relations_panel.py).

    # ------------------------------------------------------------------
    # Advanced mode
    # ------------------------------------------------------------------

    def set_advanced_mode(self, enabled: bool):
        # BETA2-UX-03: ya no hay widgets técnicos ocultos que togglear (no-op).
        return

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self):
        """Manual save (button) — saves + refreshes UI."""
        _apptrace(f"UI node save entity_id={self.entity_id!r}")
        self._autosave_timer.stop()
        self._do_save(refresh_after=True)

    def _mention_targets_provider(self):
        """Proveedor (id, name, kind) de elementos mencionables por @nombre."""

        def provider():
            ps = getattr(self.entity_controller, "ps", None)
            project = getattr(ps, "active_project", None)
            return build_known_targets(project) if project is not None else []

        return provider

    def _sync_structured_references(self, field_texts: dict) -> None:
        """Resuelve las @menciones de la prosa a referencias estructuradas (MEM-03)."""
        ps = getattr(self.entity_controller, "ps", None)
        if ps is None or getattr(ps, "active_project", None) is None:
            return
        hints: dict[str, tuple[str, str]] = {}
        for ms in getattr(self, "_mention_supports", {}).values():
            hints.update(ms.hints())
        try:
            StructuredReferenceService(ps).sync_element_references(
                MemoryTargetKind.ENTITY, self.entity_id, field_texts, hints=hints
            )
        except Exception:  # noqa: BLE001 — nunca romper el guardado por las @menciones
            pass

    # ── FIX-11 (B3): fuentes de la entidad ──────────────────────────────

    def _source_controller(self):
        """Controlador de fuentes (la UI nunca toca persistencia directamente)."""
        ctrl = getattr(self, "_src_ctrl", None)
        if ctrl is not None:
            return ctrl
        ps = getattr(self.entity_controller, "ps", None)
        if ps is None:
            return None
        from hosts.DesktopHostPySide.controllers.source_controller import SourceController

        self._src_ctrl = SourceController(project_service=ps)
        return self._src_ctrl

    def _refresh_sources(self) -> None:
        ctrl = self._source_controller()
        if ctrl is None or not self.entity_id:
            return
        result = ctrl.sources_for_entity(self.entity_id)
        fuentes = result.value if not isinstance(result, Error) else []
        if not fuentes:
            self.sources_label.setText("Sin fuentes enlazadas")
            return
        lineas = []
        for fuente in fuentes:
            nombre = str(getattr(fuente, "name", "") or "Fuente sin nombre")
            referencia = str(getattr(fuente, "reference", "") or "")
            lineas.append(f"• {nombre}{f' — {referencia}' if referencia else ''}")
        self.sources_label.setText("\n".join(lineas))

    def add_source(self, name: str, reference: str = "", fragment: str = "") -> bool:
        """Crea la fuente y la ENLAZA a esta entidad. Devuelve si salió bien."""
        ctrl = self._source_controller()
        if ctrl is None or not (name or "").strip():
            return False
        creada = ctrl.create(
            {
                "name": name.strip(),
                "reference": reference.strip(),
                "fragment": fragment.strip(),
            }
        )
        if isinstance(creada, Error):
            self.ctx.log("error", creada.error)
            return False
        enlazada = ctrl.link_to_entity(creada.value.id, self.entity_id)
        if isinstance(enlazada, Error):
            self.ctx.log("error", enlazada.error)
            return False
        save = getattr(self.ctx, "request_save_silent", None) or getattr(
            self.ctx, "request_save_debounced", None
        )
        if callable(save):
            save()
        self._refresh_sources()
        return True

    def _open_source_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Añadir fuente")
        layout = QFormLayout(dialog)
        nombre = QLineEdit()
        nombre.setPlaceholderText("López de Ayala — Crónica del rey don Pedro")
        referencia = QLineEdit()
        referencia.setPlaceholderText("BNE MSS/1234, f. 12r · ISBN · enlace")
        fragmento = QTextEdit()
        fragmento.setPlaceholderText("Cita literal (opcional)")
        fragmento.setMaximumHeight(90)
        layout.addRow("Nombre", nombre)
        layout.addRow("Referencia", referencia)
        layout.addRow("Fragmento", fragmento)
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(dialog.accept)
        botones.rejected.connect(dialog.reject)
        layout.addRow(botones)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.add_source(nombre.text(), referencia.text(), fragmento.toPlainText())

    def _life_span_payload(self, birth_year: int | None, death_year: int | None) -> dict:
        """FIX-11 (fase B): lapso con la capa DESCRIPTIVA del inicio puesta al día.

        Parte del lapso vivo de la entidad (o del espejo entero si aún no hay
        lapso) y solo reescribe precisión/fecha-mundo/periodo/nota/fuentes: la
        era y la naturaleza temporal se conservan tal cual.

        FIX-12 (G2-29): además mueve el EJE ENTERO al año que el usuario acaba de
        escribir en «Nació»/«Murió». Hace falta hacerlo aquí porque el panel manda
        SIEMPRE `life_span`, y `reconcile_entity_dating` da prioridad al lapso
        sobre el espejo: sin esto, el año tecleado se perdería contra el lapso
        viejo. Se mueve SOLO el año — la precisión, la fecha del mundo, el periodo
        y las notas siguen siendo las que el usuario tenga puestas (BETA2-SHIP-07).
        """
        span = getattr(self._entity, "life_span", None)
        if span is None:
            span = TemporalSpan.from_years(
                getattr(self._entity, "birth_year", None),
                getattr(self._entity, "death_year", None),
            )
        datos = span.to_dict()
        inicio = dict(self.rigor.apply_to_temporality(datos.get("start")) or {})
        inicio["year"] = birth_year
        # Misma regla que `_apply_mirror_years_to_span` (BETA2-SHIP-07): un año
        # escrito sobre una precisión «sin determinar» pasa a exacto. No hay dos
        # criterios; si el usuario quiere «h. 1334», elige la precisión y manda.
        if birth_year is not None and _is_undetermined(inicio.get("precision")):
            inicio["precision"] = TemporalPrecision.EXACT.value
            combo = self.rigor.precision_combo
            combo.blockSignals(True)  # no relanzar el autoguardado desde dentro
            self._set_combo_value(combo, TemporalPrecision.EXACT.value)
            combo.blockSignals(False)
        # La nota «sin datar (pendiente)» es del sistema, no del usuario: en cuanto
        # hay año, deja de ser verdad. Si el usuario escribió su propia nota, se
        # respeta. Se limpia también el widget (`setText` no emite `textEdited`,
        # así que no dispara un autoguardado en cascada).
        if birth_year is not None and str(inicio.get("notes") or "").strip() == PENDING_NOTE:
            inicio["notes"] = ""
            self.rigor.notes_edit.setText("")
        datos["start"] = inicio
        if death_year is None:
            datos["end"] = None
            datos["ongoing"] = True
        else:
            fin = dict(datos.get("end") or {})
            fin["year"] = death_year
            if _is_undetermined(fin.get("precision")):
                fin["precision"] = TemporalPrecision.EXACT.value
            datos["end"] = fin
            datos["ongoing"] = False
        return datos

    def _do_save(self, *, refresh_after: bool = True):
        """Core save logic. refresh_after=True for manual save, False for auto-save."""
        _apptrace(f"UI node _do_save entity_id={self.entity_id!r} refresh_after={refresh_after}")
        if self._entity is None:
            return
        # PLAY-16: en preview el guardado NO escribe canon — emite el diff.
        if self.preview_patch is not None:
            if self.on_preview_save is not None:
                self.on_preview_save(self.preview_payload())
            return

        # Determine the picked type from the combo (11 tipos + personalizados).
        type_data = self.type_combo.currentData()
        type_text = self.type_combo.currentText().strip()
        if type_data:
            picked = str(type_data)
        elif type_text:
            picked = type_text.lower()  # tipo personalizado
        else:
            picked = "nota"

        # Build custom_metadata with colour
        meta = dict(getattr(self._entity, "custom_metadata", {}) or {})
        meta.pop("_visual_draft", None)

        # UI2-20: la ramitud se DERIVA del tipo. Elegir un tipo de rama hace la
        # entidad rama: el marcador interno sigue siendo 'contenedor' (motor de
        # anidamiento intacto) y el tipo elegido se recuerda como tree_type (el
        # kind mostrado). Elegir un tipo de hoja la deja como hoja — basta con
        # cambiar el entity_type para promover/degradar (la ramitud es derivada).
        if is_branch_type(picked):
            entity_type_value = "contenedor"
            if picked != "contenedor":
                meta["tree_type"] = picked  # KEY_TREE_TYPE de tree_meta
        else:
            entity_type_value = picked

        # BETA2-FOCO-16 (canon total): el panel NO emite canon_state — el
        # estado solo cambia por acciones explícitas (servicios/migración).
        if self._current_color:
            meta["_node_color"] = self._current_color
        # Remove _node_color if it matches the default (no need to store)
        default_color = _default_color_for_type(entity_type_value)
        if meta.get("_node_color") == default_color:
            meta.pop("_node_color", None)

        # FIX-12 (G2-29): años enteros escritos en la ficha.
        birth_year = self._parse_year_text(
            self.birth_year_edit.text(), getattr(self._entity, "birth_year", None)
        )
        death_year = self._parse_year_text(
            self.death_year_edit.text(), getattr(self._entity, "death_year", None)
        )

        payload = {
            "name": self.name_edit.text().strip(),
            "entity_type": entity_type_value,
            "brief_description": self.brief_edit.toPlainText().strip(),
            "extended_description": self.extended_edit.toPlainText().strip(),
            # BETA2-UX-03: notas preservadas por pass-through (ya no editables).
            "private_notes": getattr(self._entity, "private_notes", "") or "",
            "exportable_notes": getattr(self._entity, "exportable_notes", "") or "",
            # BETA2-FOCO: relevancia narrativa del usuario (calibra el riego).
            "narrative_importance": self.importance_combo.currentData() or "medio",
            # BETA-AUDIT-02: editable de nuevo. Si el proyecto trae un estado fuera
            # del subconjunto que ofrece la Ficha, el combo lo conserva (ver
            # _sync_visibility_combo) en vez de degradarlo a «Visible» al guardar.
            "visibility_state": self.visibility_combo.currentData()
            or _enum_value(getattr(self._entity, "visibility_state", None), "visible_usuario"),
            "layer_ids": ([self.layer_combo.currentData()] if self.layer_combo.currentData() else list(getattr(self._entity, "layer_ids", []) or [])) if self._worldbuilding_active() else list(getattr(self._entity, "layer_ids", []) or []),
            "custom_metadata": meta,
            # BETA-MULTIAGENT2-FIX-12 (G2-29): los años salen de las casillas
            # «Nació»/«Murió» de la ficha (antes viajaban por pass-through desde
            # la entidad y NO había ningún control que los pidiera).
            "birth_year": birth_year,
            "death_year": death_year,
            # BETA1-J07: naturaleza temporal editada en la ficha.
            "temporal_nature": self.nature_combo.currentData(),
            # BETA-MULTIAGENT2-FIX-11 (fase B): certeza editable de verdad (el campo
            # existía en el dominio y tenía CERO apariciones en `hosts/`).
            "certainty_level": self.rigor.certeza(),
        }
        # FIX-11: datación rica sobre el INICIO del lapso. Se parte del lapso actual
        # (o del espejo entero) para NO perder el año, la era ni la naturaleza: aquí
        # solo se escribe la capa descriptiva (precisión/fecha-mundo/periodo/nota).
        payload["life_span"] = self._life_span_payload(birth_year, death_year)
        self.ctx.log(
            "info",
            "B44TRACE node_save_layers "
            f"entity_id={self.entity_id!r} old_layers={list(getattr(self._entity, 'layer_ids', []) or [])!r} "
            f"combo_data={self.layer_combo.currentData()!r} payload_layers={payload.get('layer_ids', [])!r} "
            f"worldbuilding_active={self._worldbuilding_active()}",
        )
        if self._is_ghost:
            # BETA2-FOCO: los fantasmas solo cambian de canon por la conversión
            # explícita (GhostService) — el autosave no puede des-fantasmarlos.
            payload.pop("canon_state", None)
        result = self.entity_controller.update(self.entity_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        # BETA2-MEM-03: al guardar, resolver @menciones de la prosa → referencias
        # estructuradas (sidecar). Preview jamás escribe canon ni referencias.
        if not self.preview_patch:
            self._sync_structured_references(
                {
                    "brief_description": payload["brief_description"],
                    "extended_description": payload["extended_description"],
                }
            )
        self.ctx.log("info", "Elemento guardado")
        self.is_new = False
        self.ctx.selected_entity_id = self.entity_id
        if refresh_after:
            self.refresh()
        if self.on_saved is not None:
            self.on_saved()
