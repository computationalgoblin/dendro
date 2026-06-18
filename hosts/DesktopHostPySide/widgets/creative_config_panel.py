"""
Creative config panel with 9 tabs (B40-T03).

Replaces the flat creative config section in ProjectPanel with a tabbed
interface covering: Basico, Direccion creativa, Narrativa, Estilo,
Reglas, IA, Evitar, Memoria creativa, Ramas.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Constants — option lists for dropdowns
# ---------------------------------------------------------------------------

GENRE_OPTIONS = [
    "", "Fantasía", "Ciencia ficción", "Terror", "Misterio", "Thriller",
    "Drama", "Romance", "Histórico", "Realismo mágico", "Weird fiction",
    "Distopía", "Otro",
]

FORMAT_OPTIONS = [
    "", "Novela", "Campaña de rol", "Videojuego narrativo", "Serie",
    "Cómic", "Mundo narrativo abierto", "Antología", "Otro",
]

STATUS_OPTIONS = [
    "", "Idea inicial", "Primer borrador", "En expansión",
    "En revisión", "Campaña activa", "Proyecto archivado",
]

AUDIENCE_OPTIONS = ["", "Todos", "Joven adulto", "Adulto"]

TENSION_OPTIONS = [
    "", "Suspense", "Fricción emocional", "Amenaza física",
    "Dilema ético", "Ironía dramática", "Misterio", "Paranoia social",
    "Conflicto político", "Terror psicológico", "Tensión romántica",
    "Tensión existencial",
]

PROGRESSION_OPTIONS = [
    "", "Revelación", "Pérdida", "Traición", "Descubrimiento",
    "Decisión irreversible", "Coste acumulativo", "Investigación",
    "Transformación personal", "Choque de intereses",
    "Consecuencia imprevista",
]

CHANGE_OPTIONS = [
    "", "Aprende", "Se corrompe", "Se endurece", "Se libera",
    "Fracasa", "Se transforma", "Se sacrifica",
    "Descubre verdad incómoda", "Pierde agencia", "Gana agencia",
]

ESCALATION_OPTIONS = [
    "", "Gradual", "Súbita", "Cíclica", "Fragmentaria",
    "Episódica", "Falsa calma con rupturas", "Lineal", "En espiral",
]

DISTANCE_OPTIONS = [
    "", "Muy cercana", "Cercana", "Media", "Observacional",
    "Distante", "Omnisciente", "Fragmentada", "Variable según escena",
]

DIALOGUE_OPTIONS = [
    "Naturalista", "Lacónico", "Teatral", "Poético", "Evasivo",
    "Irónico", "Barroco", "Directo", "Fragmentado", "Con mucho subtexto",
]

EXPOSITION_OPTIONS = [
    "Directa", "Dosificada", "Implícita", "Ambiental",
    "Mediante conflicto", "Mediante documentos", "Mediante diálogo",
    "Mediante acciones", "Mediante contradicciones",
]

CONTRADICTION_OPTIONS = [
    "Permitidas libremente", "Si son interesantes",
    "Solo si son intencionales", "No permitidas",
]

AI_ROLE_OPTIONS = [
    "Coautor", "Editor literario", "Dramaturgo",
    "Supervisor de continuidad", "Worldbuilder",
    "Analista de personajes", "Explorador", "Corrector conservador",
]

AI_ROLE_KEYS = [
    "coauthor", "editor", "dramaturgo", "supervisor",
    "worldbuilder", "analista", "explorador", "corrector",
]

AI_OUTPUT_OPTIONS = [
    ("Respuesta final pulida", "single"),
    ("Opciones contrastadas", "contrastive_options"),
    ("Diagnóstico + propuesta", "diagnosis"),
    ("Preguntas antes de crear", "questions"),
    ("Cambios mínimos", "minimal"),
    ("Propuesta estructurada", "structured"),
]

AI_UNCERTAINTY_OPTIONS = [
    ("Preguntar siempre", "ask"),
    ("Propuesta conservadora", "conservative_proposal"),
    ("Inventar libremente", "invent"),
    ("Marcar huecos", "mark_gaps"),
    ("Varias interpretaciones", "interpretations"),
]

AI_STRATEGY_OPTIONS = [
    "Profundizar", "Contrastar", "Complicar", "Extrañar",
    "Conectar con otra hoja/rama", "Reducir", "Intensificar",
    "Subvertir", "Hacer más coherente", "Hacer más ambiguo",
    "Hacer más emocional", "Hacer más extraño",
]

AI_STRATEGY_KEYS = [
    "profundizar", "contrastar", "complicar", "extranar",
    "conectar", "reducir", "intensificar", "subvertir",
    "coherente", "ambiguo", "emocional", "extrano",
]

AI_DEPTH_OPTIONS = [
    ("Rápido", "quick"), ("Equilibrado", "balanced"), ("Profundo", "deep"),
]

EMOTION_OPTIONS = [
    "Maravilla", "Inquietud", "Melancolía", "Tensión", "Ternura",
    "Fascinación", "Horror", "Catarsis", "Paranoia", "Extrañeza",
    "Euforia", "Tristeza", "Esperanza", "Fatalidad", "Humor",
    "Culpa", "Nostalgia",
]

IMPACT_OPTIONS = [
    "Aventura", "Inquietud", "Melancolía", "Dilema moral",
    "Épica", "Intimidad", "Misterio", "Sátira", "Horror",
    "Belleza", "Extrañeza", "Asombro",
]

CONFLICT_OPTIONS = [
    "Interno", "Interpersonal", "Familiar", "Social", "Político",
    "Moral", "Económico", "Religioso", "Cósmico", "Metafísico",
    "Bélico", "Ambiental",
]

NARRATIVE_FUNCTIONS = [
    "Revelar", "Ocultar", "Decidir", "Mostrar coste", "Contrastar",
    "Presagiar", "Romper expectativa", "Confirmar regla",
    "Desviar atención", "Sintetizar tramas", "Presentar personaje",
    "Expandir mundo", "Intensificar conflicto", "Resolver consecuencia",
]


# ---------------------------------------------------------------------------
# Reusable helper widgets
# ---------------------------------------------------------------------------

def _make_textarea(text: str = "", max_h: int = 80) -> QTextEdit:
    """Create a QTextEdit with limited height."""
    te = QTextEdit()
    te.setPlainText(text)
    te.setMaximumHeight(max_h)
    te.setPlaceholderText("...")
    return te


def _make_slider(value: int = 5, lo: int = 0, hi: int = 10) -> tuple[QSlider, QLabel]:
    """Create a slider with value label. Returns (slider, label)."""
    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setRange(lo, hi)
    sl.setValue(value)
    lbl = QLabel(str(value))
    sl.valueChanged.connect(lambda v: lbl.setText(str(v)))
    return sl, lbl


def _make_combo(options: list[str], current: str = "") -> QComboBox:
    """Create a combo box with options."""
    cb = QComboBox()
    cb.addItems(options)
    idx = cb.findText(current)
    cb.setCurrentIndex(idx if idx >= 0 else 0)
    return cb


def _make_combo_keyed(keys: list[str], labels: list[str], current: str = "") -> QComboBox:
    """Create combo with display labels, store keys in userData."""
    cb = QComboBox()
    for k, l in zip(keys, labels):
        cb.addItem(l, k)
    idx = cb.findData(current)
    cb.setCurrentIndex(idx if idx >= 0 else 0)
    return cb


class TagInput(QWidget):
    """Chips/tags input: text field + add button + list of removable tags."""

    def __init__(self, tags: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.tags: list[str] = list(tags or [])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setPlaceholderText("Añadir...")
        self.field.returnPressed.connect(self._add_tag)
        row.addWidget(self.field)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_tag)
        row.addWidget(add_btn)
        layout.addLayout(row)

        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(100)
        layout.addWidget(self.tag_list)

        self._refresh_list()

    def _add_tag(self):
        text = self.field.text().strip()
        if text and text not in self.tags:
            self.tags.append(text)
            self._refresh_list()
        self.field.clear()

    def _refresh_list(self):
        self.tag_list.clear()
        for t in self.tags:
            item = QListWidgetItem(t)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.tag_list.addItem(item)
        # Connect removal on double-click
        self.tag_list.itemDoubleClicked.connect(self._remove_tag)

    def _remove_tag(self, item):
        self.tags.remove(item.text())
        self._refresh_list()

    def value(self) -> list[str]:
        return list(self.tags)


class ListEditor(QWidget):
    """Editable string list with add/remove."""

    def __init__(self, items: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.items: list[str] = [i for i in (items or []) if i]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setPlaceholderText("Añadir regla...")
        self.field.returnPressed.connect(self._add_item)
        row.addWidget(self.field)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_item)
        row.addWidget(add_btn)

        del_btn = QPushButton("−")
        del_btn.setFixedWidth(28)
        del_btn.clicked.connect(self._del_selected)
        row.addWidget(del_btn)
        layout.addLayout(row)

        self.lw = QListWidget()
        self.lw.setMaximumHeight(120)
        layout.addWidget(self.lw)
        self._refresh()

    def _add_item(self):
        text = self.field.text().strip()
        if text:
            self.items.append(text)
            self._refresh()
        self.field.clear()

    def _del_selected(self):
        for item in self.lw.selectedItems():
            self.items.remove(item.text())
        self._refresh()

    def _refresh(self):
        self.lw.clear()
        for i in self.items:
            self.lw.addItem(i)

    def value(self) -> list[str]:
        return [i for i in self.items if i]


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class CreativeConfigPanel(QTabWidget):
    """Tabbed creative config panel (B40-T03)."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self._fields: dict = {}  # key → widget for collect()

        self.setDocumentMode(True)

        # Build 9 tabs
        self._build_tab_basico()
        self._build_tab_direccion()
        self._build_tab_narrativa()
        self._build_tab_estilo()
        self._build_tab_reglas()
        self._build_tab_ia()
        self._build_tab_evitar()
        self._build_tab_memoria()
        self._build_tab_ramas()

    # ── Tab builders ──────────────────────────────────────────────

    def _scroll(self, widget: QWidget) -> QScrollArea:
        """Wrap a widget in a scroll area."""
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(widget)
        return sa

    def _form_tab(self, title: str) -> tuple[QWidget, QFormLayout]:
        """Create a form tab, return (page_widget, form_layout)."""
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)
        return page, form

    # ── Tab 1: Básico ─────────────────────────────────────────────

    def _build_tab_basico(self):
        _, form = self._form_tab("Básico")
        p = self.project
        cc = p.creative_config

        self._fields["core_premise"] = _make_textarea(cc.core_premise, 60)
        form.addRow("Premisa central", self._fields["core_premise"])

        self._fields["genre"] = _make_combo(GENRE_OPTIONS, p.genre.primary_genre)
        form.addRow("Género principal", self._fields["genre"])

        self._fields["subgenres"] = TagInput(p.genre.subgenres)
        form.addRow("Subgéneros", self._fields["subgenres"])

        self._fields["target_audience"] = _make_combo(AUDIENCE_OPTIONS, cc.target_audience)
        form.addRow("Público objetivo", self._fields["target_audience"])

        self._fields["format"] = _make_combo(FORMAT_OPTIONS, cc.format)
        form.addRow("Formato narrativo", self._fields["format"])

        self._fields["development_status"] = _make_combo(STATUS_OPTIONS, cc.development_status)
        form.addRow("Estado de desarrollo", self._fields["development_status"])

        self._fields["short_summary"] = _make_textarea(cc.short_summary, 60)
        form.addRow("Resumen corto", self._fields["short_summary"])

        self._fields["language"] = QLineEdit(p.primary_language)
        form.addRow("Idioma principal", self._fields["language"])

        # PA02: el toggle de worldbuilding se eliminó — siempre está activo.

        self.addTab(self._scroll(form.parentWidget()), "Básico")

    # ── Tab 2: Dirección creativa ──────────────────────────────────

    def _build_tab_direccion(self):
        _, form = self._form_tab("Dirección creativa")
        ci = self.project.creative_config.creative_intent

        self._fields["reader_promise"] = _make_textarea(ci.get("reader_promise", ""), 60)
        form.addRow("Promesa al lector", self._fields["reader_promise"])

        self._fields["central_question"] = _make_textarea(ci.get("central_question", ""), 60)
        form.addRow("Pregunta dramática central", self._fields["central_question"])

        self._fields["desired_emotions"] = TagInput(ci.get("desired_emotions", []))
        form.addRow("Emociones buscadas", self._fields["desired_emotions"])

        self._fields["aftertaste"] = _make_textarea(ci.get("aftertaste", ""), 60)
        form.addRow("Sensación final", self._fields["aftertaste"])

        orig = ci.get("originality", 5)
        self._fields["originality"], lbl_o = _make_slider(orig)
        row_o = QHBoxLayout()
        row_o.addWidget(self._fields["originality"])
        row_o.addWidget(lbl_o)
        form.addRow("Originalidad (0=convencional, 10=experimental)", row_o)

        amb = ci.get("ambiguity", 5)
        self._fields["ambiguity"], lbl_a = _make_slider(amb)
        row_a = QHBoxLayout()
        row_a.addWidget(self._fields["ambiguity"])
        row_a.addWidget(lbl_a)
        form.addRow("Ambigüedad (0=explícito, 10=enigmático)", row_a)

        self._fields["impact_types"] = TagInput(ci.get("impact_types", []))
        form.addRow("Tipos de impacto", self._fields["impact_types"])

        self.addTab(self._scroll(form.parentWidget()), "Dirección")

    # ── Tab 3: Narrativa ───────────────────────────────────────────

    def _build_tab_narrativa(self):
        _, form = self._form_tab("Narrativa")
        ne = self.project.creative_config.narrative_engine

        self._fields["conflict_sources"] = TagInput(ne.get("conflict_sources", []))
        form.addRow("Fuentes de conflicto", self._fields["conflict_sources"])

        self._fields["dominant_tension"] = _make_combo(TENSION_OPTIONS, ne.get("dominant_tension", ""))
        form.addRow("Tensión dominante", self._fields["dominant_tension"])

        self._fields["progression"] = _make_combo(PROGRESSION_OPTIONS, ne.get("progression_mechanism", ""))
        form.addRow("Mecanismo de avance", self._fields["progression"])

        self._fields["character_change"] = _make_combo(CHANGE_OPTIONS, ne.get("character_change", ""))
        form.addRow("Cambio de personajes", self._fields["character_change"])

        self._fields["escalation"] = _make_combo(ESCALATION_OPTIONS, ne.get("escalation", ""))
        form.addRow("Escalada", self._fields["escalation"])

        agency = ne.get("character_agency", 5)
        self._fields["agency"], lbl_ag = _make_slider(agency)
        row_ag = QHBoxLayout()
        row_ag.addWidget(self._fields["agency"])
        row_ag.addWidget(lbl_ag)
        form.addRow("Agencia de personajes (0=baja, 10=alta)", row_ag)

        caus = ne.get("causality", 5)
        self._fields["causality"], lbl_c = _make_slider(caus)
        row_c = QHBoxLayout()
        row_c.addWidget(self._fields["causality"])
        row_c.addWidget(lbl_c)
        form.addRow("Causalidad (0=flexible, 10=estricta)", row_c)

        self.addTab(self._scroll(form.parentWidget()), "Narrativa")

    # ── Tab 4: Estilo ──────────────────────────────────────────────

    def _build_tab_estilo(self):
        _, form = self._form_tab("Estilo")
        cc = self.project.creative_config
        po = cc.poetics

        self._fields["narrative_style"] = _make_textarea(cc.narrative_style, 60)
        form.addRow("Estilo narrativo", self._fields["narrative_style"])

        self._fields["tone_general"] = _make_textarea(self.project.tone.narrative_tone, 60)
        form.addRow("Tono general", self._fields["tone_general"])

        self._fields["narrative_distance"] = _make_combo(DISTANCE_OPTIONS, po.get("narrative_distance", ""))
        form.addRow("Distancia narrativa", self._fields["narrative_distance"])

        dd = po.get("description_density", 5)
        self._fields["desc_density"], lbl_dd = _make_slider(dd)
        row_dd = QHBoxLayout()
        row_dd.addWidget(self._fields["desc_density"])
        row_dd.addWidget(lbl_dd)
        form.addRow("Densidad descriptiva (0=seca, 10=sensorial)", row_dd)

        cd = po.get("conceptual_density", 5)
        self._fields["conc_density"], lbl_cd = _make_slider(cd)
        row_cd = QHBoxLayout()
        row_cd.addWidget(self._fields["conc_density"])
        row_cd.addWidget(lbl_cd)
        form.addRow("Densidad conceptual (0=ligera, 10=reflexiva)", row_cd)

        st = po.get("subtext_level", 5)
        self._fields["subtext"], lbl_st = _make_slider(st)
        row_st = QHBoxLayout()
        row_st.addWidget(self._fields["subtext"])
        row_st.addWidget(lbl_st)
        form.addRow("Subtexto (0=directo, 10=muy implícito)", row_st)

        self._fields["dialogue_styles"] = TagInput(po.get("dialogue_styles", []))
        form.addRow("Tipos de diálogo", self._fields["dialogue_styles"])

        self._fields["exposition_modes"] = TagInput(po.get("exposition_modes", []))
        form.addRow("Modo de exposición", self._fields["exposition_modes"])

        self._fields["recurring_imagery"] = TagInput(po.get("recurring_imagery", []))
        form.addRow("Imágenes/motivos recurrentes", self._fields["recurring_imagery"])

        self._fields["forbidden_style"] = ListEditor(po.get("forbidden_style_habits", []))
        form.addRow("Prohibiciones de estilo", self._fields["forbidden_style"])

        self.addTab(self._scroll(form.parentWidget()), "Estilo")

    # ── Tab 5: Reglas ──────────────────────────────────────────────

    def _build_tab_reglas(self):
        _, form = self._form_tab("Reglas")
        ca = self.project.creative_config.canon

        form.addRow(QLabel("Canon duro (inviolable para la IA)"))
        self._fields["hard_rules"] = ListEditor(ca.get("hard_rules", []))
        form.addRow("", self._fields["hard_rules"])

        form.addRow(QLabel("Preferencias blandas"))
        self._fields["soft_prefs"] = ListEditor(ca.get("soft_preferences", []))
        form.addRow("", self._fields["soft_prefs"])

        cs = ca.get("continuity_strictness", 5)
        self._fields["continuity"], lbl_cs = _make_slider(cs)
        row_cs = QHBoxLayout()
        row_cs.addWidget(self._fields["continuity"])
        row_cs.addWidget(lbl_cs)
        form.addRow("Continuidad (0=flexible, 10=estricta)", row_cs)

        self._fields["contradiction"] = _make_combo(CONTRADICTION_OPTIONS, ca.get("contradiction_policy", ""))
        form.addRow("Política de contradicciones", self._fields["contradiction"])

        form.addRow(QLabel("Reglas de mundo"))
        self._fields["world_rules"] = ListEditor(ca.get("world_rules", []))
        form.addRow("", self._fields["world_rules"])

        form.addRow(QLabel("Reglas de personajes"))
        self._fields["char_rules"] = ListEditor(ca.get("character_rules", []))
        form.addRow("", self._fields["char_rules"])

        form.addRow(QLabel("Reglas de cronología"))
        self._fields["time_rules"] = ListEditor(ca.get("timeline_rules", []))
        form.addRow("", self._fields["time_rules"])

        self.addTab(self._scroll(form.parentWidget()), "Reglas")

    # ── Tab 6: IA ──────────────────────────────────────────────────

    def _build_tab_ia(self):
        _, form = self._form_tab("IA")
        ai = self.project.ai

        self._fields["ai_role"] = _make_combo_keyed(AI_ROLE_KEYS, AI_ROLE_OPTIONS, ai.default_role)
        form.addRow("Rol por defecto", self._fields["ai_role"])

        ag = ai.change_aggressiveness
        self._fields["ai_aggression"], lbl_ag = _make_slider(ag)
        row_ag = QHBoxLayout()
        row_ag.addWidget(self._fields["ai_aggression"])
        row_ag.addWidget(lbl_ag)
        form.addRow("Agresividad (0=mínima, 10=radical)", row_ag)

        self._fields["ai_num_options"] = QSpinBox()
        self._fields["ai_num_options"].setRange(1, 5)
        self._fields["ai_num_options"].setValue(ai.default_num_options)
        form.addRow("Propuestas por defecto", self._fields["ai_num_options"])

        self._fields["ai_output"] = _make_combo_keyed(
            [v for _, v in AI_OUTPUT_OPTIONS],
            [l for l, _ in AI_OUTPUT_OPTIONS],
            ai.output_mode,
        )
        form.addRow("Tipo de respuesta", self._fields["ai_output"])

        self._fields["ai_uncertainty"] = _make_combo_keyed(
            [v for _, v in AI_UNCERTAINTY_OPTIONS],
            [l for l, _ in AI_UNCERTAINTY_OPTIONS],
            ai.uncertainty_policy,
        )
        form.addRow("Cuando falte contexto", self._fields["ai_uncertainty"])

        self._fields["ai_strategy"] = _make_combo_keyed(AI_STRATEGY_KEYS, AI_STRATEGY_OPTIONS, ai.default_strategy)
        form.addRow("Estrategia creativa", self._fields["ai_strategy"])

        self._fields["ai_depth"] = _make_combo_keyed(
            [v for _, v in AI_DEPTH_OPTIONS],
            [l for l, _ in AI_DEPTH_OPTIONS],
            ai.context_depth,
        )
        form.addRow("Profundidad de contexto", self._fields["ai_depth"])

        self.addTab(self._scroll(form.parentWidget()), "IA")

    # ── Tab 7: Evitar ──────────────────────────────────────────────

    def _build_tab_evitar(self):
        _, form = self._form_tab("Evitar")
        ns = self.project.creative_config.negative_space

        self._fields["avoid_tropes"] = ListEditor(ns.get("avoid_tropes", []))
        form.addRow("Tropos a evitar", self._fields["avoid_tropes"])

        self._fields["avoid_solutions"] = ListEditor(ns.get("avoid_solutions", []))
        form.addRow("Soluciones a evitar", self._fields["avoid_solutions"])

        self._fields["avoid_style"] = ListEditor(ns.get("avoid_style_habits", []))
        form.addRow("Tics de estilo a evitar", self._fields["avoid_style"])

        self._fields["avoid_tones"] = ListEditor(ns.get("avoid_tones", []))
        form.addRow("Tonos prohibidos", self._fields["avoid_tones"])

        self._fields["avoid_phrases"] = ListEditor(ns.get("avoid_phrases", []))
        form.addRow("Frases o gestos prohibidos", self._fields["avoid_phrases"])

        self.addTab(self._scroll(form.parentWidget()), "Evitar")

    # ── Tab 8: Memoria creativa ────────────────────────────────────

    def _build_tab_memoria(self):
        _, form = self._form_tab("Memoria")
        tm = self.project.creative_config.taste_memory

        self._fields["accepted"] = ListEditor(tm.get("accepted_patterns", []))
        form.addRow("Patrones aceptados", self._fields["accepted"])

        self._fields["rejected"] = ListEditor(tm.get("rejected_patterns", []))
        form.addRow("Patrones rechazados", self._fields["rejected"])

        self._fields["style_notes"] = ListEditor(tm.get("user_style_notes", []))
        form.addRow("Notas de estilo", self._fields["style_notes"])

        self._fields["learned"] = ListEditor(tm.get("learned_decisions", []))
        form.addRow("Decisiones creativas aprendidas", self._fields["learned"])

        self._fields["pending"] = ListEditor(tm.get("pending_suggestions", []))
        form.addRow("Sugerencias pendientes", self._fields["pending"])

        self.addTab(self._scroll(form.parentWidget()), "Memoria")

    # ── Tab 9: Ramas ───────────────────────────────────────────────

    def _build_tab_ramas(self):
        _, form = self._form_tab("Ramas")

        info = QLabel(
            "Configura overrides locales por rama.\n"
            "Las ramas heredan la configuración del proyecto por defecto.\n"
            "Puedes sobrescribir campos concretos aquí."
        )
        info.setWordWrap(True)
        info.setObjectName("mutedLabel")
        form.addRow(info)

        self._fields["branch_select"] = QComboBox()
        self._fields["branch_select"].addItem("— Seleccionar rama —", "")
        # Populate with CONTENEDOR entities
        for e in self.project.entities:
            if e.entity_type.value == "CONTENEDOR":
                self._fields["branch_select"].addItem(e.name, e.id)
        form.addRow("Rama", self._fields["branch_select"])

        self._fields["branch_function"] = _make_combo([""] + NARRATIVE_FUNCTIONS)
        form.addRow("Función narrativa", self._fields["branch_function"])

        self._fields["branch_motifs"] = TagInput()
        form.addRow("Motivos locales", self._fields["branch_motifs"])

        self._fields["branch_tone"] = QLineEdit()
        self._fields["branch_tone"].setPlaceholderText("Override de tono local...")
        form.addRow("Tono local", self._fields["branch_tone"])

        self._fields["branch_rules"] = ListEditor()
        form.addRow("Reglas locales", self._fields["branch_rules"])

        restore_btn = QPushButton("Restaurar configuración global")
        restore_btn.setObjectName("secondaryButton")
        restore_btn.clicked.connect(self._restore_branch_global)
        form.addRow(restore_btn)

        self._fields["branch_select"].currentIndexChanged.connect(self._on_branch_selected)

        self.addTab(self._scroll(form.parentWidget()), "Ramas")

    def _on_branch_selected(self):
        """Load branch config when a rama is selected."""
        entity_id = self._fields["branch_select"].currentData()
        if not entity_id:
            return
        for e in self.project.entities:
            if e.id == entity_id:
                from packages.domain.branch_config import get_branch_config
                cfg = get_branch_config(e)
                self._fields["branch_function"].setCurrentText(
                    cfg.get("local_narrative_function", ""))
                # Reset tag input
                self._fields["branch_motifs"].tags = cfg.get("local_motifs", [])
                self._fields["branch_motifs"]._refresh_list()
                self._fields["branch_tone"].setText(cfg.get("local_tone_override", ""))
                self._fields["branch_rules"].items = cfg.get("local_rules", [])
                self._fields["branch_rules"]._refresh()
                break

    def _restore_branch_global(self):
        """Reset selected branch to inherit from project."""
        entity_id = self._fields["branch_select"].currentData()
        if not entity_id:
            return
        for e in self.project.entities:
            if e.id == entity_id:
                from packages.domain.branch_config import clear_all_branch_overrides
                clear_all_branch_overrides(e)
                self._on_branch_selected()
                break

    # ── Collect values ─────────────────────────────────────────────

    def collect(self) -> dict:
        """Collect all edited values into a nested dict."""
        def _text(w):
            return w.toPlainText().strip() if isinstance(w, QTextEdit) else w.text().strip()

        def _val(w):
            if isinstance(w, QTextEdit):
                return w.toPlainText().strip()
            if isinstance(w, QLineEdit):
                return w.text().strip()
            if isinstance(w, QSlider):
                return w.value()
            if isinstance(w, QSpinBox):
                return w.value()
            if isinstance(w, QCheckBox):
                return w.isChecked()
            if isinstance(w, TagInput):
                return w.value()
            if isinstance(w, ListEditor):
                return w.value()
            if isinstance(w, QComboBox):
                data = w.currentData()
                return data if data is not None else w.currentText().strip()
            return ""

        f = self._fields
        return {
            "core_premise": _text(f["core_premise"]),
            "short_summary": _text(f["short_summary"]),
            "genre": _val(f["genre"]),
            "subgenres": f["subgenres"].value(),
            "target_audience": _val(f["target_audience"]),
            "format": _val(f["format"]),
            "development_status": _val(f["development_status"]),
            "language": _text(f["language"]),
            "creative_intent": {
                "reader_promise": _text(f["reader_promise"]),
                "central_question": _text(f["central_question"]),
                "desired_emotions": f["desired_emotions"].value(),
                "aftertaste": _text(f["aftertaste"]),
                "originality": f["originality"].value(),
                "ambiguity": f["ambiguity"].value(),
                "impact_types": f["impact_types"].value(),
            },
            "narrative_engine": {
                "conflict_sources": f["conflict_sources"].value(),
                "dominant_tension": _val(f["dominant_tension"]),
                "progression_mechanism": _val(f["progression"]),
                "character_change": _val(f["character_change"]),
                "escalation": _val(f["escalation"]),
                "character_agency": f["agency"].value(),
                "causality": f["causality"].value(),
            },
            "poetics": {
                "narrative_distance": _val(f["narrative_distance"]),
                "description_density": f["desc_density"].value(),
                "conceptual_density": f["conc_density"].value(),
                "subtext_level": f["subtext"].value(),
                "dialogue_styles": f["dialogue_styles"].value(),
                "exposition_modes": f["exposition_modes"].value(),
                "recurring_imagery": f["recurring_imagery"].value(),
                "forbidden_style_habits": f["forbidden_style"].value(),
            },
            "canon": {
                "hard_rules": f["hard_rules"].value(),
                "soft_preferences": f["soft_prefs"].value(),
                "continuity_strictness": f["continuity"].value(),
                "contradiction_policy": _val(f["contradiction"]),
                "world_rules": f["world_rules"].value(),
                "character_rules": f["char_rules"].value(),
                "timeline_rules": f["time_rules"].value(),
            },
            "narrative_style": _text(f["narrative_style"]),
            "tone_general": _text(f["tone_general"]),
            "ai": {
                "default_role": _val(f["ai_role"]),
                "change_aggressiveness": f["ai_aggression"].value(),
                "default_num_options": f["ai_num_options"].value(),
                "output_mode": _val(f["ai_output"]),
                "uncertainty_policy": _val(f["ai_uncertainty"]),
                "default_strategy": _val(f["ai_strategy"]),
                "context_depth": _val(f["ai_depth"]),
            },
            "negative_space": {
                "avoid_tropes": f["avoid_tropes"].value(),
                "avoid_solutions": f["avoid_solutions"].value(),
                "avoid_style_habits": f["avoid_style"].value(),
                "avoid_tones": f["avoid_tones"].value(),
                "avoid_phrases": f["avoid_phrases"].value(),
            },
            "taste_memory": {
                "accepted_patterns": f["accepted"].value(),
                "rejected_patterns": f["rejected"].value(),
                "user_style_notes": f["style_notes"].value(),
                "learned_decisions": f["learned"].value(),
                "pending_suggestions": f["pending"].value(),
            },
            # Branch config handled separately via _on_branch_selected
        }

    def apply_to_project(self, project):
        """Apply collected values to a project object."""
        data = self.collect()
        cc = project.creative_config
        ai = project.ai

        cc.core_premise = data["core_premise"]
        cc.short_summary = data["short_summary"]
        cc.development_status = data["development_status"]
        cc.format = data["format"]
        cc.narrative_style = data["narrative_style"]

        project.genre.primary_genre = data["genre"]
        project.genre.subgenres = data["subgenres"]

        cc.target_audience = data["target_audience"]
        project.primary_language = data["language"]
        # PA02: worldbuilding siempre activo (sin toggle en la config).
        project.worldbuilding_active = True

        # Update sub-dicts (only non-empty)
        if any(data["creative_intent"].values()):
            existing = dict(cc.creative_intent) if cc.creative_intent else {}
            existing.update({k: v for k, v in data["creative_intent"].items() if v})
            cc.creative_intent = existing

        if any(data["narrative_engine"].values()):
            existing = dict(cc.narrative_engine) if cc.narrative_engine else {}
            existing.update({k: v for k, v in data["narrative_engine"].items() if v})
            cc.narrative_engine = existing

        if any(data["poetics"].values()):
            existing = dict(cc.poetics) if cc.poetics else {}
            existing.update({k: v for k, v in data["poetics"].items() if v})
            cc.poetics = existing

        if any(data["canon"].values()):
            existing = dict(cc.canon) if cc.canon else {}
            existing.update({k: v for k, v in data["canon"].items() if v})
            cc.canon = existing

        if any(data["negative_space"].values()):
            existing = dict(cc.negative_space) if cc.negative_space else {}
            existing.update({k: v for k, v in data["negative_space"].items() if v})
            cc.negative_space = existing

        if any(data["taste_memory"].values()):
            existing = dict(cc.taste_memory) if cc.taste_memory else {}
            existing.update({k: v for k, v in data["taste_memory"].items() if v})
            cc.taste_memory = existing

        # Tone
        project.tone.narrative_tone = data["tone_general"]

        # AI
        ai.default_role = data["ai"]["default_role"] or "coauthor"
        ai.change_aggressiveness = data["ai"]["change_aggressiveness"]
        ai.default_num_options = data["ai"]["default_num_options"]
        ai.output_mode = data["ai"]["output_mode"] or "contrastive_options"
        ai.uncertainty_policy = data["ai"]["uncertainty_policy"] or "conservative_proposal"
        ai.default_strategy = data["ai"]["default_strategy"] or "profundizar"
        ai.context_depth = data["ai"]["context_depth"] or "balanced"

        # Save branch config for selected branch
        entity_id = self._fields["branch_select"].currentData()
        if entity_id:
            for e in project.entities:
                if e.id == entity_id:
                    from packages.domain.branch_config import set_branch_config
                    set_branch_config(e, {
                        "inherits_from_project": False,
                        "local_narrative_function": self._fields["branch_function"].currentText(),
                        "local_motifs": self._fields["branch_motifs"].value(),
                        "local_tone_override": self._fields["branch_tone"].text().strip(),
                        "local_ai_role": "",
                        "local_rules": self._fields["branch_rules"].value(),
                        "overrides": {},
                    })
                    break
