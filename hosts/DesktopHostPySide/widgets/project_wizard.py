"""Asistente de creación de proyecto — custom, fluido, con el design-system (PA04).

Reemplaza el QWizard nativo por un asistente propio con el lenguaje visual de
Dendro: un RAIL de pasos a la izquierda, cabecera con micro-ayuda, transición
fluida y botones de oro.

PA04: el wizard solo pide el **subset esencial de Identidad** (premisa, resumen,
género, subgéneros, formato, público, idioma, estado) más la cronología. El
resto de los 30 campos canónicos se completan luego en el panel de configuración
(``CreativeConfigPanel``). Un preset opcional rellena las 5 secciones.

API pública para ``main_window``:
- señales ``accepted`` / ``cancelled``
- ``collect_config()`` → dict (incluye ``name`` y la cronología)
- ``apply_to_project(project)`` → vuelca al proyecto recién creado
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
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
    FORMATO_SUGERENCIAS,
    GENERO_SUGERENCIAS,
    PUBLICO_SUGERENCIAS,
    CreativeConfigPanel,
    TagInput,
    _make_combo_editable,
    _make_combo_keyed,
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
from hosts.DesktopHostPySide.widgets.field_help import FieldHelp
from packages.domain.creative_config import ESTADO_OPCIONES
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


def _field_block(label: str, widget: QWidget, hint: str = "", help_key: str = "") -> QWidget:
    """Bloque de campo vertical: etiqueta (+ icono ⓘ) + (ayuda) + widget."""
    block = QWidget()
    box = QVBoxLayout(block)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(5)

    head = QHBoxLayout()
    head.setContentsMargins(0, 0, 0, 0)
    head.setSpacing(6)
    lab = QLabel(label)
    lab.setStyleSheet(
        f"color: {INK_STRONG}; font-size: 13px; font-weight: 700; background: transparent; border: none;"
    )
    head.addWidget(lab)
    if help_key:
        head.addWidget(FieldHelp(help_key))
    head.addStretch(1)
    box.addLayout(head)

    if hint:
        hl = QLabel(hint)
        hl.setWordWrap(True)
        hl.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        box.addWidget(hl)
    box.addWidget(widget)
    return block


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


class ProjectWizard(QFrame):
    """Asistente de creación de proyecto (custom; embebible en overlay modal)."""

    accepted = Signal()
    cancelled = Signal()

    # (clave, título, micro-ayuda)
    STEPS = [
        ("essentials", "Tu proyecto", "Lo esencial para empezar. Solo el nombre es obligatorio."),
        ("identidad", "Identidad", "Qué clase de obra es y para quién. El resto se afina luego."),
        ("chronology", "Cronología", "¿Cómo mide el tiempo tu mundo? Puedes no usar calendario."),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("projectWizard")
        self.setMinimumSize(960, 640)
        self.setMaximumSize(1040, 720)
        self.setStyleSheet(
            f"QFrame#projectWizard {{ background: {PAPER}; border: 1px solid {LINE}; "
            f"border-radius: 12px; }}"
        )

        self._steps: list[QWidget] = []
        self._rail_items: list[_RailItem] = []
        self._current = 0
        self._advanced = False  # modo avanzado: rellenar las 5 secciones en el wizard

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

        for builder in (self._step_essentials, self._step_identidad, self._step_chronology):
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
        self._cancel_btn.clicked.connect(self.cancelled.emit)
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
        self._step_title.setText(self._step_title_for(index))
        self._step_hint.setText(self._step_hint_for(index))
        self._step_counter.setText(f"Paso {index + 1} de {len(self.STEPS)}")
        self._progress.setValue(index + 1)
        # Cambio de paso INSTANTÁNEO: nada de QGraphicsOpacityEffect aquí (provoca
        # access violations al destruir el wizard). Ver memoria
        # [[qt-avoid-graphics-effects-on-dynamic-widgets]].
        self._refresh_nav()

    def _step_title_for(self, index: int) -> str:
        if index == 1 and getattr(self, "_advanced", False):
            return "Configuración completa"
        return self.STEPS[index][1]

    def _step_hint_for(self, index: int) -> str:
        if index == 1 and getattr(self, "_advanced", False):
            return "Rellena las 5 secciones creativas ahora. Todo sigue editable luego."
        return self.STEPS[index][2]

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
        self.accepted.emit()

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

        self.advanced_check = QCheckBox(
            "Configuración avanzada: rellenar todas las secciones ahora"
        )
        self.advanced_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.advanced_check.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 13px; font-weight: 600; "
            f"background: transparent; border: none;"
        )
        self.advanced_check.toggled.connect(self._on_advanced_toggled)
        box.addWidget(self.advanced_check)
        adv_hint = QLabel(
            "Si no, solo se pide lo esencial; el resto se completa luego en Configuración."
        )
        adv_hint.setWordWrap(True)
        adv_hint.setStyleSheet(
            f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        box.addWidget(adv_hint)

        self.premise_edit = _make_textarea("", 70)
        self.premise_edit.setPlaceholderText("Ej: En un mundo donde los sueños son territorio compartido…")
        box.addWidget(_field_block(
            "Premisa", self.premise_edit, "La idea-semilla, en una o dos frases.", help_key="premisa"))

        self.summary_edit = _make_textarea("", 70)
        self.summary_edit.setPlaceholderText("1–3 párrafos de contexto global para la IA.")
        box.addWidget(_field_block(
            "Resumen corto", self.summary_edit, help_key="resumen_corto"))
        box.addStretch(1)
        return page

    def _step_identidad(self) -> QWidget:
        page, box = self._page()
        # El paso 2 alterna entre el formulario esencial (modo básico) y el panel
        # creativo completo de 30 campos (modo avanzado), según el checkbox del paso 1.
        self._identidad_stack = QStackedWidget()
        self._identidad_stack.addWidget(self._build_identidad_simple())
        # Modo avanzado: panel completo sobre un Project "scratch"; al crear, se
        # vuelca con panel.apply_to_project(project_real). Reutiliza toda la UI/lógica.
        self._adv_scratch = Project()
        self._adv_panel = CreativeConfigPanel(self._adv_scratch)
        self._identidad_stack.addWidget(self._adv_panel)
        box.addWidget(self._identidad_stack, 1)
        return page

    def _build_identidad_simple(self) -> QWidget:
        simple = QWidget()
        simple.setStyleSheet("background: transparent;")
        box = QVBoxLayout(simple)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(15)
        self.genre_combo = _make_combo_editable(GENERO_SUGERENCIAS)
        box.addWidget(_field_block("Género principal", self.genre_combo, help_key="genero_principal"))
        self.subgenres = TagInput()
        box.addWidget(_field_block(
            "Subgéneros", self.subgenres, "Escribe y pulsa Enter para añadir.", help_key="subgeneros"))
        self.format_combo = _make_combo_editable(FORMATO_SUGERENCIAS)
        box.addWidget(_field_block(
            "Formato", self.format_combo, "Novela, campaña de rol, videojuego…", help_key="formato"))
        self.audience_combo = _make_combo_editable(PUBLICO_SUGERENCIAS)
        box.addWidget(_field_block("Público", self.audience_combo, help_key="publico"))
        self.language_edit = QLineEdit("es")
        self.language_edit.setPlaceholderText("es, en, fr…")
        box.addWidget(_field_block("Idioma principal", self.language_edit, help_key="idioma"))
        self.status_combo = _make_combo_keyed(ESTADO_OPCIONES)
        box.addWidget(_field_block("Estado", self.status_combo, help_key="estado"))
        box.addStretch(1)
        return simple

    def _on_advanced_toggled(self, checked: bool) -> None:
        self._advanced = bool(checked)
        if hasattr(self, "_identidad_stack"):
            self._identidad_stack.setCurrentIndex(1 if checked else 0)
        title = "Configuración completa" if checked else self.STEPS[1][1]
        if len(self._rail_items) > 1:
            self._rail_items[1].setText(f"  2   {title}")
        if self._current == 1:
            self._step_title.setText(title)
            self._step_hint.setText(self._step_hint_for(1))

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

    # ── recogida de datos ─────────────────────────────────────────────────

    @staticmethod
    def _t(widget) -> str:
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return widget.text().strip()

    def collect_config(self) -> dict:
        """Devuelve el dict con el nombre, la identidad esencial y la cronología."""
        chronology = self._collect_chronology()
        return {
            "name": self._t(self.name_edit),
            "preset": self.preset_combo.currentData() or "",
            "primary_language": self._t(self.language_edit) or "es",
            "worldbuilding_active": True,  # PA02: siempre activo
            "identidad": {
                "premisa": self._t(self.premise_edit),
                "resumen_corto": self._t(self.summary_edit),
                "genero_principal": self.genre_combo.currentText().strip(),
                "subgeneros": self.subgenres.value(),
                "formato": self.format_combo.currentText().strip(),
                "publico": self.audience_combo.currentText().strip(),
                "estado": self.status_combo.currentData() or "",
            },
            "project_chronology": chronology,
        }

    def _collect_chronology(self) -> dict:
        mode = str(self.chrono_mode.currentData() or "none")
        periods = [line.strip() for line in self.chrono_periods.toPlainText().splitlines() if line.strip()]
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
        project.worldbuilding_active = cfg.get("worldbuilding_active", project.worldbuilding_active)

        self._apply_chronology(project, cfg.get("project_chronology", {}))

        advanced = bool(getattr(self, "advanced_check", None) and self.advanced_check.isChecked())
        if advanced and getattr(self, "_adv_panel", None) is not None:
            # Modo avanzado: el panel escribe las 5 secciones + idioma + worldbuilding.
            self._adv_panel.apply_to_project(project)
        else:
            project.primary_language = cfg.get("primary_language", project.primary_language)
            # Subset de Identidad → creative_config.identidad (solo si la config
            # expone esa sección; los tests de cronología usan un mock plano).
            identidad = getattr(getattr(project, "creative_config", None), "identidad", None)
            if identidad is not None:
                for key, value in cfg.get("identidad", {}).items():
                    if self._truthy(value):
                        setattr(identidad, key, value)

        # Preset opcional: rellena las 5 secciones (solo campos vacíos; no pisa
        # lo que el usuario ya escribió, ni en modo básico ni avanzado).
        preset = cfg.get("preset", "")
        if preset:
            apply_preset_to_project(project, preset)

    @staticmethod
    def _truthy(value) -> bool:
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
