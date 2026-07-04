"""Related milestone section for Creation detail panels (H04)."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import Badge, Card, EmptyState, enum_human
from hosts.DesktopHostPySide.widgets.milestone_labels import (
    milestone_primary_entity_id,
    milestone_sort_value,
    milestone_temporal_label,
    stable_entity_color,
)
from packages.domain.result import Error


def _raw_enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _metadata(obj: Any) -> dict[str, Any]:
    value = getattr(obj, "metadata", {}) or {}
    return dict(value) if isinstance(value, dict) else {}


def _unwrap(value: Any) -> Any:
    if isinstance(value, Error):
        return None
    return getattr(value, "value", value)


class RelatedMilestonesPanel(QGroupBox):
    """Compact, human-facing related milestone list for one selected element."""

    def __init__(
        self,
        *,
        milestone_controller: Any,
        target_kind: str,
        target_id: str,
        project_getter: Callable[[], Any] | None = None,
        entity_controller: Any = None,
        relation_controller: Any = None,
        on_open_chronology: Callable[[str, str, str], None] | None = None,
        on_suggest_milestone: Callable[[str, str], None] | None = None,
        on_created: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__("Causas / Hitos", parent)
        self.milestone_controller = milestone_controller
        self.target_kind = str(target_kind or "entity")
        self.target_id = str(target_id or "")
        self.project_getter = project_getter
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.on_open_chronology = on_open_chronology
        self.on_suggest_milestone = on_suggest_milestone
        self.on_created = on_created

        self.setObjectName("relatedMilestonesPanel")
        self.setCheckable(False)
        self.setStyleSheet(
            "QGroupBox#relatedMilestonesPanel { color: #6F6A42; font-weight: 600; "
            "border: 1px solid #D8D6C8; border-radius: 10px; margin-top: 8px; "
            "padding-top: 14px; background: transparent; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(10, 8, 10, 10)
        self.root.setSpacing(8)

        actions = QHBoxLayout()
        self.open_btn = QPushButton("Ver en cronologia")
        self.open_btn.setObjectName("openRelatedMilestonesChronology")
        self.open_btn.clicked.connect(self._open_chronology)
        actions.addWidget(self.open_btn)
        self.suggest_btn = QPushButton("Sugerir hito")
        self.suggest_btn.setObjectName("suggestRelatedMilestoneButton")
        self.suggest_btn.setVisible(callable(self.on_suggest_milestone))
        self.suggest_btn.clicked.connect(self._suggest_related)
        actions.addWidget(self.suggest_btn)
        actions.addStretch(1)
        self.create_btn = QPushButton("Crear hito vinculado")
        self.create_btn.setObjectName("createLinkedMilestoneButton")
        self.create_btn.setVisible(callable(getattr(self.milestone_controller, "create_manual", None)))
        self.create_btn.clicked.connect(self._create_linked)
        actions.addWidget(self.create_btn)
        self.root.addLayout(actions)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)
        self.root.addWidget(self.body)
        self.body.setVisible(True)

        self.refresh()

    def project(self) -> Any:
        if self.project_getter is not None:
            return self.project_getter()
        ps = getattr(self.milestone_controller, "ps", None)
        return getattr(ps, "active_project", None)

    def entities(self) -> list[Any]:
        if self.entity_controller is not None and hasattr(self.entity_controller, "list_all"):
            return list(self.entity_controller.list_all())
        project = self.project()
        return list(getattr(project, "entities", []) or [])

    def relations(self) -> list[Any]:
        if self.relation_controller is not None and hasattr(self.relation_controller, "list_all"):
            return list(self.relation_controller.list_all())
        project = self.project()
        return list(getattr(project, "relations", []) or [])

    def entity_by_id(self, entity_id: str) -> Any | None:
        for entity in self.entities():
            if str(getattr(entity, "id", "")) == str(entity_id):
                return entity
        return None

    def entity_name(self, entity_id: str) -> str:
        entity = self.entity_by_id(entity_id)
        return str(getattr(entity, "name", "") or "Elemento vinculado") if entity else "Elemento vinculado"

    def relation_by_id(self, relation_id: str) -> Any | None:
        if self.relation_controller is not None and hasattr(self.relation_controller, "get"):
            value = _unwrap(self.relation_controller.get(relation_id))
            if value is not None:
                return value
        for relation in self.relations():
            if str(getattr(relation, "id", "")) == str(relation_id):
                return relation
        return None

    def related_milestones(self) -> list[Any]:
        items: list[Any] = []
        if self.milestone_controller is None:
            return []
        method_name = {
            "entity": "list_for_leaf",
            "branch": "list_for_branch",
            "relation": "list_for_relation",
        }.get(self.target_kind, "list_for_leaf")
        if hasattr(self.milestone_controller, method_name):
            items.extend(list(_unwrap(getattr(self.milestone_controller, method_name)(self.target_id)) or []))
        if hasattr(self.milestone_controller, "list_all"):
            for hito in list(self.milestone_controller.list_all()):
                if self._is_related(hito):
                    items.append(hito)
        by_id: dict[str, Any] = {}
        for hito in items:
            hito_id = str(getattr(hito, "id", ""))
            if hito_id:
                by_id[hito_id] = hito
        return sorted(by_id.values(), key=milestone_sort_value)

    def _is_related(self, hito: Any) -> bool:
        target = self.target_id
        if not target:
            return False
        if self.target_kind in {"entity", "branch"}:
            if target in [str(v) for v in (getattr(hito, "affected_entity_ids", []) or [])]:
                return True
            if target in [str(v) for v in (getattr(hito, "affected_branch_ids", []) or [])]:
                return True
            return milestone_primary_entity_id(hito) == target
        if self.target_kind == "relation":
            return target in [str(v) for v in (getattr(hito, "caused_relation_ids", []) or [])]
        return False

    def refresh(self) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        hitos = self.related_milestones()
        if not hitos:
            self.body_layout.addWidget(EmptyState(
                "No hay hitos vinculados.",
                "Los hitos sirven para explicar como este elemento llego a ser lo que es.",
            ))
            return
        for hito in hitos:
            self.body_layout.addWidget(self._card_for(hito))

    def _card_for(self, hito: Any) -> Card:
        title = str(getattr(hito, "title", "") or "Hito sin titulo")
        card = Card(title, milestone_temporal_label(hito))
        card.setObjectName("relatedMilestoneCard")
        row = card.add_row()
        primary_id = milestone_primary_entity_id(hito)
        primary = self.entity_by_id(primary_id)
        color = stable_entity_color(primary, primary_id or title)
        swatch = QLabel("")
        swatch.setObjectName("relatedMilestoneColorSwatch")
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(f"background: {color}; border-radius: 7px;")
        row.addWidget(swatch)
        if primary_id:
            row.addWidget(Badge(self.entity_name(primary_id), "info"))
        row.addWidget(Badge(enum_human(_raw_enum(getattr(hito, "status", ""))), "neutral"))
        row.addStretch(1)
        open_btn = QPushButton("Abrir")
        open_btn.setObjectName("openRelatedMilestoneDetail")
        open_btn.clicked.connect(lambda _=False, hid=str(getattr(hito, "id", "")): self._open_chronology(hid))
        row.addWidget(open_btn)

        summary = str(getattr(hito, "description", "") or getattr(hito, "rationale", "") or "").strip()
        if summary:
            card.add_text(summary[:220], muted=True)
        linked = [self.entity_name(eid) for eid in (getattr(hito, "affected_entity_ids", []) or [])]
        if linked:
            card.add_text("Elementos: " + ", ".join(linked[:5]), muted=True)
        return card

    def _open_chronology(self, hito_id: str = "") -> None:
        if self.on_open_chronology is not None:
            self.on_open_chronology(self.target_kind, self.target_id, str(hito_id or ""))

    def _suggest_related(self) -> None:
        if self.on_suggest_milestone is not None:
            self.on_suggest_milestone(self.target_kind, self.target_id)

    def _create_linked(self) -> None:
        if self.milestone_controller is None or not callable(getattr(self.milestone_controller, "create_manual", None)):
            return
        existing = []
        if hasattr(self.milestone_controller, "list_all"):
            existing = list(self.milestone_controller.list_all())
        payload = {
            "title": "Nuevo hito vinculado",
            "description": "",
            "metadata": {"sort_index": len(existing) + 1},
        }
        if self.target_kind == "relation":
            payload["caused_relation_ids"] = [self.target_id]
            relation = self.relation_by_id(self.target_id)
            endpoints = [
                str(getattr(relation, "source_id", "") or ""),
                str(getattr(relation, "target_id", "") or ""),
            ] if relation is not None else []
            payload["affected_entity_ids"] = [eid for eid in endpoints if eid]
        else:
            # BETA1-HITO-MULTI: la entidad objetivo participa sin ser "principal".
            payload["affected_entity_ids"] = [self.target_id]
            if self.target_kind == "branch":
                payload["affected_branch_ids"] = [self.target_id]
        result = self.milestone_controller.create_manual(payload)
        if isinstance(result, Error):
            return
        if self.on_created is not None:
            self.on_created()
        self.refresh()
