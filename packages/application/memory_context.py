"""LEGACY (BETA2-WIKI-11): volcado fijo de Memoria retirado del ensamblado.

En WIKI-05 el prompt dejó de llevar esta sección `memoria_derivada` fija; el contexto
de Memoria viaja ahora como `contexto_wiki` (bundle seleccionado por navegación). Se
conserva importable (tests) hasta su borrado posterior.

Ensamblado de la Memoria para el contexto IA (BETA2-MEM-06).

Construye la sección **determinista** ``memoria_derivada`` que viaja en el prompt de
toda tarea IA (hueco reservado PA04 ``resumen_proyecto``). La Memoria entra marcada
como derivada/no canónica, con prioridad canon > Memoria > candidatos, y con AVISO si
alguna Memoria incluida está obsoleta (Falta regar / Secada) — el usuario puede
continuar igualmente (contrato §9). No usa RAG/embeddings: es determinista y acotada.
"""

from __future__ import annotations

from typing import Any

from packages.domain.narrative_memory import MemoryFreshness, MemoryIssueKind, MemoryTargetKind

# Cotas para que la Memoria no ahogue al canon en el presupuesto (sección fija).
_MAX_BLOQUES = 12
_MAX_RESUMEN = 600
_MAX_ISSUES = 5

_MARCADOR = (
    "La Memoria es una lectura DERIVADA del proyecto (resúmenes, tensiones, huecos). NO es canon."
)


def _truncate(text: str, limit: int) -> str:
    text = str(text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _issue_texts(block, kind: MemoryIssueKind) -> list[str]:
    return [i.texto for i in block.issues if i.kind == kind and i.texto][:_MAX_ISSUES]


def build_memory_prompt_section(
    project: Any, selected_ids: set[str] | None = None
) -> dict[str, Any] | None:
    """Sección de Memoria vigente/relevante para el prompt, o None si no hay Memoria.

    Incluye la Memoria global de proyecto + la de los elementos seleccionados. Marca
    los bloques y avisa si alguno está obsoleto. Salida acotada (no dump técnico).
    """
    memories = getattr(project, "narrative_memories", None)
    if not memories:
        return None
    selected = {str(x) for x in (selected_ids or set())}

    bloques: list[dict[str, Any]] = []
    hay_obsoleta = False
    for block in memories:
        is_project = block.target_kind == MemoryTargetKind.PROJECT
        is_selected = bool(block.target_id) and block.target_id in selected
        if not (is_project or is_selected):
            continue
        if not block.resumen_editorial.strip():
            continue  # bloque vacío (p. ej. marcado Falta regar sin Memoria aún)
        obsoleta = block.freshness in (MemoryFreshness.FALTA_REGAR, MemoryFreshness.SECADA)
        hay_obsoleta = hay_obsoleta or obsoleta
        entry: dict[str, Any] = {
            "elemento": f"{block.target_kind.value}:{block.target_id}"
            if block.target_id
            else "proyecto",
            "frescura": block.freshness.value,
            "resumen": _truncate(block.resumen_editorial, _MAX_RESUMEN),
        }
        if block.estado_actual.strip():
            entry["estado_actual"] = _truncate(block.estado_actual, _MAX_RESUMEN)
        contradicciones = _issue_texts(block, MemoryIssueKind.CONTRADICCION)
        if contradicciones:
            entry["contradicciones"] = contradicciones
        huecos = _issue_texts(block, MemoryIssueKind.HUECO)
        if huecos:
            entry["huecos"] = huecos
        preguntas = _issue_texts(block, MemoryIssueKind.PREGUNTA_ABIERTA)
        if preguntas:
            entry["preguntas_abiertas"] = preguntas
        bloques.append(entry)
        if len(bloques) >= _MAX_BLOQUES:
            break

    if not bloques:
        return None

    section: dict[str, Any] = {"nota": _MARCADOR, "bloques": bloques}
    if hay_obsoleta:
        section["aviso"] = (
            "Parte de esta Memoria puede estar obsoleta (Falta regar/Secada); "
            "se recomienda Regar antes de darla por vigente."
        )
    return section


__all__ = ["build_memory_prompt_section"]
