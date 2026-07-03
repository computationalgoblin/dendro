"""Rail de herramientas de Foco: tooltips, iluminación por selección, popovers
y acciones end-to-end vía servicios (BETA2-FOCO-11)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.domain.entity import CanonState, NarrativeEntity  # noqa: E402 — tras el guard HAS_QT
from packages.domain.result import Ok  # noqa: E402 — tras el guard HAS_QT


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _setup():
    project_service = ProjectService()
    project_service.create("Rail")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.ghost_controller import GhostController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service),
    )
    view = FocoView(
        project_provider=lambda: project_service.active_project,
        last_entity_setter=project_service.set_last_worked_entity,
        ctx=ctx,
        entity_controller=EntityController(project_service),
        relation_controller=RelationController(project_service),
        ghost_service=GhostController(project_service),
    )
    return project_service, view


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


class TestRailBasics:
    def test_every_tool_has_tooltip_and_icon(self, qapp):
        from hosts.DesktopHostPySide.widgets import icons
        from hosts.DesktopHostPySide.widgets.foco.foco_tool_rail import TOOL_SPECS

        available = set(icons.available())
        _, view = _setup()
        for tool_id, icon_name, tooltip in TOOL_SPECS:
            button = view.tool_rail.button(tool_id)
            assert button is not None, tool_id
            assert button.toolTip(), tool_id
            assert icon_name in available, icon_name

    def test_enablement_follows_selection_context(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id, push_history=False)
        enabled = set(view.tool_rail.enabled_tools())
        assert {"create_entity", "create_relation", "water", "dry", "view_map"} <= enabled
        assert "ghost_convert" not in enabled
        assert "cultivate" not in enabled

    def test_ghost_center_lights_ghost_tools(self, qapp):
        project_service, view = _setup()
        ghost = _entity(project_service, "¿Sombra?", canon_state=CanonState.FANTASMA)
        view.center_entity(ghost.id, push_history=False)
        enabled = set(view.tool_rail.enabled_tools())
        assert {"ghost_convert", "ghost_link"} <= enabled
        assert "water" not in enabled  # fantasma sin ciclo de riego
        assert "dry" not in enabled

    def test_paused_center_only_offers_cultivate(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Dormida")
        project_service.active_project.watering_paused_entity_ids.append(center.id)
        view.center_entity(center.id, push_history=False)
        enabled = set(view.tool_rail.enabled_tools())
        assert "cultivate" in enabled
        assert "water" not in enabled and "dry" not in enabled

    def test_ctrl_click_ghost_selection_lights_ghost_tools(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        ghost = _entity(project_service, "¿Sombra?", canon_state=CanonState.FANTASMA)
        from packages.domain.relation import NarrativeRelation, RelationType

        project_service.active_project.relations.append(
            NarrativeRelation(
                source_id=ghost.id, target_id=center.id, relation_type=RelationType.CAUSO
            )
        )
        project_service.active_project.touch()
        view.center_entity(center.id, push_history=False)
        assert "ghost_convert" not in view.tool_rail.enabled_tools()

        view.canvas._on_item_clicked(ghost.id, ctrl=True)  # multiselección ilumina
        assert "ghost_convert" in view.tool_rail.enabled_tools()


class TestPopovers:
    def test_search_popover_filters_picks_and_offers_ghost(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_popover import EntitySearchPopover

        entities = [NarrativeEntity(name="Eldrin"), NarrativeEntity(name="Bosque")]
        picked: list[str] = []
        ghosts: list[str] = []
        popover = EntitySearchPopover(
            entities_provider=lambda: entities,
            on_pick=picked.append,
            on_create_ghost=ghosts.append,
        )
        popover.set_query("eld")
        assert popover.result_ids() == [entities[0].id]
        popover.pick_first()
        assert picked == [entities[0].id]

        popover.set_query("no existe")
        assert popover.result_ids() == []
        assert not popover.ghost_button.isHidden()
        popover.create_ghost_from_query()
        assert ghosts == ["no existe"]

    def test_quick_create_popover_builds_payload(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_popover import QuickCreatePopover

        seen: list[dict] = []
        popover = QuickCreatePopover(
            title="Nuevo nodo fantasma", with_description=True, on_submit=seen.append
        )
        popover.name_edit.setText("¿Una orden?")
        popover.description_edit.setPlainText("Algo conspira")
        popover.submit()
        assert seen == [{"name": "¿Una orden?", "brief_description": "Algo conspira"}]


class TestToolActions:
    def test_create_entity_centers_the_new_one(self, qapp):
        project_service, view = _setup()
        first = _entity(project_service, "Primera")
        view.center_entity(first.id, push_history=False)

        view._create_entity({"name": "Nueva"})
        project = project_service.active_project
        created = next(e for e in project.entities if e.name == "Nueva")
        assert view.current_entity_id() == created.id

    def test_ghost_and_relate_from_search_popover(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id, push_history=False)

        view._ghost_and_relate("¿Mecenas?")
        project = project_service.active_project
        ghost = next(e for e in project.entities if e.name == "¿Mecenas?")
        assert ghost.canon_state == CanonState.FANTASMA
        relations = project.relations_for(center.id)
        assert len(relations) == 1
        assert relations[0].canon_state == CanonState.FANTASMA
        # Y el fantasma aparece en el lienzo marcado como tal.
        assert view.canvas._items[ghost.id].is_ghost is True

    def test_convert_ghost_tool_matures_center(self, qapp):
        project_service, view = _setup()
        ghost = _entity(project_service, "¿Sombra?", canon_state=CanonState.FANTASMA)
        view.center_entity(ghost.id, push_history=False)

        view._on_tool("ghost_convert")
        assert ghost.canon_state == CanonState.BORRADOR

    def test_add_to_branch_creates_containment(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Hoja")
        branch = _entity(project_service, "Rama madre", entity_type="contenedor")
        view.center_entity(center.id, push_history=False)

        view._add_to_branch(branch.id)
        assert view.canvas.container_ids() == [branch.id]

    def test_water_dry_cultivate_emit_for_workspace(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id, push_history=False)
        watered: list[list] = []
        dried: list[str] = []
        cultivated: list[str] = []
        view.waterRequested.connect(watered.append)
        view.dryRequested.connect(dried.append)
        view.cultivateRequested.connect(cultivated.append)

        view._on_tool("water")
        view._on_tool("dry")
        view._on_tool("cultivate")
        assert watered == [[center.id]]
        assert dried == [center.id]
        assert cultivated == [center.id]

    def test_link_ghost_recenters_on_real_entity(self, qapp):
        project_service, view = _setup()
        real = _entity(project_service, "La Orden Real")
        ghost = _entity(project_service, "¿La orden?", canon_state=CanonState.FANTASMA)
        view.center_entity(ghost.id, push_history=False)

        view._link_ghost(ghost.id, real.id)
        assert project_service.active_project.entity_by_id(ghost.id) is None
        assert view.current_entity_id() == real.id

    def test_create_branch_contains_center(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Hoja")
        view.center_entity(center.id, push_history=False)

        view._create_branch({"name": "Rama nueva"})
        project = project_service.active_project
        branch = next(e for e in project.entities if e.name == "Rama nueva")
        assert str(branch.entity_type.value) == "contenedor"
        assert view.canvas.container_ids() == [branch.id]

    def test_create_related_keeps_center(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id, push_history=False)

        view._create_related({"name": "Compañera"})
        assert view.current_entity_id() == center.id  # la central sigue siendo una
        assert any(
            e.name == "Compañera" for e in project_service.active_project.entities
        )
        result = Ok(None)  # sanity: import de Result usado por la vista
        assert isinstance(result, Ok)
