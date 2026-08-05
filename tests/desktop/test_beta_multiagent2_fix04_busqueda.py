"""BETA-MULTIAGENT2-FIX-04 — la búsqueda deja de expulsar la ficha que buscas.

Hallazgo **G2-04** (BLOQUEANTE) de la 2ª ronda de beta testing multi-agente.
Rubén sembró la **Posada del Cuervo Ahogado** en un mundo de 800 fichas y al
final no pudo encontrarla: la barra le enseñó ocho resultados
``['Busca', 'Posee', 'Posee', 'Oculta', ...]`` y ninguno era ella. El desempate
del orden era ``len(titulo)``, así que sus propias relaciones —de nombre corto—
la echaron de su propia búsqueda. Su diagnóstico: *«el criterio de expulsión es
estar muy relacionado»*.

Esta suite fija los cuatro contratos del arreglo:

1. **Agrupación por clase**: una relación no precede nunca a una entidad ni a
   una rama, y la longitud del título no interviene en el orden.
2. **Plegado de acentos** en los dos sentidos y en las dos superficies
   (entidades y hitos), con filtro por TÉRMINOS también en los hitos.
3. **La barra dice la verdad sobre el volumen** (total real, no el tope) y una
   relación se distingue de otra del mismo tipo (origen → destino).
4. **Coste lineal por pulsación**: se acabaron los dos escaneos de ``_all_nodes``
   por cada arista del proyecto.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from hosts.DesktopHostPySide.views.workspaces import (  # noqa: E402
    CreationWorkspace,
    _FloatingSearchBar,
)
from hosts.DesktopHostPySide.widgets.graph_canvas import (  # noqa: E402
    SEARCH_MAX_RESULTS,
    GraphCanvasView,
    _EdgeView,
    _NodeView,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── constructores ────────────────────────────────────────────────────────────


def _nodo(entity_id, name, *, kind="personaje", alias=(), cuerpo="", subtitle=""):
    entidad = SimpleNamespace(
        id=entity_id, name=name, aliases=list(alias), extended_description=cuerpo
    )
    return _NodeView(
        entity=entidad,
        entity_id=entity_id,
        name=name,
        kind=kind,
        subtitle=subtitle,
        canon="canonico",
        visibility="publico",
    )


def _arista(relation_id, source_id, target_id, *, kind="posee", label=""):
    return _EdgeView(
        relation=SimpleNamespace(id=relation_id),
        relation_id=relation_id,
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        label=label,
    )


def _vista_directa(nodos, aristas=()):
    """Vista SIN dibujar: ``search`` no pinta, así que basta con poblar el modelo.

    Evita el coste (y la fragilidad) de renderizar decenas de ítems Qt.
    """
    vista = GraphCanvasView()
    vista._all_nodes = list(nodos)
    vista._all_edges = list(aristas)
    return vista


class _CtrlHitos:
    def __init__(self, hitos):
        self._hitos = list(hitos)

    def list_all(self):
        return list(self._hitos)


def _hito(mid, title):
    return SimpleNamespace(id=mid, title=title, milestone_type=SimpleNamespace(value="pacto"))


def _workspace(vista, hitos=()):
    """CreationWorkspace mínimo (patrón de test_l02b_search_bar): solo lo que
    `_unified_search` / `_on_search_overlay_text` necesitan."""
    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws.graph = vista
    ws._milestone_ctrl = _CtrlHitos(hitos) if hitos else None
    ws._float_search = None
    ws._search_nav_timer = None
    ws._search_pending_item = None
    return ws


# ── 1. el caso Cuervo: la entidad no la desplazan sus relaciones ─────────────


def _mundo_cuervo():
    """La posada + diez relaciones suyas, todas coincidentes con «cuervo» porque
    el heno de una arista incluye los nombres de sus extremos."""
    posada = _nodo("posada", "Posada del Cuervo Ahogado", kind="lugar")
    vecinos = [_nodo(f"v{i}", f"Vecino {i}") for i in range(10)]
    tipos = [
        "busca",
        "posee",
        "posee",
        "oculta",
        "protege",
        "deriva_de",
        "traiciono",
        "depende_de",
        "vive_en",
        "teme",
    ]
    aristas = [
        _arista(f"r{i}", "posada", f"v{i}", kind=tipos[i], label=tipos[i].replace("_", " "))
        for i in range(10)
    ]
    return [posada, *vecinos], aristas


def test_beta_m2fix04_la_entidad_no_es_desplazada_por_sus_relaciones(qapp):
    nodos, aristas = _mundo_cuervo()
    ws = _workspace(_vista_directa(nodos, aristas))

    items = ws._unified_search("cuervo")

    assert items, "la búsqueda no devolvió nada"
    assert items[0]["title"] == "Posada del Cuervo Ahogado", (
        "la ficha buscada sigue sin ser la primera: la expulsan sus propias "
        f"relaciones ({[it['title'] for it in items]})"
    )
    assert items[0]["clase"] == "entity"
    # Y el total no miente: la posada + sus diez relaciones.
    assert items.total == 11


def test_beta_m2fix04_el_salto_automatico_cae_sobre_la_ficha_y_no_sobre_una_arista(qapp):
    """Criterio 7: el debounce navega al PRIMER resultado del orden nuevo."""
    nodos, aristas = _mundo_cuervo()
    ws = _workspace(_vista_directa(nodos, aristas))

    ws._on_search_overlay_text("cuervo")

    pendiente = ws._search_pending_item
    assert pendiente is not None
    assert pendiente["clase"] == "entity"
    assert pendiente["title"] == "Posada del Cuervo Ahogado"


def test_beta_m2fix04_una_relacion_nunca_precede_a_una_entidad_o_rama(qapp):
    nodos = [
        _nodo("t1", "Casa del Cuervo", kind="contenedor"),  # rama
        _nodo("e1", "Zahara del Cuervo"),  # entidad (alfabéticamente la última)
        _nodo("e2", "Vecino"),
    ]
    aristas = [
        _arista("r1", "e1", "e2", kind="posee", label="Cuervo"),
        _arista("r2", "e2", "e1", kind="busca", label="Cuervo"),
    ]
    ws = _workspace(_vista_directa(nodos, aristas))

    items = ws._unified_search("cuervo")

    clases = [it["clase"] for it in items]
    assert set(clases) == {"tree", "entity", "relation"}, clases
    ultima_ficha = max(i for i, clase in enumerate(clases) if clase in {"entity", "tree"})
    primera_relacion = min(i for i, clase in enumerate(clases) if clase == "relation")
    assert primera_relacion > ultima_ficha, (
        f"una relación se coló por delante de una ficha: {clases}"
    )


def test_beta_m2fix04_el_orden_no_depende_de_la_longitud_del_titulo(qapp):
    # Misma calidad de coincidencia (palabra completa en el nombre) y longitudes
    # muy distintas: con el criterio viejo ganaba la corta; ahora manda el
    # alfabético, que es el ÚLTIMO desempate.
    nodos = [
        _nodo("e1", "Zarza Cuervo"),  # 12 caracteres
        _nodo("e2", "Posada del Cuervo Ahogado"),  # 25 caracteres
    ]
    ws = _workspace(_vista_directa(nodos))

    titulos = [it["title"] for it in ws._unified_search("cuervo")]
    assert titulos == ["Posada del Cuervo Ahogado", "Zarza Cuervo"]

    # Y la mejor coincidencia gana aunque su título sea largo: prefijo > palabra.
    nodos = [
        _nodo("e1", "Ala Cuervo"),  # palabra completa
        _nodo("e2", "Cuervo Ahogado de la Posada Vieja"),  # prefijo, 32 caracteres
    ]
    ws = _workspace(_vista_directa(nodos))
    titulos = [it["title"] for it in ws._unified_search("cuervo")]
    assert titulos == ["Cuervo Ahogado de la Posada Vieja", "Ala Cuervo"]


# ── 2. acentos y términos ────────────────────────────────────────────────────


def test_beta_m2fix04_plegado_de_acentos_en_ambos_sentidos(qapp):
    nodos = [
        _nodo("e1", "Crónica de los Almendros"),  # con tilde en el canon
        _nodo("e2", "Cronica sin Tilde"),  # sin tilde en el canon
        _nodo("e3", "Situación de la Geografía", kind="concepto"),
    ]
    hitos = [_hito("m1", "Crónica del Sitio")]
    ws = _workspace(_vista_directa(nodos), hitos)

    # Sin tilde encuentra lo acentuado (el bug del beta: `cronica` → 0 resultados)…
    sin_tilde = {it["title"] for it in ws._unified_search("cronica")}
    assert "Crónica de los Almendros" in sin_tilde
    assert "Crónica del Sitio" in sin_tilde, "los HITOS no pliegan acentos"
    # …y con tilde encuentra lo que se escribió sin ella.
    con_tilde = {it["title"] for it in ws._unified_search("Crónica")}
    assert {"Crónica de los Almendros", "Cronica sin Tilde"} <= con_tilde

    assert [it["title"] for it in ws._unified_search("Geografia")] == [
        "Situación de la Geografía"
    ]
    assert [it["title"] for it in ws._unified_search("Situacion")] == [
        "Situación de la Geografía"
    ]


def test_beta_m2fix04_los_hitos_se_filtran_por_terminos_como_las_entidades(qapp):
    hitos = [_hito("m1", "Llegada de la Peste Negra"), _hito("m2", "Coronación")]
    ws = _workspace(_vista_directa([]), hitos)

    # El orden de los términos no importa (antes se comparaba la consulta ENTERA).
    assert [it["title"] for it in ws._unified_search("negra peste")] == [
        "Llegada de la Peste Negra"
    ]
    assert [it["title"] for it in ws._unified_search("peste negra")] == [
        "Llegada de la Peste Negra"
    ]
    # Y sigue siendo conjuntiva: dos palabras acotan, no amplían.
    assert ws._unified_search("peste coronacion") == []


# ── 3. la barra dice la verdad ───────────────────────────────────────────────


def test_beta_m2fix04_la_barra_declara_el_total_de_coincidencias(qapp):
    nodos = [_nodo(f"e{i}", f"Ficha del Cuervo {i:02d}") for i in range(20)]
    ws = _workspace(_vista_directa(nodos))

    items = ws._unified_search("cuervo")

    assert len(items) == 8  # el tope visible no cambia…
    assert items.total == 20  # …pero el recuento es el real
    texto = _FloatingSearchBar.texto_de_recuento(len(items), items.total)
    assert "8" in texto and "20" in texto, texto
    # Y hay forma de llegar al resto: «Ver más» amplía el tope visible.
    ws._show_more_search_results()
    ampliados = ws._unified_search("cuervo")
    assert len(ampliados) == 16
    assert ampliados.total == 20
    assert "16 de 20" in _FloatingSearchBar.texto_de_recuento(16, 20)


class _WorkspaceFalso(QWidget):
    """Padre mínimo de la barra flotante (solo los métodos que conecta)."""

    def __init__(self):
        super().__init__()
        self.ampliada = 0

    def _close_search_overlay(self):
        pass

    def _on_search_overlay_text(self, texto):
        pass

    def _navigate_search_item(self, item):
        return True

    def _show_more_search_results(self):
        self.ampliada += 1


def test_beta_m2fix04_la_barra_pinta_el_recuento_y_ofrece_el_resto(qapp):
    """La barra de verdad (widget Qt), no solo el cálculo."""
    padre = _WorkspaceFalso()
    barra = _FloatingSearchBar(padre)
    items = [
        {"kind": "graph", "title": f"Ficha {i}", "type_label": "Lugar", "summary": ""}
        for i in range(8)
    ]

    barra.set_results(items, total=47)

    pintados = [
        barra.results_layout.itemAt(i).widget() for i in range(barra.results_layout.count())
    ]
    etiquetas = [w for w in pintados if isinstance(w, QLabel)]
    assert len(etiquetas) == 1, "la barra no dice cuántas coincidencias hay"
    assert "8 de 47" in etiquetas[0].text()
    botones = [w for w in pintados if isinstance(w, QPushButton)]
    assert botones[-1].text() == "Ver más resultados"
    botones[-1].click()
    assert padre.ampliada == 1  # hay forma de llegar al resto

    # Con todo a la vista no hay «Ver más» y el recuento no promete un resto.
    barra.set_results(items[:3], total=3)
    pintados = [
        barra.results_layout.itemAt(i).widget() for i in range(barra.results_layout.count())
    ]
    assert not [w for w in pintados if isinstance(w, QPushButton) and "Ver más" in w.text()]
    assert [w for w in pintados if isinstance(w, QLabel)][0].text() == "3 coincidencias"


def test_beta_m2fix04_el_tope_interno_de_search_deja_de_mentir(qapp):
    """El recorte a 40 del lienzo acota el coste, no la verdad (criterio 4)."""
    nodos = [_nodo(f"e{i}", f"Cuervo {i:03d}") for i in range(SEARCH_MAX_RESULTS + 5)]
    vista = _vista_directa(nodos)

    resultados = vista.search("cuervo")

    assert len(resultados) == SEARCH_MAX_RESULTS
    assert resultados.total == SEARCH_MAX_RESULTS + 5


def test_beta_m2fix04_una_relacion_se_distingue_de_otra_del_mismo_tipo(qapp):
    nodos = [
        _nodo("posada", "Posada del Cuervo Ahogado", kind="lugar"),
        _nodo("tomas", "Tomás Vareal"),
        _nodo("elvira", "Elvira la Sorda"),
    ]
    aristas = [
        _arista("r1", "posada", "tomas", kind="posee"),
        _arista("r2", "posada", "elvira", kind="posee"),
    ]
    ws = _workspace(_vista_directa(nodos, aristas))

    relaciones = [it for it in ws._unified_search("cuervo") if it["clase"] == "relation"]
    assert len(relaciones) == 2
    assert relaciones[0]["title"] == relaciones[1]["title"]  # las dos se llaman «Posee»
    resumenes = {it["summary"] for it in relaciones}
    assert resumenes == {
        "Posada del Cuervo Ahogado → Tomás Vareal",
        "Posada del Cuervo Ahogado → Elvira la Sorda",
    }
    # Y el botón de la barra PINTA ese resumen (antes se leían las dos igual).
    doble = SimpleNamespace(workspace=None)
    etiquetas = {_FloatingSearchBar._result_button(doble, it).text() for it in relaciones}
    assert len(etiquetas) == 2, f"dos relaciones distintas se leen igual: {etiquetas}"


# ── 4. coste por pulsación ───────────────────────────────────────────────────


class _ListaEspia(list):
    """Lista que cuenta cuántas veces se la recorre."""

    def __init__(self, items):
        super().__init__(items)
        self.recorridos = 0

    def __iter__(self):
        self.recorridos += 1
        return super().__iter__()


def test_beta_m2fix04_el_coste_por_tecla_no_es_cuadratico(qapp):
    # 20 nodos y 30 aristas: antes eran 1 + 2×30 = 61 recorridos de `_all_nodes`
    # por pulsación (en el mundo del beta, 2,8 M de comparaciones por tecla).
    nodos = _ListaEspia([_nodo(f"e{i}", f"Ficha {i}") for i in range(20)])
    aristas = [_arista(f"r{i}", f"e{i % 20}", f"e{(i + 1) % 20}") for i in range(30)]
    vista = GraphCanvasView()
    vista._all_nodes = nodos
    vista._all_edges = aristas

    vista.search("ficha")

    assert nodos.recorridos <= 2, (
        f"`search` recorre `_all_nodes` {nodos.recorridos} veces por pulsación: "
        "el índice por entity_id no está haciendo su trabajo"
    )
