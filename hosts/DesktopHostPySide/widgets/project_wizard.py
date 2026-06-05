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
    """8-step project creation wizard (B40-T04)."""

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

        # Page 3: Direction
        p3 = self.page(3)
        promise = p3.promise_edit.toPlainText().strip()
        emotions = p3.emotions.value()
        aftertaste = p3.aftertaste_edit.toPlainText().strip()

        # Page 4: Narrative
        p4 = self.page(4)
        conflicts = p4.conflict_tags.value()
        tension = p4.tension_combo.currentText()
        progression = p4.progression_combo.currentText()
        agency = p4.agency_slider.value()

        # Page 5: Style
        p5 = self.page(5)
        style = p5.style_edit.toPlainText().strip()
        tone = p5.tone_edit.toPlainText().strip()
        distance = p5.distance_combo.currentText()
        density = p5.density_slider.value()

        # Page 6: Rules
        p6 = self.page(6)
        hard = p6.hard_rules.value()
        soft = p6.soft_rules.value()
        strictness = p6.strictness_slider.value()
        contradiction = p6.contradiction_combo.currentText()

        # Page 7: AI
        p7 = self.page(7)
        ai_role = p7.role_combo.currentData() or "coauthor"
        ai_aggression = p7.aggression_slider.value()
        ai_num = p7.num_spin.value()
        ai_output = p7.output_combo.currentData() or "contrastive_options"
        ai_strategy = p7.strategy_combo.currentData() or "profundizar"

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
        }

    def apply_to_project(self, project: Project) -> None:
        """Apply wizard results to an existing project."""
        cfg = self.collect_config()

        project.name = cfg.get("name", project.name)
        project.primary_language = cfg.get("primary_language", project.primary_language)
        project.worldbuilding_active = cfg.get("worldbuilding_active", project.worldbuilding_active)

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
