"""Punto de entrada para ``python -m narrative_architect``.

Delega en la capa CLI de UI (``packages.ui.cli``), que consume los servicios
de application. Importar este módulo NO ejecuta la CLI: la ejecución solo
ocurre vía :func:`main` (script de consola ``narrative-architect``) o al
correr ``python -m narrative_architect``.
"""

from packages.ui.cli import main as _cli_main


def main() -> None:
    """Entry point del script ``narrative-architect`` (delega en packages.ui.cli)."""
    _cli_main()


if __name__ == "__main__":
    main()
