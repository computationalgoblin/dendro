"""BETA2-SHIP-07: los fallos de acciones del usuario avisan de forma VISIBLE.

El panel de log de la UI está oculto (main_window: self.log setVisible(False)), así
que un `ctx.log("error"/"warning", …)` como feedback terminal de una acción que el
usuario inicia deja el botón "muerto". La auditoría encontró 69 sitios así; este test
guarda contra la regresión de los caminos de mayor tráfico, exigiendo que su mensaje
viaje por `ctx.notify(...)` (toast visible), no por `ctx.log(...)`.

Validación por FUENTE: los handlers no se instancian sin un CreationWorkspace completo
(patrón de la casa). El aviso visible de `ctx.notify` está probado aparte en
test_ai_unconfigured_feedback (notify_sink → ToastLayer).
"""

from __future__ import annotations

import re
from pathlib import Path

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
_MILESTONE = Path("hosts/DesktopHostPySide/widgets/milestone_detail_panel.py").read_text(
    encoding="utf-8"
)
_RELATION = Path("hosts/DesktopHostPySide/widgets/relation_detail_panel.py").read_text(
    encoding="utf-8"
)
_NODE = Path("hosts/DesktopHostPySide/widgets/node_detail_panel.py").read_text(encoding="utf-8")


def _notify_line(src: str, needle: str) -> bool:
    """El mensaje que contiene `needle` viaja en un ctx.notify, no en un ctx.log."""
    for line in src.splitlines():
        if needle in line and ".notify(" in line:
            return True
    return False


def _not_logged(src: str, needle: str) -> bool:
    """`needle` no aparece en ningún ctx.log("error"/"warning", ...)."""
    for line in src.splitlines():
        if needle in line and re.search(r'\.log\(\s*"(error|warning)"', line):
            return False
    return True


# ── Gestos de primera hora en el lienzo (Tier 1) ─────────────────────────────

WORKSPACE_MESSAGES = [
    "Ya existe una relación entre esas entidades",
    "No se puede crear una relación sobre la misma entidad",
    "Anidamiento cíclico",
    "Error asignando a la rama",
    "Error moviendo al anillo",
    "Error creando hoja",
    "Error creando rama",
    "Errores al eliminar",
    "Error eliminando anillo",
    "No se pudo estimar el coste del riego",
]


def test_canvas_failures_are_visible():
    for msg in WORKSPACE_MESSAGES:
        assert _notify_line(_WORKSPACES, msg), f"«{msg}» debería avisar por notify (visible)"
        assert _not_logged(_WORKSPACES, msg), f"«{msg}» sigue en un ctx.log oculto"


def test_structural_accept_failure_is_visible():
    # Asimetría corregida: el éxito ya hacía notify("...","success"); el fallo, no.
    assert _notify_line(_WORKSPACES, 'No se pudo aplicar el ajuste')


# ── Acciones discretas de los paneles de detalle ─────────────────────────────


def test_detail_panel_discrete_actions_are_visible():
    assert _notify_line(_NODE, "Error convirtiendo en rama")
    assert _notify_line(_NODE, "No se pudo convertir en rama")
    assert _notify_line(_RELATION, "result.error")  # archive()
    # Subhitos + borrado de hito: 4 notify tras la conversión.
    assert _MILESTONE.count('self.ctx.notify(result.error, "error")') >= 4
