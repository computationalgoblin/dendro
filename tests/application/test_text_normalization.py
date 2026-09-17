"""BETA2-FIX-04 — helper compartido de normalización de búsqueda.

Nace del hallazgo G2-04: buscar en castellano exigía teclear las tildes
(`cronica` → 0 resultados) porque las tres superficies de búsqueda del repo se
conformaban con `.lower()`, que no toca los diacríticos. Y del orden de la barra
flotante, que sin saber POR QUÉ había coincidido algo desempataba por
`len(titulo)`.

El módulo vive en `packages/application` (solo stdlib: `unicodedata`) para que
`hosts/` pueda importarlo sin violar capas.
"""

from __future__ import annotations

from packages.application.text_normalization import (
    PUNTUACION_ALIAS,
    PUNTUACION_CUERPO,
    PUNTUACION_MIXTA,
    PUNTUACION_NOMBRE_EXACTO,
    PUNTUACION_NOMBRE_PALABRA,
    PUNTUACION_NOMBRE_PREFIJO,
    PUNTUACION_NOMBRE_SUBCADENA,
    coincide_con_terminos,
    normalizar_para_busqueda,
    puntuar_coincidencia,
    terminos_de_busqueda,
)


class TestNormalizarParaBusqueda:
    def test_beta_m2fix04_pliega_los_acentos_castellanos(self):
        assert normalizar_para_busqueda("Crónica") == "cronica"
        assert normalizar_para_busqueda("Geografía") == "geografia"
        assert normalizar_para_busqueda("Situación") == "situacion"
        assert normalizar_para_busqueda("Ángel Éxpósito Ürsula") == "angel exposito ursula"

    def test_beta_m2fix04_la_enye_se_pliega_a_ene(self):
        """Decisión escrita en el docstring del módulo: la «ñ» SE PLIEGA.

        Consecuencia asumida: «penarana» encuentra «Peñaraña» (deseable) y
        «cana» también encuentra «caña» (ruido tolerable). Se elige por
        consistencia con `_norm_token` de persistence, que ya la plegaba.
        """
        assert normalizar_para_busqueda("Peñaraña") == "penarana"

    def test_beta_m2fix04_texto_ascii_solo_baja_a_minusculas(self):
        assert normalizar_para_busqueda("Posada Del Cuervo") == "posada del cuervo"

    def test_beta_m2fix04_tolera_none_y_no_cadenas(self):
        assert normalizar_para_busqueda(None) == ""
        assert normalizar_para_busqueda("") == ""
        assert normalizar_para_busqueda(42) == "42"


class TestTerminosDeBusqueda:
    def test_beta_m2fix04_parte_en_terminos_normalizados(self):
        assert terminos_de_busqueda("  Peste   Negra ") == ["peste", "negra"]

    def test_beta_m2fix04_consulta_vacia_no_da_terminos(self):
        assert terminos_de_busqueda("   ") == []
        assert terminos_de_busqueda(None) == []


class TestCoincideConTerminos:
    def test_beta_m2fix04_es_conjuntiva_y_sin_orden(self):
        pajar = "llegada de la peste negra"
        assert coincide_con_terminos(pajar, ["negra", "peste"])
        assert coincide_con_terminos(pajar, ["peste", "negra"])
        assert not coincide_con_terminos(pajar, ["peste", "coronacion"])

    def test_beta_m2fix04_sin_terminos_no_coincide_nada(self):
        assert not coincide_con_terminos("lo que sea", [])


class TestPuntuarCoincidencia:
    def test_beta_m2fix04_la_calidad_del_nombre_ordena_de_mejor_a_peor(self):
        terminos = ["cuervo"]
        exacto, _ = puntuar_coincidencia(terminos, "cuervo")
        prefijo, _ = puntuar_coincidencia(terminos, "cuervo ahogado de la posada")
        palabra, _ = puntuar_coincidencia(terminos, "posada del cuervo ahogado")
        subcadena, _ = puntuar_coincidencia(terminos, "matacuervos del sur")
        assert exacto == PUNTUACION_NOMBRE_EXACTO
        assert prefijo == PUNTUACION_NOMBRE_PREFIJO
        assert palabra == PUNTUACION_NOMBRE_PALABRA
        assert subcadena == PUNTUACION_NOMBRE_SUBCADENA
        assert exacto > prefijo > palabra > subcadena

    def test_beta_m2fix04_el_nombre_manda_sobre_alias_y_cuerpo(self):
        campos = (
            ("alias", "el cuervo tuerto", PUNTUACION_ALIAS),
            ("cuerpo", "vivía en el cuervo", PUNTUACION_CUERPO),
        )
        puntuacion, campo = puntuar_coincidencia(["cuervo"], "posada del cuervo", campos)
        assert (puntuacion, campo) == (PUNTUACION_NOMBRE_PALABRA, "nombre")

    def test_beta_m2fix04_devuelve_el_campo_que_explica_la_coincidencia(self):
        campos = (
            ("alias", "el tuerto", PUNTUACION_ALIAS),
            ("cuerpo", "un enano del ojo de vidrio", PUNTUACION_CUERPO),
        )
        assert puntuar_coincidencia(["tuerto"], "yusuf ibn nasr", campos) == (
            PUNTUACION_ALIAS,
            "alias",
        )
        assert puntuar_coincidencia(["vidrio"], "yusuf ibn nasr", campos) == (
            PUNTUACION_CUERPO,
            "cuerpo",
        )

    def test_beta_m2fix04_coincidencia_repartida_entre_campos_es_la_mas_debil(self):
        campos = (("cuerpo", "vivía en pleno invierno", PUNTUACION_CUERPO),)
        puntuacion, campo = puntuar_coincidencia(["pacto", "invierno"], "el pacto", campos)
        assert (puntuacion, campo) == (PUNTUACION_MIXTA, "mixta")
        assert puntuacion < PUNTUACION_CUERPO

    def test_beta_m2fix04_la_longitud_del_titulo_no_puntua(self):
        """El defecto del beta en una línea: dos títulos que coinciden igual de
        bien puntúan igual, mida lo que mida cada uno."""
        corto, _ = puntuar_coincidencia(["cuervo"], "zarza cuervo")
        largo, _ = puntuar_coincidencia(["cuervo"], "posada del cuervo ahogado")
        assert corto == largo

    def test_beta_m2fix04_sin_terminos_no_puntua(self):
        assert puntuar_coincidencia([], "lo que sea") == (0, "")
