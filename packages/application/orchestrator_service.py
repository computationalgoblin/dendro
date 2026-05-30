"""OrchestratorService — build context, invoke AI, create candidates (B15-T03)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from packages.domain.ai_models import AIMode, AIOperation, AIResponse, AuthorizedContext
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider, create_provider


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OrchestratorService:
    def __init__(
        self,
        project_service: Any,
        candidate_service: Any = None,
        source_service: Any = None,
        history_service: Any = None,
        provider_name: str = "simulated",
    ):
        self._ps = project_service
        self._cs = candidate_service
        self._ss = source_service
        self._hs = history_service
        self._provider = create_provider(provider_name)

    def _proj(self):
        p = self._ps.active_project
        if p is None:
            return Error("No active project")
        return Ok(p)

    # ── Context ───────────────────────────────────────────────────────

    def build_context(
        self,
        mode: AIMode = AIMode.GENERATE_ENTITY,
        entity_id: str | None = None,
        filters: dict | None = None,
    ) -> Result[AuthorizedContext, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        p = proj.value

        ctx = AuthorizedContext(
            project_name=p.name,
            audience=filters.get("audience", "author") if filters else "author",
        )

        if filters:
            ctx.domain_id = filters.get("domain_id")
            ctx.layer_id = filters.get("layer_id")
            ctx.allowed_canon_states = filters.get("canon_states", [])
            ctx.allowed_visibility_states = filters.get("visibility_states", [])
            ctx.include_history = filters.get("include_history", False)
            ctx.include_issues = filters.get("include_issues", False)
            ctx.output_profile = filters.get("output_profile", "default")
            if filters.get("active_framework_ids"):
                ctx.active_framework_ids = filters["active_framework_ids"]

        # Entity payload
        is_author = ctx.audience == "author"
        for e in p.entities:
            if ctx.allowed_canon_states and e.canon_state.value not in ctx.allowed_canon_states:
                continue
            if ctx.allowed_visibility_states and e.visibility_state.value not in ctx.allowed_visibility_states:
                continue
            ent = {"id": e.id, "name": e.name, "entity_type": e.entity_type.value}
            if is_author:
                ent["brief_description"] = e.brief_description
                ent["extended_description"] = e.extended_description
            else:
                ent["brief_description"] = e.brief_description
            ctx.context_entities.append(ent)

        # Relation payload
        for r in p.relations:
            ctx.context_relations.append({
                "id": r.id, "source_id": r.source_id, "target_id": r.target_id,
                "relation_type": r.relation_type.value,
            })

        # Frameworks
        for fw in getattr(p, "narrative_frameworks", []):
            if fw.is_active or not ctx.active_framework_ids or fw.id in ctx.active_framework_ids:
                ctx.framework_context.append({
                    "id": fw.id, "name": fw.name, "type": fw.framework_type.value,
                })

        # Issues
        if ctx.include_issues:
            for i in p.issues:
                ctx.context_issues.append({
                    "id": i.id, "type": i.type.value, "state": i.state.value,
                    "description": i.description,
                })

        # History
        if ctx.include_history:
            for h in p.history[-20:]:
                ctx.context_history.append({
                    "event_type": h.event_type, "description": h.description,
                })

        # Config snapshot
        ctx.project_config_snapshot = {
            "genre": getattr(p, "genre", ""),
            "tone": getattr(p, "tone", ""),
        }

        return Ok(ctx)

    # ── Invoke ────────────────────────────────────────────────────────

    def invoke(
        self, mode: AIMode, entity_id: str | None = None,
        prompt_hint: str = "", filters: dict | None = None,
    ) -> Result[AIResponse, str]:
        rctx = self.build_context(mode, entity_id, filters)
        if isinstance(rctx, Error):
            return rctx
        op = AIOperation(mode=mode, context=rctx.value, prompt_hint=prompt_hint,
                         entity_id=entity_id)
        try:
            resp = self._provider.invoke(op)
            return Ok(resp)
        except Exception as exc:
            self._log_error(f"Provider invoke failed: {exc}")
            return Error(f"AI provider error: {exc}")

    # ── Generate candidates ───────────────────────────────────────────

    def generate_candidates(
        self, mode: AIMode, entity_id: str | None = None,
        prompt_hint: str = "", filters: dict | None = None,
    ) -> Result[list[Any], str]:
        rresp = self.invoke(mode, entity_id, prompt_hint, filters)
        if isinstance(rresp, Error):
            return rresp
        resp = rresp.value

        # Create Source IA
        source_id = None
        if self._ss:
            try:
                src = self._ss.add_source({
                    "name": f"AI {mode.value}",
                    "source_type": "GENERACION_IA",
                    "notes": resp.raw_text[:500],
                    "metadata": {
                        "provider": resp.provider,
                        "mode": mode.value,
                        "audience": resp.operation.context.audience,
                        "prompt_hint": prompt_hint,
                        "filters": filters,
                    },
                })
                if not isinstance(src, Error):
                    source_id = src.value.id
            except Exception:
                pass

        # Create candidates
        candidates = []
        for data in resp.candidates:
            if not self._cs:
                break
            ctype = "entidad" if mode in (AIMode.GENERATE_ENTITY, AIMode.EXPAND_ENTITY) else                     "relacion" if mode in (AIMode.GENERATE_RELATION, AIMode.SUGGEST_RELATIONS) else                     "correccion" if mode == AIMode.REWRITE_DESCRIPTION else                     "cambio" if mode == AIMode.SUGGEST_TAGS else "sugerencia_ia"
            try:
                r = self._cs.create_candidate({
                    "title": data.get("name", mode.value),
                    "candidate_type": ctype,
                    "proposed_data": data,
                    "source": "ia",
                    "source_id": source_id,
                    "confidence": 0.5,
                })
                if not isinstance(r, Error):
                    candidates.append(r.value)
            except Exception:
                pass

        # History
        if self._hs:
            try:
                self._hs.add_entry({
                    "event_type": "candidato_generado_ia",
                    "description": f"AI {mode.value} generated {len(candidates)} candidates",
                    "metadata": {"ai_response_id": resp.id},
                })
            except Exception:
                pass

        return Ok(candidates)

    def _log_error(self, msg: str) -> None:
        if self._hs:
            try:
                self._hs.add_entry({
                    "event_type": "operacion_ia_fallida",
                    "description": msg,
                })
            except Exception:
                pass


__all__ = ["OrchestratorService"]
