"""Arnés de captura para la épica de pulido visual (BETA1-UX).

Monta la app real (MainWindow) fuera de pantalla, carga el proyecto demo y
guarda PNGs de las superficies clave (Home, Creación, Canvas y, best-effort,
un panel de detalle). Sirve para comparar "antes/después" en cada tarea y
enseñar el progreso.

Usa la plataforma Qt real por defecto (fuentes/iconos fieles). Para modo
headless/CI exporta ``QT_QPA_PLATFORM=offscreen`` (el texto saldrá en cajas).

Uso:
    python -m tests.desktop._visual.capture --out docs/ui_captures --label baseline

No es un test (sin prefijo ``test_``); pytest no lo recoge.
"""

from __future__ import annotations

# Nota: NO forzamos QT_QPA_PLATFORM aquí. En Windows, la plataforma "offscreen"
# no carga las fuentes del sistema y el texto sale en cajas (□), inútil para
# verificar tipografía/iconos. Por defecto dejamos la plataforma real (fiel) y
# movemos la ventana fuera de pantalla para no molestar. Para modo headless/CI,
# exporta QT_QPA_PLATFORM=offscreen antes de invocar.
import argparse
import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

WIN_W, WIN_H = 1440, 900


def _pump(app: QApplication, rounds: int = 8) -> None:
    """Procesa eventos varias veces para que el layout/anim se asienten."""
    for _ in range(rounds):
        app.processEvents()


def _grab(widget: QWidget, out: Path, label: str) -> Path | None:
    """Renderiza un widget a PNG. Devuelve la ruta o None si no se pudo."""
    try:
        if widget is None:
            return None
        pix = widget.grab()
        if pix.isNull() or pix.width() < 4 or pix.height() < 4:
            return None
        dest = out / f"{label}.png"
        pix.save(str(dest))
        return dest
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] no se pudo capturar {label}: {exc}")
        return None


def capture(out_dir: str | Path, label: str = "baseline") -> list[Path]:
    out = Path(out_dir) / label
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)

    # 1) Proyecto demo en disco temporal.
    from tests.desktop._visual.demo_project import build_demo_project

    demo_path = Path(tempfile.mkdtemp(prefix="dendro_demo_")) / "demo_dendro.json"
    manifest = build_demo_project(demo_path)

    # 2) App real, offscreen, tamaño fijo.
    from hosts.DesktopHostPySide.main_window import (  # noqa: E402
        _IDX_CREATION,
        MainWindow,
    )

    # BETA1-UX06: encuadre de cámara INSTANTÁNEO para las capturas (las
    # animaciones no terminan con processEvents sin tiempo real; queremos el
    # encuadre final, no un fotograma a medias).
    from hosts.DesktopHostPySide.widgets import graph_canvas as _gc

    _gc.MOTION_ENABLED = False

    mw = MainWindow()
    mw.resize(WIN_W, WIN_H)
    # Fuera de la pantalla visible: render fiel sin molestar al usuario.
    mw.move(-5000, -5000)
    mw.show()
    _pump(app)

    saved: list[Path] = []

    # 3) Home (portal).
    home = _grab(getattr(mw, "home_view", None), out, "home")
    if home:
        saved.append(home)

    # 4) Cargar el demo y entrar a Creación.
    try:
        mw.controller.open(str(demo_path))
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] no se pudo abrir el demo: {exc}")
    if hasattr(mw, "_refresh_all_views"):
        mw._refresh_all_views()
    _pump(app)
    try:
        mw._go_space(_IDX_CREATION)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] no se pudo navegar a Creación: {exc}")
    _pump(app, rounds=16)

    # 5) Creación completa + canvas aislado.
    full = _grab(mw, out, "creation_full")
    if full:
        saved.append(full)
    canvas = _grab(getattr(mw.creation_workspace, "graph", None), out, "canvas")
    if canvas:
        saved.append(canvas)

    # 5b) Vista cronológica (best-effort).
    try:
        ws = mw.creation_workspace
        if hasattr(ws, "set_active_view"):
            ws.set_active_view("chrono")
            _pump(app, rounds=16)
            chrono = getattr(ws, "chrono", None)
            if chrono is not None and hasattr(chrono, "fit_all"):
                chrono.fit_all()
            _pump(app, rounds=8)
            chrono_img = _grab(chrono, out, "chrono")
            if chrono_img:
                saved.append(chrono_img)
            ws.set_active_view("concentric")  # restaurar
            _pump(app, rounds=8)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] no se pudo capturar la vista cronológica: {exc}")

    # 6) Panel de detalle de nodo (best-effort).
    try:
        if manifest.entity_ids:
            mw.creation_workspace._open_node_panel(manifest.entity_ids[1])
            drawer = getattr(mw, "drawer", None)
            if drawer is not None and hasattr(drawer, "update_target_width"):
                drawer.update_target_width()
            _pump(app, rounds=24)
            panel = _grab(drawer, out, "panel_nodo")
            if panel:
                saved.append(panel)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] no se pudo capturar panel de nodo: {exc}")

    print(f"Capturas en {out} ({len(saved)}):")
    for p in saved:
        print(f"  - {p.name}")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Captura visual offscreen (BETA1-UX)")
    parser.add_argument("--out", default="docs/ui_captures", help="directorio raíz de salida")
    parser.add_argument("--label", default="baseline", help="subcarpeta/etiqueta de la tanda")
    args = parser.parse_args()
    capture(args.out, args.label)


if __name__ == "__main__":
    main()
