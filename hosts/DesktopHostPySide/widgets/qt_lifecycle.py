"""Utilidades de ciclo de vida de widgets Qt compartidas por el host Desktop.

PySide6/Qt puede destruir el objeto C++ subyacente de un QWidget (deleteLater,
reparentado, reconstrucción de escena) mientras el wrapper Python sigue vivo.
Acceder a ese widget lanza `RuntimeError: Internal C++ object already deleted`.

- `_qt_alive` comprueba la validez puntual de un widget antes de tocarlo.
- `_qt_safe_slot` decora un método-slot diferido para que NO se ejecute si su
  `self` ya fue destruido (y traga el RuntimeError si un hijo muere a mitad).
- `_qt_safe_timer` es un `QTimer.singleShot` que no dispara si el widget murió.
"""

from __future__ import annotations

import functools


def _qt_alive(widget) -> bool:
    """True si el QWidget Python sigue envolviendo un objeto C++ vivo (no borrado)."""
    if widget is None:
        return False
    try:
        import shiboken6

        return bool(shiboken6.isValid(widget))
    except Exception:  # noqa: BLE001 — sin shiboken, asume vivo
        return True


def _is_deleted_error(exc: RuntimeError) -> bool:
    """True si el RuntimeError es el típico de libshiboken por objeto borrado."""
    return "already deleted" in str(exc).lower()


def _qt_safe_slot(method):
    """Decorador para slots/callbacks DIFERIDOS de un QWidget (señales de hilos,
    QTimer, lambdas conectadas). No ejecuta el cuerpo si `self` ya fue destruido,
    y absorbe el `RuntimeError: ... already deleted` si un widget hijo muere
    mientras el método corre. Pensado para métodos void (su retorno se ignora)."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not _qt_alive(self):
            return None
        try:
            return method(self, *args, **kwargs)
        except RuntimeError as exc:
            if _is_deleted_error(exc):
                return None
            raise

    return wrapper


def _qt_safe_timer(widget, delay_ms: int, callback, *args) -> None:
    """Como `QTimer.singleShot(delay_ms, callback)` pero no invoca `callback` si
    `widget` fue destruido antes de que el temporizador dispare. `widget` es el
    objeto cuyo ciclo de vida condiciona la ejecución (normalmente la vista que
    posee el callback)."""
    from PySide6.QtCore import QTimer

    def _guarded() -> None:
        if not _qt_alive(widget):
            return
        try:
            callback(*args)
        except RuntimeError as exc:
            if not _is_deleted_error(exc):
                raise

    QTimer.singleShot(delay_ms, _guarded)
