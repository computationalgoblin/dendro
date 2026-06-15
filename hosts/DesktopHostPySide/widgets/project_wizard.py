"""Project creation wizard — custom, fluid, design-system styled (BETA1-G09).

Reemplaza el QWizard nativo (genérico y plano) por un asistente propio con el
lenguaje visual de Dendro: un RAIL de pasos con progreso a la izquierda, una
cabecera con micro-ayuda por paso, campos agrupados y con ejemplos, transición
suave entre pasos y botones de oro. Cubre TODO el contenido de la configuración
del proyecto (paridad con CreativeConfigPanel), guiando al usuario en vez de
abrumarle: casi todo es opcional y editable después.

API pública preservada para `main_window._new_project`:
- ``exec()`` (QDialog) → Accepted/Rejected
- ``collect_config()`` → dict de overrides
- ``apply_to_project(project)`` → vuelca al proyecto recién creado
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.calendar_date_picker import CalendarDatePicker
from hosts.DesktopHostPySide.widgets.creative_config_panel import (
    AI_DEPTH_OPTIONS,
    AI_OUTPUT_OPTIONS,
    AI_ROLE_KEYS,
    AI_ROLE_OPTIONS,
    AI_STRATEGY_KEYS,
    AI_STRATEGY_OPTIONS,
    AI_UNCERTAINTY_OPTIONS,
    AUDIENCE_OPTIONS,
    CHANGE_OPTIONS,
    CONFLICT_OPTIONS,
    CONTRADICTION_OPTIONS,
    DIALOGUE_OPTIONS,
    DISTANCE_OPTIONS,
    EMOTION_OPTIONS,
    ESCALATION_OPTIONS,
    EXPOSITION_OPTIONS,
    FORMAT_OPTIONS,
    GENRE_OPTIONS,
    IMPACT_OPTIONS,
    PROGRESSION_OPTIONS,
    STATUS_OPTIONS,
    TENSION_OPTIONS,
    ListEditor,
    TagInput,
    _make_combo,
    _make_combo_keyed,
    _make_slider,
    _make_textarea,
)
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_TINT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE,
    PAPER,
    SURFACE,
    SURFACE_HI,
)
from packages.domain.creative_presets import CREATIVE_PRESETS, apply_preset_to_project
from packages.domain.project import Project
from packages.domain.project_chronology import ProjectChronology


def _names_from_length_text(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        for separator in (":", "=", ","):
            if separator in clean:
                clean = clean.split(separator, 1)[0].strip()
                break
        if clean:
            names.append(clean)
    return names


# ── piezas visuales ────────────────────────────────────────────────────────


def _field_block(label: str, widget: QWidget, hint: str = "") -> QWidget:
    """Bloque de campo vertical: etiqueta + (ayuda) + widget. Más aire y
    legibilidad que un QFormLayout a dos columnas."""
    block = QWidget()
    box = QVBoxLayout(block)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(5)
    lab = QLabel(label)
    lab.setStyleSheet(
        f"color: {INK_STRONG}; font-size: 13px; font-weight: 700; background: transparent; border: none;"
    )
    box.addWidget(lab)
    if hint:
        hl = QLabel(hint)
        hl.setWordWrap(True)
        hl.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        box.addWidget(hl)
    box.addWidget(widget)
    return block


def _slider_row(value: int = 5) -> tuple[QWidget, object]:
    """Slider + etiqueta de valor en una fila; devuelve (contenedor, slider)."""
    slider, lbl = _make_slider(value)
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    h.addWidget(slider, 1)
    lbl.setStyleSheet(
        f"color: {GOLD_DEEP}; font-size: 13px; font-weight: 700; min-width: 18px; "
        f"background: transparent; border: none;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    h.addWidget(lbl)
    return row, slider


class _RailItem(QPushButton):
    """Paso del rail: índice + título, con estado activo (oro)."""

    def __init__(self, index: int, title: str, parent=None):
        super().__init__(parent)
        self._index = index
        self.setText(f"  {index + 1}   {title}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setStyleSheet(
            f"QPushButton {{ text-align: left; padding: 6px 12px; border: none; "
            f"border-left: 3px solid transparent; border-radius: 0px; background: transparent; "
            f"color: {INK_MUTED}; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; color: {INK_SOFT}; }} "
            f"QPushButton:checked {{ background: {SURFACE_HI}; color: {INK_STRONG}; "
            f"border-left: 3px solid {GOLD}; }}"
        )


# ── wizard ──────────────────────────────────────────────────────────────────


class ProjectWizard(QDialog):
    """Asistente de creación de proyecto (custom, BETA1-G09)."""

    # (clave, título, micro-ayuda)
    STEPS = [
        ("essentials", "Tu proyecto", "Lo esencial para empezar. Solo el nombre es obligatorio."),
        ("genre", "Género y formato", "¿Qué clase de obra es y para quién?"),
        ("chronology", "Cronología", "¿Cómo mide el tiempo tu mundo? Puedes no usar calendario."),
        ("intent", "Intención y emoción", "Qué prometes al lector y qué quieres que sienta."),
        ("engine", "Motor narrativo", "De dónde nace la tensión y cómo avanza la historia."),
        ("style", "Estilo y voz", "El tono, la distancia y la textura de la prosa."),
        ("rules", "Reglas y límites", "Lo inviolable para la IA y lo que prefieres evitar."),
        ("ai", "Inteligencia artificial", "Cómo quieres que colabore Dendro contigo."),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo proyecto")
        self.setMinimumSize(960, 660)
        self.resize(1020, 700)
        self.setStyleSheet(f"QDialog {{ background: {PAPER}; }}")

        self._steps: list[QWidget] = []
        self._rail_items: list[_RailItem] = []
        self._current = 0

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_rail())

        content = QWidget()
        content.setStyleSheet(f"background: {SURFACE};")
        col = QVBoxLayout(content)
        col.setContentsMargins(34, 28, 34, 22)
        col.setSpacing(16)
        col.addWidget(self._build_header())
        self._stack = QStackedWidget()
        col.addWidget(self._stack, 1)
        col.addWidget(self._build_footer())
        root.addWidget(content, 1)

        # construir pasos
        for builder in (
            self._step_essentials, self._step_genre, self._step_chronology,
            self._step_intent, self._step_engine, self._step_style,
            self._step_rules, self._step_ai,
        ):
            page = self._scroll(builder())
            self._steps.append(page)
            self._stack.addWidget(page)

        self.name_edit.textChanged.connect(self._refresh_nav)
        self._go_to(0)

    # ── chrome ───────────────────────────────────────────────────────────

    def _build_rail(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("wizardRail")
        rail.setFixedWidth(262)
        rail.setStyleSheet(
            f"QFrame#wizardRail {{ background: {SURFACE_HI}; border-right: 1px solid {LINE}; }}"
        )
        col = QVBoxLayout(rail)
        col.setContentsMargins(0, 24, 0, 18)
        col.setSpacing(0)

        brand = QLabel("Nuevo proyecto")
        brand.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 17px; font-weight: 700; letter-spacing: 0.4px; "
            f"font-family: Georgia, 'Iowan Old Style', serif; background: transparent; "
            f"border: none; padding: 0 20px 2px 20px;"
        )
        col.addWidget(brand)
        tag = QLabel("Da forma a tu mundo")
        tag.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 12px; background: transparent; border: none; "
            f"padding: 0 20px 14px 20px;"
        )
        col.addWidget(tag)

        self._rail_group = QButtonGroup(self)
        self._rail_group.setExclusive(True)
        for i, (_key, title, _hint) in enumerate(self.STEPS):
            item = _RailItem(i, title)
            item.clicked.connect(lambda _=False, idx=i: self._go_to(idx))
            self._rail_group.addButton(item, i)
            self._rail_items.append(item)
            col.addWidget(item)

        col.addStretch(1)
        note = QLabel("Casi todo es opcional.\nTodo es editable luego en Configuración.")
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; font-style: italic; background: transparent; "
            f"border: none; padding: 0 20px;"
        )
        col.addWidget(note)
        return rail

    def _build_header(self) -> QWidget:
        head = QWidget()
        box = QVBoxLayout(head)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self._step_title = QLabel("")
        self._step_title.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 23px; font-weight: 700; letter-spacing: 0.3px; "
            f"font-family: Georgia, 'Iowan Old Style', serif; background: transparent; border: none;"
        )
        top.addWidget(self._step_title)
        top.addStretch(1)
        self._step_counter = QLabel("")
        self._step_counter.setStyleSheet(
            f"color: {GOLD_DEEP}; font-size: 12px; font-weight: 700; background: transparent; border: none;"
        )
        top.addWidget(self._step_counter, 0, Qt.AlignmentFlag.AlignBottom)
        box.addLayout(top)

        self._step_hint = QLabel("")
        self._step_hint.setWordWrap(True)
        self._step_hint.setStyleSheet(
            f"color: {INK_SOFT}; font-size: 13px; background: transparent; border: none;"
        )
        box.addWidget(self._step_hint)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setRange(0, len(self.STEPS))
        self._progress.setStyleSheet(
            f"QProgressBar {{ background: {LINE}; border: none; border-radius: 2px; }} "
            f"QProgressBar::chunk {{ background: {GOLD}; border-radius: 2px; }}"
        )
        box.addSpacing(6)
        box.addWidget(self._progress)
        return head

    def _build_footer(self) -> QWidget:
        foot = QWidget()
        row = QHBoxLayout(foot)
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(10)

        self._skip_btn = QPushButton("Crear con lo básico")
        self._skip_btn.setToolTip("Crea el proyecto ya; podrás completar el resto en Configuración.")
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {INK_MUTED}; "
            f"font-size: 12px; text-decoration: underline; }} "
            f"QPushButton:hover {{ color: {GOLD_DEEP}; }} "
            f"QPushButton:disabled {{ color: {LINE}; }}"
        )
        self._skip_btn.clicked.connect(self._finish)
        row.addWidget(self._skip_btn)
        row.addStretch(1)

        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        row.addWidget(self._cancel_btn)

        self._back_btn = QPushButton("← Atrás")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(lambda: self._go_to(self._current - 1))
        row.addWidget(self._back_btn)

        self._next_btn = QPushButton("Siguiente →")
        self._next_btn.setObjectName("primaryButton")
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._on_next)
        row.addWidget(self._next_btn)
        return foot

    def _scroll(self, inner: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        sa.viewport().setStyleSheet("background: transparent;")
        sa.setWidget(inner)
        return sa

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        box = QVBoxLayout(page)
        box.setContentsMargins(2, 2, 14, 2)
        box.setSpacing(15)
        return page, box

    # ── navegación ───────────────────────────────────────────────────────

    def _go_to(self, index: int):
        index = max(0, min(index, len(self.STEPS) - 1))
        self._current = index
        self._stack.setCurrentIndex(index)
        if not self._rail_items[index].isChecked():
            self._rail_items[index].setChecked(True)
        key, title, hint = self.STEPS[index]
        self._step_title.setText(title)
        self._step_hint.setText(hint)
        self._step_counter.setText(f"Paso {index + 1} de {len(self.STEPS)}")
        self._progress.setValue(index + 1)
        # BETA1-G09: cambio de paso INSTANTÁNEO. Nada de QGraphicsOpacityEffect
        # aquí: una animación DeleteWhenStopped sobre el efecto quedaba colgando
        # tras destruir el wizard y provocaba un access violation entre tests.
        # El rail + la barra de progreso ya transmiten fluidez. Ver memoria
        # [[qt-avoid-graphics-effects-on-dynamic-widgets]].
        self._refresh_nav()

    def _refresh_nav(self):
        last = self._current == len(self.STEPS) - 1
        self._back_btn.setEnabled(self._current > 0)
        has_name = bool(self.name_edit.text().strip())
        self._skip_btn.setEnabled(has_name)
        if last:
            self._next_btn.setText("✓  Crear proyecto")
            self._next_btn.setEnabled(has_name)
        else:
            self._next_btn.setText("Siguiente →")
            self._next_btn.setEnabled(True)

    def _on_next(self):
        if self._current == len(self.STEPS) - 1:
            self._finish()
        else:
            self._go_to(self._current + 1)

    def _finish(self):
        if not self.name_edit.text().strip():
            self._go_to(0)
            self.name_edit.setFocus()
            return
        self.accept()

    # ── pasos ────────────────────────────────────────────────────────────

    def _step_essentials(self) -> QWidget:
        page, box = self._page()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("El nombre de tu mundo o relato…")
        box.addWidget(_field_block("Nombre del proyecto *", self.name_edit, "Lo único imprescindible."))

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("— Empezar en blanco —", "")
        for key, preset in CREATIVE_PRESETS.items():
            self.preset_combo.addItem(f"{preset['label']} — {preset['description']}", key)
        box.addWidget(_field_block(
            "Partir de un preset", self.preset_combo,
            "Una plantilla creativa que rellena valores razonables. Opcional.",
        ))

        self.premise_edit = _make_textarea("", 70)
        self.premise_edit.setPlaceholderText("Ej: En un mundo donde los sueños son territorio compartido…")
        box.addWidget(_field_block("Premisa central", self.premise_edit, "La idea-semilla, en una o dos frases."))

        self.summary_edit = _make_textarea("", 60)
        self.summary_edit.setPlaceholderText("Un resumen de una o dos líneas para ti.")
        box.addWidget(_field_block("Resumen corto", self.summary_edit))
        box.addStretch(1)
        return page

    def _step_genre(self) -> QWidget:
        page, box = self._page()
        self.genre_combo = _make_combo(GENRE_OPTIONS)
        box.addWidget(_field_block("Género principal", self.genre_combo))
        self.subgenres = TagInput()
        box.addWidget(_field_block("Subgéneros", self.subgenres, "Escribe y pulsa Enter para añadir."))
        self.audience_combo = _make_combo(AUDIENCE_OPTIONS)
        box.addWidget(_field_block("Público objetivo", self.audience_combo))
        self.format_combo = _make_combo(FORMAT_OPTIONS)
        box.addWidget(_field_block("Formato narrativo", self.format_combo, "Novela, campaña de rol, serie…"))
        self.status_combo = _make_combo(STATUS_OPTIONS)
        box.addWidget(_field_block("Estado de desarrollo", self.status_combo))
        self.language_edit = QLineEdit("es")
        self.language_edit.setPlaceholderText("es, en, fr…")
        box.addWidget(_field_block("Idioma principal", self.language_edit))
        self.wb_check = QCheckBox("Activar worldbuilding por capas causales")
        box.addWidget(self.wb_check)
        wb_info = QLabel(
            "Si lo activas, podrás organizar el mundo en anillos concéntricos:\n"
            "Metafísica → Leyes → Materia → Geografía → Vida → Cultura → …"
        )
        wb_info.setWordWrap(True)
        wb_info.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;")
        box.addWidget(wb_info)
        box.addStretch(1)
        return page

    def _step_chronology(self) -> QWidget:
        page, box = self._page()
        self.chrono_mode = QComboBox()
        for raw, label in [
            ("none", "Sin calendario"),
            ("vague_periods", "Periodos vagos (Antigüedad, Actualidad…)"),
            ("full_calendar", "Calendario completo (eras, meses, días)"),
        ]:
            self.chrono_mode.addItem(label, raw)
        self.chrono_mode.currentIndexChanged.connect(self._sync_chrono_visibility)
        box.addWidget(_field_block("¿Cómo mide el tiempo tu mundo?", self.chrono_mode))

        self.chrono_name = QLineEdit()
        self.chrono_name.setPlaceholderText("Nombre del calendario")
        self._chrono_name_block = _field_block("Nombre del calendario", self.chrono_name)
        box.addWidget(self._chrono_name_block)

        self.chrono_desc = _make_textarea("", 56)
        self.chrono_desc.setPlaceholderText("Reglas temporales o contexto del calendario")
        self._chrono_desc_block = _field_block("Descripción", self.chrono_desc)
        box.addWidget(self._chrono_desc_block)

        self.chrono_periods = _make_textarea("", 74)
        self.chrono_periods.setPlaceholderText("Antigüedad\nHistoria reciente\nActualidad")
        self._periods_block = _field_block("Periodos vagos", self.chrono_periods, "Uno por línea.")
        box.addWidget(self._periods_block)

        self.chrono_eras = _make_textarea("", 74)
        self.chrono_eras.setPlaceholderText("Era Antigua: 900\nEra Imperial: 1200\nEra de la Ruptura: 40")
        self.chrono_eras.textChanged.connect(self._sync_chrono_picker)
        self._eras_block = _field_block("Eras pasadas", self.chrono_eras, "Nombre: duración (años).")
        box.addWidget(self._eras_block)

        self.chrono_months = _make_textarea("", 84)
        self.chrono_months.setPlaceholderText("Enero: 31\nFebrero: 28\nMarzo: 31…")
        self.chrono_months.textChanged.connect(self._sync_chrono_picker)
        self._months_block = _field_block("Meses", self.chrono_months, "Nombre: días.")
        box.addWidget(self._months_block)

        self.chrono_weekdays = _make_textarea("", 62)
        self.chrono_weekdays.setPlaceholderText("Lunes\nMartes\nMiércoles…")
        self._weekdays_block = _field_block("Días de la semana", self.chrono_weekdays)
        box.addWidget(self._weekdays_block)

        self.chrono_days = QSpinBox()
        self.chrono_days.setRange(1, 999)
        self.chrono_days.setValue(30)
        self._days_block = _field_block("Días por mes (por defecto)", self.chrono_days)
        box.addWidget(self._days_block)

        self.chrono_year = QSpinBox()
        self.chrono_year.setRange(-999999, 999999)
        self.chrono_year.setValue(1)
        self._year_block = _field_block("Año actual", self.chrono_year)
        box.addWidget(self._year_block)

        self.chrono_date = CalendarDatePicker(compact=True)
        self.chrono_date.setObjectName("wizardCurrentCalendarDatePicker")
        self._date_block = _field_block("Fecha actual", self.chrono_date)
        box.addWidget(self._date_block)

        note = QLabel("La IA podrá sugerir cambios después, pero nada se aplica sin tu revisión.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;")
        box.addWidget(note)
        box.addStretch(1)
        self._sync_chrono_visibility()
        return page

    def _sync_chrono_visibility(self):
        mode = str(self.chrono_mode.currentData() or "none")
        vague = mode == "vague_periods"
        full = mode == "full_calendar"
        for blk in (self._chrono_name_block, self._chrono_desc_block):
            blk.setVisible(mode != "none")
        self._periods_block.setVisible(vague)
        for blk in (self._eras_block, self._months_block, self._weekdays_block,
                    self._days_block, self._year_block, self._date_block):
            blk.setVisible(full)
        if full:
            self._sync_chrono_picker()

    def _sync_chrono_picker(self):
        if not hasattr(self, "chrono_date"):
            return
        current = self.chrono_date.date()
        eras = _names_from_length_text(self.chrono_eras.toPlainText())
        months = _names_from_length_text(self.chrono_months.toPlainText())
        weekdays = _names_from_length_text(self.chrono_weekdays.toPlainText())
        self.chrono_date.set_calendar({
            "mode": "full_calendar",
            "eras": eras, "past_eras": eras, "months": months, "weekdays": weekdays,
            "era_lengths": self.chrono_eras.toPlainText(),
            "month_lengths": self.chrono_months.toPlainText(),
            "days_per_month": self.chrono_days.value(),
            "current_year": self.chrono_year.value(),
        })
        self.chrono_date.set_date(current)

    def _step_intent(self) -> QWidget:
        page, box = self._page()
        self.reader_promise = _make_textarea("", 56)
        self.reader_promise.setPlaceholderText("Ej: Descubrirás que la realidad es una ilusión compartida…")
        box.addWidget(_field_block("Promesa al lector", self.reader_promise, "¿Qué experiencia garantizas?"))
        self.central_question = _make_textarea("", 56)
        self.central_question.setPlaceholderText("Ej: ¿Puede uno ser libre si recuerda cada error?")
        box.addWidget(_field_block("Pregunta dramática central", self.central_question))
        self.desired_emotions = TagInput()
        box.addWidget(_field_block(
            "Emociones que buscas provocar", self.desired_emotions,
            "Ej: " + ", ".join(EMOTION_OPTIONS[:6]) + "…",
        ))
        self.aftertaste = _make_textarea("", 48)
        self.aftertaste.setPlaceholderText("Ej: Una mezcla de melancolía y extrañeza…")
        box.addWidget(_field_block("Sensación final (aftertaste)", self.aftertaste))
        row_o, self.originality = _slider_row(5)
        box.addWidget(_field_block("Originalidad", row_o, "0 = convencional · 10 = experimental"))
        row_a, self.ambiguity = _slider_row(5)
        box.addWidget(_field_block("Ambigüedad", row_a, "0 = explícito · 10 = enigmático"))
        self.impact_types = TagInput()
        box.addWidget(_field_block(
            "Tipos de impacto", self.impact_types,
            "Ej: " + ", ".join(IMPACT_OPTIONS[:6]) + "…",
        ))
        box.addStretch(1)
        return page

    def _step_engine(self) -> QWidget:
        page, box = self._page()
        self.conflict_sources = TagInput()
        box.addWidget(_field_block(
            "Fuentes de conflicto", self.conflict_sources,
            "Ej: " + ", ".join(CONFLICT_OPTIONS[:6]) + "…",
        ))
        self.tension_combo = _make_combo(TENSION_OPTIONS)
        box.addWidget(_field_block("Tensión dominante", self.tension_combo))
        self.progression_combo = _make_combo(PROGRESSION_OPTIONS)
        box.addWidget(_field_block("Mecanismo de avance", self.progression_combo))
        self.change_combo = _make_combo(CHANGE_OPTIONS)
        box.addWidget(_field_block("Cómo cambian los personajes", self.change_combo))
        self.escalation_combo = _make_combo(ESCALATION_OPTIONS)
        box.addWidget(_field_block("Escalada", self.escalation_combo))
        row_ag, self.agency = _slider_row(5)
        box.addWidget(_field_block("Agencia de personajes", row_ag, "0 = arrastrados · 10 = deciden su destino"))
        row_ca, self.causality = _slider_row(5)
        box.addWidget(_field_block("Causalidad", row_ca, "0 = flexible · 10 = estricta (todo tiene consecuencia)"))
        box.addStretch(1)
        return page

    def _step_style(self) -> QWidget:
        page, box = self._page()
        self.style_edit = _make_textarea("", 56)
        self.style_edit.setPlaceholderText("Ej: prosa sobria con destellos líricos…")
        box.addWidget(_field_block("Estilo narrativo", self.style_edit))
        self.tone_edit = _make_textarea("", 48)
        self.tone_edit.setPlaceholderText("Ej: melancólico pero con humor seco…")
        box.addWidget(_field_block("Tono general", self.tone_edit))
        self.distance_combo = _make_combo(DISTANCE_OPTIONS)
        box.addWidget(_field_block("Distancia narrativa", self.distance_combo))
        row_dd, self.desc_density = _slider_row(5)
        box.addWidget(_field_block("Densidad descriptiva", row_dd, "0 = seca · 10 = sensorial"))
        row_cd, self.conc_density = _slider_row(5)
        box.addWidget(_field_block("Densidad conceptual", row_cd, "0 = ligera · 10 = reflexiva"))
        row_st, self.subtext = _slider_row(5)
        box.addWidget(_field_block("Subtexto", row_st, "0 = directo · 10 = muy implícito"))
        self.dialogue_styles = TagInput()
        box.addWidget(_field_block("Tipos de diálogo", self.dialogue_styles, "Ej: " + ", ".join(DIALOGUE_OPTIONS[:5]) + "…"))
        self.exposition_modes = TagInput()
        box.addWidget(_field_block("Modos de exposición", self.exposition_modes, "Ej: " + ", ".join(EXPOSITION_OPTIONS[:5]) + "…"))
        self.recurring_imagery = TagInput()
        box.addWidget(_field_block("Imágenes / motivos recurrentes", self.recurring_imagery))
        self.forbidden_style = ListEditor()
        box.addWidget(_field_block("Prohibiciones de estilo", self.forbidden_style))
        box.addStretch(1)
        return page

    def _step_rules(self) -> QWidget:
        page, box = self._page()
        box.addWidget(self._section("Canon", "Lo que la IA debe respetar."))
        self.hard_rules = ListEditor()
        box.addWidget(_field_block("Reglas duras (inviolables)", self.hard_rules))
        self.soft_rules = ListEditor()
        box.addWidget(_field_block("Preferencias blandas", self.soft_rules))
        row_cs, self.continuity = _slider_row(7)
        box.addWidget(_field_block("Continuidad", row_cs, "0 = flexible · 10 = estricta"))
        self.contradiction_combo = _make_combo(CONTRADICTION_OPTIONS)
        box.addWidget(_field_block("Política de contradicciones", self.contradiction_combo))
        self.world_rules = ListEditor()
        box.addWidget(_field_block("Reglas de mundo", self.world_rules))
        self.character_rules = ListEditor()
        box.addWidget(_field_block("Reglas de personajes", self.character_rules))
        self.timeline_rules = ListEditor()
        box.addWidget(_field_block("Reglas de cronología", self.timeline_rules))

        box.addWidget(self._section("Evitar", "Lo que NO quieres ver en la obra."))
        self.avoid_tropes = ListEditor()
        box.addWidget(_field_block("Tropos a evitar", self.avoid_tropes))
        self.avoid_solutions = ListEditor()
        box.addWidget(_field_block("Soluciones a evitar", self.avoid_solutions))
        self.avoid_style = ListEditor()
        box.addWidget(_field_block("Tics de estilo a evitar", self.avoid_style))
        self.avoid_tones = ListEditor()
        box.addWidget(_field_block("Tonos prohibidos", self.avoid_tones))
        self.avoid_phrases = ListEditor()
        box.addWidget(_field_block("Frases o gestos prohibidos", self.avoid_phrases))
        box.addStretch(1)
        return page

    def _step_ai(self) -> QWidget:
        page, box = self._page()
        self.ai_role = _make_combo_keyed(AI_ROLE_KEYS, AI_ROLE_OPTIONS, "coauthor")
        box.addWidget(_field_block("Rol por defecto", self.ai_role, "Cómo se comporta la IA al colaborar."))
        row_ag, self.ai_aggression = _slider_row(5)
        box.addWidget(_field_block("Agresividad creativa", row_ag, "0 = mínima · 10 = radical"))
        self.ai_num = QSpinBox()
        self.ai_num.setRange(1, 5)
        self.ai_num.setValue(3)
        box.addWidget(_field_block("Propuestas por defecto", self.ai_num))
        self.ai_output = _make_combo_keyed(
            [v for _, v in AI_OUTPUT_OPTIONS], [l for l, _ in AI_OUTPUT_OPTIONS], "contrastive_options",
        )
        box.addWidget(_field_block("Tipo de respuesta", self.ai_output))
        self.ai_uncertainty = _make_combo_keyed(
            [v for _, v in AI_UNCERTAINTY_OPTIONS], [l for l, _ in AI_UNCERTAINTY_OPTIONS], "conservative_proposal",
        )
        box.addWidget(_field_block("Cuando falte contexto", self.ai_uncertainty))
        self.ai_strategy = _make_combo_keyed(AI_STRATEGY_KEYS, AI_STRATEGY_OPTIONS, "profundizar")
        box.addWidget(_field_block("Estrategia creativa", self.ai_strategy))
        self.ai_depth = _make_combo_keyed(
            [v for _, v in AI_DEPTH_OPTIONS], [l for l, _ in AI_DEPTH_OPTIONS], "balanced",
        )
        box.addWidget(_field_block("Profundidad de contexto", self.ai_depth))
        box.addStretch(1)
        return page

    def _section(self, title: str, subtitle: str = "") -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(2)
        t = QLabel(title.upper())
        t.setStyleSheet(
            f"color: {GOLD_DEEP}; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; "
            f"background: transparent; border: none;"
        )
        v.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;")
            v.addWidget(s)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {LINE}; border: none;")
        v.addWidget(line)
        return wrap

    # ── recogida de datos ─────────────────────────────────────────────────

    @staticmethod
    def _t(widget) -> str:
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return widget.text().strip()

    def collect_config(self) -> dict:
        """Devuelve el dict de overrides para ProjectService.create()."""
        chronology = self._collect_chronology()
        return {
            "name": self._t(self.name_edit),
            "preset": self.preset_combo.currentData() or "",
            "creative_config": {
                "core_premise": self._t(self.premise_edit),
                "short_summary": self._t(self.summary_edit),
                "narrative_style": self._t(self.style_edit),
                "target_audience": self.audience_combo.currentText(),
                "format": self.format_combo.currentText(),
                "development_status": self.status_combo.currentText() or "Idea inicial",
                "creative_intent": {
                    "reader_promise": self._t(self.reader_promise),
                    "central_question": self._t(self.central_question),
                    "desired_emotions": self.desired_emotions.value(),
                    "aftertaste": self._t(self.aftertaste),
                    "originality": self.originality.value(),
                    "ambiguity": self.ambiguity.value(),
                    "impact_types": self.impact_types.value(),
                },
                "narrative_engine": {
                    "conflict_sources": self.conflict_sources.value(),
                    "dominant_tension": self.tension_combo.currentText(),
                    "progression_mechanism": self.progression_combo.currentText(),
                    "character_change": self.change_combo.currentText(),
                    "escalation": self.escalation_combo.currentText(),
                    "character_agency": self.agency.value(),
                    "causality": self.causality.value(),
                },
                "poetics": {
                    "narrative_distance": self.distance_combo.currentText(),
                    "description_density": self.desc_density.value(),
                    "conceptual_density": self.conc_density.value(),
                    "subtext_level": self.subtext.value(),
                    "dialogue_styles": self.dialogue_styles.value(),
                    "exposition_modes": self.exposition_modes.value(),
                    "recurring_imagery": self.recurring_imagery.value(),
                    "forbidden_style_habits": self.forbidden_style.value(),
                },
                "canon": {
                    "hard_rules": self.hard_rules.value(),
                    "soft_preferences": self.soft_rules.value(),
                    "continuity_strictness": self.continuity.value(),
                    "contradiction_policy": self.contradiction_combo.currentText(),
                    "world_rules": self.world_rules.value(),
                    "character_rules": self.character_rules.value(),
                    "timeline_rules": self.timeline_rules.value(),
                },
                "negative_space": {
                    "avoid_tropes": self.avoid_tropes.value(),
                    "avoid_solutions": self.avoid_solutions.value(),
                    "avoid_style_habits": self.avoid_style.value(),
                    "avoid_tones": self.avoid_tones.value(),
                    "avoid_phrases": self.avoid_phrases.value(),
                },
            },
            "genre": {
                "primary_genre": self.genre_combo.currentText(),
                "subgenres": self.subgenres.value(),
            },
            "tone": {"narrative_tone": self._t(self.tone_edit)},
            "ai": {
                "default_role": self.ai_role.currentData() or "coauthor",
                "change_aggressiveness": self.ai_aggression.value(),
                "default_num_options": self.ai_num.value(),
                "output_mode": self.ai_output.currentData() or "contrastive_options",
                "uncertainty_policy": self.ai_uncertainty.currentData() or "conservative_proposal",
                "default_strategy": self.ai_strategy.currentData() or "profundizar",
                "context_depth": self.ai_depth.currentData() or "balanced",
            },
            "primary_language": self._t(self.language_edit) or "es",
            "worldbuilding_active": self.wb_check.isChecked(),
            "project_chronology": chronology,
        }

    def _collect_chronology(self) -> dict:
        mode = str(self.chrono_mode.currentData() or "none")
        periods = [l.strip() for l in self.chrono_periods.toPlainText().splitlines() if l.strip()]
        eras = _names_from_length_text(self.chrono_eras.toPlainText())
        months = _names_from_length_text(self.chrono_months.toPlainText())
        weekdays = _names_from_length_text(self.chrono_weekdays.toPlainText())
        return {
            "calendar_name": self._t(self.chrono_name),
            "description": self._t(self.chrono_desc),
            "calendar_system": mode,
            "metadata": {
                "mode": mode,
                "periods": periods or (["Antiguedad", "Historia reciente", "Actualidad"] if mode == "vague_periods" else []),
                "eras": eras,
                "past_eras": eras,
                "era_lengths": self.chrono_eras.toPlainText(),
                "months": months,
                "month_lengths": self.chrono_months.toPlainText(),
                "weekdays": weekdays,
                "days_per_month": self.chrono_days.value(),
                "months_per_year": len(months),
                "current_year": self.chrono_year.value(),
                "current_date": self.chrono_date.date(),
                "units": ["era", "ano", "mes", "dia"] if mode == "full_calendar" else (["periodo narrativo"] if mode == "vague_periods" else []),
                "supports_exact_dates": mode == "full_calendar",
                "date_resolution": "dia" if mode == "full_calendar" else ("periodo" if mode == "vague_periods" else ""),
            },
        }

    # ── volcado al proyecto ────────────────────────────────────────────────

    def apply_to_project(self, project: Project) -> None:
        cfg = self.collect_config()

        project.name = cfg.get("name", project.name)
        project.primary_language = cfg.get("primary_language", project.primary_language)
        project.worldbuilding_active = cfg.get("worldbuilding_active", project.worldbuilding_active)

        self._apply_chronology(project, cfg.get("project_chronology", {}))

        cc = project.creative_config
        cc_data = cfg.get("creative_config", {})
        cc.core_premise = cc_data.get("core_premise", "")
        cc.short_summary = cc_data.get("short_summary", "")
        cc.narrative_style = cc_data.get("narrative_style", "")
        cc.target_audience = cc_data.get("target_audience", "")
        cc.format = cc_data.get("format", "")
        cc.development_status = cc_data.get("development_status", "")

        for attr in ("creative_intent", "narrative_engine", "poetics", "canon", "negative_space"):
            incoming = cc_data.get(attr, {})
            if any(self._truthy(v) for v in incoming.values()):
                existing = dict(getattr(cc, attr, {}) or {})
                existing.update({k: v for k, v in incoming.items() if self._truthy(v)})
                setattr(cc, attr, existing)

        genre_data = cfg.get("genre", {})
        project.genre.primary_genre = genre_data.get("primary_genre", "")
        project.genre.subgenres = genre_data.get("subgenres", [])

        project.tone.narrative_tone = cfg.get("tone", {}).get("narrative_tone", "")

        ai_data = cfg.get("ai", {})
        project.ai.default_role = ai_data.get("default_role", "coauthor")
        project.ai.change_aggressiveness = ai_data.get("change_aggressiveness", 5)
        project.ai.default_num_options = ai_data.get("default_num_options", 3)
        project.ai.output_mode = ai_data.get("output_mode", "contrastive_options")
        if hasattr(project.ai, "uncertainty_policy"):
            project.ai.uncertainty_policy = ai_data.get("uncertainty_policy", "conservative_proposal")
        project.ai.default_strategy = ai_data.get("default_strategy", "profundizar")
        if hasattr(project.ai, "context_depth"):
            project.ai.context_depth = ai_data.get("context_depth", "balanced")

        preset = cfg.get("preset", "")
        if preset:
            apply_preset_to_project(project, preset)

    @staticmethod
    def _truthy(value) -> bool:
        if isinstance(value, (int, float)):
            return True  # sliders 0..10 son significativos aunque sean 0
        return bool(value)

    def _apply_chronology(self, project: Project, chronology_data: dict) -> None:
        if not isinstance(chronology_data, dict):
            return
        current = getattr(project, "project_chronology", None) or ProjectChronology()
        current.calendar_name = chronology_data.get("calendar_name", current.calendar_name)
        current.description = chronology_data.get("description", current.description)
        current.calendar_system = chronology_data.get("calendar_system", current.calendar_system)
        metadata = dict(getattr(current, "metadata", {}) or {})
        incoming_meta = chronology_data.get("metadata")
        if isinstance(incoming_meta, dict):
            metadata.update(incoming_meta)
        mode = str(metadata.get("mode") or chronology_data.get("calendar_system") or "none")
        if mode == "vague_periods":
            periods = metadata.get("periods") or ["Antiguedad", "Historia reciente", "Actualidad"]
            metadata.update({
                "periods": list(periods), "eras": list(periods),
                "units": ["periodo narrativo"], "supports_exact_dates": False,
                "date_resolution": "periodo",
            })
        elif mode == "full_calendar":
            months = metadata.get("months") or [
                "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
            ]
            weekdays = metadata.get("weekdays") or [
                "Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo",
            ]
            metadata.update({
                "months": list(months), "weekdays": list(weekdays),
                "month_lengths": metadata.get("month_lengths") or {str(m): 30 for m in months},
                "era_lengths": metadata.get("era_lengths") or {str(e): 100 for e in metadata.get("eras", [])},
                "current_date": metadata.get("current_date") or {
                    "era": str((metadata.get("eras") or ["Actualidad"])[-1]),
                    "year": metadata.get("current_year", 1),
                    "month": str(months[0] if months else ""), "day": 1,
                },
                "months_per_year": len(months), "units": ["era", "ano", "mes", "dia"],
                "supports_exact_dates": True, "date_resolution": "dia",
            })
        current.metadata = metadata
        project.project_chronology = current


__all__ = ["ProjectWizard"]
