"""BETA2-FIX-01 (criterio 6) — contraste de los estados del jardín.

Vera midió sobre píxeles que los dos estados de salud se separaban entre sí
1,17:1; calculado sobre los tokens da exactamente lo mismo. Sedienta («necesita
atención») y secada («pausada a propósito») llevan acciones OPUESTAS y eran el
mismo color, y ninguno de los dos se despegaba del pergamino (1,09:1).

Este fichero es la red que impide que ese contraste se vuelva a perder — también
desde BETA2-FIX-13, que toca el mismo `design_system.py`.

NOTA HONESTA sobre el alcance del criterio. El enunciado pedía además que el
«relleno sano» alcanzara 3:1 contra la parada más oscura de la viñeta (#CFC4A8).
Eso es IMPOSIBLE: el blanco puro tiene un techo de 1,733:1 contra ese fondo, así
que NINGÚN relleno claro puede cumplirlo, y oscurecer la hoja sana destruiría la
identidad del producto («hojas BLANCAS») y su texto interior. Lo que sí se puede
—y es lo que WCAG 1.4.11 mide en un componente— es que su BORDE porte el
contraste: por eso existe `LEAF_EDGE` y por eso se comprueba aquí, con el techo
matemático escrito como test para que nadie vuelva a intentarlo a ciegas.
"""

from __future__ import annotations

from hosts.DesktopHostPySide.widgets.design_system import (
    CANVAS,
    CHRONO_INK,
    CHRONO_VIGNETTE,
    EARTH_GREY_TINT,
    EARTH_INK,
    EARTH_INK_SOFT,
    EARTH_TINT,
    LEAF_EDGE,
)

# Parada MÁS OSCURA de la viñeta del lienzo: el color dominante real bajo los
# nodos (Idoia midió que es el 58,8 % de los píxeles del Mapa).
VINETA_OSCURA = "#CFC4A8"
# Relleno de la hoja sana (graph_canvas: QColor(255, 255, 253, 250)).
HOJA_SANA = "#FFFFFD"
# Mínimo AA para componentes NO textuales (WCAG 1.4.11).
AA_NO_TEXTO = 3.0
# Mínimo AA para texto normal (WCAG 1.4.3).
AA_TEXTO = 4.5


def _canal(valor: int) -> float:
    c = valor / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(hex_color: str) -> float:
    """Luminancia relativa WCAG de un color #RRGGBB."""
    raw = hex_color.lstrip("#")
    r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def contraste(a: str, b: str) -> float:
    """Razón de contraste WCAG entre dos colores (>= 1.0)."""
    la, lb = luminancia(a), luminancia(b)
    alto, bajo = max(la, lb), min(la, lb)
    return (alto + 0.05) / (bajo + 0.05)


def test_beta_m2fix01_la_formula_de_contraste_es_correcta():
    # Anclas conocidas: la fórmula tiene que dar los valores de manual.
    assert abs(contraste("#FFFFFF", "#000000") - 21.0) < 0.01
    assert abs(contraste("#FFFFFF", "#FFFFFF") - 1.0) < 1e-9
    # Y la viñeta oscura del lienzo es la parada final declarada en el token.
    assert CHRONO_VIGNETTE[-1][1].upper() == VINETA_OSCURA


def test_beta_m2fix01_sedienta_se_despega_del_lienzo():
    # ANTES: 1,086:1 contra la viñeta y 1,417:1 contra CANVAS — invisible.
    assert contraste(EARTH_TINT, VINETA_OSCURA) >= AA_NO_TEXTO
    assert contraste(EARTH_TINT, CANVAS) >= AA_NO_TEXTO


def test_beta_m2fix01_secada_se_despega_del_lienzo():
    # ANTES: 1,078:1 contra la viñeta.
    assert contraste(EARTH_GREY_TINT, VINETA_OSCURA) >= AA_NO_TEXTO
    assert contraste(EARTH_GREY_TINT, CANVAS) >= AA_NO_TEXTO


def test_beta_m2fix01_sedienta_y_secada_se_distinguen_entre_si():
    # ANTES: 1,171:1 — el valor exacto que Vera midió sobre píxeles. Dos estados
    # de significado opuesto no pueden ser el mismo color.
    assert contraste(EARTH_TINT, EARTH_GREY_TINT) >= AA_NO_TEXTO


def test_beta_m2fix01_el_perimetro_de_la_hoja_sana_porta_el_contraste():
    # El relleno sano NO puede cumplir 3:1 (ver el techo, abajo): lo cumple su
    # borde, que es el límite del componente que WCAG mide.
    assert contraste(LEAF_EDGE, VINETA_OSCURA) >= AA_NO_TEXTO
    assert contraste(LEAF_EDGE, CANVAS) >= AA_NO_TEXTO
    # …y el borde tiene que verse contra el propio relleno de la hoja.
    assert contraste(LEAF_EDGE, HOJA_SANA) >= AA_NO_TEXTO


def test_beta_m2fix01_techo_matematico_del_relleno_claro():
    """Deja constancia de POR QUÉ el relleno sano no cumple 3:1.

    Ningún color puede superar el blanco puro; contra #CFC4A8 el blanco da
    1,733:1. Cualquiera que en el futuro «suba el contraste del relleno sano»
    está persiguiendo algo imposible: el canal correcto es el borde."""
    techo = contraste("#FFFFFF", VINETA_OSCURA)
    assert techo < AA_NO_TEXTO
    assert abs(techo - 1.733) < 0.01
    assert contraste(HOJA_SANA, VINETA_OSCURA) <= techo


def test_beta_m2fix01_el_texto_sobre_tierra_sigue_siendo_legible():
    # El arreglo de contraste del jardín no puede comerse el arreglo de
    # legibilidad del nombre (criterio 1): sobre relleno oscuro, tinta clara.
    assert contraste(EARTH_INK, EARTH_TINT) >= AA_TEXTO
    assert contraste(EARTH_INK, EARTH_GREY_TINT) >= AA_TEXTO
    assert contraste(EARTH_INK_SOFT, EARTH_TINT) >= AA_NO_TEXTO
    assert contraste(EARTH_INK_SOFT, EARTH_GREY_TINT) >= AA_NO_TEXTO
    # La tinta OSCURA de antes ya no vale sobre tierra: por eso se invierte.
    assert contraste("#111827", EARTH_GREY_TINT) < AA_TEXTO


def test_beta_m2fix01_las_etiquetas_de_hito_se_leen_sobre_su_pildora():
    # Criterio 6, mitad cronología: la tinta de la etiqueta de hito sobre la
    # píldora de pergamino en la que se pinta.
    assert contraste(CHRONO_INK, "#FBF8EF") >= AA_TEXTO


def test_beta_m2fix01_los_tokens_del_jardin_los_consume_el_lienzo():
    # Guardia de acoplamiento: si alguien renombra los tokens, el Mapa deja de
    # compilar antes de que este test mienta.
    from hosts.DesktopHostPySide.widgets.graph_canvas import (
        _WATERING_TINT_FILL,
    )

    assert _WATERING_TINT_FILL["sedienta"] == EARTH_TINT
    assert _WATERING_TINT_FILL["secada"] == EARTH_GREY_TINT
