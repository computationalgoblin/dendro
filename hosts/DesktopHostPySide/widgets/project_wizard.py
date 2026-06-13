"""
Project creation wizard (B40-T04).

8-step QWizard that guides the user through initial project configuration.
Each step is optional. The wizard produces a config_overrides dict that
can be passed to ProjectService.create().
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from packages.domain.creative_presets import CREATIVE_PRESETS, apply_preset_to_project
from packages.domain.project import Project
from packages.domain.project_chronology import ProjectChronology
from hosts.DesktopHostPySide.widgets.calendar_date_picker import CalendarDatePicker


# ---------------------------------------------------------------------------
# Shared option lists (import from creative_config_panel)
# ---------------------------------------------------------------------------

from hosts.DesktopHostPySide.widgets.creative_config_panel import (
    AUDIENCE_OPTIONS,
    CHANGE_OPTIONS,
    CONTRADICTION_OPTIONS,
    CONFLICT_OPTIONS,
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
    TagInput,
    ListEditor,
)


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


# ---------------------------------------------------------------------------
# Wizard pages
# ---------------------------------------------------------------------------


class WelcomePage(QWizardPage):
    """Step 1: Name, preset, and basic info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Bienvenido al asistente de creación")
        self.setSubTitle("Dale a tu proyecto una identidad inicial. Todo es editable después.")

        layout = QVBoxLayout(self)

        # Project name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre del proyecto...")
        self.name_edit.textChanged.connect(self._validate)
        layout.addWidget(QLabel("Nombre del proyecto"))
        layout.addWidget(self.name_edit)

        # Preset
        layout.addWidget(QLabel("¿Partir de un preset?"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("— Sin preset (en blanco) —", "")
        for key, preset in CREATIVE_PRESETS.items():
            self.preset_combo.addItem(
                f"{preset['label']} — {preset['description']}", key
            )
        layout.addWidget(self.preset_combo)

        # Brief description
        layout.addWidget(QLabel("Descripción breve (opcional)"))
        self.premise_edit = QTextEdit()
        self.premise_edit.setMaximumHeight(60)
        self.premise_edit.setPlaceholderText(
            "Ej: En un mundo donde los sueños son territorio compartido..."
        )
        layout.addWidget(self.premise_edit)

        self.registerField("project_name*", self.name_edit)

    def _validate(self):
        self.completeChanged.emit()

    def isComplete(self):
        return len(self.name_edit.text().strip()) >= 1


class GenrePage(QWizardPage):
    """Step 2: Genre, subgenre, audience."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Género y audiencia")
        self.setSubTitle("Define el género principal y el público objetivo.")

        layout = QVBoxLayout(self)

        self.genre_combo = QComboBox()
        self.genre_combo.addItems(GENRE_OPTIONS)
        layout.addWidget(QLabel("Género principal"))
        layout.addWidget(self.genre_combo)

        self.subgenres = TagInput()
        layout.addWidget(QLabel("Subgéneros"))
        layout.addWidget(self.subgenres)

        self.audience_combo = QComboBox()
        self.audience_combo.addItems(AUDIENCE_OPTIONS)
        layout.addWidget(QLabel("Público objetivo"))
        layout.addWidget(self.audience_combo)


class WorldPage(QWizardPage):
    """Step 3: Worldbuilding, format, language."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Mundo y formato")
        self.setSubTitle("Formato narrativo y configuración de worldbuilding.")

        layout = QVBoxLayout(self)

        self.format_combo = QComboBox()
        self.format_combo.addItems(FORMAT_OPTIONS)
        layout.addWidget(QLabel("Formato narrativo"))
        layout.addWidget(self.format_combo)

        self.language_edit = QLineEdit("es")
        self.language_edit.setPlaceholderText("Código de idioma (es, en, fr...)")
        layout.addWidget(QLabel("Idioma principal"))
        layout.addWidget(self.language_edit)

        self.wb_check = QCheckBox("Activar worldbuilding por capas causales")
        layout.addWidget(self.wb_check)

        info = QLabel(
            "Si activas worldbuilding, podrás organizar tu mundo en capas:\n"
            "Metafísica → Leyes → Materia → Geografía → Vida → Cultura → ..."
        )
        info.setObjectName("mutedLabel")
        info.setWordWrap(True)
        layout.addWidget(info)


class ChronologyPage(QWizardPage):
    """Step 4: manual chronology/calendar baseline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Cronologia")
        self.setSubTitle("Elige si el proyecto no usa calendario, usa periodos vagos o necesita calendario completo.")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.mode_combo = QComboBox()
        for raw, label in [
            ("none", "No anadir calendario"),
            ("vague_periods", "Calendario vago"),
            ("full_calendar", "Calendario completo"),
        ]:
            self.mode_combo.addItem(label, raw)
        self.mode_combo.currentIndexChanged.connect(self._sync_mode_visibility)
        form.addRow("Modo", self.mode_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre del calendario")
        form.addRow("Nombre", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(58)
        self.description_edit.setPlaceholderText("Reglas temporales o contexto del calendario")
        form.addRow("Descripcion", self.description_edit)

        self.periods_label = QLabel("Periodos vagos")
        self.periods_edit = QTextEdit()
        self.periods_edit.setMaximumHeight(74)
        self.periods_edit.setPlaceholderText("Antiguedad\nHistoria reciente\nActualidad")
        form.addRow(self.periods_label, self.periods_edit)

        self.eras_label = QLabel("Eras pasadas")
        self.eras_edit = QTextEdit()
        self.eras_edit.setMaximumHeight(74)
        self.eras_edit.setPlaceholderText("Era Antigua: 900\nEra Imperial: 1200\nEra de la Ruptura: 40")
        self.eras_edit.textChanged.connect(self._sync_current_picker_calendar)
        form.addRow(self.eras_label, self.eras_edit)

        self.months_label = QLabel("Meses")
        self.months_edit = QTextEdit()
        self.months_edit.setMaximumHeight(90)
        self.months_edit.setPlaceholderText("Enero: 31\nFebrero: 28\nMarzo: 31...")
        self.months_edit.textChanged.connect(self._sync_current_picker_calendar)
        form.addRow(self.months_label, self.months_edit)

        self.weekdays_label = QLabel("Dias semana")
        self.weekdays_edit = QTextEdit()
        self.weekdays_edit.setMaximumHeight(64)
        self.weekdays_edit.setPlaceholderText("Lunes\nMartes\nMiercoles...")
        form.addRow(self.weekdays_label, self.weekdays_edit)

        self.days_label = QLabel("Dias por mes")
        self.days_per_month_spin = QSpinBox()
        self.days_per_month_spin.setRange(1, 999)
        self.days_per_month_spin.setValue(30)
        form.addRow(self.days_label, self.days_per_month_spin)

        self.year_label = QLabel("Ano actual")
        self.current_year_spin = QSpinBox()
        self.current_year_spin.setRange(-999999, 999999)
        self.current_year_spin.setValue(1)
        form.addRow(self.year_label, self.current_year_spin)

        self.current_date_label = QLabel("Fecha actual")
        self.current_date_picker = CalendarDatePicker(compact=True)
        self.current_date_picker.setObjectName("wizardCurrentCalendarDatePicker")
        form.addRow(self.current_date_label, self.current_date_picker)

        layout.addLayout(form)
        note = QLabel("La IA podra sugerir cambios despues, pero no se aplicaran sin revision.")
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._sync_mode_visibility()

    def _sync_mode_visibility(self):
        mode = str(self.mode_combo.currentData() or "none")
        vague = mode == "vague_periods"
        full = mode == "full_calendar"
        for widget in (self.periods_label, self.periods_edit):
            widget.setVisible(vague)
        for widget in (
            self.eras_label,
            self.eras_edit,
            self.months_label,
            self.months_edit,
            self.weekdays_label,
            self.weekdays_edit,
            self.days_label,
            self.days_per_month_spin,
            self.year_label,
            self.current_year_spin,
            self.current_date_label,
            self.current_date_picker,
        ):
            widget.setVisible(full)
        if full:
            self._sync_current_picker_calendar()

    def _sync_current_picker_calendar(self):
        if not hasattr(self, "current_date_picker"):
            return
        current = self.current_date_picker.date()
        eras = _names_from_length_text(self.eras_edit.toPlainText())
        months = _names_from_length_text(self.months_edit.toPlainText())
        weekdays = _names_from_length_text(self.weekdays_edit.toPlainText())
        self.current_date_picker.set_calendar({
            "mode": "full_calendar",
            "eras": eras,
            "past_eras": eras,
            "months": months,
            "weekdays": weekdays,
            "era_lengths": self.eras_edit.toPlainText(),
            "month_lengths": self.months_edit.toPlainText(),
            "days_per_month": self.days_per_month_spin.value(),
            "current_year": self.current_year_spin.value(),
        })
        self.current_date_picker.set_date(current)


class DirectionPage(QWizardPage):
    """Step 4: Creative direction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Dirección creativa")
        self.setSubTitle("¿Qué prometes al lector? ¿Qué emociones buscas?")

        layout = QVBoxLayout(self)

        self.promise_edit = QTextEdit()
        self.promise_edit.setMaximumHeight(50)
        self.promise_edit.setPlaceholderText(
            "Ej: Descubrirás que la realidad es una ilusión compartida..."
        )
        layout.addWidget(QLabel("Promesa al lector"))
        layout.addWidget(self.promise_edit)

        self.emotions = TagInput()
        layout.addWidget(QLabel("Emociones que buscas provocar"))
        layout.addWidget(self.emotions)

        self.aftertaste_edit = QTextEdit()
        self.aftertaste_edit.setMaximumHeight(40)
        self.aftertaste_edit.setPlaceholderText(
            "Ej: Una mezcla de melancolía y extrañeza..."
        )
        layout.addWidget(QLabel("Sensación final (aftertaste)"))
        layout.addWidget(self.aftertaste_edit)


class NarrativePage(QWizardPage):
    """Step 5: Narrative engine settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Motor narrativo")
        self.setSubTitle("Conflicto, tensión, avance, agencia.")

        layout = QVBoxLayout(self)

        self.conflict_tags = TagInput()
        layout.addWidget(QLabel("Fuentes de conflicto"))
        layout.addWidget(self.conflict_tags)

        from hosts.DesktopHostPySide.widgets.creative_config_panel import _make_combo, _make_slider

        self.tension_combo = _make_combo(TENSION_OPTIONS)
        layout.addWidget(QLabel("Tensión dominante"))
        layout.addWidget(self.tension_combo)

        self.progression_combo = _make_combo(PROGRESSION_OPTIONS)
        layout.addWidget(QLabel("Mecanismo de avance"))
        layout.addWidget(self.progression_combo)

        self.agency_slider, lbl = _make_slider(5)
        row = QHBoxLayout()
        row.addWidget(self.agency_slider)
        row.addWidget(lbl)
        layout.addWidget(QLabel("Agencia de personajes (0=baja, 10=alta)"))
        layout.addLayout(row)


class StylePage(QWizardPage):
    """Step 6: Style and poetics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Estilo y poética")
        self.setSubTitle("Tono, distancia narrativa, densidad.")

        layout = QVBoxLayout(self)

        from hosts.DesktopHostPySide.widgets.creative_config_panel import _make_combo, _make_slider, _make_textarea

        self.style_edit = _make_textarea("", 50)
        layout.addWidget(QLabel("Estilo narrativo"))
        layout.addWidget(self.style_edit)

        self.tone_edit = _make_textarea("", 50)
        layout.addWidget(QLabel("Tono general"))
        layout.addWidget(self.tone_edit)

        self.distance_combo = _make_combo(DISTANCE_OPTIONS)
        layout.addWidget(QLabel("Distancia narrativa"))
        layout.addWidget(self.distance_combo)

        self.density_slider, lbl = _make_slider(5)
        row = QHBoxLayout()
        row.addWidget(self.density_slider)
        row.addWidget(lbl)
        layout.addWidget(QLabel("Densidad descriptiva (0=seca, 10=sensorial)"))
        layout.addLayout(row)


class RulesPage(QWizardPage):
    """Step 7: Canon rules."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Reglas del canon")
        self.setSubTitle("Qué es inviolable para la IA y qué es flexible.")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Reglas duras (inviolables)"))
        self.hard_rules = ListEditor()
        layout.addWidget(self.hard_rules)

        layout.addWidget(QLabel("Preferencias blandas"))
        self.soft_rules = ListEditor()
        layout.addWidget(self.soft_rules)

        from hosts.DesktopHostPySide.widgets.creative_config_panel import _make_combo, _make_slider

        self.strictness_slider, lbl = _make_slider(7)
        row = QHBoxLayout()
        row.addWidget(self.strictness_slider)
        row.addWidget(lbl)
        layout.addWidget(QLabel("Continuidad (0=flexible, 10=estricta)"))
        layout.addLayout(row)

        self.contradiction_combo = _make_combo(CONTRADICTION_OPTIONS)
        layout.addWidget(QLabel("Contradicciones"))
        layout.addWidget(self.contradiction_combo)


class AIPage(QWizardPage):
    """Step 8: AI configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Configuración de IA")
        self.setSubTitle("Cómo quieres que colabore la IA.")

        layout = QVBoxLayout(self)

        from hosts.DesktopHostPySide.widgets.creative_config_panel import (
            AI_ROLE_OPTIONS,
            AI_ROLE_KEYS,
            AI_OUTPUT_OPTIONS,
            AI_UNCERTAINTY_OPTIONS,
            AI_STRATEGY_OPTIONS,
            AI_STRATEGY_KEYS,
            _make_combo_keyed,
            _make_slider,
        )

        self.role_combo = _make_combo_keyed(AI_ROLE_KEYS, AI_ROLE_OPTIONS, "coauthor")
        layout.addWidget(QLabel("Rol por defecto"))
        layout.addWidget(self.role_combo)

        self.aggression_slider, lbl = _make_slider(5)
        row = QHBoxLayout()
        row.addWidget(self.aggression_slider)
        row.addWidget(lbl)
        layout.addWidget(QLabel("Agresividad (0=mínima, 10=radical)"))
        layout.addLayout(row)

        self.num_spin = QSpinBox()
        self.num_spin.setRange(1, 5)
        self.num_spin.setValue(3)
        layout.addWidget(QLabel("Propuestas por defecto"))
        layout.addWidget(self.num_spin)

        self.output_combo = _make_combo_keyed(
            [v for _, v in AI_OUTPUT_OPTIONS],
            [l for l, _ in AI_OUTPUT_OPTIONS],
            "contrastive_options",
        )
        layout.addWidget(QLabel("Tipo de respuesta"))
        layout.addWidget(self.output_combo)

        self.strategy_combo = _make_combo_keyed(
            AI_STRATEGY_KEYS, AI_STRATEGY_OPTIONS, "profundizar"
        )
        layout.addWidget(QLabel("Estrategia creativa"))
        layout.addWidget(self.strategy_combo)


# ---------------------------------------------------------------------------
# Main Wizard
# ---------------------------------------------------------------------------


class ProjectWizard(QWizard):
    """Project creation wizard (B40-T04, H05 chronology)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo proyecto")
        self.setMinimumSize(600, 500)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setOption(QWizard.WizardOption.HaveCustomButton1, False)

        # Add pages
        self.addPage(WelcomePage())
        self.addPage(GenrePage())
        self.addPage(WorldPage())
        self.addPage(ChronologyPage())
        self.addPage(DirectionPage())
        self.addPage(NarrativePage())
        self.addPage(StylePage())
        self.addPage(RulesPage())
        self.addPage(AIPage())

    # ── Collect results ────────────────────────────────────────────

    def collect_config(self) -> dict:
        """Return a config_overrides dict for ProjectService.create()."""
        # Page 0: Welcome
        p0 = self.page(0)
        name = p0.name_edit.text().strip()
        preset_key = p0.preset_combo.currentData() or ""

        # Page 1: Genre
        p1 = self.page(1)
        genre = p1.genre_combo.currentText()
        subgenres = p1.subgenres.value()
        audience = p1.audience_combo.currentText()

        # Page 2: World
        p2 = self.page(2)
        fmt = p2.format_combo.currentText()
        lang = p2.language_edit.text().strip() or "es"
        wb = p2.wb_check.isChecked()

        # Page 3: Chronology
        p3 = self.page(3)
        mode = p3.mode_combo.currentData() or "none"
        periods = [line.strip() for line in p3.periods_edit.toPlainText().splitlines() if line.strip()]
        eras = _names_from_length_text(p3.eras_edit.toPlainText())
        months = _names_from_length_text(p3.months_edit.toPlainText())
        weekdays = _names_from_length_text(p3.weekdays_edit.toPlainText())
        chronology = {
            "calendar_name": p3.name_edit.text().strip(),
            "description": p3.description_edit.toPlainText().strip(),
            "calendar_system": mode,
            "metadata": {
                "mode": mode,
                "periods": periods or (["Antiguedad", "Historia reciente", "Actualidad"] if mode == "vague_periods" else []),
                "eras": eras,
                "past_eras": eras,
                "era_lengths": p3.eras_edit.toPlainText(),
                "months": months,
                "month_lengths": p3.months_edit.toPlainText(),
                "weekdays": weekdays,
                "days_per_month": p3.days_per_month_spin.value(),
                "months_per_year": len(months),
                "current_year": p3.current_year_spin.value(),
                "current_date": p3.current_date_picker.date(),
                "units": ["era", "ano", "mes", "dia"] if mode == "full_calendar" else (["periodo narrativo"] if mode == "vague_periods" else []),
                "supports_exact_dates": mode == "full_calendar",
                "date_resolution": "dia" if mode == "full_calendar" else ("periodo" if mode == "vague_periods" else ""),
            },
        }

        # Page 4: Direction
        p4 = self.page(4)
        promise = p4.promise_edit.toPlainText().strip()
        emotions = p4.emotions.value()
        aftertaste = p4.aftertaste_edit.toPlainText().strip()

        # Page 5: Narrative
        p5 = self.page(5)
        conflicts = p5.conflict_tags.value()
        tension = p5.tension_combo.currentText()
        progression = p5.progression_combo.currentText()
        agency = p5.agency_slider.value()

        # Page 6: Style
        p6 = self.page(6)
        style = p6.style_edit.toPlainText().strip()
        tone = p6.tone_edit.toPlainText().strip()
        distance = p6.distance_combo.currentText()
        density = p6.density_slider.value()

        # Page 7: Rules
        p7 = self.page(7)
        hard = p7.hard_rules.value()
        soft = p7.soft_rules.value()
        strictness = p7.strictness_slider.value()
        contradiction = p7.contradiction_combo.currentText()

        # Page 8: AI
        p8 = self.page(8)
        ai_role = p8.role_combo.currentData() or "coauthor"
        ai_aggression = p8.aggression_slider.value()
        ai_num = p8.num_spin.value()
        ai_output = p8.output_combo.currentData() or "contrastive_options"
        ai_strategy = p8.strategy_combo.currentData() or "profundizar"

        return {
            "name": name,
            "preset": preset_key,
            "creative_config": {
                "core_premise": p0.premise_edit.toPlainText().strip(),
                "narrative_style": style,
                "target_audience": audience,
                "format": fmt,
                "development_status": "Idea inicial",
                "creative_intent": {
                    "reader_promise": promise,
                    "desired_emotions": emotions,
                    "aftertaste": aftertaste,
                },
                "narrative_engine": {
                    "conflict_sources": conflicts,
                    "dominant_tension": tension,
                    "progression_mechanism": progression,
                    "character_agency": agency,
                },
                "poetics": {
                    "narrative_distance": distance,
                    "description_density": density,
                },
                "canon": {
                    "hard_rules": hard,
                    "soft_preferences": soft,
                    "continuity_strictness": strictness,
                    "contradiction_policy": contradiction,
                },
            },
            "genre": {
                "primary_genre": genre,
                "subgenres": subgenres,
            },
            "tone": {
                "narrative_tone": tone,
            },
            "ai": {
                "default_role": ai_role,
                "change_aggressiveness": ai_aggression,
                "default_num_options": ai_num,
                "output_mode": ai_output,
                "default_strategy": ai_strategy,
            },
            "primary_language": lang,
            "worldbuilding_active": wb,
            "project_chronology": chronology,
        }

    def apply_to_project(self, project: Project) -> None:
        """Apply wizard results to an existing project."""
        cfg = self.collect_config()

        project.name = cfg.get("name", project.name)
        project.primary_language = cfg.get("primary_language", project.primary_language)
        project.worldbuilding_active = cfg.get("worldbuilding_active", project.worldbuilding_active)
        chronology_data = cfg.get("project_chronology", {})
        if isinstance(chronology_data, dict):
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
                    "periods": list(periods),
                    "eras": list(periods),
                    "units": ["periodo narrativo"],
                    "supports_exact_dates": False,
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
                    "months": list(months),
                    "weekdays": list(weekdays),
                    "month_lengths": metadata.get("month_lengths") or {str(month): 30 for month in months},
                    "era_lengths": metadata.get("era_lengths") or {str(era): 100 for era in metadata.get("eras", [])},
                    "current_date": metadata.get("current_date") or {
                        "era": str((metadata.get("eras") or ["Actualidad"])[-1]),
                        "year": metadata.get("current_year", 1),
                        "month": str(months[0] if months else ""),
                        "day": 1,
                    },
                    "months_per_year": len(months),
                    "units": ["era", "ano", "mes", "dia"],
                    "supports_exact_dates": True,
                    "date_resolution": "dia",
                })
            current.metadata = metadata
            project.project_chronology = current

        cc = project.creative_config
        cc_data = cfg.get("creative_config", {})
        cc.core_premise = cc_data.get("core_premise", "")
        cc.narrative_style = cc_data.get("narrative_style", "")
        cc.target_audience = cc_data.get("target_audience", "")
        cc.format = cc_data.get("format", "")
        cc.development_status = cc_data.get("development_status", "")

        ci = cc_data.get("creative_intent", {})
        if any(ci.values()):
            cc.creative_intent = {k: v for k, v in ci.items() if v}

        ne = cc_data.get("narrative_engine", {})
        if any(ne.values()):
            cc.narrative_engine = {k: v for k, v in ne.items() if v}

        po = cc_data.get("poetics", {})
        if any(po.values()):
            cc.poetics = {k: v for k, v in po.items() if v}

        ca = cc_data.get("canon", {})
        if any(ca.values()):
            cc.canon = {k: v for k, v in ca.items() if v}

        genre_data = cfg.get("genre", {})
        project.genre.primary_genre = genre_data.get("primary_genre", "")
        project.genre.subgenres = genre_data.get("subgenres", [])

        tone_data = cfg.get("tone", {})
        project.tone.narrative_tone = tone_data.get("narrative_tone", "")

        ai_data = cfg.get("ai", {})
        project.ai.default_role = ai_data.get("default_role", "coauthor")
        project.ai.change_aggressiveness = ai_data.get("change_aggressiveness", 5)
        project.ai.default_num_options = ai_data.get("default_num_options", 3)
        project.ai.output_mode = ai_data.get("output_mode", "contrastive_options")
        project.ai.default_strategy = ai_data.get("default_strategy", "profundizar")

        # Apply preset if selected
        preset = cfg.get("preset", "")
        if preset:
            apply_preset_to_project(project, preset)
