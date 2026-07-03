"""Modo Foco (BETA2-FOCO): escritorio causal centrado en una entidad.

Paquete NUEVO a propósito: toda la lógica del Modo Foco vive aquí y
`views/workspaces.py` solo recibe diffs de integración acotados (la restricción
de auditoría "no refactor amplio" se respeta en espíritu).
"""

from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoCanvas, FocoSatelliteItem
from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

__all__ = ["FocoCanvas", "FocoSatelliteItem", "FocoView"]
