"""Ayuda contextual por campo (PA04).

Cada campo de la configuración creativa (wizard + panel) lleva un pequeño icono
``ⓘ`` que, al pasar el ratón por encima, muestra un tooltip con una explicación
breve tomada del catálogo ``FIELD_HELP``.

Se evita deliberadamente ``QGraphicsEffect`` (sombras/opacidad) sobre estos
widgets: hay constancia en la memoria del repo de que rompen widgets dinámicos
(menús/botones en blanco). Aquí basta con contraste + el tooltip nativo de Qt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK,
    INK_SOFT,
    INK_STRONG,
    SURFACE_HI,
    TYPE_BODY_PX,
    TYPE_CAPTION_PX,
)

# ---------------------------------------------------------------------------
# Catálogo de textos de ayuda (clave → texto). Fuente única para wizard+panel.
# ---------------------------------------------------------------------------

FIELD_HELP: dict[str, str] = {
    # Identidad
    "premisa": "La frase nuclear del proyecto: de qué va en una línea. El campo más importante.",
    "resumen_corto": "1–3 párrafos que sirven de contexto global constante para la IA.",
    "genero_principal": (
        "Género dominante: fantasía, ciencia ficción, terror, noir, realismo mágico…"
    ),
    "subgeneros": "Subgéneros e influencias. Añade varios; no hace falta separarlos mucho.",
    "formato": (
        "Formato de la obra: novela, videojuego, mundo abierto, antología, cómic…"
    ),
    "publico": "Para quién es: adulto, juvenil, jugadores de rol, lectores de fantasía oscura…",
    "idioma": "Idioma principal. Define consistencia de nombres, tono y salida de la IA.",
    "estado": (
        "Momento del proyecto: borrador, exploración, canon en consolidación, "
        "producción, campaña activa."
    ),
    # Dirección creativa
    "promesa": (
        "Qué experiencia promete el proyecto. Ej: 'intriga industrial donde toda "
        "victoria tiene coste'."
    ),
    "pregunta_dramatica": (
        "La pregunta central. Ej: '¿se puede escapar de una deuda que define quién eres?'"
    ),
    "temas": "Temas principales que recorren la obra (poder, identidad, memoria…).",
    "emociones": (
        "Emociones que buscas provocar: miedo, fascinación, melancolía, tensión, "
        "extrañeza, épica, intimidad."
    ),
    "sensacion_final": "Cómo debe quedarse el lector/jugador al terminar.",
    "originalidad": "Cuán convencional o autoral: de convencional a muy autoral.",
    "ambiguedad": "Grado de ambigüedad: claro y directo vs ambiguo e interpretativo.",
    "tipo_impacto": (
        "Tipo de impacto buscado: emocional, intelectual, político, sensorial, moral, lúdico."
    ),
    # Motor narrativo
    "fuente_conflicto": (
        "Fuente principal de conflicto: poder, supervivencia, deuda, deseo, trauma, ideología…"
    ),
    "mecanismo": (
        "Mecanismo narrativo dominante: intriga, investigación, guerra de facciones, "
        "viaje, conspiración…"
    ),
    "causalidad": (
        "Modelo de causalidad: suave, simbólica, estricta, política, psicológica, sistémica."
    ),
    "agencia": (
        "Agencia de los personajes: alta, media, baja, trágica o condicionada por "
        "estructuras superiores."
    ),
    "escalada": "Cómo escala la tensión: lenta, episódica, acumulativa, explosiva, cíclica.",
    "cambio_personaje": (
        "Cambio esperado en los personajes: corrupción, redención, caída, maduración, "
        "radicalización, revelación, ruptura."
    ),
    # Estilo y tono
    "tono": (
        "Tono general: oscuro, sobrio, mítico, íntimo, irónico, brutal, contemplativo, épico…"
    ),
    "realismo": "Nivel de realismo del mundo: bajo, medio o alto.",
    "grado_especulativo": (
        "Lógica del mundo / grado especulativo: realista, leve, moderado, alto, fantástico pleno."
    ),
    "estilo_narrativo": (
        "Estilo de prosa: poético, seco, documental, pulp, literario, cinematográfico, "
        "oral, fragmentario."
    ),
    "densidad": "Densidad descriptiva/conceptual: ligero, medio o denso.",
    "exposicion": (
        "Cómo se da la información: directa, gradual, por pistas, fragmentaria o misteriosa."
    ),
    # Reglas y límites
    "reglas_canon": "Reglas duras de canon que la IA NUNCA debe contradecir.",
    "evitar": "Espacio negativo: tropos, tonos, soluciones, frases o tics que se deben evitar.",
    # -----------------------------------------------------------------------
    # BETA-AUDIT-06 — Vocabulario del jardín.
    #
    # Estas palabras (anillo, regar, semilla, arraigo…) son el idioma propio de
    # Dendro y hasta ahora no se explicaban en ninguna parte de la app: las
    # definiciones buenas existían sólo dentro del prompt que se le manda al
    # modelo (packages/application/command_prompts.py, tarea "water_entity").
    # Es decir, la IA tenía el glosario y el usuario no. Aquí se adaptan a
    # lenguaje llano, para quien abre la app por primera vez.
    #
    # Prefijo `glosario_` para no colisionar con los 30 campos de arriba.
    # -----------------------------------------------------------------------
    "glosario_anillo": (
        "Un estrato del mundo. Los anillos ordenan tus cosas por cuánta consecuencia "
        "pueden desencadenar: al centro lo que causa (una guerra, una ley del mundo), "
        "hacia fuera lo que la sufre (una posada, un secundario)."
    ),
    "glosario_capa": "Otro nombre para el anillo. Es el mismo concepto.",
    "glosario_rama": (
        "Una entidad que agrupa a otras, como una carpeta con nombre propio: una "
        "familia, un gremio, una ciudad con sus barrios. No es una bifurcación de la "
        "historia."
    ),
    "glosario_hoja": (
        "Una entidad suelta, la unidad básica: un personaje, un lugar, un objeto, una "
        "idea. Se llama hoja por oposición a rama, que contiene otras."
    ),
    "glosario_hito": (
        "Un suceso fechado de tu mundo: una batalla, un pacto, una muerte. Vive en la "
        "Cronología y puede tener causas y consecuencias."
    ),
    "glosario_era": (
        "Un tramo con nombre de tu calendario: «Era de la Helada». Sirve para situar "
        "hitos y vidas sin manejar años sueltos."
    ),
    "glosario_lapso_vida": (
        "Desde cuándo hasta cuándo existe algo. En la Cronología es la barra que puedes "
        "arrastrar por los extremos."
    ),
    "glosario_canon": (
        "Lo que es verdad en tu mundo, lo que tú has aceptado. La IA nunca escribe "
        "aquí: sólo propone, y tú decides qué entra."
    ),
    "glosario_semilla": (
        "Una propuesta de la IA que aún no es tuya. Germina en el lienzo con un aviso; "
        "si la aceptas florece y pasa a ser canon, si la rechazas se marchita. Hasta "
        "que aceptas, tu mundo no ha cambiado."
    ),
    "glosario_fantasma": (
        "Un hueco con nombre: marcas que ahí falta algo («aquí va un traidor») sin "
        "inventártelo todavía. Puedes relacionarlo como cualquier entidad, pero no "
        "cuenta como canon ni sostiene nada."
    ),
    "glosario_regar": (
        "Pedirle a la IA que lea lo que hay y escriba la página de Memoria de esa "
        "entidad, con una puntuación de cómo está. No inventa canon nuevo: lo resume "
        "y lo juzga."
    ),
    "glosario_memoria": (
        "La wiki que la IA mantiene sobre tu mundo: una página por elemento, con "
        "enlaces y preguntas abiertas. Es interpretación, no canon; tu texto manda."
    ),
    "glosario_arraigo": (
        "Cuánto sostiene el resto del mundo a esta entidad: los contextos, hitos y "
        "relaciones que hacen creíble que exista. Las fechas que no cuadran restan "
        "arraigo."
    ),
    "glosario_nutrida": (
        "Cuánto tiene por dentro y cuánto encaja con sus vecinas: descripciones, "
        "coherencia propia e integración con su rama y su entorno."
    ),
    "glosario_iluminada": (
        "Cuánto proyecta hacia fuera: consecuencias, derivaciones e influencia sobre "
        "otras entidades. Una entidad iluminada deja huella en el resto."
    ),
    "glosario_relevancia": (
        "Cuánto te importa a TI para tu historia. La fijas tú, no la IA, y es "
        "independiente de que algo cause mucho o poco."
    ),
    "glosario_potencia_causal": (
        "Cuánta consecuencia puede desatar algo por su naturaleza: una guerra mucha, "
        "un campesino poca. Es lo que decide en qué anillo debería vivir. La atribuye "
        "la IA al regar."
    ),
    "glosario_falta_regar": (
        "Algo cambió cerca y esta página se quedó vieja. No es un error ni una regañina: "
        "es un aviso de que conviene revisarla."
    ),
    "glosario_secada": (
        "La has apartado del ciclo a propósito para que deje de pedirte atención. Se "
        "revierte cuando quieras con «Cultivar»."
    ),
    # -----------------------------------------------------------------------
    # BETA2-FIX-13 (G2-20) — los 8 que faltaban del «Diccionario de
    # Carmen». El glosario cubría 19 términos y estaba bien escrito, pero se
    # quedaba corto justo en las palabras con las que uno se tropieza el primer
    # día: qué es una entidad, qué significa que algo «germine», qué es el Foco.
    #
    # Aviso deliberado: la metáfora del jardín NO se renombra. Gusta («los
    # anillos son una idea de primera», dos informes). Lo que fallaba es que no
    # se enseñaba.
    # -----------------------------------------------------------------------
    "glosario_entidad": (
        "Cualquier cosa de tu mundo con nombre propio: una persona, un lugar, un objeto, "
        "una facción, una idea. Es la pieza con la que se construye todo lo demás; hojas "
        "y ramas son entidades."
    ),
    "glosario_germinar": (
        "Lo que hace una propuesta de la IA mientras esperas: aparece en el lienzo "
        "latiendo, todavía sin ser tuya. Si la aceptas FLORECE y pasa a ser canon; si la "
        "rechazas se MARCHITA y desaparece sin dejar rastro."
    ),
    "glosario_cultivar": (
        "Devolver al ciclo una entidad que habías apartado («secada»). Vuelve a contar "
        "para el riego y a pedirte atención cuando algo cambie a su alrededor."
    ),
    "glosario_foco": (
        "La vista que pone UNA entidad en el centro y dibuja a su alrededor todo lo que "
        "la toca. Es donde se trabaja de cerca: su ficha, sus relaciones y su cuaderno de "
        "cultivo."
    ),
    "glosario_raices": (
        "En el Foco, lo que sostiene a la entidad del centro: de dónde viene, quién la "
        "causó, a qué pertenece. Su ENTORNO es lo que la rodea en pie de igualdad, y sus "
        "BROTES son lo que ella provoca hacia fuera."
    ),
    "glosario_estructura": (
        "La propuesta de la app para colocar cada cosa en su anillo: mover una entidad, "
        "crear un anillo que falta o fusionar dos que sobran. Son sugerencias con "
        "justificación; tú decides."
    ),
    "glosario_play": (
        "Un recorrido guiado por tu cronología, hito a hito, como quien pasa páginas. "
        "Sirve para revisar la historia en orden y anotar sobre la marcha."
    ),
    "glosario_token": (
        "La unidad con la que se mide cuánto texto lee o escribe la IA (viene a ser "
        "media palabra). Importa porque cada consulta tiene un presupuesto: cuanto mejor "
        "esté la Memoria, menos hace falta enviarle."
    ),
}

# Orden de lectura del glosario visible: de lo que se ve primero a lo que se
# entiende después. No es alfabético a propósito — el alfabeto no enseña nada.
GLOSSARY_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Las piezas de tu mundo",
        ("entidad", "hoja", "rama", "anillo", "capa", "hito", "era", "lapso_vida", "canon"),
    ),
    (
        "Cómo se trabaja",
        ("foco", "raices", "estructura", "play", "fantasma"),
    ),
    (
        "El jardín: cuidar lo que has escrito",
        ("regar", "cultivar", "falta_regar", "secada", "memoria", "potencia_causal"),
    ),
    (
        "Lo que propone la IA",
        ("semilla", "germinar", "token"),
    ),
    (
        "Las cuatro medidas de una entidad",
        ("arraigo", "nutrida", "iluminada", "relevancia"),
    ),
)

# Título visible de cada término (el que ve el usuario; la clave es interna).
GLOSSARY_TITLES: dict[str, str] = {
    "lapso_vida": "Lapso de vida",
    "falta_regar": "Falta regar",
    "potencia_causal": "Potencia causal",
    "raices": "Raíces, entorno y brotes",
    "germinar": "Germinar, florecer, marchitarse",
    "memoria": "Memoria (la wiki)",
}


def glossary_title(term: str) -> str:
    """Título visible de un término del glosario."""
    return GLOSSARY_TITLES.get(term, term.replace("_", " ").capitalize())


def glossary_terms() -> list[str]:
    """Todos los términos del glosario, en orden de lectura."""
    ordenados = [t for _titulo, terminos in GLOSSARY_SECTIONS for t in terminos]
    sueltos = sorted(
        k[len("glosario_") :] for k in FIELD_HELP if k.startswith("glosario_")
    )
    return ordenados + [t for t in sueltos if t not in ordenados]


def glossary(term: str, *, fallback: str = "") -> str:
    """Definición del vocabulario del jardín para ``term`` (sin el prefijo).

    BETA-AUDIT-06. Devuelve ``fallback`` si el término no está en el catálogo, para
    que ningún widget se quede sin tooltip por una clave mal escrita.
    """
    return FIELD_HELP.get(f"glosario_{term}", fallback)


def metric_tooltip(metric_key: str, label: str) -> str:
    """Tooltip de una barra de métrica: «Etiqueta — definición».

    Antes el tooltip repetía la etiqueta («Arraigo» → «Arraigo»), que no explicaba
    nada a quien no conocía ya la palabra.
    """
    definicion = glossary(metric_key)
    return f"{label} — {definicion}" if definicion else label


class _HelpPopover(QFrame):
    """Globo de ayuda propio, con el estilo del resto de la app.

    BETA-AUDIT-06: este docstring afirmaba que el host instalaba un
    ``TooltipSuppressor`` global que bloqueaba ``QEvent.ToolTip`` y que por eso
    ``setToolTip`` no mostraba nada. Era falso: el supresor nunca llegó a
    instalarse y se ha retirado. Los ``setToolTip`` normales funcionan, y de hecho
    son la vía por la que el vocabulario del jardín llega ahora a las métricas y
    a los chips. Este popover se conserva porque da un globo más legible y
    consistente para los campos de configuración creativa.
    """

    def __init__(self, text: str, anchor: QWidget):
        super().__init__(anchor, Qt.WindowType.ToolTip)
        self.setObjectName("fieldHelpPopover")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            f"QFrame#fieldHelpPopover {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 10px; }}"
        )
        col = QVBoxLayout(self)
        col.setContentsMargins(12, 9, 12, 9)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(300)
        label.setStyleSheet(
            f"color: {INK}; font-size: 12px; background: transparent; border: none;"
        )
        col.addWidget(label)
        self.adjustSize()


class FieldHelp(QLabel):
    """Icono de ayuda (i) que muestra un popover propio al pasar el ratón."""

    def __init__(self, help_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._help_text = FIELD_HELP.get(help_key, "")
        self._popover: _HelpPopover | None = None
        self.setText("i")
        self.setObjectName("fieldHelp")
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(18, 18)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Círculo de acento (el fondo redondeado ES el círculo; sin glifo doble).
        self.setStyleSheet(
            f"QLabel#fieldHelp {{ color: {GOLD_DEEP}; background: {GOLD_TINT}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 9px; "
            f'font-family: "Georgia", serif; font-size: 12px; font-weight: 700; '
            f"font-style: italic; }} "
            f"QLabel#fieldHelp:hover {{ color: {INK_STRONG}; background: {GOLD_SOFT}; }}"
        )

    def enterEvent(self, event):  # noqa: N802 - Qt API
        self._show_popover()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - Qt API
        self._hide_popover()
        super().leaveEvent(event)

    def hideEvent(self, event):  # noqa: N802 - Qt API
        self._hide_popover()
        super().hideEvent(event)

    def _show_popover(self) -> None:
        if not self._help_text:
            return
        if self._popover is None:
            self._popover = _HelpPopover(self._help_text, self)
        pop = self._popover
        pop.adjustSize()
        # Debajo del icono, sin salirse del borde derecho de la pantalla.
        origin = self.mapToGlobal(self.rect().bottomLeft())
        x, y = origin.x(), origin.y() + 6
        screen = QGuiApplication.screenAt(origin) or QGuiApplication.primaryScreen()
        if screen is not None:
            right = screen.availableGeometry().right()
            if x + pop.width() > right:
                x = max(screen.availableGeometry().left(), right - pop.width() - 4)
        pop.move(x, y)
        pop.show()
        pop.raise_()

    def _hide_popover(self) -> None:
        if self._popover is not None:
            self._popover.hide()


def labeled_row(label_text: str, help_key: str, parent: QWidget | None = None) -> QWidget:
    """Devuelve un QWidget con el texto de la etiqueta + el icono de ayuda (ⓘ).

    Pensado para usarse como primer argumento de ``QFormLayout.addRow`` o dentro
    de un bloque vertical de campo. El texto de ayuda se toma de ``FIELD_HELP``.
    """
    row = QWidget(parent)
    box = QHBoxLayout(row)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(6)
    lab = QLabel(label_text)
    lab.setStyleSheet(
        f"color: {INK_STRONG}; background: transparent; border: none; font-weight: 600;"
    )
    lab.setWordWrap(True)
    box.addWidget(lab)
    box.addWidget(FieldHelp(help_key))
    box.addStretch(1)
    return row


class GlossaryPanel(QWidget):
    """El glosario, LEGIBLE SIN HOVER (BETA2-FIX-13, G2-20).

    El catálogo existía desde BETA-AUDIT-06 y estaba bien escrito, pero todos sus
    consumidores eran `setToolTip`. Para quien declara «si no pone lo que hace,
    para mí no existe», un glosario que sólo sale al pasar el ratón no existe.
    Esta es la superficie que abre «Ayuda → Glosario».
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("glossaryPanel")
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        cuerpo = QWidget(area)
        columna = QVBoxLayout(cuerpo)
        columna.setContentsMargins(16, 12, 16, 16)
        columna.setSpacing(10)

        entrada = QLabel(
            "El idioma propio de Dendro, en cristiano. Ninguna de estas palabras "
            "hace falta aprendérsela: están aquí para cuando aparezcan."
        )
        entrada.setWordWrap(True)
        entrada.setStyleSheet(
            f"color: {INK}; font-size: {TYPE_BODY_PX}px; background: transparent; border: none;"
        )
        columna.addWidget(entrada)

        self._term_labels: dict[str, QLabel] = {}
        vistos: set[str] = set()
        for titulo_seccion, terminos in GLOSSARY_SECTIONS:
            cabecera = QLabel(titulo_seccion.upper())
            cabecera.setStyleSheet(
                f"color: {GOLD_DEEP}; font-size: {TYPE_CAPTION_PX}px; font-weight: 700; "
                "letter-spacing: 1px; background: transparent; border: none; margin-top: 8px;"
            )
            columna.addWidget(cabecera)
            for termino in terminos:
                definicion = glossary(termino)
                if not definicion:
                    continue
                columna.addWidget(self._entrada(termino, definicion))
                vistos.add(termino)

        # Red de seguridad: ningún término del catálogo se queda fuera de la
        # pantalla por olvidarse de añadirlo a una sección.
        sueltos = [t for t in glossary_terms() if t not in vistos and glossary(t)]
        if sueltos:
            cabecera = QLabel("OTROS TÉRMINOS")
            cabecera.setStyleSheet(
                f"color: {GOLD_DEEP}; font-size: {TYPE_CAPTION_PX}px; font-weight: 700; "
                "letter-spacing: 1px; background: transparent; border: none; margin-top: 8px;"
            )
            columna.addWidget(cabecera)
            for termino in sueltos:
                columna.addWidget(self._entrada(termino, glossary(termino)))

        columna.addStretch(1)
        area.setWidget(cuerpo)
        raiz.addWidget(area)

    def _entrada(self, termino: str, definicion: str) -> QWidget:
        tarjeta = QFrame(self)
        tarjeta.setObjectName("glossaryEntry")
        tarjeta.setStyleSheet(
            f"QFrame#glossaryEntry {{ background: {SURFACE_HI}; border: 1px solid {GOLD_SOFT}; "
            # OJO: linea PLANA (sin prefijo f) → el cierre va con UNA llave. Con `}}`
            # Qt descarta la hoja entera y la tarjeta se pinta gris nativa (BETA2-SHIP-07).
            "border-radius: 12px; }"
        )
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(12, 9, 12, 9)
        caja.setSpacing(3)
        titulo = QLabel(glossary_title(termino))
        titulo.setStyleSheet(
            f"color: {INK_STRONG}; font-size: {TYPE_BODY_PX}px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        cuerpo = QLabel(definicion)
        cuerpo.setWordWrap(True)
        cuerpo.setStyleSheet(
            f"color: {INK_SOFT}; font-size: {TYPE_BODY_PX}px; background: transparent; "
            "border: none;"
        )
        caja.addWidget(titulo)
        caja.addWidget(cuerpo)
        self._term_labels[termino] = cuerpo
        return tarjeta

    def terms_on_screen(self) -> list[str]:
        """Términos que el panel pinta de verdad (para la guarda de tests)."""
        return list(self._term_labels)


__all__ = [
    "FIELD_HELP",
    "GLOSSARY_SECTIONS",
    "FieldHelp",
    "GlossaryPanel",
    "glossary",
    "glossary_terms",
    "glossary_title",
    "labeled_row",
    "metric_tooltip",
]
