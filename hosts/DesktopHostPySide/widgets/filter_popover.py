"""Popover de filtros visuales del Mapa (BETA2-UI2-10).

Sustituye al panel ``CreationFilterPanel`` del drawer: los filtros viven ahora
en un popover compacto anclado al embudo del pill temporal. Efímeros — nunca
escriben proyecto ni canon. El popover solo LEE el proyecto (provider) y
notifica por callbacks; la aplicación real del filtro la hace el workspace
(``apply_creation_filter``), y el CRUD de anillos/eras quedó relegado a los
menús contextuales del Mapa y la Cronología.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    INK_STRONG,
    enum_human,
)
from hosts.DesktopHostPySide.widgets.foco.foco_popover import Popover
from hosts.DesktopHostPySide.widgets.graph_canvas import VisualFilterState


class FilterPopover(Popover):
    """Filtros visuales compactos (tipo, relación, rama, anillo, estado).

    ``on_apply(state)`` en cada cambio; ``on_clear()`` al limpiar. Se
    construye fresco en cada apertura (combos siempre al día con el proyecto)
    y restaura las selecciones desde ``initial_state``.

    BETA2-FOCO-33: con ``mode="chrono"`` solo se muestran los filtros aplicables a
    una línea de tiempo — tipo de entidad, anillo, estado canon y «Ocultar
    secretas» —; los combos de relación/rama y «Mostrar relaciones» se ocultan (la
    cronología no tiene aristas). El estado se sigue devolviendo como
    ``VisualFilterState``; «Ocultar secretas» se codifica en ``visibility_states``.
    """

    def __init__(
        self,
        *,
        project_provider: Callable[[], Any],
        initial_state: VisualFilterState | None = None,
        on_apply: Callable[[VisualFilterState], None],
        on_clear: Callable[[], None],
        mode: str = "map",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_provider = project_provider
        self._on_apply = on_apply
        self._on_clear = on_clear
        self._mode = mode
        chrono = mode == "chrono"

        title = QLabel("Filtros de la cronología" if chrono else "Filtros visuales")
        title.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 12px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        self._layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        self.entity_type = QComboBox()
        self.relation_type = QComboBox()
        self.relation_family = QComboBox()
        self.tree = QComboBox()
        self.layer = QComboBox()
        self.canon = QComboBox()
        self.show_relations = QCheckBox("Mostrar relaciones")
        self.show_relations.setChecked(True)
        self.hide_secret = QCheckBox("Ocultar secretas")
        for combo in self._combos():
            combo.addItem("- Cualquiera -", "")
        for label, value in (
            ("Pertenencia estructural", "estructural"),
            ("Narrativa", "narrativa"),
            ("Causal", "causal"),
            ("Coherencia/incidencias", "coherencia"),
        ):
            self.relation_family.addItem(label, value)
        self._populate()
        form.addRow("Tipo", self.entity_type)
        form.addRow("Anillo", self.layer)
        if not chrono:
            # BETA2-FOCO-38: la Cronología solo filtra por Tipo y Anillo; los
            # combos de relación/rama, Estado canon y «Ocultar secretas» se retiraron.
            form.addRow("Tipo relación", self.relation_type)
            form.addRow("Familia relación", self.relation_family)
            form.addRow("Rama", self.tree)
            form.addRow("Estado", self.canon)
            form.addRow("Relaciones", self.show_relations)
            # BETA-AUDIT-02: la casilla se construía, se conectaba y se leía, pero
            # nunca se añadía a ningún layout: era un widget huérfano. Ahora que la
            # ficha permite marcar entidades reservadas, el filtro sirve de algo.
            self.hide_secret.setToolTip(
                "Oculta del Mapa las entidades reservadas (secretas, privadas u ocultas). "
                "Útil para enseñar la pantalla sin destripar nada."
            )
            form.addRow("Privacidad", self.hide_secret)
        self._layout.addLayout(form)

        if initial_state is not None:
            self._restore(initial_state)

        for combo in self._combos():
            combo.currentIndexChanged.connect(self._apply)
        self.show_relations.toggled.connect(self._apply)
        self.hide_secret.toggled.connect(self._apply)

        row = QHBoxLayout()
        clear = QPushButton("Limpiar filtros")
        clear.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {GOLD}; "
            "font-weight: 600; padding: 2px 4px; }"
        )
        row.addStretch(1)
        row.addWidget(clear)
        clear.clicked.connect(self._clear)
        self._layout.addLayout(row)

    def _combos(self) -> tuple[QComboBox, ...]:
        return (
            self.entity_type,
            self.relation_type,
            self.relation_family,
            self.tree,
            self.layer,
            self.canon,
        )

    # — poblar desde el proyecto (solo lectura) —

    def _add_unique(self, combo: QComboBox, label: str, value: str, seen: set[str]) -> None:
        value = str(value or "").lower()
        if not value or value in seen:
            return
        seen.add(value)
        combo.addItem(label, value)

    def _populate(self) -> None:
        project = self._project_provider()
        entities = list(getattr(project, "entities", []) or []) if project is not None else []
        relations = list(getattr(project, "relations", []) or []) if project is not None else []
        seen_entity: set[str] = set()
        seen_canon: set[str] = set()
        if self._mode == "chrono":
            # BETA2-FOCO-38: el Tipo de la Cronología lista los tipos OFRECIDOS en
            # creación (aunque no estén presentes) ∪ los que sí existen en el
            # proyecto (p. ej. Contenedor). Los presentes se añaden en el bucle.
            from packages.domain.entity_taxonomy import OFFERED_ENTITY_TYPES

            for etype in OFFERED_ENTITY_TYPES:
                value = str(getattr(etype, "value", etype) or "")
                self._add_unique(self.entity_type, enum_human(value), value, seen_entity)
        for entity in entities:
            kind = str(
                getattr(
                    getattr(entity, "entity_type", None),
                    "value",
                    getattr(entity, "entity_type", ""),
                )
                or ""
            )
            self._add_unique(self.entity_type, enum_human(kind), kind, seen_entity)
            canon = str(
                getattr(
                    getattr(entity, "canon_state", None),
                    "value",
                    getattr(entity, "canon_state", ""),
                )
                or ""
            )
            self._add_unique(self.canon, enum_human(canon), canon, seen_canon)
            if kind.lower() == "contenedor":
                self.tree.addItem(
                    str(getattr(entity, "name", "Rama")), str(getattr(entity, "id", ""))
                )
        seen_rel: set[str] = set()
        for relation in relations:
            kind = str(
                getattr(
                    getattr(relation, "relation_type", None),
                    "value",
                    getattr(relation, "relation_type", ""),
                )
                or ""
            )
            self._add_unique(self.relation_type, enum_human(kind), kind, seen_rel)
        for layer in list(getattr(project, "world_layers", []) or []):
            if getattr(layer, "is_visible", True):
                self.layer.addItem(
                    str(getattr(layer, "name", "Anillo")), str(getattr(layer, "id", ""))
                )

    def _restore(self, state: VisualFilterState) -> None:
        """Restaura las selecciones del estado activo (findData; -1 = Cualquiera)."""

        def pick(combo: QComboBox, values: tuple[str, ...]) -> None:
            value = values[0] if values else ""
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)

        pick(self.entity_type, state.entity_types)
        pick(self.relation_type, state.relation_types)
        pick(self.relation_family, state.relation_families)
        pick(self.tree, (state.tree_id,) if state.tree_id else ())
        pick(self.layer, state.layer_ids)
        pick(self.canon, state.canon_states)
        self.show_relations.setChecked(bool(state.show_relations))
        self.hide_secret.setChecked("secreto" in state.visibility_states)

    # — estado y callbacks —

    def _state(self) -> VisualFilterState:
        def one(combo: QComboBox) -> tuple[str, ...]:
            value = str(combo.currentData() or "")
            return (value,) if value else ()

        # BETA2-FOCO-33: en modo cronología «Ocultar secretas» viaja en
        # ``visibility_states`` (el workspace lo traduce a ChronoScope.hide_secret).
        visibility = ("secreto",) if self.hide_secret.isChecked() else ()
        return VisualFilterState(
            entity_types=one(self.entity_type),
            relation_types=one(self.relation_type),
            relation_families=one(self.relation_family),
            tree_id=str(self.tree.currentData() or ""),
            layer_ids=one(self.layer),
            canon_states=one(self.canon),
            visibility_states=visibility,
            show_relations=bool(self.show_relations.isChecked()),
        )

    def _apply(self) -> None:
        self._on_apply(self._state())

    def _clear(self) -> None:
        for combo in self._combos():
            block = combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(block)
        block = self.show_relations.blockSignals(True)
        self.show_relations.setChecked(True)
        self.show_relations.blockSignals(block)
        block = self.hide_secret.blockSignals(True)
        self.hide_secret.setChecked(False)
        self.hide_secret.blockSignals(block)
        self._on_clear()
