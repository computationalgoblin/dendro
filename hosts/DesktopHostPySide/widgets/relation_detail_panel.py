"""Relation detail panel — immersive relation editor for B31-CREATION-T02.

RightDrawer content opened from the graph when an edge is selected or a new
relation is created via drag-to-relate.  Reads and updates relations through
the UI controller.  Normal mode shows a warm, minimal form with type/direction,
editable fields, and non-blocking AI autocomplete.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import Badge, enum_human, human_ref
from packages.domain.entity import CanonState, VisibilityState
from packages.domain.relation import IntensityLevel, RelationType
from packages.domain.result import Error

# ---------------------------------------------------------------------------
# Warm palette constants (mirrors node_detail_panel)
# ---------------------------------------------------------------------------
_BG_DRAWER = "#F8F6ED"
_TITLE_COLOR = "#5C5A3E"
_LABEL_COLOR = "#6F6A42"
_MUTED_COLOR = "#7C806E"
_SUGGESTION_BG = "#FFFDF7"

# Simplified canon options for normal mode
_SIMPLE_CANON = ["borrador", "canonico"]

# Default edge colours per relation type (mirrors graph_canvas._EDGE_COLORS)
_EDGE_COLORS: dict[str, str] = {
    "pertenece_a": "#7C9BFF",
    "contiene": "#7EC8A5",
    "esta_ubicado_en": "#7EC8A5",
    "es_aliado_de": "#78B891",
    "es_enemigo_de": "#D46A6A",
    "faccion": "#D9908F",
    "busca": "#E0C46C",
    "protege": "#78B891",
    "oculta": "#9BB4C7",
    "sospecha": "#DCA35F",
    "esta_en_conflicto_con": "#D46A6A",
    "es_amigo_de": "#78B891",
    "es_familiar_de": "#C9A5FF",
    "ama_a": "#D9908F",
    "es_mentor_de": "#7C9BFF",
    "es_aliado_de": "#78B891",
    "es_rival_de": "#D46A6A",
    "depende_de": "#DCA35F",
    "esta_relacionado_con": "#A4AEC0",
    "gobierna": "#DCA35F",
    "sirve_a": "#7EC8A5",
    "conoce": "#9BB4C7",
    "traiciono": "#D46A6A",
    "controla": "#DCA35F",
    "posee": "#C9A5FF",
    "simboliza": "#9BB4C7",
}

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
    return _EDGE_COLORS.get((relation_type_str or "").lower(), "#A4AEC0")


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
        is_new: bool = False,
    ):
        super().__init__()
        self.ctx = ctx
        self.relation_controller = relation_controller
        self.relation_id = relation_id
        self.on_saved = on_saved
        self.ai_controller = ai_controller
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
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

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

        # Type + Color
        type_label = QLabel("Tipo:")
        type_label.setStyleSheet(_label_ss)
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        for item in RelationType:
            self.type_combo.addItem(enum_human(item.value), item.value)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo, 1)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.setToolTip("Color de la arista")
        self.color_btn.clicked.connect(self._pick_color)
        type_row.addWidget(self.color_btn)
        form.addRow(type_label, type_row)

        # Direction
        dir_label = QLabel("Dirección:")
        dir_label.setStyleSheet(_label_ss)
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Origen → destino", "source_to_target")
        self.direction_combo.addItem("Destino → origen", "target_to_source")
        self.direction_combo.addItem("Bidireccional", "bidireccional")
        form.addRow(dir_label, self.direction_combo)

        # Description (brief)
        desc_label = QLabel("Descripción:")
        desc_label.setStyleSheet(_label_ss)
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        form.addRow(desc_label, self.description_edit)

        # Cuerpo (extended body for the relation)
        body_label = QLabel("Cuerpo:")
        body_label.setStyleSheet(_label_ss)
        self.body_edit = QTextEdit()
        self.body_edit.setMaximumHeight(120)
        form.addRow(body_label, self.body_edit)

        note_label = QLabel("Notas:")
        note_label.setStyleSheet(_label_ss)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(70)
        form.addRow(note_label, self.notes_edit)

        # Estado (simplified canon)
        canon_label = QLabel("Estado:")
        canon_label.setStyleSheet(_label_ss)
        self.canon_combo = QComboBox()
        for val in _SIMPLE_CANON:
            self.canon_combo.addItem(enum_human(val), val)
        form.addRow(canon_label, self.canon_combo)

        root.addWidget(form_card)

        # -- Advanced fields (hidden in normal mode) --
        self._advanced_widgets: list[QWidget] = []

        adv_int_label = QLabel("Intensidad:")
        adv_int_label.setStyleSheet(_label_ss)
        self.intensity_combo = QComboBox()
        for item in IntensityLevel:
            self.intensity_combo.addItem(enum_human(item.value), item.value)
        form.addRow(adv_int_label, self.intensity_combo)
        self._advanced_widgets += [adv_int_label, self.intensity_combo]

        adv_temp_label = QLabel("Temporalidad:")
        adv_temp_label.setStyleSheet(_label_ss)
        self.temporality_edit = QTextEdit()
        self.temporality_edit.setMaximumHeight(60)
        form.addRow(adv_temp_label, self.temporality_edit)
        self._advanced_widgets += [adv_temp_label, self.temporality_edit]

        adv_caus_label = QLabel("Causalidad:")
        adv_caus_label.setStyleSheet(_label_ss)
        self.causality_edit = QTextEdit()
        self.causality_edit.setMaximumHeight(60)
        form.addRow(adv_caus_label, self.causality_edit)
        self._advanced_widgets += [adv_caus_label, self.causality_edit]

        adv_vis_label = QLabel("Visibilidad:")
        adv_vis_label.setStyleSheet(_label_ss)
        self.visibility_combo = QComboBox()
        for item in VisibilityState:
            self.visibility_combo.addItem(enum_human(item.value), item.value)
        form.addRow(adv_vis_label, self.visibility_combo)
        self._advanced_widgets += [adv_vis_label, self.visibility_combo]

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
        self.ai_generate_btn.clicked.connect(self._start_ai_suggestion)
        prompt_row.addWidget(self.ai_generate_btn)
        ai_layout.addLayout(prompt_row)

        if self.ai_controller is None:
            no_ai_label = QLabel("IA contextual no disponible en esta sesión.")
            no_ai_label.setObjectName("mutedLabel")
            no_ai_label.setStyleSheet(f"color: {_MUTED_COLOR}; background: transparent;")
            ai_layout.addWidget(no_ai_label)

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
        self.refine_btn.setVisible(False)
        self.refine_btn.setEnabled(False)
        sug_actions.addStretch()
        sug_actions.addWidget(self.refine_btn)
        sug_actions.addWidget(self.accept_btn)
        sug_actions.addWidget(self.discard_btn)
        sug_layout.addLayout(sug_actions)

        ai_layout.addWidget(self.suggestion_frame)
        root.addWidget(ai_card)

        # -- Technical box (advanced only) --
        self.technical_box = QGroupBox("Datos técnicos")
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
        root.addWidget(self.technical_box)

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
        self.canon_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.intensity_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.visibility_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.notes_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.temporality_edit.textChanged.connect(self._schedule_autosave_if_active)
        self.causality_edit.textChanged.connect(self._schedule_autosave_if_active)

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
        self._ai_worker.start()

    def _show_ai_error(self, message: str):
        safe_message = _safe_ai_error(message)
        self.ai_generate_btn.setEnabled(self.ai_controller is not None)
        self.ai_generate_btn.setText("Mejorar / desarrollar relación")
        self.refine_btn.setEnabled(False)
        self.suggestion_text.setPlainText(f"Error IA: {safe_message}")
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(False)
        if self.ctx is not None:
            self.ctx.log("warning", f"IA relación: {safe_message}")

    def _on_ai_finished(self, text: str, error: str):
        self.ai_generate_btn.setEnabled(True)
        self.ai_generate_btn.setText("Mejorar / desarrollar relación")
        if error:
            self._show_ai_error(error)
            return
        self.accept_btn.setEnabled(True)
        self.refine_btn.setEnabled(False)
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
        self._ai_worker.start()

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
        self.suggestion_frame.setVisible(False)
        self.suggestion_text.clear()

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def _cancel(self):
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
            return "Entidad no encontrada"
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
            kind = _enum_value(getattr(relation, "relation_type", None), "relación")
            direction = _enum_value(getattr(relation, "direction", None), "unidireccional")
            dir_icon = _DIRECTION_ICONS.get(direction, "→")
            self.title.setText(enum_human(kind))
            self.type_badge.setText(enum_human(kind))
            source_ref = self._human_entity_ref(getattr(relation, "source_id", ""))
            target_ref = self._human_entity_ref(getattr(relation, "target_id", ""))
            self.summary.setText(f"{source_ref} {dir_icon} {target_ref}")
            self.source_label.setText(f"Origen: {source_ref}")
            self.target_label.setText(f"Destino: {target_ref}")
            self._set_combo_value(self.type_combo, kind)
            if direction == "bidireccional":
                self._set_combo_value(self.direction_combo, "bidireccional")
            else:
                self._set_combo_value(self.direction_combo, "source_to_target")
            self._set_combo_value(self.intensity_combo, _enum_value(getattr(relation, "intensity", None), ""))
            self.description_edit.setPlainText(getattr(relation, "description", "") or "")
            # Body: store in custom_metadata._body or temporality field as proxy
            meta = dict(getattr(relation, "custom_metadata", {}) or {})
            body_text = meta.get("_body", "")
            notes_text = meta.get("_notes", "")
            self.body_edit.setPlainText(body_text)
            self.notes_edit.setPlainText(notes_text)
            self.temporality_edit.setPlainText(getattr(relation, "temporality", "") or "")
            self.causality_edit.setPlainText(getattr(relation, "causality", "") or "")
            canon_val = _enum_value(getattr(relation, "canon_state", None), "")
            if "canon" in canon_val.lower():
                self.canon_combo.setCurrentIndex(1)
            else:
                self.canon_combo.setCurrentIndex(0)
            self._set_combo_value(self.visibility_combo, _enum_value(getattr(relation, "visibility_state", None), ""))

            # Color
            stored_color = meta.get("_edge_color")
            if stored_color:
                self._update_color_swatch(stored_color)
            else:
                self._update_color_swatch(_default_color_for_type(kind))

            self._refresh_technical(relation)
            self.set_advanced_mode(self.ctx.advanced_mode)
        finally:
            self._refreshing = False

    def _refresh_technical(self, relation):
        payload = {
            "id": getattr(relation, "id", ""),
            "source_id": getattr(relation, "source_id", ""),
            "target_id": getattr(relation, "target_id", ""),
            "custom_metadata": getattr(relation, "custom_metadata", {}),
            "custom_relation_type_id": getattr(relation, "custom_relation_type_id", None),
            "custom_fields": [
                f.to_dict() if hasattr(f, "to_dict") else f
                for f in (getattr(relation, "custom_fields", []) or [])
            ],
            "layer_ids": getattr(relation, "layer_ids", []),
        }
        self.technical_text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    # ------------------------------------------------------------------
    # Advanced mode
    # ------------------------------------------------------------------

    def set_advanced_mode(self, enabled: bool):
        self.technical_box.setVisible(bool(enabled))
        for w in self._advanced_widgets:
            w.setVisible(bool(enabled))

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self):
        self._autosave_timer.stop()
        self._do_save(refresh_after=True)

    def _do_save(self, *, refresh_after: bool = True):
        if self._relation is None:
            return
        type_data = self.type_combo.currentData()
        type_text = self.type_combo.currentText().strip()
        relation_type_value = type_data if type_data else (type_text.lower() if type_text else "esta_relacionado_con")

        canon_data = self.canon_combo.currentData()
        canon_value = canon_data if canon_data else "borrador"

        # Build metadata with color, body, notes
        meta = dict(getattr(self._relation, "custom_metadata", {}) or {})
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

        payload = {
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type_value,
            "direction": direction_value,
            "intensity": self.intensity_combo.currentData(),
            "description": self.description_edit.toPlainText().strip(),
            "temporality": self.temporality_edit.toPlainText().strip(),
            "causality": self.causality_edit.toPlainText().strip(),
            "validity_conditions": [],
            "tags": [],
            "canon_state": canon_value,
            "visibility_state": self.visibility_combo.currentData() or "visible_usuario",
            "custom_metadata": meta,
        }
        result = self.relation_controller.update(self.relation_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
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
            self.ctx.log("error", result.error)
            return
        self.ctx.log("info", "Relación archivada")
        if self.on_saved is not None:
            self.on_saved()
        if self.ctx.drawer is not None:
            self.ctx.drawer.close()
