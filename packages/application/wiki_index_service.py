"""WikiIndexService — índice determinista de la wiki (BETA2-WIKI-03).

El **índice** es una **proyección del canon**: una entrada por cada elemento
canónico (entidad, anillo, hito, relación) con una línea de resumen y la frescura
de su página de wiki. Es la pieza clave del método Karpathy: la IA lo lee primero,
barato, para decidir qué canon/páginas traer (contrato ``wiki_memoria.md`` §3.1).

Propiedades:

- **Determinista, sin IA, sin persistencia propia.** Se recomputa al vuelo (O(n),
  barato) para estar **siempre sincronizado con el canon por construcción** — evita
  el riesgo de una caché desincronizada. La ``signature`` del índice sirve de
  detector de cambios ligero para quien quiera cachear en su capa.
- **Siempre completo:** cada elemento canónico aparece aunque no tenga página
  (``page_freshness='sin_memoria'``, ``has_page=False``). Un proyecto sin nada
  regado tiene, aun así, un mapa completo.
- La ``one_line`` es el lead de la página (``resumen_editorial``) si existe; si no,
  una derivación determinista de la ficha canónica.

Este servicio es de aplicación: no muta el ``Project`` ni escribe persistencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.application.ai_privacy import (
    REDACTED_LINE,
    REDACTED_NAME,
    is_withheld_from_ai,
    relation_withheld,
)
from packages.application.world_layer_causal import get_causal_rank
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.result import Ok, Result

# Cotas para que el índice sea compacto en el prompt (no un dump técnico).
_ONE_LINE_MAX = 140
_COMPACT_ONE_LINE_MAX = 120


def _truncate(text: Any, limit: int) -> str:
    text = str(text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


@dataclass(frozen=True)
class WikiIndexEntry:
    """Una entrada del índice: un elemento canónico proyectado."""

    kind: str  # MemoryTargetKind.value: entity | ring | milestone | relation
    id: str
    name: str
    ring: str = ""  # nombre del anillo primario, si aplica
    rank: int | None = None  # rank causal del anillo (menor = más aguas-arriba)
    one_line: str = ""
    page_freshness: str = MemoryFreshness.SIN_MEMORIA.value
    has_page: bool = False
    # WS-B: elemento reservado — su nombre/contenido no viaja a la IA (índice compacto
    # y navegación lo redactan). La UI usa el índice completo, así que este flag no la
    # afecta: solo marca el borde de egreso hacia el proveedor.
    secret: bool = False


@dataclass(frozen=True)
class WikiIndex:
    """El índice completo: entradas + conteos + firma de cambio."""

    entries: tuple[WikiIndexEntry, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    signature: str = ""

    def entry_for(self, kind: str, target_id: str) -> WikiIndexEntry | None:
        for e in self.entries:
            if e.kind == kind and e.id == target_id:
                return e
        return None


class WikiIndexService:
    """Proyecta el canon a un índice de wiki, determinista y siempre completo."""

    def build_index(self, project: Any) -> Result[WikiIndex, str]:
        if project is None:
            return Ok(WikiIndex())

        pages = self._general_pages_by_key(project)
        entries: list[WikiIndexEntry] = []

        layers = {lay.id: lay for lay in getattr(project, "world_layers", []) or []}

        # Anillos (world_layers)
        for layer in layers.values():
            rank = get_causal_rank(layer)
            entries.append(
                self._entry(
                    MemoryTargetKind.RING,
                    layer.id,
                    getattr(layer, "name", "") or layer.id,
                    pages,
                    ring=getattr(layer, "name", ""),
                    rank=rank,
                    fallback=f"{getattr(layer, 'name', '')}: {getattr(layer, 'description', '')}",
                    secret=is_withheld_from_ai(layer),
                )
            )

        # Entidades
        for ent in getattr(project, "entities", []) or []:
            ring_name, rank = self._primary_ring(ent, layers)
            fallback = f"{getattr(ent, 'name', '')} — {getattr(ent, 'brief_description', '')}"
            entries.append(
                self._entry(
                    MemoryTargetKind.ENTITY,
                    ent.id,
                    getattr(ent, "name", "") or ent.id,
                    pages,
                    ring=ring_name,
                    rank=rank,
                    fallback=fallback,
                    secret=is_withheld_from_ai(ent),
                )
            )

        # Hitos causales
        for hito in getattr(project, "causal_milestones", []) or []:
            ring_name, rank = self._primary_ring(hito, layers)
            fallback = f"{getattr(hito, 'title', '')} — {getattr(hito, 'description', '')}"
            entries.append(
                self._entry(
                    MemoryTargetKind.MILESTONE,
                    hito.id,
                    getattr(hito, "title", "") or hito.id,
                    pages,
                    ring=ring_name,
                    rank=rank,
                    fallback=fallback,
                    secret=is_withheld_from_ai(hito),
                )
            )

        # Relaciones
        for rel in getattr(project, "relations", []) or []:
            entries.append(
                self._entry(
                    MemoryTargetKind.RELATION,
                    rel.id,
                    self._relation_name(project, rel),
                    pages,
                    fallback=self._relation_fallback(project, rel),
                    secret=relation_withheld(project, rel),
                )
            )

        counts = {
            "ring": len(layers),
            "entity": len(getattr(project, "entities", []) or []),
            "milestone": len(getattr(project, "causal_milestones", []) or []),
            "relation": len(getattr(project, "relations", []) or []),
            "con_pagina": sum(1 for e in entries if e.has_page),
        }
        signature = self._signature(project, counts)
        return Ok(WikiIndex(entries=tuple(entries), counts=counts, signature=signature))

    def compact_for_prompt(
        self,
        index: WikiIndex,
        *,
        max_entries: int | None = None,
        priority_ids: Any = None,
    ) -> dict[str, Any]:
        """Vista compacta y podada del índice para viajar en el prompt de navegación.

        ``max_entries`` acota el tamaño (BETA-CIERRE WS-L / B4): sin tope, el índice
        completo viajaba en CADA ronda de navegación — un coste de entrada ilimitado que
        crece con el proyecto y puede desbordar la ventana de contexto del modelo. Lo
        omitido NO se pierde: la IA puede ``search`` sobre el índice completo. Los
        ``priority_ids`` (p. ej. el foco) se colocan primero para que el recorte nunca los
        deje fuera.
        """
        entries = list(index.entries)
        if priority_ids:
            prioritized = {str(pid) for pid in priority_ids}
            # sort estable: los prioritarios primero, el resto en su orden original.
            entries.sort(key=lambda e: 0 if e.id in prioritized else 1)
        omitidas = 0
        if max_entries is not None and len(entries) > max_entries:
            omitidas = len(entries) - max_entries
            entries = entries[:max_entries]

        lineas = [self._compact_line(e) for e in entries]
        nota = (
            "Índice de la wiki (mapa del proyecto). Abre solo las páginas o el canon de "
            "los elementos relevantes para la petición; no lo traigas todo."
        )
        if omitidas:
            nota += (
                f" Se muestran {len(entries)} de {len(index.entries)} elementos; usa "
                "search para encontrar cualquiera que no aparezca aquí."
            )
        section: dict[str, Any] = {
            "nota": nota,
            "conteos": dict(index.counts),
            "entradas": lineas,
        }
        if omitidas:
            # No truncar en silencio (contrato §9): avisar de lo omitido.
            section["omitidas"] = omitidas
        return section

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _general_pages_by_key(project: Any) -> dict[tuple[str, str], Any]:
        """Mapa (target_kind, target_id) -> página general (context vacío)."""
        result: dict[tuple[str, str], Any] = {}
        for block in getattr(project, "narrative_memories", []) or []:
            if getattr(block, "context", ""):
                continue  # las páginas contextuales no representan al elemento en el índice
            result[(block.target_kind.value, block.target_id)] = block
        return result

    def _entry(
        self,
        kind: MemoryTargetKind,
        target_id: str,
        name: str,
        pages: dict[tuple[str, str], Any],
        *,
        ring: str = "",
        rank: int | None = None,
        fallback: str = "",
        secret: bool = False,
    ) -> WikiIndexEntry:
        page = pages.get((kind.value, target_id))
        has_page = bool(page and (page.resumen_editorial.strip() or page.cuerpo.strip()))
        if page is not None and page.resumen_editorial.strip():
            one_line = _truncate(page.resumen_editorial, _ONE_LINE_MAX)
        else:
            one_line = _truncate(fallback, _ONE_LINE_MAX)
        freshness = page.freshness.value if page is not None else MemoryFreshness.SIN_MEMORIA.value
        return WikiIndexEntry(
            kind=kind.value,
            id=target_id,
            name=name,
            ring=ring or "",
            rank=rank,
            one_line=one_line,
            page_freshness=freshness,
            has_page=has_page,
            secret=secret,
        )

    @staticmethod
    def _primary_ring(obj: Any, layers: dict[str, Any]) -> tuple[str, int | None]:
        """Anillo primario de un elemento = el de menor rank causal (más aguas-arriba)."""
        best_name, best_rank = "", None
        for lid in getattr(obj, "layer_ids", []) or []:
            layer = layers.get(lid)
            if layer is None:
                continue
            rank = get_causal_rank(layer)
            if rank is None:
                if best_name == "":
                    best_name = getattr(layer, "name", "")
                continue
            if best_rank is None or rank < best_rank:
                best_rank, best_name = rank, getattr(layer, "name", "")
        return best_name, best_rank

    @staticmethod
    def _relation_name(project: Any, rel: Any) -> str:
        src = project.entity_by_id(rel.source_id) if hasattr(project, "entity_by_id") else None
        dst = project.entity_by_id(rel.target_id) if hasattr(project, "entity_by_id") else None
        src_name = getattr(src, "name", rel.source_id) if src else rel.source_id
        dst_name = getattr(dst, "name", rel.target_id) if dst else rel.target_id
        rel_type = getattr(rel.relation_type, "value", rel.relation_type)
        return f"{src_name} —{rel_type}→ {dst_name}"

    def _relation_fallback(self, project: Any, rel: Any) -> str:
        desc = getattr(rel, "description", "")
        base = self._relation_name(project, rel)
        return f"{base}: {desc}" if desc else base

    @staticmethod
    def _signature(project: Any, counts: dict[str, int]) -> str:
        """Firma barata de cambio: conteos + estado de las páginas (frescura/updated_at).

        Cambia cuando se toca una página; no pretende capturar toda edición de canon
        (el índice se recomputa siempre, así que no depende de esta firma para estar
        actualizado). Sirve a quien quiera cachear en su propia capa.
        """
        pid = getattr(project, "id", "")
        page_state = sorted(
            f"{b.target_kind.value}:{b.target_id}:{b.context}:{b.freshness.value}:{b.updated_at}"
            for b in getattr(project, "narrative_memories", []) or []
        )
        count_state = ";".join(f"{k}={counts[k]}" for k in sorted(counts))
        return f"{pid}|{count_state}|{'|'.join(page_state)}"

    @staticmethod
    def _compact_line(e: WikiIndexEntry) -> str:
        ring = f" ·{e.ring}" if e.ring else ""
        if e.secret:
            # WS-B: sin nombre ni contenido. Solo kind+id+anillo (estructura), para que
            # la IA sepa que el elemento existe pero no pueda leer nada reservado.
            return f"{e.kind} {e.id}{ring} · {REDACTED_NAME} — {REDACTED_LINE}"
        rank = f"#{e.rank}" if e.rank is not None else ""
        return (
            f"{e.kind} {e.id} · {e.name}{ring}{(' ' + rank) if rank else ''} "
            f"[{e.page_freshness}] — {_truncate(e.one_line, _COMPACT_ONE_LINE_MAX)}"
        )


__all__ = ["WikiIndex", "WikiIndexEntry", "WikiIndexService"]
