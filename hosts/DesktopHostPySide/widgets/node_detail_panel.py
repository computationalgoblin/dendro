"""Node detail panel — immersive entity editor for B31-CREATION-T01-B.

RightDrawer content opened from the graph when a node is selected. It reads and
updates entities through the UI controller.  Normal mode shows a warm, minimal
form with color picker, editable type, and non-blocking AI autocomplete.
Technical fields remain hidden unless advanced mode is active.
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QIntValidator, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.widgets.design_system import (
    ENTITY_KIND_PALETTE,
    GOLD,
    INK,
    INPUT_BG,
    LINE,
    LINE_STRONG,
    SPACE_LG,
    SPACE_MD,
    AdvancedSection,
    Badge,
    enum_human,
    human_ref,
)
from hosts.DesktopHostPySide.widgets.coherence_panel import CoherencePanel
from hosts.DesktopHostPySide.widgets.related_milestones_panel import RelatedMilestonesPanel
from packages.domain.entity import CanonState, EntityType, VisibilityState
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
_BG_DRAWER = "#F8F6ED"
_TITLE_COLOR = "#5C5A3E"
_LABEL_COLOR = "#6F6A42"
_MUTED_COLOR = "#7C806E"
_SUGGESTION_BG = "#FFFDF7"

# Default node colours per entity type (mirrors graph_canvas._NODE_COLORS).
# BETA1-UX04/UX07: paleta BOTÁNICA cálida (antes azules/lavandas frías que
# pintaban un swatch azul fuera de paleta en el editor). Debe coincidir con
# graph_canvas._NODE_COLORS.
# B39 terminology: branch types show as "Rama", all others as "Hoja"
BRANCH_TYPES = {"faccion", "cultura", "sistema_magico", "religion", "institucion", "trama", "contenedor"}

# UX15: paleta cálida por tipo centralizada en el design system (antes duplicada).
_NODE_COLORS: dict[str, str] = ENTITY_KIND_PALETTE

# Simplified canon options for normal mode
_SIMPLE_CANON = ["borrador", "canonico"]

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
    ):
        super().__init__()
        self.ctx = ctx
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
        self._connect_autosave_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)  # UX23: ritmo del scaffold
        root.setSpacing(SPACE_MD)

        # -- Header --
        head = QHBoxLayout()
        self.title = QLabel("Hoja")
        self.title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {_TITLE_COLOR}; "
            f"font-family: Georgia, 'Courier New', serif; background: transparent;"
        )
        self.title.setWordWrap(True)
        head.addWidget(self.title, 1)
        self.type_badge = Badge("Hoja", "info")
        head.addWidget(self.type_badge)
        root.addLayout(head)
        # BETA1-F04: "Enfocar vecindad" fuera del panel editorial (la
        # navegación vive en el grafo: doble click / menú contextual).

        # -- Compact summary line --
        self.summary = QLabel("")
        self.summary.setObjectName("mutedLabel")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
        root.addWidget(self.summary)

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
        # UX28: el color del nodo lo decide el TIPO de entidad (paleta de Dendro),
        # no un selector manual. Se conserva el objeto para refs internas, pero NO
        # se añade al layout (el canvas ya colorea el contorno por tipo).
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.setToolTip("Color del nodo")
        self.color_btn.clicked.connect(self._pick_color)
        self.color_btn.setVisible(False)
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
        form_layout.addRow(self.nature_label, self.nature_combo)

        # Descripción breve: tras la imagen (montada fuera del form) — el
        # widget se crea aquí, se monta más abajo en el orden F05.
        self.brief_edit = QTextEdit()
        self.brief_edit.setMaximumHeight(64)
        self.brief_edit.setPlaceholderText("Descripción breve…")
        # BETA1-F05: viñetas protagonistas (breve y cuerpo).
        # BETA1-UX08: estados coherentes con el sistema central (borde LINE,
        # hover LINE_STRONG, foco oro 2px) en vez de hexes sueltos.
        _card_ss = (
            f"QTextEdit {{ background: {INPUT_BG}; border: 1px solid {LINE}; "
            f"border-radius: 12px; padding: 10px; font-size: 13px; color: {INK}; }} "
            f"QTextEdit:hover {{ border-color: {LINE_STRONG}; }} "
            f"QTextEdit:focus {{ border: 2px solid {GOLD}; background: #FFFFFF; padding: 9px; }}"
        )
        self.brief_edit.setStyleSheet(_card_ss)
        self._editorial_card_ss = _card_ss

        # Estado/canon → submenú "Más opciones" (BETA1-F04); se crea aquí,
        # se monta más abajo.
        self.canon_combo = QComboBox()
        for val in _SIMPLE_CANON:
            self.canon_combo.addItem(enum_human(val), val)

        root.addWidget(form_card)

        # BETA1-F04: imagen opcional (placeholder + importar; persistencia
        # mínima en custom_metadata — gestión avanzada de assets = deuda)
        self.image_preview = QLabel()
        self.image_preview.setVisible(False)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet("border: 1px solid #D8D6C8; border-radius: 10px; background: rgba(255,255,255,0.4); padding: 4px;")
        self.image_preview.setMaximumHeight(160)
        root.addWidget(self.image_preview)
        image_row = QHBoxLayout()
        self.image_btn = QPushButton("Añadir imagen…")
        self.image_btn.setFixedHeight(26)
        self.image_btn.clicked.connect(self._pick_image)
        image_row.addWidget(self.image_btn)
        image_row.addStretch(1)
        root.addLayout(image_row)

        # BETA1-F05: descripción breve tras la imagen
        root.addWidget(self.brief_edit)

        # BETA1-F04: el CUERPO es el centro del panel — sin tope de altura,
        # con prioridad de espacio (~70-80% del panel).
        body_label = QLabel("Cuerpo")
        body_label.setStyleSheet(_label_ss)
        root.addWidget(body_label)
        self.extended_edit = QTextEdit()
        self.extended_edit.setMinimumHeight(300)
        self.extended_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.extended_edit.setStyleSheet(self._editorial_card_ss)
        root.addWidget(self.extended_edit, 1)

        # -- Hidden fields (only in advanced mode) --
        self._advanced_widgets: list[QWidget] = []

        self.private_notes_edit = QTextEdit()
        self.private_notes_edit.setMaximumHeight(70)
        self.exportable_notes_edit = QTextEdit()
        self.exportable_notes_edit.setMaximumHeight(70)
        self.visibility_combo = QComboBox()
        for item in VisibilityState:
            self.visibility_combo.addItem(enum_human(item.value), item.value)

        # BETA1-H07: notas privadas/exportables y visibilidad no forman parte de
        # la UI. Los widgets existen sin montar: la carga/guardado los sigue
        # leyendo y ningún dato se pierde.

        # -- Compact context summary --
        self.context_box = QGroupBox("Contexto")
        # BETA1-G07: este box vive SIN montar (dato, no UI — ver más abajo). Un
        # QGroupBox sin padre, al hacerse visible, se convierte en una VENTANA
        # flotante (los "pop ups"). Darle padre lo ancla al panel: jamás flota.
        self.context_box.setParent(self)
        self.context_box.hide()
        self.context_box.setStyleSheet(
            f"QGroupBox {{ color: {_LABEL_COLOR}; font-weight: 600; "
            f"border: 1px solid #D8D6C8; border-radius: 10px; "
            f"margin-top: 8px; padding-top: 14px; background: transparent; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )
        context_layout = QVBoxLayout(self.context_box)
        context_layout.setSpacing(2)
        self.relations_label = QLabel("Relaciones: —")
        self.relations_label.setWordWrap(True)
        self.campaigns_label = QLabel("Campañas: —")
        self.campaigns_label.setWordWrap(True)
        for w in (self.relations_label, self.campaigns_label):
            w.setObjectName("mutedLabel")
            w.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
            context_layout.addWidget(w)
        # BETA1-F04: contexto → submenú "Más opciones" (montado más abajo)

        self.related_milestones_panel = None
        if self.milestone_controller is not None:
            self.related_milestones_panel = RelatedMilestonesPanel(
                milestone_controller=self.milestone_controller,
                target_kind="entity",
                target_id=self.entity_id,
                project_getter=self._project,
                entity_controller=self.entity_controller,
                relation_controller=self.relation_controller,
                on_open_chronology=self.on_open_milestones,
                on_suggest_milestone=self.on_suggest_milestone,
                on_created=self.on_saved,
            )
            # BETA1-F04: hitos relacionados → submenú "Más opciones"

        # -- B39: Convert to branch button (hidden by default, wired in T02) --
        self.convert_to_branch_btn = QPushButton("Convertir en rama")
        self.convert_to_branch_btn.setFixedHeight(32)
        self.convert_to_branch_btn.setStyleSheet(
            "QPushButton { background: #6F6A42; color: #F8F5EA; border: none; "
            "border-radius: 8px; padding: 4px 12px; font-size: 12px; } "
            "QPushButton:hover { background: #504B2E; }"
        )
        self.convert_to_branch_btn.setVisible(False)
        self.convert_to_branch_btn.clicked.connect(self._convert_to_branch)
        # BETA1-F04: convertir en rama → submenú "Más opciones"

        # -- AI suggestion section --
        ai_card = QFrame()
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

        # Coherence analysis button
        self.ai_coherence_btn = QPushButton("Analizar coherencia")
        self.ai_coherence_btn.setFixedHeight(28)
        self.ai_coherence_btn.setToolTip("Analizar coherencia narrativa de esta entidad con su contexto")
        self.ai_coherence_btn.setEnabled(self.ai_controller is not None)
        self.ai_coherence_btn.clicked.connect(self._open_coherence)
        ai_layout.addWidget(self.ai_coherence_btn)

        # BETA1-F00B: las acciones causales antiguas ya no viven en este
        # panel; se invocan desde command bar/menu contextual.
        self.ai_coherence_btn.setVisible(False)

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

        # -- Technical box (advanced only) --
        self.technical_box = QGroupBox("Datos técnicos")
        # BETA1-G07: igual que context_box — anclado al panel para que nunca
        # flote como ventana (popup) al togglear el modo avanzado.
        self.technical_box.setParent(self)
        self.technical_box.hide()
        self.technical_box.setStyleSheet(
            f"QGroupBox {{ color: {_LABEL_COLOR}; font-weight: 600; "
            f"border: 1px solid #D8D6C8; border-radius: 10px; "
            f"margin-top: 8px; padding-top: 14px; background: transparent; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )
        technical_layout = QVBoxLayout(self.technical_box)
        self.technical_text = QTextEdit()
        self.technical_text.setReadOnly(True)
        self.technical_text.setMaximumHeight(120)
        technical_layout.addWidget(self.technical_text)

        # BETA1-F04: submenú "Más opciones" — todo lo secundario, plegado.
        # (Estado/canon, contexto, hitos, convertir en rama, datos técnicos
        # —estos últimos siguen además sujetos al modo avanzado—.)
        self.more_section = AdvancedSection("Más opciones")
        canon_row = QHBoxLayout()
        canon_mini_label = QLabel("Estado:")
        canon_mini_label.setStyleSheet(_label_ss)
        canon_row.addWidget(canon_mini_label)
        canon_row.addWidget(self.canon_combo, 1)
        self.more_section.body_layout.addLayout(canon_row)
        # BETA1-F05: contexto y datos técnicos FUERA del producto (los
        # widgets viven sin montar; _refresh_context/_refresh_technical
        # siguen escribiendo en ellos sin coste visual).
        if self.related_milestones_panel is not None:
            self.more_section.body_layout.addWidget(self.related_milestones_panel)
        self.more_section.body_layout.addWidget(self.convert_to_branch_btn)
        root.addWidget(self.more_section)

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
        from pathlib import Path as _Path
        if not path or not _Path(path).exists():
            self.image_preview.setVisible(False)
            self.image_btn.setText("Añadir imagen…")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_preview.setVisible(False)
            return
        self.image_preview.setPixmap(pixmap.scaledToHeight(150, Qt.TransformationMode.SmoothTransformation))
        self.image_preview.setVisible(True)
        self.image_btn.setText("Cambiar imagen…")

    def _update_color_swatch(self, hex_color: str):
        self._current_color = hex_color
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {hex_color}; border: 2px solid #D8D6C8; "
            f"border-radius: 6px; }} "
            f"QPushButton:hover {{ border-color: #AAA579; }}"
        )
        self.color_btn.setToolTip(f"Color: {hex_color}")

    def _pick_color(self):
        current = QColor(self._current_color)
        color = QColorDialog.getColor(current, self, "Color del nodo")
        if color.isValid():
            self._update_color_swatch(color.name())

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
        self.private_notes_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.exportable_notes_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.canon_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.type_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.layer_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.nature_combo.currentIndexChanged.connect(self._schedule_autosave)
        # BETA1-UX2C: el lapso de vida ya no se edita aquí (se estira el nodo en
        # la cronología), así que no hay campos de año que autoguardar.

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
        private_notes = self.private_notes_edit.toPlainText().strip()
        exportable_notes = self.exportable_notes_edit.toPlainText().strip()
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

    def _open_coherence(self):
        """Open coherence analysis panel for this entity."""
        _apptrace(f"UI node run_coherence_check entity_id={self.entity_id!r}")
        if self.ai_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "IA contextual no disponible para coherencia")
            return
        panel = CoherencePanel(
            self.ctx,
            self.ai_controller,
            self.entity_controller,
            self.relation_controller,
            entity_ids=[self.entity_id],
            relation_ids=[],
            on_saved=self.on_saved,
        )
        self.ctx.drawer.set_content(panel, title="Coherencia")
        self.ctx.drawer.open()

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
            self.summary.setText(
                f"{enum_human(kind)} · {enum_human(canon_val)}"
            )
            self._refresh_layer_combo(entity)

            self.name_edit.setText(getattr(entity, "name", ""))
            self._set_combo_value(self.type_combo, kind)

            # BETA1-UX2C: lapso de vida solo-lectura (se edita en la cronología)
            self._refresh_lifespan_label(entity)
            self.brief_edit.setPlainText(getattr(entity, "brief_description", "") or "")
            self.extended_edit.setPlainText(getattr(entity, "extended_description", "") or "")
            self.private_notes_edit.setPlainText(getattr(entity, "private_notes", "") or "")
            self.exportable_notes_edit.setPlainText(getattr(entity, "exportable_notes", "") or "")

            # Canon combo (simplified)
            if "canon" in canon_val.lower():
                self.canon_combo.setCurrentIndex(1)  # Canónico
            else:
                self.canon_combo.setCurrentIndex(0)  # Borrador

            self._set_combo_value(self.visibility_combo, _enum_value(getattr(entity, "visibility_state", None), ""))

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
            self._refresh_technical(entity)
            self.set_advanced_mode(self.ctx.advanced_mode)

            # B39: Show "Convertir en rama" only for non-container entities
            is_branch = kind.lower() in BRANCH_TYPES or kind.lower() == "contenedor"
            self.convert_to_branch_btn.setVisible(not is_branch)
        finally:
            self._refreshing = False

    def _refresh_context(self, entity):
        project = self._project()
        if project is None:
            return
        entity_id = getattr(entity, "id", "")
        relation_lines = []
        for relation in getattr(project, "relations", []) or []:
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if entity_id not in {src, tgt}:
                continue
            other = self._entity_by_id(tgt if src == entity_id else src)
            other_ref = (
                human_ref(
                    getattr(other, "name", "?"),
                    enum_human(_enum_value(getattr(other, "entity_type", None), "")),
                )
                if other
                else "Elemento vinculado"
            )
            relation_lines.append(
                f"{enum_human(_enum_value(getattr(relation, 'relation_type', None), 'relación'))}: {other_ref}"
            )
        self.relations_label.setText("Relaciones: " + ("; ".join(relation_lines[:6]) if relation_lines else "—"))

        campaigns = []
        for campaign in getattr(project, "campaigns", []) or []:
            refs = {getattr(campaign, "world_entity_id", None)} | set(
                getattr(campaign, "active_location_entity_ids", []) or []
            )
            if entity_id in refs:
                campaigns.append(getattr(campaign, "name", "Campaña"))
        self.campaigns_label.setText("Campañas: " + ("; ".join(campaigns[:6]) if campaigns else "—"))

    def _refresh_technical(self, entity):
        payload = {
            "id": getattr(entity, "id", ""),
            "aliases": getattr(entity, "aliases", []),
            "tags": getattr(entity, "tags", []),
            "domain_ids": getattr(entity, "domain_ids", []),
            "layer_ids": getattr(entity, "layer_ids", []),
            "custom_metadata": getattr(entity, "custom_metadata", {}),
            "custom_type_id": getattr(entity, "custom_type_id", None),
            "custom_fields": [
                f.to_dict() if hasattr(f, "to_dict") else f
                for f in (getattr(entity, "custom_fields", []) or [])
            ],
        }
        self.technical_text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    # ------------------------------------------------------------------
    # Advanced mode
    # ------------------------------------------------------------------

    def set_advanced_mode(self, enabled: bool):
        # BETA1-G07: technical_box vive SIN montar (FUERA del producto, F05).
        # NO se togglea su visibilidad: hacerlo lo abría como ventana flotante
        # (los "pop ups" al seleccionar en modo avanzado). El texto se sigue
        # rellenando por _refresh_technical para quien lo lea por código.
        for w in self._advanced_widgets:
            w.setVisible(bool(enabled))

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

        # Determine canon_state from simplified combo
        canon_data = self.canon_combo.currentData()
        canon_value = canon_data if canon_data else "borrador"

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
            "private_notes": self.private_notes_edit.toPlainText().strip(),
            "exportable_notes": self.exportable_notes_edit.toPlainText().strip(),
            "canon_state": canon_value,
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
