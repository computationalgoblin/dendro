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

from packages.application.structured_reference_service import (
    backlinks_for,
    build_known_targets,
    canon_kind_by_id,
    resolve_page_refs,
)
from packages.domain.entity_taxonomy import is_branch
from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryFreshness,
    MemoryIssue,
    MemoryOrigin,
    MemoryTargetKind,
)
from packages.domain.project_chronology import format_year_with_era
from packages.domain.result import Error, Ok, Result

_UNCONFIGURED = (
    "No hay proveedor de IA configurado. Configura NARRATIVE_AI_PROVIDER, "
    "NARRATIVE_AI_BASE_URL, NARRATIVE_AI_API_KEY y NARRATIVE_AI_MODEL para actualizar Memoria."
)

# BETA2-FIX-07: tope de relaciones que viajan al contexto de Memoria.
# Antes era un `rels[:12]` mudo; ahora el recorte se DECLARA en el propio texto
# (contrato §9: no truncar callando).
_MAX_CONTEXT_RELATIONS = 12


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
        # BETA2-FIX-07: ningún enlace se persiste sin existir en el canon.
        citations, wikilinks, refs_counts = self._resolve_refs(
            proj, citations, wikilinks, issues
        )
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
            return self._apply_regen(kind, target_id, context, sections, refs_counts)
        return self._apply_regar(kind, target_id, context, sections, refs_counts)

    # ── resolución de enlaces contra el canon (BETA2-FIX-07) ──

    @staticmethod
    def _resolve_refs(
        proj,
        citations: list[MemoryCitation],
        wikilinks: list[MemoryCitation],
        issues: list[MemoryIssue],
    ) -> tuple[list[MemoryCitation], list[MemoryCitation], dict[str, int]]:
        """Resuelve wikilinks/citas/anclajes contra el canon ANTES de persistirlos.

        La IA escribe el NOMBRE dentro de ``ref_id`` (37 de 40 refs de los dos
        mundos del beta) porque el contexto solo le daba UN id: el suyo. Aquí se
        rescata lo rescatable, se corrige el ``ref_kind`` y se tira lo que no
        existe — contándolo, para que el descarte no sea silencioso.

        Una incidencia que pierde su anclaje SOBREVIVE: una contradicción sin
        ancla sigue valiendo (lo contrario perdería el diagnóstico entero).
        """
        known = build_known_targets(proj)
        kinds = canon_kind_by_id(proj)
        total = {"resueltos": 0, "ambiguos": 0, "descartados": 0}

        def _sumar(parcial: dict[str, int]) -> None:
            for clave, valor in parcial.items():
                total[clave] += valor

        res_cit = resolve_page_refs(proj, citations, known=known, kinds_by_id=kinds)
        _sumar(res_cit.counts())
        res_wiki = resolve_page_refs(proj, wikilinks, known=known, kinds_by_id=kinds)
        _sumar(res_wiki.counts())
        for issue in issues:
            res_anc = resolve_page_refs(proj, issue.anclado_a, known=known, kinds_by_id=kinds)
            _sumar(res_anc.counts())
            issue.anclado_a = res_anc.resueltas
        return res_cit.resueltas, res_wiki.resueltas, total

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

    def _apply_regar(self, kind, target_id, context, sections, refs=None) -> Result[dict, str]:
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
        return Ok({"applied": True, "block": res.value, "refs": dict(refs or {})})

    def _apply_regen(self, kind, target_id, context, sections, refs=None) -> Result[dict, str]:
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
            return Ok({"applied": True, "block": res.value, "refs": dict(refs or {})})
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
        return Ok({"applied": False, "proposal": res.value, "refs": dict(refs or {})})

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
            lines.extend(self._entity_relation_lines(proj, target_id))
        if kind == MemoryTargetKind.MILESTONE:
            lines.extend(self._milestone_participant_lines(proj, target_id))
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
    def _element_ref(proj, entity_id: str) -> str:
        """``Nombre (entity:<id>)`` — nombre humano + referencia enlazable de una entidad."""
        ent = proj.entity_by_id(entity_id) if hasattr(proj, "entity_by_id") else None
        nombre = str(getattr(ent, "name", "") or "") if ent is not None else ""
        kind = (
            MemoryTargetKind.BRANCH.value
            if (ent is not None and is_branch(ent))
            else MemoryTargetKind.ENTITY.value
        )
        return f"{nombre or '(sin nombre)'} ({kind}:{entity_id})"

    @staticmethod
    def _entity_relation_lines(proj, target_id: str) -> list[str]:
        """RELACIONES con DIRECCIÓN explícita e ids (BETA2-FIX-07, G2-10).

        Antes esto era ``sirve_a→Nadia Kerr`` viniera la relación de entrada o de
        salida: en español se lee «(yo) sirvo a Nadia», y la página de Otho —que
        es a quien Nadia sirve— escribió «Subordinado de Nadia Kerr». La IA no
        alucinó: transcribió lo que le dijimos. Ahora cada línea dice quién es el
        origen y quién el destino, y trae el id de la vecina y el de la relación
        para que los ``wikilinks`` puedan ser correctos.
        """
        rels = proj.relations_for(target_id) or []
        if not rels:
            return []
        lines = ["RELACIONES (la dirección es literal; usa estos id en 'wikilinks'):"]
        for rel in rels[:_MAX_CONTEXT_RELATIONS]:
            rtype = getattr(rel.relation_type, "value", rel.relation_type)
            rel_id = str(getattr(rel, "id", "") or "")
            sufijo = f" · vínculo relation:{rel_id}" if rel_id else ""
            if rel.source_id == rel.target_id:
                lines.append(f"- [refleja] ESTA ENTIDAD —{rtype}→ ESTA ENTIDAD{sufijo}")
                continue
            if rel.source_id == target_id:
                otro = MemoryAIService._element_ref(proj, rel.target_id)
                lines.append(f"- [sale] ESTA ENTIDAD —{rtype}→ {otro}{sufijo}")
            else:
                otro = MemoryAIService._element_ref(proj, rel.source_id)
                lines.append(f"- [entra] {otro} —{rtype}→ ESTA ENTIDAD{sufijo}")
        resto = len(rels) - _MAX_CONTEXT_RELATIONS
        if resto > 0:
            lines.append(
                f"- (RECORTE: hay {len(rels)} relaciones y solo se listan "
                f"{_MAX_CONTEXT_RELATIONS}; quedan {resto} sin mostrar)"
            )
        return lines

    @staticmethod
    def _milestone_participant_lines(proj, milestone_id: str) -> list[str]:
        """Entidades afectadas por un hito, con su id (para que sus enlaces resuelvan)."""
        hito = None
        for h in getattr(proj, "causal_milestones", []) or []:
            if getattr(h, "id", "") == milestone_id:
                hito = h
                break
        if hito is None:
            return []
        afectadas = [str(x) for x in (getattr(hito, "affected_entity_ids", []) or []) if x]
        if not afectadas:
            return []
        refs = [MemoryAIService._element_ref(proj, eid) for eid in afectadas]
        return ["PARTICIPANTES (usa estos id en 'wikilinks'): " + "; ".join(refs)]

    @staticmethod
    def _entity_temporal_lines(proj, entity_id: str) -> list[str]:
        """LAPSO + HITOS en los que participa la entidad (identidad temporal, BETA2-WIKI-13b).

        Reutiliza ``classify_milestones`` (filtra por ``entity_id in affected_entity_ids``,
        zona por año). Best-effort: nunca rompe el contexto si faltan datos o ``proj`` es
        duck-typed en tests."""
        lines: list[str] = []
        # BETA-FIX-03 (G-03): años con su traducción a era.
        chrono = getattr(proj, "project_chronology", None)
        e = proj.entity_by_id(entity_id) if hasattr(proj, "entity_by_id") else None
        if e is not None:
            birth = getattr(e, "birth_year", None)
            death = getattr(e, "death_year", None)
            if birth is not None or death is not None:
                birth_label = (
                    format_year_with_era(chrono, birth) if birth is not None else "abierto"
                )
                death_label = (
                    format_year_with_era(chrono, death) if death is not None else "abierto"
                )
                lines.append(f"LAPSO: {birth_label} → {death_label}")
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
                    year = format_year_with_era(chrono, getattr(m, "year", None))
                    # FIX-07: el hito viaja con su id, o su wikilink no puede ser correcto.
                    hito_lines.append(
                        f"[{rol}] {getattr(m, 'title', '')} ({year}) "
                        f"({MemoryTargetKind.MILESTONE.value}:{mid})"
                    )
            if hito_lines:
                lines.append("HITOS: " + "; ".join(hito_lines))
        except Exception:  # noqa: BLE001 — la Memoria nunca rompe por el contexto temporal
            pass
        return lines

    @staticmethod
    def _narrative_type_label(entity) -> str:
        """BETA2-FIX-08 (G2-13/A3): el TIPO NARRATIVO del elemento.

        Sin este dato la IA no podía saber que una rama es un CONTENEDOR de otros
        elementos y la describía como «el ente u objeto denominado …» (ESC-13). No
        es un fallo de criterio del modelo: era un campo que faltaba en el contexto.
        """
        raw = getattr(entity, "entity_type", None)
        tipo = str(getattr(raw, "value", raw) or "").strip()
        meta = getattr(entity, "custom_metadata", None) or {}
        semantic = str(meta.get("semantic_type") or "").strip() if isinstance(meta, dict) else ""
        if tipo == "contenedor":
            detalle = f"rama/contenedor de {semantic}" if semantic else "rama/contenedor"
            return f"{tipo} ({detalle}: AGRUPA otros elementos, no es una cosa del mundo)"
        if tipo:
            return f"{tipo} (hoja: elemento individual)"
        return "desconocido"

    @staticmethod
    def _element_canon(proj, kind: MemoryTargetKind, target_id: str) -> str:
        if kind == MemoryTargetKind.ENTITY and hasattr(proj, "entity_by_id"):
            e = proj.entity_by_id(target_id)
            if e is not None:
                return (
                    f"CANON: nombre={getattr(e, 'name', '')}; "
                    f"tipo_narrativo={MemoryAIService._narrative_type_label(e)}; "
                    f"breve={getattr(e, 'brief_description', '')}; "
                    f"desarrollo={getattr(e, 'extended_description', '')}"
                )
        if kind == MemoryTargetKind.RELATION and hasattr(proj, "relation_by_id"):
            r = proj.relation_by_id(target_id)
            if r is not None:
                rtype = str(getattr(getattr(r, "relation_type", None), "value", "") or "relacion")
                # FIX-07: extremos con NOMBRE e id (antes solo dos uuid crudos), y la
                # dirección escrita de forma que no se pueda leer al revés.
                origen = MemoryAIService._element_ref(proj, r.source_id)
                destino = MemoryAIService._element_ref(proj, r.target_id)
                return (
                    f"CANON: relacion {origen} —{rtype}→ {destino} "
                    f"(el ORIGEN es {origen}, el DESTINO es {destino}); "
                    f"tipo_narrativo={rtype} "
                    "(vínculo entre dos elementos); "
                    f"{getattr(r, 'description', '')}"
                )
        if kind == MemoryTargetKind.MILESTONE:
            for h in getattr(proj, "causal_milestones", []) or []:
                if h.id == target_id:
                    mtype = getattr(h, "milestone_type", None)
                    return (
                        f"CANON: hito={getattr(h, 'title', '')}; "
                        f"tipo_narrativo={str(getattr(mtype, 'value', mtype) or 'hito')} "
                        "(evento causal de la cronología); "
                        f"{getattr(h, 'description', '')}; {getattr(h, 'rationale', '')}"
                    )
        return "CANON: (elemento sin ficha localizable)"


__all__ = ["MemoryAIService"]
