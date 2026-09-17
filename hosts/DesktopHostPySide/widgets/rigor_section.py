"""Sección «Rigor»: certeza y datación rica (BETA2-FIX-11, fase B).

El dominio modela desde siempre la frontera que define el oficio de quien
investiga —cinco niveles de certeza, cinco precisiones temporales, fecha del
mundo, periodo, nota y fuentes contradictorias— y **nada de eso tenía formulario**:
`certainty_level` tenía cero apariciones en `hosts/`, y «h. 1334» quedaba
indistinguible de un 1334 documentado (HIS-04/HIS-05).

Esta sección es UNA, compartida por la Ficha de entidad, el panel de relación y el
de hito: sin ella habría tres formularios paralelos del mismo concepto.

Dos reglas que no se rompen:
- **El año entero manda.** `TemporalSpan`/`EventTemporality` son la capa
  descriptiva ENCIMA del año; aquí no se toca `year`/`birth_year`/`death_year`, que
  siguen ordenando el Mapa y la Cronología.
- **La Ficha del perfil no técnico no crece.** La sección nace PLEGADA (solo su
  título) y con etiquetas en español llano: «Certeza», «Precisión de la fecha».
  Nada de `certainty_level` en la cara del usuario (G2-20).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from packages.domain.entity import CertaintyLevel
from packages.domain.temporal_models import EventTemporality, TemporalPrecision

#: Etiquetas humanas del nivel de certeza (el enum del dominio, en español llano).
CERTEZA_OPCIONES: tuple[tuple[str, str], ...] = (
    (CertaintyLevel.CONFIRMADO.value, "Confirmada (documentada)"),
    (CertaintyLevel.PROBABLE.value, "Probable"),
    (CertaintyLevel.POSIBLE.value, "Posible"),
    (CertaintyLevel.DUDOSO.value, "Dudosa"),
    (CertaintyLevel.FALSO.value, "Descartada (falsa)"),
)

#: Etiquetas humanas de la precisión temporal.
PRECISION_OPCIONES: tuple[tuple[str, str], ...] = (
    (TemporalPrecision.EXACT.value, "Exacta"),
    (TemporalPrecision.APPROXIMATE.value, "Aproximada («h. 1334»)"),
    (TemporalPrecision.CONTRADICTORY.value, "Contradictoria (las fuentes no coinciden)"),
    (TemporalPrecision.MYTHICAL.value, "Mítica o legendaria"),
    (TemporalPrecision.UNKNOWN.value, "Sin determinar"),
)


def _enum_value(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    return str(getattr(value, "value", value) or fallback)


class RigorSection(QWidget):
    """Sección plegable con certeza + datación rica. Emite ``changed`` al editar."""

    changed = Signal()

    def __init__(
        self,
        *,
        con_certeza: bool = True,
        con_datacion: bool = True,
        titulo: str = "Rigor: certeza y datación",
        expandida: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._con_certeza = con_certeza
        self._con_datacion = con_datacion
        self._loading = False  # durante `load()` no se emite `changed`

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 0)
        root.setSpacing(4)

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(bool(expandida))
        self.toggle.setText(titulo)
        self.toggle.setToolTip(
            "De dónde sale esto y hasta qué punto es seguro: lo documentado frente a "
            "lo inventado. Opcional; si no lo usas, no molesta."
        )
        self.toggle.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self.toggle.toggled.connect(self._on_toggled)
        root.addWidget(self.toggle)

        self.body = QWidget(self)
        form = QFormLayout(self.body)
        form.setContentsMargins(8, 4, 0, 4)
        form.setSpacing(6)

        self.certeza_combo = QComboBox()
        for value, label in CERTEZA_OPCIONES:
            self.certeza_combo.addItem(label, value)
        self.certeza_combo.setToolTip(
            "Hasta qué punto das esto por cierto. «Confirmada» = lo respalda una fuente; "
            "«Dudosa» = lo pusiste con reservas."
        )
        self.certeza_combo.currentIndexChanged.connect(self._emit_changed)
        if con_certeza:
            form.addRow(QLabel("Certeza"), self.certeza_combo)

        self.precision_combo = QComboBox()
        for value, label in PRECISION_OPCIONES:
            self.precision_combo.addItem(label, value)
        self.precision_combo.setToolTip(
            "Cómo de firme es la fecha. El año sigue ordenando la cronología: esto solo "
            "dice si es exacto, aproximado, mítico o discutido."
        )
        self.precision_combo.currentIndexChanged.connect(self._emit_changed)

        self.world_date_edit = QLineEdit()
        self.world_date_edit.setPlaceholderText("h. 1334 · 3 de mayo del año del Cuervo…")
        self.world_date_edit.setToolTip("La fecha tal y como se dice en tu mundo (texto libre).")
        self.world_date_edit.textEdited.connect(self._emit_changed)

        self.period_edit = QLineEdit()
        self.period_edit.setPlaceholderText("Reinado de Alfonso XI · Tercera Edad…")
        self.period_edit.setToolTip("Periodo o época en la que cae, si no hay fecha concreta.")
        self.period_edit.textEdited.connect(self._emit_changed)

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Fecha discutida: Ayala no la data…")
        self.notes_edit.setToolTip("Tu nota al pie sobre la fecha.")
        self.notes_edit.textEdited.connect(self._emit_changed)

        self.sources_edit = QLineEdit()
        self.sources_edit.setPlaceholderText("Crónica de Ayala; Zúñiga")
        self.sources_edit.setToolTip(
            "Fuentes que no se ponen de acuerdo, separadas por «;». Se conservan tal cual."
        )
        self.sources_edit.textEdited.connect(self._emit_changed)

        if con_datacion:
            form.addRow(QLabel("Precisión de la fecha"), self.precision_combo)
            form.addRow(QLabel("Fecha del mundo"), self.world_date_edit)
            form.addRow(QLabel("Periodo"), self.period_edit)
            form.addRow(QLabel("Nota sobre la fecha"), self.notes_edit)
            form.addRow(QLabel("Fuentes que se contradicen"), self.sources_edit)

        self.form = form
        root.addWidget(self.body)
        self.body.setVisible(self.toggle.isChecked())
        self._sync_arrow()

    def add_row(self, etiqueta: str, widget: QWidget) -> None:
        """Añade una fila propia del panel que la usa (p. ej. «Fuentes» en la Ficha).

        Vive DENTRO del plegable: el rigor entero es una sola cosa que se abre o
        se ignora, no cinco añadidos sueltos por la ficha.
        """
        self.form.addRow(QLabel(etiqueta), widget)

    # ── plegado ──────────────────────────────────────────────────────────

    def _sync_arrow(self) -> None:
        marca = "▾ " if self.toggle.isChecked() else "▸ "
        texto = self.toggle.text().lstrip("▾▸ ")
        self.toggle.setText(marca + texto)

    def _on_toggled(self, checked: bool) -> None:
        self.body.setVisible(bool(checked))
        self._sync_arrow()

    def is_expanded(self) -> bool:
        return bool(self.toggle.isChecked())

    def set_expanded(self, expandida: bool) -> None:
        self.toggle.setChecked(bool(expandida))

    def _emit_changed(self, *_args) -> None:
        if not self._loading:
            self.changed.emit()

    # ── carga ────────────────────────────────────────────────────────────

    def load(self, *, certeza: Any = None, temporalidad: Any = None) -> None:
        """Vuelca en el formulario la certeza y el punto temporal (sin emitir cambios)."""
        self._loading = True
        try:
            if certeza is not None:
                self._set_combo(self.certeza_combo, _enum_value(certeza, "probable"))
            ev = temporalidad
            self._set_combo(
                self.precision_combo,
                _enum_value(getattr(ev, "precision", None), TemporalPrecision.UNKNOWN.value),
            )
            self.world_date_edit.setText(str(getattr(ev, "world_date", "") or ""))
            self.period_edit.setText(str(getattr(ev, "period", "") or ""))
            self.notes_edit.setText(str(getattr(ev, "notes", "") or ""))
            fuentes = list(getattr(ev, "contradictory_sources", []) or [])
            self.sources_edit.setText("; ".join(str(f) for f in fuentes))
        finally:
            self._loading = False

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    # ── lectura ──────────────────────────────────────────────────────────

    def certeza(self) -> str:
        return str(self.certeza_combo.currentData() or CertaintyLevel.PROBABLE.value)

    def precision(self) -> str:
        return str(self.precision_combo.currentData() or TemporalPrecision.UNKNOWN.value)

    def fuentes_contradictorias(self) -> list[str]:
        crudo = self.sources_edit.text()
        return [parte.strip() for parte in crudo.split(";") if parte.strip()]

    def apply_to_temporality(self, base: Any = None) -> dict[str, Any]:
        """Devuelve el dict de ``EventTemporality`` con lo descriptivo puesto.

        Parte de ``base`` (un ``EventTemporality`` existente o su dict) para **no
        perder el año** ni nada que no toque esta sección: aquí solo se escribe la
        capa descriptiva.
        """
        if isinstance(base, dict):
            datos = dict(base)
        elif base is not None:
            datos = base.to_dict()
        else:
            datos = EventTemporality().to_dict()
        datos["precision"] = self.precision()
        datos["world_date"] = self.world_date_edit.text().strip() or None
        datos["period"] = self.period_edit.text().strip() or None
        datos["notes"] = self.notes_edit.text().strip()
        datos["contradictory_sources"] = self.fuentes_contradictorias()
        return datos


__all__ = ["RigorSection", "CERTEZA_OPCIONES", "PRECISION_OPCIONES"]
