"""Panel de detalle de un HITO causal (BETA1-HITO-MULTI).

Se abre en el RightDrawer al clicar un hito en la cronología. Es el equivalente
para hitos del panel de detalle de entidades (node/tree): un editor enfocado de
UN solo hito —sin el calendario ni la lista de toda la cronología—, con los
campos relevantes de un hito (tipo, estado, año/fecha, participantes, racional).

La UI nunca escribe persistencia directa: todo va por el CausalMilestoneController.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.calendar_date_picker import CalendarDatePicker
from hosts.DesktopHostPySide.widgets.mention_support import attach_mention_support
from packages.application.structured_reference_service import (
    StructuredReferenceService,
    build_known_targets,
)
from packages.domain.narrative_memory import MemoryTargetKind
from hosts.DesktopHostPySide.widgets.design_system import (
    FONT_SERIF,
    GOLD,
    INK_MUTED,
    INK_STRONG,
    LINE_SOFT,
    SPACE_SM,
    AdvancedSection,
    Badge,
    FlowLayout,
    PanelScaffold,
    enum_human,
    overline_label,
)
from hosts.DesktopHostPySide.widgets.milestone_labels import milestone_temporal_label
from hosts.DesktopHostPySide.widgets.stepper import BotanicalSpinBox
from packages.domain.causal_milestone import CausalMilestoneType
from packages.domain.result import Error


def _metadata(obj: Any) -> dict[str, Any]:
    value = getattr(obj, "metadata", {}) or {}
    return dict(value) if isinstance(value, dict) else {}


def _raw_enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


class MilestoneDetailPanel(PanelScaffold):
    """Editor enfocado de un hito (un solo hito, sin calendario ni lista).

    BETA2-PULIDO-02: construido sobre ``PanelScaffold`` (cabecera + body +
    barra de acciones con márgenes-token) y badges en ``FlowLayout`` para que
    envuelvan en paneles estrechos en vez de comprimirse."""

    def __init__(
        self,
        ctx: Any,
        controller: Any,
        milestone_id: str,
        *,
        on_saved: Callable[[], None] | None = None,
        entity_controller: Any = None,
        relation_controller: Any = None,
        chronology_controller: Any = None,
        project_getter: Callable[[], Any] | None = None,
        on_start_walk: Callable[[str], None] | None = None,
        on_open_milestone: Callable[[str], None] | None = None,
        preview_patch: dict | None = None,
        on_preview_save: Callable[[dict], None] | None = None,
    ):
        super().__init__("Hito", "Detalle del hito causal.")
        self.ctx = ctx
        # PLAY-16: modo PREVIEW — el panel real con el patch propuesto aplicado
        # encima del canon; sin autosave y guardado redirigido a callback (diff).
        self.preview_patch = dict(preview_patch) if preview_patch else None
        self.on_preview_save = on_preview_save
        self._preview_base: dict = {}
        self._preview_extra: dict = {}
        self.controller = controller
        self.milestone_id = str(milestone_id or "")
        self.on_saved = on_saved
        self.on_start_walk = on_start_walk
        self.on_open_milestone = on_open_milestone
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.chronology_controller = chronology_controller
        self.project_getter = project_getter
        self._hito: Any | None = None

        # PULIDO-02: los badges (tipo + etiqueta temporal, que puede ser larga)
        # envuelven a la siguiente línea en vez de comprimirse (FlowLayout).
        self.badge_row = FlowLayout(spacing=6)
        self.body.addLayout(self.badge_row)

        # BETA2-FOCO-29: layout INTEGRADO por grupos. TODAS las funciones se
        # conservan; el minimalismo es de LAYOUT — título protagonista + Tipo
        # arriba, luego los clústeres «Cuándo» / «Narrativa» / «Participantes».
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Título del hito")
        self.title_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: 1px solid transparent; "
            f"border-radius: 8px; padding: 2px 4px; color: {INK_STRONG}; "
            f"font-family: {FONT_SERIF}; font-size: 20px; font-weight: 700; }} "
            f"QLineEdit:hover {{ border-color: {LINE_SOFT}; }} "
            f"QLineEdit:focus {{ border-color: {GOLD}; }}"
        )
        self.type_combo = QComboBox()
        for member in CausalMilestoneType:
            self.type_combo.addItem(enum_human(member.value), member.value)
        self.year_edit = BotanicalSpinBox()
        self.year_edit.setRange(-999999999, 999999999)
        # FOCO-25: fin opcional del hito (lapso). El mínimo = "sin fin" (hito
        # puntual); con fin > inicio se persiste como duración en años.
        self.end_year_edit = BotanicalSpinBox()
        self.end_year_edit.setRange(-999999999, 999999999)
        # PULIDO-02: texto especial CORTO + ancho mínimo para que no se recorte.
        self.end_year_edit.setSpecialValueText("— sin fin")
        self.end_year_edit.setToolTip("Sin año fin: hito puntual (sin duración).")
        _fm = self.end_year_edit.fontMetrics()
        self.end_year_edit.setMinimumWidth(_fm.horizontalAdvance("— sin fin") + 2 * 24 + 16)
        self.exact_date_picker = CalendarDatePicker(compact=True)
        self.temporal_edit = QLineEdit()
        self.temporal_edit.setPlaceholderText("Era, periodo o clave de calendario")
        self.summary_edit = QTextEdit()
        self.summary_edit.setPlaceholderText("Resumen breve del hito")
        self.summary_edit.setMaximumHeight(80)
        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("Desarrollo o justificación (opcional)")
        self.body_edit.setMaximumHeight(110)
        # FOCO-20 (Editorial sereno): serif editorial en los cuerpos de escritura.
        _serif_ss = f"QTextEdit {{ font-family: {FONT_SERIF}; font-size: 14px; }}"
        self.summary_edit.setStyleSheet(_serif_ss)
        self.body_edit.setStyleSheet(_serif_ss)
        # BETA2-MEM-03: @menciones estructuradas en resumen y desarrollo del hito.
        self._mention_supports = {}
        try:
            provider = self._mention_targets_provider()
            self._mention_supports["description"] = attach_mention_support(
                self.summary_edit, provider
            )
            self._mention_supports["rationale"] = attach_mention_support(
                self.body_edit, provider
            )
        except Exception:  # noqa: BLE001 — las @menciones nunca deben romper el editor
            self._mention_supports = {}
        self.participants_list = QListWidget()
        self.participants_list.setMaximumHeight(150)

        # Cabecera: título protagonista + tipo en una fila discreta.
        self.body.addWidget(self.title_edit)
        _type_row = QHBoxLayout()
        _type_row.setSpacing(SPACE_SM)
        _type_row.addWidget(overline_label("Tipo"))
        _type_row.addWidget(self.type_combo, 1)
        self.body.addLayout(_type_row)

        # ── Cuándo (clúster temporal). self._form conserva setRowVisible para
        # ocultar la fila ENTERA de «Fecha exacta» fuera del calendario completo.
        self.body.addWidget(overline_label("Cuándo"))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(0, 0, 0, 0)
        self._form = form
        _years_row = QHBoxLayout()
        _years_row.setSpacing(SPACE_SM)
        _years_row.addWidget(self.year_edit)
        _arrow = QLabel("→")
        _arrow.setStyleSheet(f"color: {INK_MUTED}; background: transparent;")
        _years_row.addWidget(_arrow)
        _years_row.addWidget(self.end_year_edit)
        _years_row.addStretch(1)
        form.addRow("Año", _years_row)
        form.addRow("Fecha exacta", self.exact_date_picker)
        form.addRow("Fecha / posición", self.temporal_edit)
        self.body.addLayout(form)

        # ── Narrativa ──
        self.body.addWidget(overline_label("Narrativa"))
        self.body.addWidget(self.summary_edit)
        self.body.addWidget(self.body_edit)

        # ── Participantes ──
        self.body.addWidget(overline_label("Participantes"))
        self.body.addWidget(self.participants_list)

        # ── Subhitos (BETA2-SUB-01): eventos contenidos en este hito-marco ──
        # Un hito puede abarcar un intervalo (p. ej. una guerra) y contener
        # otros hitos completos dentro. Se oculta si ESTE hito ya es subhito
        # (regla de 1 nivel); en ese caso se muestra su marco como badge.
        self.subhitos_container = self._build_subhitos_section()
        self.body.addWidget(self.subhitos_container)

        # Vínculos del hito (solo lectura): relaciones causadas, causa/consecuencia.
        self.links_section = AdvancedSection("Vinculos del hito")
        self.links_label = QLabel("")
        self.links_label.setObjectName("mutedLabel")
        self.links_label.setWordWrap(True)
        self.links_section.body_layout.addWidget(self.links_label)
        self.body.addWidget(self.links_section)

        # CRON: punto de entrada al recorrido cronológico desde el hito.
        if self.on_start_walk is not None:
            self.walk_btn = QPushButton("Iniciar creación cronológica")
            self.walk_btn.setObjectName("startChronologyWalkButton")
            self.walk_btn.clicked.connect(
                lambda: self.on_start_walk(self.milestone_id) if self.on_start_walk else None
            )
            self.body.addWidget(self.walk_btn)

        buttons = self.add_action_bar()
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setObjectName("deleteMilestoneButton")
        self.delete_btn.clicked.connect(self._delete)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch(1)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(self.save_btn)

        # BETA2-UX-06: autosave (800ms) como en node/relation — modelo de
        # guardado único. El guard _loading evita autoguardar durante la
        # repoblación de los widgets en _load.
        self._loading = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(800)
        self._autosave_timer.timeout.connect(lambda: self._do_save(reload_after=False))
        self._connect_autosave()
        self._load()
        if self.preview_patch is not None:
            self._apply_preview_patch()

    def _connect_autosave(self) -> None:
        if self.preview_patch is not None:
            return  # PLAY-16: el preview no autoguarda — jamás escribe canon
        self.title_edit.textEdited.connect(self._schedule_autosave)
        self.type_combo.currentIndexChanged.connect(self._schedule_autosave)
        self.year_edit.valueChanged.connect(self._schedule_autosave)
        self.end_year_edit.valueChanged.connect(self._schedule_autosave)
        self.temporal_edit.textEdited.connect(self._schedule_autosave)
        self.summary_edit.textChanged.connect(self._schedule_autosave)
        self.body_edit.textChanged.connect(self._schedule_autosave)
        self.participants_list.itemChanged.connect(self._schedule_autosave)
        # BETA2-FOCO-29: la fecha exacta ahora autoguarda (era el único campo
        # editable sin autosave). El guard _loading evita disparar durante _load.
        self.exact_date_picker.on_changed = lambda *_: self._schedule_autosave()

    def _schedule_autosave(self, *args: Any) -> None:
        if self._loading or self._hito is None:
            return
        self._autosave_timer.start()

    # ── PLAY-16: modo preview (propuesta de la IA sobre el panel real) ──────

    _PREVIEW_GOLD = "#BBAA66"  # GOLD_SOFT: resaltado de campos propuestos

    def _set_type_value(self, value: Any) -> None:
        idx = self.type_combo.findData(str(value))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

    def _apply_preview_patch(self) -> None:
        patch = dict(self.preview_patch or {})
        self._preview_base = {
            "title": self.title_edit.text().strip(),
            "milestone_type": str(self.type_combo.currentData() or "origen"),
            "description": self.summary_edit.toPlainText().strip(),
            "rationale": self.body_edit.toPlainText().strip(),
            "year": int(self.year_edit.value()),
        }
        renderers = {
            "title": lambda v: self.title_edit.setText(str(v)),
            "milestone_type": self._set_type_value,
            "description": lambda v: self.summary_edit.setPlainText(str(v)),
            "rationale": lambda v: self.body_edit.setPlainText(str(v)),
            "year": lambda v: self.year_edit.setValue(int(v)),
        }
        widgets = {
            "title": self.title_edit,
            "milestone_type": self.type_combo,
            "description": self.summary_edit,
            "rationale": self.body_edit,
            "year": self.year_edit,
        }
        self._preview_extra = {}
        for key, value in patch.items():
            render = renderers.get(key)
            if render is None:
                self._preview_extra[key] = value
                continue
            try:
                render(value)
            except (TypeError, ValueError):
                self._preview_extra[key] = value
                continue
            widget = widgets[key]
            canon = self._preview_base.get(key)
            widget.setStyleSheet(
                widget.styleSheet() + f" border: 2px solid {self._PREVIEW_GOLD};"
            )
            widget.setToolTip(f"Propuesta de la IA — canon actual: «{canon}»")
        for side in (getattr(self, "save_btn", None), getattr(self, "delete_btn", None)):
            if side is not None:
                side.setVisible(False)

    def preview_extra_fields(self) -> dict:
        return dict(self._preview_extra)

    def preview_payload(self) -> dict:
        """Diff contra el canon (propuesta + retoques del usuario), sin escribir."""
        current = {
            "title": self.title_edit.text().strip(),
            "milestone_type": str(self.type_combo.currentData() or "origen"),
            "description": self.summary_edit.toPlainText().strip(),
            "rationale": self.body_edit.toPlainText().strip(),
            "year": int(self.year_edit.value()),
        }
        diff = {
            key: value
            for key, value in current.items()
            if value != self._preview_base.get(key)
        }
        diff.update(self._preview_extra)
        return diff

    # ── datos ──────────────────────────────────────────────────────────────

    def _project(self) -> Any:
        if self.project_getter is not None:
            return self.project_getter()
        ps = getattr(self.controller, "ps", None)
        return getattr(ps, "active_project", None)

    def _entities(self) -> list[Any]:
        if self.entity_controller is not None and hasattr(self.entity_controller, "list_all"):
            return list(self.entity_controller.list_all())
        return list(getattr(self._project(), "entities", []) or [])

    def _entity_name(self, entity_id: str) -> str:
        for entity in self._entities():
            if str(getattr(entity, "id", "")) == str(entity_id):
                return str(getattr(entity, "name", "") or "Sin nombre")
        return "Elemento vinculado"

    def _chronology_metadata(self) -> dict[str, Any]:
        chronology = None
        if self.chronology_controller is not None and hasattr(self.chronology_controller, "get"):
            value = self.chronology_controller.get()
            if not isinstance(value, Error):
                chronology = getattr(value, "value", value)
        if chronology is None:
            chronology = getattr(self._project(), "project_chronology", None)
        value = getattr(chronology, "metadata", {}) or {}
        return dict(value) if isinstance(value, dict) else {}

    def _find_hito(self) -> Any | None:
        items = self.controller.list_all() if hasattr(self.controller, "list_all") else []
        for hito in items:
            if str(getattr(hito, "id", "")) == self.milestone_id:
                return hito
        return None

    def _load(self) -> None:
        self._loading = True
        hito = self._find_hito()
        self._hito = hito
        if hito is None:
            self.header.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self._loading = False
            return
        meta = _metadata(hito)
        self.title_edit.setText(str(getattr(hito, "title", "")))
        type_idx = self.type_combo.findData(_raw_enum(getattr(hito, "milestone_type", "")))
        self.type_combo.setCurrentIndex(type_idx if type_idx >= 0 else 0)
        year = getattr(hito, "year", None)
        if not isinstance(year, int) or isinstance(year, bool):
            chronology = getattr(self._project(), "project_chronology", None)
            year = int(getattr(chronology, "present_year", 0) or 0)
        self.year_edit.setValue(year)
        # FOCO-25: fin derivado del lapso (duración); mínimo = sin fin.
        end_year = None
        span_of = getattr(hito, "as_temporal_span", None)
        if callable(span_of):
            end = getattr(span_of(), "end_year", None)
            if isinstance(end, int) and not isinstance(end, bool):
                end_year = end
        self.end_year_edit.setValue(
            end_year if end_year is not None else self.end_year_edit.minimum()
        )
        self.summary_edit.setPlainText(str(getattr(hito, "description", "")))
        self.body_edit.setPlainText(str(meta.get("body", "") or getattr(hito, "rationale", "")))
        self.temporal_edit.setText(str(meta.get("chronology_key", "") or ""))
        calendar_meta = self._chronology_metadata()
        exact_enabled = str(calendar_meta.get("mode") or "") == "full_calendar"
        # PULIDO-02: ocultar la FILA entera — antes la label "Fecha exacta"
        # quedaba huérfana descuadrando el formulario.
        self._form.setRowVisible(self.exact_date_picker, exact_enabled)
        self.exact_date_picker.set_calendar(calendar_meta)
        if exact_enabled:
            exact_date = meta.get("exact_date") if isinstance(meta.get("exact_date"), dict) else {}
            self.exact_date_picker.set_date(exact_date or calendar_meta.get("current_date") or {})

        # Participantes (multi-select). Se lee también el legacy primary_entity_id.
        selected = {str(v) for v in (getattr(hito, "affected_entity_ids", []) or []) if str(v)}
        legacy = str(meta.get("primary_entity_id", "") or "").strip()
        if legacy:
            selected.add(legacy)
        self.participants_list.clear()
        for entity in sorted(self._entities(), key=lambda e: str(getattr(e, "name", ""))):
            eid = str(getattr(entity, "id", ""))
            item = QListWidgetItem(str(getattr(entity, "name", "") or "Sin nombre"))
            item.setData(Qt.ItemDataRole.UserRole, eid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = Qt.CheckState.Checked if eid in selected else Qt.CheckState.Unchecked
            item.setCheckState(checked)
            self.participants_list.addItem(item)

        self._refresh_badges(hito)
        self._refresh_links(hito)
        self._refresh_subhitos(hito)
        self._loading = False

    def _refresh_badges(self, hito: Any) -> None:
        while self.badge_row.count():
            item = self.badge_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        type_label = enum_human(_raw_enum(getattr(hito, "milestone_type", "")))
        self.badge_row.addWidget(Badge(type_label, "info"))
        self.badge_row.addWidget(Badge(milestone_temporal_label(hito), "gold"))
        # BETA2-SUB-01: si este hito es subhito, señalar su hito-marco.
        parent_id = str(getattr(hito, "parent_milestone_id", "") or "")
        if parent_id:
            self.badge_row.addWidget(
                Badge(f"⤷ Subhito de «{self._hito_title(parent_id)}»", "neutral")
            )

    def _refresh_links(self, hito: Any) -> None:
        lines: list[str] = []
        relations = [str(v) for v in (getattr(hito, "caused_relation_ids", []) or []) if str(v)]
        if relations:
            lines.append(f"Relaciones causadas: {len(relations)}")
        parents = [str(v) for v in (getattr(hito, "causal_parent_hito_ids", []) or []) if str(v)]
        children = [str(v) for v in (getattr(hito, "causal_child_hito_ids", []) or []) if str(v)]
        if parents:
            lines.append(f"Causa de (hitos previos): {len(parents)}")
        if children:
            lines.append(f"Consecuencias (hitos posteriores): {len(children)}")
        sources = [str(v) for v in (getattr(hito, "source_ids", []) or []) if str(v)]
        if sources:
            lines.append(f"Fuentes: {len(sources)}")
        self.links_label.setText("\n".join(lines) if lines else "Sin vinculos adicionales.")

    # ── Subhitos (BETA2-SUB-01) ──────────────────────────────────────────────

    def _build_subhitos_section(self) -> QWidget:
        """Sección para contener otros hitos dentro de este hito-marco."""
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACE_SM)
        lay.addWidget(overline_label("Subhitos"))

        self.subhitos_list = QListWidget()
        self.subhitos_list.setMaximumHeight(120)
        self.subhitos_list.setObjectName("subhitosList")
        self.subhitos_list.itemDoubleClicked.connect(self._open_selected_subhito)
        lay.addWidget(self.subhitos_list)

        self.remove_subhito_btn = QPushButton("Quitar del marco")
        self.remove_subhito_btn.setObjectName("removeSubhitoButton")
        self.remove_subhito_btn.clicked.connect(self._remove_selected_subhito)
        lay.addWidget(self.remove_subhito_btn)

        # Crear un subhito nuevo (título en línea, sin diálogo modal).
        new_row = QHBoxLayout()
        new_row.setSpacing(SPACE_SM)
        self.new_subhito_edit = QLineEdit()
        self.new_subhito_edit.setPlaceholderText("Título de un nuevo subhito")
        self.new_subhito_edit.returnPressed.connect(self._create_subhito)
        new_row.addWidget(self.new_subhito_edit, 1)
        self.create_subhito_btn = QPushButton("Crear")
        self.create_subhito_btn.setObjectName("createSubhitoButton")
        self.create_subhito_btn.clicked.connect(self._create_subhito)
        new_row.addWidget(self.create_subhito_btn)
        lay.addLayout(new_row)

        # Vincular un hito existente como subhito de este marco.
        link_row = QHBoxLayout()
        link_row.setSpacing(SPACE_SM)
        self.link_subhito_combo = QComboBox()
        link_row.addWidget(self.link_subhito_combo, 1)
        self.link_subhito_btn = QPushButton("Vincular existente")
        self.link_subhito_btn.setObjectName("linkSubhitoButton")
        self.link_subhito_btn.clicked.connect(self._link_existing_subhito)
        link_row.addWidget(self.link_subhito_btn)
        lay.addLayout(link_row)
        return container

    def _hito_title(self, hito_id: str) -> str:
        items = self.controller.list_all() if hasattr(self.controller, "list_all") else []
        for hito in items:
            if str(getattr(hito, "id", "")) == str(hito_id):
                return str(getattr(hito, "title", "") or "Hito sin título")
        return "Hito"

    def _eligible_link_hitos(self) -> list[Any]:
        """Hitos que pueden volverse subhitos de este marco: no este, sin marco
        propio y sin subhitos propios (regla de 1 nivel)."""
        all_hitos = self.controller.list_all() if hasattr(self.controller, "list_all") else []
        parent_ids = {
            str(getattr(h, "parent_milestone_id", "") or "") for h in all_hitos
        }
        parent_ids.discard("")
        eligible = []
        for hito in all_hitos:
            hid = str(getattr(hito, "id", ""))
            if hid == self.milestone_id:
                continue
            if getattr(hito, "parent_milestone_id", None):
                continue
            if hid in parent_ids:  # ya contiene subhitos
                continue
            eligible.append(hito)
        return eligible

    def _refresh_subhitos(self, hito: Any) -> None:
        is_sub = bool(getattr(hito, "parent_milestone_id", None))
        # Regla de 1 nivel: un subhito no puede contener subhitos.
        self.subhitos_container.setVisible(not is_sub)
        if is_sub:
            return
        self.subhitos_list.clear()
        subhitos = (
            self.controller.list_subhitos(self.milestone_id)
            if hasattr(self.controller, "list_subhitos")
            else []
        )
        for sub in subhitos:
            label = str(getattr(sub, "title", "") or "Sin título")
            label = f"{label}  ·  {milestone_temporal_label(sub)}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(getattr(sub, "id", "")))
            self.subhitos_list.addItem(item)
        self.link_subhito_combo.clear()
        for candidate in self._eligible_link_hitos():
            self.link_subhito_combo.addItem(
                str(getattr(candidate, "title", "") or "Sin título"),
                str(getattr(candidate, "id", "")),
            )
        self.link_subhito_btn.setEnabled(self.link_subhito_combo.count() > 0)

    def _after_subhito_change(self) -> None:
        if self.on_saved:
            self.on_saved()
        self._load()

    def _create_subhito(self) -> None:
        if self._hito is None or not hasattr(self.controller, "create_subhito"):
            return
        title = self.new_subhito_edit.text().strip()
        if not title:
            return
        data = {"title": title, "year": int(self.year_edit.value())}
        result = self.controller.create_subhito(self.milestone_id, data)
        if isinstance(result, Error):
            if self.ctx is not None:
                self.ctx.notify(result.error, "error")
            return
        self.new_subhito_edit.clear()
        self._after_subhito_change()

    def _link_existing_subhito(self) -> None:
        if self._hito is None or not hasattr(self.controller, "set_parent"):
            return
        child_id = str(self.link_subhito_combo.currentData() or "")
        if not child_id:
            return
        result = self.controller.set_parent(child_id, self.milestone_id)
        if isinstance(result, Error):
            if self.ctx is not None:
                self.ctx.notify(result.error, "error")
            return
        self._after_subhito_change()

    def _remove_selected_subhito(self) -> None:
        item = self.subhitos_list.currentItem()
        if item is None or not hasattr(self.controller, "clear_parent"):
            return
        child_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not child_id:
            return
        result = self.controller.clear_parent(child_id)
        if isinstance(result, Error):
            if self.ctx is not None:
                self.ctx.notify(result.error, "error")
            return
        self._after_subhito_change()

    def _open_selected_subhito(self, item: Any) -> None:
        if self.on_open_milestone is None or item is None:
            return
        child_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if child_id:
            self.on_open_milestone(child_id)

    # ── acciones ───────────────────────────────────────────────────────────

    def _checked_participants(self) -> list[str]:
        result: list[str] = []
        for row in range(self.participants_list.count()):
            item = self.participants_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                eid = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if eid:
                    result.append(eid)
        return result

    def _save(self) -> None:
        # Guardado manual explícito (botón «Guardar»): persiste y recarga.
        self._do_save(reload_after=True)

    def _mention_targets_provider(self):
        def provider():
            ps = getattr(self.controller, "ps", None)
            project = getattr(ps, "active_project", None)
            return build_known_targets(project) if project is not None else []

        return provider

    def _sync_structured_references(self, field_texts: dict) -> None:
        """Resuelve las @menciones del hito a referencias estructuradas (MEM-03)."""
        ps = getattr(self.controller, "ps", None)
        if ps is None or getattr(ps, "active_project", None) is None:
            return
        hints: dict[str, tuple[str, str]] = {}
        for ms in getattr(self, "_mention_supports", {}).values():
            hints.update(ms.hints())
        try:
            StructuredReferenceService(ps).sync_element_references(
                MemoryTargetKind.MILESTONE, self.milestone_id, field_texts, hints=hints
            )
        except Exception:  # noqa: BLE001 — nunca romper el guardado por las @menciones
            pass

    def _do_save(self, reload_after: bool = True) -> None:
        if self._hito is None:
            return
        # PLAY-16: en preview el guardado emite SOLO el diff (nunca el payload
        # completo con status/temporality pass-through) y no toca canon.
        if self.preview_patch is not None:
            if self.on_preview_save is not None:
                self.on_preview_save(self.preview_payload())
            return
        meta = _metadata(self._hito)
        meta["chronology_key"] = self.temporal_edit.text().strip()
        meta["body"] = self.body_edit.toPlainText().strip()
        meta.pop("primary_entity_id", None)  # BETA1-HITO-MULTI: sin "entidad principal"
        calendar_meta = self._chronology_metadata()
        if str(calendar_meta.get("mode") or "") == "full_calendar":
            meta["exact_date"] = self.exact_date_picker.date()
            label = self.exact_date_picker.date_label()
            if label:
                meta["chronology_key"] = label
        # FOCO-25: el fin se persiste como DURACIÓN en años dentro de
        # ``temporality`` (contrato de 22 campos intacto: as_temporal_span
        # deriva el fin de year + duration). Sin fin ⇒ hito puntual.
        start_year = int(self.year_edit.value())
        temporality = getattr(self._hito, "temporality", None)
        temporality_data = temporality.to_dict() if hasattr(temporality, "to_dict") else {}
        temporality_data["year"] = start_year
        end_value = int(self.end_year_edit.value())
        if end_value > max(start_year, int(self.end_year_edit.minimum())):
            temporality_data["is_duration"] = True
            temporality_data["duration_value"] = end_value - start_year
            temporality_data["duration_unit"] = "años"
        else:
            temporality_data["is_duration"] = False
            temporality_data["duration_value"] = None
            temporality_data["duration_unit"] = None
        payload = {
            "title": self.title_edit.text().strip() or "Hito sin titulo",
            "milestone_type": str(self.type_combo.currentData() or "origen"),
            # BETA2-UX-06: el estado del hito ya no se edita (canon total); se
            # preserva por pass-through el que fijan los servicios.
            "status": _raw_enum(getattr(self._hito, "status", "candidate")) or "candidate",
            "description": self.summary_edit.toPlainText().strip(),
            "rationale": self.body_edit.toPlainText().strip(),
            "year": start_year,
            "temporality": temporality_data,
            "affected_entity_ids": self._checked_participants(),
            "metadata": meta,
        }
        result = self.controller.update(self.milestone_id, payload)
        if isinstance(result, Error):
            self.ctx.log("warning", result.error) if self.ctx is not None else None
            return
        # BETA2-MEM-03: resolver @menciones del hito → referencias estructuradas.
        self._sync_structured_references(
            {"description": payload["description"], "rationale": payload["rationale"]}
        )
        if self.on_saved:
            self.on_saved()
        if reload_after:
            self._load()

    def _delete(self) -> None:
        if self._hito is None or not hasattr(self.controller, "delete"):
            return
        reply = QMessageBox.question(
            self,
            "Eliminar hito",
            "¿Eliminar este hito de la cronologia?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        result = self.controller.delete(self.milestone_id)
        if isinstance(result, Error):
            if self.ctx is not None:
                self.ctx.notify(result.error, "error")
            return
        if self.on_saved:
            self.on_saved()
        drawer = getattr(self.ctx, "drawer", None)
        if drawer is not None and hasattr(drawer, "close"):
            drawer.close()
