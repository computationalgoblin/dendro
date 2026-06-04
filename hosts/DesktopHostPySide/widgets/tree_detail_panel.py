"""Tree container detail panel — B32-T02..T05.

Expanded panel for semantic tree containers.  Sections:
  1. Identidad  (name, tree_type, color, brief, extended_description)
  2. Función narrativa (narrative_role, importance, development)
  3. Contenido  (members, sub-trees, internal/external relations)
  4. Worldbuilding + Canon (layers, canon/visibility/certainty, rules, questions)
  5. IA         (suggestion frame with editable preview)

Uses TreeMeta (B32-T01) for tree-specific custom_metadata keys.
IA uses node_text_suggestion — no candidate creation.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import enum_human
from packages.application.tree_meta import NARRATIVE_ROLES, TREE_TYPES, TreeMeta
from packages.domain.entity import (
    CanonState,
    CertaintyLevel,
    DevelopmentLevel,
    EntityType,
    NarrativeImportance,
    VisibilityState,
)
from packages.domain.result import Error

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
    ):
        super().__init__(parent)
        self.ctx = ctx
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.entity_id = entity_id
        self.on_saved = on_saved
        self.ai_controller = ai_controller
        self._ai_worker: _TreeAIWorker | None = None
        self._tree_meta = TreeMeta()

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setStyleSheet(f"background: {_BG_DRAWER};")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # -- Header --
        self.header_label = QLabel("Contenedor")
        self.header_label.setStyleSheet(
            f"color: {_TITLE_COLOR}; font-weight: 700; font-size: 16px; background: transparent;"
        )
        root.addWidget(self.header_label)

        # ═══ 1. IDENTIDAD ═══
        id_card, id_layout = _section_card("Identidad")
        form = QFormLayout()
        form.setSpacing(6)

        self.name_edit = _styled_edit("Nombre del árbol...")
        form.addRow("Nombre", self.name_edit)

        self.tree_type_combo = _styled_combo(TREE_TYPES, "— Sin tipo —")
        form.addRow("Tipo de árbol", self.tree_type_combo)

        # Color row
        color_row = QHBoxLayout()
        self.color_edit = _styled_edit("#D0D8E0")
        self.color_edit.setMaximumWidth(100)
        self.color_btn = QPushButton("Color")
        self.color_btn.setFixedSize(50, 28)
        self.color_btn.setStyleSheet(
            "QPushButton { border: 1px solid #C8C6B8; border-radius: 6px; background: #D0D8E0; }"
        )
        self.color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_edit)
        color_row.addWidget(self.color_btn)
        color_row.addStretch()
        form.addRow("Color", color_row)

        self.brief_edit = _styled_edit("Descripción breve...")
        form.addRow("Descripción breve", self.brief_edit)

        self.extended_edit = _styled_textedit("Cuerpo / descripción extendida...", 150)
        form.addRow("Cuerpo", self.extended_edit)

        id_layout.addLayout(form)
        root.addWidget(id_card)

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
        root.addWidget(fn_card)

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
        root.addWidget(ct_card)

        # ═══ 4. WORLDBUILDING + CANON ═══
        wc_card, wc_layout = _section_card("Worldbuilding y canon")
        wc_form = QFormLayout()
        wc_form.setSpacing(6)

        self.canon_combo = _styled_combo([e.value for e in CanonState], "")
        wc_form.addRow("Estado canon", self.canon_combo)

        self.visibility_combo = _styled_combo([e.value for e in VisibilityState], "")
        wc_form.addRow("Visibilidad", self.visibility_combo)

        self.certainty_combo = _styled_combo([e.value for e in CertaintyLevel], "")
        wc_form.addRow("Certeza", self.certainty_combo)

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

        # -- Notas --
        wc_layout.addWidget(_label("Notas privadas"))
        self.private_notes_edit = _styled_textedit("Notas privadas...", 60)
        wc_layout.addWidget(self.private_notes_edit)

        wc_layout.addWidget(_label("Notas exportables"))
        self.exportable_notes_edit = _styled_textedit("Notas exportables...", 60)
        wc_layout.addWidget(self.exportable_notes_edit)

        root.addWidget(wc_card)

        # ═══ 5. IA ═══
        ai_card, ai_layout = _section_card("IA")
        ai_title = QLabel("Acciones IA del árbol")
        ai_title.setStyleSheet(
            f"color: {_LABEL_COLOR}; font-weight: 600; font-size: 12px; background: transparent;"
        )
        ai_layout.addWidget(ai_title)

        # Action buttons row
        ai_btn_row = QHBoxLayout()
        ai_btn_row.setSpacing(4)

        self.ai_desc_btn = QPushButton("Descripción")
        self.ai_desc_btn.setFixedHeight(28)
        self.ai_desc_btn.setToolTip("Generar descripción del árbol con contexto de miembros")
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
        self.ai_coherence_btn.setToolTip("Analizar coherencia interna del árbol")
        self.ai_coherence_btn.clicked.connect(lambda: self._start_ai("coherence"))

        self.ai_questions_btn = QPushButton("Preguntas")
        self.ai_questions_btn.setFixedHeight(28)
        self.ai_questions_btn.setToolTip("Generar preguntas abiertas sobre el árbol")
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

        # Custom prompt
        prompt_row = QHBoxLayout()
        self.ai_prompt_edit = _styled_edit("Instruccion adicional para la IA...")
        prompt_row.addWidget(self.ai_prompt_edit, 1)
        ai_layout.addLayout(prompt_row)

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

    def refresh(self):
        entity = self._entity_by_id(self.entity_id)
        if entity is None:
            self.header_label.setText("Contenedor no encontrado")
            return

        # Header
        self.header_label.setText(entity.name or "Contenedor sin nombre")

        # Identidad
        self.name_edit.setText(entity.name)
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

        self.tree_type_combo.setCurrentIndex(0)
        for i in range(self.tree_type_combo.count()):
            if self.tree_type_combo.itemText(i) == self._tree_meta.tree_type:
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
            self.ctx.log("error", f"Error guardando nombre del árbol: {result.error}")
            return
        if self.on_saved:
            self.on_saved()

    def _save_brief(self):
        """Contract helper: save only the visible tree brief description."""
        result = self.entity_controller.update(
            self.entity_id, {"brief_description": self.brief_edit.text().strip()}
        )
        if isinstance(result, Error) and self.ctx:
            self.ctx.log("error", f"Error guardando descripción del árbol: {result.error}")
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

        data: dict[str, Any] = {
            "name": self.name_edit.text().strip(),
            "brief_description": self.brief_edit.text().strip(),
            "extended_description": self.extended_edit.toPlainText().strip(),
            "custom_metadata": merged_meta,
            "narrative_importance": self._current_combo_text(self.importance_combo) or entity.narrative_importance.value,
            "development_level": self._current_combo_text(self.development_combo) or entity.development_level.value,
            "canon_state": self._current_combo_text(self.canon_combo) or entity.canon_state.value,
            "visibility_state": self._current_combo_text(self.visibility_combo) or entity.visibility_state.value,
            "certainty_level": self._current_combo_text(self.certainty_combo) or entity.certainty_level.value,
            "private_notes": self.private_notes_edit.toPlainText().strip(),
            "exportable_notes": self.exportable_notes_edit.toPlainText().strip(),
        }

        result = self.entity_controller.update(self.entity_id, data)
        if isinstance(result, Error):
            if self.ctx:
                self.ctx.log("error", f"Error guardando árbol: {result.error}")
            return
        if self.ctx:
            self.ctx.log("info", "Árbol guardado")
        if self.on_saved:
            self.on_saved()
        self.refresh()

    def _cancel(self):
        self._discard_suggestion()
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

    def _pick_color(self):
        current = QColor(self.color_edit.text().strip() or "#D0D8E0")
        color = QColorDialog.getColor(current, self, "Color del árbol")
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
        members = self._get_members_text()
        rules = self._get_rules_text()
        tree_type = self._current_combo_text(self.tree_type_combo) or "general"
        custom_hint = self.ai_prompt_edit.text().strip()

        prompts: dict[str, str] = {
            "description": (
                f"Genera una descripcion narrativa extendida para el árbol '{entity_name}' "
                f"(tipo: {tree_type}). Miembros: {members}. Reglas internas: {rules}. "
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
                     self.ai_coherence_btn, self.ai_questions_btn):
            btn.setEnabled(False)

        self._ai_worker = _TreeAIWorker(
            self.ai_controller,
            self.entity_id,
            prompt_hint,
            language=getattr(self.ctx, "language", "es"),
        )
        self._ai_worker.finished.connect(self._on_ai_finished)
        self._ai_worker.start()

    def _on_ai_finished(self, text: str, error: str):
        # Re-enable buttons
        has_ai = self.ai_controller is not None
        for btn in (self.ai_desc_btn, self.ai_members_btn, self.ai_subtrees_btn,
                     self.ai_coherence_btn, self.ai_questions_btn):
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
            self.ctx.log("warning", f"IA árbol: {message}")

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
    # Data helpers
    # ------------------------------------------------------------------

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _entity_by_id(self, eid: str):
        proj = self._project()
        if not proj:
            return None
        for e in proj.entities:
            if e.id == eid:
                return e
        return None
