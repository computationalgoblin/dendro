"""BETA1-UX36 — colapso de contenedores por defecto en la cronología.

A escala (1000+ entidades) el ancho explota porque cada entidad ocupa un carril.
Con ``ChronoScope(collapse_default=True)`` los contenedores se pliegan (una sola
"caja plegada" por rama, miembros ocultos), acotando el ancho; ``expanded_ids``
recuerda lo que el usuario abrió (expandir = un nivel). Default vacío = histórico.
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


def _ent(eid: str, name: str, kind: str = "personaje") -> SimpleNamespace:
    return SimpleNamespace(
        id=eid, name=name, entity_type=kind, layer_ids=[],
        birth_year=20, death_year=None, custom_metadata={}, metadata={},
    )


def _contains(source: str, target: str) -> SimpleNamespace:
    return SimpleNamespace(id=f"{source}->{target}", relation_type="contiene",
              source_id=source, target_id=target)


def _project_with_containers(n_containers: int, members_each: int) -> SimpleNamespace:
    """n contenedores de primer nivel, cada uno con ``members_each`` miembros."""
    entities: list[SimpleNamespace] = []
    relations: list[SimpleNamespace] = []
    for c in range(n_containers):
        cid = f"c{c}"
        entities.append(_ent(cid, f"Contenedor {c}", "contenedor"))
        for m in range(members_each):
            mid = f"c{c}_m{m}"
            entities.append(_ent(mid, f"Miembro {c}.{m}"))
            relations.append(_contains(cid, mid))
    return SimpleNamespace(
        entities=entities, relations=relations, world_layers=[],
        causal_milestones=[],
        project_chronology=SimpleNamespace(present_year=100, eras=[], metadata={}),
    )


def test_default_scope_no_cambia_comportamiento() -> None:
    proj = _project_with_containers(3, 5)
    a = build_chrono_layout(proj)
    b = build_chrono_layout(proj, scope=ChronoScope())
    assert len(a.lifelines) == len(b.lifelines) == 3 + 3 * 5
    assert a.width == b.width
    assert all(not box.collapsed for box in a.boxes)


def test_colapso_por_defecto_acota_ancho_y_carriles() -> None:
    proj = _project_with_containers(10, 20)  # 10 contenedores · 200 miembros
    full = build_chrono_layout(proj)
    collapsed = build_chrono_layout(proj, scope=ChronoScope(collapse_default=True))
    # Colapsado: solo los 10 contenedores tienen carril (miembros ocultos).
    assert len(collapsed.lifelines) == 10
    assert len(full.lifelines) == 10 + 200
    # El ancho cae drásticamente al plegar.
    assert collapsed.width < full.width / 4
    # Cada caja queda plegada con el recuento de miembros ocultos.
    assert {b.branch_id for b in collapsed.boxes} == {f"c{i}" for i in range(10)}
    assert all(b.collapsed and b.member_count == 20 for b in collapsed.boxes)


def test_expandir_revela_un_solo_nivel() -> None:
    # c0 contiene a sub (otro contenedor) que contiene a hoja.
    entities = [
        _ent("c0", "Raíz", "contenedor"),
        _ent("sub", "Sub", "contenedor"),
        _ent("hoja", "Hoja"),
    ]
    relations = [_contains("c0", "sub"), _contains("sub", "hoja")]
    proj = SimpleNamespace(entities=entities, relations=relations, world_layers=[],
              causal_milestones=[],
              project_chronology=SimpleNamespace(present_year=100, eras=[], metadata={}))

    # Todo colapsado: solo la raíz.
    col = build_chrono_layout(proj, scope=ChronoScope(collapse_default=True))
    assert sorted(ln.entity_id for ln in col.lifelines) == ["c0"]

    # Expandir la raíz revela su hijo directo (sub), pero NO el nieto (hoja):
    # sub sigue plegada por ser contenedor no expandido.
    exp = build_chrono_layout(
        proj, scope=ChronoScope(collapse_default=True, expanded_ids=frozenset({"c0"}))
    )
    assert sorted(ln.entity_id for ln in exp.lifelines) == ["c0", "sub"]
    sub_box = next(b for b in exp.boxes if b.branch_id == "sub")
    assert sub_box.collapsed and sub_box.member_count == 1


def test_entidades_sueltas_no_se_colapsan() -> None:
    # Una suelta (sin contenedor) sigue visible aunque collapse_default esté activo.
    entities = [_ent("c0", "Caja", "contenedor"), _ent("m", "Dentro"), _ent("libre", "Suelta")]
    relations = [_contains("c0", "m")]
    proj = SimpleNamespace(entities=entities, relations=relations, world_layers=[],
              causal_milestones=[],
              project_chronology=SimpleNamespace(present_year=100, eras=[], metadata={}))
    col = build_chrono_layout(proj, scope=ChronoScope(collapse_default=True))
    ids = sorted(ln.entity_id for ln in col.lifelines)
    assert ids == ["c0", "libre"]  # 'm' oculto; 'libre' (suelta) visible


def test_view_colapsa_por_defecto_y_toggle_expande_y_persiste() -> None:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    _ = QApplication.instance() or QApplication([])
    proj = _project_with_containers(2, 4)

    saved: dict = {}
    ctx = SimpleNamespace(
        creation_chrono_expanded_ids=[],
        save_preferences=lambda: saved.__setitem__("ids", list(ctx.creation_chrono_expanded_ids)),
    )
    view = ChronoCanvasView()
    view.set_atmosphere_context(ctx)
    view.set_project(proj)
    # Por defecto la vista colapsa: solo 2 contenedores tienen carril.
    assert len(view._layout.lifelines) == 2

    # Expandir c0 → revela sus 4 miembros (6 carriles) y persiste el id.
    view._toggle_collapse("c0")
    ids = {ln.entity_id for ln in view._layout.lifelines}
    assert "c0" in ids and {"c0_m0", "c0_m1", "c0_m2", "c0_m3"} <= ids
    assert saved.get("ids") == ["c0"]

    # Volver a clicar c0 → colapsa de nuevo y persiste el set vacío.
    view._toggle_collapse("c0")
    assert len(view._layout.lifelines) == 2
    assert saved.get("ids") == []
