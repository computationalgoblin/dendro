"""BETA-CIERRE WS-A — guarda de posicionamiento.

La beta se posiciona como herramienta de worldbuilding narrativo; el rol/GM queda FUERA
del alcance (código dormido, no se promete). Esta guarda estática evita que la voz
promocional de Dendro (Home, About, wizard) vuelva a vender "sesiones / campaña de rol"
como una capacidad del producto.

Es un escaneo de fuente (sin Qt) para poder correr en la puerta rápida.
"""

from __future__ import annotations

from pathlib import Path

_HOST = Path(__file__).resolve().parents[1] / "hosts" / "DesktopHostPySide"

# Frases con las que Dendro *se vendía* a sí mismo como herramienta de rol.
# NO se listan usos legítimos: el alias de dato `world_layer` "campaña,sesiones,…",
# ni el label de project_type "campana" (se tratan en WS-G, no son voz promocional).
_FORBIDDEN_PROMO = [
    "relatos y sesiones",  # subtítulo de Home + About
]


def _read(rel: str) -> str:
    return (_HOST / rel).read_text(encoding="utf-8")


def test_home_and_about_do_not_promise_rpg_sessions():
    for rel in ("views/home_view.py", "main_window.py"):
        src = _read(rel)
        for phrase in _FORBIDDEN_PROMO:
            assert phrase not in src, (
                f"{rel} vuelve a prometer rol/sesiones en la voz de Dendro: {phrase!r}. "
                "La beta es worldbuilding narrativo; el rol queda fuera (BETA-CIERRE WS-A)."
            )


def test_format_suggestions_drop_rpg_campaign():
    # El "Formato" es lo que el producto dice soportar; no debe sugerir "campaña de rol".
    src = _read("widgets/creative_config_panel.py")
    # Aísla el bloque FORMATO_SUGERENCIAS para no chocar con otros usos legítimos.
    assert "FORMATO_SUGERENCIAS" in src
    block = src.split("FORMATO_SUGERENCIAS", 1)[1].split("]", 1)[0]
    assert "campaña de rol" not in block, (
        "FORMATO_SUGERENCIAS vuelve a ofrecer 'campaña de rol' como formato soportado."
    )
