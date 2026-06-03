"""Dendro settings panels for B31 UX fix.

All panels live inside RightDrawer; no normal-flow modal dialogs. They call
callbacks/controllers supplied by MainWindow and do not import persistence.
"""
from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import Card, SectionHeader


class _PanelBase(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 18)
        self.layout.setSpacing(12)
        self.layout.addWidget(SectionHeader(title, subtitle))

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


class AppConfigPanel(_PanelBase):
    """Grouped UX/configuration actions."""

    def __init__(
        self,
        *,
        advanced_enabled: bool,
        diagnostic_visible: bool,
        callbacks: dict[str, Callable],
        parent: QWidget | None = None,
    ):
        super().__init__("Configuración", "Apariencia, modo avanzado, diagnóstico y conexión IA.", parent)

        ux = Card("Apariencia / UX", "Tema Dendro claro, cálido y minimalista.")
        ux.add_text("Paleta: blanco roto, oliva apagado, verde grisáceo y beige musgo.", muted=True)
        self.layout.addWidget(ux)

        mode = Card("Modo de trabajo", "Normal para creación; avanzado para tablas, IDs, JSON y diagnóstico.")
        self.advanced_check = QCheckBox("Modo avanzado")
        self.advanced_check.setChecked(bool(advanced_enabled))
        self.advanced_check.toggled.connect(lambda _: callbacks["toggle_advanced"]())
        mode.layout.addWidget(self.advanced_check)
        self.diagnostic_check = QCheckBox("Mostrar diagnóstico")
        self.diagnostic_check.setChecked(bool(diagnostic_visible))
        self.diagnostic_check.setEnabled(bool(advanced_enabled))
        self.diagnostic_check.toggled.connect(lambda _: callbacks["toggle_diagnostic"]())
        mode.layout.addWidget(self.diagnostic_check)
        self.layout.addWidget(mode)

        ai = Card("IA", "Estado y credenciales del proveedor, sin exponer secretos.")
        ai.layout.addWidget(self._action_button("Ajustes IA", callbacks["ai_settings"], primary=True))
        self.layout.addWidget(ai)
        self.layout.addStretch(1)


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
        save = QPushButton("Guardar en esta sesión")
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
            self.api_key.setPlaceholderText("Clave guardada para esta sesión")
        # Recreate orchestrator so Test uses the new runtime env.
        try:
            self.ai.__init__(self.ai.ps)
        except Exception as exc:
            self._render_status(f"Error reconfigurando IA: {exc}", danger=True)
            return
        self._render_status("Configuración IA actualizada para esta sesión")

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

    def _human_error(self, error: str) -> str:
        if "403" in error:
            return "Error 403: el proveedor rechazó la petición. Revisa API key, permisos o modelo."
        if "401" in error:
            return "Error 401: credenciales inválidas o ausentes."
        return f"Error IA: {error}"

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
