"""Rail de herramientas del Modo Foco (BETA2-FOCO-11 · BETA2-UX-05).

Estilo Photoshop: UNA columna vertical de botones-icono (SVG teñibles, tooltips
claros, sin texto). Las herramientas actúan al click — sin modo herramienta
persistente — y se ILUMINAN/deshabilitan según la selección (``set_selection_
context``). Si una herramienta necesita datos, FocoView abre un popover junto al
botón (``anchor_for``).

BETA2-UX-05: los clústeres casi-duplicados (los 4 «fantasma» y los 3 de «riego»)
se agrupan bajo un botón-grupo que despliega un flyout con sus herramientas, para
que un principiante no tenga que desambiguar 15 iconos por hover. La API pública
(``toolTriggered`` / ``button`` / ``anchor_for`` / ``enabled_tools`` /
``set_selection_context``) se conserva por ``tool_id``: los botones agrupados
siguen existiendo (viven en el flyout) y ``anchor_for`` devuelve el botón-grupo
visible para anclar sus popovers.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_DEEP,
    GOLD_SOFT,
    INK_SOFT,
    SURFACE_HI,
)

# (tool_id, icono, tooltip). El orden de referencia (todas las herramientas).
TOOL_SPECS: tuple[tuple[str, str, str], ...] = (
    ("create_entity", "tool_create_entity", "Crear entidad"),
    ("create_related", "tool_create_related", "Crear entidad relacionada con la del foco"),
    ("create_relation", "tool_create_relation", "Crear relación desde la entidad en foco"),
    ("ghost_relation", "tool_ghost_relation", "Crear relación fantasma (vínculo pendiente)"),
    ("add_to_branch", "tool_add_to_branch", "Añadir la entidad en foco a una rama"),
    ("create_branch", "tool_create_branch", "Crear rama contenedora de la entidad en foco"),
    ("create_in_branch", "tool_create_entity", "Crear una entidad dentro de esta rama"),
    # BETA2-CLEANUP-PANELES: crear anillo (estrato del mundo) desde el Foco.
    # Icono real en disco (no el alias "rings"): worldbuilding = coronas concéntricas.
    ("create_ring", "worldbuilding", "Crear anillo (estrato del mundo)"),
    ("ghost_node", "tool_ghost_node", "Crear nodo fantasma (borrador interno)"),
    ("ghost_convert", "tool_ghost_convert", "Convertir el fantasma en entidad real"),
    ("ghost_link", "tool_ghost_link", "Vincular el fantasma con una entidad existente"),
    ("view_map", "tool_view_map", "Ver esta entidad en el Mapa global"),
    ("view_chrono", "tool_view_chrono", "Ver esta entidad en la Cronología global"),
)

# BETA2-UX-05: (group_id, icono, tooltip, (tool_ids…)). Los clústeres casi-
# duplicados se pliegan bajo un botón-grupo con flyout.
# BETA2-FOCO-32: el grupo «riego» (regar/secar/cultivar) se retiró del rail — el
# riego/secado/cultivo vive ahora en el Cuaderno de Cultivo, el chip de siguiente
# paso y el badge 💧; «Crear hito» también se retiró (obsoleto en el rail).
_TOOL_GROUPS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "ghost",
        "tool_ghost_node",
        "Fantasmas: nodo/relación pendiente, convertir y vincular",
        ("ghost_relation", "ghost_node", "ghost_convert", "ghost_link"),
    ),
)

# Orden de la COLUMNA (spec: menos afordancias de primer nivel). Cada entrada es
# un tool_id suelto o ("group", group_id).
_COLUMN: tuple[object, ...] = (
    "create_entity",
    "create_related",
    "create_relation",
    ("group", "ghost"),
    "add_to_branch",
    "create_branch",
    "create_in_branch",
    "create_ring",
    "view_map",
    "view_chrono",
)

_BUTTON_STYLE = (
    "QPushButton { background: rgba(255,255,255,0.55); border: 1px solid %(line)s; "
    "border-radius: 16px; padding: 0; } "
    "QPushButton:hover:enabled { background: %(hover)s; border: 1px solid %(gold)s; } "
    "QPushButton:disabled { background: rgba(255,255,255,0.22); border: 1px solid #E3DCC8; }"
)


class FocoToolRail(QFrame):
    """Columna de herramientas con grupos plegables; emite ``toolTriggered(tool_id)``."""

    toolTriggered = Signal(str)  # noqa: N815 — convención Qt de señales

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focoToolRail")
        self.setStyleSheet(
            f"QFrame#focoToolRail {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 18px; }}"
        )
        self._style = _BUTTON_STYLE % {"line": "#D8D6C8", "hover": "#ECE4C7", "gold": GOLD_DEEP}
        self._tooltips = {tid: tip for tid, _icon, tip in TOOL_SPECS}
        self._icons = {tid: icon for tid, icon, _tip in TOOL_SPECS}
        self._buttons: dict[str, QPushButton] = {}
        # tool_id agrupado → (group_id, botón-grupo, flyout)
        self._group_of: dict[str, str] = {}
        self._group_buttons: dict[str, QPushButton] = {}
        self._group_flyouts: dict[str, QFrame] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 8, 5, 8)
        layout.setSpacing(4)

        groups = {gid: (icon, tip, tools) for gid, icon, tip, tools in _TOOL_GROUPS}
        for entry in _COLUMN:
            if isinstance(entry, tuple) and entry[0] == "group":
                gid = entry[1]
                icon, tip, tools = groups[gid]
                layout.addWidget(self._build_group(gid, icon, tip, tools))
            else:
                layout.addWidget(self._make_tool_button(str(entry), parent=self))
        layout.addStretch(1)
        self.set_selection_context({})

    # ── construcción ─────────────────────────────────────────────────────────

    def _make_tool_button(self, tool_id: str, parent: QWidget) -> QPushButton:
        button = QPushButton(parent)
        button.setFixedSize(32, 32)
        button.setToolTip(self._tooltips.get(tool_id, tool_id))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(icons.icon(self._icons.get(tool_id, ""), color=INK_SOFT, size=17))
        button.setStyleSheet(self._style)
        button.clicked.connect(lambda _=False, t=tool_id: self.toolTriggered.emit(t))
        self._buttons[tool_id] = button
        return button

    def _build_group(
        self, gid: str, icon: str, tooltip: str, tools: tuple[str, ...]
    ) -> QPushButton:
        group_btn = QPushButton(self)
        group_btn.setFixedSize(32, 32)
        group_btn.setToolTip(tooltip)
        group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        group_btn.setIcon(icons.icon(icon, color=GOLD_DEEP, size=17))
        group_btn.setStyleSheet(self._style)
        self._group_buttons[gid] = group_btn

        flyout = QFrame(self, Qt.WindowType.Popup)
        flyout.setObjectName("focoToolFlyout")
        flyout.setStyleSheet(
            f"QFrame#focoToolFlyout {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 16px; }}"
        )
        row = QHBoxLayout(flyout)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(4)
        for tool_id in tools:
            btn = self._make_tool_button(tool_id, parent=flyout)
            # Al elegir una herramienta del grupo, cierra el flyout.
            btn.clicked.connect(lambda _=False, f=flyout: f.hide())
            row.addWidget(btn)
            self._group_of[tool_id] = gid
        self._group_flyouts[gid] = flyout

        group_btn.clicked.connect(lambda _=False, g=gid: self._toggle_group(g))
        return group_btn

    def _toggle_group(self, gid: str) -> None:
        flyout = self._group_flyouts[gid]
        if flyout.isVisible():
            flyout.hide()
            return
        flyout.adjustSize()
        anchor = self._group_buttons[gid]
        top_right = anchor.mapToGlobal(anchor.rect().topRight())
        flyout.move(top_right.x() + 6, top_right.y())
        flyout.show()

    # ── API pública (estable por tool_id) ─────────────────────────────────────

    def button(self, tool_id: str) -> QPushButton | None:
        return self._buttons.get(tool_id)

    def anchor_for(self, tool_id: str) -> QWidget:
        # Para una herramienta agrupada, el ancla visible es su botón-grupo (el
        # botón real vive en el flyout, que puede estar cerrado).
        gid = self._group_of.get(tool_id)
        if gid is not None:
            return self._group_buttons.get(gid, self)
        return self._buttons.get(tool_id, self)

    def enabled_tools(self) -> list[str]:
        return [tool_id for tool_id, button in self._buttons.items() if button.isEnabled()]

    def set_selection_context(self, context: dict) -> None:
        """Ilumina las herramientas aplicables a la selección actual (spec)."""
        has_project = bool(context.get("has_project"))
        center = str(context.get("center_id") or "")
        center_is_ghost = bool(context.get("center_is_ghost"))
        center_is_branch = bool(context.get("center_is_branch"))
        ghost_in_scope = center_is_ghost or bool(context.get("selection_has_ghost"))

        enabled: dict[str, bool] = {
            "create_entity": has_project,
            "ghost_node": has_project,
            "create_related": bool(center),
            "create_relation": bool(center),
            "ghost_relation": bool(center),
            "add_to_branch": bool(center) and not center_is_ghost,
            "create_branch": bool(center) and not center_is_ghost,
            # BETA2-FOCO-32: solo tiene sentido cuando el foco es una rama.
            "create_in_branch": has_project and center_is_branch and not center_is_ghost,
            # BETA2-CLEANUP-PANELES: crear anillo no depende del centro.
            "create_ring": has_project,
            "ghost_convert": ghost_in_scope,
            "ghost_link": ghost_in_scope,
            "view_map": bool(center),
            "view_chrono": bool(center),
        }
        for tool_id, button in self._buttons.items():
            button.setEnabled(bool(enabled.get(tool_id, False)))
        # BETA2-UX-05: un botón-grupo se habilita si alguna de sus herramientas lo está.
        for gid, _icon, _tip, tools in _TOOL_GROUPS:
            group_btn = self._group_buttons.get(gid)
            if group_btn is not None:
                group_btn.setEnabled(any(enabled.get(t, False) for t in tools))
