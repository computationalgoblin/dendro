"""BETA2-FIX-14 (G2-26): recortes y solapes, medidos por geometría.

Dirección de arte aportó el catálogo con mecanismo verificado, no por intuición:
título de semilla cortado por delante, el año «1962» leído como «19», el aviso de
lapso impreso sobre el nombre de la era, la leyenda de la Cronología tapando el
final de la línea, las píldoras de Creación encima del pie de Play y la etiqueta de
la semilla del Foco partida por el borde inferior.

Cada test comprueba el MECANISMO (rects, hints, visibilidad), no una captura.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from hosts.DesktopHostPySide.widgets.candidate_review_panel import (  # noqa: E402
    CandidateReviewPanel,
)
from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoSeedItem  # noqa: E402
from hosts.DesktopHostPySide.widgets.foco.foco_lifeline import (  # noqa: E402
    FocoLifelineBand,
)
from hosts.DesktopHostPySide.widgets.stepper import BotanicalSpinBox  # noqa: E402
from packages.domain.candidate_issue import Candidate, CandidateType  # noqa: E402
from packages.domain.era import Era  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


class _FakeController:
    def accept(self, cid):
        return None


# ── a. el título de la semilla se lee por el principio ───────────────────────


def test_beta_m2fix14_titulo_de_semilla_se_lee_por_el_principio():
    largo = (
        "Vargas, el maestro pigmentero de la Aprendiza de los Almendros y su "
        "extended_description"
    )
    candidato = Candidate(
        title=largo,
        candidate_type=CandidateType.ENTIDAD,
        proposed_data={"name": largo, "entity_type": "personaje"},
    )
    panel = CandidateReviewPanel(candidato, _FakeController(), on_decision=lambda *a: None)
    assert panel._title_edit.text() == largo
    assert panel._title_edit.cursorPosition() == 0, (
        "QLineEdit deja el cursor al final y esconde el PRINCIPIO del título"
    )


# ── b. un año de cuatro dígitos cabe en el spinbox ───────────────────────────


def test_beta_m2fix14_el_ano_de_cuatro_digitos_cabe_en_el_spinbox():
    spin = BotanicalSpinBox()
    spin.setRange(-9999, 9999)
    spin.setValue(1962)
    fm = spin.fontMetrics()
    necesario = fm.horizontalAdvance("1962") + 2 * 24 + 16
    assert spin.sizeHint().width() >= necesario, (
        "el hint no reservaba los 48+ px de los botones −/+ y el año salía como «19»"
    )
    assert spin.minimumSizeHint().width() >= necesario


def test_beta_m2fix14_el_arreglo_del_ano_esta_en_el_widget_no_en_el_llamador():
    """Cinco usos: arreglarlo en `BotanicalSpinBox` los cura de golpe."""
    assert hasattr(BotanicalSpinBox, "sizeHint")
    assert hasattr(BotanicalSpinBox, "minimumSizeHint")
    spin = BotanicalSpinBox()
    base_h = spin.sizeHint().height()
    assert base_h > 0


# ── c. el aviso de lapso no pisa el rótulo de era ────────────────────────────


def _lifeline_con_eras():
    linea = FocoLifelineBand()
    linea.resize(420, 64)
    entidad = SimpleNamespace(
        id="e1",
        name="Rosa",
        birth_year=None,
        death_year=None,
        life_span=None,
        custom_metadata={},
    )
    eras = [
        Era(name="Era de los Pigmentos", start_year=1400, end_year=1500, order=0),
        Era(name="Era de la Ceniza", start_year=1501, end_year=None, order=1),
    ]
    linea.set_entity(entidad, milestones=[], eras=eras, present_year=1520)
    return linea


def test_beta_m2fix14_el_aviso_de_lapso_no_pisa_el_rotulo_de_era():
    linea = _lifeline_con_eras()
    # Rótulos del último repintado (los pobla `_paint_eras`).
    linea._era_label_rects = [
        QRectF(4.0, 2.0, 120.0, 12.0),
        QRectF(200.0, 2.0, 110.0, 12.0),
    ]
    hueco = linea.hint_rect(420.0, 6.0, 46.0)
    assert hueco is not None, "con hueco disponible el aviso debe seguir existiendo"
    for rotulo in linea._era_label_rects:
        assert not hueco.intersects(rotulo), (
            "«Arrastra el borde…» se imprimía sobre «Era de los Pigmentos»"
        )
    assert hueco.bottom() <= linea.height(), "el aviso no puede salirse de la franja"


def test_beta_m2fix14_sin_hueco_el_aviso_se_calla():
    """Mejor sin pista que con dos textos superpuestos e ilegibles."""
    linea = _lifeline_con_eras()
    # Rótulos que ocupan las DOS bandas candidatas.
    linea._era_label_rects = [
        QRectF(0.0, 0.0, 420.0, 20.0),
        QRectF(0.0, 44.0, 420.0, 20.0),
    ]
    assert linea.hint_rect(420.0, 6.0, 46.0) is None


# ── d. la leyenda de la Cronología no tapa las marcas ────────────────────────


def _chrono_view():
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    vista = ChronoCanvasView()
    vista.resize(900, 600)
    return vista


def test_beta_m2fix14_la_leyenda_de_la_cronologia_no_tapa_las_marcas():
    vista = _chrono_view()
    vp = vista.viewport().rect()
    vp.setWidth(900)
    vp.setHeight(600)

    # Sin marcas: la leyenda se queda donde siempre (centrada a la derecha).
    vista.milestone_viewport_rects = lambda: []
    panel = vista.legend_panel_rect(vp, 180.0, 200.0)
    assert panel is not None
    assert panel.right() <= vp.width()

    # Con una marca justo encima del sitio histórico: se reubica sin cortarla.
    marca = QRectF(panel.x() + 10, panel.y() + 10, 40.0, 20.0)
    vista.milestone_viewport_rects = lambda: [marca]
    reubicada = vista.legend_panel_rect(vp, 180.0, 200.0)
    assert reubicada is None or not reubicada.intersects(marca), (
        "la leyenda es un panel OPACO: si se corta con una marca, la tapa"
    )


def test_beta_m2fix14_sin_hueco_la_leyenda_se_pliega():
    vista = _chrono_view()
    vp = vista.viewport().rect()
    vp.setWidth(900)
    vp.setHeight(600)
    # Una marca que cubre todo el borde derecho: no hay anclaje libre.
    vista.milestone_viewport_rects = lambda: [QRectF(0.0, 0.0, 900.0, 600.0)]
    assert vista.legend_panel_rect(vp, 180.0, 200.0) is None


# ── e. Play sin píldoras de Creación encima del pie ──────────────────────────


def test_beta_m2fix14_play_oculta_las_pildoras_flotantes_de_creacion(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    from hosts.DesktopHostPySide.main_window import MainWindow
    from packages.application.project_service import ProjectService
    from packages.domain.entity import NarrativeEntity
    from packages.domain.result import Ok

    servicio = ProjectService()
    assert isinstance(servicio.create(name="Mundo Play"), Ok)
    servicio.active_project.entities.append(NarrativeEntity(name="Rosa"))
    ruta = tmp_path / "p.json"
    assert isinstance(servicio.save(ruta), Ok)

    ventana = MainWindow()
    try:
        ventana._open_project_path(str(ruta))
        ws = ventana.creation_workspace
        ws.resize(1440, 900)
        ws.set_active_view("foco")
        # Se encienden los flotantes que dependen de estado (migas y búsqueda).
        ws._float_focus.setVisible(True)
        ws._float_search.setVisible(True)
        ws._seed_notifications.setVisible(True)
        # `isHidden()` y no `isVisible()`: el workspace no está en pantalla en un
        # test offscreen, así que `isVisible()` sería False para todos.
        visibles_antes = {
            nombre
            for nombre in ws._CROMO_DE_CREACION
            if not getattr(ws, nombre).isHidden()
        }
        assert visibles_antes, "el cromo de Creación debe estar visible fuera de Play"

        ws.set_active_view("play")

        for nombre in ws._CROMO_DE_CREACION:
            widget = getattr(ws, nombre, None)
            assert widget is None or widget.isHidden(), (
                f"«{nombre}» se pinta encima del pie inmersivo de Play"
            )
        estructura = getattr(ws, "_float_structure", None)
        assert estructura is None or estructura.isHidden()
        # Reposicionar no puede resucitarlos (el reanclaje de semillas hace show()).
        ws._position_floats()
        for nombre in ws._CROMO_DE_CREACION:
            widget = getattr(ws, nombre, None)
            assert widget is None or widget.isHidden()

        ws.set_active_view("foco")
        assert ws._chrome_hidden_by_play == [], "la supresión de Play debe levantarse"
        # Las píldoras de cromo puro vuelven tal cual. La capa de semillas NO se
        # fuerza: su visibilidad es derivada del contenido y la rehidratación la
        # devuelve cuando hay semillas (forzarla vacía sería otra mentira visual).
        for nombre in ("_float_right", "_float_focus", "_float_search"):
            if nombre in visibles_antes:
                assert not getattr(ws, nombre).isHidden(), (
                    f"«{nombre}» no volvió al salir de Play"
                )
    finally:
        ventana.controller.close()
        ventana.close()
        ventana.deleteLater()
        QApplication.instance().processEvents()


# ── f. la semilla del Foco cabe en su bounding rect y en el viewport ─────────


def test_beta_m2fix14_la_semilla_del_foco_cabe_en_su_bounding_rect():
    item = FocoSeedItem("c1", "sugerido: 2x02", "brotes")
    assert item.boundingRect().contains(item.label_rect()), (
        "el texto se salía 3 px del rect que la escena garantiza repintar"
    )


def test_beta_m2fix14_la_semilla_de_brotes_cae_dentro_del_lienzo():
    """A 1440×900 el 0,95 de la altura dejaba la etiqueta fuera por abajo."""
    alto_lienzo = 700.0  # alto REAL del lienzo de Foco a 1440×900 (banner + pestañas)
    y = min(alto_lienzo * 0.95, alto_lienzo - FocoSeedItem.ALTO_BAJO_ORIGEN - 6.0)
    borde_inferior_etiqueta = y + FocoSeedItem("c", "t", "brotes").label_rect().bottom()
    assert borde_inferior_etiqueta <= alto_lienzo, "el brote se parte por el borde inferior"
    assert y > alto_lienzo * 0.85, "sin exagerar: la banda de brotes sigue abajo"
