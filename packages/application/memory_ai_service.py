"""MemoryAIService — actualizacion IA de la Memoria editorial (BETA2-MEM-05).

Orquesta el job ``update_memory`` (patron ``WateringService.water_entity``): arma un
contexto COMPACTO del elemento, ejecuta el job por el pipeline troncal
(``AIJobService.run_focused_job``), valida la salida (``memory_payload``) y la
aplica o la propone segun el modo:

- **mode="regar"** (Regar ordinario): AUTO-APLICA — ``upsert_memory`` directo,
  frescura REGADA, limpia el Falta regar. Decision de entrevista MEM-05.
- **mode="regen"** (regeneracion desde Configuracion): si ya hay Memoria, PROPONE un
  diff revisable (``MemoryRevisionProposal``); si no hay, la genera directa.

La Memoria es DERIVADA, no canon. Sin proveedor IA configurado, falla claro y la app
sigue usable. La UI nunca escribe persistencia: llama a este servicio de aplicacion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.application.structured_reference_service import backlinks_for
from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryFreshness,
    MemoryIssue,
    MemoryOrigin,
    MemoryTargetKind,
)
from packages.domain.result import Error, Ok, Result

_UNCONFIGURED = (
    "No hay proveedor de IA configurado. Configura NARRATIVE_AI_PROVIDER, "
    "NARRATIVE_AI_BASE_URL, NARRATIVE_AI_API_KEY y NARRATIVE_AI_MODEL para actualizar Memoria."
)


def _as_kind(value: MemoryTargetKind | str) -> MemoryTargetKind:
    if isinstance(value, MemoryTargetKind):
        return value
    return MemoryTargetKind(str(value))


@dataclass
class MemoryAIService:
    project_service: Any
    ai_job_service: Any
    memory_service: Any = None
    history_service: Any = None

    def __post_init__(self) -> None:
        if self.memory_service is None:
            from packages.application.narrative_memory_service import NarrativeMemoryService

            self.memory_service = NarrativeMemoryService(self.project_service, self.history_service)

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    # ── API principal ───────────────────────────────────────────────────

    def update_memory(
        self,
        target_kind: MemoryTargetKind | str,
        target_id: str = "",
        context: str = "",
        *,
        mode: str = "regar",
        progress_callback=None,
    ) -> Result[dict, str]:
        """Genera/actualiza la Memoria de un elemento con IA (regar | regen)."""
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            return Error(_UNCONFIGURED)
        kind = _as_kind(target_kind)

        prompt = self._build_context(proj, kind, target_id, context)
        job = self.ai_job_service.run_focused_job(
            "update_memory",
            prompt,
            context_scope={
                "target_kind": kind.value,
                "target_id": target_id,
                "memory": True,
            },
            progress_callback=progress_callback,
        )
        if isinstance(job, Error):
            return Error(job.error)
        staged = getattr(job.value, "result", None) or {}
        mem_data = staged.get("memory")
        if not mem_data:
            return Error(staged.get("memory_error") or "La IA no devolvio Memoria valida")

        issues = [MemoryIssue.from_dict(i) for i in mem_data.get("issues", [])]
        citations = [MemoryCitation.from_dict(c) for c in mem_data.get("citations", [])]
        wikilinks = [MemoryCitation.from_dict(w) for w in mem_data.get("wikilinks", [])]
        sections = dict(
            resumen_editorial=mem_data.get("resumen_editorial", ""),
            estado_actual=mem_data.get("estado_actual", ""),
            cuerpo=mem_data.get("cuerpo", ""),  # BETA2-WIKI-06: cuerpo de la página
            issues=issues,
            notas_causales=list(mem_data.get("notas_causales", [])),
            citations=citations,
            wikilinks=wikilinks,
            tags=list(mem_data.get("tags", [])),
        )

        if mode == "regen":
            return self._apply_regen(kind, target_id, context, sections)
        return self._apply_regar(kind, target_id, context, sections)

    # ── reconstruccion en lote de la wiki (BETA2-WIKI-06) ───────────────

    def rebuild_wiki(
        self,
        *,
        kinds: set | None = None,
        progress_callback=None,
        should_cancel=None,
    ) -> Result[dict, str]:
        """Reconstruye la wiki en lote: (re)escribe la pagina de cada elemento del canon.

        Recorre el proyecto y regenera paginas por IA elemento a elemento (mode="regar",
        auto-aplica). Cancelable entre elementos via ``should_cancel``. El host debe
        autorizar el coste antes (son muchas llamadas IA). Nunca toca canon.
        """
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        if self.ai_job_service is None or self.ai_job_service.provider_unconfigured():
            return Error(_UNCONFIGURED)

        wanted = set(kinds or {MemoryTargetKind.ENTITY})
        targets: list[tuple[MemoryTargetKind, str]] = []
        if MemoryTargetKind.ENTITY in wanted:
            targets += [
                (MemoryTargetKind.ENTITY, e.id) for e in getattr(proj, "entities", []) or []
            ]
        if MemoryTargetKind.MILESTONE in wanted:
            targets += [
                (MemoryTargetKind.MILESTONE, h.id)
                for h in getattr(proj, "causal_milestones", []) or []
            ]
        if MemoryTargetKind.RELATION in wanted:
            targets += [
                (MemoryTargetKind.RELATION, r.id) for r in getattr(proj, "relations", []) or []
            ]

        done = failed = 0
        cancelled = False
        for i, (kind, tid) in enumerate(targets):
            if should_cancel is not None and should_cancel():
                cancelled = True
                break
            if progress_callback is not None:
                try:
                    progress_callback(i, len(targets), kind.value, tid)
                except Exception:  # noqa: BLE001 — el progreso nunca rompe el lote
                    pass
            res = self.update_memory(kind, tid, mode="regar")
            if isinstance(res, Ok):
                done += 1
            else:
                failed += 1
        return Ok({"total": len(targets), "done": done, "failed": failed, "cancelled": cancelled})

    # ── aplicacion segun modo ───────────────────────────────────────────

    def _apply_regar(self, kind, target_id, context, sections) -> Result[dict, str]:
        res = self.memory_service.upsert_memory(
            kind,
            target_id,
            context,
            freshness=MemoryFreshness.REGADA,
            origin=MemoryOrigin.RIEGO,
            causa="actualizacion de Memoria por Regar",
            **sections,
        )
        if isinstance(res, Error):
            return Error(res.error)
        return Ok({"applied": True, "block": res.value})

    def _apply_regen(self, kind, target_id, context, sections) -> Result[dict, str]:
        existing = self.memory_service.get_memory(kind, target_id, context)
        block = existing.value if isinstance(existing, Ok) else None
        if block is None:
            res = self.memory_service.upsert_memory(
                kind,
                target_id,
                context,
                freshness=MemoryFreshness.REGADA,
                origin=MemoryOrigin.REGENERACION_MANUAL,
                causa="regeneracion inicial de Memoria",
                **sections,
            )
            if isinstance(res, Error):
                return Error(res.error)
            return Ok({"applied": True, "block": res.value})
        after = {
            "resumen_editorial": sections["resumen_editorial"],
            "estado_actual": sections["estado_actual"],
            "cuerpo": sections["cuerpo"],
            "issues": [i.to_dict() for i in sections["issues"]],
            "notas_causales": sections["notas_causales"],
            "citations": [c.to_dict() for c in sections["citations"]],
            "wikilinks": [c.to_dict() for c in sections["wikilinks"]],
            "tags": sections["tags"],
        }
        res = self.memory_service.stage_revision_proposal(
            kind,
            target_id,
            context,
            after=after,
            motivo="regeneracion de Memoria con IA",
            origin=MemoryOrigin.REGENERACION_MANUAL,
        )
        if isinstance(res, Error):
            return Error(res.error)
        return Ok({"applied": False, "proposal": res.value})

    # ── contexto compacto del elemento ──────────────────────────────────

    def _build_context(self, proj, kind: MemoryTargetKind, target_id: str, context: str) -> str:
        lines: list[str] = []
        lines.append(
            f"ELEMENTO: tipo={kind.value} id={target_id} contexto={context or '(general)'}"
        )
        lines.append(self._element_canon(proj, kind, target_id))
        prior = self.memory_service.get_memory(kind, target_id, context)
        block = prior.value if isinstance(prior, Ok) else None
        if block is not None and block.resumen_editorial:
            lines.append(f"MEMORIA PREVIA: {block.resumen_editorial}")
            if block.estado_actual:
                lines.append(f"ESTADO PREVIO: {block.estado_actual}")
        if kind == MemoryTargetKind.ENTITY and hasattr(proj, "relations_for"):
            rels = proj.relations_for(target_id)
            if rels:
                names = []
                for rel in rels[:12]:
                    other = rel.target_id if rel.source_id == target_id else rel.source_id
                    ent = proj.entity_by_id(other) if hasattr(proj, "entity_by_id") else None
                    label = getattr(ent, "name", other) if ent else other
                    names.append(
                        f"{getattr(rel.relation_type, 'value', rel.relation_type)}→{label}"
                    )
                lines.append("RELACIONES: " + "; ".join(names))
        # BETA2-WIKI-13b: identidad TEMPORAL de la entidad (lapso + hitos en los que
        # participa). Antes la Memoria era temporalmente ciega y no podía registrar
        # "en qué hitos intervino", parte de quién es. Riego ya lo tenía; aquí se iguala.
        if kind == MemoryTargetKind.ENTITY:
            lines.extend(self._entity_temporal_lines(proj, target_id))
        backs = backlinks_for(proj, kind, target_id)
        if backs:
            lines.append(f"MENCIONADO POR: {len(backs)} elemento(s) del proyecto")
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _entity_temporal_lines(proj, entity_id: str) -> list[str]:
        """LAPSO + HITOS en los que participa la entidad (identidad temporal, BETA2-WIKI-13b).

        Reutiliza ``classify_milestones`` (filtra por ``entity_id in affected_entity_ids``,
        zona por año). Best-effort: nunca rompe el contexto si faltan datos o ``proj`` es
        duck-typed en tests."""
        lines: list[str] = []
        e = proj.entity_by_id(entity_id) if hasattr(proj, "entity_by_id") else None
        if e is not None:
            birth = getattr(e, "birth_year", None)
            death = getattr(e, "death_year", None)
            if birth is not None or death is not None:
                lines.append(f"LAPSO: {birth} → {death}")
        if not hasattr(proj, "causal_milestones"):
            return lines
        try:
            from packages.application.foco_zones import classify_milestones

            by_id = {m.id: m for m in getattr(proj, "causal_milestones", []) or []}
            zones = classify_milestones(proj, entity_id)
            hito_lines: list[str] = []
            for zone_key, rol in (("raices", "raíz"), ("entorno", "entorno"), ("brotes", "brote")):
                for mid in zones.get(zone_key, []):
                    m = by_id.get(mid)
                    if m is None:
                        continue
                    year = f"año {m.year}" if getattr(m, "year", None) is not None else "sin fecha"
                    hito_lines.append(f"[{rol}] {getattr(m, 'title', '')} ({year})")
            if hito_lines:
                lines.append("HITOS: " + "; ".join(hito_lines))
        except Exception:  # noqa: BLE001 — la Memoria nunca rompe por el contexto temporal
            pass
        return lines

    @staticmethod
    def _element_canon(proj, kind: MemoryTargetKind, target_id: str) -> str:
        if kind == MemoryTargetKind.ENTITY and hasattr(proj, "entity_by_id"):
            e = proj.entity_by_id(target_id)
            if e is not None:
                return (
                    f"CANON: nombre={getattr(e, 'name', '')}; "
                    f"breve={getattr(e, 'brief_description', '')}; "
                    f"desarrollo={getattr(e, 'extended_description', '')}"
                )
        if kind == MemoryTargetKind.RELATION and hasattr(proj, "relation_by_id"):
            r = proj.relation_by_id(target_id)
            if r is not None:
                return (
                    f"CANON: relacion {r.source_id}→{r.target_id}; {getattr(r, 'description', '')}"
                )
        if kind == MemoryTargetKind.MILESTONE:
            for h in getattr(proj, "causal_milestones", []) or []:
                if h.id == target_id:
                    return (
                        f"CANON: hito={getattr(h, 'title', '')}; "
                        f"{getattr(h, 'description', '')}; {getattr(h, 'rationale', '')}"
                    )
        return "CANON: (elemento sin ficha localizable)"


__all__ = ["MemoryAIService"]
