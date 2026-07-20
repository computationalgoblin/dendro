"""Tests de packages/application/portrait_crop.py (BETA2-IMG-01).

Módulo puro: encuadre normalizado del retrato (centro fraccional + zoom) y su
proyección a rects fuente cuadrados o con proporción arbitraria.
"""

from packages.application.portrait_crop import (
    DEFAULT_CROP,
    MAX_ZOOM,
    PortraitCrop,
    parse_crop,
)


class TestNormalize:
    def test_defaults_ya_normalizados(self):
        assert DEFAULT_CROP.normalize() == PortraitCrop(0.5, 0.5, 1.0)

    def test_clamp_centro_y_zoom(self):
        crop = PortraitCrop(cx=-0.4, cy=1.7, zoom=99.0).normalize()
        assert crop == PortraitCrop(0.0, 1.0, MAX_ZOOM)

    def test_zoom_menor_que_uno_sube_a_uno(self):
        assert PortraitCrop(zoom=0.2).normalize().zoom == 1.0

    def test_valores_no_finitos_degradan_a_default(self):
        crop = PortraitCrop(cx=float("nan"), cy=float("inf"), zoom=float("-inf")).normalize()
        assert crop == PortraitCrop(0.5, 0.5, 1.0)


class TestSourceRect:
    def test_cuadrada_sin_zoom_cubre_todo(self):
        assert DEFAULT_CROP.source_rect(100, 100) == (0, 0, 100)

    def test_imagen_ancha_centra_el_cuadrado(self):
        x, y, side = DEFAULT_CROP.source_rect(300, 100)
        assert (x, y, side) == (100, 0, 100)

    def test_imagen_alta_centra_el_cuadrado(self):
        x, y, side = DEFAULT_CROP.source_rect(100, 300)
        assert (x, y, side) == (0, 100, 100)

    def test_zoom_reduce_el_lado(self):
        _, _, side = PortraitCrop(zoom=2.0).source_rect(200, 100)
        assert side == 50

    def test_centro_en_borde_se_clampa_dentro(self):
        x, y, side = PortraitCrop(cx=1.0, cy=1.0, zoom=2.0).source_rect(200, 100)
        assert side == 50
        assert x == 150  # 200 - 50
        assert y == 50  # 100 - 50

    def test_centro_en_origen_se_clampa_a_cero(self):
        x, y, side = PortraitCrop(cx=0.0, cy=0.0, zoom=2.0).source_rect(200, 100)
        assert (x, y) == (0, 0)
        assert side == 50

    def test_dimensiones_no_positivas_rect_degenerado(self):
        assert DEFAULT_CROP.source_rect(0, 100) == (0, 0, 0)
        assert DEFAULT_CROP.source_rect(100, -5) == (0, 0, 0)

    def test_zoom_extremo_lado_minimo_uno(self):
        _, _, side = PortraitCrop(zoom=MAX_ZOOM).source_rect(4, 4)
        assert side >= 1


class TestSourceRectForAspect:
    def test_aspect_uno_equivale_al_cuadrado(self):
        x, y, w, h = DEFAULT_CROP.source_rect_for_aspect(300, 100, 1.0)
        assert (w, h) == (100, 100)
        assert (x, y) == (100, 0)

    def test_banda_vertical_en_imagen_ancha(self):
        # aspect 0.5 (ancho/alto): banda el doble de alta que ancha.
        x, y, w, h = DEFAULT_CROP.source_rect_for_aspect(400, 200, 0.5)
        assert (w, h) == (100, 200)
        assert (x, y) == (150, 0)

    def test_banda_horizontal_en_imagen_alta(self):
        x, y, w, h = DEFAULT_CROP.source_rect_for_aspect(100, 400, 2.0)
        assert (w, h) == (100, 50)
        assert (x, y) == (0, 175)

    def test_zoom_reduce_ambos_lados(self):
        _, _, w, h = PortraitCrop(zoom=2.0).source_rect_for_aspect(400, 200, 0.5)
        assert (w, h) == (50, 100)

    def test_clamp_dentro_de_la_imagen(self):
        x, y, w, h = PortraitCrop(cx=1.0, cy=0.0, zoom=2.0).source_rect_for_aspect(400, 200, 0.5)
        assert x + w <= 400
        assert y >= 0

    def test_parametros_invalidos_rect_degenerado(self):
        assert DEFAULT_CROP.source_rect_for_aspect(0, 10, 1.0) == (0, 0, 0, 0)
        assert DEFAULT_CROP.source_rect_for_aspect(10, 10, 0.0) == (0, 0, 0, 0)


class TestParseYSerializacion:
    def test_roundtrip_dict(self):
        crop = PortraitCrop(cx=0.3, cy=0.7, zoom=2.5)
        assert parse_crop(crop.to_dict()) == crop

    def test_roundtrip_tupla(self):
        crop = PortraitCrop(cx=0.25, cy=0.75, zoom=3.0)
        assert parse_crop(crop.as_tuple()) == crop

    def test_meta_ausente_o_corrupta_da_default(self):
        assert parse_crop(None) == DEFAULT_CROP
        assert parse_crop("basura") == DEFAULT_CROP
        assert parse_crop(42) == DEFAULT_CROP
        assert parse_crop([1, 2]) == DEFAULT_CROP

    def test_dict_con_campos_corruptos_degrada_campo_a_campo(self):
        crop = parse_crop({"cx": "no", "cy": 0.8, "zoom": None})
        assert crop == PortraitCrop(0.5, 0.8, 1.0)

    def test_dict_fuera_de_rango_se_normaliza(self):
        crop = parse_crop({"cx": 5.0, "cy": -1.0, "zoom": 100.0})
        assert crop == PortraitCrop(1.0, 0.0, MAX_ZOOM)

    def test_to_dict_normaliza(self):
        assert PortraitCrop(cx=2.0, zoom=0.1).to_dict() == {"cx": 1.0, "cy": 0.5, "zoom": 1.0}
