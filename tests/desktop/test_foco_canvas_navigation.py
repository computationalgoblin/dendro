"""Navegación del lienzo de Foco: click centra, rotación/salto por anillos, Ctrl+click.

Comportamiento vigente: BETA2-FOCO-25 (navegación por posición de anillo). Sustituye
el modelo causal de BETA2-FOCO-08.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.application.world_layer_causal import set_causal_rank  # noqa: E402
from packages.domain.entity import CanonState, NarrativeEntity  # noqa: E402 — tras el guard HAS_QT
from packages.domain.relation import (  # noqa: E402 — tras el guard HAS_QT
    NarrativeRelation,
    RelationType,
)
from packages.domain.world_layer import WorldLayer  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _layer(project_service, layer_id, rank):
    layer = WorldLayer(id=layer_id, name=layer_id)
    if rank is not None:
        set_causal_rank(layer, rank)
    project_service.active_project.world_layers.append(layer)
    project_service.active_project.touch()
    return layer


def _relate(project_service, source, target, relation_type):
    relation = NarrativeRelation(
        source_id=source.id, target_id=target.id, relation_type=relation_type
    )
    project_service.active_project.relations.append(relation)
    project_service.active_project.touch()
    return relation


def _garden():
    """Centro (anillo 3) con relacionada en anillo superior, inferior, dos del mismo
    anillo, rama contenedora (sin anillo, solo marco) y un fantasma sin anillo."""
    project_service = ProjectService()
    project_service.create("Jardín Foco")
    for layer_id, rank in (("l2", 2), ("l3", 3), ("l4", 4)):
        _layer(project_service, layer_id, rank)
    center = _entity(project_service, "Centro", layer_ids=["l3"])
    root = _entity(project_service, "Guerra previa", layer_ids=["l2"])  # anillo superior
    sprout = _entity(project_service, "Derivada", layer_ids=["l4"])  # anillo inferior
    alfa = _entity(project_service, "Alfa", layer_ids=["l3"])  # mismo anillo
    beta = _entity(project_service, "Beta", layer_ids=["l3"])  # mismo anillo
    branch = _entity(project_service, "Rama madre", entity_type="contenedor")  # sin anillo
    ghost = _entity(project_service, "¿Sombra?", canon_state=CanonState.FANTASMA)  # sin anillo
    _relate(project_service, root, center, RelationType.CAUSO)
    _relate(project_service, center, sprout, RelationType.CAUSO)
    _relate(project_service, center, alfa, RelationType.ES_ALIADO_DE)
    _relate(project_service, center, beta, RelationType.ES_ALIADO_DE)
    _relate(project_service, branch, center, RelationType.CONTIENE)
    _relate(project_service, ghost, center, RelationType.CAUSO)
    return project_service, center, root, sprout, alfa, beta, branch, ghost


def _view(project_service):
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    view = FocoView(
        project_provider=lambda: project_service.active_project,
        last_entity_setter=project_service.set_last_worked_entity,
    )
    return view


def _press(view, key, *, shift=False):
    modifier = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifier)
    view.canvas.keyPressEvent(event)


class TestClickAndZones:
    def test_click_on_satellite_centers_it(self, qapp):
        project_service, center, root, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id)

        view.canvas._on_item_clicked(root.id, ctrl=False)
        assert view.current_entity_id() == root.id

    def test_zones_feed_the_canvas_by_ring(self, qapp):
        # FOCO-25: la zona la decide la POSICIÓN DE ANILLO, no el tipo de relación.
        project_service, center, root, sprout, alfa, beta, branch, ghost = _garden()
        view = _view(project_service)
        view.center_entity(center.id)

        assert view.canvas.zone_ids("raices") == [root.id]  # anillo superior
        # Anillo inferior (l4) + el fantasma sin capa (anillo no clasificado =
        # el MÁS exterior, como en el Mapa) ⇒ ambos abajo, el más cercano antes.
        assert view.canvas.zone_ids("brotes") == [sprout.id, ghost.id]
        assert view.canvas.zone_ids("entorno") == [alfa.id, beta.id]  # mismo anillo
        # FOCO-22: la contenedora es el marco, no un satélite.
        assert view.canvas.container_ids() == [branch.id]
        ghost_item = view.canvas._items[ghost.id]
        assert ghost_item.is_ghost is True  # translúcido/borrador en el lienzo

    def test_ctrl_click_accumulates_highlight_without_recentering(self, qapp):
        project_service, center, _, _, alfa, beta, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id)
        seen: list[list[str]] = []
        view.canvas.selectionChanged.connect(seen.append)

        view.canvas._on_item_clicked(alfa.id, ctrl=True)
        view.canvas._on_item_clicked(beta.id, ctrl=True)
        assert view.canvas.selected_ids() == [alfa.id, beta.id]
        assert view.current_entity_id() == center.id  # la central sigue siendo una
        assert seen[-1] == [alfa.id, beta.id]

        view.canvas._on_item_clicked(alfa.id, ctrl=True)  # toggle fuera
        assert view.canvas.selected_ids() == [beta.id]


class TestRingNavigation:
    def test_right_and_left_rotate_the_current_ring(self, qapp):
        # Anillo 3 = {Alfa, Beta, Centro} ordenado por nombre; centro en el índice 2.
        project_service, center, _, _, alfa, beta, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id)
        _press(view, Qt.Key.Key_Right)  # siguiente (cíclico) ⇒ Alfa
        assert view.current_entity_id() == alfa.id

        view.center_entity(center.id)
        _press(view, Qt.Key.Key_Left)  # anterior ⇒ Beta
        assert view.current_entity_id() == beta.id

    def test_shift_up_jumps_to_related_superior_ring(self, qapp):
        project_service, center, root, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id)
        _press(view, Qt.Key.Key_Up, shift=True)
        assert view.current_entity_id() == root.id

    def test_shift_down_jumps_to_related_inferior_ring(self, qapp):
        project_service, center, _, sprout, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id)
        _press(view, Qt.Key.Key_Down, shift=True)
        assert view.current_entity_id() == sprout.id

    def test_plain_up_goes_to_container_and_down_returns_to_member(self, qapp):
        # FOCO-25: ↑ sube a la rama contenedora; desde la rama, ↓ baja a la
        # primera entidad contenida.
        project_service, center, *_ , branch, _ = _garden()
        view = _view(project_service)
        view.center_entity(center.id)
        _press(view, Qt.Key.Key_Up)
        assert view.current_entity_id() == branch.id
        _press(view, Qt.Key.Key_Down)
        assert view.current_entity_id() == center.id  # única miembro de la rama

    def test_arrow_without_target_is_noop(self, qapp):
        project_service = ProjectService()
        project_service.create("Solitaria")
        lonely = _entity(project_service, "Sola", layer_ids=["l3"])
        _layer(project_service, "l3", 3)
        view = _view(project_service)
        view.center_entity(lonely.id)

        for key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            _press(view, key)
            assert view.current_entity_id() == lonely.id
        for key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            _press(view, key, shift=True)
            assert view.current_entity_id() == lonely.id


class TestContainerFrameAndLabels:
    """BETA2-FOCO-22: marco contenedor envolvente, zonas explicadas y rótulos."""

    def test_container_renders_as_frame_not_satellite(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoContainerFrame

        project_service, center, *_ = _garden()
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        frame = view.canvas._container_frame
        assert isinstance(frame, FocoContainerFrame)
        assert frame.container_id == view.canvas.container_ids()[0]
        assert "Rama madre" in frame.display_name
        # La contenedora NO tiene satélite propio.
        assert frame.container_id not in view.canvas._items

    def test_nested_branches_render_concentric_frames(self, qapp):
        # FOCO-25: abuela ⊃ madre ⊃ centro ⇒ dos marcos concéntricos clicables.
        project_service, center, *_ , branch, _ = _garden()
        abuela = _entity(project_service, "Rama abuela", entity_type="contenedor")
        _relate(project_service, abuela, branch, RelationType.CONTIENE)
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        frames = view.canvas._container_frames
        assert [frame.container_id for frame in frames] == [branch.id, abuela.id]
        assert view.canvas._container_frame is frames[0]
        # La interna gana el click: zValue mayor que la externa.
        assert frames[0].zValue() > frames[1].zValue()

    def test_frame_click_centers_the_branch(self, qapp):
        project_service, center, *_ , branch, _ = _garden()
        view = _view(project_service)
        view.center_entity(center.id)
        activated: list[str] = []
        view.canvas.satelliteActivated.connect(activated.append)
        view.canvas.satelliteActivated.emit(view.canvas._container_frame.container_id)
        assert activated == [branch.id]

    def test_hover_band_item_draws_and_clears_connector(self, qapp):
        # FOCO-28: los conectores de banda son POR HOVER (antes siempre dibujados).
        from PySide6.QtWidgets import QGraphicsSceneHoverEvent, QGraphicsSimpleTextItem

        project_service, center, root, _sprout, alfa, *_ = _garden()
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        def _labels():
            return [
                item.text()
                for item in view.canvas._scene.items()
                if isinstance(item, QGraphicsSimpleTextItem)
            ]

        # Sin ratón encima no hay rótulo de vínculo en la escena.
        assert not any("aliado" in text.lower() for text in _labels())

        item = view.canvas._items[alfa.id]
        assert item.acceptHoverEvents() is True
        item.hoverEnterEvent(QGraphicsSceneHoverEvent(QEvent.Type.GraphicsSceneHoverEnter))
        assert view.canvas._band_connector is not None
        assert any("aliado" in text.lower() for text in _labels())

        item.hoverLeaveEvent(QGraphicsSceneHoverEvent(QEvent.Type.GraphicsSceneHoverLeave))
        assert view.canvas._band_connector is None
        assert not any("aliado" in text.lower() for text in _labels())

        # Otra banda (relación causal, anillo superior) también rotula al hover.
        view.canvas._show_band_connector(root.id)
        assert any("caus" in text.lower() for text in _labels())

    def test_roulette_cards_flank_the_center(self, qapp):
        # FOCO-28: la anterior/siguiente del anillo se muestran como tarjetas
        # plegadas flanqueando el centro (izquierda/derecha), no dos a la izquierda.
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoRouletteCard

        project_service, center, *_ = _garden()
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        cards = [it for it in view.canvas._scene.items() if isinstance(it, FocoRouletteCard)]
        assert len(cards) == 2  # anillo 3 = {Alfa, Beta, Centro} ⇒ prev + next
        # El layout usa coordenadas de escena (clamp 720×500); el hueco central
        # está centrado, así que una tarjeta cae a cada lado del centro de escena.
        scene_center = view.canvas._scene.sceneRect().center()
        xs = sorted(card.pos().x() for card in cards)
        assert xs[0] < scene_center.x() < xs[1]  # una a cada lado del centro
        for card in cards:
            assert abs(card.pos().y() - scene_center.y()) < 1.0  # a la altura del centro

    def test_zone_captions_are_painted(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import _ZONE_CAPTIONS

        # FOCO-25: el eje es la posición de anillo; sin ENTORNO duplicado arriba.
        assert "anillos superiores" in _ZONE_CAPTIONS["raices"]
        assert "anillos inferiores" in _ZONE_CAPTIONS["brotes"]
        assert _ZONE_CAPTIONS["entorno"] == "ENTORNO"
        assert "rotacion" in _ZONE_CAPTIONS
        # Cromo anclado al VIEWPORT (resetTransform): una sola vez, sin
        # duplicados por desalineación escena↔viewport.
        source_canvas = Path("hosts/DesktopHostPySide/widgets/foco/foco_canvas.py").read_text(
            encoding="utf-8"
        )
        assert "painter.resetTransform()" in source_canvas
        source = Path("hosts/DesktopHostPySide/widgets/foco/foco_canvas.py").read_text(
            encoding="utf-8"
        )
        assert "def drawBackground" in source
        assert "_ZONE_CAPTIONS" in source


def _hover_enter():
    from PySide6.QtWidgets import QGraphicsSceneHoverEvent

    return QGraphicsSceneHoverEvent(QEvent.Type.GraphicsSceneHoverEnter)


class TestR5BandsAndBranches:
    """FOCO-30: transición de ruleta, empuje al desplegar, hermanos en el marco y
    estantería de contenidos de rama."""

    def test_scene_pos_for_covers_band_and_roulette(self, qapp):
        project_service = ProjectService()
        project_service.create("Ruleta")
        _layer(project_service, "l3", 3)
        center = _entity(project_service, "Centro", layer_ids=["l3"])
        vecino = _entity(project_service, "Aliado", layer_ids=["l3"])
        # Mismo anillo pero SIN relación: es vecino de rotación (ruleta), no banda.
        solo = _entity(project_service, "Zeta sin relacion", layer_ids=["l3"])
        _relate(project_service, center, vecino, RelationType.ES_ALIADO_DE)
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        # 'vecino' es un chip de banda (entorno) ⇒ está en _items.
        assert vecino.id in view.canvas._items
        assert view.canvas.scene_pos_for(vecino.id) is not None
        # 'solo' es tarjeta de ruleta (no chip de banda); scene_pos_for lo cubre
        # igual — así vuelve la transición direccional al rotar el anillo.
        assert solo.id in view.canvas._roulette_pos
        assert solo.id not in view.canvas._items
        assert view.canvas.scene_pos_for(solo.id) is not None
        assert view._transition_direction(solo.id) is not None
        assert view.canvas.scene_pos_for("no-existe") is None

    def test_hover_does_not_move_band_neighbors(self, qapp):
        # BETA2-HOVER-02: el chip ya no se expande al hover (el detalle va a la
        # tarjeta flotante), así que NINGUNA vecina se mueve.
        project_service = ProjectService()
        project_service.create("Empuje")
        _layer(project_service, "l3", 3)
        center = _entity(project_service, "Centro", layer_ids=["l3"])
        a = _entity(project_service, "A entorno", layer_ids=["l3"])
        b = _entity(project_service, "B entorno", layer_ids=["l3"])
        c = _entity(project_service, "C entorno", layer_ids=["l3"])
        for other in (a, b, c):
            _relate(project_service, center, other, RelationType.ES_ALIADO_DE)
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        track = view.canvas._band_tracks["right"]
        assert len(track) == 3
        before = [item.pos().y() for item in track]
        track[1].hoverEnterEvent(_hover_enter())  # hover del del medio
        after = [item.pos().y() for item in track]
        assert after == before  # nada se mueve
        # el chip hover conserva el mismo tamaño fijo que sus vecinos (no crece)
        assert track[1]._chip_rect() == track[0]._chip_rect()

    def test_siblings_render_on_frame_not_in_bands(self, qapp):
        project_service = ProjectService()
        project_service.create("Hermanos")
        _layer(project_service, "l3", 3)
        casa = _entity(project_service, "Casa", layer_ids=["l3"], entity_type="faccion")
        center = _entity(project_service, "Centro", layer_ids=["l3"])
        herm = _entity(project_service, "Hermano", layer_ids=["l3"])
        _relate(project_service, casa, center, RelationType.CONTIENE)
        _relate(project_service, casa, herm, RelationType.CONTIENE)
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        # El hermano NO es un chip de banda (no está en _items)...
        assert herm.id not in view.canvas._items
        # ...sino una miniatura en el marco contenedor.
        frame = view.canvas._container_frame
        assert frame is not None
        assert herm.id in [member_id for _rect, member_id in frame._thumb_rects]

    def test_branch_shelf_only_for_branches(self, qapp):
        project_service = ProjectService()
        project_service.create("Estanteria")
        _layer(project_service, "l3", 3)
        casa = _entity(project_service, "Casa", layer_ids=["l3"], entity_type="faccion")
        m1 = _entity(project_service, "M1", layer_ids=["l3"])
        m2 = _entity(project_service, "M2", layer_ids=["l3"])
        _relate(project_service, casa, m1, RelationType.CONTIENE)
        _relate(project_service, casa, m2, RelationType.CONTIENE)
        view = _view(project_service)
        view.resize(1100, 760)

        view.center_entity(casa.id)  # rama ⇒ estantería con miniaturas
        assert view._contents_layout.count() - 1 == 2
        assert not view._contents_shelf.isHidden()

        view.center_entity(m1.id)  # hoja ⇒ estantería oculta y vacía
        assert view._contents_shelf.isHidden()
        assert view._contents_layout.count() - 1 == 0
