"""Node detail panel — immersive entity editor for B31-CREATION-T01-B.

RightDrawer content opened from the graph when a node is selected. It reads and
updates entities through the UI controller.  Normal mode shows a warm, minimal
form with color picker, editable type, and non-blocking AI autocomplete.
Technical fields remain hidden unless advanced mode is active.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
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
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from hosts.DesktopHostPySide.app_trace import _apptrace
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
    SURFACE,
    SURFACE_HI,
    Badge,
    enum_human,
)
from packages.domain.entity import EntityType
from packages.domain.entity_taxonomy import (
    BEING_NATURES,
    LEAF_ENTITY_TYPES,
    has_temporal_nature,
)
from packages.domain.result import Error
from packages.application.world_layer_causal import get_causal_rank, sort_layers_by_causal_rank

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
# B39 terminology: branch types show as "Rama", all others as "Hoja"
BRANCH_TYPES = {"faccion", "cultura", "sistema_magico", "religion", "institucion", "trama", "contenedor"}

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
    ):
        super().__init__()
        self.ctx = ctx
        # BETA2-FOCO: variant="foco" monta las relaciones clicables en el propio
        # formulario (abren panel ADYACENTE) y oculta el bloque IA inline.
        self.variant = str(variant or "drawer")
        self.on_open_relation = on_open_relation
        # FOCO-20: «+» de la sección Relaciones (abre el flujo de crear relación).
        self.on_create_relation = on_create_relation
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
        self._connect_autosave_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
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
            "font-size: 11px; text-align: center; }} "
            f"QPushButton:hover {{ color: {_TITLE_COLOR}; }}"
        )
        self.image_btn.clicked.connect(self._pick_image)
        image_column.addWidget(self.image_btn)
        image_column.addStretch(1)
        head.addLayout(image_column)

        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        self.title = QLabel("Hoja")
        self.title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {_TITLE_COLOR}; "
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
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
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
        self.convert_to_branch_action = self._more_menu.addAction("Convertir en rama")
        self.convert_to_branch_action.triggered.connect(self._convert_to_branch)
        self.more_menu_btn.setMenu(self._more_menu)
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
        form_layout = QFormLayout(form_card)
        form_layout.setContentsMargins(0, 4, 0, 4)
        form_layout.setSpacing(8)
        form_layout.labelAlignment = 0x0002  # Qt.AlignmentFlag.AlignRight
        _label_ss = f"color: {_LABEL_COLOR}; background: transparent; font-weight: 600;"

        # BETA1-F05 layout exacto: NOMBRE + TIPO + ANILLO en UNA fila fluida.
        first_row = QHBoxLayout()
        first_row.setSpacing(8)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre")
        first_row.addWidget(self.name_edit, 3)
        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        # BETA1-J08: la HOJA solo ofrece tipos de hoja (sigue editable por los
        # tipos personalizados).
        for item in LEAF_ENTITY_TYPES:
            self.type_combo.addItem(enum_human(item.value), item.value)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        first_row.addWidget(self.type_combo, 2)
        # Legacy ref kept for older code paths; never shown as UI. If this
        # empty label is made visible without a layout, Qt opens it as a
        # top-level blank popout.
        self.layer_label = QLabel("", self)
        self.layer_label.hide()
        self.layer_combo = QComboBox()
        self.layer_combo.addItem("— Sin anillo —", "")
        first_row.addWidget(self.layer_combo, 2)
        # UX28/BETA2-UX-03: el color del nodo lo decide el TIPO de entidad
        # (paleta de Dendro); no hay selector manual de color.
        form_layout.addRow(first_row)

        # BETA1-UX2C: el lapso de vida (origen → fin) se EDITA estirando el nodo
        # en la vista Cronología; aquí solo se MUESTRA, derivado de birth/death y
        # de las eras efectivas (las mismas que pinta la cronológica). Solo lectura.
        self.lifespan_label = QLabel("")
        self.lifespan_label.setWordWrap(True)
        self.lifespan_label.setStyleSheet(
            f"color: {_MUTED_COLOR}; background: transparent; font-size: 12px;"
        )
        self.lifespan_label.setToolTip(
            "Define el origen y el fin estirando el nodo en la vista Cronología."
        )
        form_layout.addRow(self.lifespan_label)

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
        form_layout.addRow(self.nature_label, self.nature_combo)

        # FOCO-20: «Relevancia narrativa» visible en el formulario principal
        # (calibra el riego y la invalidación de 2º grado; antes estaba
        # enterrada en «Más opciones»). Se crea aquí y se conecta al autosave.
        self.importance_combo = QComboBox()
        for val in ("critico", "alto", "medio", "bajo", "menor"):
            self.importance_combo.addItem(enum_human(val), val)
        self.importance_combo.setToolTip(
            "Cuánto pesa esta entidad en la trama. Calibra la exigencia del "
            "riego y qué cambios vecinos la invalidan."
        )
        importance_label = QLabel("Relevancia")
        importance_label.setStyleSheet(_label_ss)
        form_layout.addRow(importance_label, self.importance_combo)

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

        # BETA2-UX-03: notas privadas/exportables, visibilidad y el resumen de
        # «Contexto» (relations_label/campaigns_label) eran widgets muertos (sin
        # montar). Se eliminaron; notas y visibilidad se PRESERVAN por
        # pass-through en el guardado. La lista viva de relaciones clicables la
        # construye _build_relations_section/_rebuild_relation_rows.

        # FOCO-20: los hitos ya NO viven en el formulario — se muestran y se
        # crean en la cronología local bajo el editor (FocoLifelineBand); el
        # atributo queda en None para las rutas que lo consultan.
        self.related_milestones_panel = None
        # FOCO-20: «Convertir en rama» vive en el menú ⋯ de la cabecera
        # (self.convert_to_branch_action, creado junto al header).

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
        # «Convertir en rama» en el menú ⋯ de la cabecera. La sección de
        # RELACIONES es una lista real (todas, clicables → panel adyacente).
        if self.variant == "foco":
            root.addWidget(self._build_relations_section())

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
    # FOCO-20: sección de Relaciones (lista real, clicable, sin tope)
    # ------------------------------------------------------------------

    def _build_relations_section(self) -> QFrame:
        section = QFrame()
        section.setObjectName("relationsSection")
        section.setStyleSheet("QFrame#relationsSection { background: transparent; border: none; }")
        box = QVBoxLayout(section)
        box.setContentsMargins(0, SPACE_MD, 0, 0)
        box.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("RELACIONES")
        title.setStyleSheet(
            f"color: {_MUTED_COLOR}; background: transparent; font-size: 11px; "
            "font-weight: 700; letter-spacing: 1px;"
        )
        header.addWidget(title)
        header.addStretch(1)
        self.add_relation_btn = QToolButton()
        self.add_relation_btn.setText("+")
        self.add_relation_btn.setToolTip("Crear relación desde esta entidad")
        self.add_relation_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_relation_btn.setStyleSheet(
            f"QToolButton {{ border: 1px solid {LINE_SOFT}; border-radius: 10px; "
            f"background: transparent; color: {_LABEL_COLOR}; font-size: 14px; "
            f"padding: 0 7px; }} "
            f"QToolButton:hover {{ border-color: {GOLD}; color: {_TITLE_COLOR}; }}"
        )
        self.add_relation_btn.setVisible(callable(self.on_create_relation))
        if callable(self.on_create_relation):
            self.add_relation_btn.clicked.connect(lambda: self.on_create_relation())
        header.addWidget(self.add_relation_btn)
        box.addLayout(header)

        self._relations_rows = QVBoxLayout()
        self._relations_rows.setSpacing(2)
        box.addLayout(self._relations_rows)
        self.relations_empty_label = QLabel("Sin relaciones todavía.")
        self.relations_empty_label.setStyleSheet(
            f"color: {_MUTED_COLOR}; background: transparent; font-style: italic;"
        )
        box.addWidget(self.relations_empty_label)
        return section

    def _rebuild_relation_rows(self, entries: list[tuple[str, str]]) -> None:
        """entries = [(relation_id, texto)] — una fila-botón por relación."""
        rows = getattr(self, "_relations_rows", None)
        if rows is None:
            return
        while rows.count():
            item = rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.relations_empty_label.setVisible(not entries)
        for relation_id, text in entries:
            row = QPushButton(text)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 8px; background: transparent; "
                f"color: {_LABEL_COLOR}; text-align: left; padding: 6px 8px; font-size: 13px; }} "
                f"QPushButton:hover {{ background: {SURFACE}; color: {_TITLE_COLOR}; }}"
            )
            if relation_id:
                row.clicked.connect(
                    lambda _=False, rid=relation_id: self._on_relation_link(rid)
                )
            rows.addWidget(row)

    # ------------------------------------------------------------------
    # Colour helpers
    # ------------------------------------------------------------------

    # ── BETA1-F04: imagen opcional ───────────────────────────────────────

    def _pick_image(self):
        """Importa una imagen y la asocia a la hoja (persistencia mínima:
        ruta en custom_metadata. Gestión avanzada de assets = deuda F)."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar imagen", "", "Imágenes (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        entity = self._entity_by_id(self.entity_id)
        metadata = dict(getattr(entity, "custom_metadata", {}) or {}) if entity is not None else {}
        metadata["_image_path"] = path
        result = self.entity_controller.update(self.entity_id, {"custom_metadata": metadata})
        if isinstance(result, Error):
            self.ctx.log("error", f"No se pudo asociar la imagen: {result.error}")
            return
        self._show_image(path)
        self.ctx.log("info", "Imagen asociada a la hoja")

    def _show_image(self, path: str):
        # FOCO-20: miniatura integrada en la cabecera — siempre visible; sin
        # imagen queda el marco punteado como placeholder.
        from pathlib import Path as _Path
        if not path or not _Path(path).exists():
            self.image_preview.clear()
            self.image_btn.setText("Imagen…")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_preview.clear()
            return
        self.image_preview.setPixmap(
            pixmap.scaled(
                self.image_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
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
            self._update_color_swatch(_default_color_for_type(type_val))
        self._update_nature_visibility()
        self._schedule_autosave()

    def _update_nature_visibility(self):
        """BETA1-J08: el combo de naturaleza solo aparece para seres."""
        type_val = self.type_combo.currentData() or self.type_combo.currentText().strip().lower()
        try:
            is_being = has_temporal_nature(EntityType(type_val))
        except ValueError:
            is_being = False
        self.nature_combo.setVisible(is_being)
        self.nature_label.setVisible(is_being)

    # ------------------------------------------------------------------
    # Auto-save (debounced)
    # ------------------------------------------------------------------

    def _connect_autosave_signals(self):
        """Connect all editable field signals to the debounced auto-save timer."""
        self.name_edit.textEdited.connect(self._schedule_autosave)
        self.brief_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.extended_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.importance_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.type_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.layer_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.nature_combo.currentIndexChanged.connect(self._schedule_autosave)
        # BETA1-UX2C: el lapso de vida ya no se edita aquí (se estira el nodo en
        # la cronología), así que no hay campos de año que autoguardar.

    def _on_relation_link(self, relation_id: str) -> None:
        """BETA2-FOCO: una relación de la lista se abre en su panel adyacente."""
        if callable(self.on_open_relation) and relation_id:
            self.on_open_relation(relation_id)

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
            self.ctx.log("error", "No se pudo convertir en rama: servicio no disponible")
            return
        from packages.domain.result import Error
        result = entity_service.convert_to_branch(self.entity_id)
        if isinstance(result, Error):
            self.ctx.log("error", f"Error convirtiendo en rama: {result.error}")
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

    def _era_name_for_year(self, year) -> str:
        """Nombre de era para *year* usando las eras EFECTIVAS (las mismas que
        pinta la cronológica: dominio o derivadas del calendario completo)."""
        if year is None:
            return ""
        project = self._project()
        if project is None:
            return ""
        try:
            from hosts.DesktopHostPySide.widgets.chrono_canvas import effective_eras
            for era in effective_eras(project):
                start = getattr(era, "start_year", None)
                end = getattr(era, "end_year", None)
                if start is None or int(year) < int(start):
                    continue
                if end is None or int(year) < int(end):
                    return str(getattr(era, "name", "") or "")
        except Exception:
            return ""
        return ""

    def _refresh_lifespan_label(self, entity) -> None:
        """Muestra el lapso derivado de birth/death (origen → fin/presente) y el
        estado de datación (BETA1-J06: Por datar / Sin fundamentar / Datado…)."""
        from hosts.DesktopHostPySide.widgets.candidate_review_panel import dating_badge_label

        # BETA1-J07: sincroniza el combo de naturaleza temporal con la entidad.
        span = getattr(entity, "life_span", None)
        nature_value = getattr(getattr(span, "nature", None), "value", "mortal")
        self.nature_combo.blockSignals(True)
        idx = self.nature_combo.findData(nature_value)
        self.nature_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.nature_combo.blockSignals(False)
        self._update_nature_visibility()

        badge = dating_badge_label(entity)
        birth = getattr(entity, "birth_year", None)
        death = getattr(entity, "death_year", None)
        if birth is None:
            self.lifespan_label.setText(
                f"Lapso de vida: [{badge}] · dátalo aquí o en la Cronología"
            )
            return

        def part(year: int) -> str:
            era = self._era_name_for_year(year)
            return f"año {int(year)}" + (f" · {era}" if era else "")

        if death is None:
            text = f"Lapso de vida:  origen {part(birth)}  →  presente"
        else:
            text = f"Lapso de vida:  origen {part(birth)}  →  fin {part(death)}"
        self.lifespan_label.setText(f"{text}   [{badge}]")

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
            # BETA1-F04: imagen asociada (si la hay)
            metadata = dict(getattr(entity, "custom_metadata", {}) or {})
            self._show_image(str(metadata.get("_image_path", "")))
            self._entity = entity
            kind = _enum_value(getattr(entity, "entity_type", None), "entidad")
            self.title.setText(getattr(entity, "name", "Sin nombre") or "Sin nombre")
            # B39: badge shows "Rama" for branch types, "Hoja" otherwise
            b39_label = "Rama" if kind.lower() in BRANCH_TYPES else "Hoja"
            self.type_badge.setText(b39_label)
            canon_val = _enum_value(getattr(entity, "canon_state", None), "")
            # FOCO-20 + canon total: la línea resumen muestra el TIPO; el único
            # estado que existe de cara al usuario es «fantasma» (badge propio).
            self.summary.setText(enum_human(kind))
            self._refresh_layer_combo(entity)

            self.name_edit.setText(getattr(entity, "name", ""))
            self._set_combo_value(self.type_combo, kind)

            # BETA1-UX2C: lapso de vida solo-lectura (se edita en la cronología)
            self._refresh_lifespan_label(entity)
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


            # Color
            meta = getattr(entity, "custom_metadata", {}) or {}
            stored_color = meta.get("_node_color")
            if stored_color:
                self._update_color_swatch(stored_color)
            else:
                self._update_color_swatch(_default_color_for_type(kind))

            self._refresh_context(entity)
            if self.related_milestones_panel is not None:
                self.related_milestones_panel.refresh()
            self.set_advanced_mode(self.ctx.advanced_mode)

            # B39/FOCO-20: «Convertir en rama» (menú ⋯) solo para hojas; un
            # fantasma se convierte primero en entidad real (rail de Foco).
            is_branch = kind.lower() in BRANCH_TYPES or kind.lower() == "contenedor"
            self.convert_to_branch_action.setVisible(not is_branch)
            self.convert_to_branch_action.setEnabled(not self._is_ghost)
            self.more_menu_btn.setVisible(not is_branch)
        finally:
            self._refreshing = False

    def _refresh_context(self, entity):
        # BETA2-UX-03: el resumen «Contexto» (relations_label/campaigns_label)
        # era dato-no-UI y se eliminó. Aquí solo se construye la lista VIVA de
        # relaciones clicables del formulario (_rebuild_relation_rows).
        project = self._project()
        if project is None:
            return
        entity_id = getattr(entity, "id", "")
        relation_rows: list[tuple[str, str]] = []
        for relation in getattr(project, "relations", []) or []:
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if entity_id not in {src, tgt}:
                continue
            outgoing = src == entity_id
            other = self._entity_by_id(tgt if outgoing else src)
            kind_text = enum_human(
                _enum_value(getattr(relation, "relation_type", None), "relación")
            )
            relation_id = str(getattr(relation, "id", "") or "")
            # FOCO-20: fila real con glifo de dirección (todas, sin tope).
            direction = _enum_value(getattr(relation, "direction", None), "")
            glyph = "↔" if direction == "bidireccional" else ("→" if outgoing else "←")
            ghost_mark = (
                "  ·  fantasma"
                if _enum_value(getattr(relation, "canon_state", None), "") == "fantasma"
                else ""
            )
            other_name = getattr(other, "name", "?") if other else "Elemento vinculado"
            relation_rows.append(
                (relation_id, f"{glyph}  {kind_text} · {other_name}{ghost_mark}")
            )
        self._rebuild_relation_rows(relation_rows)

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

    def _do_save(self, *, refresh_after: bool = True):
        """Core save logic. refresh_after=True for manual save, False for auto-save."""
        _apptrace(f"UI node _do_save entity_id={self.entity_id!r} refresh_after={refresh_after}")
        if self._entity is None:
            return

        # Determine entity_type — prefer combo data (enum value), fall back to text
        type_data = self.type_combo.currentData()
        type_text = self.type_combo.currentText().strip()
        if type_data:
            entity_type_value = type_data
        elif type_text:
            # Custom type — store as string (lowered)
            entity_type_value = type_text.lower()
        else:
            entity_type_value = "nota"

        # BETA2-FOCO-16 (canon total): el panel NO emite canon_state — el
        # estado solo cambia por acciones explícitas (servicios/migración).

        # Build custom_metadata with colour
        meta = dict(getattr(self._entity, "custom_metadata", {}) or {})
        meta.pop("_visual_draft", None)
        if self._current_color:
            meta["_node_color"] = self._current_color
        # Remove _node_color if it matches the default (no need to store)
        default_color = _default_color_for_type(entity_type_value)
        if meta.get("_node_color") == default_color:
            meta.pop("_node_color", None)

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
            "visibility_state": _enum_value(getattr(self._entity, "visibility_state", None), "visible_usuario"),
            "layer_ids": ([self.layer_combo.currentData()] if self.layer_combo.currentData() else list(getattr(self._entity, "layer_ids", []) or [])) if self._worldbuilding_active() else list(getattr(self._entity, "layer_ids", []) or []),
            "custom_metadata": meta,
            # BETA1-UX2C: el lapso de vida se edita en la cronología; al guardar
            # el panel se conservan TAL CUAL (pass-through) para no borrarlo.
            "birth_year": getattr(self._entity, "birth_year", None),
            "death_year": getattr(self._entity, "death_year", None),
            # BETA1-J07: naturaleza temporal editada en la ficha.
            "temporal_nature": self.nature_combo.currentData(),
        }
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
        self.ctx.log("info", "Elemento guardado")
        self.is_new = False
        self.ctx.selected_entity_id = self.entity_id
        if refresh_after:
            self.refresh()
        if self.on_saved is not None:
            self.on_saved()
