"""BETA1-G04: vista cronológica — layout determinista, sin física.

Contrato: docs/architecture/G01_time_contract.md §7. La capa de cálculo
(`build_chrono_layout`, `YearScale`) es pura y se testea sin Qt.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    MAX_GAP_PX,
    MIN_GAP_PX,
    YearScale,
    build_chrono_layout,
)
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.world_layer_service import WorldLayerService
from packages.domain.era import Era
from packages.domain.result import Ok

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None

ROOT = Path(__file__).resolve().parents[2]


# ── Fixture: mundo con dos anillos, rama, vidas y un hito ────────────────

@pytest.fixture()
def world():
    ps = ProjectService()
    assert isinstance(ps.create("G04 Chrono"), Ok)
    project = ps.active_project
    chronology = project.project_chronology
    chronology.present_year = 10
    chronology.eras = [
        Era(name="Antigua", start_year=-1000, end_year=-1, order=0),
        Era(name="Presente", start_year=0, end_year=None, order=1),
    ]
    layers = WorldLayerService(ps)
    ring1 = layers.create_layer("Físico", "", 1).value
    ring2 = layers.create_layer("Social", "", 2).value
    svc = EntityService(ps, ps.store)
    a = svc.create_entity({"name": "Ancestro", "entity_type": "personaje",
                           "layer_ids": [ring1.id], "birth_year": -100, "death_year": -20}).value
    b = svc.create_entity({"name": "Viva", "entity_type": "personaje",
                           "layer_ids": [ring1.id], "birth_year": 0}).value
    tree = svc.create_entity({"name": "La Orden", "entity_type": "contenedor",
                              "layer_ids": [ring2.id], "birth_year": -50}).value
    c = svc.create_entity({"name": "Miembro", "entity_type": "personaje",
                           "birth_year": -40}).value  # sin anillo: hereda de la rama
    project.relations.append(SimpleNamespace(
        relation_type="contiene", source_id=tree.id, target_id=c.id,
    ))
    hitos = CausalMilestoneService(project_service=ps)
    hito = hitos.create_hito_manual({
        "title": "La Caída", "year": -30,
        "affected_entity_ids": [a.id, c.id],
        "metadata": {"primary_entity_id": a.id},
    }).value
    return SimpleNamespace(ps=ps, project=project, ring1=ring1, ring2=ring2,
                           a=a, b=b, c=c, tree=tree, hito=hito)


# ── YearScale ─────────────────────────────────────────────────────────────

def test_year_scale_is_monotonic_and_compressed():
    scale = YearScale([-1000, -100, -99, 0, 10])
    ys = [scale.y(year) for year in (-1000, -100, -99, 0, 10)]
    assert ys == sorted(ys)
    assert ys[1] - ys[0] <= MAX_GAP_PX  # desierto de 900 años comprimido
    assert ys[2] - ys[1] >= MIN_GAP_PX  # 1 año nunca colapsa a 0
    # Interpolación dentro de tramo: estrictamente entre los anclas
    mid = scale.y(-550)
    assert ys[0] < mid < ys[1]


# ── Layout puro ───────────────────────────────────────────────────────────

def test_layout_groups_lifelines_by_effective_ring(world):
    layout = build_chrono_layout(world.project)
    by_id = {line.entity_id: line for line in layout.lifelines}
    assert len(layout.lifelines) == 4
    assert by_id[world.a.id].ring_id == world.ring1.id
    assert by_id[world.b.id].ring_id == world.ring1.id
    assert by_id[world.tree.id].ring_id == world.ring2.id
    assert by_id[world.c.id].ring_id == world.ring2.id  # heredado de la rama
    # Columnas: orden causal (Físico antes que Social), sin "Sin anillo"
    assert [col.name for col in layout.columns] == ["Físico", "Social"]
    assert layout.columns[0].x_center < layout.columns[1].x_center


def test_layout_time_axis_descends(world):
    layout = build_chrono_layout(world.project)
    by_id = {line.entity_id: line for line in layout.lifelines}
    ancestor, alive = by_id[world.a.id], by_id[world.b.id]
    # Y desciende con el tiempo
    assert ancestor.y_birth < alive.y_birth < layout.y_present
    # Muerta: termina en su año; viva: llega al presente
    assert not ancestor.alive and ancestor.y_birth < ancestor.y_end < layout.y_present
    assert alive.alive and alive.y_end == pytest.approx(layout.y_present)


def test_layout_eras_are_ordered_strata(world):
    layout = build_chrono_layout(world.project)
    assert [band.name for band in layout.eras] == ["Antigua", "Presente"]
    old, present = layout.eras
    assert old.y0 < old.y1 <= present.y1
    assert old.y0 < present.y0  # estratos descendentes
    # La era abierta cubre el presente
    assert present.y0 <= layout.y_present <= present.y1


def test_layout_milestone_band_marks_every_participant(world):
    # BETA1-HITO-MULTI: el hito es una franja con un punto por entidad
    # participante (sin "entidad principal").
    layout = build_chrono_layout(world.project)
    by_id = {line.entity_id: line for line in layout.lifelines}
    assert len(layout.milestones) == 1
    mark = layout.milestones[0]
    assert mark.year == -30
    # Un punto por cada affected_entity_id presente, en su carril, ordenados.
    expected = sorted([by_id[world.a.id].x, by_id[world.c.id].x])
    assert mark.entity_xs == [pytest.approx(x) for x in expected]
    # La franja vive a la altura del año.
    assert mark.y == pytest.approx(layout.scale.y(-30))
    assert mark.y_offset == 0.0  # único hito en su año → sin desplazamiento


def test_lane_width_widens_spacing_for_long_names(world):
    # BETA1-HITO-MULTI: el nombre va centrado sobre la línea, así que la capa Qt
    # ensancha el carril (lane_width) al nombre más ancho. La separación entre
    # líneas del mismo anillo debe escalar exactamente con lane_width.
    def ring1_gaps(lane_width):
        layout = build_chrono_layout(world.project, lane_width=lane_width)
        by_id = {line.entity_id: line for line in layout.lifelines}
        xs = sorted(by_id[e].x for e in (world.a.id, world.b.id))  # ambos en ring1
        return round(xs[1] - xs[0], 2)

    assert ring1_gaps(92) == pytest.approx(92.0)
    assert ring1_gaps(300) == pytest.approx(300.0)
    # Nunca por debajo del mínimo, aunque se pida menos.
    assert ring1_gaps(10) == pytest.approx(92.0)


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_milestone_quick_create_panel_payload_with_and_without_calendar():
    # BETA1-HITO-MULTI: el panel del clic derecho (overlay interno, no ventana)
    # produce un payload listo para create_manual; mes/día solo si hay calendario
    # completo y se eligen.
    from PySide6.QtWidgets import QApplication, QWidget

    from hosts.DesktopHostPySide.widgets.chrono_canvas import (
        ChronoCanvasView,
        MilestoneQuickCreatePanel,
    )
    _ = QApplication.instance() or QApplication([])

    assert hasattr(ChronoCanvasView, "milestoneCreateRequested")
    # Es un QWidget (overlay interno), NO un QDialog (ventana del SO).
    assert issubclass(MilestoneQuickCreatePanel, QWidget)
    assert hasattr(MilestoneQuickCreatePanel, "submitted")
    assert hasattr(MilestoneQuickCreatePanel, "cancelled")

    # Sin calendario: solo título y año (obligatorio).
    simple = MilestoneQuickCreatePanel(default_year=7, calendar_meta={})
    assert simple.payload() == {"title": "Nuevo hito", "year": 7}
    assert simple.month_combo is None  # mes/día no se ofrecen

    # Calendario completo: mes y día opcionales viajan en metadata.exact_date.
    full = MilestoneQuickCreatePanel(
        default_year=7,
        calendar_meta={"mode": "full_calendar", "months": ["Muharram", "Safar", "Rabi"]},
        era_name="Revelación",
    )
    full.month_combo.setCurrentIndex(3)  # "Rabi" (índice 0 = "(ninguno)")
    full.day_spin.setValue(11)
    data = full.payload()
    assert data["year"] == 7
    assert data["metadata"]["exact_date"] == {
        "year": 7, "month": "Rabi", "day": "11", "era": "Revelación",
    }
    # Mes "(ninguno)" → sin exact_date.
    full.month_combo.setCurrentIndex(0)
    assert "metadata" not in full.payload()


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_same_year_milestones_share_one_year_label_box(world):
    # BETA1-HITO-MULTI: dos hitos del mismo año comparten "caja": una sola
    # etiqueta "Año N" y un título por hito (sin "Año N" duplicado).
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QGraphicsSimpleTextItem

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    _ = QApplication.instance() or QApplication([])
    CausalMilestoneService(project_service=world.ps).create_hito_manual({
        "title": "Otra Caída", "year": -30, "affected_entity_ids": [world.b.id],
    })
    view = ChronoCanvasView()
    view.set_project(world.project)
    texts = [
        it.text() for it in view.scene().items()
        if isinstance(it, QGraphicsSimpleTextItem)
    ]
    # El año -30 aparece UNA sola vez pese a haber dos hitos en él.
    assert texts.count("Año -30") == 1
    # Y ambos títulos están presentes.
    assert any("La Caída" in t for t in texts)
    assert any("Otra Caída" in t for t in texts)


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_milestone_ghosts_for_unlinked_entities_within_lifespan(world):
    # BETA1-HITO-MULTI: el hito de `world` vincula a `a` y `c`. En sus cruces hay
    # puntos SÓLIDOS; en los carriles de entidades NO vinculadas y vivas en ese
    # año hay puntos FANTASMA (clic = vincular).
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import (
        ChronoCanvasView,
        _GhostNode,
        _MilestoneNode,
    )

    _ = QApplication.instance() or QApplication([])
    view = ChronoCanvasView()
    # BETA1-UX36: la vista colapsa contenedores por defecto; este test verifica la
    # lógica de nodos sólidos/fantasma sobre el layout COMPLETO (c vive en una rama).
    view._collapse_default = False
    view.set_project(world.project)
    items = view.scene().items()
    solid_ids = {n.entity_id for n in items if isinstance(n, _MilestoneNode)}
    ghost_ids = {g.entity_id for g in items if isinstance(g, _GhostNode)}
    # Sólidos exactamente para las entidades vinculadas (a y c).
    assert solid_ids == {world.a.id, world.c.id}
    # Fantasmas solo para entidades NO vinculadas; nunca para las vinculadas.
    assert world.a.id not in ghost_ids and world.c.id not in ghost_ids
    # Todos los fantasmas del hito llevan su milestone_id.
    assert all(g.milestone_id == world.hito.id for g in items if isinstance(g, _GhostNode))


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_chrono_click_signals_exist():
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    # Clic simple abre paneles (entidad/hito/era) y vincula por fantasma.
    for sig in ("entityActivated", "milestoneActivated", "eraActivated",
                "milestoneEntityLinkRequested"):
        assert hasattr(ChronoCanvasView, sig), sig


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_chrono_click_dispatch_routes_each_item_type(world):
    # BETA1-HITO-MULTI: fantasma→vincular; punto sólido→panel de la ENTIDAD;
    # franja→hito; era→editar era; nombre/línea→entidad; título→hito.
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import (
        _MILESTONE_ID_ROLE,
        ChronoCanvasView,
        _EraBandItem,
        _GhostNode,
        _MilestoneBand,
        _MilestoneNode,
    )

    _ = QApplication.instance() or QApplication([])
    view = ChronoCanvasView()
    view.set_project(world.project)
    items = view.scene().items()
    out = {}
    view.milestoneEntityLinkRequested.connect(lambda m, e: out.__setitem__("link", (m, e)))
    view.milestoneActivated.connect(lambda m: out.__setitem__("hito", m))
    view.entityActivated.connect(lambda e: out.__setitem__("ent", e))
    view.eraActivated.connect(lambda e: out.__setitem__("era", e))

    def route(item):
        out.clear()
        view.itemAt = lambda _p, it=item: it
        view._dispatch_click(None)

    ghost = next(i for i in items if isinstance(i, _GhostNode))
    route(ghost)
    assert out.get("link") == (ghost.milestone_id, ghost.entity_id)

    solid = next(i for i in items if isinstance(i, _MilestoneNode))
    route(solid)
    assert out.get("hito") == solid.milestone_id  # sólido → HITO (la participación)

    band = next(i for i in items if isinstance(i, _MilestoneBand))
    route(band)
    assert out.get("hito") == band.milestone_id

    era = next(i for i in items if isinstance(i, _EraBandItem))
    route(era)
    assert out.get("era") == era.era_id

    title = next(i for i in items if i.data(_MILESTONE_ID_ROLE))
    route(title)
    assert out.get("hito") == str(title.data(_MILESTONE_ID_ROLE))


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_chrono_real_mouse_press_on_ghost_emits_link(world):
    # BETA1-HITO-MULTI (regresión): el clic se resuelve en el mousePressEvent
    # (NoDrag), no en el release. Un PRESS real de Qt sobre un fantasma debe
    # emitir el vínculo (mis tests previos llamaban a _dispatch_click directo y
    # NO cubrían el camino real de eventos, que en la app fallaba).
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView, _GhostNode

    _ = QApplication.instance() or QApplication([])
    view = ChronoCanvasView()
    view.set_project(world.project)
    view.resize(1100, 750)
    view.show()
    view.fit_all()
    got = []
    view.milestoneEntityLinkRequested.connect(lambda m, e: got.append((m, e)))
    ghost = next(i for i in view.scene().items() if isinstance(i, _GhostNode))
    vp = view.mapFromScene(ghost.scenePos())
    gp = view.viewport().mapToGlobal(vp)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(vp), QPointF(gp),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), press)
    assert got == [(ghost.milestone_id, ghost.entity_id)]


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_chrono_band_click_resolves_to_nearest_lane(world):
    # BETA1-HITO-MULTI (regresión del bug "abre cronología al clicar la
    # intersección"): un clic SOBRE la franja se atribuye al carril más cercano.
    # En el carril de una entidad NO vinculada y viva → VINCULA (no abre el hito).
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView, _MilestoneBand

    _ = QApplication.instance() or QApplication([])
    view = ChronoCanvasView()
    view.set_project(world.project)
    view.resize(1100, 750)
    view.show()
    view.fit_all()
    out = {}
    view.milestoneEntityLinkRequested.connect(lambda m, e: out.__setitem__("link", (m, e)))
    view.entityActivated.connect(lambda e: out.__setitem__("ent", e))
    view.milestoneActivated.connect(lambda m: out.__setitem__("hito", m))
    band = next(i for i in view.scene().items() if isinstance(i, _MilestoneBand))
    # BETA1-UX7: el punto de escena se reconstruye desde coords lógicas
    # (cross = carril, time = año del hito) vía view._pt, así el test vale para
    # cualquier orientación.
    mark = next(m for m in view._layout.milestones if m.milestone_id == band.milestone_id)
    time = mark.y_band
    xby = {lf.entity_id: lf.x for lf in view._layout.lifelines}

    # `tree` no está vinculado y vive en el año -30 → clic en la franja, a su
    # carril, debe VINCULAR (no abrir el hito).
    out.clear()
    view._dispatch_click(view.mapFromScene(view._pt(xby[world.tree.id], time)))
    assert out.get("link") == (world.hito.id, world.tree.id)

    # `a` ya está vinculado → clic en la franja, a su carril, abre el HITO
    # (la intersección sólida representa la participación en el hito).
    out.clear()
    view._dispatch_click(view.mapFromScene(view._pt(xby[world.a.id], time)))
    assert out.get("hito") == world.hito.id


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_milestone_detail_panel_loads_and_saves(world):
    # BETA1-HITO-MULTI: clic en un hito abre su PANEL DE DETALLE enfocado (no el
    # menú de cronología). Carga los campos y persiste por el controller.
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
        CausalMilestoneController,
    )
    from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

    _ = QApplication.instance() or QApplication([])
    ctrl = CausalMilestoneController(world.ps)
    ctx = SimpleNamespace(log=lambda *a, **k: None, drawer=None)
    panel = MilestoneDetailPanel(ctx, ctrl, world.hito.id, project_getter=lambda: world.project)

    # Carga: el hito de `world` vincula a `a` y `c` → pre-marcados.
    assert panel.title_edit.text() == "La Caída"
    checked = {
        str(panel.participants_list.item(i).data(Qt.ItemDataRole.UserRole))
        for i in range(panel.participants_list.count())
        if panel.participants_list.item(i).checkState() == Qt.CheckState.Checked
    }
    assert checked == {world.a.id, world.c.id}

    # Guardado: cambia título y tipo; persiste por el controller.
    panel.title_edit.setText("La Gran Caída")
    panel.type_combo.setCurrentIndex(panel.type_combo.findData("guerra"))
    panel._save()
    saved = next(h for h in ctrl.list_all() if h.id == world.hito.id)
    assert saved.title == "La Gran Caída"
    assert saved.milestone_type.value == "guerra"
    assert "primary_entity_id" not in saved.metadata  # ya no hay primaria


def test_layout_milestones_same_year_offset_into_box(world):
    # BETA1-HITO-MULTI: dos hitos del mismo año caen en la misma "caja" y se
    # desplazan en Y para que ambas franjas se lean.
    hitos = CausalMilestoneService(project_service=world.ps)
    hitos.create_hito_manual({
        "title": "Otra Caída", "year": -30,
        "affected_entity_ids": [world.b.id],
    })
    layout = build_chrono_layout(world.project)
    same_year = [m for m in layout.milestones if m.year == -30]
    assert len(same_year) == 2
    offsets = sorted(m.y_offset for m in same_year)
    assert offsets[0] != offsets[1]  # desplazamientos distintos
    # Centrados alrededor del año: simétricos respecto a 0.
    assert offsets[0] == pytest.approx(-offsets[1])
    # Misma altura base (mismo año) pese al offset.
    for m in same_year:
        assert m.y == pytest.approx(layout.scale.y(-30))


def test_chrono_module_has_no_physics():
    source = (ROOT / "hosts/DesktopHostPySide/widgets/chrono_canvas.py").read_text(encoding="utf-8")
    assert "PhysicsEngine" not in source
    assert "graph_physics.engine" not in source
    assert "SIN física" in source


# ── Vista Qt ──────────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_chrono_view_builds_scene_and_signals(world):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView
    view = ChronoCanvasView()
    view.set_project(world.project)
    assert len(view.scene().items()) > 10
    assert hasattr(view, "entityActivated") and hasattr(view, "milestoneActivated")
    # Reconstrucción idempotente (refresh)
    view.set_project(world.project)
    assert len(view.scene().items()) > 10


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_workspace_wires_view_toggle_and_eras():
    """El ◷ ya no abre el panel H03: alterna la vista (G04)."""
    source = (ROOT / "hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
    assert '("◷", "Cronología e hitos", self._open_milestone_chronology_view)' not in source
    assert "_build_view_toggle" in source
    assert "def set_active_view" in source
    assert "creation/active_view" in source  # preferencia persistida
    assert "_build_eras_section" in source  # G03: eras en filtros
    assert "EraQuickCreatePanel" in source and "EraEditPanel" in source
