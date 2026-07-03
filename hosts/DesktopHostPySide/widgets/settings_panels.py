"""Dendro settings panels for B31 UX fix (B31-UX-FIX-02-T04).

All panels live inside RightDrawer; no normal-flow modal dialogs. They call
callbacks/controllers supplied by MainWindow and do not import persistence.
"""
from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import Card, PanelScaffold, SectionHeader


# ── Module-level helpers ──────────────────────────────────────────────────

def _human_error(error: str) -> str:
    """Return a human-friendly Spanish error message for common AI failures."""
    if "403" in error:
        return "Error 403: el proveedor rechazó la petición. Revisa API key, permisos o modelo."
    if "401" in error:
        return "Error 401: credenciales inválidas o ausentes."
    if "ReadTimeout" in error or "timed out" in error.lower():
        return "Timeout: la petición tardó demasiado. Revisa la conexión o el timeout del proveedor."
    if "ConnectionError" in error or "connection" in error.lower():
        return "No se pudo conectar. Revisa la URL y la conexión a internet."
    if "404" in error:
        return "Modelo no encontrado. Revisa el nombre del modelo en la configuración."
    return f"Error IA: {error}"


class _AIWorker(QThread):
    """Background thread for AI provider calls."""
    finished = Signal(object)  # result object or exception

    def __init__(self, ai_controller, prompt: str = ""):
        super().__init__()
        self.ai = ai_controller
        self.prompt = prompt

    def run(self):
        try:
            result = self.ai.test_provider()
            self.finished.emit(result)
        except Exception as exc:
            self.finished.emit(exc)


class _AIChatWorker(QThread):
    """Background thread for AI chat calls."""
    finished = Signal(str, str)  # (text, error) — one will be empty

    def __init__(self, ai_controller, system_prompt: str, user_message: str):
        super().__init__()
        self.ai = ai_controller
        self.system_prompt = system_prompt
        self.user_message = user_message

    def run(self):
        try:
            text, error = self.ai.chat(self.system_prompt, self.user_message)
            if error:
                self.finished.emit("", error)
            else:
                self.finished.emit(text or "(sin respuesta)", "")
        except Exception as exc:
            self.finished.emit("", str(exc))


class _PanelBase(PanelScaffold):
    """Base de los paneles de settings, ahora sobre PanelScaffold (UX14).

    Mantiene la API previa: ``self.layout`` es el cuerpo del scaffold (las
    subclases añaden contenido ahí) y la cabecera la pone PanelScaffold."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(title, subtitle, parent=parent)
        # compat: las subclases montan su contenido en self.layout (= body).
        self.layout = self.body

    def _action_button(self, text: str, callback: Callable, *, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        if primary:
            btn.setObjectName("primaryButton")
        btn.clicked.connect(callback)
        return btn

    def _note(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("mutedLabel")
        label.setWordWrap(True)
        return label


class ProjectActionsPanel(_PanelBase):
    """Grouped project actions: new/open/save/change."""

    def __init__(self, callbacks: dict[str, Callable], parent: QWidget | None = None):
        super().__init__("Proyecto", "Acciones de archivo agrupadas para mantener la Home limpia.", parent)
        card = Card("Archivo narrativo", "Crea, abre o guarda el proyecto actual.")
        for text, key, primary in [
            ("Nuevo proyecto", "new_project", True),
            ("Abrir proyecto", "open_project", False),
            ("Guardar", "save_project", False),
            ("Cambiar / cerrar proyecto", "close_project", False),
        ]:
            card.layout.addWidget(self._action_button(text, callbacks[key], primary=primary))
        self.layout.addWidget(card)
        self.layout.addWidget(self._note("Abrir/Nuevo usan el selector de archivos del sistema; el resto permanece dentro de Dendro."))
        self.layout.addStretch(1)


# ── Project type / label mapping ──────────────────────────────────────────

_PROJECT_TYPE_LABELS = {
    "campana": "Campaña de rol",
    "novela": "Novela / Relato",
    "otro": "Otro narrativo",
}
_PROJECT_TYPE_VALUES = {v: k for k, v in _PROJECT_TYPE_LABELS.items()}


class ProjectPanel(QWidget):
    """Full project configuration: file management, type, worldbuilding, creative config."""

    def __init__(self, *, ctx, callbacks: dict[str, Callable], on_preview=None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.callbacks = callbacks
        self.on_preview = on_preview

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(18, 16, 18, 18)
        self.root_layout.setSpacing(12)
        self.root_layout.addWidget(SectionHeader("Proyecto", "Configuración completa del proyecto."))

        # Grab project (may be None)
        self.project = self._get_project()

        # ── Section A: Current Project / File Management ──
        self._build_file_management_section()

        if self.project is None:
            no_proj = QLabel("Abre o crea un proyecto primero")
            no_proj.setObjectName("mutedLabel")
            no_proj.setWordWrap(True)
            no_proj.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.root_layout.addWidget(no_proj)
            self.root_layout.addStretch(1)
            return

        # ── Section B: Project Type — RETIRADA (BETA1-UX): la caja "Tipo de
        # proyecto" no aporta al flujo; el tipo almacenado se conserva al guardar.
        # self._build_project_type_section()

        # ── Section C: Cronología (PA02: worldbuilding ya no es opcional) ──
        self._build_chronology_section()

        # ── Section D-G: Creative Config (B40 tabbed panel) ──
        from hosts.DesktopHostPySide.widgets.creative_config_panel import CreativeConfigPanel
        self.creative_tabs = CreativeConfigPanel(self.project, self)
        self.root_layout.addWidget(self.creative_tabs)

        # ── Save button ──
        self.save_btn = QPushButton("Guardar proyecto")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save_all)
        self.root_layout.addWidget(self.save_btn)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        self.root_layout.addWidget(self.status_label)

        self.root_layout.addStretch(1)

        # Apply initial visibility for conditional sections
        self._update_type_visibility()

    # ── Helpers ──

    def _get_project(self):
        pc = getattr(self.ctx, "project_controller", None)
        if pc is None:
            return None
        ps = getattr(pc, "ps", None)
        if ps is None:
            return None
        return getattr(ps, "active_project", None)

    def _safe(self, obj, attr, default=None):
        """Safe getattr with default."""
        return getattr(obj, attr, default) if obj is not None else default

    @staticmethod
    def _make_card(title: str, subtitle: str = "") -> Card:
        return Card(title, subtitle)

    # ── Section builders ──

    def _build_file_management_section(self):
        name = self.project.name if self.project else "Sin proyecto"
        card = self._make_card("Archivo narrativo", f"Proyecto: {name}")
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for text, key, primary in [
            ("Nuevo", "new_project", True),
            ("Abrir", "open_project", False),
            ("Guardar", "save_project", False),
        ]:
            btn = QPushButton(text)
            if primary:
                btn.setObjectName("primaryButton")
            btn.clicked.connect(self.callbacks[key])
            btn_row.addWidget(btn)
        # Close/Change button
        close_btn = QPushButton("Cambiar / Cerrar")
        close_btn.clicked.connect(self.callbacks["close_project"])
        btn_row.addWidget(close_btn)
        card.layout.addLayout(btn_row)
        self.root_layout.addWidget(card)

    def _build_project_type_section(self):
        card = self._make_card("Tipo de proyecto")
        form = QFormLayout()
        form.setSpacing(10)
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(_PROJECT_TYPE_LABELS.values()))
        current_type = self._safe(self.project, "project_type", "otro")
        label = _PROJECT_TYPE_LABELS.get(current_type, "Otro narrativo")
        idx = self.type_combo.findText(label)
        self.type_combo.setCurrentIndex(idx if idx >= 0 else 2)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Tipo", self.type_combo)
        card.layout.addLayout(form)
        self.root_layout.addWidget(card)

    def _build_chronology_section(self):
        pc = getattr(self.ctx, "project_controller", None)
        ps = getattr(pc, "ps", None) if pc is not None else None
        if ps is None:
            return
        from hosts.DesktopHostPySide.controllers.project_chronology_controller import ProjectChronologyController
        from hosts.DesktopHostPySide.widgets.chronology_config_panel import ChronologyConfigPanel

        self.root_layout.addWidget(ChronologyConfigPanel(ProjectChronologyController(ps), compact=True))

    def _build_creative_config_section(self):
        card = self._make_card("Configuración creativa")
        form = QFormLayout()
        form.setSpacing(10)

        cc = getattr(self.project, "creative_config", None)

        self.narrative_style_edit = QLineEdit(self._safe(cc, "narrative_style"))
        self.narrative_style_edit.setPlaceholderText("Ej: descriptivo, ágil, poético…")
        form.addRow("Estilo narrativo", self.narrative_style_edit)

        themes_val = self._safe(cc, "main_themes", [])
        self.main_themes_edit = QLineEdit(
            ", ".join(themes_val) if isinstance(themes_val, list) else str(themes_val)
        )
        self.main_themes_edit.setPlaceholderText("Coma-separated: fantasía, amistad, redención")
        form.addRow("Temas principales", self.main_themes_edit)

        self.target_audience_edit = QLineEdit(self._safe(cc, "target_audience"))
        self.target_audience_edit.setPlaceholderText("Ej: joven adulto, general")
        form.addRow("Público objetivo", self.target_audience_edit)

        rules_val = self._safe(cc, "creative_rules", [])
        self.creative_rules_edit = QLineEdit(
            ", ".join(rules_val) if isinstance(rules_val, list) else str(rules_val)
        )
        self.creative_rules_edit.setPlaceholderText("Coma-separated: sin violencia gráfica, finales felices")
        form.addRow("Reglas creativas", self.creative_rules_edit)

        card.layout.addLayout(form)
        self.root_layout.addWidget(card)

    def _build_genre_tone_realism_section(self):
        card = self._make_card("Género / Tono / Realismo")
        form = QFormLayout()
        form.setSpacing(10)

        # Genre
        genre_obj = getattr(self.project, "genre", None)
        self.genre_edit = QLineEdit(self._safe(genre_obj, "primary_genre"))
        self.genre_edit.setPlaceholderText("Ej: fantasía, ciencia ficción, terror")
        form.addRow("Género", self.genre_edit)

        # Tone
        tone_obj = getattr(self.project, "tone", None)
        self.tone_combo = QComboBox()
        tone_options = ["Serio", "Equilibrado", "Ligero"]
        self.tone_combo.addItems(tone_options)
        current_tone = self._safe(tone_obj, "narrative_tone", "neutral")
        tone_map = {"Serio": "serious", "Equilibrado": "neutral", "Ligero": "light"}
        tone_rev = {v: k for k, v in tone_map.items()}
        tone_label = tone_rev.get(current_tone, "Equilibrado")
        t_idx = self.tone_combo.findText(tone_label)
        self.tone_combo.setCurrentIndex(t_idx if t_idx >= 0 else 1)
        form.addRow("Tono", self.tone_combo)

        # Realism
        realism_obj = getattr(self.project, "realism", None)
        self.realism_combo = QComboBox()
        realism_options = ["Bajo", "Medio", "Alto"]
        self.realism_combo.addItems(realism_options)
        current_realism = self._safe(realism_obj, "realism_level", "medium")
        realism_map = {"Bajo": "low", "Medio": "medium", "Alto": "high"}
        realism_rev = {v: k for k, v in realism_map.items()}
        realism_label = realism_rev.get(current_realism, "Medio")
        r_idx = self.realism_combo.findText(realism_label)
        self.realism_combo.setCurrentIndex(r_idx if r_idx >= 0 else 1)
        form.addRow("Realismo", self.realism_combo)

        card.layout.addLayout(form)
        self.root_layout.addWidget(card)

    def _build_campaign_config_section(self):
        self.campaign_card = self._make_card("Configuración de campaña")
        form = QFormLayout()
        form.setSpacing(10)

        # General config has a 'theme' field; campaign doesn't have its own
        # top-level config, so we store campaign-specific fields on general.
        general = getattr(self.project, "general", None)

        self.campaign_system_edit = QLineEdit(self._safe(general, "theme"))
        self.campaign_system_edit.setPlaceholderText("Ej: D&D 5e, Vampiro, propio…")
        form.addRow("Sistema de rol", self.campaign_system_edit)

        self.campaign_type_combo = QComboBox()
        self.campaign_type_combo.addItems(["One-shot", "Corta", "Larga", "Sandbox"])
        form.addRow("Tipo de campaña", self.campaign_type_combo)

        self.campaign_tone_combo = QComboBox()
        self.campaign_tone_combo.addItems(["Serio", "Equilibrado", "Divertido"])
        self.campaign_tone_combo.setCurrentIndex(1)
        form.addRow("Tono de mesa", self.campaign_tone_combo)

        self.campaign_card.layout.addLayout(form)
        self.root_layout.addWidget(self.campaign_card)

    # ── Visibility logic ──

    def _current_type_value(self) -> str:
        # BETA1-UX: la caja "Tipo de proyecto" se retiró del menú; se conserva
        # el tipo ya almacenado en el proyecto.
        if not hasattr(self, "type_combo"):
            return self._safe(self.project, "project_type", "otro")
        label = self.type_combo.currentText()
        return _PROJECT_TYPE_VALUES.get(label, "otro")

    def _on_type_changed(self, _label: str):
        self._update_type_visibility()
        self._mark_pending()
        if self.on_preview:
            self.on_preview(self._current_type_value(), True)

    def _mark_pending(self):
        """Show a pending changes indicator."""
        if hasattr(self, 'save_btn'):
            self.save_btn.setText("Guardar proyecto *")
            self.save_btn.setStyleSheet("QPushButton { font-weight: bold; }")

    def _update_type_visibility(self):
        """Update project-type dependent controls.

        B40 replaced the old campaign/novela cards with a unified tabbed
        creative configuration panel. Keep this hook because type changes still
        trigger preview/pending state, but do not assume the removed cards
        exist.
        """
        return

    # ── Save ──

    def _save_all(self):
        if self.project is None:
            return
        try:
            p = self.project

            # Project type
            p.project_type = self._current_type_value()

            # PA02: worldbuilding siempre activo.
            p.worldbuilding_active = True

            # Apply all creative config from tabbed panel (B40)
            self.creative_tabs.apply_to_project(p)

            # Persist
            self.callbacks["save_project"]()
            self.status_label.setText("✓ Proyecto guardado correctamente")
            self.save_btn.setText("Guardar proyecto")
            self.save_btn.setStyleSheet("")
        except Exception as exc:
            self.status_label.setText(f"Error guardando: {exc}")


class AISettingsPanel(_PanelBase):
    """OpenAI-compatible/simulated provider settings and test surface."""

    def __init__(self, ai_controller, on_status: Callable[[str], None] | None = None, parent: QWidget | None = None):
        super().__init__("Ajustes IA", "Configura el proveedor sin mostrar la clave en claro.", parent)
        self.ai = ai_controller
        self.on_status = on_status
        status = self.ai.provider_status()

        self.form_card = Card("Proveedor")
        form = QFormLayout()
        form.setSpacing(10)
        self.provider = QComboBox()
        self.provider.addItems(["simulated", "openai_compatible"])
        current_provider = str(status.get("provider", "simulated") or "simulated")
        idx = self.provider.findText(current_provider)
        self.provider.setCurrentIndex(idx if idx >= 0 else 0)
        self.base_url = QLineEdit(str(status.get("base_url", "") or ""))
        self.base_url.setPlaceholderText("https://api.example.com/v1")
        self.model = QLineEdit(str(status.get("model", "") or ""))
        self.model.setPlaceholderText("modelo")
        self.api_key = QLineEdit("")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Mantener actual" if status.get("has_key") else "API key / token")
        form.addRow("Proveedor", self.provider)
        form.addRow("Base URL", self.base_url)
        form.addRow("Modelo", self.model)
        form.addRow("API key / token", self.api_key)
        self.form_card.layout.addLayout(form)
        self.layout.addWidget(self.form_card)

        row = QHBoxLayout()
        save = QPushButton("Guardar configuración")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save_env)
        test = QPushButton("Test")
        test.clicked.connect(self._test)
        row.addWidget(save)
        row.addWidget(test)
        self.layout.addLayout(row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("mutedLabel")
        self.layout.addWidget(self.status_label)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(130)
        self.layout.addWidget(self.output)
        self.layout.addStretch(1)
        self._render_status("Estado cargado")

    def _save_env(self):
        provider = self.provider.currentText().strip() or "simulated"
        os.environ["NARRATIVE_AI_PROVIDER"] = provider
        os.environ["NARRATIVE_AI_BASE_URL"] = self.base_url.text().strip()
        os.environ["NARRATIVE_AI_MODEL"] = self.model.text().strip()
        key = self.api_key.text().strip()
        if key:
            os.environ["NARRATIVE_AI_API_KEY"] = key
            self.api_key.clear()
            self.api_key.setPlaceholderText("Clave guardada")
        # Recreate orchestrator so Test uses the new runtime env.
        try:
            self.ai.__init__(self.ai.ps)
        except Exception as exc:
            self._render_status(f"Error reconfigurando IA: {exc}", danger=True)
            return
        self._render_status("Configuración IA actualizada")

    def _test(self):
        self._save_env()
        result = self.ai.test_provider()
        if hasattr(result, "error"):
            self._render_status(f"Error: {result.error}", danger=True)
            return
        resp = result.value
        error = getattr(resp, "error", None)
        provider = getattr(resp, "provider", "?")
        text = getattr(resp, "raw_text", "") or ""
        if error:
            human = self._human_error(str(error))
            self._render_status(human, danger=True)
            self.output.setPlainText(str(error))
            return
        self._render_status(f"Conectado: {provider}")
        self.output.setPlainText(text[:1200])

    @staticmethod
    def _human_error(error: str) -> str:
        return _human_error(error)  # delegate to module-level helper

    def _render_status(self, message: str, *, danger: bool = False):
        status = self.ai.provider_status()
        connected = "error" if danger or status.get("fallback") else "conectado"
        if status.get("provider") == "simulated":
            connected = "simulado"
        key_text = "sí" if status.get("has_key") else "no"
        safe = (
            f"Estado: {connected}\n"
            f"Proveedor: {status.get('provider')}\n"
            f"Modelo: {status.get('model')}\n"
            f"Base URL: {status.get('base_url') or '—'}\n"
            f"API key configurada: {key_text}\n"
            f"Último resultado: {message}"
        )
        self.status_label.setText(safe)
        if self.on_status:
            self.on_status(message)


# ── Tab builders for ConfigPanel ──────────────────────────────────────────

_CHATBOT_SYSTEM_PROMPT_ES = (
    "Eres el asistente de ayuda de Dendro. Tu función es explicar cómo usar la aplicación Dendro "
    "de forma clara, breve y práctica. "
    "Responde en español. "
    "No crees entidades, personajes, relaciones, escenas, canon ni contenido narrativo "
    "salvo que el usuario pida explícitamente un ejemplo. "
    "No modifiques proyectos. No actúes como generador narrativo. "
    "Si el usuario saluda, responde con una bienvenida breve y ofrece ayuda sobre funciones de la app."
)
_CHATBOT_SYSTEM_PROMPT_EN = (
    "You are the Dendro help assistant. Your role is to explain how to use the Dendro application "
    "in a clear, brief, and practical way. "
    "Respond in English. "
    "Do not create entities, characters, relationships, scenes, canon, or narrative content "
    "unless the user explicitly asks for an example. "
    "Do not modify projects. Do not act as a narrative generator. "
    "If the user greets you, respond with a brief welcome and offer help about the app's features."
)

_FONT_SIZE_MAP = {"Pequeño": "small", "Mediano": "medium", "Grande": "large"}
_FONT_SIZE_MAP_REV = {"small": 0, "medium": 1, "large": 2}
_FONT_FAMILY_MAP = {"Georgia": "Georgia", "Courier New": "Courier New", "Serif genérico": "serif"}
_ANIM_MAP = {"Baja": "low", "Normal": "normal", "Alta": "high"}
_ANIM_MAP_REV = {"low": 0, "normal": 1, "high": 2}


def _build_appearance_tab(ctx, on_apply=None, parent: QWidget | None = None) -> QWidget:
    """Build the Apariencia tab content."""
    tab = QWidget(parent)
    lay = QVBoxLayout(tab)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(10)

    card = Card("Apariencia", "Personaliza el aspecto visual de Dendro.")
    form = QFormLayout()
    form.setSpacing(10)

    # Font size
    font_size_combo = QComboBox()
    font_size_combo.addItems(list(_FONT_SIZE_MAP.keys()))
    idx = _FONT_SIZE_MAP_REV.get(ctx.font_size, 1)
    font_size_combo.setCurrentIndex(idx)
    form.addRow("Tamaño de fuente", font_size_combo)

    # Font family
    font_family_combo = QComboBox()
    font_family_combo.addItems(list(_FONT_FAMILY_MAP.keys()))
    fam_idx = font_family_combo.findText(ctx.font_family)
    font_family_combo.setCurrentIndex(fam_idx if fam_idx >= 0 else 0)
    form.addRow("Familia tipográfica", font_family_combo)

    # Animation intensity
    anim_combo = QComboBox()
    anim_combo.addItems(list(_ANIM_MAP.keys()))
    anim_idx = _ANIM_MAP_REV.get(ctx.animation_intensity, 1)
    anim_combo.setCurrentIndex(anim_idx)
    form.addRow("Intensidad de animación", anim_combo)

    # Language
    lang_combo = QComboBox()
    lang_combo.addItems(["Español", "English"])
    current_lang = getattr(ctx, 'language', 'es')
    lang_combo.setCurrentIndex(0 if current_lang == 'es' else 1)
    form.addRow("Idioma", lang_combo)

    card.layout.addLayout(form)
    lay.addWidget(card)

    # Save button
    def _save_appearance():
        ctx.font_size = _FONT_SIZE_MAP.get(font_size_combo.currentText(), "medium")
        ctx.font_family = _FONT_FAMILY_MAP.get(font_family_combo.currentText(), "Georgia")
        ctx.animation_intensity = _ANIM_MAP.get(anim_combo.currentText(), "normal")
        ctx.language = 'es' if lang_combo.currentText() == "Español" else 'en'
        ctx.save_preferences()
        status_lbl.setText("✓ Preferencias de apariencia guardadas")
        if on_apply:
            on_apply()

    save_btn = QPushButton("Guardar preferencias")
    save_btn.setObjectName("primaryButton")
    save_btn.clicked.connect(_save_appearance)
    lay.addWidget(save_btn)

    status_lbl = QLabel("")
    status_lbl.setObjectName("mutedLabel")
    status_lbl.setWordWrap(True)
    lay.addWidget(status_lbl)

    lay.addStretch(1)
    return tab


def _build_ia_tab(ctx, ai_controller, on_status, parent: QWidget | None = None) -> QWidget:
    """Build the IA tab with provider config + mini chatbot."""
    tab = QWidget(parent)
    lay = QVBoxLayout(tab)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(10)

    # ── Provider config section ──
    provider_card = Card("Proveedor IA", "Configura el proveedor sin mostrar la clave en claro.")
    form = QFormLayout()
    form.setSpacing(10)

    status = ai_controller.provider_status() if ai_controller else {}

    provider_combo = QComboBox()
    provider_combo.addItems(["simulated", "openai_compatible"])
    current_provider = str(status.get("provider", "simulated") or "simulated")
    p_idx = provider_combo.findText(current_provider)
    provider_combo.setCurrentIndex(p_idx if p_idx >= 0 else 0)

    base_url_edit = QLineEdit(str(status.get("base_url", "") or ""))
    base_url_edit.setPlaceholderText("https://api.example.com/v1")

    model_edit = QLineEdit(str(status.get("model", "") or ""))
    model_edit.setPlaceholderText("modelo")

    api_key_edit = QLineEdit("")
    api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
    api_key_edit.setPlaceholderText("Mantener actual" if status.get("has_key") else "API key / token")

    form.addRow("Proveedor", provider_combo)
    form.addRow("Base URL", base_url_edit)
    form.addRow("Modelo", model_edit)
    form.addRow("API key / token", api_key_edit)

    # Temperature
    temp_slider = QSlider(Qt.Orientation.Horizontal)
    temp_slider.setRange(0, 20)  # 0.0 - 2.0 with 0.1 steps
    temp_slider.setValue(int(round(float(getattr(ctx, "ai_temperature", 0.7)) * 10)))
    temp_label = QLabel("0.7")
    temp_row = QHBoxLayout()
    temp_row.addWidget(temp_slider)
    temp_row.addWidget(temp_label)
    temp_slider.valueChanged.connect(lambda v: temp_label.setText(f"{v / 10:.1f}"))
    form.addRow("Temperatura", temp_row)

    # Timeout
    timeout_combo = QComboBox()
    timeout_combo.addItems(["30s", "60s", "120s", "180s", "300s"])
    timeout_value = f"{getattr(ctx, 'ai_timeout', '300')}s"
    timeout_idx = timeout_combo.findText(timeout_value)
    timeout_combo.setCurrentIndex(timeout_idx if timeout_idx >= 0 else 4)
    form.addRow("Timeout", timeout_combo)

    provider_card.layout.addLayout(form)
    lay.addWidget(provider_card)

    # ── Save + Test buttons ──
    btn_row = QHBoxLayout()
    ia_status_label = QLabel("")
    ia_status_label.setObjectName("mutedLabel")
    ia_status_label.setWordWrap(True)

    def _save_ia_env():
        prov = provider_combo.currentText().strip() or "simulated"
        base_url = base_url_edit.text().strip()
        model = model_edit.text().strip()
        timeout_text = timeout_combo.currentText().replace("s", "")
        temperature = temp_slider.value() / 10
        key = api_key_edit.text().strip()

        ctx.ai_provider = prov
        ctx.ai_base_url = base_url
        ctx.ai_model = model
        ctx.ai_timeout = timeout_text
        ctx.ai_temperature = temperature
        if key:
            ctx.ai_api_key = key
            api_key_edit.clear()
            api_key_edit.setPlaceholderText("Clave guardada")
        ctx.save_preferences()

        os.environ["NARRATIVE_AI_PROVIDER"] = prov
        os.environ["NARRATIVE_AI_BASE_URL"] = base_url
        os.environ["NARRATIVE_AI_MODEL"] = model
        os.environ["NARRATIVE_AI_TIMEOUT"] = timeout_text
        if ctx.ai_api_key:
            os.environ["NARRATIVE_AI_API_KEY"] = ctx.ai_api_key
        try:
            ai_controller.__init__(ai_controller.ps)
        except Exception as exc:
            ia_status_label.setText(f"Error reconfigurando IA: {exc}")
            return
        ia_status_label.setText("Configuración IA guardada")
        if on_status:
            on_status("Configuración IA guardada")

    save_ia_btn = QPushButton("Guardar configuración")
    save_ia_btn.setObjectName("primaryButton")
    save_ia_btn.clicked.connect(_save_ia_env)
    btn_row.addWidget(save_ia_btn)

    def _test_connection():
        _save_ia_env()
        test_btn.setEnabled(False)
        save_ia_btn.setEnabled(False)
        ia_status_label.setText("Conectando...")

        def _on_test_result(result):
            test_btn.setEnabled(True)
            save_ia_btn.setEnabled(True)
            if isinstance(result, Exception):
                ia_status_label.setText(f"Error: {_human_error(str(result))}")
                return
            if hasattr(result, "error"):
                ia_status_label.setText(f"Error: {result.error}")
                return
            resp = result.value
            error = getattr(resp, "error", None)
            if error:
                ia_status_label.setText(_human_error(str(error)))
                return
            provider = getattr(resp, "provider", "?")
            ia_status_label.setText(f"Conectado: {provider}")
            if on_status:
                on_status(f"Conectado: {provider}")

        worker = _AIWorker(ai_controller)
        worker.finished.connect(_on_test_result)
        worker.start()
        # Keep reference to prevent GC
        _test_connection._worker = worker

    test_btn = QPushButton("Probar conexión")
    test_btn.clicked.connect(_test_connection)
    btn_row.addWidget(test_btn)
    lay.addLayout(btn_row)
    lay.addWidget(ia_status_label)

    # ── Mini chatbot area ──
    chat_card = Card("Asistente Dendro", "Pregunta sobre las funcionalidades de la app.")
    chat_history = QTextEdit()
    chat_history.setReadOnly(True)
    chat_history.setMinimumHeight(120)
    chat_history.setMaximumHeight(200)
    chat_history.setPlaceholderText("Las respuestas del asistente aparecerán aquí...")
    chat_card.layout.addWidget(chat_history)

    chat_input_row = QHBoxLayout()
    chat_input = QLineEdit()
    chat_input.setPlaceholderText("Escribe tu pregunta...")
    chat_input_row.addWidget(chat_input, stretch=1)

    def _send_chat_message():
        user_msg = chat_input.text().strip()
        if not user_msg:
            return
        chat_input.clear()
        chat_history.append(f"<b>Tú:</b> {user_msg}")
        chat_history.append("<i>Esperando respuesta...</i>")
        send_btn.setEnabled(False)
        chat_input.setEnabled(False)

        s = ai_controller.provider_status() if ai_controller else {}
        if s.get("provider") == "simulated" or not s.get("has_key"):
            # Remove "thinking" line
            cursor = chat_history.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.movePosition(cursor.MoveOperation.StartOfBlock, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
            chat_history.append(
                "<span style='color: #8A6849;'>Configura un proveedor IA (con API key) para usar el asistente.</span>"
            )
            send_btn.setEnabled(True)
            chat_input.setEnabled(True)
            return

        def _on_chat_result(text, error):
            send_btn.setEnabled(True)
            chat_input.setEnabled(True)
            # Remove "thinking" line
            cursor = chat_history.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.movePosition(cursor.MoveOperation.StartOfBlock, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()

            if error:
                msg = _human_error(error)
                chat_history.append(f"<span style='color: #8A4E43;'>{msg}</span>")
                return
            chat_history.append(f"<b>Asistente:</b> {text[:600]}")

        # Determine language for system prompt
        lang = getattr(ctx, 'language', 'es')
        if lang == 'en':
            sys_prompt = _CHATBOT_SYSTEM_PROMPT_EN
        else:
            sys_prompt = _CHATBOT_SYSTEM_PROMPT_ES

        worker = _AIChatWorker(ai_controller, sys_prompt, user_msg)
        worker.finished.connect(_on_chat_result)
        worker.start()
        _send_chat_message._worker = worker

    send_btn = QPushButton("Enviar")
    send_btn.clicked.connect(_send_chat_message)
    chat_input.returnPressed.connect(_send_chat_message)
    chat_input_row.addWidget(send_btn)
    chat_card.layout.addLayout(chat_input_row)

    lay.addWidget(chat_card)
    lay.addStretch(1)
    return tab


class ConfigPanel(QWidget):
    """Tabbed configuration panel with Apariencia and IA tabs."""

    def __init__(
        self,
        *,
        ctx,
        ai_controller=None,
        on_status=None,
        on_apply=None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.ctx = ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = SectionHeader("Configuración", "Apariencia, IA y opciones avanzadas.")
        header.layout().setContentsMargins(18, 16, 18, 4)
        root.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Tab 1: Apariencia
        appearance = _build_appearance_tab(ctx, on_apply=on_apply, parent=self)
        self.tabs.addTab(appearance, "Apariencia")

        # Tab 2: IA
        ia = _build_ia_tab(ctx, ai_controller, on_status, self)
        self.tabs.addTab(ia, "IA")

        root.addWidget(self.tabs, stretch=1)
