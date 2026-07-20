"""Semillas (Fase A): capa de notificaciones (círculos palpitantes)."""

from __future__ import annotations

import pytest

from hosts.DesktopHostPySide.widgets.seed_notifications import SeedNotificationLayer


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def parent(qapp):
    from PySide6.QtWidgets import QWidget

    p = QWidget()
    p.resize(800, 600)
    yield p  # se mantiene vivo durante el test (si no, Qt lo destruye)
    p.deleteLater()


def test_add_and_remove(parent):
    layer = SeedNotificationLayer(parent)
    layer.add("c1", "Hermano traidor")
    layer.add("c2", "Hermana traidora")
    assert set(layer.notifications) == {"c1", "c2"}
    assert not layer.isHidden()  # mostrada al haber notificaciones
    layer.remove("c1")
    assert set(layer.notifications) == {"c2"}
    layer.clear()
    assert layer.notifications == {}
    assert layer.isHidden()  # oculta al quedar vacía


def test_click_candidate_emits_review_request(parent):
    layer = SeedNotificationLayer(parent)
    seen = []
    layer.reviewRequested.connect(seen.append)
    layer.add("c1", "Algo")
    layer.notifications["c1"].clicked.emit("c1")
    assert seen == ["c1"]


def test_click_error_dismisses_without_review(parent):
    layer = SeedNotificationLayer(parent)
    seen = []
    layer.reviewRequested.connect(seen.append)
    layer.add("error:job1", "Falló", kind="error")
    layer.notifications["error:job1"].clicked.emit("error:job1")
    assert seen == []  # error no abre revisión
    assert "error:job1" not in layer.notifications  # se descarta


def test_anchored_bottom_right(parent):
    layer = SeedNotificationLayer(parent)
    layer.add("c1", "x")
    # Esquina inferior derecha: dentro del padre y pegado al borde.
    assert layer.x() + layer.width() <= parent.width()
    assert layer.y() + layer.height() <= parent.height()
    assert layer.x() > parent.width() // 2


# ── BETA2-JARDIN-03 + UI2-04: badge de riego, regar todas y recorrido ──────


def test_thirsty_badge_counts_and_shows(parent):
    layer = SeedNotificationLayer(parent)
    assert layer.isHidden()
    layer.set_thirsty(["e1", "e2", "e3"])
    assert layer.thirsty_ids == ["e1", "e2", "e3"]
    assert not layer.isHidden()  # visible aunque no haya semillas
    # UI2-04: gota SVG teñida + texto sin emoji (los emojis de color rompen la paleta).
    assert "3 por regar" in layer._water_badge.text()
    assert "💧" not in layer._water_badge.text()
    assert not layer._water_badge.icon().isNull()
    layer.set_thirsty([])
    assert layer.isHidden()  # sin sedientas ni semillas → capa oculta


def test_water_badge_click_requests_water_all(parent):
    # UI2-04: el clic primario pide regar TODAS (una sola emisión con la cola
    # completa); la autorización visible vive en el workspace.
    layer = SeedNotificationLayer(parent)
    all_requests: list[list[str]] = []
    tours: list[str] = []
    layer.waterAllRequested.connect(all_requests.append)
    layer.thirstyRequested.connect(tours.append)
    layer.set_thirsty(["vieja", "media", "nueva"])
    layer._water_badge.click()
    assert all_requests == [["vieja", "media", "nueva"]]
    assert tours == []  # el clic ya no recorre


def test_thirsty_tour_cycles_oldest_first(parent):
    # UI2-04: el recorrido sobrevive como acción secundaria (emit_next_thirsty,
    # expuesto en el menú contextual del badge).
    layer = SeedNotificationLayer(parent)
    seen: list[str] = []
    layer.thirstyRequested.connect(seen.append)
    layer.set_thirsty(["vieja", "media", "nueva"])
    for _ in range(4):
        layer.emit_next_thirsty()
    # Recorrido cíclico empezando por la más antigua.
    assert seen == ["vieja", "media", "nueva", "vieja"]


def test_thirsty_refresh_keeps_cycle_within_bounds(parent):
    layer = SeedNotificationLayer(parent)
    seen: list[str] = []
    layer.thirstyRequested.connect(seen.append)
    layer.set_thirsty(["a", "b", "c"])
    layer.emit_next_thirsty()  # emite "a", índice → 1
    layer.set_thirsty(["b"])  # tras regar a y c, la cola encoge
    layer.emit_next_thirsty()
    assert seen == ["a", "b"]  # el índice se reajusta, sin IndexError


def test_water_badge_shows_batch_progress_and_restores(parent):
    # UI2-04/FOCO-35: durante el lote, la píldora informa «Regando D/T…» y sigue
    # clicable (abre el popover de progreso); al terminar restaura el conteo.
    layer = SeedNotificationLayer(parent)
    layer.set_thirsty(["a", "b", "c"])
    layer.set_watering_progress(1, 3)
    assert "Regando 1/3" in layer._water_badge.text()
    assert layer._water_badge.isEnabled()  # FOCO-35: clicable en lote
    # Un refresco de la cola en mitad del lote NO pisa el progreso.
    layer.set_thirsty(["b", "c"])
    assert "Regando 1/3" in layer._water_badge.text()
    layer.set_watering_progress(0, 0)
    assert layer._water_badge.isEnabled()
    assert "2 por regar" in layer._water_badge.text()


def test_thirsty_coexists_with_seed_badge(parent):
    layer = SeedNotificationLayer(parent)
    layer.add("c1", "Semilla")
    layer.set_thirsty(["e1"])
    assert not layer._count_badge.isHidden()
    assert not layer._water_badge.isHidden()
    # Quitar las semillas no oculta la capa mientras queden sedientas.
    layer.clear()
    assert not layer.isHidden()


# ── BETA2-PULIDO-01: re-anclaje medido, ranuras estables y píldoras unificadas ─


def _settle_events(qapp):
    # Vacía los singleShot(0) del asentamiento diferido.
    qapp.processEvents()
    qapp.processEvents()


def test_layer_stays_inside_parent_after_growing(qapp, parent):
    parent.show()
    layer = SeedNotificationLayer(parent)
    layer.add("c1", "Semilla")
    layer.set_thirsty(["e1", "e2"])
    _settle_events(qapp)
    geo = layer.geometry()
    # Con las dos píldoras medidas, la capa queda entera dentro del padre
    # (antes crecía hacia abajo tras el move y pisaba la píldora Guardar).
    assert geo.bottom() <= parent.height()
    assert geo.height() >= 2 * layer._count_badge.height()


def test_water_badge_slot_is_stable(qapp, parent):
    parent.show()
    layer = SeedNotificationLayer(parent)
    layer.set_thirsty(["e1"])
    _settle_events(qapp)
    before = layer._water_badge.mapTo(parent, layer._water_badge.rect().topLeft())
    # Aparece el badge 🌱 (ranura superior): el 💧 NO debe moverse.
    layer.add("c1", "Semilla")
    _settle_events(qapp)
    after = layer._water_badge.mapTo(parent, layer._water_badge.rect().topLeft())
    assert before == after


def test_pills_share_style_with_hover(parent):
    layer = SeedNotificationLayer(parent)
    for badge in (layer._count_badge, layer._water_badge):
        style = badge.styleSheet()
        assert ":hover" in style and ":pressed" in style
        assert "#FCF8EC" in style  # INK_INVERSE (texto claro sobre oro)
        assert badge.height() == layer._count_badge.height()  # misma altura fija
