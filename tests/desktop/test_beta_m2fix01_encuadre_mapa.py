"""BETA2-FIX-01 — el Mapa se abre LEGIBLE.

Siete de las ocho personas de la 2ª ronda de beta testing abrieron su proyecto y
vieron una hoja en blanco. Aquí se fijan las tres mitades del arreglo del Mapa:

  1. El NOMBRE de cada entidad tiene un piso de tamaño EN PANTALLA (>= 11 px),
     no solo permiso para pintarse: el título es un item de escena de 9 pt que a
     la escala de encuadre (0,127) se rasterizaba a 1-2 px.
  2. El ENCUADRE se calcula con el viewport REAL (antes se calculaba con la vista
     aún oculta y nadie lo rehacía) y tiene un SUELO de escala legible.
  3. La PRIORIDAD DE TINTA es coherente: si no se lee el nombre de una cosa,
     tampoco se leen los nombres de sus relaciones ni de sus anillos.

Y la guardia que nada de esto puede romper: la cámara del usuario manda.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QImage, QPainter, QTransform
    from PySide6.QtWidgets import QStyleOptionGraphicsItem

    import hosts.DesktopHostPySide.widgets.graph_canvas as gc
    from hosts.DesktopHostPySide.widgets.graph_canvas import (
        GraphCanvasView,
        GraphNodeItem,
        _EdgeView,
        _NodeView,
    )

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

VIEWPORT = (1440, 900)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_animacion(monkeypatch):
    """La cámara animada no termina sin bucle de eventos: encuadre instantáneo."""
    if HAS_QT:
        monkeypatch.setattr(gc, "MOTION_ENABLED", False)
        monkeypatch.setattr(gc, "_b44trace", lambda *a, **k: None)


def _layer(layer_id: str, name: str, rank: int):
    return SimpleNamespace(
        id=layer_id, name=name, metadata={"causal_rank": str(rank)}, is_visible=True, order=0
    )


def _node(entity_id: str, name: str, *, layer_id: str = ""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id,
        name=name,
        kind="concepto",
        subtitle="",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


def _edge(relation_id: str, source_id: str, target_id: str):
    return _EdgeView(
        relation=SimpleNamespace(id=relation_id),
        relation_id=relation_id,
        source_id=source_id,
        target_id=target_id,
        kind="deriva_de",
        label="deriva de",
    )


def _vista(width: int = VIEWPORT[0], height: int = VIEWPORT[1]) -> "GraphCanvasView":
    view = GraphCanvasView()
    view.resize(width, height)
    view.show()
    QApplication.processEvents()
    return view


def _mundo_de_nueve() -> tuple[list, list, list]:
    """El mundo de Carmen: nueve fichas repartidas en dos anillos."""
    layers = [_layer("mundo", "Mundo", 1), _layer("gente", "Gente", 2)]
    nodes = [
        _node(f"m{i}", f"Lugar numero {i}", layer_id="mundo") for i in range(4)
    ] + [_node(f"g{i}", f"Persona numero {i}", layer_id="gente") for i in range(5)]
    edges = [_edge("r0", "m0", "g0"), _edge("r1", "g1", "g2")]
    return nodes, edges, layers


def _alto_en_viewport(view, item) -> float:
    """Altura del item medida en píxeles de VIEWPORT (lo que ve el usuario)."""
    return float(view.mapFromScene(item.sceneBoundingRect()).boundingRect().height())


def _pinta_sin_gate(item, view_scale: float) -> bool:
    """¿`_LodTextItem.paint` deja tinta a esta escala, o sale por el `return`?

    Se pinta el item a mano sobre un QImage con la transformada de mundo puesta a
    la escala pedida: si el gate de LOD corta, la imagen queda intacta."""
    image = QImage(400, 120, QImage.Format.Format_ARGB32)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    painter.setWorldTransform(QTransform().scale(view_scale, view_scale))
    painter.translate(10.0, 10.0)
    item.paint(painter, QStyleOptionGraphicsItem(), None)
    painter.end()
    blanco = 0xFFFFFFFF
    return any(
        image.pixel(x, y) & 0xFFFFFFFF != blanco
        for y in range(image.height())
        for x in range(image.width())
    )


def test_beta_m2fix01_nombres_visibles_al_encuadrar(qapp):
    # CRITERIO 1: al abrir, cada nombre mide >= 11 px de alto en PANTALLA, sin
    # que el usuario toque el zoom. Antes: cero nombres a 0,127-0,183 de escala.
    view = _vista()
    nodes, edges, layers = _mundo_de_nueve()
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    hojas = [item for item in view._nodes.values() if isinstance(item, GraphNodeItem)]
    assert len(hojas) == 9
    escala = view.transform().m11()
    assert escala > 0.0

    for item in hojas:
        assert item._title_item.isVisible(), "con nueve fichas no se descarta ningún nombre"
        alto = _alto_en_viewport(view, item._title_item)
        assert alto >= gc._LABEL_MIN_PX - 0.5, f"{item.node.name}: {alto:.1f} px en pantalla"
        # …y el gate de LOD no lo corta (el nombre se PINTA de verdad).
        lod = escala * item._title_item.scale()
        assert gc.label_paints_at(escala, item._title_item.scale()), lod
        assert _pinta_sin_gate(item._title_item, lod)


def test_beta_m2fix01_encuadre_no_baja_del_suelo_legible(qapp):
    # CRITERIO 4: con 800 entidades el encuadre antiguo daba 0,0029 sobre una
    # escena de 63.967 x 287.480 px — «un amonites fósil vacío». Ahora la vista
    # acota a una porción CENTRADA en contenido real.
    view = _vista()
    layers = [_layer("mundo", "Mundo", 1)]
    nodes = [_node(f"n{i}", f"Entidad numero {i}", layer_id="mundo") for i in range(800)]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    escala = view.transform().m11()
    assert escala >= gc._MIN_READABLE_SCALE - 1e-6, f"escala de apertura {escala:.4f}"
    assert view.fit_was_clamped(), "800 entidades no caben: el encuadre debe acotarse"

    centro = view.mapToScene(view.viewport().rect().center())
    caja = view._nodes_bounding_rect()
    assert caja.contains(centro), "la cámara cayó en un hueco, no sobre contenido"

    # Y los nombres que sobreviven al descarte por densidad siguen siendo legibles.
    visibles = [
        item
        for item in view._nodes.values()
        if isinstance(item, GraphNodeItem) and item._title_item.isVisible()
    ]
    assert visibles, "el descarte por densidad no puede dejar el Mapa anónimo"
    for item in visibles:
        assert item.label_screen_height(escala) >= gc._LABEL_MIN_PX - 0.5


def test_beta_m2fix01_encuadre_se_recalcula_al_mostrar(qapp):
    # CRITERIO 3: el encuadre se calculaba ANTES del setVisible, contra un
    # viewport que aún no existía (Elvira: 0,0711 al abrir vs 0,125 con un
    # fit_all posterior, un 76 % de error). Ahora se rehace al mostrar/redimensionar.
    view = GraphCanvasView()
    view.set_physics_enabled(False)  # el asentamiento físico movería el contenido
    view.resize(100, 30)  # viewport falso, como el de una vista nunca mostrada
    nodes, edges, layers = _mundo_de_nueve()
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)
    assert view._pending_initial_fit is not None, "debe quedar anotado el reencuadre"

    view.show()
    view.resize(*VIEWPORT)
    QApplication.processEvents()

    aparece = view.transform().m11()
    view.fit_all()  # el mismo encuadre, pero pedido explícitamente
    explicito = view.transform().m11()
    assert explicito > 0.0
    assert abs(aparece - explicito) / explicito <= 0.02, (
        f"la escala con la que la vista APARECE ({aparece:.4f}) no coincide con la "
        f"de un fit_all explícito ({explicito:.4f})"
    )


def test_beta_m2fix01_camara_de_usuario_gana_sobre_el_reencuadre(qapp):
    # CRITERIO 8: editar/crear/borrar y refrescar NO puede reencuadrar. El
    # arreglo del criterio 3 es de UNA sola vez y cede ante cualquier cámara.
    view = _vista()
    nodes, edges, layers = _mundo_de_nueve()
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    for _ in range(5):
        view.zoom_in()
    view.centerOn(QPointF(120.0, -80.0))
    antes = QTransform(view.transform())
    centro_antes = view.mapToScene(view.viewport().rect().center())
    assert view._pending_initial_fit is None, "el zoom del usuario cancela el pendiente"

    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    despues = view.transform()
    assert abs(despues.m11() - antes.m11()) < 1e-6
    centro_despues = view.mapToScene(view.viewport().rect().center())
    assert (centro_despues - centro_antes).manhattanLength() < 4.0


def test_beta_m2fix01_etiqueta_de_relacion_no_sobrevive_al_nombre(qapp):
    # CRITERIO 7 (ART-03): antes la etiqueta de ARISTA y la de ANILLO se pintaban
    # SIEMPRE y el nombre estaba gateado — se conservaban los nombres de las
    # relaciones entre cosas sin nombre. La relación debe ser la inversa.
    view = _vista()
    nodes, edges, layers = _mundo_de_nueve()
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    hoja = next(item for item in view._nodes.values() if isinstance(item, GraphNodeItem))
    arista = view._edges[0]
    assert isinstance(arista.label_item, gc._LodTextItem), "la arista debe llevar gate de LOD"

    # Escala a la que el propio NOMBRE deja de pintarse (compensación al tope).
    escala_muerte = gc._LABEL_MIN_LOD / gc._LABEL_MAX_UPSCALE * 0.9
    view.resetTransform()
    view.scale(escala_muerte, escala_muerte)
    view.refresh_label_legibility()

    factor_nombre = hoja._title_item.scale()
    assert not gc.label_paints_at(escala_muerte, factor_nombre), "el nombre debería estar apagado"
    # …y por tanto la arista (escala 0,86) y el anillo (escala 1) tampoco.
    assert not gc.label_paints_at(escala_muerte, arista.label_item.scale())
    assert not _pinta_sin_gate(arista.label_item, escala_muerte * arista.label_item.scale())

    # Invariante estructural: ninguna etiqueta sin compensar puede sobrevivir al
    # nombre, porque su factor es <= 1 y el del nombre es >= 1.
    assert arista.label_item.scale() <= factor_nombre + 1e-9


def test_beta_m2fix01_un_solo_comportamiento_de_ver_todo(qapp):
    # CRITERIO 9: las dos implementaciones duplicadas quedan alineadas.
    view = _vista()
    nodes, edges, layers = _mundo_de_nueve()
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    view.fit_all()
    por_tecla = view.transform().m11()
    view.resetTransform()
    view.scale(2.0, 2.0)
    view.reset_to_panorama()
    por_panorama = view.transform().m11()
    assert abs(por_tecla - por_panorama) < 1e-6

    # `_fit_target_rect` es el único cálculo de encuadre y respeta el suelo.
    rect = view._fit_target_rect(140.0)
    assert isinstance(rect, QRectF) and not rect.isEmpty()
    assert view._scale_for_rect(rect) >= gc._MIN_READABLE_SCALE - 1e-6


def test_beta_m2fix01_elision_por_ancho_no_por_caracteres(qapp):
    # ART-04: `_fit_text` cortaba por `len()` a 20/26 caracteres sin mirar el
    # ancho disponible. Ahora se elide por ancho real de la fuente.
    from PySide6.QtGui import QFont

    font = QFont()
    font.setBold(True)
    font.setPointSize(9)
    largo = "Ilva Cinabrio, la Alquimista de las Marismas Rojas"
    assert gc._fit_text_px(largo, font, 210.0).endswith("…")
    assert gc._fit_text_px(largo, font, 4000.0) == largo  # con sitio, no se corta
    assert gc._fit_text_px("Corto", font, 210.0) == "Corto"


def test_beta_m2fix01_redimensionar_no_arranca_la_camara_del_usuario(qapp):
    # Guardia del criterio 8 frente al criterio 3: una vez consumido el encuadre
    # diferido, redimensionar la ventana NO vuelve a encuadrar.
    view = _vista()
    nodes, edges, layers = _mundo_de_nueve()
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)
    for _ in range(4):
        view.zoom_in()
    escala = view.transform().m11()

    view.resize(1000, 700)
    QApplication.processEvents()

    assert abs(view.transform().m11() - escala) < 1e-6
