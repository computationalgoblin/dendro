"""Relation detail panel — immersive relation editor for B31-CREATION-T02.

RightDrawer content opened from the graph when an edge is selected or a new
relation is created via drag-to-relate.  Reads and updates relations through
the UI controller.  Normal mode shows a warm, minimal form with type/direction,
editable fields, and non-blocking AI autocomplete.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
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
from hosts.DesktopHostPySide.widgets.mention_support import attach_mention_support
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_safe_slot, track_worker
from packages.application.structured_reference_service import (
    StructuredReferenceService,
    build_known_targets,
)
from packages.domain.narrative_memory import MemoryTargetKind
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.widgets.design_system import (
    FONT_SERIF,
    GOLD,
    INK,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    INPUT_BG,
    LINE,
    LINE_STRONG,
    RELATION_KIND_PALETTE,
    SPACE_LG,
    SPACE_MD,
    SURFACE_HI,
    AdvancedSection,
    Badge,
    enum_human,
    human_ref,
)
from hosts.DesktopHostPySide.widgets.related_milestones_panel import RelatedMilestonesPanel
from hosts.DesktopHostPySide.widgets.rigor_section import RigorSection
from packages.domain.entity_taxonomy import OFFERED_RELATION_TYPES
from packages.domain.relation import RelationType
from packages.domain.result import Error

# ---------------------------------------------------------------------------
# BETA2-FOCO-20 (Editorial sereno): tokens del design system (espejo del
# node_detail_panel — antes hexes cálidos duplicados).
# ---------------------------------------------------------------------------
_BG_DRAWER = SURFACE_HI
_TITLE_COLOR = INK_STRONG
_LABEL_COLOR = INK_SOFT
_MUTED_COLOR = INK_MUTED
_SUGGESTION_BG = INPUT_BG

# UX21: paleta cálida de relaciones centralizada (antes este mapa estaba drifteado
# a azules/púrpuras fríos pese a "mirrors graph_canvas"). Ahora coincide con el arco.
_EDGE_COLORS: dict[str, str] = RELATION_KIND_PALETTE

_DIRECTION_ICONS = {
    "unidireccional": "→",
    "bidireccional": "↔",
}


def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _default_color_for_type(relation_type_str: str) -> str:
    return _EDGE_COLORS.get((relation_type_str or "").lower(), "#9A8E72")  # UX21: neutro cálido


def _custom_relation_label(relation) -> str:
    meta = dict(getattr(relation, "custom_metadata", {}) or {})
    return str(meta.get("custom_relation_label") or "").strip()


def _slug_relation_label(label: str) -> str:
    return "_".join((label or "").strip().lower().split())


def _safe_ai_error(message: str) -> str:
    raw = str(message or "Error IA desconocido.").strip()
    lower = raw.lower()
    if "traceback" in lower:
        raw = raw.splitlines()[-1] if raw.splitlines() else "Error IA."
    for token in ("api_key", "apikey", "authorization", "bearer ", "token"):
        if token in lower:
            return "Error IA: credenciales o conexión no válidas. Revisa Configuración > IA."
    if len(raw) > 220:
        raw = raw[:220].rstrip() + "…"
    return raw or "Error IA desconocido."


# ---------------------------------------------------------------------------
# Non-blocking AI worker for relation text suggestion
# ---------------------------------------------------------------------------

class _RelationAIWorker(QThread):
    """Runs AI relation text suggestion in a background thread."""

    finished = Signal(str, str)  # (text_or_empty, error_or_empty)

    def __init__(
        self,
        ai_controller,
        relation_id: str,
        prompt_hint: str,
        language: str = "es",
    ):
        super().__init__()
        self.ai_controller = ai_controller
        self.relation_id = relation_id
        self.prompt_hint = prompt_hint
        self.language = language

    def run(self):
        try:
            if not hasattr(self.ai_controller, "relation_text_suggestion"):
                self.finished.emit("", "La acción IA de texto de relación no está disponible.")
                return
            result = self.ai_controller.relation_text_suggestion(
                self.relation_id, prompt_hint=self.prompt_hint, language=self.language
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
                self.finished.emit("\n\n".join(parts) if parts else "Sin sugerencia disponible.", "")
        except Exception as exc:
            self.finished.emit("", str(exc))


# ---------------------------------------------------------------------------
# Refine AI system prompt
# ---------------------------------------------------------------------------

_REFINE_RELATION_SYSTEM_PROMPT_ES = (
    "Eres un asistente de escritura integrado en Dendro. El usuario ha seleccionado "
    "un fragmento de una sugerencia anterior para una relación narrativa y quiere que "
    "lo modifiques. Devuelve ÚNICAMENTE el fragmento reescrito que reemplazará al "
    "seleccionado. No repitas el resto del texto. No añadas explicaciones. "
    "Respeta el tono, género, realismo y estilo del texto original. Responde en español."
)


class _RelationRefineWorker(QThread):
    """Runs a refine-AI action for relation text in background."""

    finished = Signal(str, str)

    def __init__(self, ai_controller, full_text: str, selected_text: str,
                 user_instruction: str, language: str = "es"):
        super().__init__()
        self.ai_controller = ai_controller
        self.full_text = full_text
        self.selected_text = selected_text
        self.user_instruction = user_instruction
        self.language = language

    def run(self):
        try:
            system = _REFINE_RELATION_SYSTEM_PROMPT_ES
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
# RelationDetailPanel
# ---------------------------------------------------------------------------

class RelationDetailPanel(QWidget):
    """Contextual relation editor shown inside the global RightDrawer."""

    def __init__(
        self,
        ctx: AppContext,
        relation_controller,
        relation_id: str,
        *,
        on_saved=None,
        ai_controller=None,
        entity_controller=None,
        milestone_controller=None,
        is_new: bool = False,
        on_focus_neighborhood=None,
        on_open_milestones=None,
        on_suggest_milestone=None,
    ):
        super().__init__()
        self.ctx = ctx
        self.relation_controller = relation_controller
        self.relation_id = relation_id
        self.on_saved = on_saved
        self.ai_controller = ai_controller
        self.entity_controller = entity_controller
        self.milestone_controller = milestone_controller
        self.on_focus_neighborhood = on_focus_neighborhood
        self.on_open_milestones = on_open_milestones
        self.on_suggest_milestone = on_suggest_milestone
        self.is_new = is_new
        self._relation = None
        self._current_color: str = ""
        self._ai_worker = None
        self._refreshing: bool = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(800)
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
        self.title = QLabel("Relación")
        self.title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {_TITLE_COLOR}; "
            f"font-family: Georgia, 'Courier New', serif; background: transparent;"
        )
        self.title.setWordWrap(True)
        head.addWidget(self.title, 1)
        self.type_badge = Badge("Relación", "info")
        head.addWidget(self.type_badge)
        root.addLayout(head)
        # BETA1-F04: "Enfocar vecindad" fuera del panel editorial.

        # -- Direction summary --
        self.summary = QLabel("")
        self.summary.setObjectName("mutedLabel")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
        root.addWidget(self.summary)

        # -- Source / Target box --
        self.ends_box = QGroupBox("Extremos")
        self.ends_box.setStyleSheet(
            f"QGroupBox {{ color: {_LABEL_COLOR}; font-weight: 600; "
            f"border: 1px solid #D8D6C8; border-radius: 10px; "
            f"margin-top: 8px; padding-top: 14px; background: transparent; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )
        ends_layout = QVBoxLayout(self.ends_box)
        ends_layout.setSpacing(2)
        self.source_label = QLabel("Origen: —")
        self.target_label = QLabel("Destino: —")
        for w in (self.source_label, self.target_label):
            w.setObjectName("mutedLabel")
            w.setWordWrap(True)
            w.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
            ends_layout.addWidget(w)
        root.addWidget(self.ends_box)

        # -- Form card --
        form_card = QFrame()
        form_card.setObjectName("formCard")
        form_card.setStyleSheet(
            f"QFrame#formCard {{ background: {_BG_DRAWER}; border: none; }}"
        )
        form = QFormLayout(form_card)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(8)
        form.labelAlignment = 0x0002  # AlignRight
        _label_ss = f"color: {_LABEL_COLOR}; background: transparent; font-weight: 600;"

        # BETA1-F05 layout exacto: TIPO + color en una fila fluida (la
        # identidad de la relación son sus extremos, ya resumidos arriba).
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        self.type_combo.lineEdit().setPlaceholderText("Tipo personalizado de relación")
        self.type_combo.addItem("Relación personalizada", "")
        project = self._project()
        for custom in list(getattr(project, "custom_relation_types", []) or []) if project is not None else []:
            if getattr(custom, "is_active", True):
                self.type_combo.addItem(str(getattr(custom, "name", "")), f"custom:{getattr(custom, 'id', '')}")
        # BETA1-J08: solo se ofrece el núcleo de relaciones (la familia de
        # conocimiento se conserva en el enum pero no se ofrece).
        for item in OFFERED_RELATION_TYPES:
            self.type_combo.addItem(enum_human(item.value), item.value)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo, 1)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.setToolTip("Color de la arista")
        self.color_btn.clicked.connect(self._pick_color)
        type_row.addWidget(self.color_btn)
        form.addRow(type_row)

        # Dirección → submenú "Más opciones" (BETA1-F04); el resumen de
        # extremos ya comunica el sentido en lenguaje natural.
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Origen → destino", "source_to_target")
        self.direction_combo.addItem("Destino → origen", "target_to_source")
        self.direction_combo.addItem("Bidireccional", "bidireccional")

        # Descripción breve: tras la imagen (orden F05) — creada aquí,
        # montada más abajo.
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Descripción breve…")
        # BETA2-MEM-03: @menciones estructuradas en la descripción de la relación.
        self._mention_supports = {}
        try:
            self._mention_supports["description"] = attach_mention_support(
                self.description_edit, self._mention_targets_provider()
            )
        except Exception:  # noqa: BLE001 — las @menciones nunca deben romper el editor
            self._mention_supports = {}

        # BETA2-FOCO-16 (canon total): el estado canon ya no se edita en el
        # panel — todo es canon salvo relación fantasma (conversión explícita).

        root.addWidget(form_card)

        # BETA1-F05: imagen opcional (uniforme con hoja/rama; persistencia
        # protegida — si el dominio de relaciones no admite metadata, deuda)
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

        # FOCO-20 (Editorial sereno): serif y foco dorado, misma superficie
        # que la hoja — aquí también se escribe largo.
        _card_ss = (
            f"QTextEdit {{ background: {INPUT_BG}; border: 1px solid {LINE}; "
            f"border-radius: 12px; padding: 12px; font-size: 14px; color: {INK}; "
            f"font-family: {FONT_SERIF}; }} "
            f"QTextEdit:hover {{ border-color: {LINE_STRONG}; }} "
            f"QTextEdit:focus {{ border: 2px solid {GOLD}; background: #FFFFFF; padding: 11px; }}"
        )
        self.description_edit.setStyleSheet(_card_ss)
        root.addWidget(self.description_edit)

        # BETA1-F04: el CUERPO de la relación domina el panel
        body_header = QLabel("Cuerpo")
        body_header.setStyleSheet(_label_ss)
        root.addWidget(body_header)
        self.body_edit = QTextEdit()
        self.body_edit.setMinimumHeight(240)
        self.body_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.body_edit.setStyleSheet(_card_ss)
        root.addWidget(self.body_edit, 1)

        # Notas → submenú "Más opciones"
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(70)

        self.related_milestones_panel = None
        if self.milestone_controller is not None:
            self.related_milestones_panel = RelatedMilestonesPanel(
                milestone_controller=self.milestone_controller,
                target_kind="relation",
                target_id=self.relation_id,
                project_getter=self._project,
                entity_controller=self.entity_controller,
                relation_controller=self.relation_controller,
                on_open_chronology=self.on_open_milestones,
                on_suggest_milestone=self.on_suggest_milestone,
                on_created=self.on_saved,
            )
            # BETA1-F04: hitos relacionados → submenú "Más opciones"

        # BETA2-UX-03: los campos "avanzados" ocultos (combo de visibilidad) eran
        # widgets muertos sin montar. Eliminados; visibility_state se preserva por
        # pass-through en el guardado.

        # -- AI suggestion section --
        ai_card = QFrame()
        ai_card.setObjectName("aiCard")
        ai_card.setStyleSheet(f"QFrame#aiCard {{ background: transparent; border: none; }}")
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
        self.ai_prompt_edit.setPlaceholderText("Ej: Haz la relación más tensa, añade conflicto…")
        prompt_row.addWidget(self.ai_prompt_edit, 1)
        self.ai_generate_btn = QPushButton("Mejorar / desarrollar relación")
        self.ai_generate_btn.setEnabled(self.ai_controller is not None)
        self.ai_generate_btn.setText("Consultar")
        self.ai_generate_btn.clicked.connect(self._start_ai_suggestion)
        prompt_row.addWidget(self.ai_generate_btn)
        ai_layout.addLayout(prompt_row)

        # BETA2-UX-03: botón «Analizar coherencia» estaba oculto — eliminado.

        # Suggestion display area
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
        self.refine_btn.setVisible(True)
        self.refine_btn.setEnabled(False)
        sug_actions.addStretch()
        sug_actions.addWidget(self.refine_btn)
        sug_actions.addWidget(self.accept_btn)
        sug_actions.addWidget(self.discard_btn)
        sug_layout.addLayout(sug_actions)

        ai_layout.addWidget(self.suggestion_frame)
        # BETA2-WIKI-10: la superficie de IA del panel de relación queda RETIRADA de
        # la UI (recorte de IA a Regar+Sugerencias+wiki+cronología). El bloque solo se
        # monta si hay ai_controller; hoy es siempre None → no se muestra nada de IA.
        # Si no se monta, el card queda como huérfano oculto propiedad del panel (sin
        # dejar referencias colgantes a los widgets internos).
        if self.ai_controller is not None:
            root.addWidget(ai_card)
        else:
            ai_card.setParent(self)
            ai_card.hide()

        # BETA1-F04: submenú "Más opciones" — dirección, estado, notas,
        # hitos y datos técnicos (estos, además, solo en modo avanzado).
        self.more_section = AdvancedSection("Más opciones")
        more_form = QFormLayout()
        more_form.setSpacing(6)
        more_dir_label = QLabel("Dirección:")
        more_dir_label.setStyleSheet(_label_ss)
        more_form.addRow(more_dir_label, self.direction_combo)

        # BETA1-G06: intervalo temporal de la relación
        more_temp_label = QLabel("Temporal:")
        more_temp_label.setStyleSheet(_label_ss)
        _temp_row = QHBoxLayout()
        _temp_row.setSpacing(6)
        _nace_lbl = QLabel("Nace")
        _nace_lbl.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent; font-size: 12px;")
        self.birth_year_edit = QLineEdit()
        self.birth_year_edit.setPlaceholderText("—")
        self.birth_year_edit.setMaximumWidth(72)
        self.birth_year_edit.setToolTip("Año diegético en que nace la relación (puede ser negativo)")
        _termina_lbl = QLabel("Termina")
        _termina_lbl.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent; font-size: 12px;")
        self.death_year_edit = QLineEdit()
        self.death_year_edit.setPlaceholderText("—")
        self.death_year_edit.setMaximumWidth(72)
        self.death_year_edit.setToolTip("Año en que termina la relación; vacío = activa indefinidamente")
        _temp_row.addWidget(_nace_lbl)
        _temp_row.addWidget(self.birth_year_edit)
        _temp_row.addWidget(_termina_lbl)
        _temp_row.addWidget(self.death_year_edit)
        _temp_row.addStretch()
        _temp_widget = QWidget()
        _temp_widget.setLayout(_temp_row)
        more_form.addRow(more_temp_label, _temp_widget)

        more_notes_label = QLabel("Notas:")
        more_notes_label.setStyleSheet(_label_ss)
        more_form.addRow(more_notes_label, self.notes_edit)
        self.more_section.body_layout.addLayout(more_form)
        if self.related_milestones_panel is not None:
            self.more_section.body_layout.addWidget(self.related_milestones_panel)
        root.addWidget(self.more_section)

        # BETA2-FIX-11 (fase B1): certeza de la relación. El campo
        # existía en el dominio y el SERVICIO lo tiraba en silencio (ya no). Aquí
        # solo la certeza: el intervalo temporal de la relación se sigue editando
        # arriba en años enteros, que son su espejo autoritativo.
        self.rigor = RigorSection(
            con_datacion=False,
            titulo="Rigor: certeza",
            expandida=bool(getattr(self.ctx, "advanced_mode", False)),
        )
        self.rigor.changed.connect(self._schedule_autosave)
        root.addWidget(self.rigor)

        # BETA2-UX-03: caja «Datos técnicos» (sin montar, dato-no-UI) eliminada.
        # BETA1-F05: datos técnicos FUERA del producto (widget sin montar;
        # _refresh los sigue escribiendo sin coste visual).

        # -- Actions --
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel)
        self.archive_btn = QPushButton("Archivar")
        self.archive_btn.clicked.connect(self.archive)
        self.archive_btn.setVisible(not self.is_new)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.save)
        actions.addWidget(self.cancel_btn)
        if not self.is_new:
            actions.addWidget(self.archive_btn)
        actions.addStretch()
        actions.addWidget(self.save_btn)
        root.addLayout(actions)
        root.addStretch()

        # Apply drawer background
        self.setStyleSheet(f"background: {_BG_DRAWER};")
        self.set_advanced_mode(self.ctx.advanced_mode)

    # ------------------------------------------------------------------
    # Colour helpers
    # ------------------------------------------------------------------

    def _update_color_swatch(self, hex_color: str):
        self._current_color = hex_color
        self.color_btn.setStyleSheet(
            f"QPushButton {{ background: {hex_color}; border: 2px solid #D8D6C8; "
            f"border-radius: 6px; }} "
            f"QPushButton:hover {{ border-color: #AAA579; }}"
        )
        self.color_btn.setToolTip(f"Color: {hex_color}")

    # ── BETA1-F05: imagen opcional (uniforme con hoja/rama) ─────────────

    def _pick_image(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar imagen", "", "Imágenes (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        result = self.relation_controller.get(self.relation_id)
        relation = getattr(result, "value", None)
        metadata = dict(getattr(relation, "custom_metadata", {}) or {}) if relation is not None else {}
        metadata["_image_path"] = path
        update = self.relation_controller.update(self.relation_id, {"custom_metadata": metadata})
        if isinstance(update, Error):
            # El dominio de relaciones puede no admitir metadata → deuda F
            self.ctx.log("warning", f"Imagen no persistida en la relación: {update.error}")
        self._show_image(path)

    def _show_image(self, path: str):
        from pathlib import Path as _Path
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt as _Qt
        if not path or not _Path(path).exists():
            self.image_preview.setVisible(False)
            self.image_btn.setText("Añadir imagen…")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_preview.setVisible(False)
            return
        self.image_preview.setPixmap(pixmap.scaledToHeight(150, _Qt.TransformationMode.SmoothTransformation))
        self.image_preview.setVisible(True)
        self.image_btn.setText("Cambiar imagen…")

    def _pick_color(self):
        """Cycle through relation palette colors without opening external dialogs."""
        palette = list(dict.fromkeys(_EDGE_COLORS.values()))
        if not palette:
            return
        try:
            idx = palette.index(self._current_color)
        except ValueError:
            idx = -1
        self._update_color_swatch(palette[(idx + 1) % len(palette)])
        self._schedule_autosave()

    def _on_type_changed(self, _index: int = -1):
        type_val = self.type_combo.currentData() or self.type_combo.currentText().strip().lower()
        if not self._relation:
            return
        meta = dict(getattr(self._relation, "custom_metadata", {}) or {})
        has_custom = bool(meta.get("_edge_color"))
        if not has_custom:
            self._update_color_swatch(_default_color_for_type(type_val))
        self._schedule_autosave()

    # ------------------------------------------------------------------
    # Auto-save (debounced)
    # ------------------------------------------------------------------

    def _connect_autosave_signals(self):
        self.type_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.direction_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.description_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.body_edit.textChanged.connect(self._schedule_autosave_if_active)

        self.notes_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.birth_year_edit.textChanged.connect(self._schedule_autosave)
        self.death_year_edit.textChanged.connect(self._schedule_autosave)

    def _schedule_autosave(self):
        if self._refreshing:
            return
        self._autosave_timer.start()

    def _schedule_autosave_if_active(self):
        self._schedule_autosave()

    def _autosave(self):
        if self._refreshing or self._relation is None or self.is_new:
            return
        self._do_save(refresh_after=False)

    # ------------------------------------------------------------------
    # AI suggestion (non-blocking)
    # ------------------------------------------------------------------

    def _build_ai_instruction(self, user_instruction: str) -> str:
        source_name = self.source_label.text().replace("Origen: ", "")
        target_name = self.target_label.text().replace("Destino: ", "")
        type_value = self.type_combo.currentData() or self.type_combo.currentText().strip() or "relación"
        direction = self.direction_combo.currentData() or "unidireccional"
        desc = self.description_edit.toPlainText().strip()
        body = self.body_edit.toPlainText().strip()
        notes = self.notes_edit.toPlainText().strip()
        instruction = (user_instruction or "").strip()
        return (
            f"Origen: {source_name}\n"
            f"Destino: {target_name}\n"
            f"Tipo de relación: {type_value}\n"
            f"Dirección: {direction}\n"
            f"Descripción actual:\n{desc or '—'}\n\n"
            f"Cuerpo actual:\n{body or '—'}\n\n"
            f"Notas:\n{notes or '—'}\n\n"
            f"Instrucción del usuario: {instruction or '—'}"
        )

    def _start_ai_suggestion(self):
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
        self.ai_generate_btn.setText("Generando sugerencia…")
        self.suggestion_text.setPlainText("Generando sugerencia…")
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(False)
        self.refine_btn.setEnabled(False)

        self._ai_worker = _RelationAIWorker(
            self.ai_controller,
            self.relation_id,
            prompt_hint,
            getattr(self.ctx, "language", "es"),
        )
        self._ai_worker.finished.connect(self._on_ai_finished)
        track_worker(self._ai_worker)  # sobrevive al panel; se para al cerrar la app
        self._ai_worker.start()

    def _show_ai_error(self, message: str):
        safe_message = _safe_ai_error(message)
        self.ai_generate_btn.setEnabled(self.ai_controller is not None)
        self.ai_generate_btn.setText("Consultar")
        self.refine_btn.setEnabled(False)
        self.suggestion_text.setPlainText(f"Error IA: {safe_message}")
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(False)
        if self.ctx is not None:
            self.ctx.log("warning", f"IA relación: {safe_message}")

    @_qt_safe_slot
    def _on_ai_finished(self, text: str, error: str):
        self.ai_generate_btn.setEnabled(True)
        self.ai_generate_btn.setText("Consultar")
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
        if self.ai_controller is None:
            self._show_ai_error("IA contextual no disponible.")
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
        self._ai_worker = _RelationRefineWorker(
            self.ai_controller,
            full_text=full_text,
            selected_text=selected,
            user_instruction=user_instruction,
            language=getattr(self.ctx, "language", "es"),
        )
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
        full = getattr(self, "_refine_full_text", "")
        start = getattr(self, "_refine_selection_start", 0)
        end = getattr(self, "_refine_selection_end", 0)
        if full and start != end:
            new_full = full[:start] + text + full[end:]
            self.suggestion_text.setPlainText(new_full)
        else:
            self.suggestion_text.setPlainText(text)
        self.suggestion_frame.setVisible(True)

    def _accept_suggestion(self):
        _apptrace(f"UI relation accept_suggestion relation_id={self.relation_id!r}")
        text = self.suggestion_text.toPlainText().strip()
        if text:
            current_body = self.body_edit.toPlainText().strip()
            # Relation AI suggestions are narrative text: keep short description stable and write/append to body.
            if not current_body:
                self.body_edit.setPlainText(text)
            else:
                self.body_edit.setPlainText(current_body + "\n\n" + text)
        self._discard_suggestion()

    def _discard_suggestion(self):
        _apptrace(f"UI relation discard_suggestion relation_id={self.relation_id!r}")
        self.suggestion_frame.setVisible(False)
        self.suggestion_text.clear()

    # ------------------------------------------------------------------
    # Coherence analysis
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def _cancel(self):
        _apptrace(f"UI relation cancel_edit relation_id={self.relation_id!r} is_new={self.is_new}")
        self._discard_suggestion()
        if self.is_new:
             # Cancel on new relation: remove the unsaved visual draft, then close drawer.
            if self.relation_controller is not None:
                result = self.relation_controller.delete(self.relation_id)
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
        else:
            self.refresh()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _entity_by_id(self, entity_id: str):
        project = self._project()
        if project is None:
            return None
        for entity in getattr(project, "entities", []) or []:
            if getattr(entity, "id", None) == entity_id:
                return entity
        return None

    def _human_entity_ref(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return "Elemento no encontrado"
        return human_ref(
            getattr(entity, "name", "Sin nombre"),
            enum_human(_enum_value(getattr(entity, "entity_type", None), "entidad")),
        )

    def _set_combo_value(self, combo: QComboBox, value: str):
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findText(enum_human(value))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setEditText(str(value))

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        _apptrace(f"UI relation set_relation relation_id={self.relation_id!r}")
        self._refreshing = True
        try:
            result = self.relation_controller.get(self.relation_id)
            if isinstance(result, Error):
                self.title.setText("Relación no encontrada")
                self.summary.setText(result.error)
                self.save_btn.setEnabled(False)
                self.archive_btn.setEnabled(False)
                return
            relation = result.value
            self._relation = relation
            custom_label = _custom_relation_label(relation)
            kind = custom_label or _enum_value(getattr(relation, "relation_type", None), "relación")
            direction = _enum_value(getattr(relation, "direction", None), "unidireccional")
            dir_icon = _DIRECTION_ICONS.get(direction, "→")
            self.title.setText(kind if custom_label else enum_human(kind))
            self.type_badge.setText(kind if custom_label else enum_human(kind))
            source_ref = self._human_entity_ref(getattr(relation, "source_id", ""))
            target_ref = self._human_entity_ref(getattr(relation, "target_id", ""))
            self.summary.setText(f"{source_ref} {dir_icon} {target_ref}")
            self.source_label.setText(f"Origen: {source_ref}")
            self.target_label.setText(f"Destino: {target_ref}")
            if custom_label:
                self.type_combo.setEditText(custom_label)
            else:
                self._set_combo_value(self.type_combo, kind)
            if direction == "bidireccional":
                self._set_combo_value(self.direction_combo, "bidireccional")
            else:
                self._set_combo_value(self.direction_combo, "source_to_target")
            self.description_edit.setPlainText(getattr(relation, "description", "") or "")
            meta = dict(getattr(relation, "custom_metadata", {}) or {})
            body_text = meta.get("_body", "")
            notes_text = meta.get("_notes", "")
            self.body_edit.setPlainText(body_text)
            self.notes_edit.setPlainText(notes_text)
            # BETA1-G06: temporal interval
            by = getattr(relation, "birth_year", None)
            dy = getattr(relation, "death_year", None)
            self.birth_year_edit.setText("" if by is None else str(by))
            self.death_year_edit.setText("" if dy is None else str(dy))
            # FIX-11 (B1): certeza de la relación.
            self.rigor.load(certeza=getattr(relation, "certainty_level", None))
            canon_val = _enum_value(getattr(relation, "canon_state", None), "")
            # BETA2-FOCO: una relación fantasma no se des-fantasma por autosave.
            # BETA2-FOCO-16 (canon total): el canon ya no se edita en el panel.
            self._is_ghost_relation = canon_val.lower() == "fantasma"

            # Color
            stored_color = meta.get("_edge_color")
            if stored_color:
                self._update_color_swatch(stored_color)
            else:
                self._update_color_swatch(_default_color_for_type(kind))

            if self.related_milestones_panel is not None:
                self.related_milestones_panel.refresh()
            self.set_advanced_mode(self.ctx.advanced_mode)
        finally:
            self._refreshing = False

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
        _apptrace(f"UI relation save relation_id={self.relation_id!r}")
        self._autosave_timer.stop()
        self._do_save(refresh_after=True)

    def _mention_targets_provider(self):
        def provider():
            ps = getattr(self.relation_controller, "ps", None)
            project = getattr(ps, "active_project", None)
            return build_known_targets(project) if project is not None else []

        return provider

    def _sync_structured_references(self, field_texts: dict) -> None:
        """Resuelve las @menciones de la relación a referencias estructuradas (MEM-03)."""
        ps = getattr(self.relation_controller, "ps", None)
        if ps is None or getattr(ps, "active_project", None) is None:
            return
        hints: dict[str, tuple[str, str]] = {}
        for ms in getattr(self, "_mention_supports", {}).values():
            hints.update(ms.hints())
        try:
            StructuredReferenceService(ps).sync_element_references(
                MemoryTargetKind.RELATION, self.relation_id, field_texts, hints=hints
            )
        except Exception:  # noqa: BLE001 — nunca romper el guardado por las @menciones
            pass

    def _do_save(self, *, refresh_after: bool = True):
        if self._relation is None:
            return
        type_data = self.type_combo.currentData()
        type_text = self.type_combo.currentText().strip()
        if type_text == "Relación personalizada":
            type_text = ""
        custom_relation_type_id = None
        custom_label = ""
        if isinstance(type_data, str) and type_data.startswith("custom:"):
            custom_relation_type_id = type_data.split(":", 1)[1]
            custom_label = type_text
            relation_type_value = "esta_relacionado_con"
        elif type_data:
            relation_type_value = type_data
        else:
            slug = _slug_relation_label(type_text)
            if slug and slug not in {item.value for item in RelationType}:
                custom_label = type_text
                relation_type_value = "esta_relacionado_con"
            else:
                relation_type_value = slug or "esta_relacionado_con"

        # BETA2-FOCO-16 (canon total): el panel NO emite canon_state.

        # Build metadata with color, body, notes
        meta = dict(getattr(self._relation, "custom_metadata", {}) or {})
        if custom_label:
            meta["custom_relation_label"] = custom_label
        else:
            meta.pop("custom_relation_label", None)
        if self._current_color:
            meta["_edge_color"] = self._current_color
        default_color = _default_color_for_type(relation_type_value)
        if meta.get("_edge_color") == default_color:
            meta.pop("_edge_color", None)

        body = self.body_edit.toPlainText().strip()
        if body:
            meta["_body"] = body
        else:
            meta.pop("_body", None)

        notes = self.notes_edit.toPlainText().strip()
        if notes:
            meta["_notes"] = notes
        else:
            meta.pop("_notes", None)

        meta.pop("_visual_draft", None)

        direction_choice = self.direction_combo.currentData() or "source_to_target"
        source_id = getattr(self._relation, "source_id", "")
        target_id = getattr(self._relation, "target_id", "")
        direction_value = "bidireccional" if direction_choice == "bidireccional" else "unidireccional"
        if direction_choice == "target_to_source":
            source_id, target_id = target_id, source_id

        # BETA1-G06: parse temporal fields (empty string → None = no constraint)
        def _parse_year(text: str) -> int | None:
            t = text.strip()
            if not t:
                return None
            try:
                return int(t)
            except ValueError:
                return None

        payload = {
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type_value,
            "direction": direction_value,
            "description": self.description_edit.toPlainText().strip(),
            "birth_year": _parse_year(self.birth_year_edit.text()),
            "death_year": _parse_year(self.death_year_edit.text()),
            "validity_conditions": [],
            "tags": [],
            # BETA2-UX-03: visibilidad preservada por pass-through (ya no editable).
            "visibility_state": _enum_value(getattr(self._relation, "visibility_state", None), "visible_usuario"),
            "custom_metadata": meta,
            "custom_relation_type_id": custom_relation_type_id,
            # FIX-11 (B1): el servicio ya no lo tira en silencio.
            "certainty_level": self.rigor.certeza(),
        }
        if getattr(self, "_is_ghost_relation", False):
            # BETA2-FOCO: el canon fantasma solo cambia en la conversión explícita.
            payload.pop("canon_state", None)
        result = self.relation_controller.update(self.relation_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        # BETA2-MEM-03: resolver @menciones de la descripción → refs estructuradas.
        if not getattr(self, "preview_patch", None):
            self._sync_structured_references(
                {"description": self.description_edit.toPlainText().strip()}
            )
        self.ctx.log("info", "Relación guardada")
        self.ctx.selected_relation_id = self.relation_id
        if self.is_new:
            self.is_new = False
            self.archive_btn.setVisible(True)
        if refresh_after:
            self.refresh()
        if self.on_saved is not None:
            self.on_saved()

    def archive(self):
        result = self.relation_controller.archive(self.relation_id)
        if isinstance(result, Error):
            self.ctx.notify(result.error, "error")
            return
        self.ctx.log("info", "Relación archivada")
        if self.on_saved is not None:
            self.on_saved()
        if self.ctx.drawer is not None:
            self.ctx.drawer.close()
