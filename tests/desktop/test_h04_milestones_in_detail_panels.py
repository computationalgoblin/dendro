"""H04: related milestones in Creation detail panels."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.result import Ok

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.related_milestones_panel import RelatedMilestonesPanel
    from hosts.DesktopHostPySide.widgets.milestone_chronology_view import MilestoneChronologyView


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

ROOT = Path(__file__).resolve().parents[2]
RELATED_SOURCE = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "related_milestones_panel.py"
NODE_SOURCE = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "node_detail_panel.py"
TREE_SOURCE = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "tree_detail_panel.py"
REL_SOURCE = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "relation_detail_panel.py"
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def entity(entity_id: str, name: str, color: str = ""):
    meta = {"color": color} if color else {}
    return SimpleNamespace(id=entity_id, name=name, custom_metadata=meta)


def relation(relation_id: str, source_id: str = "ent-a", target_id: str = "ent-b"):
    return SimpleNamespace(id=relation_id, source_id=source_id, target_id=target_id)


class FakeMilestoneController:
    def __init__(self, hitos=None, can_create: bool = True):
        self.hitos = list(hitos or [])
        self.created: list[dict] = []
        self.can_create = can_create

    def list_all(self):
        return list(self.hitos)

    def list_for_leaf(self, leaf_id: str):
        return [h for h in self.hitos if leaf_id in h.affected_entity_ids]

    def list_for_branch(self, branch_id: str):
        return [h for h in self.hitos if branch_id in h.affected_branch_ids]

    def list_for_relation(self, relation_id: str):
        return [h for h in self.hitos if relation_id in h.caused_relation_ids]

    def create_manual(self, data: dict):
        if not self.can_create:
            raise AssertionError("create_manual should not be called")
        self.created.append(dict(data))
        hito = CausalMilestone.from_dict({"id": f"hito-{len(self.hitos) + 1}", **data})
        self.hitos.append(hito)
        return Ok(hito)


class ReadOnlyMilestoneController(FakeMilestoneController):
    create_manual = None


class FakeEntityController:
    def __init__(self, entities):
        self._entities = list(entities)

    def list_all(self):
        return list(self._entities)


class FakeRelationController:
    def __init__(self, relations):
        self._relations = list(relations)

    def list_all(self):
        return list(self._relations)

    def get(self, relation_id: str):
        for rel in self._relations:
            if rel.id == relation_id:
                return Ok(rel)
        return Ok(None)


def visible_text(widget) -> str:
    texts = []
    for label in widget.findChildren(QLabel):
        if label.text():
            texts.append(label.text())
    for button in widget.findChildren(QPushButton):
        if button.text():
            texts.append(button.text())
    return "\n".join(texts)


def make_panel(kind: str, target_id: str, hitos=None, opened=None, controller=None):
    entities = [
        entity("ent-a", "Aster", "#336699"),
        entity("ent-b", "Bruma"),
        entity("branch-a", "Hermandad", "#663399"),
    ]
    relations = [relation("rel-a", "ent-a", "ent-b")]
    ctrl = controller or FakeMilestoneController(hitos or [])
    opened = opened if opened is not None else []
    panel = RelatedMilestonesPanel(
        milestone_controller=ctrl,
        target_kind=kind,
        target_id=target_id,
        project_getter=lambda: SimpleNamespace(entities=entities, relations=relations, causal_milestones=ctrl.hitos),
        entity_controller=FakeEntityController(entities),
        relation_controller=FakeRelationController(relations),
        on_open_chronology=lambda k, tid, hid: opened.append((k, tid, hid)),
    )
    return panel, ctrl, opened


def test_node_detail_source_mounts_causes_hitos_section():
    text = NODE_SOURCE.read_text(encoding="utf-8")

    assert "RelatedMilestonesPanel" in text
    assert 'target_kind="entity"' in text


def test_tree_detail_source_mounts_causes_hitos_section():
    text = TREE_SOURCE.read_text(encoding="utf-8")

    assert "RelatedMilestonesPanel" in text
    assert 'target_kind="branch"' in text


def test_relation_detail_source_mounts_causes_hitos_section():
    text = REL_SOURCE.read_text(encoding="utf-8")

    assert "RelatedMilestonesPanel" in text
    assert 'target_kind="relation"' in text


def test_empty_related_milestones_shows_human_empty_state(qapp):
    panel, _, _ = make_panel("entity", "ent-a", hitos=[])

    text = visible_text(panel)

    assert "Causas / Hitos" in panel.title()
    assert "No hay hitos vinculados." in text


def test_leaf_related_milestones_are_listed_without_ids_or_json(qapp):
    hito = CausalMilestone(
        id="hito-secret",
        title="Fundacion",
        description="La ciudad aprende a resistir.",
        affected_entity_ids=["ent-a"],
        metadata={"primary_entity_id": "ent-a", "chronology_key": "Era Primera"},
    )
    panel, _, _ = make_panel("entity", "ent-a", hitos=[hito])

    text = visible_text(panel)

    assert "Fundacion" in text
    assert "Era Primera" in text
    assert "Aster" in text
    assert "hito-secret" not in text
    assert "ent-a" not in text
    assert "{" not in text
    assert "JSON" not in text


def test_branch_related_milestones_use_branch_links(qapp):
    hito = CausalMilestone(
        id="hito-branch",
        title="Juramento comun",
        affected_branch_ids=["branch-a"],
        affected_entity_ids=["branch-a"],
    )
    panel, _, _ = make_panel("branch", "branch-a", hitos=[hito])

    assert "Juramento comun" in visible_text(panel)


def test_relation_related_milestones_use_relation_links(qapp):
    hito = CausalMilestone(id="hito-rel", title="Traicion", caused_relation_ids=["rel-a"])
    panel, _, _ = make_panel("relation", "rel-a", hitos=[hito])

    assert "Traicion" in visible_text(panel)


def test_primary_entity_uses_visual_color_marker(qapp):
    hito = CausalMilestone(
        id="hito-color",
        title="Ascenso",
        affected_entity_ids=["ent-a"],
        metadata={"primary_entity_id": "ent-a"},
    )
    panel, _, _ = make_panel("entity", "ent-a", hitos=[hito])

    swatches = panel.findChildren(QLabel, "relatedMilestoneColorSwatch")

    assert swatches
    assert "#336699" in swatches[0].styleSheet()


def test_open_chronology_action_emits_target_filter(qapp):
    panel, _, opened = make_panel("entity", "ent-a", hitos=[])
    button = panel.findChild(QPushButton, "openRelatedMilestonesChronology")

    assert button.isEnabled()
    button.click()

    assert opened == [("entity", "ent-a", "")]


def test_open_milestone_action_emits_selected_hito(qapp):
    hito = CausalMilestone(id="hito-open", title="Ruptura", affected_entity_ids=["ent-a"])
    panel, _, opened = make_panel("entity", "ent-a", hitos=[hito])

    panel.findChild(QPushButton, "openRelatedMilestoneDetail").click()

    assert opened == [("entity", "ent-a", "hito-open")]


def test_create_linked_milestone_from_leaf_uses_safe_controller(qapp):
    panel, ctrl, _ = make_panel("entity", "ent-a", hitos=[])
    button = panel.findChild(QPushButton, "createLinkedMilestoneButton")

    assert button.isEnabled()
    button.click()

    assert ctrl.created
    assert ctrl.created[0]["affected_entity_ids"] == ["ent-a"]
    assert ctrl.created[0]["metadata"]["primary_entity_id"] == "ent-a"


def test_create_linked_milestone_from_relation_adds_relation_and_endpoints(qapp):
    panel, ctrl, _ = make_panel("relation", "rel-a", hitos=[])

    panel.findChild(QPushButton, "createLinkedMilestoneButton").click()

    assert ctrl.created
    assert ctrl.created[0]["caused_relation_ids"] == ["rel-a"]
    assert ctrl.created[0]["affected_entity_ids"] == ["ent-a", "ent-b"]


def test_create_action_is_hidden_without_safe_route(qapp):
    ctrl = ReadOnlyMilestoneController([])
    panel, _, _ = make_panel("entity", "ent-a", controller=ctrl)

    assert panel.findChild(QPushButton, "createLinkedMilestoneButton").isHidden()


def test_h03_opens_with_initial_entity_and_relation_filters(qapp):
    hitos = [
        CausalMilestone(id="hito-a", title="Aster", affected_entity_ids=["ent-a"]),
        CausalMilestone(id="hito-r", title="Pacto", caused_relation_ids=["rel-a"]),
    ]
    ctrl = FakeMilestoneController(hitos)
    entities = [entity("ent-a", "Aster"), entity("ent-b", "Bruma")]
    relations = [relation("rel-a", "ent-a", "ent-b")]

    by_entity = MilestoneChronologyView(
        ctrl,
        project_getter=lambda: SimpleNamespace(entities=entities, relations=relations, causal_milestones=ctrl.hitos),
        entity_controller=FakeEntityController(entities),
        initial_entity_id="ent-a",
    )
    by_relation = MilestoneChronologyView(
        ctrl,
        project_getter=lambda: SimpleNamespace(entities=entities, relations=relations, causal_milestones=ctrl.hitos),
        entity_controller=FakeEntityController(entities),
        relation_controller=FakeRelationController(relations),
        initial_relation_id="rel-a",
        initial_hito_id="hito-r",
    )

    assert [h.title for h in by_entity.filtered_milestones()] == ["Aster"]
    assert [h.title for h in by_relation.filtered_milestones()] == ["Pacto"]
    assert by_relation._selected_hito_id == "hito-r"


def test_sources_do_not_instantiate_graph_nodes_or_touch_physics():
    text = "\n".join([
        RELATED_SOURCE.read_text(encoding="utf-8"),
        NODE_SOURCE.read_text(encoding="utf-8"),
        TREE_SOURCE.read_text(encoding="utf-8"),
        REL_SOURCE.read_text(encoding="utf-8"),
        WORKSPACES.read_text(encoding="utf-8"),
    ])

    assert "GraphNodeItem(" not in text
    assert "GraphCanvasWidget(" not in RELATED_SOURCE.read_text(encoding="utf-8")
    assert "_physics_enabled" not in RELATED_SOURCE.read_text(encoding="utf-8")
    assert "_layout_mode" not in RELATED_SOURCE.read_text(encoding="utf-8")
