"""Tree container detail panel — B32-T02..T05.

Expanded panel for semantic tree containers.  Sections:
  1. Identidad  (name, tree_type, color, brief, extended_description)
  2. Función narrativa (narrative_role, importance, development)
  3. Contenido  (members, sub-trees, internal/external relations)
  4. Worldbuilding + Canon (layers, canon/certainty, rules, questions)
  5. IA         (suggestion frame with editable preview)

Uses TreeMeta (B32-T01) for tree-specific custom_metadata keys.
IA uses node_text_suggestion — no candidate creation.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.widgets.design_system import SPACE_LG, SPACE_MD, AdvancedSection
from hosts.DesktopHostPySide.widgets.related_milestones_panel import RelatedMilestonesPanel
from packages.application.tree_meta import NARRATIVE_ROLES, TreeMeta
from packages.application.world_layer_causal import get_causal_rank, sort_layers_by_causal_rank
from packages.domain.entity import (
    CanonState,
    CertaintyLevel,
    DevelopmentLevel,
    EntityType,
    NarrativeImportance,
    VisibilityState,
)
from packages.domain.entity_taxonomy import BRANCH_ENTITY_TYPES
from packages.domain.result import Error

# BETA1-J08: la rama ofrece solo tipos de CONTENEDOR (facción, cultura,
# localización…), distintos de los de la hoja.
_RAMA_TYPE_VALUES = [t.value for t in BRANCH_ENTITY_TYPES]

# ---------------------------------------------------------------------------
# Warm palette (same as node_detail_panel)
# ---------------------------------------------------------------------------
_BG_DRAWER = "#F8F6ED"
_TITLE_COLOR = "#5C5A3E"
_LABEL_COLOR = "#6F6A42"
_MUTED_COLOR = "#7C806E"
_SUGGESTION_BG = "#FFFDF7"
_SECTION_BG = "transparent"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _section_card(title: str) -> tuple[QFrame, QVBoxLayout]:
    """Return a (frame, layout) styled as a collapsible section."""
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame {{ background: {_SECTION_BG}; "
        f"border: 1px solid #D8D6C8; border-radius: 10px; padding: 2px; }}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(6)
    header = QLabel(title)
    header.setStyleSheet(
        f"color: {_TITLE_COLOR}; font-weight: 700; font-size: 14px; background: transparent;"
    )
    layout.addWidget(header)
    return frame, layout


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {_LABEL_COLOR}; font-size: 12px; background: transparent;")
    return lbl


def _muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {_MUTED_COLOR}; font-size: 11px; background: transparent;")
    lbl.setWordWrap(True)
    return lbl


def _styled_combo(items: list[str], placeholder: str = "") -> QComboBox:
    cb = QComboBox()
    cb.setEditable(False)
    if placeholder:
        cb.addItem(placeholder)
    for item in items:
        cb.addItem(item)
    cb.setStyleSheet(
        "QComboBox { border: 1px solid #C8C6B8; border-radius: 6px; "
        "padding: 4px 8px; background: white; min-height: 26px; }"
        "QComboBox::drop-down { border: none; }"
        "QComboBox QAbstractItemView { border: 1px solid #C8C6B8; selection-background-color: #E8E6D8; }"
    )
    return cb


def _styled_edit(placeholder: str = "", max_h: int = 0) -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setStyleSheet(
        "QLineEdit { border: 1px solid #C8C6B8; border-radius: 6px; "
        "padding: 4px 8px; background: white; }"
    )
    if max_h:
        le.setMaximumHeight(max_h)
    return le


def _styled_textedit(placeholder: str = "", max_h: int = 0) -> QTextEdit:
    te = QTextEdit()
    te.setPlaceholderText(placeholder)
    te.setStyleSheet(
        "QTextEdit { border: 1px solid #C8C6B8; border-radius: 6px; "
        "padding: 4px 8px; background: white; }"
    )
    if max_h:
        te.setMaximumHeight(max_h)
    return te


# ---------------------------------------------------------------------------
# AI Worker — same pattern as _NodeAIWorker in node_detail_panel
# ---------------------------------------------------------------------------

class _TreeAIWorker(QThread):
    """Runs AI tree text suggestion in a background thread."""
    finished = Signal(str, str)  # (text_or_empty, error_or_empty)

    def __init__(self, ai_controller, entity_id: str, prompt_hint: str, language: str = "es"):
        super().__init__()
        self.ai_controller = ai_controller
        self.entity_id = entity_id
        self.prompt_hint = prompt_hint
        self.language = language

    def run(self):
        try:
            if not hasattr(self.ai_controller, "node_text_suggestion"):
                self.finished.emit("", "IA no disponible en esta versión.")
                return
            result = self.ai_controller.node_text_suggestion(
                self.entity_id, prompt_hint=self.prompt_hint, language=self.language,
            )
            if isinstance(result, Error):
                self.finished.emit("", result.error)
                return
            value = result.value
            raw_text = getattr(value, "raw_text", "")
            if raw_text:
                self.finished.emit(raw_text, "")
            else:
                parts: list[str] = []
                for p in getattr(value, "previews", []) or []:
                    rt = p.get("raw_text", "")
                    if rt:
                        parts.append(rt)
                self.finished.emit(
                    "\n\n".join(parts) if parts else "Sin sugerencia disponible.", "",
                )
        except Exception as exc:
            self.finished.emit("", str(exc))


# ═══════════════════════════════════════════════════════════════════════
# TreeDetailPanel
# ═══════════════════════════════════════════════════════════════════════

class TreeDetailPanel(QWidget):
    """Immersive tree-container editor with semantic fields and AI."""

    membershipChanged = Signal(str, str)  # tree_id, member_id

    def __init__(
        self,
        ctx: AppContext,
        entity_controller,
        relation_controller,
        entity_id: str,
        on_saved: Callable[[], None] | None = None,
        ai_controller=None,
        parent: QWidget | None = None,
        *,
        is_new: bool = False,
        on_focus_tree: Callable[[str], None] | None = None,
        milestone_controller=None,
        on_open_milestones: Callable[[str, str, str], None] | None = None,
        on_suggest_milestone: Callable[[str, str], None] | None = None,
    ):
        super().__init__(parent)
        self.ctx = ctx
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.entity_id = entity_id
        self.on_saved = on_saved
        self.ai_controller = ai_controller
        self.on_focus_tree = on_focus_tree
        self.milestone_controller = milestone_controller
        self.on_open_milestones = on_open_milestones
        self.on_suggest_milestone = on_suggest_milestone
        self._ai_worker: _TreeAIWorker | None = None
        self._tree_meta = TreeMeta()
        self._is_new = is_new

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setStyleSheet(f"background: {_BG_DRAWER};")

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)  # UX23: ritmo del scaffold
        root.setSpacing(SPACE_MD)

        # -- Header --
        self.header_label = QLabel("Rama")
        self.header_label.setStyleSheet(
            f"color: {_TITLE_COLOR}; font-weight: 700; font-size: 16px; background: transparent;"
        )
        root.addWidget(self.header_label)
        # BETA1-F04: "Enfocar rama" fuera del panel editorial (doble click
        # en el grafo / menú contextual cubren la navegación).

        # ═══ 1. IDENTIDAD ═══ (BETA1-F05: plana, idéntica al panel de hoja)
        id_card = QWidget()
        id_layout = QVBoxLayout(id_card)
        id_layout.setContentsMargins(0, 0, 0, 0)
        id_layout.setSpacing(6)
        form = QFormLayout()
        form.setSpacing(6)

        # BETA1-F05 layout exacto: NOMBRE + TIPO + ANILLO en UNA fila fluida.
        first_row = QHBoxLayout()
        first_row.setSpacing(8)
        self.name_edit = _styled_edit("Nombre de la rama...")
        first_row.addWidget(self.name_edit, 3)
        self.tree_type_combo = _styled_combo(_RAMA_TYPE_VALUES, "— Sin tipo —")
        first_row.addWidget(self.tree_type_combo, 2)
        self.layer_combo = _styled_combo([], "— Sin anillo —")
        # Legacy ref kept for older code paths; never shown as UI. If this
        # empty label is made visible without a layout, Qt opens it as a
        # top-level blank popout.
        self.layer_label = QLabel("", self)
        self.layer_label.hide()
        first_row.addWidget(self.layer_combo, 2)
        self.color_edit = _styled_edit("#D0D8E0")
        self.color_edit.setVisible(False)  # editable desde el botón
        # UX28: el color de la rama lo decide el TIPO de entidad (paleta de Dendro),
        # no un selector manual. Objeto conservado para refs internas, fuera del layout.
        self.color_btn = QPushButton("")
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.setToolTip("Color de la rama")
        self.color_btn.setStyleSheet(
            "QPushButton { border: 1px solid #C8C6B8; border-radius: 14px; background: #D0D8E0; }"
        )
        self.color_btn.clicked.connect(self._pick_color)
        self.color_btn.setVisible(False)
        form.addRow(first_row)

        # BETA1-UX2C: el lapso de vida (origen → fin) se EDITA estirando el nodo
        # en la Cronología; aquí solo se MUESTRA (solo lectura), derivado de
        # birth/death y de las eras efectivas.
        _time_label_ss = f"color: {_MUTED_COLOR}; background: transparent; font-size: 12px;"
        self.lifespan_label = QLabel("")
        self.lifespan_label.setWordWrap(True)
        self.lifespan_label.setStyleSheet(_time_label_ss)
        self.lifespan_label.setToolTip(
            "Define el origen y el fin estirando el nodo en la vista Cronología."
        )
        form.addRow(self.lifespan_label)

        # Descripción breve: se monta tras la imagen (orden F05)
        self.brief_edit = _styled_edit("Descripción breve...")

        id_layout.addLayout(form)
        root.addWidget(id_card)

        # BETA1-F04: imagen opcional de la rama (persistencia mínima en
        # custom_metadata; gestión avanzada de assets = deuda F)
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

        # BETA1-F05: viñetas protagonistas — misma estética que la hoja
        _card_ss = (
            "QTextEdit, QLineEdit { background: #FFFDF7; border: 1px solid #E7E3D4; "
            "border-radius: 12px; padding: 10px; font-size: 13px; color: #3F3D2E; } "
            "QTextEdit:focus, QLineEdit:focus { border: 1px solid #C9C0A0; background: #FFFFFF; }"
        )
        self.brief_edit.setStyleSheet(_card_ss)
        root.addWidget(self.brief_edit)

        # BETA1-F04: el CUERPO domina el panel (contenedor narrativo)
        body_header = QLabel("Cuerpo")
        body_header.setStyleSheet(f"color: {_TITLE_COLOR}; font-weight: 600; background: transparent;")
        root.addWidget(body_header)
        self.extended_edit = _styled_textedit("Cuerpo / descripción extendida...", 150)
        self.extended_edit.setMaximumHeight(16777215)  # sin tope
        self.extended_edit.setMinimumHeight(260)
        self.extended_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.extended_edit.setStyleSheet(_card_ss)
        root.addWidget(self.extended_edit, 1)

        # ═══ 2. FUNCION NARRATIVA ═══
        fn_card, fn_layout = _section_card("Función narrativa")
        fn_form = QFormLayout()
        fn_form.setSpacing(6)

        self.role_combo = _styled_combo(NARRATIVE_ROLES, "— Sin rol —")
        fn_form.addRow("Rol narrativo", self.role_combo)

        self.importance_combo = _styled_combo(
            [e.value for e in NarrativeImportance], ""
        )
        fn_form.addRow("Importancia", self.importance_combo)

        self.development_combo = _styled_combo(
            [e.value for e in DevelopmentLevel], ""
        )
        fn_form.addRow("Desarrollo", self.development_combo)

        fn_layout.addLayout(fn_form)
        # BETA1-F04: secundarios → submenú "Más opciones" (montado tras la IA)
        self.more_section = AdvancedSection("Más opciones")
        self.more_section.body_layout.addWidget(fn_card)

        # ═══ 3. CONTENIDO ═══
        ct_card, ct_layout = _section_card("Contenido")
        ct_form = QFormLayout()
        ct_form.setSpacing(4)

        self.members_list = QListWidget()
        self.members_list.setMaximumHeight(120)
        self.members_list.setStyleSheet(
            "QListWidget { border: 1px solid #C8C6B8; border-radius: 6px; "
            "background: white; font-size: 12px; }"
        )
        ct_form.addRow("Miembros", self.members_list)

        self.subtrees_list = QListWidget()
        self.subtrees_list.setMaximumHeight(80)
        self.subtrees_list.setStyleSheet(self.members_list.styleSheet())
        ct_form.addRow("Subárboles", self.subtrees_list)

        self.internal_rels_list = QListWidget()
        self.internal_rels_list.setMaximumHeight(100)
        self.internal_rels_list.setStyleSheet(self.members_list.styleSheet())
        ct_form.addRow("Rel. internas", self.internal_rels_list)

        self.external_rels_list = QListWidget()
        self.external_rels_list.setMaximumHeight(100)
        self.external_rels_list.setStyleSheet(self.members_list.styleSheet())
        ct_form.addRow("Rel. externas", self.external_rels_list)

        ct_layout.addLayout(ct_form)
        self.more_section.body_layout.addWidget(ct_card)

        # ═══ 4. WORLDBUILDING + CANON ═══
        wc_card, wc_layout = _section_card("Worldbuilding y canon")
        wc_form = QFormLayout()
        wc_form.setSpacing(6)

        self.canon_combo = _styled_combo([e.value for e in CanonState], "")
        wc_form.addRow("Estado canon", self.canon_combo)

        # BETA1-H07: la visibilidad sale del producto visible.
        # El combo existe (la carga/guardado lo siguen usando) pero no se
        # monta en la UI.
        self.visibility_combo = _styled_combo([e.value for e in VisibilityState], "")

        self.certainty_combo = _styled_combo([e.value for e in CertaintyLevel], "")
        wc_form.addRow("Certeza", self.certainty_combo)
        # (El anillo vive ahora en la sección de identidad — BETA1-F04)

        wc_layout.addLayout(wc_form)

        # -- Reglas internas --
        wc_layout.addWidget(_label("Reglas internas"))
        self.rules_list = QListWidget()
        self.rules_list.setMaximumHeight(90)
        self.rules_list.setStyleSheet(self.members_list.styleSheet())
        rules_row = QHBoxLayout()
        self.rule_input = _styled_edit("Nueva regla...")
        add_rule_btn = QPushButton("+")
        add_rule_btn.setFixedSize(28, 28)
        add_rule_btn.clicked.connect(self._add_rule)
        del_rule_btn = QPushButton("−")
        del_rule_btn.setFixedSize(28, 28)
        del_rule_btn.clicked.connect(self._del_rule)
        rules_row.addWidget(self.rule_input, 1)
        rules_row.addWidget(add_rule_btn)
        rules_row.addWidget(del_rule_btn)
        wc_layout.addWidget(self.rules_list)
        wc_layout.addLayout(rules_row)

        # -- Preguntas abiertas --
        wc_layout.addWidget(_label("Preguntas abiertas"))
        self.questions_list = QListWidget()
        self.questions_list.setMaximumHeight(90)
        self.questions_list.setStyleSheet(self.members_list.styleSheet())
        q_row = QHBoxLayout()
        self.question_input = _styled_edit("Nueva pregunta...")
        add_q_btn = QPushButton("+")
        add_q_btn.setFixedSize(28, 28)
        add_q_btn.clicked.connect(self._add_question)
        del_q_btn = QPushButton("−")
        del_q_btn.setFixedSize(28, 28)
        del_q_btn.clicked.connect(self._del_question)
        q_row.addWidget(self.question_input, 1)
        q_row.addWidget(add_q_btn)
        q_row.addWidget(del_q_btn)
        wc_layout.addWidget(self.questions_list)
        wc_layout.addLayout(q_row)

        # BETA1-F05: notas privadas/exportables DESAPARECEN de la UI.
        # Widgets sin montar — carga/guardado intactos, sin pérdida de datos.
        self.private_notes_edit = _styled_textedit("Notas privadas...", 60)
        self.exportable_notes_edit = _styled_textedit("Notas exportables...", 60)

        self.more_section.body_layout.addWidget(wc_card)

        self.related_milestones_panel = None
        if self.milestone_controller is not None:
            self.related_milestones_panel = RelatedMilestonesPanel(
                milestone_controller=self.milestone_controller,
                target_kind="branch",
                target_id=self.entity_id,
                project_getter=self._project,
                entity_controller=self.entity_controller,
                relation_controller=self.relation_controller,
                on_open_chronology=self.on_open_milestones,
                on_suggest_milestone=self.on_suggest_milestone,
                on_created=self.on_saved,
            )
            self.more_section.body_layout.addWidget(self.related_milestones_panel)

        # -- B39: Create ring from branch button (hidden by default, wired in T02) --
        self.create_ring_btn = QPushButton("Crear anillo desde rama")
        self.create_ring_btn.setFixedHeight(32)
        self.create_ring_btn.setStyleSheet(
            "QPushButton { background: #6F6A42; color: #F8F5EA; border: none; "
            "border-radius: 8px; padding: 4px 12px; font-size: 12px; } "
            "QPushButton:hover { background: #504B2E; }"
        )
        self.create_ring_btn.setVisible(False)
        self.create_ring_btn.clicked.connect(self._create_ring_from_branch)
        self.more_section.body_layout.addWidget(self.create_ring_btn)

        # ═══ 5. IA ═══
        # R8: _section_card already renders the "IA" header — no second title.
        ai_card, ai_layout = _section_card("IA")

        # Action buttons row
        ai_btn_row = QHBoxLayout()
        ai_btn_row.setSpacing(4)

        self.ai_desc_btn = QPushButton("Descripción")
        self.ai_desc_btn.setFixedHeight(28)
        self.ai_desc_btn.setToolTip("Generar descripción de la rama con contexto de miembros")
        self.ai_desc_btn.clicked.connect(lambda: self._start_ai("description"))

        self.ai_members_btn = QPushButton("Miembros")
        self.ai_members_btn.setFixedHeight(28)
        self.ai_members_btn.setToolTip("Sugerir miembros faltantes")
        self.ai_members_btn.clicked.connect(lambda: self._start_ai("suggest_members"))

        self.ai_subtrees_btn = QPushButton("Subárboles")
        self.ai_subtrees_btn.setFixedHeight(28)
        self.ai_subtrees_btn.setToolTip("Sugerir subárboles")
        self.ai_subtrees_btn.clicked.connect(lambda: self._start_ai("suggest_subtrees"))

        self.ai_coherence_btn = QPushButton("Coherencia")
        self.ai_coherence_btn.setFixedHeight(28)
        self.ai_coherence_btn.setToolTip("Analizar coherencia interna de la rama")
        self.ai_coherence_btn.clicked.connect(lambda: self._start_ai("coherence"))

        self.ai_questions_btn = QPushButton("Preguntas")
        self.ai_questions_btn.setFixedHeight(28)
        self.ai_questions_btn.setToolTip("Generar preguntas abiertas sobre la rama")
        self.ai_questions_btn.clicked.connect(lambda: self._start_ai("questions"))

        for btn in (self.ai_desc_btn, self.ai_members_btn, self.ai_subtrees_btn,
                     self.ai_coherence_btn, self.ai_questions_btn):
            btn.setEnabled(self.ai_controller is not None)
            btn.setStyleSheet(
                "QPushButton { border: 1px solid #C8C6B8; border-radius: 6px; "
                "padding: 2px 8px; background: white; font-size: 11px; }"
                "QPushButton:hover { background: #F0EFE6; }"
                "QPushButton:disabled { color: #AAA; }"
            )
            ai_btn_row.addWidget(btn)
        ai_layout.addLayout(ai_btn_row)

        # BETA1-F00B: las acciones causales antiguas ya no viven en este
        # panel; se invocan desde command bar/menu contextual.

        # Custom prompt
        prompt_row = QHBoxLayout()
        self.ai_prompt_edit = _styled_edit("Instruccion adicional para la IA...")
        prompt_row.addWidget(self.ai_prompt_edit, 1)
        self.ai_run_btn = QPushButton("Consultar")
        self.ai_run_btn.setFixedHeight(28)
        self.ai_run_btn.setEnabled(self.ai_controller is not None)
        self.ai_run_btn.clicked.connect(lambda: self._start_ai("description"))
        prompt_row.addWidget(self.ai_run_btn)
        ai_layout.addLayout(prompt_row)

        for extra_ai_widget in (
            self.ai_desc_btn,
            self.ai_members_btn,
            self.ai_subtrees_btn,
            self.ai_coherence_btn,
            self.ai_questions_btn,
        ):
            extra_ai_widget.setVisible(False)

        if self.ai_controller is None:
            no_ai = _muted("IA contextual no disponible en esta sesión.")
            ai_layout.addWidget(no_ai)

        # Suggestion frame (hidden by default)
        self.suggestion_frame = QFrame()
        self.suggestion_frame.setObjectName("treeSuggestionFrame")
        self.suggestion_frame.setStyleSheet(
            f"QFrame#treeSuggestionFrame {{ background: {_SUGGESTION_BG}; "
            f"border: 1px dashed #B8B5A2; border-radius: 10px; padding: 6px; }}"
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
            "background: transparent; border: none; color: #4F4D38; font-style: italic;"
        )
        sug_layout.addWidget(self.suggestion_text)

        sug_actions = QHBoxLayout()
        sug_actions.setSpacing(6)
        self.accept_btn = QPushButton("Aceptar")
        self.accept_btn.setObjectName("primaryButton")
        self.accept_btn.setFixedHeight(28)
        self.accept_btn.clicked.connect(self._accept_suggestion)
        self.discard_btn = QPushButton("Descartar")
        self.discard_btn.setFixedHeight(28)
        self.discard_btn.clicked.connect(self._discard_suggestion)
        sug_actions.addStretch()
        sug_actions.addWidget(self.accept_btn)
        sug_actions.addWidget(self.discard_btn)
        sug_layout.addLayout(sug_actions)

        ai_layout.addWidget(self.suggestion_frame)
        root.addWidget(ai_card)
        # BETA1-F04: todo lo secundario, plegado bajo la IA
        root.addWidget(self.more_section)

        # -- Save / Cancel --
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.setFixedHeight(32)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        root.addLayout(btn_row)

        root.addStretch()

    # ------------------------------------------------------------------
    # Refresh — load entity data into UI
    # ------------------------------------------------------------------

    def _worldbuilding_active(self) -> bool:
        project = self._project()
        return bool(getattr(project, "worldbuilding_active", False)) if project is not None else False

    def _refresh_layer_combo(self, entity=None):
        current = str((getattr(entity, "layer_ids", []) or [""])[0] or "") if entity is not None else ""
        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        self.layer_combo.addItem("— Sin anillo —", "")
        project = self._project()
        for layer in sort_layers_by_causal_rank(list(getattr(project, "world_layers", []) or []) if project is not None else []):
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

    def refresh(self):
        _apptrace(f"UI tree set_entity entity_id={self.entity_id!r}")
        entity = self._entity_by_id(self.entity_id)
        if entity is None:
            self.header_label.setText("Rama no encontrada")
            return

        # Header
        self.header_label.setText(entity.name or "Rama sin nombre")

        # BETA1-F04: imagen asociada (si la hay)
        metadata = dict(getattr(entity, "custom_metadata", {}) or {})
        self._show_image(str(metadata.get("_image_path", "")))

        # Identidad
        self.name_edit.setText(entity.name)

        # BETA1-UX2C: lapso de vida solo-lectura (se edita en la cronología)
        self._refresh_lifespan_label(entity)

        self.brief_edit.setText(entity.brief_description)
        self.extended_edit.setPlainText(entity.extended_description)
        color = entity.custom_metadata.get("tree_color", "#D0D8E0")
        self.color_edit.setText(color)
        self.color_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid #C8C6B8; border-radius: 6px; "
            f"background: {color}; }}"
        )

        # TreeMeta
        self._tree_meta = TreeMeta.from_metadata(entity.custom_metadata)

        # BETA1-J08: preserva un tree_type heredado fuera del set curado
        # (p.ej. 'reino'/'familia' de proyectos antiguos) para no perder el dato.
        legacy_type = (self._tree_meta.tree_type or "").strip()
        if legacy_type and self.tree_type_combo.findText(legacy_type) < 0:
            self.tree_type_combo.addItem(legacy_type)
        self.tree_type_combo.setCurrentIndex(0)
        for i in range(self.tree_type_combo.count()):
            if self.tree_type_combo.itemText(i) == legacy_type:
                self.tree_type_combo.setCurrentIndex(i)
                break

        self.role_combo.setCurrentIndex(0)
        for i in range(self.role_combo.count()):
            if self.role_combo.itemText(i) == self._tree_meta.narrative_role:
                self.role_combo.setCurrentIndex(i)
                break

        # Función narrativa
        self._set_combo_value(self.importance_combo, _enum_value(entity.narrative_importance))
        self._set_combo_value(self.development_combo, _enum_value(entity.development_level))

        # Canon
        self._set_combo_value(self.canon_combo, _enum_value(entity.canon_state))
        self._set_combo_value(self.visibility_combo, _enum_value(entity.visibility_state))
        self._set_combo_value(self.certainty_combo, _enum_value(entity.certainty_level))
        self._refresh_layer_combo(entity)

        # Notes
        self.private_notes_edit.setPlainText(entity.private_notes)
        self.exportable_notes_edit.setPlainText(entity.exportable_notes)

        # Contenido
        self._refresh_members(entity)
        self._refresh_relations(entity)

        # Reglas / preguntas
        self.rules_list.clear()
        for rule in self._tree_meta.internal_rules:
            self.rules_list.addItem(rule)
        self.questions_list.clear()
        for q in self._tree_meta.open_questions:
            self.questions_list.addItem(q)

        # B39: Show "Crear anillo desde rama" if worldbuilding is active
        project = self._project()
        wb_on = getattr(project, "worldbuilding_active", False) if project else False
        self.create_ring_btn.setVisible(bool(wb_on))
        if self.related_milestones_panel is not None:
            self.related_milestones_panel.refresh()

    # ------------------------------------------------------------------
    # Members / Relations
    # ------------------------------------------------------------------

    def _refresh_members(self, entity):
        """Populate members list and subtrees list."""
        self.members_list.clear()
        self.subtrees_list.clear()
        if self.relation_controller is None:
            return
        rels_raw = self.relation_controller.list_all()
        rels = getattr(rels_raw, "value", rels_raw) or []
        for rel in rels:
            rtype = _enum_value(getattr(rel, "relation_type", ""), "")
            if rtype == "contiene" and getattr(rel, "source_id", "") == entity.id:
                target_id = getattr(rel, "target_id", "")
                target = self._entity_by_id(target_id)
                name = target.name if target else target_id
                if target and target.entity_type == EntityType.CONTENEDOR:
                    self.subtrees_list.addItem(name)
                else:
                    self.members_list.addItem(name)

    def _refresh_relations(self, entity):
        """Populate internal and external relations lists."""
        self.internal_rels_list.clear()
        self.external_rels_list.clear()
        if self.relation_controller is None:
            return

        # Get member IDs
        rels_raw = self.relation_controller.list_all()
        rels = getattr(rels_raw, "value", rels_raw) or []
        member_ids: set[str] = set()
        for rel in rels:
            rtype = _enum_value(getattr(rel, "relation_type", ""), "")
            if rtype == "contiene" and getattr(rel, "source_id", "") == entity.id:
                member_ids.add(getattr(rel, "target_id", ""))

        # All relations involving tree or its members
        all_rels_raw = self.relation_controller.list_all()
        all_rels = getattr(all_rels_raw, "value", all_rels_raw) or []
        for rel in all_rels:
            rtype = _enum_value(getattr(rel, "relation_type", ""), "")
            if not rtype:
                continue
            src = getattr(rel, "source_id", "")
            tgt = getattr(rel, "target_id", "")

            # Skip contiene (already shown as members)
            if rtype == "contiene":
                continue

            src_name = self._entity_name(src)
            tgt_name = self._entity_name(tgt)

            # Internal: both endpoints are members
            if src in member_ids and tgt in member_ids:
                self.internal_rels_list.addItem(f"{src_name} → {tgt_name}: {rtype}")
            # External: one endpoint is the tree, other is not a member
            elif src == entity.id or tgt == entity.id:
                other = tgt_name if src == entity.id else src_name
                direction = "→" if src == entity.id else "←"
                label = f"{entity.name} {direction} {other}: {rtype}"
                self.external_rels_list.addItem(label)

    def _entity_name(self, eid: str) -> str:
        e = self._entity_by_id(eid)
        return e.name if e else eid

    def _get_members(self) -> list[str]:
        """Return current member entity ids for this tree."""
        if self.relation_controller is None:
            return []
        rels_raw = self.relation_controller.list_all()
        rels = getattr(rels_raw, "value", rels_raw) or []
        members: list[str] = []
        for rel in rels:
            rtype = _enum_value(getattr(rel, "relation_type", ""), "")
            if rtype == "contiene" and getattr(rel, "source_id", "") == self.entity_id:
                target_id = getattr(rel, "target_id", "")
                if target_id:
                    members.append(target_id)
        return members

    def _save_name(self):
        """Contract helper: save only the visible tree name through the controller."""
        result = self.entity_controller.update(
            self.entity_id, {"name": self.name_edit.text().strip()}
        )
        if isinstance(result, Error) and self.ctx:
            self.ctx.log("error", f"Error guardando nombre de la rama: {result.error}")
            return
        if self.on_saved:
            self.on_saved()

    def _save_brief(self):
        """Contract helper: save only the visible tree brief description."""
        result = self.entity_controller.update(
            self.entity_id, {"brief_description": self.brief_edit.text().strip()}
        )
        if isinstance(result, Error) and self.ctx:
            self.ctx.log("error", f"Error guardando descripción de la rama: {result.error}")
            return
        if self.on_saved:
            self.on_saved()

    def _remove_member(self, member_id: str):
        """Remove an existing contains relation between this tree and a member."""
        if self.relation_controller is None:
            return
        rels_raw = self.relation_controller.list_all()
        rels = getattr(rels_raw, "value", rels_raw) or []
        for rel in rels:
            rtype = _enum_value(getattr(rel, "relation_type", ""), "")
            if (
                rtype == "contiene"
                and getattr(rel, "source_id", "") == self.entity_id
                and getattr(rel, "target_id", "") == member_id
            ):
                relation_id = getattr(rel, "id", "")
                if relation_id:
                    self.relation_controller.archive(relation_id)
                    self.membershipChanged.emit(self.entity_id, member_id)
                    self.refresh()
                return

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self):
        _apptrace(f"UI tree save entity_id={self.entity_id!r}")
        entity = self._entity_by_id(self.entity_id)
        if entity is None:
            return

        # Build updates
        tree_type = self._current_combo_text(self.tree_type_combo)
        narrative_role = self._current_combo_text(self.role_combo)

        # Update TreeMeta
        self._tree_meta.tree_type = tree_type
        self._tree_meta.narrative_role = narrative_role
        self._tree_meta.color = self.color_edit.text().strip()
        # Collect rules/questions from lists
        self._tree_meta.internal_rules = [
            self.rules_list.item(i).text() for i in range(self.rules_list.count())
        ]
        self._tree_meta.open_questions = [
            self.questions_list.item(i).text() for i in range(self.questions_list.count())
        ]

        merged_meta = self._tree_meta.merge_into(entity.custom_metadata)
        # Remove draft marker on save
        merged_meta.pop("_visual_draft", None)

        data: dict[str, Any] = {
            "name": self.name_edit.text().strip(),
            "brief_description": self.brief_edit.text().strip(),
            "extended_description": self.extended_edit.toPlainText().strip(),
            "custom_metadata": merged_meta,
            "narrative_importance": self._current_combo_text(self.importance_combo) or entity.narrative_importance.value,
            "development_level": self._current_combo_text(self.development_combo) or entity.development_level.value,
            "canon_state": self._current_combo_text(self.canon_combo) or entity.canon_state.value,
            "visibility_state": _enum_value(getattr(entity, "visibility_state", None), "visible_usuario"),
            "certainty_level": self._current_combo_text(self.certainty_combo) or entity.certainty_level.value,
            "layer_ids": ([self.layer_combo.currentData()] if self.layer_combo.currentData() else list(getattr(entity, "layer_ids", []) or [])) if self._worldbuilding_active() else list(getattr(entity, "layer_ids", []) or []),
            "private_notes": self.private_notes_edit.toPlainText().strip(),
            "exportable_notes": self.exportable_notes_edit.toPlainText().strip(),
            # BETA1-UX2C: el lapso se edita en la cronología; pass-through al
            # guardar para no borrarlo.
            "birth_year": getattr(entity, "birth_year", None),
            "death_year": getattr(entity, "death_year", None),
        }

        result = self.entity_controller.update(self.entity_id, data)
        if isinstance(result, Error):
            if self.ctx:
                self.ctx.log("error", f"Error guardando rama: {result.error}")
            return
        self._is_new = False
        if self.ctx:
            self.ctx.log("info", "Rama guardada")
        if self.on_saved:
            self.on_saved()
        self.refresh()

    def _cancel(self):
        self._discard_suggestion()
        if self._is_new:
            # Delete the draft entity
            if self.entity_controller is not None:
                self.entity_controller.delete(self.entity_id)
            self._is_new = False
            if self.on_saved:
                self.on_saved()
        else:
            self.refresh()
        parent = self.parent()
        while parent is not None:
            if type(parent).__name__ == "RightDrawer":
                parent.close()
                return
            parent = parent.parent()

    # ------------------------------------------------------------------
    # Color picker
    # ------------------------------------------------------------------

    # ── BETA1-F04: imagen opcional ───────────────────────────────────────

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar imagen", "", "Imágenes (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        result = self.entity_controller.get(self.entity_id)
        entity = getattr(result, "value", None)
        metadata = dict(getattr(entity, "custom_metadata", {}) or {}) if entity is not None else {}
        metadata["_image_path"] = path
        update = self.entity_controller.update(self.entity_id, {"custom_metadata": metadata})
        if isinstance(update, Error):
            self.ctx.log("error", f"No se pudo asociar la imagen: {update.error}")
            return
        self._show_image(path)
        self.ctx.log("info", "Imagen asociada a la rama")

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

    def _pick_color(self):
        current = QColor(self.color_edit.text().strip() or "#D0D8E0")
        color = QColorDialog.getColor(current, self, "Color de la rama")
        if color.isValid():
            self.color_edit.setText(color.name())
            self.color_btn.setStyleSheet(
                f"QPushButton {{ border: 1px solid #C8C6B8; border-radius: 6px; "
                f"background: {color.name()}; }}"
            )

    # ------------------------------------------------------------------
    # Rules / Questions lists
    # ------------------------------------------------------------------

    def _add_rule(self):
        text = self.rule_input.text().strip()
        if text:
            self.rules_list.addItem(text)
            self.rule_input.clear()

    def _del_rule(self):
        row = self.rules_list.currentRow()
        if row >= 0:
            self.rules_list.takeItem(row)

    def _add_question(self):
        text = self.question_input.text().strip()
        if text:
            self.questions_list.addItem(text)
            self.question_input.clear()

    def _del_question(self):
        row = self.questions_list.currentRow()
        if row >= 0:
            self.questions_list.takeItem(row)

    # ------------------------------------------------------------------
    # IA actions
    # ------------------------------------------------------------------

    def _get_members_text(self) -> str:
        """Return comma-separated member names for AI context."""
        names: list[str] = []
        for i in range(self.members_list.count()):
            names.append(self.members_list.item(i).text())
        return ", ".join(names) if names else "ninguno"

    def _get_rules_text(self) -> str:
        rules = [
            self.rules_list.item(i).text() for i in range(self.rules_list.count())
        ]
        return "; ".join(rules) if rules else "ninguna definida"

    def _start_ai(self, action: str):
        if self.ai_controller is None:
            self._show_ai_error("IA no disponible.")
            return
        if self._ai_worker is not None and self._ai_worker.isRunning():
            return

        entity = self._entity_by_id(self.entity_id)
        entity_name = entity.name if entity else "este árbol"
        layer_name = self.layer_combo.currentText() if self._worldbuilding_active() else "—"
        members = self._get_members_text()
        rules = self._get_rules_text()
        tree_type = self._current_combo_text(self.tree_type_combo) or "general"
        custom_hint = self.ai_prompt_edit.text().strip()

        prompts: dict[str, str] = {
            "description": (
                f"Genera una descripcion narrativa extendida para el árbol '{entity_name}' "
                f"(tipo: {tree_type}, capa causal: {layer_name}). Miembros: {members}. Reglas internas: {rules}. "
                f"El texto debe ser coherente con los miembros y las reglas. "
                f"{custom_hint}"
            ),
            "suggest_members": (
                f"Sugiere entidades que podrían pertenecer al árbol '{entity_name}' "
                f"(tipo: {tree_type}). Miembros actuales: {members}. "
                f"Indica nombre y rol propuesto para cada sugerencia. "
                f"{custom_hint}"
            ),
            "suggest_subtrees": (
                f"Sugiere sub-agrupaciones internas (subárboles) para '{entity_name}' "
                f"(tipo: {tree_type}). Miembros: {members}. "
                f"Indica nombre del subárbol y que miembros contendría. "
                f"{custom_hint}"
            ),
            "coherence": (
                f"Analiza la coherencia interna del arbol '{entity_name}' "
                f"(tipo: {tree_type}). Miembros: {members}. Reglas: {rules}. "
                f"Detecta contradicciones, miembros huerfanos, relaciones faltantes. "
                f"{custom_hint}"
            ),
            "questions": (
                f"Genera preguntas narrativas abiertas sobre el arbol '{entity_name}' "
                f"(tipo: {tree_type}). Miembros: {members}. Reglas: {rules}. "
                f"Las preguntas deben ayudar a desarrollar la historia. "
                f"{custom_hint}"
            ),
        }

        prompt_hint = prompts.get(action, prompts["description"])

        # Disable buttons while running
        for btn in (self.ai_desc_btn, self.ai_members_btn, self.ai_subtrees_btn,
                     self.ai_coherence_btn, self.ai_questions_btn,
                     self.ai_run_btn):
            btn.setEnabled(False)

        self._ai_worker = _TreeAIWorker(
            self.ai_controller,
            self.entity_id,
            prompt_hint,
            language=getattr(self.ctx, "language", "es"),
        )
        self._ai_worker.finished.connect(self._on_ai_finished)
        track_worker(self._ai_worker)  # sobrevive al panel; se para al cerrar la app
        self._ai_worker.start()

    @_qt_safe_slot
    def _on_ai_finished(self, text: str, error: str):
        # Re-enable buttons
        has_ai = self.ai_controller is not None
        for btn in (self.ai_desc_btn, self.ai_members_btn, self.ai_subtrees_btn,
                     self.ai_coherence_btn, self.ai_questions_btn,
                     self.ai_run_btn):
            btn.setEnabled(has_ai)

        if error:
            self._show_ai_error(error)
            return
        if not text:
            self._show_ai_error("La IA no devolvio texto.")
            return
        self.suggestion_text.setPlainText(text)
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(True)

    def _show_ai_error(self, message: str):
        self.suggestion_text.setPlainText(f"Error IA: {message}")
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(False)
        if self.ctx:
            self.ctx.log("warning", f"IA rama: {message}")

    def _accept_suggestion(self):
        text = self.suggestion_text.toPlainText().strip()
        if text:
            current = self.extended_edit.toPlainText().strip()
            if current:
                self.extended_edit.setPlainText(current + "\n\n" + text)
            else:
                self.extended_edit.setPlainText(text)
        self._discard_suggestion()

    def _discard_suggestion(self):
        self.suggestion_frame.setVisible(False)
        self.suggestion_text.clear()

    # ------------------------------------------------------------------
    # Combo helpers
    # ------------------------------------------------------------------

    def _current_combo_text(self, combo: QComboBox) -> str:
        """Return current text, or empty string if placeholder is selected."""
        idx = combo.currentIndex()
        if idx <= 0:
            return ""
        return combo.currentText()

    def _set_combo_value(self, combo: QComboBox, value: str):
        """Set combo to the item matching *value*, if present."""
        for i in range(combo.count()):
            if combo.itemText(i) == value:
                combo.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------
    # B39: Create ring from branch
    # ------------------------------------------------------------------

    def _create_ring_from_branch(self):
        """Create a new anillo (WorldLayer) based on this branch."""
        entity = self._entity_by_id(self.entity_id)
        if entity is None:
            return
        pc = getattr(self.ctx, "project_controller", None)
        if pc is None:
            return
        layer_service = getattr(pc, "ls", None)
        if layer_service is None:
            return
        from packages.domain.result import Error
        name = getattr(entity, "name", "Nuevo anillo") or "Nuevo anillo"
        desc = getattr(entity, "brief_description", "") or ""
        result = layer_service.create_ring_from_branch(name=name, description=desc)
        if isinstance(result, Error):
            self.ctx.log("error", f"Error creando anillo: {result.error}")
            return
        self.ctx.log("info", f"Anillo creado desde rama: {name}")
        # Refresh workspace to show the new ring
        workspace = getattr(self.ctx, "workspace", None)
        if workspace is not None:
            workspace.refresh()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    # BETA1-UX2C: lapso de vida (solo lectura) -------------------------

    def _era_name_for_year(self, year) -> str:
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
        birth = getattr(entity, "birth_year", None)
        death = getattr(entity, "death_year", None)
        if birth is None:
            self.lifespan_label.setText("Lapso de vida: sin definir · estíralo en la Cronología")
            return

        def part(year: int) -> str:
            era = self._era_name_for_year(year)
            return f"año {int(year)}" + (f" · {era}" if era else "")

        if death is None:
            self.lifespan_label.setText(f"Lapso de vida:  origen {part(birth)}  →  presente")
        else:
            self.lifespan_label.setText(
                f"Lapso de vida:  origen {part(birth)}  →  fin {part(death)}"
            )

    def _entity_by_id(self, eid: str):
        proj = self._project()
        if not proj:
            return None
        for e in proj.entities:
            if e.id == eid:
                return e
        return None
