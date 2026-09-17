"""Normalización y puntuación de texto para BÚSQUEDA (BETA2-FIX-04).

Helper único y compartido para que las superficies de búsqueda de la app comparen
texto de la misma manera. Nace del hallazgo **G2-04** de la 2ª ronda de beta
testing: buscar en castellano exigía teclear las tildes (`cronica` → 0
resultados, `Crónica` → resultados) y el orden de la barra flotante premiaba los
títulos cortos, así que una entidad muy relacionada quedaba expulsada de su
propia búsqueda por sus relaciones.

Dos piezas, ambas puras (stdlib: `unicodedata`), sin estado y sin canon:

- **Plegado** (`normalizar_para_busqueda` / `terminos_de_busqueda` /
  `coincide_con_terminos`): minúsculas + NFD descartando los diacríticos.
- **Calidad de la coincidencia** (`puntuar_coincidencia`): devuelve *por qué* ha
  coincidido algo, para que quien ordene no tenga que adivinarlo a partir del
  texto del título (que es exactamente lo que hacía la barra, cayendo en
  `len(titulo)` como desempate).

**Decisión sobre la «ñ»: SE PLIEGA a «n».** `unicodedata.normalize("NFD", "ñ")`
la descompone en `n` + tilde combinante, así que el plegado estándar la
convierte en `n`. Consecuencia asumida a conciencia: «penarana» encuentra
«Peñaraña» (deseable para quien teclea rápido y sin acentos) pero «cana»
también encuentra «caña» (ruido tolerable). Se pliega **por consistencia** con
`_norm_token` de `packages/persistence/schema.py`, que ya la plegaba desde la
migración PA04; tener dos criterios de plegado distintos en el mismo repo sería
peor que el ruido.

La escala de puntuación está **alineada con `TextSearchService._entity_score`**
(nombre exacto 100 · nombre 80 · alias 60 · descripción breve 30 · extendida 20)
para que el día que ese servicio tenga puerta en la UI (hallazgo G2-15) no haya
dos rankings que se contradigan. Aquí se abren los tramos altos del nombre
(exacto > prefijo > palabra completa > subcadena), que es la distinción que la
barra necesitaba y no tenía.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence

#: Coincidencia perfecta: el título ES la consulta.
PUNTUACION_NOMBRE_EXACTO = 100
#: El título EMPIEZA por la consulta («posada del» → «Posada del Cuervo…»).
PUNTUACION_NOMBRE_PREFIJO = 90
#: Todos los términos son palabras completas del título (en cualquier orden).
PUNTUACION_NOMBRE_PALABRA = 85
#: Todos los términos aparecen en el título, aunque sea a medias de palabra.
PUNTUACION_NOMBRE_SUBCADENA = 80
#: Coincidencia por alias / apodo.
PUNTUACION_ALIAS = 60
#: Coincidencia en el subtítulo (descripción breve).
PUNTUACION_SUBTITULO = 30
#: Coincidencia en el cuerpo (descripción extendida).
PUNTUACION_CUERPO = 20
#: Ningún campo contiene TODOS los términos: la coincidencia está repartida
#: entre campos (p. ej. un término en el nombre y otro en el cuerpo). Sigue
#: siendo una coincidencia válida —la búsqueda es conjuntiva sobre el conjunto—
#: pero es la más débil de todas.
PUNTUACION_MIXTA = 10


def normalizar_para_busqueda(texto: object) -> str:
    """Devuelve ``texto`` en minúsculas y sin diacríticos, listo para comparar.

    `«Crónica»` → `«cronica»`, `«Peñaraña»` → `«penarana»` (ver la nota sobre la
    «ñ» en el docstring del módulo). El texto ya ASCII se devuelve solo en
    minúsculas: el atajo evita pagar la descomposición NFD en el caso común y no
    cambia el resultado.
    """
    plano = str(texto or "").lower()
    if plano.isascii():
        return plano
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", plano)
        if unicodedata.category(caracter) != "Mn"
    )


def terminos_de_busqueda(consulta: object) -> list[str]:
    """Parte la consulta en términos normalizados (lista vacía si no hay nada)."""
    return [termino for termino in normalizar_para_busqueda(consulta).split() if termino]


def coincide_con_terminos(pajar_normalizado: str, terminos: Sequence[str]) -> bool:
    """¿Aparecen TODOS los términos en el pajar? La búsqueda es **conjuntiva**.

    Dos palabras acotan, no amplían (contrato fijado en BETA-AUDIT-10). El pajar
    debe venir ya normalizado con `normalizar_para_busqueda`.
    """
    if not terminos:
        return False
    return all(termino in pajar_normalizado for termino in terminos)


def puntuar_coincidencia(
    terminos: Sequence[str],
    titulo_normalizado: str,
    campos_secundarios: Sequence[tuple[str, str, int]] = (),
) -> tuple[int, str]:
    """Devuelve ``(puntuación, campo)``: cuánto y POR QUÉ ha coincidido algo.

    El título se puntúa por **calidad** (exacto > prefijo > palabra completa >
    subcadena); los ``campos_secundarios`` —tuplas ``(nombre, texto_normalizado,
    puntuación)`` en orden de preferencia— solo por contener todos los términos.
    Si ningún campo por separado los contiene todos, la coincidencia es
    ``PUNTUACION_MIXTA``: está repartida entre campos.

    Todos los textos deben venir ya normalizados. No decide nada sobre el orden
    entre CLASES de resultado (entidad / hito / relación): eso es de quien
    ordena, no del texto.
    """
    if not terminos:
        return (0, "")
    consulta = " ".join(terminos)
    if titulo_normalizado:
        if titulo_normalizado == consulta:
            return (PUNTUACION_NOMBRE_EXACTO, "nombre")
        if titulo_normalizado.startswith(consulta):
            return (PUNTUACION_NOMBRE_PREFIJO, "nombre")
        palabras = set(titulo_normalizado.split())
        if all(termino in palabras for termino in terminos):
            return (PUNTUACION_NOMBRE_PALABRA, "nombre")
        if all(termino in titulo_normalizado for termino in terminos):
            return (PUNTUACION_NOMBRE_SUBCADENA, "nombre")
    for nombre_campo, texto, puntuacion in campos_secundarios:
        if texto and all(termino in texto for termino in terminos):
            return (int(puntuacion), nombre_campo)
    return (PUNTUACION_MIXTA, "mixta")
