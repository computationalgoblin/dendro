"""Panel de configuración creativa canónica (PA04).

5 pestañas que reflejan las 5 secciones de ``CreativeProjectConfig``:
Identidad, Dirección, Motor, Estilo y Reglas. Sustituye al panel de 10
pestañas anterior (que mezclaba IA, memoria, ramas e importación sobre un
modelo de configuración ya retirado).

El **idioma** del proyecto no vive en ``creative_config``: se edita aquí pero se
escribe en ``project.primary_language``. La IA nunca escribe canon: este panel
solo persiste configuración del proyecto.

Los desplegables categóricos usan los tokens canónicos de
[creative_config.py]; muestran una etiqueta legible y guardan el token en
``currentData``. Género/formato/público son combos editables (texto libre).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.field_help import labeled_row
from packages.domain.creative_config import (
    AGENCIA_OPCIONES,
    AMBIGUEDAD_OPCIONES,
    CAMBIO_PERSONAJE_OPCIONES,
    CAUSALIDAD_OPCIONES,
    DENSIDAD_OPCIONES,
    ESCALADA_OPCIONES,
    ESTADO_OPCIONES,
    EXPOSICION_OPCIONES,
    FUENTE_CONFLICTO_OPCIONES,
    GRADO_ESPECULATIVO_OPCIONES,
    MECANISMO_OPCIONES,
    ORIGINALIDAD_OPCIONES,
    REALISMO_OPCIONES,
)

# ---------------------------------------------------------------------------
# Sugerencias para combos de texto libre (no son tokens cerrados)
# ---------------------------------------------------------------------------

GENERO_SUGERENCIAS = [
    "fantasía", "ciencia ficción", "terror", "noir", "realismo mágico",
    "thriller", "drama", "misterio", "histórico", "weird fiction", "distopía",
]

FORMATO_SUGERENCIAS = [
    "novela", "campaña de rol", "videojuego", "mundo abierto", "antología",
    "serie", "relato", "cómic",
]

PUBLICO_SUGERENCIAS = [
    "adulto", "juvenil", "todos", "jugadores de rol", "lectores de fantasía oscura",
]


# ---------------------------------------------------------------------------
# Helpers de widgets reutilizables
# ---------------------------------------------------------------------------

def _make_textarea(text: str = "", max_h: int = 80) -> QTextEdit:
    """QTextEdit de altura limitada."""
    te = QTextEdit()
    te.setPlainText(text)
    te.setMaximumHeight(max_h)
    te.setPlaceholderText("…")
    return te


def _legible(token: str) -> str:
    """Etiqueta legible para un token (capitaliza, reemplaza `_` por espacio)."""
    return token.replace("_", " ").capitalize()


def _make_combo_keyed(opciones: list[str], current: str = "") -> QComboBox:
    """Combo de tokens cerrados: muestra etiqueta legible, guarda token en userData.

    Incluye una opción vacía inicial ("—") para "sin definir".
    """
    cb = QComboBox()
    cb.addItem("—", "")
    for token in opciones:
        cb.addItem(_legible(token), token)
    idx = cb.findData(current)
    cb.setCurrentIndex(idx if idx >= 0 else 0)
    return cb


def _make_combo_editable(sugerencias: list[str], current: str = "") -> QComboBox:
    """Combo editable (texto libre permitido) con sugerencias."""
    cb = QComboBox()
    cb.setEditable(True)
    cb.addItem("")
    cb.addItems(sugerencias)
    cb.setCurrentText(current or "")
    return cb


class TagInput(QWidget):
    """Entrada de tags: campo + botón añadir + lista de tags eliminables."""

    def __init__(self, tags: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.tags: list[str] = list(tags or [])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setPlaceholderText("Añadir…")
        self.field.returnPressed.connect(self._add_tag)
        row.addWidget(self.field)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_tag)
        row.addWidget(add_btn)
        layout.addLayout(row)

        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(100)
        self.tag_list.itemDoubleClicked.connect(self._remove_tag)
        layout.addWidget(self.tag_list)

        self._refresh_list()

    def _add_tag(self):
        text = self.field.text().strip()
        if text and text not in self.tags:
            self.tags.append(text)
            self._refresh_list()
        self.field.clear()

    def _refresh_list(self):
        self.tag_list.clear()
        for t in self.tags:
            item = QListWidgetItem(t)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.tag_list.addItem(item)

    def _remove_tag(self, item):
        if item.text() in self.tags:
            self.tags.remove(item.text())
        self._refresh_list()

    def value(self) -> list[str]:
        return list(self.tags)


class ListEditor(QWidget):
    """Lista de strings editable con añadir/quitar."""

    def __init__(self, items: list[str] | None = None, placeholder: str = "Añadir…", parent=None):
        super().__init__(parent)
        self.items: list[str] = [i for i in (items or []) if i]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setPlaceholderText(placeholder)
        self.field.returnPressed.connect(self._add_item)
        row.addWidget(self.field)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_item)
        row.addWidget(add_btn)

        del_btn = QPushButton("−")
        del_btn.setFixedWidth(28)
        del_btn.clicked.connect(self._del_selected)
        row.addWidget(del_btn)
        layout.addLayout(row)

        self.lw = QListWidget()
        self.lw.setMaximumHeight(120)
        layout.addWidget(self.lw)
        self._refresh()

    def _add_item(self):
        text = self.field.text().strip()
        if text:
            self.items.append(text)
            self._refresh()
        self.field.clear()

    def _del_selected(self):
        for item in self.lw.selectedItems():
            if item.text() in self.items:
                self.items.remove(item.text())
        self._refresh()

    def _refresh(self):
        self.lw.clear()
        for i in self.items:
            self.lw.addItem(i)

    def value(self) -> list[str]:
        return [i for i in self.items if i]


# ---------------------------------------------------------------------------
# Panel principal
# ---------------------------------------------------------------------------

class CreativeConfigPanel(QTabWidget):
    """Panel de configuración creativa (PA04): 5 pestañas tipadas."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self._fields: dict = {}  # clave → widget para collect()

        self.setDocumentMode(True)

        self._build_tab_identidad()
        self._build_tab_direccion()
        self._build_tab_motor()
        self._build_tab_estilo()
        self._build_tab_reglas()

    # ── chrome ──────────────────────────────────────────────────────

    def _scroll(self, widget: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(widget)
        return sa

    def _form_tab(self) -> tuple[QWidget, QFormLayout]:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)
        # Los campos crecen hasta ocupar todo el ancho; las etiquetas largas
        # envuelven sobre su campo en lugar de desbordar a la derecha.
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        return page, form

    def _add(self, form: QFormLayout, label: str, key: str, widget: QWidget):
        """Registra el widget bajo ``key`` y lo añade con su etiqueta + ayuda (ⓘ).

        La clave de campo coincide con la clave del catálogo de ayuda ``FIELD_HELP``.
        """
        self._fields[key] = widget
        form.addRow(labeled_row(label, key), widget)

    # ── Pestaña 1: Identidad ────────────────────────────────────────

    def _build_tab_identidad(self):
        page, form = self._form_tab()
        i = self.project.creative_config.identidad

        self._add(form, "Premisa", "premisa", _make_textarea(i.premisa, 70))
        self._add(form, "Resumen corto", "resumen_corto", _make_textarea(i.resumen_corto, 90))
        self._add(form, "Género principal", "genero_principal",
                  _make_combo_editable(GENERO_SUGERENCIAS, i.genero_principal))
        self._add(form, "Subgéneros", "subgeneros", TagInput(i.subgeneros))
        self._add(form, "Formato", "formato", _make_combo_editable(FORMATO_SUGERENCIAS, i.formato))
        self._add(form, "Público", "publico", _make_combo_editable(PUBLICO_SUGERENCIAS, i.publico))
        self._add(form, "Idioma", "idioma", QLineEdit(self.project.primary_language))
        self._add(form, "Estado", "estado", _make_combo_keyed(ESTADO_OPCIONES, i.estado))

        self.addTab(self._scroll(page), "Identidad")

    # ── Pestaña 2: Dirección ────────────────────────────────────────

    def _build_tab_direccion(self):
        page, form = self._form_tab()
        d = self.project.creative_config.direccion

        self._add(form, "Promesa", "promesa", _make_textarea(d.promesa, 70))
        self._add(form, "Pregunta dramática", "pregunta_dramatica",
                  _make_textarea(d.pregunta_dramatica, 70))
        self._add(form, "Temas", "temas", TagInput(d.temas))
        self._add(form, "Emociones", "emociones", TagInput(d.emociones))
        self._add(form, "Sensación final", "sensacion_final", _make_textarea(d.sensacion_final, 70))
        self._add(form, "Originalidad", "originalidad",
                  _make_combo_keyed(ORIGINALIDAD_OPCIONES, d.originalidad))
        self._add(form, "Ambigüedad", "ambiguedad",
                  _make_combo_keyed(AMBIGUEDAD_OPCIONES, d.ambiguedad))
        self._add(form, "Tipo de impacto", "tipo_impacto", TagInput(d.tipo_impacto))

        self.addTab(self._scroll(page), "Dirección")

    # ── Pestaña 3: Motor ────────────────────────────────────────────

    def _build_tab_motor(self):
        page, form = self._form_tab()
        m = self.project.creative_config.motor

        self._add(form, "Fuente de conflicto", "fuente_conflicto",
                  _make_combo_keyed(FUENTE_CONFLICTO_OPCIONES, m.fuente_conflicto))
        self._add(form, "Mecanismo", "mecanismo",
                  _make_combo_keyed(MECANISMO_OPCIONES, m.mecanismo))
        self._add(form, "Causalidad", "causalidad",
                  _make_combo_keyed(CAUSALIDAD_OPCIONES, m.causalidad))
        self._add(form, "Agencia", "agencia",
                  _make_combo_keyed(AGENCIA_OPCIONES, m.agencia))
        self._add(form, "Escalada", "escalada",
                  _make_combo_keyed(ESCALADA_OPCIONES, m.escalada))
        self._add(form, "Cambio de personaje", "cambio_personaje",
                  _make_combo_keyed(CAMBIO_PERSONAJE_OPCIONES, m.cambio_personaje))

        self.addTab(self._scroll(page), "Motor")

    # ── Pestaña 4: Estilo ───────────────────────────────────────────

    def _build_tab_estilo(self):
        page, form = self._form_tab()
        e = self.project.creative_config.estilo

        self._add(form, "Tono", "tono", QLineEdit(e.tono))
        self._add(form, "Realismo", "realismo",
                  _make_combo_keyed(REALISMO_OPCIONES, e.realismo))
        self._add(form, "Grado especulativo", "grado_especulativo",
                  _make_combo_keyed(GRADO_ESPECULATIVO_OPCIONES, e.grado_especulativo))
        self._add(form, "Estilo narrativo", "estilo_narrativo", QLineEdit(e.estilo_narrativo))
        self._add(form, "Densidad", "densidad",
                  _make_combo_keyed(DENSIDAD_OPCIONES, e.densidad))
        self._add(form, "Exposición", "exposicion",
                  _make_combo_keyed(EXPOSICION_OPCIONES, e.exposicion))

        self.addTab(self._scroll(page), "Estilo")

    # ── Pestaña 5: Reglas ───────────────────────────────────────────

    def _build_tab_reglas(self):
        page, form = self._form_tab()
        r = self.project.creative_config.reglas

        self._add(form, "Reglas de canon", "reglas_canon",
                  ListEditor(r.reglas_canon, placeholder="Añadir regla de canon…"))
        self._add(form, "Evitar", "evitar",
                  ListEditor(r.evitar, placeholder="Añadir algo a evitar…"))

        self.addTab(self._scroll(page), "Reglas")

    # ── Recogida de valores ─────────────────────────────────────────

    def collect(self) -> dict:
        """Recoge los valores editados en un dict anidado por sección."""
        def _text(w) -> str:
            if isinstance(w, QTextEdit):
                return w.toPlainText().strip()
            if isinstance(w, QLineEdit):
                return w.text().strip()
            return ""

        def _combo(w: QComboBox) -> str:
            # Combos cerrados guardan token en userData; editables, texto libre.
            if w.isEditable():
                return w.currentText().strip()
            data = w.currentData()
            return data if data is not None else w.currentText().strip()

        f = self._fields
        return {
            "idioma": _text(f["idioma"]),
            "identidad": {
                "premisa": _text(f["premisa"]),
                "resumen_corto": _text(f["resumen_corto"]),
                "genero_principal": _combo(f["genero_principal"]),
                "subgeneros": f["subgeneros"].value(),
                "formato": _combo(f["formato"]),
                "publico": _combo(f["publico"]),
                "estado": _combo(f["estado"]),
            },
            "direccion": {
                "promesa": _text(f["promesa"]),
                "pregunta_dramatica": _text(f["pregunta_dramatica"]),
                "temas": f["temas"].value(),
                "emociones": f["emociones"].value(),
                "sensacion_final": _text(f["sensacion_final"]),
                "originalidad": _combo(f["originalidad"]),
                "ambiguedad": _combo(f["ambiguedad"]),
                "tipo_impacto": f["tipo_impacto"].value(),
            },
            "motor": {
                "fuente_conflicto": _combo(f["fuente_conflicto"]),
                "mecanismo": _combo(f["mecanismo"]),
                "causalidad": _combo(f["causalidad"]),
                "agencia": _combo(f["agencia"]),
                "escalada": _combo(f["escalada"]),
                "cambio_personaje": _combo(f["cambio_personaje"]),
            },
            "estilo": {
                "tono": _text(f["tono"]),
                "realismo": _combo(f["realismo"]),
                "grado_especulativo": _combo(f["grado_especulativo"]),
                "estilo_narrativo": _text(f["estilo_narrativo"]),
                "densidad": _combo(f["densidad"]),
                "exposicion": _combo(f["exposicion"]),
            },
            "reglas": {
                "reglas_canon": f["reglas_canon"].value(),
                "evitar": f["evitar"].value(),
            },
        }

    def apply_to_project(self, project):
        """Vuelca los valores recogidos a ``project.creative_config`` + idioma."""
        data = self.collect()
        cc = project.creative_config

        for section_name in ("identidad", "direccion", "motor", "estilo", "reglas"):
            section = getattr(cc, section_name)
            for key, value in data[section_name].items():
                setattr(section, key, value)

        project.primary_language = data["idioma"] or project.primary_language
        # Worldbuilding por capas causales siempre activo (PA02).
        project.worldbuilding_active = True
