"""Context retrieval for advanced narrative RAG (E04).

This module turns an AI job plan into a structured ContextPack. It only reads
the in-memory corpus index; it never calls AI providers, persists data or
mutates canon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import math
import re

from packages.application.corpus_indexer import CorpusIndexRecord, IndexingOptions, NarrativeCorpusIndex
from packages.application.narrative_rag_contract import (
    ContextPack,
    ContextPriority,
    CorpusItemKind,
    RetrievalPlan,
    RetrievalStrategy,
)
from packages.application.rag_service import RAGService
from packages.domain.result import Error, Ok, Result


_STOPWORDS: frozenset[str] = frozenset({
    "a",
    "al",
    "algo",
    "con",
    "de",
    "del",
    "desde",
    "el",
    "en",
    "entre",
    "es",
    "esta",
    "este",
    "esto",
    "la",
    "las",
    "lo",
    "los",
    "para",
    "por",
    "que",
    "se",
    "si",
    "sin",
    "sobre",
    "su",
    "sus",
    "un",
    "una",
    "unas",
    "unos",
    "y",
})


_KIND_BY_NEED: dict[str, tuple[CorpusItemKind, ...]] = {
    "selection": (CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.RELATION),
    "relations": (CorpusItemKind.RELATION, CorpusItemKind.ENTITY, CorpusItemKind.BRANCH),
    "chronology": (CorpusItemKind.CHRONOLOGY, CorpusItemKind.MILESTONE),
    "milestones": (CorpusItemKind.MILESTONE, CorpusItemKind.CHRONOLOGY, CorpusItemKind.RELATION),
    "issues": (CorpusItemKind.ISSUE, CorpusItemKind.RELATION, CorpusItemKind.ENTITY, CorpusItemKind.BRANCH),
    "creative_config": (CorpusItemKind.CREATIVE_CONFIG,),
    "world_layers": (CorpusItemKind.WORLD_LAYER, CorpusItemKind.BRANCH, CorpusItemKind.ENTITY),
    "branches": (CorpusItemKind.BRANCH,),
    "entities": (CorpusItemKind.ENTITY, CorpusItemKind.BRANCH),
}


_KIND_BY_INTENT: dict[str, tuple[CorpusItemKind, ...]] = {
    "generate_entities": (CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.WORLD_LAYER, CorpusItemKind.CREATIVE_CONFIG),
    "generate_tree": (CorpusItemKind.BRANCH, CorpusItemKind.ENTITY, CorpusItemKind.WORLD_LAYER, CorpusItemKind.CREATIVE_CONFIG),
    "suggest_relations": (CorpusItemKind.RELATION, CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.MILESTONE),
    "analyze_coherence": (CorpusItemKind.ISSUE, CorpusItemKind.RELATION, CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.MILESTONE),
    "expand_worldbuilding": (CorpusItemKind.WORLD_LAYER, CorpusItemKind.BRANCH, CorpusItemKind.ENTITY, CorpusItemKind.CREATIVE_CONFIG),
    "explain_from_causes": (CorpusItemKind.MILESTONE, CorpusItemKind.CHRONOLOGY, CorpusItemKind.RELATION, CorpusItemKind.WORLD_LAYER),
    "review_graph": (CorpusItemKind.ISSUE, CorpusItemKind.RELATION, CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.CREATIVE_CONFIG),
    "freeform_planning": (CorpusItemKind.CREATIVE_CONFIG, CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.RELATION),
    "edit_entities": (CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.CREATIVE_CONFIG),
    "propose_milestones": (CorpusItemKind.MILESTONE, CorpusItemKind.CHRONOLOGY, CorpusItemKind.ENTITY, CorpusItemKind.BRANCH, CorpusItemKind.RELATION),
}


@dataclass(frozen=True)
class _ScoredRecord:
    record: CorpusIndexRecord
    score: float
    priority: ContextPriority
    reasons: list[str] = field(default_factory=list)

    @property
    def sort_key(self) -> tuple[int, float, int, str]:
        priority_order = {
            ContextPriority.REQUIRED: 0,
            ContextPriority.HIGH: 1,
            ContextPriority.NORMAL: 2,
            ContextPriority.LOW: 3,
        }
        return (
            priority_order.get(self.priority, 9),
            -self.score,
            self.record.tokens_estimated,
            self.record.key,
        )


class RAGContextBuilder:
    """Builds RetrievalPlan and ContextPack for AI jobs."""

    def __init__(self, rag_service: RAGService | None = None):
        self.rag_service = rag_service or RAGService()

    def build_for_job_plan(self, project: Any, job_plan: Any) -> Result:
        plan = self.build_retrieval_plan(
            prompt=str(getattr(job_plan, "prompt", "") or ""),
            intent=getattr(job_plan, "intent", None),
            context=dict(getattr(job_plan, "context", {}) or {}),
        )
        return self.build_context_pack(project, plan)

    def build_context_pack(self, project: Any, plan: RetrievalPlan) -> Result:
        if project is None:
            return Ok(ContextPack(
                plan=plan,
                warnings=["rag_project_unavailable"],
                tokens_budget=plan.token_budget,
            ))

        options = IndexingOptions(
            include_pending_candidates=plan.include_pending_candidates,
            include_rejected_candidates=plan.include_rejected_candidates,
            include_unaccepted_imports=plan.include_unaccepted_imports,
            audience=plan.audience,
        )
        indexed = self.rag_service.index_project(project, options=options)
        if isinstance(indexed, Error):
            return Ok(ContextPack(
                plan=plan,
                warnings=[f"rag_index_unavailable: {indexed.error}"],
                tokens_budget=plan.token_budget,
            ))
        return Ok(self.retrieve(indexed.value, plan))

    def build_retrieval_plan(
        self,
        *,
        prompt: str,
        intent: Any,
        context: dict[str, Any] | None = None,
    ) -> RetrievalPlan:
        ctx = dict(context or {})
        intent_type = _intent_type(intent)
        retrieval_needs = _string_list(getattr(intent, "retrieval_needs", None))
        if not retrieval_needs and isinstance(ctx.get("command_bar_plan"), dict):
            retrieval_needs = _string_list(ctx["command_bar_plan"].get("retrieval_needs"))
        include_kinds = _include_kinds_for(intent_type, retrieval_needs, prompt)
        if bool(ctx.get("include_unaccepted_imports", False)) or bool(ctx.get("include_import_documents", False)):
            include_kinds = _dedupe_kinds([*include_kinds, CorpusItemKind.IMPORT_DOCUMENT])
        active_layer_ids = _dedupe(
            _string_list(ctx.get("active_layer_ids"))
            + _ring_as_layer_ids(ctx.get("active_ring_id") or ctx.get("focused_ring_id"))
        )
        strategy = _strategy_for(intent_type, retrieval_needs, prompt)
        return RetrievalPlan(
            intent_type=intent_type,
            query=_query_text(prompt, retrieval_needs, ctx),
            selected_entity_ids=_string_list(ctx.get("selected_entity_ids")),
            selected_relation_ids=_string_list(ctx.get("selected_relation_ids")),
            active_layer_ids=active_layer_ids,
            include_kinds=include_kinds,
            strategy=strategy,
            token_budget=_token_budget_for(strategy, ctx),
            timeout_ms=1500,
            include_pending_candidates=bool(ctx.get("include_pending_candidates", False)),
            include_rejected_candidates=bool(ctx.get("include_rejected_candidates", False)),
            include_unaccepted_imports=bool(ctx.get("include_unaccepted_imports", False)),
            audience=str(ctx.get("audience") or "gm"),
        )

    def retrieve(self, index: NarrativeCorpusIndex, plan: RetrievalPlan) -> ContextPack:
        warnings = list(index.stats.warnings)
        if not index.records:
            return ContextPack(
                plan=plan,
                warnings=warnings + ["rag_index_empty"],
                tokens_budget=plan.token_budget,
            )

        tokens = _tokens(plan.query)
        # BETA1-AI01: IDF over the corpus so distinctive query words drive
        # retrieval, not raw word count (a step up from naive token overlap).
        idf = _idf_map(index, tokens)
        scored = [
            scored_record
            for record in index.items()
            if (scored_record := _score_record(record, plan, tokens, idf)) is not None
        ]
        scored.sort(key=lambda item: item.sort_key)

        selected: list[_ScoredRecord] = []
        used = 0
        truncated = False
        for item in scored:
            cost = max(0, item.record.tokens_estimated)
            must_include = item.priority == ContextPriority.REQUIRED
            if not must_include and used + cost > plan.token_budget:
                truncated = True
                continue
            selected.append(item)
            used += cost

        if not selected:
            warnings.append("rag_no_relevant_items")
        if truncated:
            warnings.append("rag_context_truncated_to_budget")

        context_items = [
            item.record.to_context_item(
                score=round(item.score, 3),
                reason=", ".join(_dedupe(item.reasons)) or "retrieved",
                priority=item.priority,
            )
            for item in selected
        ]
        return ContextPack(
            plan=plan,
            items=context_items,
            warnings=_dedupe(warnings),
            tokens_budget=plan.token_budget,
            tokens_estimated=sum(max(0, item.tokens_estimated) for item in context_items),
            truncated=truncated,
        )


def _score_record(record: CorpusIndexRecord, plan: RetrievalPlan, query_tokens: set[str], idf: dict[str, float] | None = None) -> _ScoredRecord | None:
    reasons: list[str] = []
    score = 0.0
    priority = ContextPriority.LOW

    if _is_selected_record(record, plan):
        score += 100.0
        priority = ContextPriority.REQUIRED
        reasons.append("selected_item")

    if _references_selection(record, plan):
        score += 55.0
        priority = _max_priority(priority, ContextPriority.HIGH)
        reasons.append("references_selection")

    if _matches_active_layer(record, plan):
        score += 24.0
        priority = _max_priority(priority, ContextPriority.HIGH)
        reasons.append("active_ring_or_layer")

    if record.kind in plan.include_kinds:
        score += 12.0
        priority = _max_priority(priority, ContextPriority.NORMAL)
        reasons.append("intent_relevant_kind")

    overlap = _text_overlap_score(record, query_tokens, idf or {})
    if overlap > 0:
        score += min(40.0, overlap * 3.0)
        priority = _max_priority(priority, ContextPriority.NORMAL)
        reasons.append("text_overlap")

    if _is_structural_relation(record):
        score += 5.0
        reasons.append("structural_relation")

    if record.kind == CorpusItemKind.CREATIVE_CONFIG and plan.strategy != RetrievalStrategy.PRECISION:
        score += 8.0
        priority = _max_priority(priority, ContextPriority.NORMAL)
        reasons.append("creative_baseline")

    if score <= 0:
        return None
    return _ScoredRecord(record=record, score=score, priority=priority, reasons=reasons)


def _intent_type(intent: Any) -> str:
    value = getattr(intent, "intent_type", "unknown")
    return str(getattr(value, "value", value) or "unknown")


def _include_kinds_for(intent_type: str, retrieval_needs: list[str], prompt: str) -> list[CorpusItemKind]:
    kinds: list[CorpusItemKind] = list(_KIND_BY_INTENT.get(intent_type, (CorpusItemKind.ENTITY, CorpusItemKind.BRANCH)))
    for need in retrieval_needs:
        kinds.extend(_KIND_BY_NEED.get(str(need).strip().lower(), ()))

    prompt_tokens = _tokens(prompt)
    if prompt_tokens & {"relacion", "relaciones", "vinculo", "vinculos"}:
        kinds.append(CorpusItemKind.RELATION)
    if prompt_tokens & {"hito", "hitos", "cronologia", "calendario"}:
        kinds.extend((CorpusItemKind.MILESTONE, CorpusItemKind.CHRONOLOGY))
    if prompt_tokens & {"coherencia", "incoherencia", "contradiccion", "contradicciones"}:
        kinds.extend((CorpusItemKind.ISSUE, CorpusItemKind.RELATION))
    if prompt_tokens & {"anillo", "anillos", "capa", "capas", "worldbuilding"}:
        kinds.extend((CorpusItemKind.WORLD_LAYER, CorpusItemKind.BRANCH))
    if prompt_tokens & {"documento", "documentos", "importacion", "importaciones", "importado", "importados", "chunk", "chunks"}:
        kinds.append(CorpusItemKind.IMPORT_DOCUMENT)

    kinds.append(CorpusItemKind.CREATIVE_CONFIG)
    return _dedupe_kinds(kinds)


def _strategy_for(intent_type: str, retrieval_needs: list[str], prompt: str) -> RetrievalStrategy:
    text = f"{intent_type} {' '.join(retrieval_needs)} {prompt}".lower()
    if "hito" in text or "cronolog" in text or "calendario" in text:
        return RetrievalStrategy.CHRONOLOGICAL
    if "causa" in text or "causal" in text or "anillo" in text:
        return RetrievalStrategy.CAUSAL
    if intent_type in {"suggest_relations", "edit_entities"}:
        return RetrievalStrategy.PRECISION
    if intent_type in {"review_graph", "freeform_planning", "expand_worldbuilding"}:
        return RetrievalStrategy.BREADTH
    return RetrievalStrategy.BALANCED


def _token_budget_for(strategy: RetrievalStrategy, context: dict[str, Any]) -> int:
    raw = context.get("rag_token_budget")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = {
            RetrievalStrategy.PRECISION: 1800,
            RetrievalStrategy.BALANCED: 2400,
            RetrievalStrategy.BREADTH: 3200,
            RetrievalStrategy.CAUSAL: 2800,
            RetrievalStrategy.CHRONOLOGICAL: 2800,
        }.get(strategy, 2400)
    return max(300, min(6000, value))


def _query_text(prompt: str, retrieval_needs: list[str], context: dict[str, Any]) -> str:
    parts = [prompt or "", " ".join(retrieval_needs)]
    focus = context.get("focus_label")
    if focus:
        parts.append(str(focus))
    return " ".join(part for part in parts if part).strip()


def _is_selected_record(record: CorpusIndexRecord, plan: RetrievalPlan) -> bool:
    if record.kind in {CorpusItemKind.ENTITY, CorpusItemKind.BRANCH}:
        return record.ref_id in set(plan.selected_entity_ids)
    if record.kind == CorpusItemKind.RELATION:
        return record.ref_id in set(plan.selected_relation_ids)
    return False


def _references_selection(record: CorpusIndexRecord, plan: RetrievalPlan) -> bool:
    selected_refs = _selection_ref_tokens(plan)
    if selected_refs.intersection(record.references):
        return True
    metadata = record.metadata or {}
    for key in ("source_id", "target_id"):
        value = metadata.get(key)
        if value and f"entity:{value}" in selected_refs:
            return True
    for key in ("affected_entity_ids", "affected_branch_ids", "child_entity_ids", "parent_branch_ids"):
        if any(f"entity:{item}" in selected_refs or f"branch:{item}" in selected_refs for item in _string_list(metadata.get(key))):
            return True
    for key in ("affected_relation_ids", "caused_relation_ids"):
        if any(f"relation:{item}" in selected_refs for item in _string_list(metadata.get(key))):
            return True
    return False


def _matches_active_layer(record: CorpusIndexRecord, plan: RetrievalPlan) -> bool:
    active = {layer_id for layer_id in plan.active_layer_ids if layer_id}
    if not active:
        return False
    if record.kind == CorpusItemKind.WORLD_LAYER and record.ref_id in active:
        return True
    if {ref.split(":", 1)[1] for ref in record.references if ref.startswith("world_layer:")}.intersection(active):
        return True
    return bool(set(_string_list((record.metadata or {}).get("layer_ids"))).intersection(active))


def _record_text_tokens(record: CorpusIndexRecord) -> set[str]:
    metadata_tokens = _tokens(" ".join(str(value) for value in (record.metadata or {}).values()))
    return _tokens(record.rendered_text) | metadata_tokens


def _idf_map(index: NarrativeCorpusIndex, query_tokens: set[str]) -> dict[str, float]:
    """Inverse document frequency for the query tokens over the corpus.

    Rare words (appear in few records) weigh more than common ones. Computed
    only for the query tokens, so it stays cheap."""
    if not query_tokens:
        return {}
    records = list(index.items())
    total = len(records) or 1
    df = {token: 0 for token in query_tokens}
    for record in records:
        record_tokens = _record_text_tokens(record)
        for token in query_tokens:
            if token in record_tokens:
                df[token] += 1
    return {token: math.log(1.0 + total / (1.0 + count)) for token, count in df.items()}


def _text_overlap_score(record: CorpusIndexRecord, query_tokens: set[str], idf: dict[str, float]) -> float:
    """IDF-weighted overlap between the query and a record (BETA1-AI01)."""
    if not query_tokens:
        return 0.0
    shared = query_tokens & _record_text_tokens(record)
    if not shared:
        return 0.0
    return sum(idf.get(token, 1.0) for token in shared)


def _selection_ref_tokens(plan: RetrievalPlan) -> set[str]:
    refs = {f"entity:{item}" for item in plan.selected_entity_ids}
    refs.update(f"branch:{item}" for item in plan.selected_entity_ids)
    refs.update(f"relation:{item}" for item in plan.selected_relation_ids)
    return refs


def _is_structural_relation(record: CorpusIndexRecord) -> bool:
    return record.kind == CorpusItemKind.RELATION and bool((record.metadata or {}).get("structural", False))


def _max_priority(current: ContextPriority, candidate: ContextPriority) -> ContextPriority:
    rank = {
        ContextPriority.REQUIRED: 0,
        ContextPriority.HIGH: 1,
        ContextPriority.NORMAL: 2,
        ContextPriority.LOW: 3,
    }
    return candidate if rank[candidate] < rank[current] else current


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[\w]+", str(text or "").lower(), flags=re.UNICODE)
    return {token for token in raw if len(token) > 2 and token not in _STOPWORDS}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _ring_as_layer_ids(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text or text in {"global", "unclassified", "__unclassified__", "sin_anillo"}:
        return []
    return [text]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _dedupe_kinds(items: Iterable[CorpusItemKind]) -> list[CorpusItemKind]:
    seen: set[str] = set()
    result: list[CorpusItemKind] = []
    for item in items:
        if item.value not in seen:
            seen.add(item.value)
            result.append(item)
    return result


__all__ = ["RAGContextBuilder"]
