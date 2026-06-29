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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK,
    INK_STRONG,
    SURFACE_HI,
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
        "Formato de la obra: campaña de rol, novela, videojuego, mundo abierto, antología…"
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
}


class _HelpPopover(QFrame):
    """Globo de ayuda propio (no usa el tooltip nativo, que el host suprime).

    El host instala un ``TooltipSuppressor`` global que bloquea ``QEvent.ToolTip``,
    así que ``setToolTip`` no muestra nada. Este popover es una ventana flotante
    (``Qt.ToolTip``) que el supresor NO intercepta, con el mismo estilo que el
    popover de ayuda del command bar.
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


__all__ = ["FIELD_HELP", "FieldHelp", "labeled_row"]
