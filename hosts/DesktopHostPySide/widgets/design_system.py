"""Minimal desktop design-system widgets for B27.5 UX redesign.

These widgets are intentionally presentation-only. They do not import persistence
or infrastructure and do not mutate domain objects directly.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# ─────────────────────────────────────────────────────────────────────────
# Dendro — paleta con identidad ("tinta, pergamino y oro botánico")
#
# Una sola fuente de verdad para el color. Pergamino cálido con una escalera
# tonal real (de hundido a elevado), tinta profunda para contraste serio, y un
# ÚNICO acento de oro-oliva con carácter para las acciones. La estética sigue
# siendo orgánica y editorial; lo que cambia es la PROFUNDIDAD y el aplomo.
# ─────────────────────────────────────────────────────────────────────────

# Superficies (escalera cálida: de lo hundido a lo elevado)
PAPER       = "#E8E1CF"   # base de la app (detrás de todo)
CANVAS      = "#E6DFCD"   # lienzo del grafo (con viñeta propia)
WELL        = "#DDD5BF"   # carriles/pozos hundidos
SURFACE     = "#F4EFE1"   # tarjetas, cajones
SURFACE_HI  = "#FBF8EF"   # tarjetas elevadas, barras flotantes
INPUT_BG    = "#FFFDF8"   # campos de texto

# Tinta (texto) — más profunda y cálida, para contraste profesional
#
# BETA-MULTIAGENT2-FIX-13 (G2-17), TANDA A. La escalera de tinta tenía tres
# peldaños pero solo los dos primeros se leían: `INK_MUTED` medía 2,93:1 sobre
# SURFACE, 2,58:1 sobre PAPER y 2,30:1 sobre WELL, e `INK_SOFT` se quedaba a
# 4,24:1 sobre PAPER. Y no eran tintas decorativas: `QLabel#mutedLabel` es
# exactamente lo que pinta la justificación de la IA (structure_review_panel),
# el origen del candidato (candidate_review_panel) y las filas de riesgo del
# Cuaderno de Cultivo. O sea: la prosa humana a 10:1 y el razonamiento de la
# máquina a 2,58:1, justo al revés de lo que pide la confianza.
#
# La escalera NO se aplana (sigue habiendo tres niveles de énfasis): se BAJA
# ENTERA hasta que su último peldaño cumple AA sobre la superficie más oscura
# del sistema (WELL). Medido con `contrast_ratio`, sobre WELL / PAPER / SURFACE:
#   INK        7,08 · 7,95 · 9,02
#   INK_SOFT   5,53 · 6,21 · 7,04
#   INK_MUTED  4,67 · 5,24 · 5,95   (antes: 2,30 · 2,58 · 2,93)
# ΔE entre peldaños ≈ 7 y ≈ 5: la jerarquía se sigue viendo.
INK_STRONG  = "#34301E"
INK         = "#45402E"
INK_SOFT    = "#55503A"
INK_MUTED   = "#605B41"

# Líneas y bordes
LINE        = "#D2CAB1"
LINE_SOFT   = "#E3DCC8"
LINE_STRONG = "#BCB28E"
# Borde de CONTROL interactivo (WCAG 1.4.11 · 3:1 para componentes de interfaz).
# FIX-13: `LINE` (1,43:1 sobre SURFACE) y `LINE_STRONG` (1,85:1) valen como
# ornamento —separadores, rejillas, marcos decorativos— pero NO como el único
# indicio visual de que ahí hay un botón o un campo. Este token sí llega:
# 3,86 sobre SURFACE · 4,36 sobre INPUT_BG · 3,40 sobre PAPER · 3,03 sobre WELL.
LINE_CONTROL = "#807855"

# Acento — oro-oliva (identidad / acciones)
# FIX-13 (G2-17): el oro era #8B7A36 y la etiqueta del botón primario (INK_INVERSE)
# medía 4,01:1 contra él — el peor punto de su gradiente, y es el control más
# pulsado de la app. Bajado un peldaño de luminosidad SIN mover el tono: ahora
# 4,98:1 contra INK_INVERSE (el stop inferior, GOLD_DEEP, ya daba 5,73:1) y
# 4,60:1 sobre SURFACE, con lo que el oro además pasa a ser legible como texto.
GOLD        = "#7A6B2F"
GOLD_DEEP   = "#6E622E"
GOLD_PRESS  = "#5E5427"   # oro hundido (estado :pressed de acciones doradas)
GOLD_SOFT   = "#BBAA66"
GOLD_TINT   = "#ECE4C7"   # relleno sutil de acento (hover/selección)

# Verde botánico (secundario, con mucha mesura: vida, foco orgánico)
SAGE        = "#6E7E58"
SAGE_DEEP   = "#546243"  # verde profundo (reservado; aún sin uso)

# Tierra (BETA2-JARDIN-01): ciclo de riego en el Mapa — sedienta (marrón) y
# secada (carbón-tierra).
#
# BETA-MULTIAGENT2-FIX-01 (criterio 6): los tintes ANTIGUOS eran claros
# (#CDBB97 / #D0CCBE) y medían 1,09:1 contra la parada más oscura de la viñeta
# (#CFC4A8) y 1,17:1 ENTRE SÍ: dos estados de significado opuesto pintados del
# mismo color e invisibles sobre el pergamino. Con un lienzo CLARO la única
# forma de que un relleno alcance 3:1 es oscurecerlo (un relleno claro tiene un
# techo matemático de 1,73:1 contra #CFC4A8), y para que además los dos estados
# se separen 3:1 entre sí uno tiene que ser carbón. De ahí estos valores:
#   sedienta  vs #CFC4A8 = 3,12:1 · vs CANVAS = 4,07:1
#   secada    vs #CFC4A8 = 9,67:1 · vs CANVAS = 12,6:1
#   sedienta  vs secada  = 3,10:1
# Al ser rellenos OSCUROS, el texto que va encima se invierte a EARTH_INK.
EARTH           = "#8A6B45"   # borde/acento de entidad sedienta (falta regar)
EARTH_TINT      = "#8C6137"   # relleno de entidad sedienta (marrón tierra)
EARTH_GREY      = "#A29B87"   # borde de entidad secada (pausada a propósito)
EARTH_GREY_TINT = "#231C1A"   # relleno de entidad secada (carbón cálido)
EARTH_INK       = "#F7F1E8"   # tinta sobre relleno de tierra (4,8:1 / 14,4:1)
EARTH_INK_SOFT  = "#EDE6D6"   # tinta secundaria sobre relleno de tierra

# Perímetro de la hoja SANA. El relleno blanco de una entidad sana no puede
# alcanzar 3:1 contra el pergamino (techo 1,73:1), así que quien porta el
# contraste del componente es su BORDE — que es lo que WCAG 1.4.11 mide.
# LEAF_EDGE vs #CFC4A8 = 3,42:1 · vs CANVAS = 4,46:1 · vs el relleno = 5,9:1.
LEAF_EDGE       = "#6B6448"

# Sombra cálida base (RGB) — las sombras nunca son grises neutros aquí
SHADOW_RGB  = (52, 47, 28)


# ─────────────────────────────────────────────────────────────────────────
# Tokens extraídos del host (BETA1-AUDIT-04) — extracción PURA de hex que
# vivían hardcodeados en widgets/vistas. Mismos valores exactos: mover el
# color aquí NO cambia nada visual, solo da una única fuente de verdad.
# ─────────────────────────────────────────────────────────────────────────

WHITE = "#FFFFFF"   # blanco puro (hover de superficies claras)

# Tinta oliva — títulos/etiquetas de paneles e iconos de cierre
INK_OLIVE      = "#6F6A42"
INK_OLIVE_DEEP = "#5C5A3E"
INK_OLIVE_SOFT = "#7A733D"

# Texto claro sobre oro (botón primario, badge dorado)
INK_INVERSE = "#FCF8EC"

# Superficies y bordes de tarjetas flotantes claras (popups, sugerencias)
POPUP_BG     = "#FFFDF7"
SURFACE_PALE = "#F8F5EA"   # pergamino muy claro (hover de botones, rellenos)
LINE_CARD    = "#D8D6C8"   # borde suave de tarjetas/group boxes claros
LINE_OLIVE   = "#AFA77A"   # borde de realce (hover) / halos neutros
LINE_MUTED   = "#C9C5B1"   # conectores y ornamentos tenues del Home

# Tono "sesión" (cuero cálido): badge AVANZADO de la topbar y nodo Sesión del Home
SESSION_INK  = "#8A6849"
SESSION_TINT = "#EFE3C7"
SESSION_LINE = "#C8AF8C"


# ─────────────────────────────────────────────────────────────────────────
# Cronología (BETA1-AUDIT-04) — paleta base de chrono_canvas. El fondo
# (CANVAS), la píldora (SURFACE_HI) y su borde (LINE) reutilizan los tokens
# generales; aquí viven solo los valores propios de la vista.
# ─────────────────────────────────────────────────────────────────────────

CHRONO_INK   = "#504B2E"   # tinta de la cronología (etiquetas sobre pergamino)
CHRONO_MUTED = "#7C806E"   # texto secundario
CHRONO_LINE  = "#8A8563"   # líneas de vida y bordes de hito

CHRONO_GOLD      = "#C8A24C"   # oro de la cronología (scrubber, foco de navegación)
CHRONO_GOLD_DEEP = "#8A7A33"
CHRONO_BLOOM     = "#E2B23C"   # glow dorado de germinación (hitos/vidas que brotan)
CHRONO_EDGE_HI   = "#FCF8EE"   # filo iluminado del relieve (estratos/columnas)

# Tintes BOTÁNICOS de los estratos de ERA (oro · salvia · terracota · ciruela ·
# musgo). Mismos que el slider de la concéntrica, para que las dos vistas hablen
# el mismo idioma de color.
CHRONO_ERA_TINTS = ("#C8A24C", "#7E9568", "#A87C53", "#937083", "#B28A3C")
# Tintes por ANILLO (world layer) para las columnas de la cronología. Cálidos y
# distintos entre sí, pero deliberadamente SEPARADOS de los de era (que tiñen el
# fondo por TIEMPO) para que era×anillo no colisionen en tono.
CHRONO_RING_TINTS = ("#B0794A", "#6F8A5E", "#A05C6E", "#8C7BA0", "#B79A46", "#7E8A74")
CHRONO_RING_UNCLASSIFIED = "#9A927C"   # gris cálido neutro del anillo "Sin anillo"
# Viñeta cálida (corazón con luz → bordes que se hunden), idéntica a la concéntrica.
CHRONO_VIGNETTE = (
    (0.0, "#F3EDDD"),
    (0.50, CANVAS),
    (0.82, "#DBD1B9"),
    (1.0, "#CFC4A8"),
)


def canvas_vignette_brush(center_x: float, center_y: float, radius: float) -> "QBrush":
    """BETA2-PULIDO-07: viñeta radial cálida ÚNICA de los lienzos de Creación
    (Mapa, Cronología y Foco) — el «corazón del mundo» recibe luz suave y los
    bordes se hunden. Paradas canónicas = CHRONO_VIGNETTE (misma escala)."""
    gradient = QRadialGradient(QPointF(center_x, center_y), radius)
    for stop, hex_color in CHRONO_VIGNETTE:
        gradient.setColorAt(stop, QColor(hex_color))
    return QBrush(gradient)


# ─────────────────────────────────────────────────────────────────────────
# Cimientos del sistema (BETA1-UX01) — tokens transversales que dan
# COHESIÓN y APLOMO. Principios:
#   · Una sola voz de oro para la acción (nunca arcoíris).
#   · Profundidad por capas cálidas, nunca gris neutro.
#   · Movimiento "expresivo pero elegante": notable, pero al servicio de la calma.
#   · Radios coherentes: pocas medidas, repetidas con disciplina.
# ─────────────────────────────────────────────────────────────────────────

# Escala de radios (cohesión de formas)
RADIUS_SM      = 9    # chips, celdas, controles pequeños
RADIUS_MD      = 12   # botones, inputs, combos
RADIUS_LG      = 16   # tarjetas, cajones
RADIUS_CAPSULE = 19   # PULIDO-05: cápsulas flotantes (save pill, view toggle, command bar)
RADIUS_PILL    = 999  # botones-cápsula

# Espaciado: escala 4-pt única (en vez de valores mágicos dispersos por widget).
# Úsala para márgenes, padding y spacing de layouts. El ritmo espacial consistente
# es el factor invisible que más "ordena" una UI.
SPACE_XS  = 4   # micro: separación interna de chips, gaps mínimos
SPACE_SM  = 8   # estándar entre controles afines
SPACE_MD  = 12  # entre grupos dentro de un bloque
SPACE_LG  = 16  # márgenes de tarjeta/panel, separación de secciones
SPACE_XL  = 24  # aire entre secciones mayores
SPACE_2XL = 32  # respiración de cabeceras / zonas vacías

# Animación: cadencia única de los widgets que repintan por timer (~25 fps, barato).
# Una sola fuente del FPS en vez de "40" duplicado por widget.
TICK_INTERVAL = 40  # ms entre fotogramas de animaciones pintadas a mano

# Paleta cálida por tipo de entidad (BETA1-UX05): única fuente para nodos del grafo
# y paneles de detalle (antes duplicada idéntica en cada widget). Tonos botánicos
# coherentes con el pergamino, NUNCA azules/púrpuras fríos.
#
# BETA-MULTIAGENT2-FIX-13 (G2-17), TANDA A: la paleta cubría 10 claves para los
# 21 `EntityType` del dominio — 14 tipos caían al neutro y eran indistinguibles
# entre sí. Se COMPLETA sin mover ni uno de los 9 hex históricos (fijados por
# `test_ux15_entity_palette.py`): los 14 colores nuevos se eligieron dentro de la
# misma banda estética (H 0-130 y 280-350, S 0,20-0,56, V 0,42-0,88 — cálidos,
# nunca azules fríos) con la restricción de quedar a ΔE(CIE76) ≥ 10 de TODOS los
# demás. Los únicos pares por debajo de 10 son los cuatro que YA existían entre
# los hex históricos (concepto/nota 4,62 · contenedor/nota 4,86 ·
# concepto/contenedor 8,11 · organizacion/evento 9,35): no se tocan porque
# moverlos rompe el snapshot y es un cambio visual que nadie pidió.
ENTITY_KIND_PALETTE: dict[str, str] = {
    "personaje": "#C07B53",      # terracota — calidez humana
    "lugar": "#7E9568",          # salvia — legado; ver _ENTITY_LEGACY_KEYS
    "localizacion": "#7E9568",   # salvia — el tipo real del dominio
    "organizacion": "#B28A3C",   # oro-oliva — legado; ver _ENTITY_LEGACY_KEYS
    "faccion": "#A65C54",        # granate-arcilla — conflicto
    "objeto": "#937083",         # ciruela apagada — reliquia
    "evento": "#C8A24C",         # miel — momento
    "concepto": "#8E8A6A",       # oliva-piedra — legado; ver _ENTITY_LEGACY_KEYS
    "contenedor": "#A89878",     # madera clara — rama
    "nota": "#9A8E72",           # piedra cálida — nota
    # FIX-13 — los 14 que faltaban
    "cultura": "#9E7D5C",          # arena tostada — costumbre heredada
    "escena": "#D1C38A",           # trigo claro — momento representado
    "sesion": "#856A58",           # cuero — mesa de juego
    "conflicto": "#854A4C",        # granate hondo — la herida abierta
    "secreto": "#704F6B",          # ciruela oscura — lo que no se dice
    "pista": "#B8B56A",            # oliva luminosa — el rastro que se sigue
    "regla_del_mundo": "#6A704C",  # musgo profundo — la ley que sostiene
    "tecnologia": "#6B5B54",       # peltre cálido — el artefacto
    "sistema_magico": "#916C9E",   # amatista cálida — lo prodigioso reglado
    "religion": "#E0D3AB",         # incienso — lo sagrado
    "idioma": "#598059",           # verde hoja — la lengua viva
    "institucion": "#856C3A",      # bronce viejo — la estructura que dura
    "criatura": "#B2796B",         # arcilla rojiza — lo que respira
    "trama": "#8A5869",            # vino apagado — el hilo que enhebra
}
# Claves que NO son un `EntityType` del dominio y se conservan a propósito: son
# el vocabulario natural con el que el modelo (y proyectos viejos) nombran tipos.
# Sin ellas caerían al neutro. Declaradas por escrito para que nadie las confunda
# con tipos reales.
_ENTITY_LEGACY_KEYS: dict[str, str] = {
    "lugar": "localizacion",       # el dominio dice «localizacion»
    "organizacion": "institucion",  # el dominio dice «institucion»
    "concepto": "regla_del_mundo",  # idea abstracta → regla del mundo
}
_ENTITY_KIND_DEFAULT = "#9A8E72"  # piedra cálida (neutro de la propia gama)


def entity_kind_color(kind: str | None, default: str = _ENTITY_KIND_DEFAULT) -> str:
    """Color cálido del tipo de entidad (clave normalizada en minúsculas)."""
    return ENTITY_KIND_PALETTE.get(str(kind or "").lower(), default)


# Paleta cálida por tipo de relación (BETA1-UX05): única fuente para los arcos del
# grafo y el panel de detalle. Familias por significado: vínculo (salvia), conflicto
# (granate), contención/lugar (oliva), jerarquía (oro-oliva), afecto/familia
# (terracota/rosa), causalidad (ciruela apagada). NUNCA azules/púrpuras fríos.
#
# El color de una relación identifica su FAMILIA de significado, no el tipo
# concreto: dos arcos de la misma familia comparten tono a propósito (así el
# lienzo se lee de un vistazo). Los tonos canónicos viven en
# RELATION_FAMILY_TONES y cada tipo del dominio se asigna a uno de ellos.
RELATION_FAMILY_TONES: dict[str, str] = {
    "vinculo": "#7E9568",       # salvia — alianza, protección
    "conflicto": "#A65C54",     # granate — enemistad, traición, contradicción
    "jerarquia": "#B28A3C",     # oro-oliva — pertenencia, mando, obligación
    "contencion": "#94A06F",    # oliva — contener, ubicar, servir
    "afecto": "#C07B53",        # terracota — posesión, vínculo íntimo
    "busqueda": "#C8A24C",      # miel — lo que se persigue
    "conocimiento": "#8E8A6A",  # oliva-piedra — saber, creer, ocultar, revelar
    "causalidad": "#8A6B7C",    # ciruela apagada — causa, consecuencia, derivación
    "neutro": "#9A8E72",        # piedra cálida — relación genérica
}

# BETA-MULTIAGENT2-FIX-13 (G2-17), TANDA A: la paleta declaraba 31 claves para
# los 41 `RelationType` del dominio y 7 de esas claves no correspondían a ningún
# tipo. Faltaban 17 tipos, entre ellos `causo` y `fue_causado_por`, que son la
# columna vertebral causal del producto: la causalidad se pintaba del neutro.
RELATION_KIND_PALETTE: dict[str, str] = {
    # vínculo
    "es_aliado_de": RELATION_FAMILY_TONES["vinculo"],
    "protege": RELATION_FAMILY_TONES["vinculo"],
    # conflicto
    "es_enemigo_de": RELATION_FAMILY_TONES["conflicto"],
    "esta_en_conflicto_con": RELATION_FAMILY_TONES["conflicto"],
    "traiciono": RELATION_FAMILY_TONES["conflicto"],
    "contradice": RELATION_FAMILY_TONES["conflicto"],
    # jerarquía / obligación
    "pertenece_a": RELATION_FAMILY_TONES["jerarquia"],
    "depende_de": RELATION_FAMILY_TONES["jerarquia"],
    "sospecha": RELATION_FAMILY_TONES["jerarquia"],
    "gobierna": RELATION_FAMILY_TONES["jerarquia"],
    "controla": RELATION_FAMILY_TONES["jerarquia"],
    "tiene_deuda_con": RELATION_FAMILY_TONES["jerarquia"],
    # contención / lugar
    "contiene": RELATION_FAMILY_TONES["contencion"],
    "esta_ubicado_en": RELATION_FAMILY_TONES["contencion"],
    "sirve_a": RELATION_FAMILY_TONES["contencion"],
    # afecto / posesión
    "posee": RELATION_FAMILY_TONES["afecto"],
    # búsqueda
    "busca": RELATION_FAMILY_TONES["busqueda"],
    # conocimiento (lo que un personaje sabe, cree, oculta o revela)
    "oculta": RELATION_FAMILY_TONES["conocimiento"],
    "conoce": RELATION_FAMILY_TONES["conocimiento"],
    "simboliza": RELATION_FAMILY_TONES["conocimiento"],
    "desconoce": RELATION_FAMILY_TONES["conocimiento"],
    "revela": RELATION_FAMILY_TONES["conocimiento"],
    "sabe": RELATION_FAMILY_TONES["conocimiento"],
    "cree": RELATION_FAMILY_TONES["conocimiento"],
    "ignora": RELATION_FAMILY_TONES["conocimiento"],
    "malinterpreta": RELATION_FAMILY_TONES["conocimiento"],
    "ha_oido": RELATION_FAMILY_TONES["conocimiento"],
    "ha_visto": RELATION_FAMILY_TONES["conocimiento"],
    "ha_recibido_pista": RELATION_FAMILY_TONES["conocimiento"],
    "conoce_parcialmente": RELATION_FAMILY_TONES["conocimiento"],
    "conoce_falsamente": RELATION_FAMILY_TONES["conocimiento"],
    "posee_conocimiento": RELATION_FAMILY_TONES["conocimiento"],
    "revela_conocimiento": RELATION_FAMILY_TONES["conocimiento"],
    # causalidad — la columna vertebral del producto
    "causo": RELATION_FAMILY_TONES["causalidad"],
    "fue_causado_por": RELATION_FAMILY_TONES["causalidad"],
    "participo_en": RELATION_FAMILY_TONES["causalidad"],
    "deriva_de": RELATION_FAMILY_TONES["causalidad"],
    "condiciona": RELATION_FAMILY_TONES["causalidad"],
    "explica": RELATION_FAMILY_TONES["causalidad"],
    "produce_consecuencia_en": RELATION_FAMILY_TONES["causalidad"],
    # parentesco (BETA-MULTIAGENT2-FIX-12, G2-16) — el color del vínculo íntimo
    # ya estaba reservado en `es_familiar_de` esperando a que el dominio tuviera
    # los tipos. Ahora existen y la clave deja de ser huérfana.
    "es_familiar_de": RELATION_FAMILY_TONES["afecto"],
    "es_progenitor_de": RELATION_FAMILY_TONES["afecto"],
    "es_madre_de": RELATION_FAMILY_TONES["afecto"],
    "es_padre_de": RELATION_FAMILY_TONES["afecto"],
    "es_hijo_de": RELATION_FAMILY_TONES["afecto"],
    "es_hermano_de": RELATION_FAMILY_TONES["afecto"],
    "es_antepasado_de": RELATION_FAMILY_TONES["afecto"],
    "es_descendiente_de": RELATION_FAMILY_TONES["afecto"],
    # El matrimonio comparte el tono de la familia (el color identifica la
    # FAMILIA de significado, no el tipo concreto — regla UX05/FIX-13).
    "esta_casado_con": RELATION_FAMILY_TONES["afecto"],
    # genérica
    "esta_relacionado_con": RELATION_FAMILY_TONES["neutro"],
}

# Claves que el dominio NO define como `RelationType` y que se conservan a
# propósito: el modelo todavía las emite (son el vocabulario natural de un
# escritor) y sin color caerían al neutro. Se declaran aquí, por escrito, para
# que ningún lector futuro las confunda con tipos reales.
# BETA-MULTIAGENT2-FIX-12 (G2-16): `es_familiar_de` YA NO vive aquí — el dominio
# tiene la familia de parentesco y su color se declara arriba, con los tipos
# reales. Las que quedan siguen siendo huérfanas a propósito.
_RELATION_LEGACY_KEYS: dict[str, str] = {
    "es_amigo_de": RELATION_FAMILY_TONES["vinculo"],
    "es_rival_de": RELATION_FAMILY_TONES["conflicto"],
    "es_mentor_de": RELATION_FAMILY_TONES["jerarquia"],
    "esta_en": RELATION_FAMILY_TONES["contencion"],
    "ama_a": "#BD7E73",   # rosa-arcilla — el único afecto con tono propio
    "faccion": RELATION_FAMILY_TONES["conflicto"],
}
RELATION_KIND_PALETTE.update(_RELATION_LEGACY_KEYS)
_RELATION_KIND_DEFAULT = RELATION_FAMILY_TONES["neutro"]  # piedra cálida


def relation_kind_color(rel_type: str | None, default: str = _RELATION_KIND_DEFAULT) -> str:
    """Color cálido del tipo de relación (clave normalizada en minúsculas)."""
    return RELATION_KIND_PALETTE.get(str(rel_type or "").lower(), default)


# Tipografía: familias + jerarquía nombrada (en vez de font-size sueltos por widget).
# Serif (Georgia) para contenido editorial; sans (Segoe UI) para controles/datos.
FONT_SERIF = '"Georgia", "Iowan Old Style", "Palatino Linotype", serif'
FONT_SANS = '"Segoe UI", "Inter", "Helvetica Neue", "Arial", sans-serif'

# Escala nombrada. BETA-MULTIAGENT2-FIX-13 (G2-18), TANDA C: estos valores dejan
# de ser constantes muertas y pasan a ser FUNCIÓN de la preferencia «Tamaño de
# fuente» (ver `set_font_scale`). Hasta ahora la preferencia sí llegaba —
# `main_window._apply_live_preferences` emitía un override correcto— pero perdía
# contra los ~190 `font-size:` literales que los widgets se ponen a sí mismos:
# en Qt, la hoja de estilo del PROPIO widget gana a la del ancestro (comprobado:
# hijo con `font-size: 11px` bajo un padre a 16px sigue midiendo 11 px). Poner la
# preferencia en «Grande» no agrandaba nada donde se trabaja.
_TYPE_BASE_PX: dict[str, int] = {
    "h1": 19,       # título de sección
    "h2": 16,       # título de tarjeta/panel
    "subhead": 14,  # subtítulo de tarjeta (entre cuerpo y h2)
    "body": 13,     # cuerpo del sistema
    "label": 12,    # etiquetas/chips
    "caption": 11,  # subtítulos muted / pies (PISO del sistema: nada por debajo)
    "overline": 11,  # PULIDO-05: micro-título en mayúsculas con tracking
}

# Factor por preferencia. «Grande» debe NOTARSE (es el único ajuste que salva la
# vista de quien lee con gafas), «Pequeño» encoge pero nunca por debajo del piso.
FONT_SCALE_FACTORS: dict[str, float] = {"small": 0.88, "medium": 1.0, "large": 1.30}
# Piso absoluto del sistema: ningún texto baja de aquí, ni en «Pequeño».
TYPE_FLOOR_PX = 11
_FONT_SCALE = 1.0

TYPE_H1_PX = _TYPE_BASE_PX["h1"]
TYPE_H2_PX = _TYPE_BASE_PX["h2"]
TYPE_SUBHEAD_PX = _TYPE_BASE_PX["subhead"]
TYPE_BODY_PX = _TYPE_BASE_PX["body"]
TYPE_LABEL_PX = _TYPE_BASE_PX["label"]
TYPE_CAPTION_PX = _TYPE_BASE_PX["caption"]
TYPE_OVERLINE_PX = _TYPE_BASE_PX["overline"]

WEIGHT_BOLD = 700
WEIGHT_SEMIBOLD = 600

_TYPE_WEIGHTS: dict[str, QFont.Weight] = {
    "h1": QFont.Weight.Bold,
    "h2": QFont.Weight.Bold,
    "subhead": QFont.Weight.DemiBold,
    "body": QFont.Weight.Normal,
    "label": QFont.Weight.DemiBold,
    "caption": QFont.Weight.Normal,
    "overline": QFont.Weight.Bold,
}


def scale_px(px: int | float) -> int:
    """Aplica la escala tipográfica activa a un tamaño en píxeles, con piso."""
    try:
        value = int(round(float(px) * _FONT_SCALE))
    except (TypeError, ValueError):
        return int(TYPE_FLOOR_PX)
    return max(int(TYPE_FLOOR_PX), value)


def fs(role: str = "body") -> int:
    """Píxeles del rol tipográfico *role* con la preferencia activa aplicada."""
    return scale_px(_TYPE_BASE_PX.get(role, _TYPE_BASE_PX["body"]))


def font_scale() -> float:
    """Factor de escala tipográfica activo (1.0 = «Mediano»)."""
    return _FONT_SCALE


def set_font_scale(size_key: str) -> float:
    """Fija la escala desde la preferencia («small»/«medium»/«large»).

    Recalcula las constantes `TYPE_*_PX` del módulo para que TODO widget que se
    construya a partir de ahora nazca ya con el tamaño correcto. Para los que ya
    existen está `apply_font_scale`, que reescribe sus hojas de estilo.
    """
    global _FONT_SCALE, TYPE_H1_PX, TYPE_H2_PX, TYPE_SUBHEAD_PX
    global TYPE_BODY_PX, TYPE_LABEL_PX, TYPE_CAPTION_PX, TYPE_OVERLINE_PX
    _FONT_SCALE = FONT_SCALE_FACTORS.get(str(size_key or "medium"), 1.0)
    TYPE_H1_PX = fs("h1")
    TYPE_H2_PX = fs("h2")
    TYPE_SUBHEAD_PX = fs("subhead")
    TYPE_BODY_PX = fs("body")
    TYPE_LABEL_PX = fs("label")
    TYPE_CAPTION_PX = fs("caption")
    TYPE_OVERLINE_PX = fs("overline")
    return _FONT_SCALE


_FONT_SIZE_RE = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)(\s*px)")
_QSS_BASE_PROP = "_ds_qss_base"
_QSS_APPLIED_PROP = "_ds_qss_scaled"


def scale_stylesheet(qss: str) -> str:
    """Reescribe cada `font-size: Npx` de *qss* con la escala activa.

    Es el ÚNICO punto donde se corrige el problema de precedencia de Qt: como el
    literal del propio widget gana a cualquier override del ancestro, la única
    forma fiable de que «Grande» agrande es tocar ese literal.
    """
    if not qss or _FONT_SCALE == 1.0:
        return qss
    return _FONT_SIZE_RE.sub(lambda m: f"{m.group(1)}{scale_px(float(m.group(2)))}px", qss)


def _rescale_widget_qss(widget: QWidget) -> None:
    try:
        current = widget.styleSheet()
        base = widget.property(_QSS_BASE_PROP)
        applied = widget.property(_QSS_APPLIED_PROP)
        # Si el widget se ha reestilado por su cuenta desde la última pasada, su
        # hoja actual pasa a ser la nueva base (nunca se reescala dos veces).
        if base is None or current != applied:
            base = current
            widget.setProperty(_QSS_BASE_PROP, base)
        if not base or "font-size" not in base:
            return
        scaled = scale_stylesheet(base)
        if scaled != current:
            widget.setStyleSheet(scaled)
        widget.setProperty(_QSS_APPLIED_PROP, scaled)
    except Exception:  # noqa: BLE001 — la accesibilidad nunca rompe el render
        pass


def apply_font_scale(root: QWidget, *, include_root: bool = False) -> int:
    """Reaplica la escala tipográfica a un árbol de widgets YA construido.

    Devuelve cuántos widgets se revisaron. Idempotente: guarda la hoja original
    de cada widget y siempre reescala desde ella, así que llamarla N veces con
    la misma preferencia no compone tamaños.
    """
    try:
        widgets = list(root.findChildren(QWidget))
    except Exception:  # noqa: BLE001
        return 0
    if include_root:
        widgets.append(root)
    for widget in widgets:
        _rescale_widget_qss(widget)
    return len(widgets)


class _FontScaleWatcher(QObject):
    """Reescala las superficies que se construyen DESPUÉS del cambio de ajuste.

    Un panel, un cajón o un diálogo que nace más tarde trae sus propios
    `font-size:` literales y nadie los habría tocado. Se reescalan al mostrarse.
    """

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and _FONT_SCALE != 1.0:
            if isinstance(obj, QWidget):
                _rescale_widget_qss(obj)
                apply_font_scale(obj)
        return False


_FONT_SCALE_WATCHER = _FontScaleWatcher()


def sync_font_scale_watcher(app) -> None:
    """Engancha el vigía SOLO si la escala no es la de casa.

    Es un filtro de eventos de aplicación: ve pasar TODOS los eventos, así que
    con «Mediano» —el caso por defecto— se desengancha del todo y no cuesta ni un
    ciclo. La app ya arrastra quejas de fluidez; la accesibilidad no las agrava.
    """
    try:
        activo = getattr(app, "_ds_font_scale_watcher", None) is not None
        hace_falta = _FONT_SCALE != 1.0
        if hace_falta and not activo:
            app.installEventFilter(_FONT_SCALE_WATCHER)
            app._ds_font_scale_watcher = _FONT_SCALE_WATCHER
        elif activo and not hace_falta:
            app.removeEventFilter(_FONT_SCALE_WATCHER)
            app._ds_font_scale_watcher = None
    except Exception:  # noqa: BLE001 — la accesibilidad nunca impide arrancar
        pass


def relative_luminance(hex_color: str) -> float:
    """Luminancia relativa WCAG 2.x de un color #RRGGBB (0=negro, 1=blanco)."""
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """Ratio de contraste WCAG entre dos colores (1.0 = igual, 21 = blanco/negro)."""
    la, lb = relative_luminance(hex_a), relative_luminance(hex_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def role_font(role: str = "body", *, serif: bool = True) -> QFont:
    """QFont para un rol tipográfico nombrado (h1/h2/body/label/caption).

    Para widgets que fijan fuente por código; el QSS global sigue usando el stack
    completo de familias. Rol desconocido → body. FIX-13: el tamaño sale de la
    escala activa, así que también obedece a «Tamaño de fuente»."""
    font = QFont()
    font.setFamily("Georgia" if serif else "Segoe UI")
    font.setPixelSize(fs(role))
    font.setWeight(_TYPE_WEIGHTS.get(role, QFont.Weight.Normal))
    return font

# Movimiento: tres niveles + curvas con carácter
MOTION_FAST     = 150   # micro-feedback: hover, foco, press
MOTION_BASE     = 220   # transición estándar: aparición de contenido/paneles
MOTION_SLOW     = 360   # presencia: entradas/salidas con carácter
EASING_STD      = QEasingCurve.Type.OutCubic        # asentamiento natural
EASING_ENTER    = QEasingCurve.Type.OutQuint        # entrada con empuje y calma
EASING_EMPHASIS = QEasingCurve.Type.InOutCubic      # énfasis simétrico

# Elevación canvas-safe — sombra cálida PINTADA A MANO (QPainter), nunca
# QGraphicsDropShadowEffect (cachea el render y deja zonas en blanco; lección G08).
# nivel -> (radio_difuminado_px, desplazamiento_y_px, alpha_máximo)
ELEVATION: dict[int, tuple[int, int, int]] = {
    0: (0, 0, 0),
    1: (16, 3, 34),
    2: (26, 7, 46),
    3: (42, 13, 58),
}


def paint_soft_shadow(painter, rect, *, radius: float = RADIUS_MD, level: int = 2) -> None:
    """Pinta una sombra cálida y suave bajo *rect* (QRectF/QRect), sin efectos gráficos.

    Apta para el canvas (QPainter directo): emula el difuminado con capas de
    rectángulos redondeados de alpha decreciente. Presentation-only: falla en
    silencio para que el pulido nunca rompa el render.
    """
    try:
        blur, dy, alpha = ELEVATION.get(level, ELEVATION[2])
        if alpha <= 0 or painter is None or rect is None:
            return
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        base = QRectF(rect)
        layers = 6
        for i in range(layers, 0, -1):
            t = i / layers
            grow = blur * t
            a = int(alpha * (1.0 - t) ** 1.6)
            if a <= 0:
                continue
            painter.setBrush(QColor(SHADOW_RGB[0], SHADOW_RGB[1], SHADOW_RGB[2], a))
            r = base.adjusted(-grow, -grow + dy, grow, grow + dy)
            painter.drawRoundedRect(r, radius + grow, radius + grow)
        painter.restore()
    except Exception:  # noqa: BLE001 - el pulido nunca rompe el render
        pass


def _qss() -> str:
    """Hoja de estilo global construida desde la paleta (una sola verdad)."""
    return f"""
QMainWindow, QWidget {{
    background: {PAPER};
    color: {INK};
    font-family: "Georgia", "Iowan Old Style", "Palatino Linotype", serif;
    font-size: 13px;
}}
QToolTip {{
    background: {INK_STRONG};
    color: {SURFACE_HI};
    border: 1px solid {GOLD_DEEP};
    border-radius: 6px;
    padding: 5px 8px;
}}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {SURFACE_HI}, stop:1 {SURFACE});
    /* FIX-13 (WCAG 1.4.11): el borde es la ÚNICA señal de que aquí hay un
       control — `LINE` daba 1,43:1 y no lo marcaba para nadie. */
    border: 1px solid {LINE_CONTROL};
    border-radius: {RADIUS_MD}px;
    padding: 8px 14px;
    color: {INK_SOFT};
    font-weight: 600;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {INPUT_BG}, stop:1 {SURFACE_HI});
    border-color: {GOLD_SOFT};
    color: {INK_STRONG};
}}
QPushButton:focus {{ border: 2px solid {GOLD}; padding: 7px 13px; }}
QPushButton:pressed {{ background: {WELL}; padding-top: 9px; padding-bottom: 7px; }}
QPushButton:disabled {{ background: {SURFACE}; color: {INK_MUTED}; border-color: {LINE_SOFT}; }}
QPushButton#primaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {GOLD}, stop:1 {GOLD_DEEP});
    border: 1px solid {GOLD_DEEP};
    border-radius: {RADIUS_MD}px;
    color: {INK_INVERSE};
    font-weight: 700;
    padding: 9px 16px;
}}
QPushButton#primaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {GOLD_DEEP}, stop:1 #5E5427);
    border-color: {GOLD_DEEP};
}}
QPushButton#primaryButton:pressed {{ background: #5E5427; }}
QPushButton#primaryButton:disabled {{ background: #E3D8B8; color: {INK_SOFT}; border: 1px solid {LINE_STRONG}; }}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 6px 8px;
    color: {INK_SOFT};
}}
QToolButton:hover {{ background: {SURFACE_HI}; border-color: {LINE}; color: {INK_STRONG}; }}
QToolButton:checked {{ background: {GOLD_TINT}; border-color: {GOLD_SOFT}; color: {INK_STRONG}; }}
QToolButton:focus {{ border-color: {GOLD}; }}
QLabel#mutedLabel {{ color: {INK_MUTED}; }}
QLabel#overline {{
    color: {GOLD_DEEP};
    font-size: 11px;
    font-weight: 700;
}}
QLabel#sectionTitle {{
    font-size: 19px;
    font-weight: 700;
    color: {INK_STRONG};
    font-family: Georgia, "Iowan Old Style", serif;
}}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QTableWidget, QSpinBox, QDoubleSpinBox {{
    background: {INPUT_BG};
    border: 1px solid {LINE_CONTROL};   /* FIX-13: 3:1 real (WCAG 1.4.11) */
    border-radius: {RADIUS_MD}px;
    color: {INK};
    padding: 8px 10px;
    min-height: 28px;
    selection-background-color: {GOLD_SOFT};
    selection-color: {INK_STRONG};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", "Arial";
}}
QTextEdit:hover, QPlainTextEdit:hover, QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
    border-color: {LINE_STRONG};
}}
QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {GOLD};
    background: #FFFFFF;
    padding: 7px 9px;
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: {SURFACE};
    color: {INK_MUTED};
    border-color: {LINE_SOFT};
}}
QComboBox {{ min-height: 32px; padding: 6px 28px 6px 10px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {INK_SOFT};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {INPUT_BG};
    border: 1px solid {LINE};
    border-radius: {RADIUS_MD}px;
    color: {INK};
    selection-background-color: {GOLD_TINT};
    selection-color: {INK_STRONG};
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{ padding: 7px 8px; min-height: 28px; color: {INK}; border-radius: 6px; }}
QComboBox QAbstractItemView::item:hover {{ background: {SURFACE}; }}
QComboBox QAbstractItemView::item:selected {{ background: {GOLD_TINT}; color: {INK_STRONG}; }}
QComboBox QLineEdit {{
    /* BETA2-FOCO-17: el line-edit interno de un combo editable NO hereda el
       color del QSS de QComboBox — bajo la paleta oscura de Windows su texto
       se veía blanco sobre pergamino. Se fija tinta explícitamente. */
    color: {INK};
    background: transparent;
    border: none;
    padding: 0;
    min-height: 0;
}}
QToolTip {{
    /* BETA2-FOCO-17: tooltips legibles en pergamino (antes: popup negro del
       estilo del SO, motivo por el que se suprimían globalmente). */
    background: {SURFACE_HI};
    color: {INK};
    border: 1px solid {LINE};
    border-radius: {RADIUS_SM}px;
    padding: 6px 9px;
}}
QTextEdit, QPlainTextEdit {{ min-height: 60px; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: {RADIUS_LG}px; background: {SURFACE}; }}
QTabBar::tab {{
    background: transparent;
    color: {INK_MUTED};
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}}
QTabBar::tab:hover {{ color: {INK_SOFT}; }}
QTabBar::tab:selected {{ color: {INK_STRONG}; border-bottom: 2px solid {GOLD}; }}
QTableWidget {{ gridline-color: {LINE_SOFT}; }}
QHeaderView::section {{ background: {SURFACE}; color: {INK_SOFT}; padding: 7px; border: none; font-weight: 600; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE_STRONG}; border-radius: 5px; min-height: 34px; }}
QScrollBar::handle:vertical:hover {{ background: {GOLD_SOFT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {LINE_STRONG}; border-radius: 5px; min-width: 34px; }}
QScrollBar::handle:horizontal:hover {{ background: {GOLD_SOFT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
"""


APP_STYLESHEET = _qss()


def build_light_palette():
    """BETA2-FOCO-17: QPalette clara construida con los tokens Dendro.

    En Windows 11 con modo oscuro del SO, Qt 6.5+ aplica una paleta oscura
    (texto casi blanco) allí donde el QSS no fija ``color`` explícito — el
    texto se veía blanco sobre pergamino y los tooltips salían ilegibles.
    La app es de tema claro por diseño: se fija la paleta SIEMPRE.
    """
    from PySide6.QtGui import QPalette

    palette = QPalette()
    groups = (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    )
    spec = {
        QPalette.ColorRole.Window: PAPER,
        QPalette.ColorRole.WindowText: INK,
        QPalette.ColorRole.Base: INPUT_BG,
        QPalette.ColorRole.AlternateBase: SURFACE,
        QPalette.ColorRole.Text: INK,
        QPalette.ColorRole.PlaceholderText: INK_MUTED,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: INK,
        QPalette.ColorRole.ToolTipBase: SURFACE_HI,
        QPalette.ColorRole.ToolTipText: INK,
        QPalette.ColorRole.Highlight: GOLD,
        QPalette.ColorRole.HighlightedText: SURFACE_HI,
        QPalette.ColorRole.Link: GOLD_DEEP,
        QPalette.ColorRole.BrightText: SURFACE_HI,
    }
    for role, hex_color in spec.items():
        for group in groups:
            palette.setColor(group, role, QColor(hex_color))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(INK_MUTED)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(INK_MUTED)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(INK_MUTED)
    )
    return palette


def apply_light_theme(app) -> None:
    """Fija estilo Fusion + paleta clara Dendro a nivel de aplicación.

    Debe llamarse tras crear el ``QApplication`` y antes de construir ventanas.
    Fusion respeta QPalette al 100% (los estilos nativos de Windows no); el
    aspecto real lo sigue mandando ``APP_STYLESHEET``.
    """
    try:
        app.setStyle("Fusion")
    except Exception:  # noqa: BLE001 — el tema nunca debe impedir arrancar
        pass
    app.setPalette(build_light_palette())


# ─────────────────────────────────────────────────────────────────────────
# Elevación y movimiento — la profundidad y las microanimaciones que dan
# aplomo "de producto". Todo falla en silencio: el pulido nunca rompe la lógica.
# ─────────────────────────────────────────────────────────────────────────

def apply_shadow(
    widget: QWidget,
    *,
    blur: float = 26.0,
    y: float = 8.0,
    x: float = 0.0,
    alpha: int = 48,
) -> QGraphicsDropShadowEffect:
    """Sombra cálida suave para dar elevación a una superficie ESTÁTICA.

    AVISO (G08): NO usar en widgets dinámicos, dentro de scroll areas o sobre el
    canvas — QGraphicsDropShadowEffect cachea el render y deja zonas en blanco al
    refrescar. Para esos casos usa ``paint_soft_shadow`` (pintada) o elevación por
    contraste (Card). Para realce-al-hover usa ``install_hover_lift`` (canvas-safe).
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(x)
    effect.setYOffset(y)
    effect.setColor(QColor(SHADOW_RGB[0], SHADOW_RGB[1], SHADOW_RGB[2], alpha))
    widget.setGraphicsEffect(effect)
    return effect


class _HoverLift(QObject):
    """Filtro de eventos que REALZA una superficie al pasar el ratón, CANVAS-SAFE.

    En vez de proyectar sombra con QGraphicsDropShadowEffect (que cachea el render
    y deja zonas en blanco en widgets dinámicos; lección G08), resalta el borde por
    contraste — la elevación canon del repo. Una regla QSS sin selector aplica al
    propio widget, así que ``base + 'border: ...'`` funciona sobre cualquier
    superficie sin tocar su selector con objectName. Falla en silencio."""

    def __init__(self, widget: QWidget, *, hover_border: str = GOLD_SOFT):
        super().__init__(widget)
        self._w = widget
        self._base = widget.styleSheet() or ""
        self._hover = f"{self._base}\nborder: 1px solid {hover_border};"
        widget.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        try:
            etype = event.type()
            if etype == QEvent.Type.Enter:
                self._w.setStyleSheet(self._hover)
            elif etype == QEvent.Type.Leave:
                self._w.setStyleSheet(self._base)
        except Exception:  # noqa: BLE001 - el pulido nunca rompe la UI
            pass
        return False


def install_hover_lift(
    widget: QWidget,
    *,
    hover_border: str = GOLD_SOFT,
    **_legacy: object,
) -> _HoverLift | None:
    """Instala un realce-al-hover CANVAS-SAFE (contraste de borde) y lo devuelve.

    Sustituye al antiguo realce por sombra (QGraphicsDropShadowEffect, prohibido en
    widgets dinámicos). Acepta y descarta kwargs legados (blur/alpha/duration) para
    no romper llamadas existentes."""
    try:
        return _HoverLift(widget, hover_border=hover_border)
    except Exception:  # noqa: BLE001
        return None


ICON_GLYPHS = {
    "settings": "⚙",
    "project": "◇",
    "creation": "✧",
    "gallery": "◌",
    "session": "☉",
    "back": "←",
    "close": "✕",
    "add": "+",
    "edit": "✎",
    "delete": "✕",
    "refresh": "↻",
    "save": "💾",
    "search": "⌕",
    "filter": "▽",
    "expand": "▾",
    "collapse": "▸",
    "worldbuilding": "🌐",
    "layers": "☰",
}


class Card(QFrame):
    """Soft bordered card used by normal-mode product UI.

    Ahora con elevación real (sombra cálida) y, opcionalmente, una leve
    elevación al pasar el ratón — el aplomo "de producto"."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
        *,
        elevated: bool = True,
        hover: bool = True,
    ):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame#card {{ background: {SURFACE_HI}; border: 1px solid {LINE}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(SPACE_LG, 14, SPACE_LG, 14)
        self.layout.setSpacing(SPACE_SM)
        if title:
            self.title = QLabel(title)
            self.title.setStyleSheet(
                f"font-size: {TYPE_H2_PX}px; font-weight: {WEIGHT_BOLD}; "
                f"color: {INK_STRONG}; background: transparent;"
            )
            self.title.setWordWrap(True)
            self.layout.addWidget(self.title)
        if subtitle:
            self.subtitle = QLabel(subtitle)
            self.subtitle.setObjectName("mutedLabel")
            self.subtitle.setWordWrap(True)
            self.layout.addWidget(self.subtitle)
        # BETA1-G08: la elevación de las tarjetas se consigue por CONTRASTE
        # (SURFACE_HI brillante sobre superficies más profundas) + borde, NO con
        # QGraphicsDropShadowEffect. Las tarjetas viven en scroll areas y se
        # reconstruyen al refrescar; un efecto gráfico ahí cachea el render y
        # deja menús/botones en blanco al cambiar. La estabilidad manda.
        self._elevated = bool(elevated)
        self._hover = bool(hover)

    def add_text(self, text: str, muted: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        if muted:
            label.setObjectName("mutedLabel")
        self.layout.addWidget(label)
        return label

    def add_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(SPACE_SM)
        self.layout.addLayout(row)
        return row

    def add_flow_row(self) -> "FlowLayout":
        """Fila que envuelve sus hijos cuando no caben (badges, botones de acción).

        Evita el desbordamiento horizontal de la tarjeta en paneles estrechos.
        """
        row = FlowLayout(spacing=SPACE_SM)
        self.layout.addLayout(row)
        return row


class FlowLayout(QLayout):
    """Layout que coloca los hijos en fila y los ENVUELVE a la siguiente línea
    cuando no caben en el ancho disponible.

    Necesario en las tarjetas: con un QHBoxLayout, una fila de badges o de varios
    botones impone un ancho mínimo igual a la suma de sus hijos y se pierde hacia
    la derecha en paneles estrechos. Con FlowLayout el ancho mínimo es el del hijo
    más ancho, así que la tarjeta cabe a cualquier anchura.
    """

    def __init__(self, parent: QWidget | None = None, spacing: int = 8):
        super().__init__(parent)
        self._items: list[Any] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):  # noqa: N802 (API Qt)
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x, y, line_height = rect.x(), rect.y(), 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


# ─────────────────────────────────────────────────────────────────────────
# BETA-MULTIAGENT2-FIX-14 (G2-21): vaciar un layout SIN dejar fantasmas
# ─────────────────────────────────────────────────────────────────────────


def clear_layout(layout, *, conservar_al_final: int = 0) -> int:
    """Retira y destruye el contenido de `layout`. Devuelve cuántos ítems sacó.

    `conservar_al_final` deja intactos los N últimos ítems (típicamente el
    `addStretch` final de una estantería, que es un espaciador y no un widget).

    El idioma repetido por el host —``while layout.count(): layout.takeAt(0)`` +
    ``widget.deleteLater()``— NO basta: ``deleteLater`` solo ENCOLA el borrado, así
    que hasta que el bucle de eventos lo procese el widget sigue siendo hijo del
    contenedor y **sigue pintándose**. De ahí el mensaje nuevo escrito encima del
    viejo en el panel de Estructura y los chips «MedioMedio» de la Ficha del Foco:
    el mismo defecto en dos ficheros.

    ``setParent(None)`` lo saca del árbol AL INSTANTE (deja de pintarse y de contar
    como hijo) y ``deleteLater`` libera el objeto C++ cuando toque. Recurre sobre
    los sub-layouts porque varios ``_build`` mezclan ``addWidget`` y ``addLayout``.
    """
    if layout is None:
        return 0
    retirados = 0
    while layout.count() > max(0, conservar_al_final):
        item = layout.takeAt(0)
        if item is None:
            break
        retirados += 1
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
            continue
        hijo = item.layout()
        if hijo is not None:
            clear_layout(hijo)
            hijo.setParent(None)
            hijo.deleteLater()
    return retirados


# ─────────────────────────────────────────────────────────────────────────
# BETA-MULTIAGENT2-FIX-14 (G2-22): microcopia de borrado que no miente
# ─────────────────────────────────────────────────────────────────────────
#
# Los tres diálogos de borrado (Foco entidad, Foco relación, Mapa) afirmaban
# «Esta acción no se puede deshacer» — y Ctrl+Z la deshacía en 0,19 s medidos.
# El daño no es el bug: es la conducta que induce (nadie borra nada, el proyecto
# se llena de basura intocable). El resto del mensaje NO se toca: decir QUÉ se
# lleva por delante es el mejor microcopy del producto según dos testers.
AVISO_DESHACER_BORRADO = "Podrás deshacerlo con Ctrl+Z mientras la ventana siga abierta."


class Badge(QLabel):
    """Small chip/badge for user-facing states."""

    def __init__(self, text: str, tone: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        colors = {
            "neutral": (GOLD_TINT, INK_SOFT),
            "info": ("#DDE4D6", "#566B47"),
            "success": ("#DCE8D2", "#4F6E3F"),
            "warning": ("#EFE2C3", "#8A6534"),
            "danger": ("#EFD4C9", "#8C4A3C"),
            "gold": (GOLD, INK_INVERSE),
        }
        bg, fg = colors.get(tone, colors["neutral"])
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: {RADIUS_SM}px; "
            "padding: 3px 9px; font-size: 12px; font-weight: 700;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACE_XS)
        layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        # BETA1-UX07: regla dorada corta bajo el título — jerarquía editorial
        # cálida, coherente con el acento de oro del sistema.
        accent = QFrame()
        accent.setFixedSize(30, 2)
        accent.setStyleSheet(f"background: {GOLD_SOFT}; border: none; border-radius: 1px;")
        layout.addWidget(accent)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("mutedLabel")
            sub.setWordWrap(True)
            layout.addWidget(sub)


class EmptyState(Card):
    """Estado vacío que GUÍA: título + mensaje y, opcionalmente, una acción sugerida.

    Con ``action_text`` + ``on_action`` añade un botón primario centrado para que la
    pantalla/lista vacía invite a actuar ("Crea tu primera entidad") en vez de
    quedar en blanco."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
        *,
        action_text: str | None = None,
        on_action=None,
        close_text: str | None = None,
        on_close=None,
    ):
        super().__init__(title, message, parent, elevated=False)
        self.setStyleSheet(
            f"QFrame#card {{ background: {SURFACE}; border: 1px dashed {LINE_STRONG}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        self.action_button: QPushButton | None = None
        self.close_button: QPushButton | None = None
        buttons: list[QPushButton] = []
        # BETA1-I78: botón de cerrar (secundario) para descartar el aviso vacío.
        if close_text and callable(on_close):
            close_btn = QPushButton(close_text)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.clicked.connect(on_close)
            self.close_button = close_btn
            buttons.append(close_btn)
        if action_text and callable(on_action):
            button = QPushButton(action_text)
            button.setObjectName("primaryButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(on_action)
            self.action_button = button
            buttons.append(button)
        if buttons:
            row = self.add_row()
            row.addStretch(1)
            for button in buttons:
                row.addWidget(button)
            row.addStretch(1)


class PanelScaffold(QWidget):
    """Estructura común de los paneles de cajón.

    Unifica jerarquía y márgenes: cabecera (``SectionHeader`` + badge opcional),
    ``body`` (QVBoxLayout para el contenido) con márgenes-token, y una barra de
    acciones inferior opcional (secundarios a la izquierda, primario a la derecha).
    Construir paneles a partir de esto, en vez de a mano, mantiene coherentes TODOS
    los cajones. Sin graphics effect (canvas-safe)."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        *,
        badge: str | None = None,
        badge_tone: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        self._outer.setSpacing(SPACE_MD)

        # BETA2-PULIDO-04: sin título/subtítulo/badge no se monta cabecera —
        # para paneles cuyo título lo pone el contenedor (p. ej. el drawer).
        self.header: SectionHeader | None = None
        if title or subtitle or badge:
            header_row = QHBoxLayout()
            header_row.setContentsMargins(0, 0, 0, 0)
            header_row.setSpacing(SPACE_SM)
            self.header = SectionHeader(title, subtitle)
            header_row.addWidget(self.header, 1)
            if badge:
                header_row.addWidget(
                    Badge(badge, tone=badge_tone), 0, Qt.AlignmentFlag.AlignTop
                )
            self._outer.addLayout(header_row)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(SPACE_MD)
        self._outer.addLayout(self.body, 1)

        self._action_bar: QHBoxLayout | None = None

    def add_widget(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout: QLayout) -> QLayout:
        self.body.addLayout(layout)
        return layout

    def add_stretch(self) -> None:
        self.body.addStretch(1)

    def add_action_bar(self) -> QHBoxLayout:
        """Crea (una vez) la fila de acciones al pie del panel y la devuelve.

        Añade tú los botones: los secundarios primero, luego ``addStretch()`` y
        el primario, para el patrón estándar (primario a la derecha)."""
        if self._action_bar is None:
            self._action_bar = QHBoxLayout()
            self._action_bar.setContentsMargins(0, 0, 0, 0)
            self._action_bar.setSpacing(SPACE_SM)
            self._outer.addLayout(self._action_bar)
        return self._action_bar


class AdvancedSection(QWidget):
    """Collapsible container for technical details visible only in advanced mode."""

    def __init__(self, title: str = "Datos técnicos", parent: QWidget | None = None):
        super().__init__(parent)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.body = QWidget()
        self.body.setVisible(False)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 6, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        # BETA1-UX feedback: desplegar Y plegar con movimiento (antes el cierre
        # era instantáneo). Anima la altura del cuerpo con los tokens comunes.
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        body = self.body
        anim = QPropertyAnimation(body, b"maximumHeight", self)
        anim.setDuration(MOTION_BASE)
        if checked:
            body.setVisible(True)
            body.setMaximumHeight(0)
            target = max(body.sizeHint().height(), body.layout().sizeHint().height(), 1)
            anim.setStartValue(0)
            anim.setEndValue(target)
            anim.setEasingCurve(EASING_ENTER)
            anim.finished.connect(lambda: body.setMaximumHeight(16777215))
            fade_in(body, duration_ms=MOTION_BASE, start_opacity=0.4)
        else:
            anim.setStartValue(max(body.height(), 1))
            anim.setEndValue(0)
            anim.setEasingCurve(EASING_STD)
            anim.finished.connect(lambda: body.setVisible(False))
        self._anim = anim
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class DisclosureSection(QWidget):
    """Sección plegable ESTÁTICA — alterna visibilidad, sin QGraphicsEffects.

    A diferencia de ``AdvancedSection`` (que anima con ``fade_in`` → efecto de opacidad),
    esta variante NO usa efectos gráficos: los efectos de opacidad vacían menús/botones y
    rejillas dinámicas (lección conocida del repo). Pensada para contenidos editables
    (rejillas de meses, listas de días). Cabecera = ``QToolButton`` con flecha.
    """

    toggled = Signal(bool)

    def __init__(self, title: str, *, expanded: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setObjectName("disclosureToggle")
        self.body = QWidget()
        self.body.setVisible(expanded)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 6, 0, 0)
        self.body_layout.setSpacing(6)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.body.setVisible(checked)
        self.toggled.emit(checked)

    def add_widget(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def add_layout(self, layout: QLayout) -> None:
        self.body_layout.addLayout(layout)

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(bool(expanded))

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()


def fade_in(widget: QWidget, *, duration_ms: int = MOTION_BASE, start_opacity: float = 0.0):
    """Subtle opacity transition for content that appears inside the shell.

    Presentation-only helper: no domain/persistence side effects. It intentionally
    fails closed so visual polish never breaks workflow logic.
    """
    try:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(start_opacity)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(duration_ms)
        animation.setStartValue(start_opacity)
        animation.setEndValue(1.0)
        animation.setEasingCurve(EASING_STD)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        pass


def fade_out(widget: QWidget, *, duration_ms: int = MOTION_BASE, on_done=None):
    """Desvanece *widget* de opaco a transparente y, al terminar, llama on_done.

    Pensado para velos/overlays PLANOS (sin hijos interactivos) — p. ej. la
    transición entre vistas. NO usar sobre widgets con menús/botones dinámicos
    (los efectos de opacidad los vacían; lección conocida). Falla en silencio."""
    try:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(1.0)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(duration_ms)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(EASING_STD)
        if on_done is not None:
            animation.finished.connect(on_done)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass


def pulse_feedback(widget: QWidget, *, duration_ms: int = MOTION_BASE):
    """Quick tactile feedback for successful/acknowledged actions."""
    try:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(duration_ms)
        animation.setStartValue(0.62)
        animation.setKeyValueAt(0.45, 1.0)
        animation.setEndValue(0.92)
        animation.setEasingCurve(EASING_STD)
        animation.finished.connect(lambda: effect.setOpacity(1.0))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        pass


class BusyIndicator(QWidget):
    """Indicador de actividad orgánico, canvas-safe.

    Un arco dorado que gira mientras una operación asíncrona está en curso. Pensado
    para puntos SIN metáfora de semilla (cálculo de vista previa, jobs IA en vuelo).
    Usa el patrón establecido (QTimer ~40fps + paintEvent), nunca QGraphicsEffect
    (que vacía widgets dinámicos; lección G08). Oculto y parado por defecto: no
    consume CPU hasta que se llama a ``start()``.
    """

    def __init__(
        self,
        *,
        diameter: int = 18,
        period_ms: int = 900,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._diameter = max(8, int(diameter))
        self._period_ms = max(120, int(period_ms))
        self._angle = 0.0  # grados
        self._running = False
        self.setFixedSize(self._diameter + 4, self._diameter + 4)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL)  # cadencia única del design system
        self._timer.timeout.connect(self._tick)
        self.hide()

    # ── API ──────────────────────────────────────────────────────────────
    def set_period_ms(self, period_ms: int) -> None:
        """Duración de una vuelta completa (ms). El caller la deriva de
        ``animation_duration()`` para respetar la intensidad del usuario."""
        self._period_ms = max(120, int(period_ms))

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        self.hide()

    def is_running(self) -> bool:
        return self._running

    # ── animación ────────────────────────────────────────────────────────
    def _tick(self) -> None:
        # Grados por tick = 360 * (intervalo / periodo). Avance constante y suave.
        self._angle = (self._angle + 360.0 * (self._timer.interval() / self._period_ms)) % 360.0
        self.update()

    def hideEvent(self, event):  # noqa: N802 (Qt signature)
        # Parar el timer al ocultar evita consumir CPU en vano.
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt signature)
        if self._running and not self._timer.isActive():
            self._timer.start()
        super().showEvent(event)

    def paintEvent(self, _event):  # noqa: N802
        if not self._running:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        m = 2.0
        arc_rect = QRectF(m, m, rect.width() - 2 * m, rect.height() - 2 * m)
        pen = QPen(QColor(GOLD), 2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        # Pista tenue de fondo (anillo completo) para dar cuerpo sin ruido.
        track = QPen(QColor(GOLD_SOFT), 2.0)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        track_col = QColor(GOLD_SOFT)
        track_col.setAlpha(70)
        track.setColor(track_col)
        painter.setPen(track)
        painter.drawArc(arc_rect, 0, 360 * 16)
        # Arco activo: 270° que giran. Qt mide en 1/16 de grado, sentido antihorario.
        painter.setPen(pen)
        start_angle = int(-self._angle * 16)
        painter.drawArc(arc_rect, start_angle, 270 * 16)


def make_scroll_area(content: QWidget, *, transparent: bool = False) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    if transparent:
        # PULIDO-05: variante para scrolls sobre tarjetas (el viewport no tapa
        # el fondo del contenedor).
        area.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
    return area


def meta_chip_style() -> str:
    """UI2-07: QSS de chip compacto para los combos de metadatos de la Ficha
    del Foco (tipo/anillo/naturaleza/relevancia). Discretos y en una fila:
    el protagonista de la Ficha es el texto, no el formulario."""
    return (
        f"QComboBox {{ background: {SURFACE}; border: 1px solid {LINE_SOFT}; "
        f"border-radius: 11px; padding: 1px 10px; font-size: {TYPE_CAPTION_PX}px; "
        f"color: {INK_SOFT}; }} "
        f"QComboBox:hover {{ border-color: {GOLD_SOFT}; background: {GOLD_TINT}; }} "
        "QComboBox::drop-down { border: none; width: 14px; }"
    )


def overline_label(text: str, *, color: str = "", parent: QWidget | None = None) -> QLabel:
    """PULIDO-05: rol tipográfico «overline» — micro-título en MAYÚSCULAS con
    tracking (11px/700/1px), única forma de encabezado menor del sistema.

    WS-J: Qt IGNORA ``letter-spacing`` en QSS; el tracking se aplica de verdad vía
    ``QFont.setLetterSpacing`` (y las mayúsculas ya se hacen en Python, no con el
    ``text-transform`` inerte). El QSS solo lleva color/fondo."""
    label = QLabel(str(text).upper(), parent)
    label.setStyleSheet(
        f"color: {color or INK_MUTED}; background: transparent; border: none;"
    )
    font = label.font()
    font.setPixelSize(TYPE_OVERLINE_PX)
    font.setWeight(QFont.Weight.Bold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
    label.setFont(font)
    return label


class ElidedLabel(QLabel):
    """PULIDO-05: QLabel de UNA línea que elide con «…» en vez de desbordar o
    forzar el ancho del layout. Sin QGraphicsEffect (canvas-safe)."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self._full_text = str(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802 (API Qt)
        self._full_text = str(text)
        self._apply_elide()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event):  # noqa: N802 (API Qt)
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        metrics = self.fontMetrics()
        width = max(0, self.width() - 2)
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        super().setText(elided)
        self.setToolTip(self._full_text if elided != self._full_text else "")


class CapsuleTabBar(QFrame):
    """UI2-06: segmento cápsula de pestañas — el patrón visual del alternador
    de modos (Foco | Mapa | Cronología) aplicado a pestañas locales de un
    panel. QSS puro, sin QGraphicsEffect (canvas-safe).

    API: ``add_tab(key, label)``, ``set_current(key)``, ``current()`` y la
    señal ``tabChanged(str)`` (solo se emite en cambios reales).
    """

    tabChanged = Signal(str)  # noqa: N815 — convención Qt de señales

    _ACTIVE_SS = (
        "QPushButton {{ background: {gold_tint}; border: none; border-radius: 13px; "
        "color: {ink_strong}; font-size: 12px; font-weight: 700; padding: 0 14px; }}"
    )
    _IDLE_SS = (
        "QPushButton {{ background: transparent; border: none; border-radius: 13px; "
        "color: {ink_soft}; font-size: 12px; font-weight: 600; padding: 0 14px; }} "
        "QPushButton:hover {{ background: {gold_tint}; color: {ink_strong}; }} "
        "QPushButton:pressed {{ background: {gold_soft}; }}"
    )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {SURFACE_HI}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: {RADIUS_CAPSULE}px; }}"
        )
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(5, 3, 5, 3)
        self._row.setSpacing(0)
        self._buttons: dict[str, QPushButton] = {}
        self._current = ""

    def add_tab(self, key: str, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(26)
        button.clicked.connect(lambda _=False, k=key: self.set_current(k))
        self._row.addWidget(button)
        self._buttons[str(key)] = button
        if not self._current:
            self.set_current(key)
        else:
            self._restyle()
        return button

    def current(self) -> str:
        return self._current

    def set_current(self, key: str) -> None:
        key = str(key)
        if key not in self._buttons or key == self._current:
            return
        self._current = key
        self._restyle()
        self.tabChanged.emit(key)

    def _restyle(self) -> None:
        tones = {
            "gold_tint": GOLD_TINT,
            "gold_soft": GOLD_SOFT,
            "ink_strong": INK_STRONG,
            "ink_soft": INK_SOFT,
        }
        for key, button in self._buttons.items():
            template = self._ACTIVE_SS if key == self._current else self._IDLE_SS
            button.setStyleSheet(template.format(**tones))


# ─────────────────────────────────────────────────────────────────────────
# Guard de rueda del ratón (BETA1-UX feedback): dentro de los cajones, la rueda
# sobre un combo/spin/slider NO debe cambiar su valor (el usuario solo quiere
# desplazar el menú). Redirige la rueda al QScrollArea ancestro y bloquea el
# cambio salvo que el control tenga el foco explícito (click).
# ─────────────────────────────────────────────────────────────────────────

_WHEEL_GUARDED_TYPES = (QComboBox, QAbstractSpinBox, QSlider)


class _WheelGuard(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            # Buscar el QScrollArea ancestro y desplazarlo en su lugar.
            node = obj.parent()
            while node is not None and not isinstance(node, QScrollArea):
                node = node.parent()
            if isinstance(node, QScrollArea):
                bar = node.verticalScrollBar()
                try:
                    bar.setValue(bar.value() - event.angleDelta().y())
                except Exception:  # noqa: BLE001
                    pass
            return True  # consumir: el valor del control no cambia
        return False


# Filtro compartido (sin estado): un único objeto basta para todos los controles.
_WHEEL_GUARD = _WheelGuard()


def install_wheel_guard(container: QWidget) -> None:
    """Protege todos los combos/spin/slider descendientes de *container* contra
    cambios accidentales por rueda. Idempotente y tolerante a fallos."""
    try:
        for tipo in _WHEEL_GUARDED_TYPES:
            for child in container.findChildren(tipo):
                child.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # la rueda no enfoca
                child.installEventFilter(_WHEEL_GUARD)
    except Exception:  # noqa: BLE001 - el pulido nunca rompe la UI
        pass


# ─────────────────────────────────────────────────────────────────────────
# BETA-MULTIAGENT2-FIX-13 (G2-20), TANDA E — las tildes.
#
# Los valores de los enums son la FORMA EN DISCO y van sin tilde por diseño
# (`localizacion`, `faccion`, `catastrofe`…). `enum_human` era un
# `replace("_"," ").capitalize()` sin mapa, así que la app enseñaba a una
# novelista «Localizacion», «Faccion», «Sistema magico» y «Catastrofe».
#
# El mapa vive DENTRO de `enum_human` a propósito: `node_detail_panel` y
# `relation_detail_panel` reseleccionan su combo con `combo.findText(
# enum_human(value))`. Si la etiqueta se pusiera en los `addItem`, la ficha
# dejaría de reseleccionar su propio tipo al abrirse, en silencio.
#
# Ningún valor cambia en disco: esto es SOLO la cara visible.
# ─────────────────────────────────────────────────────────────────────────

_ENUM_LABELS: dict[str, str] = {
    # EntityType
    "localizacion": "Localización",
    "faccion": "Facción",
    "tecnologia": "Tecnología",
    "sistema_magico": "Sistema mágico",
    "religion": "Religión",
    "institucion": "Institución",
    "sesion": "Sesión",
    "organizacion": "Organización",
    "regla_del_mundo": "Regla del mundo",
    # CausalMilestoneType
    "fundacion": "Fundación",
    "traicion": "Traición",
    "catastrofe": "Catástrofe",
    "migracion": "Migración",
    "caida": "Caída",
    "revelacion": "Revelación",
    # RelationType — verbos con tilde y preposiciones en minúscula
    "participo_en": "Participó en",
    "causo": "Causó",
    "traiciono": "Traicionó",
    "esta_ubicado_en": "Está ubicado en",
    "esta_en_conflicto_con": "Está en conflicto con",
    "esta_relacionado_con": "Está relacionado con",
    "ha_oido": "Ha oído",
    "esta_en": "Está en",
    # CanonState / VisibilityState
    "canonico": "Canónico",
    "publico_mundo": "Público en el mundo",
    # Candidatos / incidencias
    "requiere_revision": "Requiere revisión",
    "correccion": "Corrección",
    "fusion": "Fusión",
    "relacion": "Relación",
    "contradiccion": "Contradicción",
    "propuesta_post_sesion": "Propuesta tras la sesión",
    "nota_post_sesion": "Nota tras la sesión",
    "actualizacion_post_sesion": "Actualización tras la sesión",
    "cambio_configuracion": "Cambio de configuración",
    "creacion_relacion": "Creación de relación",
    "edicion_relacion": "Edición de relación",
    "archivado_relacion": "Archivado de relación",
    "memoria_propuesta_revision": "Memoria: propuesta de revisión",
    # Otros enums visibles
    "vision": "Visión",
    "investigacion": "Investigación",
    "conspiracion": "Conspiración",
    "preparacion": "Preparación",
    "estado_revision": "Estado de revisión",
}


def enum_human(value: Any) -> str:
    """Etiqueta legible (y ACENTUADA) de un valor de enum del dominio."""
    raw = getattr(value, "value", value)
    text = str(raw if raw not in (None, "") else "—")
    etiqueta = _ENUM_LABELS.get(text.strip().lower())
    if etiqueta:
        return etiqueta
    return text.replace("_", " ").replace("-", " ").strip().capitalize() or "—"


def human_ref(name: str | None, kind: str | None = None) -> str:
    clean_name = (name or "Sin nombre").strip() or "Sin nombre"
    clean_kind = (kind or "").strip()
    return f"{clean_name} · {clean_kind}" if clean_kind else clean_name


def join_human(items: Iterable[Any], empty: str = "—") -> str:
    values = [str(item) for item in items if str(item)]
    return ", ".join(values) if values else empty
