"""Validacion autoritativa del payload JSON de actualizacion de Memoria (BETA2-MEM-05).

Como el riego, el job de Memoria valida su propia salida aqui (``stage_results`` la
importa de forma perezosa) porque la ruta de jobs llama al gateway con
``validate=False``. Un payload invalido produce un error claro — nunca una Memoria
basura ni contenido inventado como canon.

La Memoria es derivada, no canon: este normalizador NO acepta que el modelo declare
entidades/relaciones/hitos nuevos; solo secciones editoriales ancladas por id.
"""

from __future__ import annotations

import re
from typing import Any

from packages.domain.narrative_memory import MemoryIssueKind, MemoryTargetKind
from packages.domain.result import Error, Ok, Result

_ISSUE_KINDS = frozenset(k.value for k in MemoryIssueKind)
_REF_KINDS = frozenset(k.value for k in MemoryTargetKind)

# BETA2-FIX-07: el prompt NUNCA ha pedido enlaces dentro de la prosa
# (solo el array `wikilinks`), pero el modelo se los inventa igual: 13
# `[Nombre](ref_id: Nombre)` en una página del beta y 8 `[[Nombre]]` en otra. El
# visor pinta el cuerpo con `setPlainText`, así que esa sintaxis llegaba cruda a
# la cara del usuario. Se limpia al normalizar: queda el TEXTO, se va el andamio.
_WIKILINK_DOBLE = re.compile(r"\[\[([^\[\]]+)\]\]")
_ENLACE_MD = re.compile(r"\[([^\[\]]+)\]\([^()]*\)")


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _sin_enlaces_inventados(value: Any) -> str:
    """Quita del texto los enlaces markdown/wiki que el modelo se inventa.

    ``[[Ana]]`` → ``Ana``; ``[[Ana|la reina]]`` → ``la reina`` (el texto visible);
    ``[Ana](ref_id: Ana)`` → ``Ana``. No toca los corchetes sueltos ni el resto
    de la prosa: solo esas dos formas.
    """
    text = _clean_str(value)
    if not text:
        return text
    text = _WIKILINK_DOBLE.sub(lambda m: m.group(1).split("|")[-1].strip(), text)
    for _ in range(3):  # enlaces anidados o pegados: converge rápido
        limpio = _ENLACE_MD.sub(r"\1", text)
        if limpio == text:
            break
        text = limpio
    return text.strip()


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_str(v) for v in value if _clean_str(v)]
    return []


def _citation_list(value: Any) -> list[dict[str, Any]]:
    """Normaliza citas a {ref_kind, ref_id, nota}; descarta las mal formadas."""
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        ref_id = _clean_str(item.get("ref_id"))
        if not ref_id:
            continue  # una cita sin id estable no sirve (contrato: id, no texto)
        ref_kind = _clean_str(item.get("ref_kind")) or MemoryTargetKind.ENTITY.value
        if ref_kind not in _REF_KINDS:
            ref_kind = MemoryTargetKind.ENTITY.value
        out.append({"ref_kind": ref_kind, "ref_id": ref_id, "nota": _clean_str(item.get("nota"))})
    return out


def _issue_list(value: Any) -> list[dict[str, Any]]:
    """Normaliza incidencias a {kind, texto, anclado_a}; descarta las vacias."""
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        texto = _clean_str(item.get("texto"))
        if not texto:
            continue
        kind = _clean_str(item.get("kind"))
        if kind not in _ISSUE_KINDS:
            kind = MemoryIssueKind.CONTRADICCION.value
        out.append(
            {"kind": kind, "texto": texto, "anclado_a": _citation_list(item.get("anclado_a"))}
        )
    return out


def normalize_memory_payload(payload: Any) -> Result[dict[str, Any], str]:
    """Valida y normaliza el JSON del modelo para una actualizacion de Memoria.

    Exige un ``resumen_editorial`` no vacio. El resto de secciones son opcionales
    pero se saneen. Devuelve un dict con las claves editoriales; NUNCA declara canon.
    """
    if not isinstance(payload, dict):
        return Error("La actualizacion de Memoria debe ser un objeto JSON")

    resumen = _sin_enlaces_inventados(payload.get("resumen_editorial") or payload.get("summary"))
    if not resumen:
        return Error("Actualizacion de Memoria sin 'resumen_editorial'")

    return Ok(
        {
            "resumen_editorial": resumen,
            "estado_actual": _sin_enlaces_inventados(payload.get("estado_actual")),
            # BETA2-WIKI-06: cuerpo editorial largo (la "página") + enlaces/etiquetas.
            "cuerpo": _sin_enlaces_inventados(payload.get("cuerpo")),
            "notas_causales": _str_list(payload.get("notas_causales")),
            "issues": _issue_list(payload.get("issues")),
            "citations": _citation_list(payload.get("citations")),
            "wikilinks": _citation_list(payload.get("wikilinks")),
            "tags": _str_list(payload.get("tags")),
        }
    )
