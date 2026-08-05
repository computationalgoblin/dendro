"""BETA-AUDIT-03: guarda del proyecto de ejemplo que viaja en el zip.

El ejemplo es la via de entrada principal de un usuario nuevo («Abrir proyecto de
ejemplo» en el Inicio), y estaba sin curar: 6 de 10 entidades conservaban el nombre
marcador «Nueva hoja»/«Nueva rama», los 5 hitos se llamaban «Nuevo hito», no habia
ni un anillo que dibujar, y dos paginas de wiki describian literalmente los huecos
(«Entidad placeholder…», «en estado de esqueleto»).

Estos tests fallan si vuelve a degradarse. Son JSON puro y sin Qt para que corran en
la puerta rapida.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from packages.persistence.store import ProjectStore

RAIZ = pathlib.Path(__file__).resolve().parents[1]
EJEMPLO = RAIZ / "ejemplos" / "La Flor de los Almendros" / "La Flor de Los Almendros.json"
IMAGENES = (
    RAIZ
    / "ejemplos"
    / "La Flor de los Almendros"
    / "La Flor de Los Almendros.assets"
    / "images"
)

# Cadenas que la app pone por defecto al crear algo y que el autor no llego a tocar.
MARCADORES = ("Nueva hoja", "Nueva rama", "Nuevo hito", "Subhito", "Entidad editada")
# Palabras con las que la IA describio los huecos cuando se le pidio regar basura.
DELATORES = ("placeholder", "esqueleto", "contenedor vacío", "contenedor vacio")


@pytest.fixture(scope="module")
def datos() -> dict:
    assert EJEMPLO.exists(), f"falta el proyecto de ejemplo en {EJEMPLO}"
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))


def test_sin_cadenas_marcador(datos):
    crudo = json.dumps(datos, ensure_ascii=False)
    presentes = [m for m in MARCADORES if m in crudo]
    assert not presentes, (
        f"el ejemplo volvio a contener nombres marcador: {presentes}. "
        "Es lo primero que ve un usuario nuevo: dale nombre diegetico."
    )


def test_entidades_con_nombre_y_descripcion(datos):
    for ent in datos["entities"]:
        assert (ent.get("name") or "").strip(), "entidad sin nombre"
        assert (ent.get("brief_description") or "").strip(), (
            f"«{ent.get('name')}» no tiene descripcion breve; en el Mapa y en el Foco "
            "se veria como una ficha vacia"
        )


def test_world_layers_no_vacio_y_entidades_asignadas(datos):
    capas = datos.get("world_layers") or []
    assert capas, (
        "sin anillos, el Mapa concentrico —la vista insignia— no dibuja nada al abrir "
        "el ejemplo"
    )
    ids = {c["id"] for c in capas}
    for ent in datos["entities"]:
        asignadas = ent.get("layer_ids") or []
        assert asignadas, f"«{ent.get('name')}» no esta en ningun anillo"
        assert set(asignadas) <= ids, f"«{ent.get('name')}» apunta a un anillo inexistente"


def test_hitos_con_titulo_y_tipo_variado(datos):
    hitos = datos.get("causal_milestones") or []
    assert hitos, "el ejemplo deberia traer cronologia"
    for h in hitos:
        assert (h.get("title") or "").strip(), "hito sin titulo"
    tipos = {h.get("milestone_type") for h in hitos}
    assert len(tipos) > 1, (
        f"los {len(hitos)} hitos comparten un solo tipo ({tipos}); el enum tiene 15 y "
        "la demo deberia enseñar mas de uno"
    )


def test_paginas_wiki_regadas_y_sin_delatores(datos):
    for mem in datos.get("narrative_memories") or []:
        assert mem.get("freshness") == "regada", (
            "una pagina de wiki del ejemplo no esta regada: el usuario abriria la demo "
            "con la Memoria ya en rojo"
        )
        texto = " ".join(
            str(mem.get(c) or "")
            for c in ("resumen_editorial", "estado_actual", "cuerpo")
        ).lower()
        for delator in DELATORES:
            assert delator not in texto, (
                f"una pagina de wiki describe un hueco ({delator!r}) en vez de canon"
            )


def test_sin_diagnosticos_huerfanos(datos):
    vivos = {e["id"] for e in datos["entities"]}
    huerfanos = {
        d.get("entity_id")
        for d in datos.get("watering_diagnostics") or []
        if d.get("entity_id") not in vivos
    }
    assert not huerfanos, (
        f"{len(huerfanos)} diagnosticos de riego apuntan a entidades borradas; "
        "engordan el fichero y no los ve nadie"
    )


def test_assets_referenciados_en_ambos_sentidos(datos):
    referenciadas = set()
    for ent in datos["entities"]:
        ruta = (ent.get("custom_metadata") or {}).get("_image_path")
        if ruta:
            referenciadas.add(pathlib.PurePosixPath(ruta).name)
    en_disco = {p.name for p in IMAGENES.glob("*")} if IMAGENES.exists() else set()
    assert referenciadas <= en_disco, (
        f"retratos referenciados que no estan en el sidecar: {referenciadas - en_disco}"
    )
    assert en_disco <= referenciadas, (
        f"imagenes que ya no usa nadie y viajan igual en el zip: {en_disco - referenciadas}"
    )


def test_carga_con_project_store_sin_perdida(datos):
    resultado = ProjectStore().load(EJEMPLO)
    assert hasattr(resultado, "value"), f"el ejemplo no carga: {resultado}"
    proyecto = resultado.value
    assert datos["schema_version"] == 39
    ida_y_vuelta = proyecto.to_dict()
    for coleccion in ("entities", "relations", "causal_milestones", "world_layers"):
        assert len(ida_y_vuelta[coleccion]) == len(datos[coleccion]), (
            f"el round-trip pierde elementos en {coleccion}"
        )
