"""OrchestratorService — build context, run AI, create candidates (B15-T03).

BETA1-AI02: migrated off the legacy ``provider.invoke()`` / ``AIMode`` /
``AIResponse`` path. Real providers now go through ``AIRequestGateway`` →
``provider.chat``; the simulated provider uses a deterministic, mode-keyed
generator (``_simulated_modes``). Modes are plain strings (the old AIMode
values) so the public API stays source-compatible for callers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest
from packages.domain.ai_models import AuthorizedContext
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import create_provider


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OrchestratorResult:
    """Lightweight result for legacy orchestrator calls (replaces AIResponse)."""
    id: str
    mode: str
    raw_text: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    error: str | None = None
    provider: str = "simulated"
    context: AuthorizedContext = field(default_factory=AuthorizedContext)


def _simulated_modes(mode: str, max_candidates: int = 3) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Deterministic simulated output by mode (moved from SimulatedAIProvider).

    Returns ``(raw_text, candidates, observations)``. Text-only modes return an
    empty candidate list. Unknown modes return a generic empty result.
    """
    if mode == "generate_entity":
        return "Simulated entity generation", [
            {"name": "Simulated Entity", "entity_type": "personaje"},
            {"name": "Simulated Location", "entity_type": "localizacion"},
        ][:max_candidates], []
    if mode == "generate_relation":
        return "Simulated relation generation", [
            {"source_id": "", "target_id": "", "relation_type": "es_aliado_de"},
        ][:max_candidates], []
    if mode == "expand_entity":
        return "Simulated expansion: this entity could have additional details...", [
            {"name": "Expanded detail", "entity_type": "objeto"},
        ], []
    if mode == "summarize":
        return "Simulated summary of the entity.", [], []
    if mode == "rewrite_description":
        return (
            "Sugerencia de reescritura simulada. Revisa y acepta solo si encaja con el canon.",
            [{"description": "Texto de reescritura simulado"}], [],
        )
    if mode == "suggest_tags":
        return "Suggested tags: magia, anciano, torre", [{"tags": ["magia", "anciano", "torre"]}], []
    if mode == "suggest_relations":
        return "Simulated relation suggestions", [
            {"source_id": "", "target_id": "", "relation_type": "es_aliado_de"},
        ], []
    if mode == "critical_analysis":
        return "Simulated critical analysis", [
            {"type": "invalid_entity_type", "description": "Entity may lack description", "severity": "MEDIA"},
            {"title": "Add description to entity", "proposed_data": {"brief_description": "Suggested brief"}},
        ], ["Entity has limited faction interactions"]
    if mode == "causal_analysis":
        return "Simulated causal analysis", [
            {"name": "Consequence X", "entity_type": "evento"},
            {"source_id": "", "target_id": "", "relation_type": "causo"},
        ], ["Event has no documented cause"]
    if mode == "consistency_analysis":
        return "Simulated consistency analysis", [
            {"type": "narrative", "description": "Character motivation contradicts earlier behavior"},
            {"type": "causal_gap", "description": "Missing cause for major event"},
        ], []
    if mode == "continuity_question":
        return "Simulated answer to continuity question.", [], ["Consider checking historical timeline for consistency."]
    return "", [], []


class OrchestratorService:
    """Legacy orchestrator — do not use in new features (B42+).

    New code should use AIRequestGateway + AIContextActionService instead.
    Kept for the desktop AI settings/test path, the CLI, and analysis.
    """
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
        mode: str = "generate_entity",
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

    # ── Run ───────────────────────────────────────────────────────────

    def _run_model(self, mode: str, ctx: AuthorizedContext, prompt_hint: str, max_candidates: int = 3):
        """Return (raw_text, candidates, observations) for *mode*."""
        provider_name = str(getattr(self._provider, "provider_name", ""))
        if provider_name == "simulated":
            return _simulated_modes(mode, max_candidates)
        # Real provider: go through the gateway (sanitize → params → chat).
        gateway = AIRequestGateway(provider=self._provider)
        request = GatewayRequest(
            intent=mode,
            user_prompt=prompt_hint or f"Tarea IA: {mode}",
            context=ctx.to_dict(),
            json_mode=True,
            validate=False,
        )
        response = gateway.execute(request)
        if response.error:
            raise RuntimeError(response.error)
        text = response.text or ""
        candidates: list[dict[str, Any]] = []
        parsed = response.parsed_json
        if isinstance(parsed, dict):
            for key in ("candidates", "entities", "relations"):
                value = parsed.get(key)
                if isinstance(value, list):
                    candidates.extend([c for c in value if isinstance(c, dict)])
        return text, candidates, []

    def invoke(
        self, mode: str, entity_id: str | None = None,
        prompt_hint: str = "", filters: dict | None = None,
    ) -> Result[OrchestratorResult, str]:
        if self._provider is None:
            return Error("Provider error: no AI provider configured")
        rctx = self.build_context(mode, entity_id, filters)
        if isinstance(rctx, Error):
            return rctx
        ctx = rctx.value
        try:
            raw_text, candidates, observations = self._run_model(mode, ctx, prompt_hint)
        except Exception as exc:
            self._log_error(f"Provider call failed: {exc}")
            return Error(f"Provider error: {exc}")
        return Ok(OrchestratorResult(
            id=str(uuid.uuid4()),
            mode=mode,
            raw_text=raw_text,
            candidates=candidates,
            observations=observations,
            error=None,
            provider=str(getattr(self._provider, "provider_name", "")) or "simulated",
            context=ctx,
        ))

    def improvise(self, context: str) -> dict | None:
        """Generate improvisation output for LiveModeService (B27)."""
        if self._provider is None:
            return None
        try:
            provider_name = str(getattr(self._provider, "provider_name", ""))
            if provider_name == "simulated":
                raw_text, _, _ = _simulated_modes("generate_entity", 3)
            else:
                text, err = self._provider.chat(
                    "Eres un asistente de improvisación narrativa. Responde en líneas breves.",
                    f"Improvisa elementos a partir de: {context}",
                )
                raw_text = text or ""
            lines = [line.strip("- *") for line in raw_text.split("\n") if len(line.strip()) > 3]
            return {
                "name": lines[0] if len(lines) > 0 else "Improvised element",
                "description": lines[1] if len(lines) > 1 else "Quick improvisation",
                "complication": lines[2] if len(lines) > 2 else "Raise the stakes",
                "consequence": lines[3] if len(lines) > 3 else "Unexpected outcome",
            }
        except Exception:
            return None

    # ── Generate candidates ───────────────────────────────────────────

    def generate_candidates(
        self, mode: str, entity_id: str | None = None,
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
                    "name": f"AI {mode}",
                    "source_type": "GENERACION_IA",
                    "notes": resp.raw_text[:500],
                    "metadata": {
                        "provider": resp.provider,
                        "mode": mode,
                        "audience": resp.context.audience,
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
            ctype = (
                "entidad" if mode in ("generate_entity", "expand_entity")
                else "relacion" if mode in ("generate_relation", "suggest_relations")
                else "correccion" if mode == "rewrite_description"
                else "cambio" if mode == "suggest_tags"
                else "sugerencia_ia"
            )
            try:
                r = self._cs.create_candidate({
                    "title": data.get("name", mode),
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
                    "description": f"AI {mode} generated {len(candidates)} candidates",
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


__all__ = ["OrchestratorService", "OrchestratorResult"]
