"""BETA2-FIX-01 — la Cronología se abre LEGIBLE.

Elvira, historiadora: «abrir Cronología y ver mi siglo XIV» → un lienzo vacío
color pergamino. 370 ítems, todos dentro del viewport, todos a escala 0,0711,
ninguno legible. Y su era «Alta Edad Media», sin un solo hito, ocupaba el 56 %
del lienzo.

Aquí se fijan:
  · el encuadre por contenido POBLADO (las eras vacías no mandan),
  · el piso de tamaño en pantalla de la etiqueta de hito,
  · que el encuadre no dependa del `sceneRect`,
  · y la guardia del gate asimétrico de zoom de BETA1-UX2D.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    ZOOM_MIN_SCALE,
    zoom_step,
)

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from PySide6.QtCore import QRectF

    import hosts.DesktopHostPySide.widgets.chrono_canvas as cc
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _era(era_id, name, start, end, order):
    return SimpleNamespace(
        id=era_id, name=name, start_year=start, end_year=end, order=order
    )


def _hito(hito_id, title, year, entidades=()):
    return SimpleNamespace(
        id=hito_id,
        title=title,
        year=year,
        affected_entity_ids=list(entidades),
        metadata={},
    )


def _entidad(entity_id, name, birth, death=None, ring="r"):
    return SimpleNamespace(
        id=entity_id,
        name=name,
        entity_type="personaje",
        layer_ids=[ring],
        birth_year=birth,
        death_year=death,
        custom_metadata={},
        brief_description="",
    )


def _proyecto(eras, hitos, entidades, present=1400):
    chronology = SimpleNamespace(present_year=present, eras=list(eras), metadata={})
    layers = [SimpleNamespace(id="r", name="Reino", is_visible=True, order=1, metadata={})]
    entities = list(entidades)
    return SimpleNamespace(
        entities=entities,
        relations=[],
        world_layers=layers,
        causal_milestones=list(hitos),
        project_chronology=chronology,
        entity_by_id=lambda eid, es=entities: next(
            (e for e in es if str(e.id) == str(eid)), None
        ),
    )


def _mundo_de_elvira():
    """Una era VACÍA enorme delante de una era poblada pequeña."""
    eras = [
        _era("vacia", "Alta Edad Media", 500, 1300, 0),
        _era("poblada", "Siglo XIV", 1300, 1400, 1),
    ]
    entidades = [_entidad("e1", "Pedro I", 1334, 1369)]
    hitos = [
        _hito("h1", "Muerte de Alfonso XI en Gibraltar", 1350, ["e1"]),
        _hito("h2", "Llegada de la Peste Negra a Castilla", 1348, ["e1"]),
        _hito("h3", "Batalla de Montiel", 1369, ["e1"]),
    ]
    return _proyecto(eras, hitos, entidades)


def _vista(qapp, project, width=1440, height=900) -> "ChronoCanvasView":
    view = ChronoCanvasView()
    view.resize(width, height)
    view.show()
    QApplication.processEvents()
    view.set_project(project)
    view.fit_all()
    return view


@pytest_qt
def test_beta_m2fix01_encuadre_ignora_las_eras_vacias(qapp):
    # CRITERIO 5: una era sin hitos ni lapsos no puede llevarse el lienzo.
    view = _vista(qapp, _mundo_de_elvira())
    layout = view._layout
    assert layout is not None

    vacia = next(b for b in layout.eras if b.era_id == "vacia")
    poblada = next(b for b in layout.eras if b.era_id == "poblada")
    ancho_vacia = vacia.y1 - vacia.y0
    assert ancho_vacia > 0.0

    poblado = view.populated_rect()
    assert poblado is not None

    # El rect encuadrado NO contiene la era vacía entera…
    banda_vacia = view._logical_rect(0.0, vacia.y0, layout.width, vacia.y1)
    assert not poblado.contains(banda_vacia), (
        "el encuadre se sigue tragando la era vacía entera"
    )
    # …y sí contiene la poblada.
    banda_poblada = view._logical_rect(0.0, poblada.y0, layout.width, poblada.y1)
    assert poblado.intersects(banda_poblada)

    # La escala resultante es MEJOR que la que dejaría el eje completo.
    completo = view.scene().sceneRect()
    vp = view.viewport()
    escala_completo = min(vp.width() / completo.width(), vp.height() / completo.height())
    assert view.transform().m11() >= escala_completo, (
        f"encuadrar lo poblado debería acercar: {view.transform().m11():.4f} vs "
        f"{escala_completo:.4f}"
    )


@pytest_qt
def test_beta_m2fix01_etiqueta_de_hito_legible_al_abrir(qapp):
    # CRITERIO 2: al abrir, al menos una etiqueta de hito se lee (>= 11 px).
    view = _vista(qapp, _mundo_de_elvira())
    view._refresh_sticky_labels()

    escala = view.transform().m11()
    assert escala > 0.0
    assert view._milestone_label_items, "la escena debe tener rótulos de hito"

    natural = view._milestone_label_items[0]["text"].boundingRect().height()
    if natural * escala >= cc.CHRONO_LABEL_MIN_PX:
        # A esta escala los rótulos in-scene YA son legibles.
        assert not view._sticky_labels_active
        return

    # Si no, se pintan en coords de viewport y NO escalan: siempre legibles.
    assert view._sticky_labels_active, "el rótulo in-scene mediría menos de 11 px"
    etiquetas = view.sticky_milestone_labels()
    assert etiquetas, "no se pintó ni una etiqueta de hito legible"
    for etiqueta in etiquetas:
        assert etiqueta["glyph_height"] >= cc.CHRONO_LABEL_MIN_PX
        assert etiqueta["rect"].height() >= cc.CHRONO_LABEL_MIN_PX
    # …y los rótulos in-scene ilegibles quedan apagados (no se pinta dos veces).
    assert not view._milestone_label_items[0]["text"].isVisible()


@pytest_qt
def test_beta_m2fix01_fit_usa_el_contenido_no_el_scenerect(qapp):
    # CRITERIO 3/5: inflar el sceneRect a mano no puede mover el encuadre. El
    # INFORME-GLOBAL culpaba al sceneRect; el mecanismo real es otro y este test
    # deja constancia de que ya no depende de él.
    view = _vista(qapp, _mundo_de_elvira())
    antes = view.transform().m11()

    rect = view.scene().sceneRect()
    view.scene().setSceneRect(rect.adjusted(-50000, -50000, 50000, 50000))
    view.fit_all()

    assert abs(view.transform().m11() - antes) / antes < 0.02


@pytest_qt
def test_beta_m2fix01_encuadre_no_baja_del_suelo_legible(qapp):
    # CRITERIO 4: con muchos hitos repartidos por milenios, la vista encuadra un
    # tramo poblado en vez de meter el eje entero y no mostrar nada.
    eras = [_era("todo", "Toda la historia", 0, 4000, 0)]
    entidades = [_entidad(f"e{i}", f"Persona {i}", i * 12, i * 12 + 40) for i in range(60)]
    hitos = [
        _hito(f"h{i}", f"Hito numero {i} de la cronica", i * 12 + 5, [f"e{i}"])
        for i in range(60)
    ]
    view = _vista(qapp, _proyecto(eras, hitos, entidades, present=4000))

    escala = view.transform().m11()
    assert escala >= cc.CHRONO_MIN_READABLE_SCALE * 0.98, f"escala de apertura {escala:.4f}"

    view._refresh_sticky_labels()
    etiquetas = view.sticky_milestone_labels()
    assert etiquetas, "la apertura debe contener al menos un hito identificable"


@pytest_qt
def test_beta_m2fix01_encuadre_diferido_al_mostrar(qapp):
    # CRITERIO 3: encuadrar con la vista aún oculta deja el trabajo anotado y se
    # rehace al mostrarla — es el bug de `set_active_view` (fit antes de show).
    view = ChronoCanvasView()
    view.resize(100, 30)
    view.set_project(_mundo_de_elvira())
    view.fit_all()
    assert view._pending_fit is True

    view.show()
    view.resize(1440, 900)
    QApplication.processEvents()

    aparece = view.transform().m11()
    view.fit_all()
    explicito = view.transform().m11()
    assert abs(aparece - explicito) / explicito <= 0.02, (
        f"aparece a {aparece:.4f} y un fit_all explícito da {explicito:.4f}"
    )


@pytest_qt
def test_beta_m2fix01_clicar_un_hito_acerca_si_la_vista_es_ilegible(qapp):
    # El único escape de la vista ilegible tampoco te sacaba de ella:
    # `center_on_milestone` hacía `centerOn` y nada más.
    view = _vista(qapp, _mundo_de_elvira())
    view.resetTransform()
    view.scale(0.02, 0.02)  # vista deliberadamente ilegible
    assert view.center_on_milestone("h1") is True
    assert view.transform().m11() >= cc.CHRONO_MIN_READABLE_SCALE - 1e-6


def test_beta_m2fix01_zoom_step_sigue_pudiendo_acercar():
    # No-regresión de BETA1-UX2D: el gate ASIMÉTRICO existe porque `fit_all`
    # dejaba m11 por debajo de ZOOM_MIN_SCALE y no se podía acercar. Aunque el
    # nuevo encuadre ya no baje tanto, la red de seguridad se queda.
    assert zoom_step(0.001, True) is not None  # acercar SIEMPRE se puede
    assert zoom_step(0.001, False) is None  # alejar por debajo del suelo, no
    assert zoom_step(ZOOM_MIN_SCALE * 2, False) is not None


@pytest_qt
def test_beta_m2fix01_populated_rect_es_none_sin_contenido(qapp):
    # Guardia: sin hitos ni lapsos no hay contenido poblado y el encuadre cae al
    # camino de siempre en vez de reventar.
    view = ChronoCanvasView()
    view.resize(800, 600)
    view.show()
    view.set_project(_proyecto([_era("e", "Era", 0, 100, 0)], [], []))
    assert view.populated_rect() is None
    view.fit_all()  # no debe lanzar
    assert isinstance(view._fit_target_rect(), (QRectF, type(None)))
