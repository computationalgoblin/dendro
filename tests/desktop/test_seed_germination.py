"""Semillas (Fase B / SEM02): bloom al aceptar, wither al rechazar, rehidratación."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
from hosts.DesktopHostPySide.widgets.graph_canvas import (
    GraphCanvasView,
    GraphNodeItem,
    GraphSeedItem,
    _NodeView,
)
from hosts.DesktopHostPySide.widgets.seed_notifications import SeedNotificationLayer


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _layer(qapp):
    from PySide6.QtWidgets import QWidget

    host = QWidget()
    host.resize(900, 600)
    layer = SeedNotificationLayer(host)
    layer._host = host  # mantener vivo el padre
    return layer


# ── Rehidratación al cargar ──────────────────────────────────────────────


class _RehydrateController:
    """Devuelve solo los candidatos pendientes de revisión (como el real)."""

    def __init__(self, pending):
        self._pending = pending

    def list_all(self):
        return list(self._pending)


def _cand(cid, title="x", state="pendiente"):
    return SimpleNamespace(id=cid, title=title, state=SimpleNamespace(value=state))


def _rehydrate_stub(layer, pending):
    return SimpleNamespace(
        _seed_notifications=layer,
        candidate_view=SimpleNamespace(cc=_RehydrateController(pending)),
        # SEM04: rehidratación también recrea las semillas-candidato del grafo.
        graph=SimpleNamespace(rehydrate_candidate_seeds=lambda ids: None),
        # FOCO-13: los chips se saltan las semillas visibles en Foco — el stub
        # no enfoca nada, así que ninguna es visible; la sincronización
        # espacial de Foco es un no-op aquí.
        _foco_visible_candidate_ids=lambda: set(),
        _sync_foco_seeds=lambda: None,
    )


def test_rehydrate_recreates_pending_notifications(qapp):
    layer = _layer(qapp)
    pending = [_cand("cand-1", "Aldea del Sur"), _cand("cand-2", "Capitán Ruiz")]
    stub = _rehydrate_stub(layer, pending)

    CreationWorkspace._rehydrate_seed_notifications(stub)

    assert set(layer.notifications) == {"cand-1", "cand-2"}


def test_rehydrate_is_idempotent(qapp):
    layer = _layer(qapp)
    pending = [_cand("cand-1", "Aldea")]
    stub = _rehydrate_stub(layer, pending)

    CreationWorkspace._rehydrate_seed_notifications(stub)
    CreationWorkspace._rehydrate_seed_notifications(stub)

    assert list(layer.notifications) == ["cand-1"]


def test_rehydrate_skips_resolved_candidates(qapp):
    # list_all() ya excluye aceptados/rechazados → no deben germinar notificaciones.
    layer = _layer(qapp)
    stub = _rehydrate_stub(layer, [])

    CreationWorkspace._rehydrate_seed_notifications(stub)

    assert layer.notifications == {}


def test_rehydrate_excludes_postponed_and_archived(qapp):
    # SEM04-fix: solo germina PENDIENTE; pospuestos/archivados no aparecen.
    layer = _layer(qapp)
    pending = [
        _cand("c-pend", "Pendiente", state="pendiente"),
        _cand("c-posp", "Pospuesto", state="pospuesto"),
        _cand("c-arch", "Archivado", state="archivado"),
    ]
    stub = _rehydrate_stub(layer, pending)

    CreationWorkspace._rehydrate_seed_notifications(stub)

    assert set(layer.notifications) == {"c-pend"}


# ── Decisión: bloom (accept) / wither (reject) ───────────────────────────


def _decision_stub(layer, candidate):
    calls = {"bloom_seed": [], "wither_seed": [], "bloom_node": []}
    stub = SimpleNamespace(
        _seed_notifications=layer,
        ctx=SimpleNamespace(drawer=None, log=lambda *a, **k: None),
        _on_suggestion_changed=lambda: None,
        _find_candidate=lambda cid: candidate,
        graph=SimpleNamespace(
            bloom_node=lambda eid: calls["bloom_node"].append(eid),
            bloom_seed=lambda cid: calls["bloom_seed"].append(cid),  # UX33
            wither_seed=lambda cid: calls["wither_seed"].append(cid),
        ),
    )
    return stub, calls


def test_accept_blooms_seed_not_node(qapp):
    # UX33: aceptar florece la SEMILLA en su posición viva; ya NO se vuelve a
    # florecer el nodo recién creado en otro punto (era una doble floración).
    layer = _layer(qapp)
    layer.add("cand-1", "Aldea del Sur")
    candidate = SimpleNamespace(metadata={"created_entity_id": "ent-99"})
    stub, calls = _decision_stub(layer, candidate)

    CreationWorkspace._on_candidate_decision(stub, "cand-1", "accept")

    assert calls["bloom_seed"] == ["cand-1"]  # florece la semilla
    assert calls["bloom_node"] == []  # ya no germina el nodo nuevo
    assert not layer.has("cand-1")  # notificación retirada (sin wither)


def test_reject_withers_seed_without_bloom(qapp):
    layer = _layer(qapp)
    layer.add("cand-1", "Aldea")
    candidate = SimpleNamespace(metadata={"created_entity_id": "ent-99"})
    stub, calls = _decision_stub(layer, candidate)

    CreationWorkspace._on_candidate_decision(stub, "cand-1", "reject")

    assert calls["wither_seed"] == ["cand-1"]  # marchita la semilla
    assert calls["bloom_seed"] == [] and calls["bloom_node"] == []
    # Wither de la notificación es animado: sigue presente hasta terminar.
    dot = layer.notifications["cand-1"]
    assert dot._withering is True
    for _ in range(12):  # avanzar la animación a mano (sin event loop)
        dot._tick()
    assert not layer.has("cand-1")  # finalizó y se retiró


# ── Glow a nivel de item del canvas ──────────────────────────────────────


def _node_item(entity_id="ent-1"):
    node = _NodeView(
        entity=None,
        entity_id=entity_id,
        name="Eldrin",
        kind="personaje",
        subtitle="",
        canon="borrador",
        visibility="privado",
    )
    return GraphNodeItem(node, x=0.0, y=0.0)


def test_node_bloom_phase_expands_bounding_rect(qapp):
    item = _node_item()
    base = item.boundingRect()
    item.set_bloom_phase(0.5)  # germinando
    blooming = item.boundingRect()
    assert blooming.width() > base.width()
    item.set_bloom_phase(0.0)  # apagado → vuelve al tamaño base
    assert item.boundingRect().width() == base.width()


def test_ring_item_bloom_phase_expands_bounding_rect(qapp):
    from PySide6.QtGui import QPainterPath

    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphRingItem, _RingVisual

    ring = _RingVisual(
        ring_id="layer_1", display_name="Materia", causal_rank=0,
        color="#88aa66", inner_radius=40.0, outer_radius=120.0,
    )
    path = QPainterPath()
    path.addEllipse(-120, -120, 240, 240)
    item = GraphRingItem(ring, path)
    base = item.boundingRect()
    item.set_bloom_phase(0.5)
    assert item.boundingRect().width() > base.width()
    item.set_bloom_phase(0.0)
    assert item.boundingRect().width() == base.width()


def test_milestone_node_bloom_phase_expands_bounding_rect(qapp):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import MilestoneMark, _MilestoneNode

    mark = MilestoneMark(milestone_id="hito-1", title="Fundación", year=10, y=0.0)
    node = _MilestoneNode(mark)
    base = node.boundingRect()
    node.set_bloom_phase(0.5)
    assert node.boundingRect().width() > base.width()
    node.set_bloom_phase(0.0)
    assert node.boundingRect().width() == base.width()


# ── _germinate: enrutado del bloom por familia ───────────────────────────


def _germinate_stub():
    calls = {"node": [], "relation": [], "ring": [], "milestone": []}
    stub = SimpleNamespace(
        graph=SimpleNamespace(
            bloom_node=lambda i: calls["node"].append(i),
            bloom_relation=lambda i: calls["relation"].append(i),
            bloom_ring=lambda i: calls["ring"].append(i),
        ),
        chrono=SimpleNamespace(bloom_milestone=lambda i: calls["milestone"].append(i)),
    )
    return stub, calls


def test_germinate_routes_entity_to_bloom_node(qapp):
    stub, calls = _germinate_stub()
    CreationWorkspace._germinate(stub, {"created_entity_id": "ent-1"})
    assert calls["node"] == ["ent-1"]
    assert calls["relation"] == [] and calls["ring"] == [] and calls["milestone"] == []


def test_germinate_routes_relation_ring_and_milestone(qapp):
    stub, calls = _germinate_stub()
    CreationWorkspace._germinate(stub, {"created_relation_id": "rel-1"})
    CreationWorkspace._germinate(stub, {"created_ring_id": "layer-1"})
    CreationWorkspace._germinate(stub, {"created_milestone_id": "hito-1"})
    assert calls["relation"] == ["rel-1"]
    assert calls["ring"] == ["layer-1"]
    assert calls["milestone"] == ["hito-1"]
    assert calls["node"] == []


def test_germinate_noop_without_stamps(qapp):
    stub, calls = _germinate_stub()
    CreationWorkspace._germinate(stub, {})
    assert all(v == [] for v in calls.values())


# ── SEM04: germinación en el grafo con el canvas REAL (no stubs) ──────────


def _seed_items(view):
    return [it for it in view.scene_obj.items() if isinstance(it, GraphSeedItem)]


def test_canvas_plant_split_lifecycle(qapp):
    view = GraphCanvasView()
    view.plant_seed("job1")
    assert "job:job1" in view._seed_items
    view.advance_seed("job1", 0.6)
    view.split_seed("job1", ["c1", "c2"])
    assert "job:job1" not in view._seed_items  # la semilla del job se dividió
    assert set(view._candidate_seed_data) == {"c1", "c2"}
    assert len(_seed_items(view)) == 2


def _concentric_view():
    # Vista en modo concéntrico con un anillo dibujado, para que las semillas
    # se registren como cuerpos orbitadores.
    view = GraphCanvasView()
    layers = [SimpleNamespace(id="metafisica", name="Metafísica",
                              metadata={"causal_rank": "1"}, is_visible=True, order=0)]
    node = _NodeView(
        entity=SimpleNamespace(id="n1", name="Dioses", layer_ids=["metafisica"]),
        entity_id="n1", name="Dioses", kind="concepto", subtitle="",
        canon="canonico", visibility="publico", layer_id="metafisica",
    )
    view.set_graph([node], [], layout_mode="concentric_rings", layers=layers)
    return view


def test_candidate_seed_inherits_orbit_of_job_seed(qapp):
    # SEM04: al dividirse, las semillas-candidato HEREDAN la física orbitadora
    # de la semilla que las engendró (no quedan estáticas).
    view = _concentric_view()
    view.plant_seed("job1", "metafisica")
    assert "__seed__job1" in view._physics_engine.bodies  # la semilla orbita
    view.split_seed("job1", ["c1", "c2"], {"c1": "metafisica", "c2": "metafisica"})
    assert "__seed__job1" not in view._physics_engine.bodies  # relevada
    # cada candidato es ahora un cuerpo orbitador en su corona
    for cid in ("c1", "c2"):
        body = view._physics_engine.bodies.get(f"__seed__cand__{cid}")
        assert body is not None
        assert body.orbit_speed is not None
        assert view._candidate_seed_data[cid].get("ring_id") == "metafisica"
    assert view._has_live_seed() is True
    # al florecer/marchitar, el candidato deja de orbitar (su cuerpo se retira)
    view.bloom_seed("c1")
    assert "__seed__cand__c1" not in view._physics_engine.bodies
    view.wither_seed("c2")
    assert "__seed__cand__c2" not in view._physics_engine.bodies
    view._keep = view  # mantener vivo


def test_canvas_bloom_seed_removes_after_ticks(qapp):
    view = GraphCanvasView()
    view.split_seed("job1", ["c1"])
    view.bloom_seed("c1")
    for _ in range(25):
        view._seed_tick()
    assert "cand:c1" not in view._seed_items
    assert "c1" not in view._candidate_seed_data


def test_canvas_wither_seed_removes_after_ticks(qapp):
    view = GraphCanvasView()
    view.split_seed("job1", ["c1"])
    view.wither_seed("c1")
    for _ in range(25):
        view._seed_tick()
    assert "cand:c1" not in view._seed_items


def test_canvas_rehydrate_adds_and_removes(qapp):
    view = GraphCanvasView()
    view.rehydrate_candidate_seeds(["c1", "c2"])
    assert set(view._candidate_seed_data) == {"c1", "c2"}
    view.rehydrate_candidate_seeds(["c2"])  # c1 ya no pendiente
    assert set(view._candidate_seed_data) == {"c2"}


def test_canvas_seeds_survive_clear_graph(qapp):
    # SEM04: clear_graph (rebuild) destruye los items, pero el modelo de datos
    # persiste y las semillas se re-renderizan.
    view = GraphCanvasView()
    view.split_seed("job1", ["c1", "c2"])
    assert len(_seed_items(view)) == 2
    view.clear_graph()
    assert set(view._candidate_seed_data) == {"c1", "c2"}
    assert len(_seed_items(view)) == 2  # re-renderizadas tras el wipe


def test_canvas_seed_click_emits_signal(qapp):
    view = GraphCanvasView()
    got = []
    view.seedClicked.connect(got.append)
    view._seed_clicked("c9")
    assert got == ["c9"]


def test_seed_click_via_real_mousepress_emits(qapp):
    # SEM04-fix: el mousePressEvent REAL del view rutea el clic de la semilla
    # (antes el view resolvía solo nodos/aristas/anillos y la semilla se ignoraba).
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    view = GraphCanvasView()
    view.resize(800, 600)
    view.show()
    view.split_seed("job1", ["c1"])
    seed = next(it for it in view.scene_obj.items() if isinstance(it, GraphSeedItem))
    vp = view.mapFromScene(seed.scenePos())
    got = []
    view.seedClicked.connect(got.append)
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(vp),
        QPointF(view.mapToGlobal(vp)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(ev)
    assert got == ["c1"]


def test_review_panel_close_does_not_decide(qapp):
    # SEM04: «Cerrar» revisa sin compromiso — ni acepta ni rechaza; la semilla
    # sigue pendiente.
    from hosts.DesktopHostPySide.widgets.candidate_review_panel import CandidateReviewPanel

    decisions = []
    closed = []
    candidate = SimpleNamespace(
        id="c1", title="X",
        candidate_type=SimpleNamespace(value="entidad"), proposed_data={},
    )
    controller = SimpleNamespace(
        accept=lambda cid: decisions.append(("accept", cid)),
        reject=lambda cid: decisions.append(("reject", cid)),
    )
    panel = CandidateReviewPanel(
        candidate, controller,
        on_decision=lambda cid, d: decisions.append((d, cid)),
        on_close=lambda: closed.append(True),
    )
    panel._close()
    assert closed == [True]
    assert decisions == []  # cerrar no decide nada


def test_workspaces_uses_real_candidate_review_panel(qapp):
    # SEM04-fix: anti-regresión de la clase local que sombreaba el import y rompía
    # la apertura del panel (TypeError por firma distinta).
    import hosts.DesktopHostPySide.views.workspaces as w
    from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
        CandidateReviewPanel as Real,
    )

    assert w.CandidateReviewPanel is Real


def test_seed_layer_anchors_above_right_cluster(qapp):
    # SEM04: con widgets REALES, la capa de notificaciones queda POR ENCIMA del
    # cluster de botones derecho (no lo solapa → es clickable).
    from PySide6.QtWidgets import QWidget

    host = QWidget()
    host.resize(900, 600)
    right = QWidget(host)
    right.resize(120, 50)
    right.move(900 - 120 - 18, 600 - 66)  # cluster abajo-derecha
    layer = SeedNotificationLayer(host)
    layer.add("c1", "Aldea")
    stub = SimpleNamespace(_seed_notifications=layer, _float_right=right)

    CreationWorkspace._position_seed_layer(stub)

    assert layer.y() + layer.height() <= right.y()  # por encima del cluster
    assert not layer.isHidden()  # mostrada (isVisible es False sin ventana visible)
    host._keep = (right, layer)  # mantener vivos


# ── SEM: germinación como acreción cósmica (ambiental, sin etapas) ────────


def test_germinating_bounding_rect_is_stable_across_phases(qapp):
    # El boundingRect en germinación es constante (margen fijo) → no encoge al
    # avanzar la acreción, evitando artefactos de repintado.
    seed = GraphSeedItem(job_id="job-x")
    assert seed.mode == "germinating"
    seed.set_phase(0.4)
    rect_a = seed.boundingRect()
    seed.set_phase(0.7)
    rect_b = seed.boundingRect()
    assert rect_b.width() >= rect_a.width()
    assert rect_b.height() >= rect_a.height()


def test_germinating_paint_runs_through_phases(qapp):
    # Pintar la acreción en todo el rango (polvo orbitando → núcleo condensado)
    # no debe lanzar. restore_phase fija la fase MOSTRADA (sin suavizado).
    from PySide6.QtGui import QPainter, QPixmap

    seed = GraphSeedItem(job_id="job-y")
    pix = QPixmap(80, 80)
    for phase in (0.0, 0.18, 0.35, 0.5, 0.7, 0.85, 0.95):
        seed.restore_phase(phase)
        painter = QPainter(pix)
        try:
            painter.translate(40, 40)
            seed.paint(painter, None)
        finally:
            painter.end()


def test_advance_seed_drives_phase_on_canvas(qapp):
    # UX3+: advance_seed fija el OBJETIVO; la fase mostrada lo persigue suavemente
    # en cada tick (germinación paulatina, sin saltos).
    canvas = GraphCanvasView()
    canvas.plant_seed("job-z")
    item = canvas._seed_items["job:job-z"]
    canvas.advance_seed("job-z", 0.25)
    assert item._target_phase == pytest.approx(0.25)
    assert item._phase < 0.25  # aún no ha alcanzado el objetivo (suavizado)
    for _ in range(80):
        item.tick(pulse=0.0)
    assert item._phase == pytest.approx(0.25)
    canvas.advance_seed("job-z", 1.0)
    for _ in range(120):
        item.tick(pulse=0.0)
    assert item._phase == pytest.approx(1.0)
    canvas._keep = item  # mantener vivo
