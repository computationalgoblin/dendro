"""H03: milestone chronology drawer view."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.result import Ok

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.milestone_chronology_view import (
        MilestoneChronologyView,
        milestone_sort_value,
        stable_entity_color,
    )


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

ROOT = Path(__file__).resolve().parents[2]
VIEW_SOURCE = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "milestone_chronology_view.py"
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def entity(entity_id: str, name: str, color: str = ""):
    meta = {"color": color} if color else {}
    return SimpleNamespace(id=entity_id, name=name, custom_metadata=meta)


class FakeMilestoneController:
    def __init__(self, hitos=None):
        self.hitos = list(hitos or [])
        self.updated: list[tuple[str, dict]] = []

    def list_all(self):
        return list(self.hitos)

    def update(self, hito_id: str, data: dict):
        self.updated.append((hito_id, data))
        for idx, hito in enumerate(self.hitos):
            if hito.id == hito_id:
                merged = hito.to_dict()
                merged.update(data)
                self.hitos[idx] = CausalMilestone.from_dict(merged)
                return Ok(self.hitos[idx])
        return Ok(None)

    def create_manual(self, data: dict):
        hito = CausalMilestone.from_dict({"id": f"hito-{len(self.hitos) + 1}", **data})
        self.hitos.append(hito)
        return Ok(hito)

    def delete(self, hito_id: str):
        for index, hito in enumerate(list(self.hitos)):
            if hito.id == hito_id:
                return Ok(self.hitos.pop(index))
        return Ok(None)


class FakeEntityController:
    def __init__(self, entities):
        self._entities = list(entities)

    def list_all(self):
        return list(self._entities)


def make_view(qapp, hitos=None, entities=None):
    entities = entities or [
        entity("ent-a", "Aster", "#336699"),
        entity("ent-b", "Bruma"),
    ]
    ctrl = FakeMilestoneController(hitos or [])
    view = MilestoneChronologyView(
        ctrl,
        project_getter=lambda: SimpleNamespace(entities=entities, causal_milestones=ctrl.hitos),
        entity_controller=FakeEntityController(entities),
    )
    return view, ctrl


def labels_and_buttons(widget) -> list[str]:
    texts = []
    for label in widget.findChildren(QLabel):
        if label.text():
            texts.append(label.text())
    for button in widget.findChildren(QPushButton):
        if button.text():
            texts.append(button.text())
    return texts


def test_view_can_be_instantiated(qapp):
    view, _ = make_view(qapp)

    assert isinstance(view, MilestoneChronologyView)


def test_empty_project_shows_empty_state(qapp):
    view, _ = make_view(qapp, hitos=[])

    assert any("No hay hitos todavia." in text for text in labels_and_buttons(view))


def test_milestones_are_ordered_by_sort_index(qapp):
    late = CausalMilestone(id="hito-late", title="Tarde", metadata={"sort_index": 20})
    early = CausalMilestone(id="hito-early", title="Temprano", metadata={"sort_index": 1})
    view, _ = make_view(qapp, hitos=[late, early])

    ordered = [h.title for h in view.filtered_milestones()]

    assert ordered == ["Temprano", "Tarde"]
    assert milestone_sort_value(early) < milestone_sort_value(late)


def test_text_filter_matches_title_summary_and_body(qapp):
    hitos = [
        CausalMilestone(id="hito-1", title="Guerra solar", description="Nada"),
        CausalMilestone(id="hito-2", title="Pacto lunar", metadata={"body": "Juramento secreto"}),
    ]
    view, _ = make_view(qapp, hitos=hitos)

    view.search_input.setText("secreto")

    assert [h.title for h in view.filtered_milestones()] == ["Pacto lunar"]


def test_entity_filter_matches_linked_entity(qapp):
    hitos = [
        CausalMilestone(id="hito-1", title="Aster cae", affected_entity_ids=["ent-a"]),
        CausalMilestone(id="hito-2", title="Bruma asciende", affected_entity_ids=["ent-b"]),
    ]
    view, _ = make_view(qapp, hitos=hitos)

    idx = view.entity_filter.findData("ent-b")
    view.entity_filter.setCurrentIndex(idx)

    assert [h.title for h in view.filtered_milestones()] == ["Bruma asciende"]


def test_primary_entity_has_visual_color_marker(qapp):
    hito = CausalMilestone(
        id="hito-1",
        title="Fundacion",
        affected_entity_ids=["ent-a"],
        metadata={"primary_entity_id": "ent-a"},
    )
    view, _ = make_view(qapp, hitos=[hito])

    assert stable_entity_color(entity("ent-a", "Aster", "#336699")) == "#336699"
    assert view.findChildren(QLabel, "milestoneColorSwatch")


def test_selecting_milestone_opens_detail(qapp):
    hito = CausalMilestone(id="hito-1", title="Fundacion")
    view, _ = make_view(qapp, hitos=[hito])

    view.select_milestone("hito-1")

    assert not view.detail_frame.isHidden()
    assert view.title_edit.text() == "Fundacion"


def test_editing_title_summary_and_body_updates_model_through_controller(qapp):
    hito = CausalMilestone(id="hito-1", title="Viejo", description="Resumen viejo")
    view, ctrl = make_view(qapp, hitos=[hito])

    view.select_milestone("hito-1")
    view.title_edit.setText("Nuevo titulo")
    view.summary_edit.setPlainText("Nuevo resumen")
    view.body_edit.setPlainText("Nuevo cuerpo")
    view._save_detail()

    assert ctrl.updated
    assert ctrl.hitos[0].title == "Nuevo titulo"
    assert ctrl.hitos[0].description == "Nuevo resumen"
    assert ctrl.hitos[0].metadata["body"] == "Nuevo cuerpo"


def _check_participant(view, entity_id: str, checked: bool = True) -> None:
    for row in range(view.participants_list.count()):
        item = view.participants_list.item(row)
        if str(item.data(Qt.ItemDataRole.UserRole)) == entity_id:
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            return
    raise AssertionError(f"participante {entity_id} no está en la lista")


def _participant_checked(view, entity_id: str) -> bool:
    for row in range(view.participants_list.count()):
        item = view.participants_list.item(row)
        if str(item.data(Qt.ItemDataRole.UserRole)) == entity_id:
            return item.checkState() == Qt.CheckState.Checked
    return False


def test_participants_multiselect_premarks_affected_entities(qapp):
    # BETA1-HITO-MULTI: la lista marca las entidades ya participantes.
    hito = CausalMilestone(id="hito-1", title="Pacto", affected_entity_ids=["ent-a"])
    view, _ = make_view(qapp, hitos=[hito])

    view.select_milestone("hito-1")

    assert _participant_checked(view, "ent-a")
    assert not _participant_checked(view, "ent-b")


def test_saving_multiselect_persists_all_participants_without_primary(qapp):
    # BETA1-HITO-MULTI: guardar escribe el conjunto marcado y NO primary_entity_id.
    hito = CausalMilestone(
        id="hito-1",
        title="Pacto",
        affected_entity_ids=["ent-a"],
        metadata={"primary_entity_id": "ent-a"},
    )
    view, ctrl = make_view(qapp, hitos=[hito])

    view.select_milestone("hito-1")
    _check_participant(view, "ent-b", checked=True)
    view._save_detail()

    saved = ctrl.hitos[0]
    assert sorted(saved.affected_entity_ids) == ["ent-a", "ent-b"]
    assert "primary_entity_id" not in saved.metadata


def test_legacy_primary_entity_is_premarked_for_backcompat(qapp):
    # BETA1-HITO-MULTI: proyectos antiguos con primary fuera de affected no pierden
    # el vínculo: se pre-marca igualmente.
    hito = CausalMilestone(
        id="hito-1",
        title="Antiguo",
        affected_entity_ids=[],
        metadata={"primary_entity_id": "ent-b"},
    )
    view, _ = make_view(qapp, hitos=[hito])

    view.select_milestone("hito-1")

    assert _participant_checked(view, "ent-b")


def test_delete_milestone_removes_it_through_controller(qapp):
    hito = CausalMilestone(id="hito-1", title="Eliminar")
    view, ctrl = make_view(qapp, hitos=[hito])

    view._delete_milestone("hito-1", confirm=False)

    assert ctrl.hitos == []
    assert view.filtered_milestones() == []


def test_normal_visible_text_does_not_show_ids_or_json(qapp):
    hito = CausalMilestone(id="hito-secret-id", title="Fundacion", affected_entity_ids=["ent-a"])
    view, _ = make_view(qapp, hitos=[hito])

    visible_text = "\n".join(labels_and_buttons(view))

    assert "hito-secret-id" not in visible_text
    assert "ent-a" not in visible_text
    assert "{" not in visible_text
    assert "JSON" not in visible_text


def test_view_source_does_not_instantiate_graph_nodes_or_touch_physics():
    text = VIEW_SOURCE.read_text(encoding="utf-8")
    workspace = WORKSPACES.read_text(encoding="utf-8")

    assert "GraphNodeItem" not in text
    assert "GraphCanvasWidget(" not in text
    assert "_physics_enabled" not in text
    assert "_layout_mode" not in text
    assert "MilestoneChronologyView" in workspace
    assert "_open_milestone_chronology_view" in workspace
