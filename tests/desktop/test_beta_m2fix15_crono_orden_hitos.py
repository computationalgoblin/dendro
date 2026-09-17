"""BETA2-FIX-15 (G2-28) — los hitos del mismo año se ordenan por una
clave NUMÉRICA, no por el texto que se pinta.

El escalonado de hitos coetáneos desempataba con la cadena `sub_label`, así que la
escaleta de una temporada salía barajada a partir del noveno episodio
(«1x01, 1x10, 1x11, 1x12, 1x02…») y, con calendario completo, los meses se ordenaban
por su NOMBRE en orden alfabético. El repo ya tenía el criterio bien resuelto dos
veces (`milestone_sort_value` y `ChronologyWalkService._sort_key`); la única
implementación incorrecta era la que se ve.
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
    _milestone_sub_label,
    build_chrono_layout,
)
from hosts.DesktopHostPySide.widgets.milestone_labels import (  # noqa: E402
    milestone_order_key,
)
from packages.application.chronology_walk_service import _sort_key  # noqa: E402

# Calendario diegético cuyo orden REAL invierte el alfabético.
_MESES = [{"name": "Zafiro", "length": 30}, {"name": "Amaranto", "length": 30}]


def _ent(eid, name):
    return SimpleNamespace(
        id=eid, name=name, entity_type="personaje", layer_ids=["r0"],
        birth_year=0, death_year=None, custom_metadata={}, metadata={},
        visibility_state="visible_usuario", canon_state="canonico",
    )


def _hito(hid, title, year, **meta):
    return SimpleNamespace(
        id=hid, title=title, year=year, affected_entity_ids=[],
        metadata=dict(meta), custom_metadata={}, parent_milestone_id="",
    )


def _project(hitos, *, calendario=None):
    meta = {"calendar": {"months": list(calendario), "weekdays": ["Uno", "Dos"],
                         "week_anchor": 0}} if calendario else {}
    return SimpleNamespace(
        entities=[_ent("e0", "Testigo")], relations=[],
        world_layers=[SimpleNamespace(id="r0", name="Uno", metadata={"causal_rank": 0.0},
                                      order=0, is_visible=True)],
        causal_milestones=list(hitos),
        project_chronology=SimpleNamespace(present_year=100, eras=[], metadata=meta),
    )


def _orden_pintado(layout, year):
    """Títulos del año dado en el orden en que se LEEN sobre el eje de tiempo."""
    grupo = [m for m in layout.milestones if m.year == year]
    return [m.title for m in sorted(grupo, key=lambda m: m.y_band)]


# ── sort_index numérico ─────────────────────────────────────────────────────

def test_hitos_del_mismo_ano_ordenan_por_sort_index_numerico():
    hitos = [_hito(f"h{i}", f"1x{i:02d}", 1, sort_index=i) for i in range(1, 13)]
    layout = build_chrono_layout(_project(hitos))
    assert _orden_pintado(layout, 1) == [f"1x{i:02d}" for i in range(1, 13)]


def test_el_texto_pintado_habria_dado_el_orden_barajado():
    # Guarda del bug original: con la clave vieja (la CADENA `sub_label`) el
    # noveno episodio en adelante se colaba entre el primero y el segundo.
    hitos = [_hito(f"h{i}", f"1x{i:02d}", 1, sort_index=i) for i in range(1, 13)]
    viejo = sorted(hitos, key=lambda h: (_milestone_sub_label(h), h.title, h.id))
    assert [h.title for h in viejo][:4] == ["1x01", "1x10", "1x11", "1x12"]
    layout = build_chrono_layout(_project(hitos))
    assert _orden_pintado(layout, 1)[:4] == ["1x01", "1x02", "1x03", "1x04"]


# ── Calendario completo ─────────────────────────────────────────────────────

def test_orden_por_fecha_exacta_usa_indice_de_mes_del_calendario():
    # "Amaranto" va antes que "Zafiro" en el alfabeto, pero es el SEGUNDO mes.
    hitos = [
        _hito("h_a", "Segundo mes", 5,
              exact_date={"era": "E", "year": 5, "month": "Amaranto", "day": 1}),
        _hito("h_z", "Primer mes", 5,
              exact_date={"era": "E", "year": 5, "month": "Zafiro", "day": 20}),
    ]
    layout = build_chrono_layout(_project(hitos, calendario=_MESES))
    assert _orden_pintado(layout, 5) == ["Primer mes", "Segundo mes"]


def test_orden_por_dia_es_numerico_no_textual():
    hitos = [
        _hito("h12", "Día doce", 5,
              exact_date={"era": "E", "year": 5, "month": "Zafiro", "day": 12}),
        _hito("h3", "Día tres", 5,
              exact_date={"era": "E", "year": 5, "month": "Zafiro", "day": 3}),
    ]
    layout = build_chrono_layout(_project(hitos, calendario=_MESES))
    assert _orden_pintado(layout, 5) == ["Día tres", "Día doce"]


def test_clave_homogenea_no_revienta_al_mezclar_fecha_y_sort_index():
    # Dentro de un mismo año pueden convivir un hito con fecha exacta y otro con
    # solo `sort_index`: la clave debe ser comparable (la de `milestone_sort_value`
    # no lo es — devuelve tupla o float según la rama).
    hitos = [
        _hito("h_fecha", "Con fecha", 5,
              exact_date={"era": "E", "year": 5, "month": "Zafiro", "day": 2}),
        _hito("h_orden", "Con orden", 5, sort_index=3),
        _hito("h_nada", "Sin nada", 5),
    ]
    layout = build_chrono_layout(_project(hitos, calendario=_MESES))
    orden = _orden_pintado(layout, 5)
    assert len(orden) == 3
    # Los datados con calendario van después de los que solo traen posición.
    assert orden[-1] == "Con fecha"


# ── La etiqueta no cambia ───────────────────────────────────────────────────

def test_sub_label_sigue_siendo_la_etiqueta_pintada():
    # `sub_label` es solo TEXTO y no ha cambiado con este arreglo. OJO: el formato
    # ya no es «Orden 3» sino «3.º» — lo cambió BETA2-FIX-03 (G2-03),
    # que además dejó de pintar el «Orden 0» que fabricaba la IA.
    assert _milestone_sub_label(_hito("h", "T", 1, sort_index=3)) == "3.º"
    assert _milestone_sub_label(_hito("h", "T", 1, sort_index=0)) == ""
    assert _milestone_sub_label(_hito("h", "T", 1)) == ""
    exacto = _hito("h", "T", 1, exact_date={"era": "E", "year": 1,
                                            "month": "Nivoso", "day": 12})
    assert _milestone_sub_label(exacto) == "Nivoso 12"
    # Y sigue llegando a la marca tal cual.
    layout = build_chrono_layout(_project([_hito("h1", "T", 1, sort_index=3)]))
    assert layout.milestones[0].sub_label == "3.º"


# ── Un solo criterio en el repo ─────────────────────────────────────────────

def test_orden_de_la_vista_coincide_con_el_del_walk():
    hitos = [_hito(f"h{i}", f"1x{i:02d}", 1, sort_index=i) for i in (7, 2, 11, 1, 10)]
    layout = build_chrono_layout(_project(hitos))
    por_el_walk = [h.title for h in sorted(hitos, key=_sort_key)]
    assert _orden_pintado(layout, 1) == por_el_walk


def test_la_clave_numerica_es_la_del_repo_no_una_cuarta():
    # `milestone_order_key` desempata con `float(sort_index)`, igual que
    # `ChronologyWalkService._sort_key` y `milestone_sort_value`.
    hito = _hito("h", "T", 1, sort_index="4")
    assert milestone_order_key(hito)[2] == 4.0
    assert milestone_order_key(_hito("h", "T", 1))[2] == 0.0
    assert milestone_order_key(_hito("h", "T", 1, sort_index="ni idea"))[2] == 0.0
    # Sin meses conocidos, una fecha exacta no inventa índice de mes.
    con_fecha = _hito("h", "T", 1, exact_date={"month": "Zafiro", "day": 7})
    assert milestone_order_key(con_fecha) == (0, 7, 0.0, "T", "h")
    assert milestone_order_key(con_fecha, ["Zafiro"]) == (1, 7, 0.0, "T", "h")


# ── No romper lo que ya se testeaba ─────────────────────────────────────────

def test_offsets_siguen_siendo_simetricos():
    hitos = [_hito("h1", "Uno", 1, sort_index=1), _hito("h2", "Dos", 1, sort_index=2)]
    layout = build_chrono_layout(_project(hitos))
    offsets = sorted(m.y_offset for m in layout.milestones)
    assert offsets[0] != offsets[1]
    assert offsets[0] == pytest.approx(-offsets[1])
    for mark in layout.milestones:
        assert mark.y == pytest.approx(layout.scale.y(1))
