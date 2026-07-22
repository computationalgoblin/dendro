"""BETA2-SHIP-07: navegar en Foco no debe perder el borrador recién escrito.

Bug (auditoría de datos): al saltar a otra entidad con el editor abierto (flechas,
satélite, Ctrl+B), _update_center_card → _mount_form hacía deleteLater() del panel
con su temporizador de autoguardado (800 ms) aún armado, perdiendo en silencio lo
tecleado. close_editor SÍ volcaba (_flush_form_autosave); la ruta de navegación no.

Validación por FUENTE: _mount_form no se ejerce sin un FocoView completo. La
corrección canaliza TODAS las rutas de navegación (todas pasan por _mount_form) a
través del flush ya probado que usa close_editor.
"""

from __future__ import annotations

from pathlib import Path

_FOCO = Path("hosts/DesktopHostPySide/widgets/foco/foco_view.py").read_text(encoding="utf-8")


def _method(name: str) -> str:
    return _FOCO.split(f"def {name}(self")[1].split("\n    def ")[0]


def test_mount_form_flushes_before_destroying_panel():
    body = _method("_mount_form")
    flush = body.find("self._flush_form_autosave()")
    delete = body.find("self._form_panel.deleteLater()")
    assert flush != -1, "_mount_form debe volcar el autoguardado pendiente"
    assert delete != -1
    assert flush < delete, "el flush debe ir ANTES del deleteLater (si no, se pierde)"


def test_flush_helper_still_exists_and_stops_timer():
    body = _method("_flush_form_autosave")
    assert "_autosave_timer" in body
    assert "timer.stop()" in body
    assert "form._autosave()" in body
