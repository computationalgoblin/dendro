"""BETA1-UX2A: viewport acelerado por GPU (OpenGL) para los QGraphicsView del
canvas, con *fallback* automático a raster (software).

El render por software a 30 fps hacía que el movimiento (paneo, zoom, física)
se viera "escalonado". Un viewport OpenGL delega la composición a la GPU y, con
MSAA (ver main._enable_msaa) + 60 fps, el canvas va fluido.

Es un no-op seguro bajo la plataforma ``offscreen`` (arnés de captura/tests, que
no tiene contexto GL) y ante cualquier fallo de inicialización de OpenGL: en esos
casos se conserva el viewport raster por defecto.
"""
from __future__ import annotations

import os


def install_gpu_viewport(view) -> bool:
    """Instala un ``QOpenGLWidget`` como viewport de *view*.

    Devuelve ``True`` si lo logró; ``False`` si se mantiene el viewport raster
    (offscreen o GL no disponible). Nunca lanza.
    """
    if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
        return False
    try:
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        from PySide6.QtWidgets import QGraphicsView

        view.setViewport(QOpenGLWidget())
        # Con OpenGL, el repintado parcial no compone bien; repintar todo el
        # viewport cada frame es lo recomendado y lo más fluido aquí.
        view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        return True
    except Exception:  # noqa: BLE001 — el pulido nunca debe romper el arranque
        return False


__all__ = ["install_gpu_viewport"]
