"""BETA2-FIX-15 (G2-25) — la Cronología no siembra un objeto gráfico
por cada cruce hito × entidad.

El sembrado de `_GhostNode` era ciego: por CADA hito recorría TODAS las líneas de
vida y creaba un marcador en el cruce con cada entidad viva no vinculada. El censo
crecía con el PRODUCTO (a 800 fichas: 137.311 fantasmas de 143.116 ítems, 96 % de
la escena, 24,9 s por cambio de vista). Aquí se fija el contrato nuevo:

- el rebuild solo siembra si el censo cabe en `CHRONO_GHOST_SEED_BUDGET`;
- por encima no siembra ninguno y los del hito APUNTADO se materializan al hover;
- la afordancia de vincular NO depende del fantasma: la resuelve
  `_resolve_band_click` sobre la franja.
"""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from hosts.DesktopHostPySide.widgets.chrono_canvas import (  # noqa: E402
    CHRONO_GHOST_SEED_BUDGET,
    ChronoCanvasView,
    _GhostNode,
    _MilestoneBand,
)


def _ent(eid, name, *, ring="r0", birth=0, death=None):
    return SimpleNamespace(
        id=eid, name=name, entity_type="personaje", layer_ids=[ring],
        birth_year=birth, death_year=death, custom_metadata={}, metadata={},
        visibility_state="visible_usuario", canon_state="canonico",
    )


def _hito(hid, title, year, affected=(), meta=None):
    return SimpleNamespace(
        id=hid, title=title, year=year, affected_entity_ids=list(affected),
        metadata=dict(meta or {}), custom_metadata={}, parent_milestone_id="",
    )


def _layer(lid, name, rank):
    return SimpleNamespace(id=lid, name=name, metadata={"causal_rank": float(rank)},
                           order=rank, is_visible=True)


def _sintetico(n_entidades: int, n_hitos: int):
    """Mundo sintético: N entidades VIVAS (nacen en el año 0, sin muerte) y M
    hitos repartidos por los años, cada uno con 2 participantes."""
    ents = [_ent(f"e{i}", f"Ficha {i}") for i in range(n_entidades)]
    hitos = [
        _hito(f"h{j}", f"Hito {j}", year=j + 1,
              affected=[f"e{j % n_entidades}", f"e{(j + 1) % n_entidades}"])
        for j in range(n_hitos)
    ]
    return SimpleNamespace(
        entities=ents, relations=[], world_layers=[_layer("r0", "Uno", 0)],
        causal_milestones=hitos,
        project_chronology=SimpleNamespace(present_year=500, eras=[], metadata={}),
    )


def _view(project):
    from PySide6.QtWidgets import QApplication

    _ = QApplication.instance() or QApplication([])
    view = ChronoCanvasView()
    view.set_project(project)
    # `set_project` traga excepciones para no tumbar la app: si el layout no se
    # construyó, cualquier censo de ítems sería un falso verde.
    assert view._layout is not None
    return view


def _censo(view, klass):
    return [item for item in view.scene().items() if isinstance(item, klass)]


def test_escena_no_siembra_fantasmas_a_ciegas():
    # 200 entidades × 40 hitos = 8.000 cruces posibles, muy por encima del
    # presupuesto → el rebuild no siembra NINGUNO.
    view = _view(_sintetico(200, 40))
    assert len(view._layout.milestones) == 40
    assert len(view._layout.lifelines) == 200
    fantasmas = _censo(view, _GhostNode)
    assert len(fantasmas) <= CHRONO_GHOST_SEED_BUDGET
    assert fantasmas == []  # opción implementada: cero sembrados por encima del tope
    assert view._ghosts_seeded is False


def test_mundo_pequeno_sigue_sembrando_como_siempre():
    # No-regresión de la afordancia visual: por debajo del presupuesto el
    # comportamiento es EXACTAMENTE el histórico (fantasma en cada cruce libre).
    view = _view(_sintetico(6, 3))
    assert view._ghosts_seeded is True
    fantasmas = _censo(view, _GhostNode)
    # 3 hitos × (6 vivas − 2 vinculadas) = 12 cruces libres.
    assert len(fantasmas) == 12


def test_escena_crece_lineal_no_cuadratica():
    pequena = _view(_sintetico(200, 40))
    grande = _view(_sintetico(400, 80))
    n_pequena = len(pequena.scene().items())
    n_grande = len(grande.scene().items())
    assert n_pequena > 0
    # Doblar el mundo cuadruplicaba los fantasmas (32.639 → 137.311). Ahora el
    # censo crece con hitos + entidades: menos del triple al doblar ambos.
    assert n_grande < 3 * n_pequena


def test_vincular_sigue_funcionando_sin_fantasma():
    # Espejo de `test_chrono_band_click_resolves_to_nearest_lane` en el mundo
    # GRANDE (sin fantasmas sembrados): un clic sobre la franja, a la altura del
    # carril de una entidad no vinculada y viva, sigue VINCULANDO.
    view = _view(_sintetico(200, 40))
    assert _censo(view, _GhostNode) == []
    view.resize(1100, 750)
    view.show()
    view.fit_all()
    out = {}
    view.milestoneEntityLinkRequested.connect(lambda m, e: out.__setitem__("link", (m, e)))
    view.milestoneActivated.connect(lambda m: out.__setitem__("hito", m))

    band = next(i for i in _censo(view, _MilestoneBand) if i.milestone_id == "h5")
    mark = next(m for m in view._layout.milestones if m.milestone_id == band.milestone_id)
    xby = {lf.entity_id: lf.x for lf in view._layout.lifelines}

    # "e100" no participa en h5 y está viva ese año → vincular.
    out.clear()
    view._dispatch_click(view.mapFromScene(view._pt(xby["e100"], mark.y_band)))
    assert out.get("link") == ("h5", "e100")

    # "e5" ya participa en h5 → abre el hito.
    out.clear()
    view._dispatch_click(view.mapFromScene(view._pt(xby["e5"], mark.y_band)))
    assert out.get("hito") == "h5"


def test_fantasmas_bajo_demanda_se_materializan_y_se_retiran():
    # Apuntar a la franja de un hito crea SUS fantasmas (y solo los suyos);
    # apuntar fuera —o salir del lienzo— los retira. Sin fugas: reconstruir la
    # escena no deja fantasmas huérfanos.
    view = _view(_sintetico(200, 40))
    view.resize(1100, 750)
    view.show()
    view.fit_all()
    assert _censo(view, _GhostNode) == []

    mark = next(m for m in view._layout.milestones if m.milestone_id == "h7")
    xby = {lf.entity_id: lf.x for lf in view._layout.lifelines}
    sobre_la_franja = view.mapFromScene(view._pt(xby["e100"], mark.y_band))
    view._update_hover_ghosts(sobre_la_franja)
    fantasmas = _censo(view, _GhostNode)
    assert fantasmas, "el hover debe materializar los fantasmas del hito apuntado"
    assert {g.milestone_id for g in fantasmas} == {"h7"}
    # Nunca en la lista de bloom/centrado (esa alimenta la germinación).
    assert all(g not in view._milestone_items.get("h7", []) for g in fantasmas)

    # Fuera de toda franja → se retiran.
    view._update_hover_ghosts(None)
    assert _censo(view, _GhostNode) == []

    # Y una reconstrucción no deja fantasmas colgados.
    view._update_hover_ghosts(sobre_la_franja)
    assert _censo(view, _GhostNode)
    view.set_project(view._project)
    assert _censo(view, _GhostNode) == []
    assert view._ghost_items == []


def test_hover_no_toca_la_escena_cuando_ya_estan_sembrados():
    # Mundo pequeño: los fantasmas viven en la escena desde el rebuild y el
    # hover no los duplica ni los borra.
    view = _view(_sintetico(6, 3))
    view.resize(1100, 750)
    view.show()
    view.fit_all()
    antes = len(_censo(view, _GhostNode))
    mark = view._layout.milestones[0]
    xby = {lf.entity_id: lf.x for lf in view._layout.lifelines}
    view._update_hover_ghosts(view.mapFromScene(view._pt(next(iter(xby.values())), mark.y_band)))
    assert len(_censo(view, _GhostNode)) == antes
