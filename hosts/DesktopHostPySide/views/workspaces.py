"""Product workspaces for the B27.5 Desktop UX shell.

These wrappers reorganize existing connected views into three product spaces
without deleting functionality. Technical CRUD screens are kept behind advanced
mode while normal mode starts from clean cards/overviews.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.ai_context_controller import AIContextController
from hosts.DesktopHostPySide.widgets.entity_card import EntityCard
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget, GraphSearchResult, VisualFilterState, relation_family
from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
from hosts.DesktopHostPySide.widgets.coherence_panel import CoherencePanel
from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    Card,
    EmptyState,
    ICON_GLYPHS,
    SectionHeader,
    enum_human,
    human_ref,
    make_scroll_area,
)
from packages.domain.result import Error
from packages.domain.world_layer import default_world_layers
from packages.application.ai_jobs import AIJobService, AIJobStatus, classify_ai_job_intent


class _SimpleFormPanel(QWidget):
    """Small drawer form used by normal-mode creation paths."""

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 18)
        self.layout.setSpacing(12)
        self.layout.addWidget(SectionHeader(title, subtitle))

    def add_status(self) -> QLabel:
        label = QLabel("")
        label.setObjectName("mutedLabel")
        label.setWordWrap(True)
        self.layout.addWidget(label)
        return label


class EntityQuickCreatePanel(_SimpleFormPanel):
    def __init__(self, controller, on_created):
        super().__init__("Nueva entidad", "Crea una pieza narrativa sin ver campos técnicos.")
        self.controller = controller
        self.on_created = on_created
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre visible")
        self.kind = QComboBox()
        self.kind.addItems(["personaje", "localizacion", "objeto", "evento", "faccion", "secreto", "pista", "trama", "nota"])
        self.description = QTextEdit()
        self.description.setPlaceholderText("Descripción breve")
        self.description.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Tipo", self.kind)
        form.addRow("Descripción", self.description)
        self.layout.addLayout(form)
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Crear entidad")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        result = self.controller.create({
            "name": self.name.text().strip(),
            "entity_type": self.kind.currentText(),
            "brief_description": self.description.toPlainText().strip(),
        })
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        entity = result.value
        self.status.setText(f"Entidad creada: {getattr(entity, 'name', 'sin nombre')}")
        self.on_created()


class SourceQuickCreatePanel(_SimpleFormPanel):
    def __init__(self, controller, on_created):
        super().__init__("Nueva fuente", "Registra una referencia legible para trazabilidad narrativa.")
        self.controller = controller
        self.on_created = on_created
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre de la referencia")
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("URL, libro, nota o archivo")
        self.fragment = QTextEdit()
        self.fragment.setPlaceholderText("Fragmento o contexto")
        self.fragment.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Referencia", self.reference)
        form.addRow("Fragmento", self.fragment)
        self.layout.addLayout(form)
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Crear fuente")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        result = self.controller.create({
            "name": self.name.text().strip(),
            "reference": self.reference.text().strip(),
            "fragment": self.fragment.toPlainText().strip(),
            "source_type": "entrada_manual",
        })
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        source = result.value
        self.status.setText(f"Fuente creada: {getattr(source, 'name', 'sin nombre')}")
        self.on_created()


class LayerQuickCreatePanel(_SimpleFormPanel):
    def __init__(self, controller, on_created):
        super().__init__("Nueva capa", "Organiza el worldbuilding como estratos visuales.")
        self.controller = controller
        self.on_created = on_created
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre de la capa")
        self.description = QTextEdit()
        self.description.setPlaceholderText("Qué representa esta capa")
        self.description.setMinimumHeight(90)
        form.addRow("Nombre", self.name)
        form.addRow("Descripción", self.description)
        self.layout.addLayout(form)
        self.status = self.add_status()
        row = QHBoxLayout()
        save = QPushButton("Crear capa")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(save)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def _save(self):
        result = self.controller.create({
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
        })
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        layer = result.value
        self.status.setText(f"Capa creada: {getattr(layer, 'name', 'sin nombre')}")
        self.on_created()


class CandidateReviewPanel(_SimpleFormPanel):
    def __init__(self, controller, on_changed):
        super().__init__("Sugerencias", "Revisa candidatos como tarjetas, sin tabla técnica.")
        self.controller = controller
        self.on_changed = on_changed
        self.cards = QWidget()
        self.cards_layout = QVBoxLayout(self.cards)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.layout.addWidget(make_scroll_area(self.cards), 1)
        self.refresh()

    def refresh(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        candidates = self.controller.list_all()
        if not candidates:
            self.cards_layout.addWidget(EmptyState("Sin sugerencias", "Cuando la IA proponga candidatos aparecerán aquí."))
            return
        for candidate in candidates:
            title = getattr(candidate, "title", "") or getattr(candidate, "name", "Sugerencia")
            desc = getattr(candidate, "description", "") or getattr(candidate, "summary", "") or "Revisión pendiente"
            card = Card(title, desc)
            row = QHBoxLayout()
            accept = QPushButton("Aceptar")
            reject = QPushButton("Rechazar")
            accept.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._accept(cid))
            reject.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._reject(cid))
            row.addStretch(1)
            row.addWidget(accept)
            row.addWidget(reject)
            card.layout.addLayout(row)
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

    def _accept(self, candidate_id: str):
        result = self.controller.accept(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()

    def _reject(self, candidate_id: str):
        result = self.controller.reject(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()


class SuggestionInboxPanel(_SimpleFormPanel):
    """Unified suggestion inbox with type, origin, summary and focus action."""

    def __init__(self, controller, on_changed, on_focus=None):
        super().__init__("Bandeja de sugerencias", "Candidatos IA generados por coherencia, worldbuilding e importación.")
        self.controller = controller
        self.on_changed = on_changed
        self.on_focus = on_focus
        self.cards = QWidget()
        self.cards_layout = QVBoxLayout(self.cards)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.layout.addWidget(make_scroll_area(self.cards), 1)
        self.refresh()

    def refresh(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        candidates = self.controller.list_all()
        if not candidates:
            self.cards_layout.addWidget(EmptyState("Sin sugerencias", "Cuando la IA proponga candidatos aparecerán aquí."))
            return
        for candidate in candidates:
            title = getattr(candidate, "title", "") or getattr(candidate, "name", "Sugerencia")
            cand_type = str(getattr(getattr(candidate, "candidate_type", ""), "value", ""))
            origin = getattr(candidate, "source", "") or ""
            state = str(getattr(getattr(candidate, "state", ""), "value", ""))
            confidence = getattr(candidate, "confidence", 0)
            summary = getattr(candidate, "summary", "") or getattr(candidate, "description", "") or ""
            if not summary and cand_type:
                summary = f"Candidato de tipo {cand_type}"
            # Card subtitle
            subtitle_parts = []
            if cand_type:
                subtitle_parts.append(cand_type)
            if origin:
                subtitle_parts.append(origin)
            if state:
                subtitle_parts.append(state)
            if confidence:
                subtitle_parts.append(f"{confidence:.0%}")
            subtitle = " · ".join(subtitle_parts) if subtitle_parts else summary or "Pendiente de revisión"
            card = Card(title, subtitle)
            row = QHBoxLayout()
            focus_btn = QPushButton("Enfocar")
            focus_btn.setToolTip("Ir al elemento relacionado en el grafo")
            focus_btn.setEnabled(bool(self.on_focus))
            focus_btn.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._focus(cid))
            accept = QPushButton("Aceptar")
            reject = QPushButton("Descartar")
            accept.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._accept(cid))
            reject.clicked.connect(lambda _, cid=getattr(candidate, "id", ""): self._reject(cid))
            row.addStretch(1)
            row.addWidget(focus_btn)
            row.addWidget(accept)
            row.addWidget(reject)
            card.layout.addLayout(row)
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

    def _focus(self, candidate_id: str):
        if self.on_focus is None:
            return
        candidates = self.controller.list_all()
        for c in candidates:
            if getattr(c, "id", "") == candidate_id:
                proposed = getattr(c, "proposed_data", {}) or {}
                entity_id = proposed.get("entity_id") or proposed.get("source_id") or proposed.get("target_id") or ""
                if entity_id:
                    self.on_focus(entity_id)
                else:
                    from hosts.DesktopHostPySide.app_context import AppContext
                    pass  # no entity to focus
                break

    def _accept(self, candidate_id: str):
        result = self.controller.accept(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()

    def _reject(self, candidate_id: str):
        result = self.controller.reject(candidate_id)
        if isinstance(result, Error):
            self.layout.addWidget(QLabel(result.error))
            return
        self.on_changed()
        self.refresh()


class NarrativeWorkbench(QWidget):
    """Normal-mode clean entry points for creation work."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__()
        self.workspace = workspace
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(SectionHeader(
            "Taller narrativo",
            "Crea y organiza sin tablas técnicas; los detalles avanzados quedan detrás del modo avanzado."
        ))
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)
        actions = [
            ("Entidad", "Crear personaje, lugar, objeto o concepto.", "Nueva entidad", self.workspace.open_entity_create),
            ("Relaciones", "Conecta nodos visualmente desde el grafo.", "Ir al grafo", self.workspace.open_graph),
            ("Sugerencias", "Revisa candidatos como tarjetas.", "Revisar", self.workspace.open_candidates_clean),
            ("Fuentes", "Guarda referencias legibles.", "Nueva fuente", self.workspace.open_source_create),
            ("Capas", "Ordena el worldbuilding por estratos.", "Nueva capa", self.workspace.open_layer_create),
        ]
        self._cards: dict[str, tuple[QWidget, int, int]] = {}
        for idx, (title, desc, button, callback) in enumerate(actions):
            card = Card(title, desc)
            btn = QPushButton(button)
            if idx == 0:
                btn.setObjectName("primaryButton")
            btn.clicked.connect(callback)
            card.layout.addWidget(btn)
            row, col = idx // 2, idx % 2
            self._cards[title] = (card, row, col)
            grid.addWidget(card, row, col)
        layout.addWidget(grid_host)

        # Store layer card data for worldbuilding visibility control
        self._layer_card_data = self._cards.get("Capas")

        # Worldbuilding layer chips section
        self._layer_section = QWidget()
        layer_section_layout = QVBoxLayout(self._layer_section)
        layer_section_layout.setContentsMargins(0, 8, 0, 0)
        layer_section_layout.setSpacing(6)

        layer_header = QLabel("Capas de worldbuilding")
        layer_header.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #7A733D; background: transparent; border: none;"
        )
        layer_section_layout.addWidget(layer_header)

        self._layer_chips_container = QWidget()
        self._chips_layout = QHBoxLayout(self._layer_chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(8)
        layer_section_layout.addWidget(self._layer_chips_container)

        self._layer_empty = QLabel("Worldbuilding activo. Aún no hay capas.")
        self._layer_empty.setStyleSheet(
            "font-size: 11px; color: #8C8A74; background: transparent; border: none; font-style: italic;"
        )
        layer_section_layout.addWidget(self._layer_empty)

        layout.addWidget(self._layer_section)
        self._layer_section.setVisible(False)  # hidden by default

        # Check worldbuilding on init
        project = self._get_active_project()
        if project:
            wb = getattr(project, "worldbuilding_active", False)
            self.set_worldbuilding_active(wb)
        else:
            self.set_worldbuilding_active(False)
        layout.addWidget(EmptyState(
            "Modo normal activo",
            "IDs, JSON, tablas técnicas y metadatos quedan en Avanzado. La funcionalidad sigue disponible con lenguaje narrativo."
        ))
        layout.addStretch(1)

    def _get_active_project(self):
        pc = getattr(self.workspace.ctx, "project_controller", None)
        if pc:
            return getattr(pc.ps, "active_project", None)
        return None

    def set_worldbuilding_active(self, active: bool):
        """Show/hide the Capas card based on worldbuilding status."""
        if self._layer_card_data:
            card, row, col = self._layer_card_data
            card.setVisible(active)
        self.refresh_layers()

    def refresh_layers(self):
        """Update layer chips based on current project layers."""
        project = self._get_active_project()
        if project is None or not getattr(project, "worldbuilding_active", False):
            self._layer_section.setVisible(False)
            return

        self._layer_section.setVisible(True)

        # Clear existing chips
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Get layers from controller
        layers = []
        if self.workspace.layer_controller:
            try:
                layers = self.workspace.layer_controller.list_all() or []
            except Exception:
                layers = []

        if not layers:
            self._layer_empty.setVisible(True)
            self._layer_chips_container.setVisible(False)
            return

        self._layer_empty.setVisible(False)
        self._layer_chips_container.setVisible(True)

        for layer in layers[:8]:  # max 8 chips
            name = getattr(layer, "name", getattr(layer, "title", "Capa"))
            chip = QLabel(f"  {name}  ")
            chip.setStyleSheet(
                "background: #E8E5D4; border: 1px solid #C9C5B1; border-radius: 10px; "
                "padding: 3px 10px; font-size: 11px; color: #6E705E; "
                "font-family: Georgia, 'Courier New', serif;"
            )
            self._chips_layout.addWidget(chip)
        self._chips_layout.addStretch(1)


class CreationSearchPanel(_SimpleFormPanel):
    """B37-T01 clean graph search panel inside the right drawer."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__("Buscar en Creación", "Encuentra nodos, árboles o relaciones sin tablas técnicas.")
        self.workspace = workspace
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, tipo, descripción, árbol, relación o capa")
        self.search.textChanged.connect(self._run_search)
        self.layout.addWidget(self.search)
        self.status = self.add_status()
        self.results_layout = QVBoxLayout()
        self.results_layout.setSpacing(6)
        self.layout.addLayout(self.results_layout)
        self.layout.addStretch(1)
        self._run_search("")

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _run_search(self, text: str):
        self._clear_results()
        query = (text or "").strip()
        if not query:
            self.status.setText("Escribe para buscar en el grafo actual.")
            return
        results = self.workspace.graph.search(query)
        if not results:
            self.status.setText("Sin resultados.")
            return
        self.status.setText(f"{len(results)} resultado(s). Selecciona uno para enfocarlo.")
        for result in results:
            self.results_layout.addWidget(self._result_button(result))

    def _result_button(self, result: GraphSearchResult) -> QPushButton:
        title, details, summary = result.display_lines()
        collapsed_hint = "\nDentro de árbol colapsado: se expandirá la ruta al enfocar." if result.is_inside_collapsed_tree else ""
        button = QPushButton(f"{title}\n{details}{collapsed_hint}\n{summary}".strip())
        button.setStyleSheet(
            "QPushButton { text-align: left; background: #F8F5EA; border: 1px solid #D8D2BF; "
            "border-radius: 10px; padding: 8px; color: #4F4D38; } "
            "QPushButton:hover { background: #FFFDF6; border-color: #AFA77A; }"
        )
        button.clicked.connect(lambda _=False, r=result: self._focus_result(r))
        return button

    def _focus_result(self, result: GraphSearchResult):
        ok = self.workspace.focus_search_result(result)
        if ok:
            self.status.setText(f"Enfocado: {result.title}")
        else:
            self.status.setText("No se pudo enfocar. Puede estar oculto por filtros activos; limpia filtros e inténtalo de nuevo.")


class CreationFilterPanel(_SimpleFormPanel):
    """B37-T02 visual filters. Ephemeral: never writes project/canon."""

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__("Filtros visuales", "Reduce la vista sin modificar el proyecto ni el canon.")
        self.workspace = workspace
        self.status = self.add_status()
        form = QFormLayout()
        self.entity_type = QComboBox()
        self.relation_type = QComboBox()
        self.relation_family = QComboBox()
        self.tree = QComboBox()
        self.layer = QComboBox()
        self.canon = QComboBox()
        self.visibility = QComboBox()
        self.show_relations = QCheckBox("Mostrar relaciones")
        self.show_relations.setChecked(True)
        for combo in (self.entity_type, self.relation_type, self.relation_family, self.tree, self.layer, self.canon, self.visibility):
            combo.addItem("— Cualquiera —", "")
        for label, value in (("Pertenencia estructural", "estructural"), ("Narrativa", "narrativa"), ("Causal", "causal"), ("Coherencia/incidencias", "coherencia")):
            self.relation_family.addItem(label, value)
        self._populate()
        form.addRow("Tipo entidad", self.entity_type)
        form.addRow("Tipo relación", self.relation_type)
        form.addRow("Familia relación", self.relation_family)
        form.addRow("Árbol", self.tree)
        if self._worldbuilding_active():
            form.addRow("Capa", self.layer)
        form.addRow("Estado", self.canon)
        form.addRow("Visibilidad", self.visibility)
        form.addRow("Relaciones", self.show_relations)
        self.layout.addLayout(form)
        for widget in (self.entity_type, self.relation_type, self.relation_family, self.tree, self.layer, self.canon, self.visibility):
            widget.currentIndexChanged.connect(self._apply)
        self.show_relations.toggled.connect(self._apply)
        row = QHBoxLayout()
        clear = QPushButton("Limpiar filtros")
        clear.clicked.connect(self._clear)
        row.addStretch(1)
        row.addWidget(clear)
        self.layout.addLayout(row)
        self.layout.addStretch(1)
        self._sync_status()

    def _worldbuilding_active(self) -> bool:
        project = self.workspace._get_active_project()
        return bool(getattr(project, "worldbuilding_active", False)) if project is not None else False

    def _add_unique(self, combo: QComboBox, label: str, value: str, seen: set[str]):
        value = str(value or "").lower()
        if not value or value in seen:
            return
        seen.add(value)
        combo.addItem(label, value)

    def _populate(self):
        project = self.workspace._get_active_project()
        entities = list(getattr(project, "entities", []) or []) if project is not None else []
        relations = list(getattr(project, "relations", []) or []) if project is not None else []
        seen_entity: set[str] = set()
        seen_canon: set[str] = set()
        seen_vis: set[str] = set()
        for entity in entities:
            kind = str(getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "")) or "")
            self._add_unique(self.entity_type, enum_human(kind), kind, seen_entity)
            canon = str(getattr(getattr(entity, "canon_state", None), "value", getattr(entity, "canon_state", "")) or "")
            self._add_unique(self.canon, enum_human(canon), canon, seen_canon)
            visibility = str(getattr(getattr(entity, "visibility_state", None), "value", getattr(entity, "visibility_state", "")) or "")
            self._add_unique(self.visibility, enum_human(visibility), visibility, seen_vis)
            if kind.lower() == "contenedor":
                self.tree.addItem(str(getattr(entity, "name", "Árbol")), str(getattr(entity, "id", "")))
        seen_rel: set[str] = set()
        for relation in relations:
            kind = str(getattr(getattr(relation, "relation_type", None), "value", getattr(relation, "relation_type", "")) or "")
            self._add_unique(self.relation_type, enum_human(kind), kind, seen_rel)
        if self._worldbuilding_active():
            for layer in list(getattr(project, "world_layers", []) or []):
                if getattr(layer, "is_visible", True):
                    self.layer.addItem(str(getattr(layer, "name", "Capa")), str(getattr(layer, "id", "")))

    def _state(self) -> VisualFilterState:
        def one(combo: QComboBox) -> tuple[str, ...]:
            value = str(combo.currentData() or "")
            return (value,) if value else ()
        return VisualFilterState(
            entity_types=one(self.entity_type),
            relation_types=one(self.relation_type),
            relation_families=one(self.relation_family),
            tree_id=str(self.tree.currentData() or ""),
            layer_ids=one(self.layer) if self._worldbuilding_active() else (),
            canon_states=one(self.canon),
            visibility_states=one(self.visibility),
            show_relations=bool(self.show_relations.isChecked()),
        )

    def _apply(self):
        self.workspace.apply_creation_filter(self._state())
        self._sync_status()

    def _clear(self):
        self.entity_type.setCurrentIndex(0)
        self.relation_type.setCurrentIndex(0)
        self.relation_family.setCurrentIndex(0)
        self.tree.setCurrentIndex(0)
        self.layer.setCurrentIndex(0)
        self.canon.setCurrentIndex(0)
        self.visibility.setCurrentIndex(0)
        self.show_relations.setChecked(True)
        self.workspace.clear_creation_filters()
        self._sync_status()

    def _sync_status(self):
        count = self.workspace.graph.active_filter_count()
        self.status.setText(f"{count} filtro(s) activo(s)." if count else "Sin filtros activos.")



# ── Left-edge layer flyout ──────────────────────────────────────────────

class _LayerEdgeFlyout(QFrame):
    """Persistent left drawer for causal layers when Worldbuilding is ON.

    B38 replaces fragile hover reveal with an explicit top-bar button.
    The drawer stays open until the user toggles it closed.
    """

    LAYER_BG = "rgba(248,246,237,0.96)"
    LAYER_BORDER = "#D8D6C8"
    CHIP_BG = "rgba(255,255,255,0.55)"
    CHIP_ACTIVE_BG = "rgba(175,167,122,0.22)"
    CHIP_HOVER_BG = "rgba(255,255,255,0.80)"
    TEXT_COLOR = "#6F6A42"
    TEXT_ACTIVE = "#504B2E"
    MUTED = "#8C8A74"

    def __init__(self, workspace: "CreationWorkspace"):
        super().__init__(workspace)
        self._workspace = workspace
        self.setObjectName("layerEdgeFlyout")
        self.setFixedWidth(240)
        self.setStyleSheet(
            f"QFrame#layerEdgeFlyout {{ background: {self.LAYER_BG}; "
            f"border-right: 2px solid {self.LAYER_BORDER}; "
            f"border-top: 1px solid {self.LAYER_BORDER}; "
            f"border-bottom: 1px solid {self.LAYER_BORDER}; "
            f"border-radius: 0 10px 10px 0; }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Header
        header = QLabel("Capas causales")
        header.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {self.TEXT_ACTIVE}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(header)

        hint = QLabel("Clic para enfocar capa · contador visible")
        hint.setStyleSheet(
            f"font-size: 10px; color: {self.MUTED}; background: transparent; "
            f"border: none; font-style: italic;"
        )
        layout.addWidget(hint)

        # Toggle layers mode button
        self._toggle_btn = QPushButton("Vista por bandas")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: {self.CHIP_BG}; border: 1px solid {self.LAYER_BORDER}; "
            f"border-radius: 8px; padding: 5px 10px; color: {self.TEXT_COLOR}; font-size: 11px; }} "
            f"QPushButton:checked {{ background: {self.CHIP_ACTIVE_BG}; border-color: #AFA77A; }} "
            f"QPushButton:hover {{ background: {self.CHIP_HOVER_BG}; }}"
        )
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_layers_mode)
        layout.addWidget(self._toggle_btn)

        # Scroll area for layer chips
        self._chips_widget = QWidget()
        self._chips_layout = QVBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(0, 4, 0, 0)
        self._chips_layout.setSpacing(4)
        self._chips_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._chips_widget)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }} "
            f"QScrollBar:vertical {{ width: 4px; background: transparent; }} "
            f"QScrollBar::handle:vertical {{ background: {self.LAYER_BORDER}; border-radius: 2px; }}"
        )
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

        # Clear filter button
        self._clear_btn = QPushButton("Quitar filtro")
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {self.LAYER_BORDER}; "
            f"border-radius: 8px; padding: 4px 10px; color: {self.MUTED}; font-size: 10px; }} "
            f"QPushButton:hover {{ background: {self.CHIP_HOVER_BG}; color: {self.TEXT_COLOR}; }}"
        )
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_layer_filter)
        layout.addWidget(self._clear_btn)

        # State
        self._active_layer_id: str | None = None
        self._layer_chips: dict[str, QPushButton] = {}

        # Initially hidden
        self.setVisible(False)
        self._layers_loaded = False

    def _layer_counts(self) -> dict[str, int]:
        """Count visible project elements per layer without exposing IDs."""
        project = self._workspace._get_active_project()
        counts: dict[str, int] = {}
        if project is None:
            return counts
        collections = [
            getattr(project, "entities", None),
            getattr(project, "relations", None),
        ]
        for collection in collections:
            if collection is None:
                continue
            values = collection.values() if hasattr(collection, "values") else collection
            for item in values or []:
                for lid in getattr(item, "layer_ids", []) or []:
                    if lid:
                        counts[str(lid)] = counts.get(str(lid), 0) + 1
        return counts

    def populate_layers(self):
        """Fill chip list from project layers or defaults."""
        # Clear existing
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._layer_chips.clear()

        # Get layers from project or defaults
        project = self._workspace._get_active_project()
        if project and getattr(project, "world_layers", None):
            layers = list(project.world_layers)
        else:
            layers = default_world_layers()

        # Sort by order
        layers = sorted(layers, key=lambda l: getattr(l, "order", 99))
        counts = self._layer_counts()

        for layer in layers:
            lid = str(getattr(layer, "id", ""))
            name = str(getattr(layer, "name", ""))
            if not lid or not name:
                continue
            total = counts.get(lid, 0)
            chip = QPushButton(f"{name}  ·  {total}")
            chip.setCheckable(True)
            chip.setProperty("layer_id", lid)
            chip.setStyleSheet(
                f"QPushButton {{ background: {self.CHIP_BG}; border: 1px solid {self.LAYER_BORDER}; "
                f"border-radius: 6px; padding: 4px 8px; color: {self.TEXT_COLOR}; "
                f"font-size: 11px; text-align: left; }} "
                f"QPushButton:checked {{ background: {self.CHIP_ACTIVE_BG}; "
                f"border-color: #AFA77A; color: {self.TEXT_ACTIVE}; font-weight: bold; }} "
                f"QPushButton:hover {{ background: {self.CHIP_HOVER_BG}; }}"
            )
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda checked, _lid=lid: self._on_chip_clicked(_lid))
            # Insert before the stretch
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
            self._layer_chips[lid] = chip

        self._layers_loaded = True

    def _on_chip_clicked(self, layer_id: str):
        """Toggle layer filter on chip click."""
        if self._active_layer_id == layer_id:
            # Deselect
            self._clear_layer_filter()
            return
        # Activate this layer
        self._active_layer_id = layer_id
        for lid, chip in self._layer_chips.items():
            chip.setChecked(lid == layer_id)
        # Apply visual filter
        self._workspace._apply_layer_filter(layer_id)

    def _clear_layer_filter(self):
        """Remove layer filter."""
        self._active_layer_id = None
        for chip in self._layer_chips.values():
            chip.setChecked(False)
        self._workspace._clear_layer_filter()

    def _toggle_layers_mode(self, checked: bool):
        """Toggle the band-based layers view."""
        if checked:
            self._workspace._activate_layers_view()
        else:
            self._workspace._deactivate_layers_view()

    def show_flyout(self):
        """Show the flyout if worldbuilding is active."""
        project = self._workspace._get_active_project()
        if not project or not getattr(project, "worldbuilding_active", False):
            return
        if not self._layers_loaded:
            self.populate_layers()
        self.setVisible(True)
        self.raise_()

    def hide_flyout(self):
        """Hide the flyout."""
        self.setVisible(False)

    def update_toggle_state(self, layers_active: bool):
        """Sync the toggle button with the current layers mode."""
        self._toggle_btn.setChecked(layers_active)


class CreationWorkspace(QWidget):
    """Creation space: graph-first immersive experience."""

    def __init__(self, ctx: AppContext, *, corpus_view, relation_view, candidate_view,
                 import_export_view, writing_view, timeline_view, framework_view,
                 source_view=None, layer_view=None):
        super().__init__()
        self.ctx = ctx
        self.import_export_view = import_export_view
        self.writing_view = writing_view
        self.timeline_view = timeline_view
        self.framework_view = framework_view
        self.corpus_view = corpus_view
        self.relation_view = relation_view
        self.candidate_view = candidate_view
        self.source_view = source_view
        self.layer_view = layer_view
        self.source_controller = getattr(source_view, "ctrl", None)
        self.layer_controller = getattr(layer_view, "ctrl", None)
        self.entity_controller = getattr(corpus_view, "ec", None)
        self.relation_controller = getattr(relation_view, "rc", None)
        self.ai_context_controller = None
        self.ai_job_service = AIJobService()
        self._active_layer_id = ""
        self._advanced_mode = bool(ctx.advanced_mode)
        project_controller = getattr(ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is not None:
            self.ai_context_controller = AIContextController(project_service)

        self._build_ui()

        # Apply worldbuilding visibility based on current project
        project = self._get_active_project()
        if project:
            wb = getattr(project, "worldbuilding_active", False)
            self.set_worldbuilding_active(wb)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Persistent top toolbar: creative graph actions left, utilities right.
        self._top_toolbar = self._build_top_toolbar()
        self._top_toolbar.setFixedHeight(48)
        self._top_toolbar.setVisible(True)
        layout.addWidget(self._top_toolbar)

        # Graph canvas (takes all space)
        self.graph = GraphCanvasWidget(self.ctx)
        self.graph.set_ai_controller(self.ai_context_controller)
        self.graph.entitySelected.connect(self._open_node_panel)
        self.graph.relationSelected.connect(self._open_relation_panel)
        self.graph.relationCreateRequested.connect(self._open_relation_create_panel)
        self.graph.relationCreateRejected.connect(self._on_relation_create_rejected)
        self.graph.graphSelectionChanged.connect(self._on_graph_selection_changed)
        self.graph.nodeAssignToTreeRequested.connect(self._assign_node_to_tree)
        layout.addWidget(self.graph, 1)

        # Command bar area replaces the old bottom button toolbar.
        command_bar = self._build_command_bar()
        layout.addWidget(command_bar)

        # Left layer drawer is persistent: explicit button toggles it.
        self._layer_flyout = _LayerEdgeFlyout(self)
        self._layer_flyout.setVisible(False)

        self.setMouseTracking(True)
        self.graph.setMouseTracking(True)

    def _build_top_toolbar(self) -> QWidget:
        """Persistent B38 toolbar: creative actions left, utilities right."""
        bar = QFrame()
        bar.setObjectName("topUtilsBar")
        bar.setStyleSheet(
            "QFrame#topUtilsBar { background: rgba(238,236,221,0.96); "
            "border-bottom: 1px solid #D8D6C8; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(6)

        btn_style = (
            "QPushButton { background: rgba(255,255,255,0.48); border: 1px solid #D8D6C8; "
            "border-radius: 15px; padding: 4px; color: #6F6A42; font-size: 16px; "
            "min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; } "
            "QPushButton:hover { background: #F8F5EA; border: 1px solid #AFA77A; color: #504B2E; }"
        )
        disabled_style = (
            "QPushButton { background: rgba(255,255,255,0.25); border: 1px solid #E0DDD0; "
            "border-radius: 15px; padding: 4px; color: #B8B5A8; font-size: 16px; "
            "min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; } "
        )
        text_btn_style = (
            "QPushButton { background: transparent; border: 1px solid #D0CCB8; "
            "border-radius: 12px; padding: 4px 12px; color: #6F6A42; font-size: 12px; } "
            "QPushButton:hover { background: #F8F5EA; }"
        )
        self._toolbar_btn_style = btn_style
        self._toolbar_disabled_style = disabled_style

        def icon_btn(text: str, tip: str, callback, *, enabled: bool = True) -> QPushButton:
            button = QPushButton(text)
            button.setToolTip(tip)
            button.setStyleSheet(btn_style if enabled else disabled_style)
            button.setEnabled(enabled)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(callback)
            layout.addWidget(button)
            return button

        # Left: primary creative graph actions.
        icon_btn(ICON_GLYPHS["add"], "Crear entidad", self._create_entity_on_graph)
        icon_btn("⊞", "Crear árbol/contenedor", self._create_tree_on_graph)
        self._connect_mode_btn = icon_btn("↔", "Crear relación / modo conexión", self._start_relation_mode)
        self._suggest_entity_btn = icon_btn("✨", "Sugerir entidad con IA", self._suggest_node)
        self._coherence_btn = icon_btn("⚠", "Selecciona nodos o relaciones para analizar coherencia", self._open_coherence_panel, enabled=False)
        icon_btn("⌕", "Buscar y enfocar elementos", self._open_search_panel)
        self._filter_btn = icon_btn("◌", "Filtros visuales", self._open_filter_panel)
        self._suggestion_btn = icon_btn("⊹", "Bandeja de sugerencias", self._open_suggestion_inbox)
        self._suggestion_count = 0
        self._layers_toggle_btn = icon_btn("Capas", "Abrir/cerrar panel de capas causales", self._toggle_layer_drawer)
        self._layers_toggle_btn.setStyleSheet(text_btn_style)
        self._layers_toggle_btn.setFixedWidth(72)

        self._global_focus_btn = QPushButton("Global")
        self._global_focus_btn.setToolTip("Volver a vista global")
        self._global_focus_btn.setStyleSheet(text_btn_style)
        self._global_focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._global_focus_btn.clicked.connect(self.clear_focus_scope)
        self._global_focus_btn.setVisible(False)
        layout.addWidget(self._global_focus_btn)

        self._focus_label = QLabel("Global")
        self._focus_label.setStyleSheet("color: #6F6A42; font-size: 11px; padding: 0 8px;")
        layout.addWidget(self._focus_label)

        layout.addStretch(1)

        # Right: secondary management / view tools.
        import_btn = QPushButton("Importar documento")
        import_btn.setStyleSheet(text_btn_style)
        import_btn.clicked.connect(lambda: self._open_utility(self.import_export_view))
        layout.addWidget(import_btn)

        self._layers_view_btn = QPushButton("Vista libre/capas")
        self._layers_view_btn.setToolTip("Alternar vista por bandas causales")
        self._layers_view_btn.setStyleSheet(text_btn_style)
        self._layers_view_btn.clicked.connect(self._toggle_layers_view_from_toolbar)
        layout.addWidget(self._layers_view_btn)

        fit_btn = QPushButton("Fit all")
        fit_btn.setToolTip("Encajar todo")
        fit_btn.setStyleSheet(text_btn_style)
        fit_btn.clicked.connect(self.fit_all)
        layout.addWidget(fit_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset vista")
        reset_btn.setStyleSheet(text_btn_style)
        reset_btn.clicked.connect(self.reset_view)
        layout.addWidget(reset_btn)

        delete_btn = QPushButton("🗑")
        delete_btn.setToolTip("Selecciona algo para eliminar")
        delete_btn.setStyleSheet(disabled_style)
        delete_btn.setEnabled(False)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(self._delete_selected)
        self._delete_btn = delete_btn
        layout.addWidget(delete_btn)

        return bar

    def _build_command_bar(self) -> QWidget:
        """Bottom B38 contextual AI command bar. Creates jobs, never mutates canon."""
        bar = QFrame()
        bar.setObjectName("aiCommandBar")
        bar.setStyleSheet(
            "QFrame#aiCommandBar { background: rgba(248,246,237,0.94); "
            "border-top: 1px solid #D8D6C8; }"
        )
        bar.setFixedHeight(62)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(80, 10, 80, 10)
        layout.setSpacing(8)

        self._command_input = QLineEdit()
        self._command_input.setObjectName("aiCommandInput")
        self._command_input.setPlaceholderText("Pídele a Dendro que actúe sobre el grafo…")
        self._command_input.setStyleSheet(
            "QLineEdit#aiCommandInput { background: rgba(255,255,255,0.82); "
            "border: 1px solid #D0CCB8; border-radius: 18px; padding: 8px 14px; "
            "font-size: 13px; color: #504B2E; }"
        )
        self._command_input.returnPressed.connect(self._submit_ai_command)
        layout.addWidget(self._command_input, 1)

        self._command_submit_btn = QPushButton("↵")
        self._command_submit_btn.setToolTip("Crear job IA revisable")
        self._command_submit_btn.setStyleSheet(
            "QPushButton { background: #6F6A42; color: #F8F5EA; border: none; "
            "border-radius: 17px; min-width: 38px; min-height: 34px; font-size: 16px; } "
            "QPushButton:hover { background: #504B2E; }"
        )
        self._command_submit_btn.clicked.connect(self._submit_ai_command)
        layout.addWidget(self._command_submit_btn)

        self._job_status_label = QLabel("Sin tareas IA activas")
        self._job_status_label.setStyleSheet("color: #6F6A42; font-size: 11px; min-width: 170px;")
        layout.addWidget(self._job_status_label)
        return bar

    # ── B38 persistent layer drawer and command bar ───────────────────────

    def _start_relation_mode(self):
        """Guide the existing drag-to-connect relation flow; no parallel mode."""
        self.ctx.log("info", "Para crear relación: arrastra desde un nodo o árbol hacia otro elemento del grafo.")

    def _toggle_layer_drawer(self):
        """Persistent explicit drawer: stays open until user toggles it again."""
        project = self._get_active_project()
        active = bool(project and getattr(project, "worldbuilding_active", False))
        if not active:
            self.ctx.log("warning", "Activa Worldbuilding en el proyecto para usar capas causales")
            return
        if self._layer_flyout.isVisible():
            self._layer_flyout.hide_flyout()
        else:
            self._layer_flyout.show_flyout()

    def _toggle_layers_view_from_toolbar(self):
        project = self._get_active_project()
        active = bool(project and getattr(project, "worldbuilding_active", False))
        if not active:
            self.ctx.log("warning", "La vista por capas requiere Worldbuilding activado")
            return
        layer_mode = bool(getattr(getattr(self.graph, "canvas", None), "_layer_mode_active", False))
        if layer_mode:
            self._deactivate_layers_view()
        else:
            self._activate_layers_view()

    def _current_context_scope(self) -> dict:
        project = self._get_active_project()
        layer_ids = tuple(getattr(getattr(self.graph, "canvas", None), "_visual_filter", VisualFilterState()).layer_ids)
        return {
            "project_id": str(getattr(project, "id", "")) if project is not None else "",
            "worldbuilding_active": bool(getattr(project, "worldbuilding_active", False)) if project is not None else False,
            "selected_entity_ids": self.graph.selected_entity_ids() if hasattr(self, "graph") else [],
            "selected_relation_ids": self.graph.selected_relation_ids() if hasattr(self, "graph") else [],
            "active_layer_ids": list(layer_ids),
            "focus_label": self._focus_label.text() if hasattr(self, "_focus_label") else "Global",
            "visual_filters_active": self.graph.active_filter_count() if hasattr(self, "graph") else 0,
        }

    def _submit_ai_command(self):
        prompt = self._command_input.text().strip()
        if not prompt:
            self._job_status_label.setText("Escribe una orden para Dendro")
            return
        scope = self._current_context_scope()
        job_type = classify_ai_job_intent(prompt, worldbuilding_active=bool(scope.get("worldbuilding_active")))
        result = self.ai_job_service.create_job(job_type, prompt, context_scope=scope)
        if isinstance(result, Error):
            self._job_status_label.setText(result.error)
            self.ctx.log("error", result.error)
            return
        job = result.value
        # B38-T03/T04 only creates a reviewable job. Runner/results arrive in T05+.
        self.ai_job_service.update_status(
            job.id,
            AIJobStatus.QUEUED,
            message="Job creado. Pendiente de runner no bloqueante.",
            progress=0.0,
        )
        self._command_input.clear()
        self._job_status_label.setText(f"Job creado: {job.type.value.replace('_', ' ')}")
        self.ctx.log("info", "Job IA creado: resultado revisable, sin cambios automáticos en canon")

    def resizeEvent(self, event):
        """Position persistent layer drawer along the left edge."""
        super().resizeEvent(event)
        if hasattr(self, "_layer_flyout"):
            h = self.height() - 48 - 62  # top toolbar + command bar
            self._layer_flyout.setGeometry(0, 48, 260, max(h, 220))

    def _activate_layers_view(self):
        project = self._get_active_project()
        if project is None or not bool(getattr(project, "worldbuilding_active", False)):
            self.ctx.log("warning", "La vista Capas solo está disponible con Worldbuilding activado")
            return
        self.ctx.log("info", "Vista Capas causales activa")
        if hasattr(self.graph, "set_worldbuilding_active"):
            self.graph.set_worldbuilding_active(True)
        else:
            self.refresh()
        if hasattr(self, "_layer_flyout"):
            self._layer_flyout.update_toggle_state(True)

    def _deactivate_layers_view(self):
        """Switch back from layers band view to normal graph view."""
        if hasattr(self.graph, "set_worldbuilding_active"):
            self.graph.set_worldbuilding_active(False)
        else:
            self.refresh()
        if hasattr(self, "_layer_flyout"):
            self._layer_flyout.update_toggle_state(False)

    def _apply_layer_filter(self, layer_id: str):
        """Filter the graph to show only nodes/edges in the selected causal layer."""
        from hosts.DesktopHostPySide.widgets.graph_canvas import VisualFilterState
        self.graph.canvas.apply_visual_filter(
            VisualFilterState(layer_ids=(layer_id,))
        )

    def _clear_layer_filter(self):
        """Remove layer filter and show all nodes."""
        if hasattr(self.graph, "canvas") and hasattr(self.graph.canvas, "clear_visual_filters"):
            self.graph.canvas.clear_visual_filters()

    def _open_search_panel(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        panel = CreationSearchPanel(self)
        drawer.set_content(panel, title="Buscar")
        drawer.open()

    def _open_filter_panel(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        panel = CreationFilterPanel(self)
        drawer.set_content(panel, title="Filtros")
        drawer.open()

    def _open_suggestion_inbox(self):
        drawer = self.ctx.drawer
        controller = getattr(self.candidate_view, "cc", None)
        if controller is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir la bandeja de sugerencias")
            return
        panel = SuggestionInboxPanel(controller, on_changed=self._on_suggestion_changed, on_focus=self._focus_suggestion_entity)
        drawer.set_content(panel, title="Sugerencias")
        drawer.open()

    def _on_suggestion_changed(self):
        self.refresh()
        self._sync_suggestion_indicator()

    def _focus_suggestion_entity(self, entity_id: str):
        if hasattr(self.graph, "focus_node"):
            self.graph.focus_node(entity_id)
            self._open_node_panel(entity_id)

    def _sync_suggestion_indicator(self):
        btn = getattr(self, "_suggestion_btn", None)
        if btn is None:
            return
        controller = getattr(self.candidate_view, "cc", None)
        if controller is None:
            return
        count = len(controller.list_all())
        self._suggestion_count = count
        if count > 0:
            btn.setText(f"💡 {count}")
        else:
            btn.setText("💡")

    def _sync_filter_indicator(self):
        btn = getattr(self, "_filter_btn", None)
        if btn is None:
            return
        count = self.graph.active_filter_count()
        if count:
            btn.setText(f"◫{count}")
            btn.setToolTip(f"Filtros visuales ({count} activo(s))")
        else:
            btn.setText("◫")
            btn.setToolTip("Filtros visuales")

    def apply_creation_filter(self, filter_state: VisualFilterState):
        self.graph.apply_visual_filter(filter_state)
        self._sync_filter_indicator()

    def clear_creation_filters(self):
        self.graph.clear_visual_filters()
        self._sync_filter_indicator()

    def focus_search_result(self, result: GraphSearchResult) -> bool:
        if result.item_kind == "relation":
            return self.graph.focus_relation(result.item_id)
        if result.item_kind == "tree":
            return self.graph.focus_tree(result.item_id)
        return self.graph.focus_node(result.item_id)

    def _set_focus_breadcrumb(self, text: str, *, active: bool):
        if hasattr(self, "_focus_label"):
            self._focus_label.setText(text)
        if hasattr(self, "_global_focus_btn"):
            self._global_focus_btn.setVisible(active)

    def _entity_name(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        return str(getattr(entity, "name", entity_id)) if entity is not None else "Elemento"

    def focus_tree_scope(self, tree_id: str) -> bool:
        ok = self.graph.focus_tree_scope(tree_id)
        if ok:
            self._set_focus_breadcrumb(f"Global > {self._entity_name(tree_id)}", active=True)
            self.ctx.log("info", "Vista enfocada de árbol activa")
        return ok

    def focus_neighborhood(self, item_id: str, *, kind: str = "entity") -> bool:
        ok = self.graph.focus_neighborhood(item_id)
        if ok:
            label = self._entity_name(item_id) if kind != "relation" else "Relación seleccionada"
            self._set_focus_breadcrumb(f"Global > Vecindad > {label}", active=True)
            self.ctx.log("info", "Vista enfocada de vecindad activa")
        return ok

    def clear_focus_scope(self):
        self.graph.clear_focus_scope()
        self._set_focus_breadcrumb("Global", active=False)
        self._sync_filter_indicator()
        self.ctx.log("info", "Vista global restaurada")

    def fit_all(self):
        self.graph.fit_all()

    def reset_view(self):
        self.graph.reset_view()

    def center_selection(self):
        if not self.graph.center_selection():
            self.ctx.log("info", "No hay selección que centrar")

    # ── Utility openers ────────────────────────────────────────────────────

    def _on_graph_selection_changed(self, entity_ids: list[str], relation_ids: list[str]):
        has_selection = bool(entity_ids or relation_ids)
        n_e = len(entity_ids)
        n_r = len(relation_ids)

        # Coherence button
        button = getattr(self, "_coherence_btn", None)
        if button is not None:
            button.setEnabled(has_selection)
            button.setStyleSheet(self._toolbar_btn_style if has_selection else self._toolbar_disabled_style)
            if has_selection:
                button.setToolTip(f"Analizar coherencia: {n_e} nodo(s), {n_r} relación(es)")
            else:
                button.setToolTip("Selecciona nodos o relaciones para analizar coherencia")

        # Suggest entity / relation buttons: always enabled, but update tooltip with context info
        for attr, base in [("_suggest_entity_btn", "Sugerir entidad"), ("_suggest_relation_btn", "Sugerir relación")]:
            btn = getattr(self, attr, None)
            if btn is not None and btn.isEnabled():
                if has_selection:
                    btn.setToolTip(f"{base} con IA (contexto: {n_e} nodo(s), {n_r} relación(es) seleccionado(s))")
                else:
                    btn.setToolTip(f"{base} con IA (contexto: todo el proyecto)")

        # Delete button: enabled when something is selected
        del_btn = getattr(self, "_delete_btn", None)
        if del_btn is not None:
            del_btn.setEnabled(has_selection)
            del_btn.setStyleSheet(self._toolbar_btn_style if has_selection else self._toolbar_disabled_style)
            if has_selection:
                parts = []
                if n_e:
                    parts.append(f"{n_e} nodo(s)")
                if n_r:
                    parts.append(f"{n_r} relación(es)")
                del_btn.setToolTip(f"Eliminar: {', '.join(parts)}")
            else:
                del_btn.setToolTip("Selecciona algo para eliminar")

    def _delete_selected(self):
        """Delete selected entities and/or relations."""
        entity_ids = self.graph.selected_entity_ids()
        relation_ids = self.graph.selected_relation_ids()
        if not (entity_ids or relation_ids):
            return
        deleted = 0
        errors = []
        # Delete relations first (before cascade from entity delete removes them)
        if self.relation_controller is not None:
            for rid in relation_ids:
                result = self.relation_controller.delete(rid)
                if isinstance(result, Error):
                    errors.append(result.error)
                else:
                    deleted += 1
        # Delete entities (cascades to their relations)
        if self.entity_controller is not None:
            for eid in entity_ids:
                result = self.entity_controller.delete(eid)
                if isinstance(result, Error):
                    errors.append(result.error)
                else:
                    deleted += 1
        if errors:
            self.ctx.log("error", f"Errores al eliminar: {'; '.join(errors)}")
        if deleted > 0:
            self.ctx.log("info", f"Eliminado(s): {deleted} elemento(s)")
            # Close drawer if it shows a deleted entity/relation
            if hasattr(self, "ctx") and hasattr(self.ctx, "drawer"):
                self.ctx.drawer.close()
            self.refresh()

    def _open_coherence_panel(self):
        entity_ids = self.graph.selected_entity_ids()
        relation_ids = self.graph.selected_relation_ids()
        if not (entity_ids or relation_ids):
            self.ctx.log("info", "Selecciona uno o varios nodos/relaciones para analizar coherencia")
            return
        if self.ai_context_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "IA contextual no disponible para coherencia")
            return
        panel = CoherencePanel(
            self.ctx,
            self.ai_context_controller,
            self.entity_controller,
            self.relation_controller,
            entity_ids=entity_ids,
            relation_ids=relation_ids,
            on_saved=self.refresh,
        )
        self.ctx.drawer.set_content(panel, title="Coherencia")
        self.ctx.drawer.open()

    def _open_utility(self, view):
        """Open a utility view in the right drawer."""
        drawer = self.ctx.drawer
        if drawer is None or view is None:
            return
        title = getattr(view, "windowTitle", "")
        if callable(title):
            title = title()
        if not title:
            title = "Herramienta"
        drawer.set_content(view, title=title)
        drawer.open()

    # ── Suggest node / relation via AI ─────────────────────────────────

    def _suggest_node(self):
        """Ask AI to suggest missing entities. Uses graph selection as context if available."""
        if self.ai_context_controller is None:
            self.ctx.log("error", "IA no configurada. Verifica proveedor en Ajustes.")
            return
        project = self._get_active_project()
        if project is None:
            self.ctx.log("error", "No hay proyecto activo")
            return

        # Selection takes priority; fall back to all entities
        sel_e = self.graph.selected_entity_ids()
        sel_r = self.graph.selected_relation_ids()
        if sel_e:
            entity_ids = sel_e
            relation_ids = sel_r
            context_label = f"{len(sel_e)} nodo(s) seleccionado(s)"
        else:
            entity_ids = [getattr(e, "id", "") for e in getattr(project, "entities", []) or []]
            relation_ids = []
            context_label = "todo el proyecto"

        btn = getattr(self, "_suggest_entity_btn", None)
        if btn:
            btn.setEnabled(False)
            btn.setToolTip("Consultando IA...")

        self._suggest_worker = _SuggestWorker(
            self.ai_context_controller,
            action="suggest_missing_nodes",
            entity_ids=entity_ids,
            relation_ids=relation_ids,
        )
        self._suggest_worker.finished.connect(lambda: self._on_suggest_done("nodo", "_suggest_entity_btn", "_suggest_worker"))
        self._suggest_worker.start()
        self.ctx.log("info", f"Consultando IA para sugerir entidades (contexto: {context_label})...")

    def _suggest_relation(self):
        """Ask AI to suggest missing relations. Uses graph selection as context if available."""
        if self.ai_context_controller is None:
            self.ctx.log("error", "IA no configurada. Verifica proveedor en Ajustes.")
            return
        project = self._get_active_project()
        if project is None:
            self.ctx.log("error", "No hay proyecto activo")
            return

        sel_e = self.graph.selected_entity_ids()
        sel_r = self.graph.selected_relation_ids()
        if sel_e:
            entity_ids = sel_e
            relation_ids = sel_r
            context_label = f"{len(sel_e)} nodo(s) seleccionado(s)"
        else:
            entity_ids = [getattr(e, "id", "") for e in getattr(project, "entities", []) or []]
            relation_ids = []
            context_label = "todo el proyecto"

        btn = getattr(self, "_suggest_relation_btn", None)
        if btn:
            btn.setEnabled(False)
            btn.setToolTip("Consultando IA...")

        self._suggest_rel_worker = _SuggestWorker(
            self.ai_context_controller,
            action="suggest_missing_relations",
            entity_ids=entity_ids,
            relation_ids=relation_ids,
        )
        self._suggest_rel_worker.finished.connect(lambda: self._on_suggest_done("relación", "_suggest_relation_btn", "_suggest_rel_worker"))
        self._suggest_rel_worker.start()
        self.ctx.log("info", f"Consultando IA para sugerir relaciones (contexto: {context_label})...")

    def _on_suggest_done(self, kind: str, btn_attr: str, worker_attr: str):
        """Handle AI suggestion result (works for both nodes and relations)."""
        btn = getattr(self, btn_attr, None)
        if btn:
            btn.setEnabled(True)
            tooltip_base = "Sugerir entidad" if kind == "nodo" else "Sugerir relación"
            btn.setToolTip(f"{tooltip_base} con IA (selecciona nodos como contexto)")

        worker = getattr(self, worker_attr, None)
        if worker is None:
            return
        result = worker.result
        setattr(self, worker_attr, None)

        if result is None:
            self.ctx.log("error", f"La sugerencia IA de {kind} falló sin resultado")
            return
        if isinstance(result, Error):
            self.ctx.log("error", f"Error IA: {result.error}")
            return

        value = result.value
        candidate_count = len(getattr(value, "candidates", []) or [])
        preview_count = len(getattr(value, "previews", []) or [])

        if candidate_count == 0 and preview_count == 0:
            raw = getattr(value, "raw_text", "") or ""
            if raw:
                self.ctx.log("info", f"IA: {raw[:200]}")
            else:
                self.ctx.log("info", f"La IA no generó sugerencias de {kind}")
            return

        self.ctx.log("info", f"IA sugirió {candidate_count} candidato(s) de {kind}")
        self.refresh()
        self.open_candidates_clean()

    def _create_entity_on_graph(self):
        """Create a new entity, add node to graph center, open detail panel."""
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo crear entidad: servicio no disponible")
            return
        result = self.entity_controller.create({
            "name": "Nueva entidad",
            "entity_type": "nota",
            "brief_description": "",
            "canon_state": "borrador",
            "custom_metadata": {"_visual_draft": True},
        })
        if isinstance(result, Error):
            self.ctx.log("error", f"Error creando entidad: {result.error}")
            return
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Entidad creada en modo borrador")
        self.refresh()
        # Focus the new node
        self.graph.canvas.focus_entity(entity_id)
        # Open detail panel for editing
        self._open_node_panel(entity_id, is_new=True)

    def _create_tree_on_graph(self):
        """Create a new contenedor entity and open tree detail panel."""
        if self.entity_controller is None:
            self.ctx.log("error", "No se pudo crear contenedor: servicio no disponible")
            return
        result = self.entity_controller.create({
            "name": "Nuevo contenedor",
            "entity_type": "contenedor",
            "brief_description": "",
            "canon_state": "borrador",
            "custom_metadata": {"_visual_draft": True},
        })
        if isinstance(result, Error):
            self.ctx.log("error", f"Error creando contenedor: {result.error}")
            return
        entity = result.value
        entity_id = getattr(entity, "id", "")
        self.ctx.log("info", "Contenedor creado en modo borrador")
        self.refresh()
        self.graph.canvas.focus_entity(entity_id)
        self._open_tree_panel(entity_id, is_new=True)

    def _assign_node_to_tree(self, entity_id: str, tree_id: str):
        """Assign entity (or container) to a container tree. Removes old 'contiene' first."""
        if self.relation_controller is None:
            self.ctx.log("error", "No se pudo asignar al contenedor: servicio no disponible")
            return
        # Check for cycle
        if entity_id == tree_id:
            self.ctx.log("error", "Un contenedor no puede contenerse a sí mismo")
            return
        # Check for nesting cycle: tree_id must not be inside entity_id
        if self._is_nested_in(tree_id, entity_id):
            self.ctx.log("error", "Anidamiento cíclico: el contenedor destino ya pertenece al origen")
            return
        # Remove any existing 'contiene' relation pointing to this entity
        self._remove_tree_membership(entity_id)
        # Check if already in this tree
        if self._relation_exists(tree_id, entity_id):
            self.ctx.log("info", "Esta entidad ya pertenece al contenedor")
            return
        result = self.relation_controller.create(
            tree_id,
            entity_id,
            "contiene",
            "Pertenencia semántica (árbol)",
        )
        if isinstance(result, Error):
            self.ctx.log("error", f"Error asignando al contenedor: {result.error}")
            return
        self.ctx.log("info", "Entidad asignada al contenedor")
        self.refresh()

    def _open_tree_panel(self, entity_id: str, *, is_new: bool = False):
        if self.entity_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de contenedor")
            return
        from hosts.DesktopHostPySide.widgets.tree_detail_panel import TreeDetailPanel
        panel = TreeDetailPanel(
            self.ctx,
            self.entity_controller,
            self.relation_controller,
            entity_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
            is_new=is_new,
            on_focus_tree=self.focus_tree_scope,
        )
        self.ctx.drawer.set_content(panel, title="Contenedor")
        self.ctx.drawer.open()

    # ── Existing workspace methods (preserved) ─────────────────────────────

    def refresh_ai_controller(self):
        """Rebuild contextual AI controller after provider/settings changes."""
        project_controller = getattr(self.ctx, "project_controller", None)
        project_service = getattr(project_controller, "ps", None)
        if project_service is None:
            self.ai_context_controller = None
        else:
            self.ai_context_controller = AIContextController(project_service)
        if hasattr(self, "graph"):
            self.graph.set_ai_controller(self.ai_context_controller)

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        if hasattr(self.graph, "set_advanced_mode"):
            self.graph.set_advanced_mode(enabled)

    def _get_active_project(self):
        pc = getattr(self.ctx, "project_controller", None)
        if pc:
            return getattr(pc.ps, "active_project", None)
        return None

    def set_worldbuilding_active(self, active: bool):
        """Show/hide worldbuilding-related UI elements without forcing layer view."""
        active = bool(active)
        if hasattr(self, "_layers_view_btn"):
            self._layers_view_btn.setVisible(active)
        if hasattr(self, "_layers_toggle_btn"):
            self._layers_toggle_btn.setVisible(active)
            self._layers_toggle_btn.setEnabled(active)
            self._layers_toggle_btn.setToolTip(
                "Abrir/cerrar panel de capas causales" if active else "Activa Worldbuilding para usar capas causales"
            )
        if not active and hasattr(self, "_layer_flyout"):
            self._layer_flyout.hide_flyout()
        if not active and hasattr(self, "graph") and hasattr(self.graph, "set_worldbuilding_active"):
            self.graph.set_worldbuilding_active(False)

    def refresh(self):
        for widget in [self.graph, self.import_export_view, self.writing_view, self.timeline_view,
                       self.framework_view, self.corpus_view, self.relation_view, self.candidate_view,
                       self.source_view, self.layer_view]:
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()

    def open_graph(self):
        """Graph is always visible — this is now a no-op."""
        pass

    def open_entity_create(self):
        drawer = self.ctx.drawer
        if self.entity_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear entidad: servicio no disponible")
            return
        panel = EntityQuickCreatePanel(self.entity_controller, on_created=self.refresh)
        drawer.set_content(panel, title="Nueva entidad")
        drawer.open()

    def open_candidates_clean(self):
        drawer = self.ctx.drawer
        controller = getattr(self.candidate_view, "cc", None)
        if controller is None or drawer is None:
            self.ctx.log("error", "No se pudo abrir sugerencias: servicio no disponible")
            return
        panel = CandidateReviewPanel(controller, on_changed=self.refresh)
        drawer.set_content(panel, title="Sugerencias")
        drawer.open()

    def open_source_create(self):
        drawer = self.ctx.drawer
        if self.source_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear fuente: servicio no disponible")
            return
        panel = SourceQuickCreatePanel(self.source_controller, on_created=self.refresh)
        drawer.set_content(panel, title="Nueva fuente")
        drawer.open()

    def open_layer_create(self):
        drawer = self.ctx.drawer
        if self.layer_controller is None or drawer is None:
            self.ctx.log("error", "No se pudo crear capa: servicio no disponible")
            return
        panel = LayerQuickCreatePanel(self.layer_controller, on_created=self.refresh)
        drawer.set_content(panel, title="Nueva capa")
        drawer.open()

    def _open_node_panel(self, entity_id: str, *, is_new: bool = False):
        if self.entity_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de nodo")
            return
        # Route contenedor entities to tree detail panel
        entity = self._entity_by_id(entity_id)
        if entity is not None:
            etype = str(getattr(getattr(entity, "entity_type", ""), "value", getattr(entity, "entity_type", "")))
            if etype == "contenedor":
                self._open_tree_panel(entity_id)
                return
        panel = NodeDetailPanel(
            self.ctx,
            self.entity_controller,
            entity_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
            relation_controller=self.relation_controller,
            is_new=is_new,
            on_focus_neighborhood=lambda eid=entity_id: self.focus_neighborhood(eid, kind="entity"),
        )
        self.ctx.drawer.set_content(panel, title="Nodo")
        self.ctx.drawer.open()

    def _open_relation_panel(self, relation_id: str, *, is_new: bool = False):
        if self.relation_controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir el panel de relación")
            return
        panel = RelationDetailPanel(
            self.ctx,
            self.relation_controller,
            relation_id,
            on_saved=self.refresh,
            ai_controller=self.ai_context_controller,
            entity_controller=self.entity_controller,
            is_new=is_new,
            on_focus_neighborhood=lambda rid=relation_id: self.focus_neighborhood(rid, kind="relation"),
        )
        self.ctx.drawer.set_content(panel, title="Relación")
        self.ctx.drawer.open()

    def _entity_by_id(self, entity_id: str):
        pc = self.ctx.project_controller
        project = pc.ps.active_project if pc else None
        if project is None:
            return None
        for entity in getattr(project, "entities", []) or []:
            if getattr(entity, "id", None) == entity_id:
                return entity
        return None

    def _entity_label(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return "Entidad no encontrada"
        kind = getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "entidad"))
        return human_ref(getattr(entity, "name", "Sin nombre"), enum_human(str(kind)))

    def _relation_exists(self, source_id: str, target_id: str) -> bool:
        if self.relation_controller is None:
            return False
        for relation in self.relation_controller.list_all():
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if (src, tgt) == (source_id, target_id) or (src, tgt) == (target_id, source_id):
                return True
        return False

    @staticmethod
    def _rtype_value(rel) -> str:
        """Extract relation_type value as lowercase string, handling enum and str."""
        rtype = getattr(rel, "relation_type", "")
        if hasattr(rtype, "value"):
            return str(rtype.value).lower()
        return str(rtype).lower()

    def _remove_tree_membership(self, entity_id: str):
        """Remove any existing 'contiene' relation where entity_id is the target."""
        if self.relation_controller is None:
            return
        to_delete = []
        for rel in self.relation_controller.list_all():
            if self._rtype_value(rel) == "contiene" and getattr(rel, "target_id", "") == entity_id:
                to_delete.append(rel.id)
        for rid in to_delete:
            self.relation_controller.delete(rid)

    def _is_nested_in(self, entity_id: str, ancestor_id: str, visited: set | None = None) -> bool:
        """Check if entity_id is transitively contained inside ancestor_id."""
        if visited is None:
            visited = set()
        if entity_id in visited:
            return False
        visited.add(entity_id)
        if self.relation_controller is None:
            return False
        for rel in self.relation_controller.list_all():
            if self._rtype_value(rel) == "contiene" and getattr(rel, "target_id", "") == entity_id:
                parent = getattr(rel, "source_id", "")
                if parent == ancestor_id:
                    return True
                if self._is_nested_in(parent, ancestor_id, visited):
                    return True
        return False

    def _on_relation_create_rejected(self, message: str):
        if message and message != "Relación cancelada":
            self.ctx.log("warning", message)

    def _open_relation_create_panel(self, source_id: str, target_id: str):
        controller = self.relation_controller
        if controller is None or self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo crear relación: servicio no disponible")
            return
        if source_id == target_id:
            self.ctx.log("warning", "No se puede crear una relación sobre la misma entidad")
            return
        if self._relation_exists(source_id, target_id):
            self.ctx.log("warning", "Ya existe una relación entre esas entidades")
            return
        result = controller.create(
            source_id,
            target_id,
            "esta_relacionado_con",
            {
                "description": "",
                "custom_metadata": {
                    "_visual_draft": True,
                    "_edge_color": "#A4AEC0",
                },
            },
        )
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        relation = result.value
        relation_id = getattr(relation, "id", "")
        self.ctx.log("info", "Relación provisional creada")
        self.refresh()
        if relation_id:
            self._open_relation_panel(relation_id, is_new=True)


class GalleryWorkspace(QWidget):
    """Immersive gallery of narrative material."""

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(22, 22, 22, 22)
        self.grid.setSpacing(14)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Galería",
            "Explora tu material narrativo en tarjetas limpias, sin datos técnicos en modo normal."
        ))
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre, tipo o descripción…")
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search, 2)
        self.kind_filter = QComboBox()
        self.kind_filter.addItems(["Todo", "Entidades", "Campañas", "Sesiones", "Facciones", "Secretos/Pistas"])
        self.kind_filter.currentTextChanged.connect(self.refresh)
        filters.addWidget(self.kind_filter)
        self.group_filter = QComboBox()
        self.group_filter.addItems(["Sin agrupar", "Agrupar por tipo", "Agrupar por estado"])
        self.group_filter.currentTextChanged.connect(self.refresh)
        filters.addWidget(self.group_filter)
        self.toggle_filters = QPushButton("Filtros")
        self.toggle_filters.clicked.connect(self._toggle_filters)
        filters.addWidget(self.toggle_filters)
        header_layout.addLayout(filters)
        self.filters_hint = QLabel("Secretos y pistas solo se muestran para perfil GM. IDs y JSON permanecen ocultos en modo normal.")
        self.filters_hint.setObjectName("mutedLabel")
        self.filters_hint.setWordWrap(True)
        self.filters_hint.hide()
        header_layout.addWidget(self.filters_hint)
        layout.addWidget(header)
        layout.addWidget(make_scroll_area(self.container), 1)

    def _clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _toggle_filters(self):
        self.filters_hint.setVisible(not self.filters_hint.isVisible())

    def _is_gm(self) -> bool:
        return str(getattr(self.ctx, "current_audience", "gm") or "gm").lower() == "gm"

    def _entity_relations(self, project, entity_id: str) -> str:
        names = []
        for relation in getattr(project, "relations", []) or []:
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if entity_id not in {src, tgt}:
                continue
            other_id = tgt if src == entity_id else src
            for entity in getattr(project, "entities", []) or []:
                if getattr(entity, "id", "") == other_id:
                    names.append(getattr(entity, "name", "Entidad"))
                    break
            if len(names) >= 2:
                break
        return "Relaciones: " + ", ".join(names) if names else "Sin relaciones destacadas"

    def _items(self, project) -> list[dict]:
        items: list[dict] = []
        for entity in getattr(project, "entities", []) or []:
            kind_key = str(getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", "entidad")))
            visibility = str(getattr(getattr(entity, "visibility_state", None), "value", getattr(entity, "visibility_state", "")))
            if not self._is_gm() and visibility in {"secreto_mundo", "privado_gm", "oculto"}:
                continue
            canon = str(getattr(getattr(entity, "canon_state", None), "value", getattr(entity, "canon_state", "")))
            items.append({
                "id": getattr(entity, "id", ""),
                "source": entity,
                "source_type": "entity",
                "title": getattr(entity, "name", "Sin nombre"),
                "kind": enum_human(kind_key),
                "kind_key": kind_key,
                "subtitle": getattr(entity, "brief_description", "") or getattr(entity, "brief", "") or getattr(entity, "description", ""),
                "symbol": "◆",
                "badges": [(enum_human(canon or "canon"), "success"), (enum_human(visibility or "visible"), "info")],
                "relation_summary": self._entity_relations(project, getattr(entity, "id", "")),
                "group_type": enum_human(kind_key),
                "group_state": enum_human(canon or "canon"),
            })
        for campaign in getattr(project, "campaigns", []) or []:
            items.append({
                "id": getattr(campaign, "id", ""),
                "source": campaign,
                "source_type": "campaign",
                "title": getattr(campaign, "name", "Sin campaña"),
                "kind": "Campaña",
                "kind_key": "campaña",
                "subtitle": getattr(campaign, "description", "") or "Campaña narrativa",
                "symbol": "◎",
                "badges": [("Campaña", "info")],
                "relation_summary": f"Sesiones: {len(getattr(campaign, 'session_ids', []) or [])}",
                "group_type": "Campaña",
                "group_state": "Campaña",
            })
        for faction in getattr(project, "factions", []) or []:
            items.append({
                "id": getattr(faction, "id", ""),
                "source": faction,
                "source_type": "faction",
                "title": getattr(faction, "name", "Sin facción"),
                "kind": "Facción",
                "kind_key": "faccion",
                "subtitle": getattr(faction, "description", "") or "Facción del mundo",
                "symbol": "◈",
                "badges": [("Facción", "warning")],
                "relation_summary": f"Aliados/enemigos: {len(getattr(faction, 'ally_faction_ids', []) or [])}/{len(getattr(faction, 'enemy_faction_ids', []) or [])}",
                "group_type": "Facción",
                "group_state": "Facción",
            })
        for session in getattr(project, "sessions", []) or []:
            items.append({
                "id": getattr(session, "id", ""),
                "source": session,
                "source_type": "session",
                "title": getattr(session, "title", "") or getattr(session, "name", "Sesión"),
                "kind": "Sesión",
                "kind_key": "sesión",
                "subtitle": getattr(session, "context_summary", "") or getattr(session, "summary", "") or "Sesión preparada",
                "symbol": "◌",
                "badges": [("Sesión", "info")],
                "relation_summary": f"Escenas: {len(getattr(session, 'scenes', []) or [])}",
                "group_type": "Sesión",
                "group_state": "Sesión",
            })
        if self._is_gm():
            for secret in getattr(project, "secrets", []) or []:
                items.append({
                    "id": getattr(secret, "id", ""),
                    "source": secret,
                    "source_type": "secret",
                    "title": getattr(secret, "title", "") or "Secreto",
                    "kind": "Secreto",
                    "kind_key": "secreto",
                    "subtitle": getattr(secret, "content", "") or getattr(secret, "description", "") or "Secreto narrativo",
                    "symbol": "✦",
                    "badges": [("GM", "danger")],
                    "relation_summary": "Visible solo para dirección",
                    "group_type": "Secretos/Pistas",
                    "group_state": "GM",
                })
            for clue in getattr(project, "clues", []) or []:
                items.append({
                    "id": getattr(clue, "id", ""),
                    "source": clue,
                    "source_type": "clue",
                    "title": getattr(clue, "title", "") or "Pista",
                    "kind": "Pista",
                    "kind_key": "pista",
                    "subtitle": getattr(clue, "content", "") or getattr(clue, "description", "") or "Pista narrativa",
                    "symbol": "✧",
                    "badges": [("GM", "success")],
                    "relation_summary": "Revelación controlada",
                    "group_type": "Secretos/Pistas",
                    "group_state": "GM",
                })
        return items

    def _filtered_items(self, items: list[dict]) -> list[dict]:
        text = self.search.text().strip().lower()
        kind_filter = self.kind_filter.currentText()
        def matches(item: dict) -> bool:
            haystack = " ".join(str(item.get(key, "")) for key in ["title", "kind", "subtitle", "relation_summary"]).lower()
            if text and text not in haystack:
                return False
            source_type = item.get("source_type")
            if kind_filter == "Entidades" and source_type != "entity":
                return False
            if kind_filter == "Campañas" and source_type != "campaign":
                return False
            if kind_filter == "Sesiones" and source_type != "session":
                return False
            if kind_filter == "Facciones" and source_type != "faction":
                return False
            if kind_filter == "Secretos/Pistas" and source_type not in {"secret", "clue"}:
                return False
            return True
        return [item for item in items if matches(item)]

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.grid.addWidget(EmptyState("Galería", "Abre un proyecto para ver tus elementos como tarjetas."), 0, 0)
            return
        items = self._filtered_items(self._items(project))
        if not items:
            self.grid.addWidget(EmptyState("Sin elementos", "Crea contenido o ajusta búsqueda/filtros para poblar esta galería."), 0, 0)
            return
        group_mode = self.group_filter.currentText()
        row = 0
        col = 0
        current_group = None
        for item in sorted(items, key=lambda x: (x.get("group_type", ""), x.get("title", ""))):
            group = ""
            if group_mode == "Agrupar por tipo":
                group = str(item.get("group_type") or item.get("kind") or "Elementos")
            elif group_mode == "Agrupar por estado":
                group = str(item.get("group_state") or "Estado")
            if group and group != current_group:
                current_group = group
                col = 0
                if row > 0:
                    row += 1
                self.grid.addWidget(SectionHeader(group, ""), row, 0, 1, 3)
                row += 1
            card = EntityCard(item)
            card.clicked.connect(self._open_detail)
            self.grid.addWidget(card, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

    def _open_detail(self, item: dict):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de galería")
            return
        detail = QWidget()
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        layout.addWidget(SectionHeader(str(item.get("title") or "Detalle"), str(item.get("kind") or "Elemento")))
        layout.addWidget(QLabel(str(item.get("subtitle") or "Sin descripción breve")))
        layout.addWidget(QLabel(str(item.get("relation_summary") or "")))
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {item.get('id', '')}\nTipo fuente: {item.get('source_type', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(detail, title="Detalle")
        self.ctx.drawer.open()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()


class SessionWorkspace(QTabWidget):
    """Session space divided into Campaña, Preparación and En vivo/Post."""

    def __init__(self, ctx: AppContext, *, campaign_view, faction_view, session_view,
                 live_post_view, secrets_view, issues_view=None):
        super().__init__()
        self.ctx = ctx
        self.overview = SessionOverview(ctx)
        self.preparation = SessionPreparationWorkspace(ctx)
        self.campaign_view = campaign_view
        self.faction_view = faction_view
        self.session_view = session_view
        self.live_post_view = live_post_view
        self.secrets_view = secrets_view
        self.issues_view = issues_view
        self.addTab(self.overview, "Resumen")
        self.addTab(self.preparation, "Preparación")
        self.addTab(self.campaign_view, "Campaña")
        self.technical_session_index = self.addTab(self.session_view, "Preparación técnica")
        self.addTab(self.faction_view, "Facciones/Frentes")
        self.addTab(self.secrets_view, "Secretos/Pistas")
        self.addTab(self.live_post_view, "En vivo/Post")
        if self.issues_view is not None:
            self.addTab(self.issues_view, "Incidencias")
        self.set_advanced_mode(bool(ctx.advanced_mode))

    def refresh(self):
        for widget in [self.overview, self.preparation, self.campaign_view, self.session_view, self.faction_view,
                       self.secrets_view, self.live_post_view, self.issues_view]:
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()

    def set_advanced_mode(self, enabled: bool):
        if hasattr(self.overview, "set_advanced_mode"):
            self.overview.set_advanced_mode(enabled)
        if hasattr(self.preparation, "set_advanced_mode"):
            self.preparation.set_advanced_mode(enabled)
        self.setTabVisible(self.technical_session_index, bool(enabled))


class SessionPreparationWorkspace(QWidget):
    """Immersive preparation view: scenes, secrets and clues without live/post execution."""

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.selected_session_id: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Preparación",
            "Escenas, secretos y pistas de la próxima sesión. Sin modo live ni mutaciones de canon."
        ))
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Sesión:"))
        self.session_selector = QComboBox()
        self.session_selector.currentIndexChanged.connect(self._session_changed)
        controls.addWidget(self.session_selector, 1)
        self.summary_label = QLabel("Sin sesión")
        self.summary_label.setObjectName("mutedLabel")
        controls.addWidget(self.summary_label)
        header_layout.addLayout(controls)
        root.addWidget(header)

        self.container = QWidget()
        self.cards = QVBoxLayout(self.container)
        self.cards.setContentsMargins(22, 22, 22, 22)
        self.cards.setSpacing(14)
        root.addWidget(make_scroll_area(self.container), 1)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _is_gm(self) -> bool:
        return str(getattr(self.ctx, "current_audience", "gm") or "gm").lower() == "gm"

    def _clear(self):
        while self.cards.count():
            item = self.cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _session_changed(self):
        self.selected_session_id = self.session_selector.currentData()
        self.refresh()

    def _sessions(self, project):
        sessions = list(getattr(project, "sessions", []) or [])
        return sorted(sessions, key=lambda s: (getattr(s, "session_number", 0), getattr(s, "name", "")))

    def _selected_session(self, project):
        sessions = self._sessions(project)
        if not sessions:
            return None
        if self.selected_session_id:
            for session in sessions:
                if getattr(session, "id", "") == self.selected_session_id:
                    return session
        self.selected_session_id = getattr(sessions[0], "id", "")
        return sessions[0]

    def _populate_selector(self, project):
        sessions = self._sessions(project)
        current = self.selected_session_id
        self.session_selector.blockSignals(True)
        self.session_selector.clear()
        for session in sessions:
            number = getattr(session, "session_number", 0)
            label = getattr(session, "name", "Sesión")
            if number:
                label = f"#{number} · {label}"
            self.session_selector.addItem(label, getattr(session, "id", ""))
        if current:
            idx = self.session_selector.findData(current)
            if idx >= 0:
                self.session_selector.setCurrentIndex(idx)
        self.session_selector.blockSignals(False)

    def _detail(self, title: str, subtitle: str, obj, rows: list[tuple[str, str]]):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de preparación")
            return
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        layout.addWidget(SectionHeader(title, subtitle))
        for label, value in rows:
            line = QHBoxLayout()
            left = QLabel(label)
            left.setObjectName("mutedLabel")
            line.addWidget(left)
            right = QLabel(value or "—")
            right.setWordWrap(True)
            line.addWidget(right, 1)
            layout.addLayout(line)
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {getattr(obj, 'id', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(panel, title="Preparación")
        self.ctx.drawer.open()

    def _scene_card(self, scene, kind: str):
        title = getattr(scene, "name", "Escena")
        subtitle = getattr(scene, "description", "") or getattr(scene, "notes", "") or "Escena preparada"
        card = Card(title, subtitle)
        row = card.add_row()
        scene_type = enum_human(str(getattr(getattr(scene, "scene_type", None), "value", getattr(scene, "scene_type", kind))))
        row.addWidget(Badge(scene_type, "info" if kind == "prevista" else "warning"))
        row.addWidget(Badge(f"Orden {getattr(scene, 'order', 0)}", "success"))
        row.addStretch()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._detail(title, "Escena", scene, [
            ("Tipo", scene_type),
            ("Descripción", getattr(scene, "description", "") or "—"),
            ("Notas", getattr(scene, "notes", "") or "—"),
            ("NPCs", str(len(getattr(scene, "npc_ids", []) or []))),
        ]))
        row.addWidget(btn)
        return card

    def _secret_card(self, secret):
        state = enum_human(str(getattr(getattr(secret, "revelation_state", None), "value", getattr(secret, "revelation_state", "oculto"))))
        title = "Secreto" if not self._is_gm() else (getattr(secret, "content", "")[:80] or "Secreto")
        subtitle = "Oculto para jugadores" if not self._is_gm() else getattr(secret, "content", "")
        card = Card(title, subtitle)
        row = card.add_row()
        row.addWidget(Badge(state, "danger" if "oculto" in state.lower() else "success"))
        row.addWidget(Badge(f"Importancia {getattr(secret, 'importance', 3)}", "warning"))
        row.addStretch()
        if self._is_gm():
            btn = QPushButton("Detalle")
            btn.clicked.connect(lambda: self._detail("Secreto", state, secret, [
                ("Contenido", getattr(secret, "content", "") or "—"),
                ("Consecuencias", ", ".join(getattr(secret, "revelation_consequences", []) or []) or "—"),
                ("Pistas asociadas", str(len(getattr(secret, "associated_clue_ids", []) or []))),
            ]))
            row.addWidget(btn)
        return card

    def _clue_card(self, clue):
        state_raw = str(getattr(getattr(clue, "delivery_state", None), "value", getattr(clue, "delivery_state", "pendiente")))
        state = enum_human(state_raw)
        form = enum_human(str(getattr(getattr(clue, "delivery_form", None), "value", getattr(clue, "delivery_form", "pista"))))
        card = Card(form, getattr(clue, "content", "") or "Pista preparada")
        row = card.add_row()
        row.addWidget(Badge(state, "success" if state_raw == "entregada" else "warning"))
        row.addWidget(Badge(f"Claridad {getattr(clue, 'clarity', 3)}", "info"))
        row.addStretch()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._detail("Pista", state, clue, [
            ("Contenido", getattr(clue, "content", "") or "—"),
            ("Interpretación probable", getattr(clue, "probable_interpretation", "") or "—"),
            ("Riesgo de pérdida", str(getattr(clue, "loss_risk", 3))),
        ]))
        row.addWidget(btn)
        return card

    def _session_clues(self, project, session):
        ids = set(getattr(session, "available_clue_ids", []) or [])
        session_id = getattr(session, "id", "")
        clues = []
        for clue in getattr(project, "clues", []) or []:
            if getattr(clue, "id", "") in ids or session_id in (getattr(clue, "planned_session_ids", []) or []) or getattr(clue, "delivered_session_id", None) == session_id:
                clues.append(clue)
        return clues

    def _session_secrets(self, project, session):
        ids = set(getattr(session, "revealable_secret_ids", []) or [])
        session_id = getattr(session, "id", "")
        secrets = []
        for secret in getattr(project, "secrets", []) or []:
            if getattr(secret, "id", "") in ids or session_id in (getattr(secret, "planned_revelation_session_ids", []) or []) or getattr(secret, "actual_revelation_session_id", None) == session_id:
                secrets.append(secret)
        return secrets

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.session_selector.clear()
            self.summary_label.setText("Sin proyecto")
            self.cards.addWidget(EmptyState("Sin proyecto", "Abre un proyecto para preparar sesión."))
            self.cards.addStretch()
            return
        self._populate_selector(project)
        session = self._selected_session(project)
        if session is None:
            self.summary_label.setText("Sin sesiones")
            self.cards.addWidget(EmptyState("Sin sesiones", "Crea una sesión para preparar escenas, pistas y secretos."))
            self.cards.addStretch()
            return
        state = enum_human(str(getattr(getattr(session, "state", None), "value", getattr(session, "state", "preparacion"))))
        self.summary_label.setText(state)
        summary = Card(getattr(session, "name", "Sesión"), getattr(session, "context_summary", "") or getattr(session, "player_safe_summary", "") or "Preparación de sesión")
        row = summary.add_row()
        row.addWidget(Badge(state, "info"))
        row.addWidget(Badge(f"Escenas {len(getattr(session, 'planned_scenes', []) or []) + len(getattr(session, 'optional_scenes', []) or [])}", "success"))
        row.addWidget(Badge(f"Pistas {len(self._session_clues(project, session))}", "warning"))
        row.addStretch()
        self.cards.addWidget(summary)

        self.cards.addWidget(SectionHeader("Escenas preparadas", "Navegación de escenas previstas y opcionales."))
        scenes = list(getattr(session, "planned_scenes", []) or []) + list(getattr(session, "optional_scenes", []) or [])
        scenes = sorted(scenes, key=lambda s: getattr(s, "order", 0))
        if scenes:
            for scene in scenes:
                kind = str(getattr(getattr(scene, "scene_type", None), "value", getattr(scene, "scene_type", "prevista")))
                self.cards.addWidget(self._scene_card(scene, kind))
        else:
            self.cards.addWidget(EmptyState("Sin escenas", "Añade escenas previstas u opcionales en la vista técnica o servicios existentes."))

        self.cards.addWidget(SectionHeader("Pistas", "Pendientes y entregadas para esta sesión."))
        clues = self._session_clues(project, session)
        if clues:
            for clue in clues:
                self.cards.addWidget(self._clue_card(clue))
        else:
            self.cards.addWidget(EmptyState("Sin pistas", "No hay pistas planificadas para esta sesión."))

        self.cards.addWidget(SectionHeader("Secretos", "Respeta visibilidad: contenido completo solo para GM."))
        secrets = self._session_secrets(project, session)
        if secrets:
            for secret in secrets:
                self.cards.addWidget(self._secret_card(secret))
        else:
            self.cards.addWidget(EmptyState("Sin secretos", "No hay secretos revelables planificados."))

        self.cards.addWidget(SectionHeader("Checklist", "Objetivos, continuidad y preguntas abiertas."))
        checklist = []
        if self._is_gm():
            checklist.extend(getattr(session, "gm_objectives", []) or [])
            checklist.extend(getattr(session, "continuity_checklist", []) or [])
            checklist.extend(getattr(session, "open_questions", []) or [])
        else:
            checklist.extend(getattr(session, "player_known_objectives", []) or [])
        if checklist:
            for item in checklist[:12]:
                self.cards.addWidget(Card("•", str(item)))
        else:
            self.cards.addWidget(EmptyState("Sin checklist", "No hay elementos de preparación pendientes."))
        self.cards.addStretch()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()


class SessionOverview(QWidget):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.selected_campaign_id: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(10)
        header_layout.addWidget(SectionHeader(
            "Sesión",
            "Estado de campaña para dirigir: relojes, frentes y facciones en una sola superficie tranquila."
        ))
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Campaña:"))
        self.campaign_selector = QComboBox()
        self.campaign_selector.currentIndexChanged.connect(self._campaign_changed)
        controls.addWidget(self.campaign_selector, 1)
        self.status_label = QLabel("Sin campaña")
        self.status_label.setObjectName("mutedLabel")
        controls.addWidget(self.status_label)
        header_layout.addLayout(controls)
        root.addWidget(header)

        self.container = QWidget()
        self.layout_cards = QVBoxLayout(self.container)
        self.layout_cards.setContentsMargins(22, 22, 22, 22)
        self.layout_cards.setSpacing(14)
        root.addWidget(make_scroll_area(self.container), 1)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _clear(self):
        while self.layout_cards.count():
            item = self.layout_cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _campaign_changed(self):
        self.selected_campaign_id = self.campaign_selector.currentData()
        self.refresh()

    def _campaigns(self, project):
        return list(getattr(project, "campaigns", []) or [])

    def _selected_campaign(self, project):
        campaigns = self._campaigns(project)
        if not campaigns:
            return None
        if self.selected_campaign_id:
            for campaign in campaigns:
                if getattr(campaign, "id", "") == self.selected_campaign_id:
                    return campaign
        self.selected_campaign_id = getattr(campaigns[0], "id", "")
        return campaigns[0]

    def _populate_campaign_selector(self, project):
        campaigns = self._campaigns(project)
        current = self.selected_campaign_id
        self.campaign_selector.blockSignals(True)
        self.campaign_selector.clear()
        for campaign in campaigns:
            self.campaign_selector.addItem(getattr(campaign, "name", "Campaña"), getattr(campaign, "id", ""))
        if current:
            idx = self.campaign_selector.findData(current)
            if idx >= 0:
                self.campaign_selector.setCurrentIndex(idx)
        self.campaign_selector.blockSignals(False)

    def _clocks_for_campaign(self, project, campaign):
        ids = set(getattr(campaign, "clock_ids", []) or [])
        clocks = list(getattr(project, "campaign_clocks", []) or [])
        return [clock for clock in clocks if not ids or getattr(clock, "id", "") in ids]

    def _fronts_for_campaign(self, project, campaign):
        campaign_clock_ids = set(getattr(campaign, "clock_ids", []) or [])
        campaign_sessions = set(getattr(campaign, "session_ids", []) or [])
        fronts = []
        for front in getattr(project, "fronts", []) or []:
            if getattr(front, "clock_id", None) in campaign_clock_ids:
                fronts.append(front)
                continue
            if campaign_sessions and set(getattr(front, "session_ids", []) or []) & campaign_sessions:
                fronts.append(front)
        return fronts or list(getattr(project, "fronts", []) or [])

    def _factions_for_campaign(self, project, campaign):
        active_entities = set(getattr(campaign, "active_faction_entity_ids", []) or [])
        factions = []
        for faction in getattr(project, "factions", []) or []:
            if not active_entities or getattr(faction, "entity_id", "") in active_entities or getattr(faction, "id", "") in active_entities:
                factions.append(faction)
        return factions

    def _progress_card(self, clock):
        current = max(0, int(getattr(clock, "current_value", 0) or 0))
        max_value = max(1, int(getattr(clock, "max_value", 1) or 1))
        card = Card(getattr(clock, "name", "Clock"), getattr(clock, "description", "") or "Reloj de campaña")
        row = card.add_row()
        row.addWidget(Badge(enum_human(str(getattr(getattr(clock, "state", None), "value", getattr(clock, "state", "activo")))), "warning"))
        row.addStretch()
        bar = QProgressBar()
        bar.setRange(0, max_value)
        bar.setValue(min(current, max_value))
        bar.setFormat(f"{current}/{max_value}")
        card.layout().addWidget(bar)
        btn_row = card.add_row()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._open_detail("Clock", clock, [
            ("Estado", enum_human(str(getattr(getattr(clock, "state", None), "value", getattr(clock, "state", ""))))),
            ("Progreso", f"{current}/{max_value}"),
            ("Condiciones de avance", ", ".join(getattr(clock, "advance_conditions", []) or []) or "—"),
        ]))
        btn_row.addStretch()
        btn_row.addWidget(btn)
        return card

    def _simple_card(self, title: str, subtitle: str, badge: str, tone: str, obj, details: list[tuple[str, str]]):
        card = Card(title, subtitle or "Sin descripción")
        row = card.add_row()
        row.addWidget(Badge(badge, tone))
        row.addStretch()
        btn = QPushButton("Detalle")
        btn.clicked.connect(lambda: self._open_detail(badge, obj, details))
        row.addWidget(btn)
        return card

    def _open_detail(self, title: str, obj, details: list[tuple[str, str]]):
        if self.ctx.drawer is None:
            self.ctx.log("error", "No se pudo abrir detalle de sesión")
            return
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        name = getattr(obj, "name", title)
        layout.addWidget(SectionHeader(str(name), title))
        description = getattr(obj, "description", "") or getattr(obj, "relation_with_pcs", "") or "Sin descripción"
        desc = QLabel(str(description))
        desc.setWordWrap(True)
        layout.addWidget(desc)
        for label, value in details:
            row = QHBoxLayout()
            left = QLabel(label)
            left.setObjectName("mutedLabel")
            row.addWidget(left)
            value_label = QLabel(value or "—")
            value_label.setWordWrap(True)
            row.addWidget(value_label, 1)
            layout.addLayout(row)
        technical = QTextEdit()
        technical.setReadOnly(True)
        technical.setPlainText(f"ID: {getattr(obj, 'id', '')}")
        technical.setVisible(self._advanced_mode)
        layout.addWidget(technical)
        layout.addStretch()
        self.ctx.drawer.set_content(panel, title="Sesión")
        self.ctx.drawer.open()

    def refresh(self):
        self._clear()
        project = self._project()
        if project is None:
            self.campaign_selector.clear()
            self.status_label.setText("Sin proyecto")
            self.layout_cards.addWidget(EmptyState("Sin proyecto", "Abre un proyecto desde Configuración."))
            self.layout_cards.addStretch()
            return
        self._populate_campaign_selector(project)
        campaign = self._selected_campaign(project)
        if campaign is None:
            self.status_label.setText("Sin campañas")
            self.layout_cards.addWidget(EmptyState("Sin campañas", "Crea una campaña para preparar sesiones."))
            self.layout_cards.addStretch()
            return
        self.status_label.setText(enum_human(str(getattr(getattr(campaign, "state", None), "value", getattr(campaign, "state", "activa")))))
        summary = Card(getattr(campaign, "name", "Campaña"), getattr(campaign, "description", "") or "Campaña activa")
        row = summary.add_row()
        for label, value, tone in [
            ("Sistema", getattr(campaign, "game_system", "") or "—", "info"),
            ("Tono", getattr(campaign, "tone", "") or "—", "info"),
            ("Sesiones", str(len(getattr(campaign, "session_ids", []) or [])), "success"),
            ("Jugadores", str(len(getattr(campaign, "players", []) or [])), "success"),
        ]:
            row.addWidget(Badge(f"{label}: {value}", tone))
        row.addStretch()
        detail_row = summary.add_row()
        detail_btn = QPushButton("Detalle campaña")
        detail_btn.clicked.connect(lambda: self._open_detail("Campaña", campaign, [
            ("Sistema", getattr(campaign, "game_system", "") or "—"),
            ("Tono", getattr(campaign, "tone", "") or "—"),
            ("Género", getattr(campaign, "genre", "") or "—"),
        ]))
        detail_row.addStretch()
        detail_row.addWidget(detail_btn)
        self.layout_cards.addWidget(summary)

        clocks = self._clocks_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Clocks", "Progreso visual de amenazas, frentes y cuenta atrás."))
        if clocks:
            for clock in clocks:
                self.layout_cards.addWidget(self._progress_card(clock))
        else:
            self.layout_cards.addWidget(EmptyState("Sin clocks", "No hay relojes asociados a esta campaña."))

        fronts = self._fronts_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Frentes activos", "Procesos dinámicos y amenazas de la campaña."))
        if fronts:
            for front in fronts:
                stage = getattr(front, "current_stage_index", 0)
                stages = getattr(front, "stages", []) or []
                subtitle = getattr(front, "description", "") or (stages[stage].description if stages and stage < len(stages) else "Frente narrativo")
                self.layout_cards.addWidget(self._simple_card(
                    getattr(front, "name", "Frente"),
                    subtitle,
                    enum_human(str(getattr(getattr(front, "state", None), "value", getattr(front, "state", "latente")))),
                    "warning",
                    front,
                    [("Etapa", f"{stage + 1}/{len(stages) or 1}"), ("Tipo", enum_human(str(getattr(getattr(front, "front_type", None), "value", getattr(front, "front_type", "frente")))))]
                ))
        else:
            self.layout_cards.addWidget(EmptyState("Sin frentes", "No hay frentes activos para esta campaña."))

        factions = self._factions_for_campaign(project, campaign)
        self.layout_cards.addWidget(SectionHeader("Facciones", "Actores activos y relaciones de presión."))
        if factions:
            for faction in factions:
                self.layout_cards.addWidget(self._simple_card(
                    getattr(faction, "name", "Facción"),
                    getattr(faction, "relation_with_pcs", "") or getattr(faction, "ideology", "") or "Facción activa",
                    enum_human(str(getattr(getattr(faction, "state", None), "value", getattr(faction, "state", "activa")))),
                    "info",
                    faction,
                    [("Aliados", str(len(getattr(faction, "ally_faction_ids", []) or []))), ("Enemigos", str(len(getattr(faction, "enemy_faction_ids", []) or []))), ("Recursos", ", ".join(getattr(faction, "resources", []) or []) or "—")]
                ))
        else:
            self.layout_cards.addWidget(EmptyState("Sin facciones", "No hay facciones activas vinculadas."))

        self.layout_cards.addWidget(SectionHeader("Siguientes zonas", "Preparación/escenas y Live/Post se completan en T10B/T10C."))
        self.layout_cards.addWidget(EmptyState("Preparación y Live/Post", "Placeholder deliberado de T10A; se implementa en los tickets siguientes."))
        self.layout_cards.addStretch()

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
        self.refresh()


class _SuggestWorker(QThread):
    """Background worker for AI suggestions (nodes or relations) — keeps UI responsive."""

    def __init__(self, ai_controller, action: str, entity_ids: list[str] | None = None, relation_ids: list[str] | None = None):
        super().__init__()
        self.ai_controller = ai_controller
        self.action = action
        self.entity_ids = entity_ids or []
        self.relation_ids = relation_ids or []
        self.result = None

    def run(self):
        try:
            self.result = self.ai_controller.graph_action(
                self.action,
                entity_ids=self.entity_ids,
                relation_ids=self.relation_ids,
            )
        except Exception as exc:
            from packages.domain.result import Error as _Err
            self.result = _Err(f"Worker exception: {exc}")
