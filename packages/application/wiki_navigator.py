"""WikiNavigator — navegación índice-first por bucle de lectura (BETA2-WIKI-04).

El proveedor de IA es de **un solo turno** (sin tool-calling). La navegación
agéntica se implementa aquí, en la capa de aplicación, como un **bucle de lectura
acotado**: la IA recibe el índice compacto + la petición y responde en JSON qué
quiere leer (``open_page`` / ``read_canon`` / ``search``) o que ya tiene bastante;
la app **cumple los reads de forma determinista** y repite, hasta un tope de rondas
o de presupuesto (contrato ``wiki_memoria.md`` §4).

Garantías (verificables): nunca supera ``max_rounds``; deduplica reads ya servidos;
para si una ronda no pide nada nuevo; ante JSON inválido o error del proveedor, para
con lo reunido (fallback). La IA nunca accede al store: solo pide, la app sirve.

Lo usan las mecánicas generativas (Sugerencias, Play/walk). Regar NO navega.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from packages.application.wiki_index_service import WikiIndex, WikiIndexService
from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.result import Error, Ok, Result

_UNCONFIGURED = (
    "No hay proveedor de IA configurado. Configura NARRATIVE_AI_PROVIDER, "
    "NARRATIVE_AI_BASE_URL, NARRATIVE_AI_API_KEY y NARRATIVE_AI_MODEL para navegar la wiki."
)

_CHARS_PER_TOKEN = 3.5
_VALID_OPS = frozenset({"open_page", "read_canon", "search"})
_VALID_KINDS = frozenset(k.value for k in MemoryTargetKind)
_SEARCH_HITS = 8
_STOPWORDS = frozenset(
    "de la el en y a los las un una que se su sus con por para del al lo es".split()
)

_SYSTEM_PROMPT = (
    "Eres el navegador de una wiki interna sobre un proyecto narrativo. Recibirás un "
    "ÍNDICE compacto (mapa del proyecto) y una PETICIÓN. Tu tarea es decidir qué mínimo "
    "de información hace falta traer del proyecto para atender la petición, consumiendo lo "
    "menos posible.\n"
    "Responde SIEMPRE y SOLO con un objeto JSON con esta forma exacta:\n"
    '{"reads": [{"op": "open_page|read_canon|search", "kind": "entity|ring|milestone|relation", '
    '"id": "<id>", "query": "<texto>"}], "enough": false}\n'
    "- open_page: abre la página de wiki (síntesis editorial) de un elemento (usa kind+id).\n"
    "- read_canon: trae la ficha canónica de un elemento (usa kind+id).\n"
    "- search: busca por palabras clave en el índice (usa query).\n"
    "Pide solo lo relevante. Cuando ya tengas bastante para atender la petición, responde "
    '{"reads": [], "enough": true}. No inventes ids: usa los del índice. No añadas texto '
    "fuera del JSON."
)


@dataclass
class NavigationRequest:
    """Una petición de contexto para navegar la wiki."""

    intent: str = ""
    user_text: str = ""
    focus_ids: list[str] = field(default_factory=list)
    focus_kind: str = MemoryTargetKind.ENTITY.value
    max_rounds: int = 3
    max_reads_per_round: int = 6
    token_budget: int = 4000
    # BETA-CIERRE WS-L / B4: tope de entradas del índice que viajan en el prompt CADA
    # ronda. Sin esto el índice completo (uno por entidad/relación/hito/anillo) se
    # re-enviaba entero por ronda, coste de entrada ilimitado en proyectos grandes. Lo
    # omitido sigue siendo alcanzable por ``search``.
    max_index_entries: int = 400


@dataclass
class NavigationBundle:
    """El contexto reunido por la navegación (no canónico)."""

    pages: list[dict] = field(default_factory=list)
    canon: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    rounds_used: int = 0
    truncated: bool = False
    index_signature: str = ""

    def is_empty(self) -> bool:
        return not (self.pages or self.canon)

    def as_context_dict(self) -> dict[str, Any]:
        """Vista para inyectar en el prompt (marcada no canónica)."""
        return {
            "nota": (
                "Contexto seleccionado de la wiki (páginas derivadas) y del canon, traído por "
                "navegación. Las páginas son DERIVADAS, no canon; el canon manda."
            ),
            "paginas": self.pages,
            "canon": self.canon,
            "notas": self.notes,
        }


@dataclass
class WikiNavigator:
    project_service: Any
    ai_job_service: Any = None
    memory_service: Any = None
    index_service: WikiIndexService = None

    def __post_init__(self) -> None:
        if self.index_service is None:
            self.index_service = WikiIndexService()
        if self.memory_service is None:
            from packages.application.narrative_memory_service import NarrativeMemoryService

            self.memory_service = NarrativeMemoryService(self.project_service)

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    # ── API principal ───────────────────────────────────────────────────

    def assemble_context(self, request: NavigationRequest) -> Result[NavigationBundle, str]:
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            return Error(_UNCONFIGURED)

        index_res = self.index_service.build_index(proj)
        if not isinstance(index_res, Ok):
            return Error("No se pudo construir el índice de la wiki")
        index = index_res.value
        compact = self.index_service.compact_for_prompt(
            index,
            max_entries=request.max_index_entries,
            priority_ids=request.focus_ids,
        )

        bundle = NavigationBundle(index_signature=index.signature)
        served: set[tuple] = set()
        # Presupuesto honrado tal cual: un presupuesto ínfimo trunca (es lo honesto);
        # los llamantes reales (Sugerencias/Play) pasan un presupuesto holgado.
        budget_chars = max(0, int(request.token_budget * _CHARS_PER_TOKEN))
        used_chars = 0

        for round_i in range(max(1, request.max_rounds)):
            bundle.rounds_used = round_i + 1
            user_message = self._round_message(request, compact, bundle)
            text, err = self._ask(user_message)
            if err or not text:
                bundle.notes.append(
                    f"navegación interrumpida: {err or 'sin respuesta del proveedor'}"
                )
                break
            parsed = self._parse(text)
            if parsed is None:
                bundle.notes.append(
                    "respuesta de navegación no interpretable; se sigue con lo reunido"
                )
                break

            enough = bool(parsed.get("enough"))
            new_reads = self._dedup_new_reads(
                parsed.get("reads"), served, request.max_reads_per_round
            )
            if not new_reads:
                break  # ronda vacía o solo repeticiones -> parar

            for read in new_reads:
                fetched = self._fulfill(proj, index, read)
                if fetched is None:
                    continue
                size = len(json.dumps(fetched, ensure_ascii=False))
                if used_chars + size > budget_chars:
                    bundle.truncated = True
                    break
                used_chars += size
                self._store(bundle, fetched)
            if bundle.truncated or enough:
                break

        return Ok(bundle)

    # ── llamada al proveedor (single-shot) ──────────────────────────────

    def _ask(self, user_message: str) -> tuple[str | None, str | None]:
        try:
            return self.ai_job_service.raw_json_completion(_SYSTEM_PROMPT, user_message)
        except Exception as exc:  # el bucle nunca debe romper el flujo del llamante
            return None, str(exc)

    def _round_message(
        self, request: NavigationRequest, compact: dict, bundle: NavigationBundle
    ) -> str:
        payload = {
            "peticion": {
                "intent": request.intent,
                "texto": request.user_text,
                "foco": [{"kind": request.focus_kind, "id": fid} for fid in request.focus_ids],
            },
            "indice": compact,
            "ya_leido": {
                "paginas": [
                    {"kind": p["kind"], "id": p["id"], "name": p.get("name", "")}
                    for p in bundle.pages
                ],
                "canon": [{"kind": c["kind"], "id": c["id"]} for c in bundle.canon],
                "notas": bundle.notes,
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    # ── parseo + dedup ──────────────────────────────────────────────────

    @staticmethod
    def _parse(text: str) -> dict | None:
        text = (text or "").strip()
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except (ValueError, TypeError):
            pass
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                return obj if isinstance(obj, dict) else None
            except (ValueError, TypeError):
                return None
        return None

    def _dedup_new_reads(self, reads: Any, served: set, cap: int) -> list[dict]:
        if not isinstance(reads, list):
            return []
        out: list[dict] = []
        for read in reads:
            if not isinstance(read, dict):
                continue
            key = self._read_key(read)
            if key is None or key in served:
                continue
            served.add(key)
            out.append(read)
            if len(out) >= max(1, cap):
                break
        return out

    @staticmethod
    def _read_key(read: dict) -> tuple | None:
        op = str(read.get("op", "")).strip()
        if op not in _VALID_OPS:
            return None
        if op == "search":
            query = str(read.get("query", "")).strip().lower()
            return ("search", query) if query else None
        kind = str(read.get("kind", "")).strip()
        target_id = str(read.get("id", "")).strip()
        if kind not in _VALID_KINDS or not target_id:
            return None
        return (op, kind, target_id)

    # ── fulfillment determinista ────────────────────────────────────────

    def _fulfill(self, proj: Any, index: WikiIndex, read: dict) -> dict | None:
        op = str(read.get("op", "")).strip()
        if op == "search":
            return self._do_search(index, str(read.get("query", "")))
        kind = str(read.get("kind", "")).strip()
        target_id = str(read.get("id", "")).strip()
        if kind not in _VALID_KINDS or not target_id:
            return None
        # WS-B: no servir página ni canon de un elemento reservado (el índice lo marca).
        entry = index.entry_for(kind, target_id)
        if entry is not None and entry.secret:
            return None
        if op == "open_page":
            return self._do_open_page(index, kind, target_id)
        if op == "read_canon":
            return self._do_read_canon(proj, index, kind, target_id)
        return None

    def _do_open_page(self, index: WikiIndex, kind: str, target_id: str) -> dict | None:
        res = self.memory_service.get_memory(MemoryTargetKind(kind), target_id)
        block = res.value if isinstance(res, Ok) else None
        if block is None or not (block.resumen_editorial.strip() or block.cuerpo.strip()):
            return None
        entry = index.entry_for(kind, target_id)
        return {
            "type": "page",
            "kind": kind,
            "id": target_id,
            "name": entry.name if entry else target_id,
            "resumen": block.resumen_editorial,
            "estado_actual": block.estado_actual,
            "cuerpo": block.cuerpo,
            "frescura": block.freshness.value,
            "issues": [{"kind": i.kind.value, "texto": i.texto} for i in block.issues if i.texto],
        }

    def _do_read_canon(self, proj: Any, index: WikiIndex, kind: str, target_id: str) -> dict | None:
        ficha = self._canon_ficha(proj, kind, target_id)
        if ficha is None:
            return None
        entry = index.entry_for(kind, target_id)
        return {
            "type": "canon",
            "kind": kind,
            "id": target_id,
            "name": entry.name if entry else target_id,
            "ficha": ficha,
        }

    def _do_search(self, index: WikiIndex, query: str) -> dict | None:
        tokens = self._tokenize(query)
        if not tokens:
            return None
        scored: list[tuple[int, Any]] = []
        for entry in index.entries:
            if entry.secret:
                continue  # WS-B: los elementos reservados no aparecen en la búsqueda de la IA
            hay = self._tokenize(f"{entry.name} {entry.one_line}")
            score = sum(1 for t in tokens if t in hay)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        hits = [
            {"kind": e.kind, "id": e.id, "name": e.name, "one_line": e.one_line}
            for _, e in scored[:_SEARCH_HITS]
        ]
        return {"type": "search", "query": query, "resultados": hits}

    @staticmethod
    def _canon_ficha(proj: Any, kind: str, target_id: str) -> dict | None:
        if kind == MemoryTargetKind.ENTITY.value and hasattr(proj, "entity_by_id"):
            e = proj.entity_by_id(target_id)
            if e is not None:
                return {
                    "nombre": getattr(e, "name", ""),
                    "breve": getattr(e, "brief_description", ""),
                    "desarrollo": getattr(e, "extended_description", ""),
                }
        if kind == MemoryTargetKind.RELATION.value and hasattr(proj, "relation_by_id"):
            r = proj.relation_by_id(target_id)
            if r is not None:
                return {
                    "origen": r.source_id,
                    "destino": r.target_id,
                    "tipo": getattr(r.relation_type, "value", r.relation_type),
                    "descripcion": getattr(r, "description", ""),
                }
        if kind == MemoryTargetKind.MILESTONE.value:
            for h in getattr(proj, "causal_milestones", []) or []:
                if h.id == target_id:
                    return {
                        "titulo": getattr(h, "title", ""),
                        "descripcion": getattr(h, "description", ""),
                    }
        if kind == MemoryTargetKind.RING.value:
            for lay in getattr(proj, "world_layers", []) or []:
                if lay.id == target_id:
                    return {
                        "nombre": getattr(lay, "name", ""),
                        "descripcion": getattr(lay, "description", ""),
                    }
        return None

    @staticmethod
    def _store(bundle: NavigationBundle, fetched: dict) -> None:
        kind = fetched.get("type")
        if kind == "page":
            bundle.pages.append(fetched)
        elif kind == "canon":
            bundle.canon.append(fetched)
        elif kind == "search":
            hits = ", ".join(f"{h['kind']}:{h['id']}" for h in fetched.get("resultados", []))
            query = fetched.get("query", "")
            bundle.notes.append(f"búsqueda «{query}» → {hits or 'sin resultados'}")

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        words = re.split(r"[^0-9a-záéíóúüñ]+", (text or "").lower())
        return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


__all__ = ["NavigationBundle", "NavigationRequest", "WikiNavigator"]
