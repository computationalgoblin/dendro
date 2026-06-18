"""AnalysisService — critical, causal, consistency analysis (B16-T03)."""

from __future__ import annotations

from typing import Any

from packages.application.orchestrator_service import OrchestratorResult, OrchestratorService
from packages.domain.analysis_models import (
    CausalAnalysisResult, ConsistencyAnalysisResult, CriticalAnalysisResult,
    CriticalAnalysisTarget,
)
from packages.domain.candidate_issue import StructuredIssue
from packages.domain.result import Error, Ok, Result


class AnalysisService:
    def __init__(self, orchestrator: OrchestratorService, issue_service=None, source_service=None):
        self._orch = orchestrator
        self._is = issue_service
        self._ss = source_service

    def _create_source_ia(self, mode: str, resp: OrchestratorResult) -> str | None:
        if not self._ss:
            return None
        try:
            src = self._ss.add_source({
                "name": f"AI Analysis {mode}",
                "source_type": "GENERACION_IA",
                "notes": resp.raw_text[:500],
                "metadata": {
                    "provider": resp.provider,
                    "ai_mode": mode,
                    "audience": resp.context.audience,
                    "filters": {
                        "canon": resp.context.allowed_canon_states,
                        "visibility": resp.context.allowed_visibility_states,
                    },
                },
            })
            return src.value.id if not isinstance(src, Error) else None
        except Exception:
            return None

    def analyze_entity(self, entity_id: str, filters=None) -> Result[CriticalAnalysisResult, str]:
        rresp = self._orch.invoke("critical_analysis", entity_id, "", filters)
        if isinstance(rresp, Error):
            return rresp
        resp = rresp.value
        src_id = self._create_source_ia("critical", resp)

        result = CriticalAnalysisResult(
            target_id=entity_id, target_type=CriticalAnalysisTarget.ENTITY,
            observations=resp.observations,
            raw_response=resp.raw_text,
        )
        candidates = resp.candidates
        for cand in candidates:
            if "type" in cand and "description" in cand:
                result.candidate_issues.append(cand)
                self._create_issue_ia(cand, "critical", src_id)
            elif "title" in cand or "proposed_data" in cand:
                result.correction_proposals.append(cand)
                self._create_candidate_ia(cand, "correccion", src_id)
        return Ok(result)

    def analyze_causal(self, entity_id: str, filters=None) -> Result[CausalAnalysisResult, str]:
        rresp = self._orch.invoke("causal_analysis", entity_id, "", filters)
        if isinstance(rresp, Error):
            return rresp
        resp = rresp.value
        src_id = self._create_source_ia("causal", resp)

        result = CausalAnalysisResult(source_entity_id=entity_id, raw_response=resp.raw_text)
        for cand in resp.candidates:
            if "source_id" in cand and "relation_type" in cand:
                result.causal_relation_candidates.append(cand)
                self._create_candidate_ia(cand, "relacion", src_id)
            elif "entity_type" in cand:
                result.direct_consequences.append(cand)
                self._create_candidate_ia(cand, "entidad", src_id)
        return Ok(result)

    def analyze_consistency(self, scope_id=None, filters=None) -> Result[ConsistencyAnalysisResult, str]:
        rresp = self._orch.invoke("consistency_analysis", scope_id, "", filters)
        if isinstance(rresp, Error):
            return rresp
        resp = rresp.value
        src_id = self._create_source_ia("consistency", resp)

        result = ConsistencyAnalysisResult(scope_id=scope_id, raw_response=resp.raw_text)
        for cand in resp.candidates:
            ctype = cand.get("type", "")
            if ctype == "narrative":
                result.narrative_contradictions.append(cand)
            elif ctype == "causal_gap":
                result.causal_gaps.append(cand)
            else:
                result.narrative_contradictions.append(cand)
            self._create_issue_ia(cand, "consistency", src_id)
        return Ok(result)

    def _create_candidate_ia(self, data, ctype, src_id):
        cs = self._orch._cs
        if cs:
            try:
                cs.create_candidate({
                    "title": data.get("name", data.get("title", ctype)),
                    "candidate_type": ctype,
                    "proposed_data": data,
                    "source": "ia",
                    "source_id": src_id,
                    "confidence": 0.5,
                })
            except Exception:
                pass

    def _create_issue_ia(self, data, ai_mode, src_id):
        if not self._is:
            return
        try:
            itype = data.get("type", "invalid_entity_type")
            from packages.domain.candidate_issue import StructuredIssueType
            try:
                itype_enum = StructuredIssueType(itype)
            except ValueError:
                itype_enum = StructuredIssueType.INVALID_ENTITY_TYPE
            metadata = {"ai_mode": ai_mode, "source": "ia"}
            affected_source_ids = []
            if src_id:
                metadata["source_id"] = src_id
                affected_source_ids.append(src_id)
            issue = StructuredIssue(
                description=data.get("description", f"AI {ai_mode} issue"),
                affected_entity_ids=[],
                affected_source_ids=affected_source_ids,
                metadata=metadata,
                type=itype_enum,
            )
            self._is.add_issue(issue)
        except Exception:
            pass


__all__ = ["AnalysisService"]
