"""DesktopHost entry point — PySide6 MVP (B27.1)."""
from __future__ import annotations

import faulthandler
import sys
import traceback
from pathlib import Path

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 not installed. Run: pip install narrative-architect[desktop]")
    sys.exit(1)
from hosts.DesktopHostPySide.main_window import MainWindow
from hosts.DesktopHostPySide.widgets.tooltip_suppression import install_tooltip_suppression


def _install_crash_guard() -> None:
    """BETA1-UX2D: la app NO debe cerrarse de golpe ante una excepción suelta.

    En PySide6, una excepción no capturada dentro de un slot/evento de Qt aborta
    el proceso (parece un "crash" sin rastro). Instalamos:
    - ``faulthandler`` → vuelca un traceback nativo si hay un segfault de C++.
    - ``sys.excepthook`` propio → registra el traceback completo (consola + fichero
      ``dendro_crash.log`` junto al ejecutable) y DEVUELVE el control al bucle de
      eventos, de modo que un fallo aislado no tumba la sesión. El rastro queda
      para diagnosticar la causa raíz.
    """
    faulthandler.enable()

    log_path = Path.cwd() / "dendro_crash.log"

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write("\n[DENDRO] Excepción no controlada (la app sigue viva):\n")
        sys.stderr.write(text)
        sys.stderr.flush()
        try:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("=== excepción ===\n")
                fh.write(text)
        except Exception:  # noqa: BLE001 — el log nunca debe romper el guard
            pass

    sys.excepthook = hook


def _enable_msaa() -> None:
    """BETA1-UX2A: MSAA por defecto para que los bordes (anillos, hojas, líneas
    de vida) se vean suaves cuando el canvas se acelera por GPU (OpenGL). Debe
    fijarse ANTES de crear el QApplication. Inofensivo si no hay GPU.

    BETA1-UX2D: además forzamos el buffer ALFA a 0 (superficie OPACA). Con el
    valor por defecto (-1), algunos drivers asignan canal alfa a la superficie del
    QOpenGLWidget y la VENTANA acaba siendo translúcida (se veía el fondo de
    escritorio detrás de la cronología). Sobre esa superficie con alfa, el
    viewport RASTER de la cronología dejaba fragmentos obsoletos al repintar por
    regiones (píldoras de nombre que se quedaban VACÍAS, etiquetas sin píldora) al
    clicar. Una superficie opaca elimina la translucidez y esos artefactos."""
    try:
        from PySide6.QtGui import QSurfaceFormat

        fmt = QSurfaceFormat.defaultFormat()
        fmt.setSamples(4)
        fmt.setAlphaBufferSize(0)
        QSurfaceFormat.setDefaultFormat(fmt)
    except Exception:  # noqa: BLE001 — el pulido nunca debe impedir arrancar
        pass


def main():
    _install_crash_guard()
    _enable_msaa()
    app = QApplication(sys.argv)
    install_tooltip_suppression(app)
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
