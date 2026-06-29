"""BETA1-UX37/38/39 — filtros, ventana temporal y agregación de sueltas (capa pura).

`build_chrono_layout(project, scope=...)` acota QUÉ se emite sin tocar el dominio:
filtros (tipo/anillo/foco/secreto/canon), ventana de años, y agregación de sueltas.
Default = histórico (todo visible).
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
    ChronoScope,
    build_chrono_layout,
)


def _ent(eid, name, *, kind="personaje", ring="", birth=20, death=None,
         visibility="visible_usuario", canon="canonico"):
    return SimpleNamespace(
        id=eid, name=name, entity_type=kind, layer_ids=[ring] if ring else [],
        birth_year=birth, death_year=death, custom_metadata={}, metadata={},
        visibility_state=visibility, canon_state=canon,
    )


def _layer(lid, name, rank):
    return SimpleNamespace(id=lid, name=name, metadata={"causal_rank": float(rank)},
                           order=rank, is_visible=True)


def _ids(layout):
    return {ln.entity_id for ln in layout.lifelines}


def _chron(present=100, eras=None):
    return SimpleNamespace(present_year=present, eras=eras or [], metadata={})


def _two_ring_project():
    ents = [
        _ent("a", "A", ring="r0"), _ent("b", "B", ring="r0"),
        _ent("c", "C", ring="r1"), _ent("d", "D", ring="r1", kind="lugar"),
    ]
    return SimpleNamespace(
        entities=ents, relations=[], world_layers=[_layer("r0", "Uno", 0), _layer("r1", "Dos", 1)],
        causal_milestones=[],
        project_chronology=SimpleNamespace(present_year=100, eras=[], metadata={}),
    )


# ── UX37: filtros + foco de anillo ──────────────────────────────────────────

def test_default_scope_muestra_todo():
    proj = _two_ring_project()
    assert _ids(build_chrono_layout(proj)) == {"a", "b", "c", "d"}


def test_foco_de_anillo_deja_solo_ese_anillo():
    proj = _two_ring_project()
    out = build_chrono_layout(proj, scope=ChronoScope(focused_ring_id="r1"))
    assert _ids(out) == {"c", "d"}


def test_filtro_por_tipo():
    proj = _two_ring_project()
    out = build_chrono_layout(proj, scope=ChronoScope(entity_types=frozenset({"lugar"})))
    assert _ids(out) == {"d"}


def test_filtro_oculta_secretos():
    proj = _two_ring_project()
    proj.entities.append(_ent("s", "Secreta", ring="r0", visibility="secreto_mundo"))
    full = build_chrono_layout(proj)
    assert "s" in _ids(full)
    hidden = build_chrono_layout(proj, scope=ChronoScope(hide_secret=True))
    assert "s" not in _ids(hidden)


# ── UX38: ventana temporal ──────────────────────────────────────────────────

def test_ventana_temporal_recorta_por_solape():
    ents = [
        _ent("early", "Temprana", birth=10, death=50),
        _ent("mid", "Media", birth=80, death=120),
        _ent("alive", "Viva", birth=5, death=None),  # viva → solapa siempre arriba
    ]
    proj = SimpleNamespace(entities=ents, relations=[], world_layers=[], causal_milestones=[],
                           project_chronology=_chron(200))
    out = build_chrono_layout(proj, scope=ChronoScope(year_min=100, year_max=150))
    # 'early' (10-50) queda fuera; 'mid' (80-120) solapa; 'alive' (5-…) solapa.
    assert _ids(out) == {"mid", "alive"}


def test_ventana_temporal_oculta_eras_fuera_de_rango():
    eras = [
        SimpleNamespace(id="e0", name="Antigua", start_year=0, end_year=40, order=0),
        SimpleNamespace(id="e1", name="Media", start_year=90, end_year=140, order=1),
    ]
    proj = SimpleNamespace(
        entities=[_ent("x", "X", birth=100, death=130)], relations=[], world_layers=[],
        causal_milestones=[],
        project_chronology=_chron(200, eras),
    )
    out = build_chrono_layout(proj, scope=ChronoScope(year_min=80, year_max=160))
    era_ids = {b.era_id for b in out.eras}
    assert "e1" in era_ids and "e0" not in era_ids


# ── UX39: agregación de sueltas ─────────────────────────────────────────────

def test_aggregate_loose_saca_sueltas_y_las_cuenta():
    ents = [_ent("caja", "Caja", kind="contenedor", ring="r0")]
    rels = [SimpleNamespace(id="r", relation_type="contiene", source_id="caja", target_id="m")]
    ents.append(_ent("m", "Miembro", ring="r0"))
    ents += [_ent(f"libre{i}", f"L{i}", ring="r0") for i in range(5)]
    proj = SimpleNamespace(entities=ents, relations=rels,
                           world_layers=[_layer("r0", "Uno", 0)], causal_milestones=[],
                           project_chronology=_chron(100))
    out = build_chrono_layout(proj, scope=ChronoScope(aggregate_loose=True))
    # Solo el contenedor queda como carril (su miembro lo oculta el colapso por defecto
    # NO está activo aquí, pero 'm' tiene padre → no es suelto; las 5 libres se agregan).
    ids = _ids(out)
    assert "caja" in ids and "m" in ids  # contenedor y su miembro (con padre) siguen
    assert not any(i.startswith("libre") for i in ids)  # las sueltas no ocupan carril
    assert out.loose_counts.get("r0") == 5


def test_aggregate_loose_default_off_muestra_sueltas():
    ents = [_ent("libre", "Libre", ring="r0")]
    proj = SimpleNamespace(entities=ents, relations=[], world_layers=[_layer("r0", "Uno", 0)],
                           causal_milestones=[],
                           project_chronology=_chron(100))
    out = build_chrono_layout(proj)
    assert _ids(out) == {"libre"}
    assert out.loose_counts == {}
