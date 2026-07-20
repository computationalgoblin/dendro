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
from hosts.DesktopHostPySide.widgets.design_system import apply_light_theme

_crash_notifier = None


def set_crash_notifier(notifier) -> None:
    """SHIP-03: registra cómo avisar al usuario tras una recuperación (lo fija
    ``main()`` cuando la ventana ya existe). ``notifier(log_path)``, fail-soft."""
    global _crash_notifier
    _crash_notifier = notifier


def _crash_log_path() -> Path:
    """SHIP-03: el registro de crashes va al data_dir del usuario, no al cwd
    (en una instalación real el cwd puede no ser escribible ni encontrable)."""
    base = Path.home() / ".narrative-architect"
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base / "dendro_crash.log"
    except Exception:  # noqa: BLE001 — mejor el cwd que perder el rastro
        return Path.cwd() / "dendro_crash.log"


def _install_crash_guard() -> None:
    """BETA1-UX2D: la app NO debe cerrarse de golpe ante una excepción suelta.

    En PySide6, una excepción no capturada dentro de un slot/evento de Qt aborta
    el proceso (parece un "crash" sin rastro). Instalamos:
    - ``faulthandler`` → vuelca un traceback nativo si hay un segfault de C++.
    - ``sys.excepthook`` propio → registra el traceback completo (consola + fichero
      ``dendro_crash.log`` en el data_dir del usuario, SHIP-03) y DEVUELVE el
      control al bucle de eventos, de modo que un fallo aislado no tumba la
      sesión. Si hay notificador registrado, el usuario ve un aviso no bloqueante.
    """
    faulthandler.enable()

    log_path = _crash_log_path()

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
        if _crash_notifier is not None:
            try:
                _crash_notifier(log_path)
            except Exception:  # noqa: BLE001 — el aviso nunca debe romper el guard
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
    # BETA2-FOCO-17: tema claro SIEMPRE (Fusion + paleta Dendro). Sin esto,
    # Windows en modo oscuro imponía texto casi blanco sobre pergamino y
    # tooltips ilegibles (la causa raíz de la antigua supresión global de
    # tooltips de BETA1-F00, que se retira: ahora QToolTip va estilado).
    apply_light_theme(app)
    w = MainWindow(); w.show()
    # SHIP-03: con la ventana viva, una recuperación de error se comunica (toast).
    set_crash_notifier(
        lambda log_path: w.ctx.notify(
            f"Dendro se ha recuperado de un error. Registro: {log_path}", "error"
        )
    )
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
