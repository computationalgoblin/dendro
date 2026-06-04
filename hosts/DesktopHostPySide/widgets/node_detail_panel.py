"""Node detail panel — immersive entity editor for B31-CREATION-T01-B.

RightDrawer content opened from the graph when a node is selected. It reads and
updates entities through the UI controller.  Normal mode shows a warm, minimal
form with color picker, editable type, and non-blocking AI autocomplete.
Technical fields remain hidden unless advanced mode is active.
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
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
from hosts.DesktopHostPySide.widgets.coherence_panel import CoherencePanel
from packages.domain.entity import CanonState, EntityType, VisibilityState
from packages.domain.result import Error

# ---------------------------------------------------------------------------
# Warm palette constants
# ---------------------------------------------------------------------------
_BG_DRAWER = "#F8F6ED"
_TITLE_COLOR = "#5C5A3E"
_LABEL_COLOR = "#6F6A42"
_MUTED_COLOR = "#7C806E"
_SUGGESTION_BG = "#FFFDF7"

# Default node colours per entity type (mirrors graph_canvas._NODE_COLORS)
_NODE_COLORS: dict[str, str] = {
    "personaje": "#7C9BFF",
    "lugar": "#7EC8A5",
    "localizacion": "#7EC8A5",
    "organizacion": "#DCA35F",
    "faccion": "#D9908F",
    "objeto": "#C9A5FF",
    "evento": "#E0C46C",
    "concepto": "#9BB4C7",
}

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
        is_new: bool = False,
    ):
        super().__init__()
        self.ctx = ctx
        self.entity_controller = entity_controller
        self.entity_id = entity_id
        self.on_saved = on_saved
        self.ai_controller = ai_controller
        self.relation_controller = relation_controller
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
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # -- Header --
        head = QHBoxLayout()
        self.title = QLabel("Entidad")
        self.title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {_TITLE_COLOR}; "
            f"font-family: Georgia, 'Courier New', serif; background: transparent;"
        )
        self.title.setWordWrap(True)
        head.addWidget(self.title, 1)
        self.type_badge = Badge("Entidad", "info")
        head.addWidget(self.type_badge)
        root.addLayout(head)

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

        # Nombre
        name_label = QLabel("Nombre:")
        name_label.setStyleSheet(_label_ss)
        self.name_edit = QLineEdit()
        form_layout.addRow(name_label, self.name_edit)

        # Tipo + Color (on one row)
        type_label = QLabel("Tipo:")
        type_label.setStyleSheet(_label_ss)
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        for item in EntityType:
            self.type_combo.addItem(enum_human(item.value), item.value)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo, 1)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.setToolTip("Color del nodo")
        self.color_btn.setCursor(self.color_btn.cursor())
        self.color_btn.clicked.connect(self._pick_color)
        type_row.addWidget(self.color_btn)
        form_layout.addRow(type_label, type_row)

        # Descripción breve
        brief_label = QLabel("Descripción breve:")
        brief_label.setStyleSheet(_label_ss)
        self.brief_edit = QTextEdit()
        self.brief_edit.setMaximumHeight(56)
        form_layout.addRow(brief_label, self.brief_edit)

        # Cuerpo
        body_label = QLabel("Cuerpo:")
        body_label.setStyleSheet(_label_ss)
        self.extended_edit = QTextEdit()
        self.extended_edit.setMaximumHeight(120)
        form_layout.addRow(body_label, self.extended_edit)

        # Estado (simplified canon: Borrador / Canon)
        canon_label = QLabel("Estado:")
        canon_label.setStyleSheet(_label_ss)
        self.canon_combo = QComboBox()
        for val in _SIMPLE_CANON:
            self.canon_combo.addItem(enum_human(val), val)
        form_layout.addRow(canon_label, self.canon_combo)

        root.addWidget(form_card)

        # -- Hidden fields (only in advanced mode) --
        self._advanced_widgets: list[QWidget] = []

        self.private_notes_edit = QTextEdit()
        self.private_notes_edit.setMaximumHeight(70)
        self.exportable_notes_edit = QTextEdit()
        self.exportable_notes_edit.setMaximumHeight(70)
        self.visibility_combo = QComboBox()
        for item in VisibilityState:
            self.visibility_combo.addItem(enum_human(item.value), item.value)

        adv_notes_label = QLabel("Notas privadas:")
        adv_notes_label.setStyleSheet(_label_ss)
        form_layout.addRow(adv_notes_label, self.private_notes_edit)
        self._advanced_widgets.append(adv_notes_label)
        self._advanced_widgets.append(self.private_notes_edit)

        adv_export_label = QLabel("Notas exportables:")
        adv_export_label.setStyleSheet(_label_ss)
        form_layout.addRow(adv_export_label, self.exportable_notes_edit)
        self._advanced_widgets.append(adv_export_label)
        self._advanced_widgets.append(self.exportable_notes_edit)

        adv_vis_label = QLabel("Visibilidad:")
        adv_vis_label.setStyleSheet(_label_ss)
        form_layout.addRow(adv_vis_label, self.visibility_combo)
        self._advanced_widgets.append(adv_vis_label)
        self._advanced_widgets.append(self.visibility_combo)

        # -- Compact context summary --
        self.context_box = QGroupBox("Contexto")
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
        root.addWidget(self.context_box)

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
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.save)
        actions.addWidget(self.cancel_btn)
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
        self._schedule_autosave()

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
        self.visibility_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.type_combo.currentIndexChanged.connect(self._schedule_autosave)

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
        return (
            f"Nombre actual: {entity_name}\n"
            f"Tipo actual: {type_value}\n"
            f"Descripción breve actual del formulario:\n{brief or '—'}\n\n"
            f"Cuerpo actual del formulario:\n{body or '—'}\n\n"
            f"Notas actuales:\n{private_notes or exportable_notes or '—'}\n\n"
            f"Instrucción opcional del usuario: {instruction or '—'}"
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
        self._ai_worker.start()

    def _show_ai_error(self, message: str):
        self.ai_generate_btn.setEnabled(self.ai_controller is not None)
        self.ai_generate_btn.setText("Generar sugerencia")
        self.refine_btn.setEnabled(True)
        self.suggestion_text.setPlainText(f"Error IA: {message}")
        self.suggestion_frame.setVisible(True)
        self.accept_btn.setEnabled(False)
        if self.ctx is not None:
            self.ctx.log("warning", f"IA: {message}")

    def _on_ai_finished(self, text: str, error: str):
        self.ai_generate_btn.setEnabled(True)
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
        self.suggestion_frame.setVisible(False)
        self.suggestion_text.clear()

    # ------------------------------------------------------------------
    # Coherence analysis
    # ------------------------------------------------------------------

    def _open_coherence(self):
        """Open coherence analysis panel for this entity."""
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
    # Cancel
    # ------------------------------------------------------------------

    def _cancel(self):
        """Cancel edits. New visual drafts are removed; saved entities are reloaded."""
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
        self._refreshing = True
        try:
            result = self.entity_controller.get(self.entity_id)
            if isinstance(result, Error):
                self.title.setText("Entidad no encontrada")
                self.summary.setText(result.error)
                self.save_btn.setEnabled(False)
                return
            entity = result.value
            self._entity = entity
            kind = _enum_value(getattr(entity, "entity_type", None), "entidad")
            self.title.setText(getattr(entity, "name", "Sin nombre") or "Sin nombre")
            self.type_badge.setText(enum_human(kind))
            canon_val = _enum_value(getattr(entity, "canon_state", None), "")
            self.summary.setText(
                f"{enum_human(kind)} · {enum_human(canon_val)}"
            )

            self.name_edit.setText(getattr(entity, "name", ""))
            self._set_combo_value(self.type_combo, kind)
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
            self._refresh_technical(entity)
            self.set_advanced_mode(self.ctx.advanced_mode)
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
                else "Entidad vinculada"
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
        self.technical_box.setVisible(bool(enabled))
        for w in self._advanced_widgets:
            w.setVisible(bool(enabled))

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self):
        """Manual save (button) — saves + refreshes UI."""
        self._autosave_timer.stop()
        self._do_save(refresh_after=True)

    def _do_save(self, *, refresh_after: bool = True):
        """Core save logic. refresh_after=True for manual save, False for auto-save."""
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
            "visibility_state": self.visibility_combo.currentData() or "visible_usuario",
            "custom_metadata": meta,
        }
        result = self.entity_controller.update(self.entity_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        self.ctx.log("info", "Entidad guardada")
        self.is_new = False
        self.ctx.selected_entity_id = self.entity_id
        if refresh_after:
            self.refresh()
        if self.on_saved is not None:
            self.on_saved()
