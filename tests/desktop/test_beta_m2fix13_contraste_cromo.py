"""BETA2-FIX-13 · TANDA A — contraste de los tokens del CROMO (G2-17).

Aritmética pura sobre los tokens: no necesita QApplication.

Frontera declarada con BETA2-FIX-01: aquel ticket es el dueño de los
tokens que consumen los dos LIENZOS (`EARTH*`, relleno de nodo, tinta de las
etiquetas de hito); este fija los del cromo — tintas de panel, botón primario,
bordes de control y la paleta CATEGÓRICA como token.
"""
from __future__ import annotations

import itertools
import math
import re
from pathlib import Path

from hosts.DesktopHostPySide.widgets import design_system as ds
from packages.domain.entity import EntityType
from packages.domain.relation import RelationType

_AA = 4.5   # WCAG 1.4.3 — texto normal
_UI = 3.0   # WCAG 1.4.11 — componentes de interfaz y objetos gráficos

# Las superficies del sistema sobre las que de verdad se pinta texto de panel.
_SUPERFICIES = ("SURFACE", "SURFACE_HI", "PAPER", "WELL")


def _superficie(nombre: str) -> str:
    return getattr(ds, nombre)


# ── ΔE (CIE76) — distancia perceptual entre dos colores ────────────────────


def _lab(hex_color: str) -> tuple[float, float, float]:
    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    h = hex_color.lstrip("#")
    r, g, b = (_lin(int(h[i : i + 2], 16) / 255.0) for i in (0, 2, 4))
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505

    def _f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = _f(x / 0.95047), _f(y / 1.0), _f(z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _delta_e(a: str, b: str) -> float:
    return math.dist(_lab(a), _lab(b))


# ── 1. tintas de texto ─────────────────────────────────────────────────────


def test_beta_m2fix13_tintas_de_texto_cumplen_AA() -> None:
    """Hoy (antes del arreglo): 2,93 / 2,58 / 2,30 para INK_MUTED y 4,24 para
    INK_SOFT sobre PAPER. Ninguna tinta que se use como TEXTO puede bajar de AA
    sobre la superficie en la que se usa."""
    fallos = []
    for tinta in ("INK", "INK_STRONG", "INK_SOFT", "INK_MUTED"):
        for nombre in _SUPERFICIES:
            ratio = ds.contrast_ratio(getattr(ds, tinta), _superficie(nombre))
            if ratio < _AA:
                fallos.append(f"{tinta} sobre {nombre} = {ratio:.2f}")
    assert not fallos, "tintas de texto por debajo de AA: " + " · ".join(fallos)


def test_beta_m2fix13_la_jerarquia_de_tinta_sigue_teniendo_tres_peldanos() -> None:
    """Subir INK_MUTED no puede aplanar la escalera a dos niveles (pregunta
    abierta 2 del ticket): los tres peldaños deben seguir distinguiéndose."""
    assert _delta_e(ds.INK, ds.INK_SOFT) >= 4.0
    assert _delta_e(ds.INK_SOFT, ds.INK_MUTED) >= 4.0


# ── 2. botón primario ──────────────────────────────────────────────────────


def test_beta_m2fix13_boton_primario_cumple_AA_en_todo_el_gradiente() -> None:
    """El primario NO es un color plano: es `qlineargradient(GOLD → GOLD_DEEP)`.
    El 4,01:1 medido por la diseñadora era correcto pero correspondía al stop
    SUPERIOR; el inferior daba 5,73:1. Se exigen los dos extremos."""
    for stop in (ds.GOLD, ds.GOLD_DEEP, ds.GOLD_PRESS):
        assert ds.contrast_ratio(ds.INK_INVERSE, stop) >= _AA, stop
    # …y el gradiente sigue siendo un gradiente (los stops no se colapsaron).
    assert ds.GOLD != ds.GOLD_DEEP


def test_beta_m2fix13_el_qss_del_primario_usa_los_stops_guardados() -> None:
    qss = ds.APP_STYLESHEET
    assert "QPushButton#primaryButton" in qss
    bloque = qss.split("QPushButton#primaryButton", 1)[1][:400]
    assert ds.GOLD in bloque and ds.GOLD_DEEP in bloque
    assert ds.INK_INVERSE in bloque


# ── 3. el oro como TEXTO ───────────────────────────────────────────────────


_HOST = Path("hosts/DesktopHostPySide")
# Play tiene fondo OSCURO por diseño (modo inmersivo): el oro claro ahí es texto
# claro sobre oscuro, no oro sobre tarjeta. Queda fuera por escrito.
_FUERA_DEL_CROMO = ("widgets/play/",)


def _fuentes_del_cromo() -> list[Path]:
    return [
        p
        for p in _HOST.rglob("*.py")
        if not any(marca in p.as_posix() for marca in _FUERA_DEL_CROMO)
    ]


def test_beta_m2fix13_oro_como_texto_o_no_se_usa() -> None:
    """`GOLD_SOFT` (2,02:1) no puede ser color de TEXTO sobre tarjeta. `GOLD`, tras
    bajarlo un peldaño, sí llega a AA — así que se permite y se guarda su ratio."""
    assert ds.contrast_ratio(ds.GOLD, ds.SURFACE) >= _AA
    assert ds.contrast_ratio(ds.GOLD_DEEP, ds.SURFACE_HI) >= _AA
    assert ds.contrast_ratio(ds.GOLD_SOFT, ds.SURFACE) < _AA  # por eso no es texto

    # `(?<![-\w])` para no cazar `border-color:` ni `selection-background-color:`.
    patron = re.compile(
        r"(?<![-\w])color:\s*(?:\{GOLD_SOFT\}|" + re.escape(ds.GOLD_SOFT) + r")"
    )
    culpables = [
        p.as_posix() for p in _fuentes_del_cromo() if patron.search(p.read_text(encoding="utf-8"))
    ]
    assert not culpables, f"GOLD_SOFT usado como color de texto en el cromo: {culpables}"


# ── 4. bordes de control (WCAG 1.4.11) ─────────────────────────────────────


def test_beta_m2fix13_bordes_de_control_cumplen_1_4_11() -> None:
    """`LINE` da 1,43:1 sobre SURFACE: sirve de ornamento, no de «aquí hay un
    control». `LINE_CONTROL` es el token que porta el 3:1 de WCAG 1.4.11."""
    for nombre in (*_SUPERFICIES, "INPUT_BG"):
        ratio = ds.contrast_ratio(ds.LINE_CONTROL, _superficie(nombre))
        assert ratio >= _UI, f"LINE_CONTROL sobre {nombre} = {ratio:.2f}"


def test_beta_m2fix13_el_qss_usa_el_borde_de_control_en_botones_y_campos() -> None:
    qss = ds.APP_STYLESHEET
    boton = qss.split("QPushButton {", 1)[1].split("}", 1)[0]
    assert ds.LINE_CONTROL in boton, "el borde base del botón no porta el 3:1"
    campos = qss.split("QTextEdit, QPlainTextEdit, QLineEdit, QComboBox", 1)[1].split("}", 1)[0]
    assert ds.LINE_CONTROL in campos, "el borde base de los campos no porta el 3:1"


# ── 5. paleta categórica ───────────────────────────────────────────────────


def test_beta_m2fix13_paleta_categorica_completa() -> None:
    """14 de 21 `EntityType` y 17 de 41 `RelationType` no tenían color propio —
    entre ellos `causo` y `fue_causado_por`, la columna vertebral causal."""
    sin_color_e = [t.value for t in EntityType if t.value not in ds.ENTITY_KIND_PALETTE]
    assert not sin_color_e, f"EntityType sin color: {sin_color_e}"
    sin_color_r = [t.value for t in RelationType if t.value not in ds.RELATION_KIND_PALETTE]
    assert not sin_color_r, f"RelationType sin color: {sin_color_r}"


def test_beta_m2fix13_las_claves_muertas_estan_declaradas_por_escrito() -> None:
    """Las claves que no corresponden a ningún tipo del dominio se toleran, pero
    SOLO si están declaradas: una paleta con un color reservado para
    `es_familiar_de` —un tipo que el dominio no define— es una pista falsa."""
    tipos_e = {t.value for t in EntityType}
    huerfanas_e = {k for k in ds.ENTITY_KIND_PALETTE if k not in tipos_e}
    assert huerfanas_e == set(ds._ENTITY_LEGACY_KEYS), huerfanas_e

    tipos_r = {t.value for t in RelationType}
    huerfanas_r = {k for k in ds.RELATION_KIND_PALETTE if k not in tipos_r}
    assert huerfanas_r == set(ds._RELATION_LEGACY_KEYS), huerfanas_r


# Pares que YA estaban por debajo de ΔE 10 entre los 9 hex históricos. No se
# tocan: `test_ux15_entity_palette.py::test_equivalencia_de_hex_con_valores_previos`
# los fija, y moverlos sería un cambio visual que nadie pidió (criterio 5).
_DEUDA_HEREDADA = {
    frozenset(("concepto", "nota")),
    frozenset(("contenedor", "nota")),
    frozenset(("concepto", "contenedor")),
    frozenset(("organizacion", "evento")),
}


def test_beta_m2fix13_los_colores_de_entidad_se_distinguen_entre_si() -> None:
    pal = {k: v for k, v in ds.ENTITY_KIND_PALETTE.items() if k != "lugar"}  # alias de localizacion
    juntos = []
    for a, b in itertools.combinations(sorted(pal), 2):
        if frozenset((a, b)) in _DEUDA_HEREDADA:
            continue
        distancia = _delta_e(pal[a], pal[b])
        if distancia < 10.0:
            juntos.append(f"{a}/{b} = ΔE {distancia:.1f}")
    assert not juntos, "tipos de entidad indistinguibles: " + " · ".join(juntos)


def test_beta_m2fix13_los_hex_historicos_no_se_movieron() -> None:
    """Criterio 5: añadir sí, mover no."""
    for clave, hexv in (
        ("personaje", "#C07B53"),
        ("lugar", "#7E9568"),
        ("localizacion", "#7E9568"),
        ("organizacion", "#B28A3C"),
        ("faccion", "#A65C54"),
        ("objeto", "#937083"),
        ("evento", "#C8A24C"),
        ("concepto", "#8E8A6A"),
        ("contenedor", "#A89878"),
        ("nota", "#9A8E72"),
    ):
        assert ds.ENTITY_KIND_PALETTE[clave] == hexv, clave
    for clave, hexv in (
        ("pertenece_a", "#B28A3C"),
        ("es_enemigo_de", "#A65C54"),
        ("es_aliado_de", "#7E9568"),
    ):
        assert ds.RELATION_KIND_PALETTE[clave] == hexv, clave


def test_beta_m2fix13_cada_relacion_lleva_el_tono_de_su_familia() -> None:
    """El color de una relación identifica su FAMILIA de significado, no el tipo
    concreto (dos aliados y una protección comparten salvia a propósito). Lo que
    se guarda es que no aparezcan tonos sueltos fuera del catálogo de familias."""
    tonos = set(ds.RELATION_FAMILY_TONES.values())
    intrusos = {
        clave: color
        for clave, color in ds.RELATION_KIND_PALETTE.items()
        if color not in tonos and clave not in ds._RELATION_LEGACY_KEYS
    }
    assert not intrusos, f"tonos fuera del catálogo de familias: {intrusos}"
    # La causalidad —la columna vertebral del producto— ya no cae al neutro.
    for clave in ("causo", "fue_causado_por"):
        assert ds.RELATION_KIND_PALETTE[clave] == ds.RELATION_FAMILY_TONES["causalidad"]
        assert ds.RELATION_KIND_PALETTE[clave] != ds._RELATION_KIND_DEFAULT


def test_beta_m2fix13_la_paleta_sigue_siendo_calida() -> None:
    """Ningún azul/púrpura frío se cuela con los colores nuevos (regla UX05/UX21)."""
    frios = {"#7C9BFF", "#7EC8A5", "#D46A6A", "#C9A5FF", "#9BB4C7", "#A4AEC0"}
    assert not (set(ds.ENTITY_KIND_PALETTE.values()) & frios)
    assert not (set(ds.RELATION_KIND_PALETTE.values()) & frios)
    for color in (*ds.ENTITY_KIND_PALETTE.values(), *ds.RELATION_KIND_PALETTE.values()):
        h = color.lstrip("#")
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
        assert not (b > r + 24 and b > g + 24), f"{color} es un azul frío"
