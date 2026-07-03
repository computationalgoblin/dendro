"""Rail de herramientas del Modo Foco (BETA2-FOCO-11).

Estilo Photoshop: UNA única columna vertical de botones-icono (SVG teñibles,
tooltips claros, sin texto). Las herramientas actúan al click — sin modo
herramienta persistente — y se ILUMINAN/deshabilitan según la selección actual
(``set_selection_context``). Si una herramienta necesita datos, FocoView abre
un popover junto al botón (``anchor_for``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_DEEP,
    GOLD_SOFT,
    INK_SOFT,
    SURFACE_HI,
)

# (tool_id, icono, tooltip). El orden es el del rail (spec: herramientas mínimas).
TOOL_SPECS: tuple[tuple[str, str, str], ...] = (
    ("create_entity", "tool_create_entity", "Crear entidad"),
    ("create_related", "tool_create_related", "Crear entidad relacionada con la del foco"),
    ("create_relation", "tool_create_relation", "Crear relación desde la entidad en foco"),
    ("ghost_relation", "tool_ghost_relation", "Crear relación fantasma (vínculo pendiente)"),
    ("add_to_branch", "tool_add_to_branch", "Añadir la entidad en foco a una rama"),
    ("create_branch", "tool_create_branch", "Crear rama contenedora de la entidad en foco"),
    ("create_milestone", "tool_create_milestone", "Crear hito ligado a la entidad en foco"),
    ("ghost_node", "tool_ghost_node", "Crear nodo fantasma (borrador interno)"),
    ("ghost_convert", "tool_ghost_convert", "Convertir el fantasma en entidad real"),
    ("ghost_link", "tool_ghost_link", "Vincular el fantasma con una entidad existente"),
    ("water", "tool_water", "Regar (diagnóstico IA autorizado de la selección)"),
    ("dry", "tool_dry", "Secar (sacar del ciclo de riego, sin IA)"),
    ("cultivate", "tool_cultivate", "Cultivar (volver al ciclo de riego, sin IA)"),
    ("view_map", "tool_view_map", "Ver esta entidad en el Mapa global"),
    ("view_chrono", "tool_view_chrono", "Ver esta entidad en la Cronología global"),
)

_BUTTON_STYLE = (
    "QPushButton { background: rgba(255,255,255,0.55); border: 1px solid %(line)s; "
    "border-radius: 16px; padding: 0; } "
    "QPushButton:hover:enabled { background: %(hover)s; border: 1px solid %(gold)s; } "
    "QPushButton:disabled { background: rgba(255,255,255,0.22); border: 1px solid #E3DCC8; }"
)


class FocoToolRail(QFrame):
    """Columna única de herramientas; emite ``toolTriggered(tool_id)``."""

    toolTriggered = Signal(str)  # noqa: N815 — convención Qt de señales

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focoToolRail")
        self.setStyleSheet(
            f"QFrame#focoToolRail {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 18px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 8, 5, 8)
        layout.setSpacing(4)
        self._buttons: dict[str, QPushButton] = {}
        style = _BUTTON_STYLE % {"line": "#D8D6C8", "hover": "#ECE4C7", "gold": GOLD_DEEP}
        for tool_id, icon_name, tooltip in TOOL_SPECS:
            button = QPushButton(self)
            button.setFixedSize(32, 32)
            button.setToolTip(tooltip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(icons.icon(icon_name, color=INK_SOFT, size=17))
            button.setStyleSheet(style)
            button.clicked.connect(lambda _=False, t=tool_id: self.toolTriggered.emit(t))
            layout.addWidget(button)
            self._buttons[tool_id] = button
        layout.addStretch(1)
        self.set_selection_context({})

    def button(self, tool_id: str) -> QPushButton | None:
        return self._buttons.get(tool_id)

    def anchor_for(self, tool_id: str) -> QWidget:
        return self._buttons.get(tool_id, self)

    def enabled_tools(self) -> list[str]:
        return [tool_id for tool_id, button in self._buttons.items() if button.isEnabled()]

    def set_selection_context(self, context: dict) -> None:
        """Ilumina las herramientas aplicables a la selección actual (spec)."""
        has_project = bool(context.get("has_project"))
        center = str(context.get("center_id") or "")
        center_is_ghost = bool(context.get("center_is_ghost"))
        center_is_paused = bool(context.get("center_is_paused"))
        selection = list(context.get("selection") or [])
        ghost_in_scope = center_is_ghost or bool(context.get("selection_has_ghost"))
        waterable = bool(center) and not center_is_ghost or bool(selection)

        enabled: dict[str, bool] = {
            "create_entity": has_project,
            "ghost_node": has_project,
            "create_related": bool(center),
            "create_relation": bool(center),
            "ghost_relation": bool(center),
            "add_to_branch": bool(center) and not center_is_ghost,
            "create_branch": bool(center) and not center_is_ghost,
            "create_milestone": bool(center) and not center_is_ghost,
            "ghost_convert": ghost_in_scope,
            "ghost_link": ghost_in_scope,
            "water": has_project and waterable and not center_is_paused,
            "dry": bool(center) and not center_is_ghost and not center_is_paused,
            "cultivate": center_is_paused,  # solo aparece útil para Secadas (spec)
            "view_map": bool(center),
            "view_chrono": bool(center),
        }
        for tool_id, button in self._buttons.items():
            button.setEnabled(bool(enabled.get(tool_id, False)))
