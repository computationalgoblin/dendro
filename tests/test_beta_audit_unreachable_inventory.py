"""BETA-AUDIT-14: inventario vivo de los módulos de aplicación sin superficie.

La auditoría encontró que **28 de los 82 módulos de `packages/application` son
inalcanzables desde la interfaz** (imports directos desde `hosts/` más el cierre
transitivo dentro de la propia capa). No es deuda que se arregle cableándolos: la app
mejoró cuando la IA se recortó de 23 tipos de trabajo a 9, y enchufar lint, incidencias,
diagnósticos y análisis reconstruiría justo la confusión que se acababa de quitar.

Lo que sí es deuda es que ese conjunto viva sin decisión escrita y cambie sin que nadie
se entere. Esta guarda ata el cálculo por AST a la tabla de `product_debt_map.md`: si
alguien añade un módulo huérfano o cablea uno sin actualizar el documento, falla y dice
cuál.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "packages" / "application"
MAPA = RAIZ / "docs" / "product" / "product_debt_map.md"

VEREDICTOS = {"cablear", "cuarentena", "borrar"}
#: Decisión de producto: el rol quedó FUERA de la beta (BETA-CIERRE WS-A) y su código
#: se cuarentena, no se borra. El perfil de Game Master de la auditoría agradeció
#: explícitamente la retirada: prefiere que no se le prometa a que se le venda un modo
#: máster que se cae en mesa.
VERTICAL_DE_ROL = {
    "campaign_service",
    "faction_service",
    "secrets_service",
    "session_service",
    "live_mode_service",
    "post_session_service",
}


def _imports_de_application(fichero: Path) -> set[str]:
    """Módulos de `packages.application` que importa `fichero` (incluidos perezosos)."""
    try:
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    encontrados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            if nodo.module.startswith("packages.application."):
                encontrados.add(nodo.module.split(".")[2])
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name.startswith("packages.application."):
                    encontrados.add(alias.name.split(".")[2])
    return encontrados


def _modulos_inalcanzables() -> set[str]:
    todos = {p.stem for p in APP.glob("*.py") if p.stem != "__init__"}
    alcanzables: set[str] = set()
    for fichero in (RAIZ / "hosts").rglob("*.py"):
        alcanzables |= _imports_de_application(fichero)
    frontera = set(alcanzables)
    while frontera:
        siguiente: set[str] = set()
        for modulo in frontera:
            fichero = APP / f"{modulo}.py"
            if fichero.exists():
                siguiente |= _imports_de_application(fichero) - alcanzables
        alcanzables |= siguiente
        frontera = siguiente
    return todos - alcanzables


def _tabla_documentada() -> dict[str, str]:
    """Lee la tabla del mapa de deuda: {módulo: veredicto}."""
    texto = MAPA.read_text(encoding="utf-8")
    filas = re.findall(
        r"^\|\s*`([a-z_0-9]+)`\s*\|[^|]*\|[^|]*\|\s*([a-zá-ú]+)\s*\|", texto, re.M
    )
    return {modulo: veredicto for modulo, veredicto in filas}


def test_inventario_coincide_con_el_calculo():
    calculado = _modulos_inalcanzables()
    documentado = set(_tabla_documentada())
    sin_documentar = sorted(calculado - documentado)
    ya_no_huerfanos = sorted(documentado - calculado)
    assert not sin_documentar, (
        "módulos inalcanzables que no están en la tabla de product_debt_map.md: "
        f"{sin_documentar}. Añádelos con un veredicto, o cabléalos."
    )
    assert not ya_no_huerfanos, (
        "la tabla lista módulos que YA son alcanzables (¿los cableó alguien?): "
        f"{ya_no_huerfanos}. Retíralos de la tabla y anota en qué ticket se cablearon."
    )


def test_todo_modulo_tiene_veredicto():
    for modulo, veredicto in _tabla_documentada().items():
        assert veredicto in VEREDICTOS, (
            f"«{modulo}» tiene el veredicto {veredicto!r}, que no es uno de {VEREDICTOS}"
        )


def test_cablear_exige_ticket():
    """Un módulo no puede quedar marcado para cablear sin quién lo ejecute."""
    texto = MAPA.read_text(encoding="utf-8")
    for linea in texto.splitlines():
        if not re.match(r"^\|\s*`[a-z_0-9]+`", linea):
            continue
        if "| cablear |" in linea:
            assert re.search(r"BETA-AUDIT-\d\d", linea), (
                f"fila marcada «cablear» sin ticket que lo ejecute: {linea.strip()}"
            )


def test_la_vertical_de_rol_esta_en_cuarentena():
    documentado = _tabla_documentada()
    for modulo in VERTICAL_DE_ROL:
        assert documentado.get(modulo) == "cuarentena", (
            f"«{modulo}» es de la vertical de rol: se cuarentena, no se borra ni se "
            "cablea (decisión de producto de BETA-CIERRE WS-A)"
        )
