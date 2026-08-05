"""BETA-AUDIT-10: el buscador indexa alias y cuerpo, no sólo el nombre.

El heno era `name + kind + subtitle + anillo`, así que Ctrl+B sólo servía para «ir a»
un nombre que ya recuerdas. La pregunta real de quien tiene un mundo grande no es
«dónde está Nasr» sino «dónde dije que el pacto se firmó en invierno» o «el enano del
ojo de vidrio» — dos perfiles de la auditoría coincidieron en esto por separado.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.graph_canvas import (  # noqa: E402
    GraphCanvasView,
    _NodeView,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _nodo(entity_id, name, *, alias=(), cuerpo="", subtitle=""):
    entidad = SimpleNamespace(
        id=entity_id, name=name, aliases=list(alias), extended_description=cuerpo
    )
    return _NodeView(
        entity=entidad,
        entity_id=entity_id,
        name=name,
        kind="personaje",
        subtitle=subtitle,
        canon="canonico",
        visibility="publico",
    )


def _vista(qapp, nodos):
    vista = GraphCanvasView()
    vista.set_graph(nodos, [], layer_mode=False, layers=[])
    return vista


def test_encuentra_por_alias(qapp):
    vista = _vista(
        qapp,
        [_nodo("e1", "Yusuf ibn Nasr", alias=["el Tuerto", "Yusuf el viejo"])],
    )
    resultados = vista.search("tuerto")
    assert any(r.title == "Yusuf ibn Nasr" for r in resultados), (
        "no encuentra por el apodo con el que el autor lo llama de verdad"
    )


def test_encuentra_por_una_frase_del_cuerpo(qapp):
    vista = _vista(
        qapp,
        [
            _nodo(
                "e1",
                "El Pacto de los Almendros",
                cuerpo="Se firmó en pleno invierno, bajo los árboles helados de la vega.",
            ),
            _nodo("e2", "Zoraida", cuerpo="Copista de la corte."),
        ],
    )
    resultados = vista.search("invierno")
    titulos = [r.title for r in resultados]
    assert "El Pacto de los Almendros" in titulos
    assert "Zoraida" not in titulos, "el filtro dejó pasar una entidad que no cuadra"


def test_sigue_encontrando_por_nombre(qapp):
    """No regresión: ampliar el heno no puede romper el «ir a» de siempre."""
    vista = _vista(qapp, [_nodo("e1", "Granada", cuerpo="La ciudad condenada.")])
    assert any(r.title == "Granada" for r in vista.search("Granada"))


def test_todos_los_terminos_deben_aparecer(qapp):
    """La búsqueda es conjuntiva: dos palabras acotan, no amplían."""
    vista = _vista(
        qapp,
        [
            _nodo("e1", "Nasr", cuerpo="Noble militar de linaje secundario."),
            _nodo("e2", "Sharif", cuerpo="Veterano de guerra, obediente."),
        ],
    )
    assert [r.title for r in vista.search("noble linaje")] == ["Nasr"]


def test_una_entidad_sin_alias_ni_cuerpo_no_rompe(qapp):
    vista = _vista(qapp, [_nodo("e1", "Hueco")])
    assert vista.search("hueco")
    assert vista.search("nada de nada") == []
