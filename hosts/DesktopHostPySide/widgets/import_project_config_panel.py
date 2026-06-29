"""ImportProjectConfigPanel — revisión de la configuración propuesta (I13).

Muestra la propuesta de configuración que la IA generó al importar un documento
(``basket.metadata['project_config_suggestion']``): calendario (modo + nombre +
año presente + eras), ubicación temporal de entidades, anillos, hitos y tono/género.
El núcleo del calendario es editable; al aceptar, guarda las ediciones y aplica
la configuración (calendario + ubicación temporal + anillos + hitos + tono/género) en un paso.

No escribe persistencia directamente: delega en el ImportController.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import Badge, SectionHeader
from packages.domain.result import Error

_MODE_LABELS: list[tuple[str, str]] = [
    ("Sin calendario", "none"),
    ("Periodos vagos", "vague_periods"),
    ("Calendario completo", "full_calendar"),
]


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("mutedLabel")
    label.setWordWrap(True)
    return label


class ImportProjectConfigPanel(QWidget):
    def __init__(
        self,
        proposal: dict[str, Any],
        controller: Any,
        *,
        basket_id: str,
        on_decision: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.proposal = proposal or {}
        self.controller = controller
        self.basket_id = basket_id
        self.on_decision = on_decision
        chronology = self.proposal.get("chronology") or {}
        config = self.proposal.get("config") or {}
        placements = self.proposal.get("entity_temporal") or []

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(Badge("Configuración propuesta", "gold"))
        header.addStretch()
        layout.addLayout(header)
        layout.addWidget(SectionHeader("Calendario del proyecto"))

        # ── Calendario (editable: modo, nombre, año presente) ──
        layout.addWidget(QLabel("Modo de calendario"))
        self.mode_combo = QComboBox()
        for label, value in _MODE_LABELS:
            self.mode_combo.addItem(label, value)
        idx = self.mode_combo.findData(str(chronology.get("mode") or "vague_periods"))
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        layout.addWidget(self.mode_combo)

        layout.addWidget(QLabel("Nombre del calendario"))
        self.name_edit = QLineEdit(str(chronology.get("calendar_name") or ""))
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Año presente"))
        present = chronology.get("present_year")
        self.year_edit = QLineEdit("" if present is None else str(present))
        layout.addWidget(self.year_edit)

        # ── Eras (solo lectura) ──
        eras = [e for e in (chronology.get("eras") or []) if isinstance(e, dict)]
        if eras:
            layout.addWidget(QLabel("Eras detectadas"))
            for era in eras:
                start, end = era.get("start_year"), era.get("end_year")
                span = ""
                if start is not None:
                    span = f" ({start}–{end if end is not None else '…'})"
                layout.addWidget(_muted(f"• {era.get('name', '?')}{span}"))

        # ── Ubicación temporal de entidades (solo lectura) ──
        placed = [p for p in placements if isinstance(p, dict) and p.get("name")]
        if placed:
            layout.addWidget(SectionHeader("Entidades en el tiempo"))
            for place in placed:
                birth = place.get("birth_year")
                death = place.get("death_year")
                when = ""
                if birth is not None or death is not None:
                    b = birth if birth is not None else "?"
                    d = death if death is not None else "?"
                    when = f" · {b}–{d}"
                nature = place.get("nature", "mortal")
                layout.addWidget(_muted(f"• {place['name']} [{nature}]{when}"))

        # ── Anillos / capas causales propuestos (solo lectura) ──
        world_layers = self.proposal.get("world_layers") or {}
        activated = list(world_layers.get("activate_default_layer_ids") or [])
        custom = [c for c in (world_layers.get("custom_layers") or []) if isinstance(c, dict)]
        if activated or custom:
            layout.addWidget(SectionHeader("Anillos (capas causales)"))
            for layer_id in activated:
                layout.addWidget(_muted(f"• {layer_id} (predefinido)"))
            for layer in custom:
                role = str(layer.get("causal_role") or "")
                suffix = f" — {role}" if role else ""
                layout.addWidget(_muted(f"• {layer.get('name', '?')} (a medida){suffix}"))

        # ── Hitos propuestos (solo lectura) ──
        milestones = [m for m in (self.proposal.get("milestones") or []) if isinstance(m, dict)]
        if milestones:
            layout.addWidget(SectionHeader("Hitos en la cronología"))
            for hito in milestones:
                year = hito.get("year")
                when = f" · año {year}" if year is not None else ""
                layout.addWidget(_muted(f"• {hito.get('title', '?')}{when}"))

        # ── Tono / género (solo lectura) ──
        tone, genre = str(config.get("tone") or ""), str(config.get("genre") or "")
        if tone or genre:
            layout.addWidget(SectionHeader("Otros ajustes"))
            if tone:
                layout.addWidget(_muted(f"Tono: {tone}"))
            if genre:
                layout.addWidget(_muted(f"Género: {genre}"))
            layout.addWidget(_muted("(Se aplican solo si el proyecto no los tenía fijados.)"))

        layout.addStretch()
        self.status = QLabel("")
        self.status.setObjectName("mutedLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        close_btn = QPushButton("Volver")
        close_btn.clicked.connect(lambda: self._finish("close"))
        discard_btn = QPushButton("Descartar")
        discard_btn.clicked.connect(self._discard)
        accept_btn = QPushButton("Aceptar")
        accept_btn.setObjectName("primaryButton")
        accept_btn.clicked.connect(self._accept)
        actions.addWidget(close_btn)
        actions.addStretch()
        actions.addWidget(discard_btn)
        actions.addWidget(accept_btn)
        layout.addLayout(actions)

    def _collect_edits(self) -> dict[str, Any]:
        return {
            "mode": self.mode_combo.currentData(),
            "calendar_name": self.name_edit.text().strip(),
            "present_year": self.year_edit.text().strip(),
        }

    def _accept(self):
        edited = self.controller.update_project_config_suggestion(
            self.basket_id, self._collect_edits()
        )
        if isinstance(edited, Error):
            self.status.setText(f"No se pudo guardar la edición: {edited.error}")
            return
        result = self.controller.apply_project_config_suggestion(self.basket_id)
        if isinstance(result, Error):
            self.status.setText(f"No se pudo aplicar: {result.error}")
            return
        self.status.setText("Configuración aplicada al proyecto.")
        self._finish("accept")

    def _discard(self):
        result = self.controller.discard_project_config_suggestion(self.basket_id)
        if isinstance(result, Error):
            self.status.setText(f"No se pudo descartar: {result.error}")
            return
        self.status.setText("Propuesta descartada.")
        self._finish("discard")

    def _finish(self, decision: str):
        if self.on_decision:
            self.on_decision(decision)
