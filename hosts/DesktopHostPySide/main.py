"""DesktopHost entry point — PySide6 MVP (B27.1)."""
from __future__ import annotations

import datetime
import faulthandler
import os
import platform
import sys
import traceback
from pathlib import Path

_crash_notifier = None


def _app_version() -> str:
    try:
        from packages.domain.config import AppConfig

        return AppConfig().app_version
    except Exception:  # noqa: BLE001 — el sello nunca debe romper el guard
        return "?"

# SHIP-06: en el exe empaquetado sin consola (PyInstaller ``console=False``) los
# streams estándar son ``None`` y algún import del árbol revienta ANTES de crear
# la ventana (comprobado: el MISMO exe arranca si el proceso recibe handles
# reales). Sintetizamos stdio de inmediato y los imports pesados (Qt/MainWindow)
# se hacen DENTRO de ``main()``, tras instalar el crash-guard, para que cualquier
# fallo de import acabe en ``dendro_crash.log`` y no en un diálogo mudo.
_stdio_synthesized = False
_stdio_refs: list = []  # mantiene vivos los streams sintéticos toda la sesión


def _ensure_windowed_stdio() -> None:
    """Sustituye stdout/stderr ``None`` (modo windowed) por streams reales."""
    global _stdio_synthesized
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            try:
                stream = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
            except Exception:  # noqa: BLE001 — el stdio nunca impide arrancar
                continue
            _stdio_refs.append(stream)
            setattr(sys, name, stream)
            _stdio_synthesized = True


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


# SHIP-06: faulthandler retiene el descriptor, no el objeto — el stream del volcado
# nativo debe seguir vivo durante toda la sesión (módulo, no local).
_faulthandler_stream = None


def _install_crash_guard() -> None:
    """BETA1-UX2D: la app NO debe cerrarse de golpe ante una excepción suelta.

    En PySide6, una excepción no capturada dentro de un slot/evento de Qt aborta
    el proceso (parece un "crash" sin rastro). Instalamos:
    - ``faulthandler`` → vuelca un traceback nativo si hay un segfault de C++.
    - ``sys.excepthook`` propio → registra el traceback completo (consola + fichero
      ``dendro_crash.log`` en el data_dir del usuario, SHIP-03) y DEVUELVE el
      control al bucle de eventos, de modo que un fallo aislado no tumba la
      sesión. Si hay notificador registrado, el usuario ve un aviso no bloqueante.

    SHIP-06: en el exe empaquetado sin consola (PyInstaller ``console=False``)
    ``sys.stderr``/``sys.stdout`` son ``None`` — ``faulthandler.enable()`` a secas
    reventaba ANTES de crear la ventana. Sin consola, el volcado nativo va
    directamente a ``dendro_crash.log``; y el hook solo escribe a stderr si existe.
    """
    global _faulthandler_stream

    log_path = _crash_log_path()

    stream = sys.stderr
    if stream is None or _stdio_synthesized:
        # Sin consola real (o con stdio sintético a devnull), el volcado nativo
        # de un segfault solo sirve si va al fichero de crashes.
        try:
            stream = log_path.open("a", encoding="utf-8")
            _faulthandler_stream = stream
        except Exception:  # noqa: BLE001 — el guard nunca impide arrancar
            stream = None
    if stream is not None:
        try:
            faulthandler.enable(file=stream)
        except Exception:  # noqa: BLE001 — el guard nunca impide arrancar
            pass

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        if sys.stderr is not None:
            sys.stderr.write("\n[DENDRO] Excepción no controlada (la app sigue viva):\n")
            sys.stderr.write(text)
            sys.stderr.flush()
        try:
            # WS-O: sello versión + OS + timestamp UTC → reportes correlacionables b1→bN.
            stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"=== excepción {stamp} | Dendro {_app_version()} "
                    f"| {platform.platform()} ===\n"
                )
                fh.write(text)
                fh.write("\n")
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
    _ensure_windowed_stdio()
    _install_crash_guard()
    _enable_msaa()
    # SHIP-06: los imports pesados van DESPUÉS del guard — un fallo al importar
    # queda registrado en dendro_crash.log en vez de matar la app sin rastro.
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 not installed. Run: pip install narrative-architect[desktop]")
        sys.exit(1)
    from hosts.DesktopHostPySide.main_window import MainWindow
    from hosts.DesktopHostPySide.widgets.design_system import apply_light_theme

    app = QApplication(sys.argv)
    # BETA2-FOCO-17: tema claro SIEMPRE (Fusion + paleta Dendro). Sin esto,
    # Windows en modo oscuro imponía texto casi blanco sobre pergamino y
    # tooltips ilegibles (la causa raíz de la antigua supresión global de
    # tooltips de BETA1-F00, que se retira: ahora QToolTip va estilado).
    apply_light_theme(app)
    # WS-I/B5: icono de la app (barra de tareas, alt-tab, título). Resuelve tanto en
    # dev como en el exe congelado (los assets viajan bajo _internal/ conservando ruta).
    from pathlib import Path as _Path

    from PySide6.QtGui import QIcon

    _icon = _Path(__file__).resolve().parent / "assets" / "dendro.ico"
    if _icon.exists():
        app.setWindowIcon(QIcon(str(_icon)))
    # WS-M/B3: maximizada de inicio → todo el shell (incluida la barra inferior y Guardar)
    # es siempre alcanzable, también en 1366×768 y 1080p@150%.
    w = MainWindow()
    w.showMaximized()
    # SHIP-03: con la ventana viva, una recuperación de error se comunica (toast).
    set_crash_notifier(
        lambda log_path: w.ctx.notify(
            f"Dendro se ha recuperado de un error. Registro: {log_path}", "error"
        )
    )
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
