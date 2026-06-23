"""Import candidate deduplication, aliases and merge suggestions (I04)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any
import re
import unicodedata
import uuid

from packages.domain.candidate_issue import CandidateType
from packages.domain.import_models import ImportBasket, ImportCandidate, ImportReviewState
from packages.domain.result import Error, Ok, Result


MERGEABLE_STATES = {
    ImportReviewState.PENDIENTE,
    ImportReviewState.EDITADO,
    ImportReviewState.PARCIAL,
}

MERGEABLE_KINDS = {"entity", "branch"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _unique_text(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _as_text(value)
        if not text:
            continue
        key = _norm(text)
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _norm(value: Any) -> str:
    text = _as_text(value).lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = [
        word for word in text.split()
        if word not in {"el", "la", "los", "las", "un", "una", "de", "del"}
    ]
    return " ".join(words)


def _similarity(left: str, right: str) -> float:
    left_n = _norm(left)
    right_n = _norm(right)
    if not left_n or not right_n:
        return 0.0
    if left_n == right_n:
        return 1.0
    left_tokens = set(left_n.split())
    right_tokens = set(right_n.split())
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
        if overlap >= 0.75:
            return max(overlap, SequenceMatcher(None, left_n, right_n).ratio())
    return SequenceMatcher(None, left_n, right_n).ratio()


def _payload(candidate: ImportCandidate) -> dict[str, Any]:
    return _as_dict(getattr(candidate, "proposed_data", {}))


def _kind(candidate: ImportCandidate) -> str:
    payload = _payload(candidate)
    kind = _as_text(payload.get("kind")).lower()
    if kind:
        return kind
    if candidate.candidate_type == CandidateType.ENTIDAD.value:
        return "entity"
    if candidate.candidate_type == CandidateType.RELACION.value:
        return "relation"
    return _as_text(candidate.candidate_type)


def _candidate_name(candidate: ImportCandidate) -> str:
    payload = _payload(candidate)
    return (
        _as_text(payload.get("name"))
        or _as_text(payload.get("entity_name"))
        or _as_text(payload.get("title"))
        or _as_text(payload.get("ring_name"))
    )


def _candidate_aliases(candidate: ImportCandidate) -> list[str]:
    payload = _payload(candidate)
    values: list[Any] = []
    values.extend(_as_list(payload.get("aliases")))
    values.extend(_as_list(payload.get("alias_names")))
    if payload.get("alias"):
        values.append(payload.get("alias"))
    return _unique_text(values)


def _candidate_type_name(candidate: ImportCandidate) -> str:
    payload = _payload(candidate)
    return (
        _as_text(payload.get("entity_type"))
        or _as_text(payload.get("branch_type"))
        or _as_text(payload.get("candidate_subtype"))
    )


def _source_references(candidate: ImportCandidate) -> list[dict[str, Any]]:
    payload = _payload(candidate)
    refs = []
    for ref in _as_list(payload.get("source_references")):
        if isinstance(ref, dict):
            refs.append(dict(ref))
    return refs


def _dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for ref in refs:
        key = (
            _as_text(ref.get("source_id")),
            _as_text(ref.get("segment_id")),
            _as_text(ref.get("chunk_id")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def _candidate_ref(candidate: ImportCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.id,
        "kind": _kind(candidate),
        "name": _candidate_name(candidate),
        "candidate_type": candidate.candidate_type,
        "source_references": _source_references(candidate),
    }


def _append_unique(target: list[str], values: list[str]) -> None:
    seen = set(target)
    for value in values:
        if value and value not in seen:
            target.append(value)
            seen.add(value)


@dataclass
class ImportDeduplicationService:
    """Detect duplicate import candidates and manage merge suggestions."""

    project: Any | None = None

    def analyze_basket(self, basket: ImportBasket, *, append: bool = True) -> Result[list[ImportCandidate], str]:
        suggestions: list[ImportCandidate] = []
        self._mark_canon_duplicates(basket)
        candidates = [c for c in basket.import_candidates if self._is_mergeable(c)]

        for index, left in enumerate(candidates):
            for right in candidates[index + 1:]:
                suggestion = self._build_suggestion(left, right)
                if suggestion is None:
                    continue
                suggestions.append(suggestion)

        if append:
            existing_keys = {
                self._suggestion_key(c)
                for c in basket.import_candidates
                if _kind(c) == "merge_suggestion"
            }
            for suggestion in suggestions:
                key = self._suggestion_key(suggestion)
                if key in existing_keys:
                    continue
                basket.import_candidates.append(suggestion)
                existing_keys.add(key)
            basket.updated_at = _now_iso()
        return Ok(suggestions)

    def consolidate_basket(self, basket: ImportBasket) -> Result[list[ImportCandidate], str]:
        """Fusiona duplicados internos del documento ANTES de presentar (I15).

        A diferencia de ``analyze_basket`` (que solo SUGIERE merge_suggestions),
        aquí se consolida in situ: cada grupo de candidatos equivalentes se
        sustituye por UN candidato fusionado enriquecido; los originales quedan
        ``FUSIONADO`` y el merged ``PENDIENTE``. Así la IA no ofrece el mismo
        candidato N veces. Idempotente (candidatos ya FUSIONADO se ignoran).
        """
        candidates = [c for c in basket.import_candidates if self._is_mergeable(c)]
        if len(candidates) < 2:
            return Ok([])

        parent = {c.id: c.id for c in candidates}

        def find(node: str) -> str:
            root = node
            while parent[root] != root:
                root = parent[root]
            while parent[node] != root:
                parent[node], node = root, parent[node]
            return root

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for index, left in enumerate(candidates):
            for right in candidates[index + 1:]:
                if _kind(left) == _kind(right) and self._equivalent(left, right):
                    union(left.id, right.id)

        groups: dict[str, list[ImportCandidate]] = {}
        for candidate in candidates:
            groups.setdefault(find(candidate.id), []).append(candidate)

        order = {c.id: i for i, c in enumerate(basket.import_candidates)}
        merged_list: list[ImportCandidate] = []
        for members in groups.values():
            if len(members) < 2:
                continue
            ordered = sorted(members, key=lambda c: order.get(c.id, 0))
            suggestion = self._build_merge_suggestion(
                ordered, reason="auto_consolidation", confidence=0.9
            )
            merged = self._merged_candidate(suggestion, ordered)
            for source in ordered:
                source.review_state = ImportReviewState.FUSIONADO
            basket.import_candidates.append(merged)
            merged_list.append(merged)
        if merged_list:
            basket.updated_at = _now_iso()
        return Ok(merged_list)

    def _equivalent(self, left: ImportCandidate, right: ImportCandidate) -> bool:
        """Igualdad de candidatos sin efectos secundarios (para consolidar)."""
        left_name = _candidate_name(left)
        right_name = _candidate_name(right)
        if not left_name or not right_name:
            return False
        if _norm(left_name) == _norm(right_name):
            return True
        left_aliases = {_norm(a) for a in _candidate_aliases(left)}
        right_aliases = {_norm(a) for a in _candidate_aliases(right)}
        if _norm(left_name) in right_aliases or _norm(right_name) in left_aliases:
            return True
        return _similarity(left_name, right_name) >= 0.84

    def create_merge_suggestion(
        self,
        basket: ImportBasket,
        candidate_ids: list[str],
        *,
        reason: str = "manual_merge",
    ) -> Result[ImportCandidate, str]:
        sources = self._find_candidates(basket, candidate_ids)
        if len(sources) < 2:
            return Error("Need at least 2 mergeable candidates")
        suggestion = self._build_manual_suggestion(sources, reason=reason)
        basket.import_candidates.append(suggestion)
        basket.updated_at = _now_iso()
        return Ok(suggestion)

    def accept_merge_suggestion(self, basket: ImportBasket, suggestion_id: str) -> Result[ImportCandidate, str]:
        suggestion = self._get_candidate(basket, suggestion_id)
        if suggestion is None:
            return Error(f"Merge suggestion '{suggestion_id[:8]}' not found")
        if _kind(suggestion) != "merge_suggestion":
            return Error("Candidate is not a merge suggestion")
        if suggestion.review_state not in MERGEABLE_STATES:
            return Error(f"Cannot accept merge suggestion in state '{suggestion.review_state.value}'")

        payload = _payload(suggestion)
        source_ids = [
            _as_text(item.get("candidate_id"))
            for item in _as_list(payload.get("candidate_refs"))
            if isinstance(item, dict)
        ]
        if not source_ids:
            source_ids = [_as_text(v) for v in _as_list(payload.get("affected_candidate_ids"))]
        sources = self._find_candidates(basket, source_ids)
        if len(sources) < 2:
            return Error("Merge suggestion does not reference at least 2 existing candidates")

        merged = self._merged_candidate(suggestion, sources)
        for source in sources:
            source.review_state = ImportReviewState.FUSIONADO
        suggestion.review_state = ImportReviewState.ACEPTADO
        basket.import_candidates.append(merged)
        basket.updated_at = _now_iso()
        return Ok(merged)

    def reject_merge_suggestion(self, basket: ImportBasket, suggestion_id: str) -> Result[None, str]:
        suggestion = self._get_candidate(basket, suggestion_id)
        if suggestion is None:
            return Error(f"Merge suggestion '{suggestion_id[:8]}' not found")
        if _kind(suggestion) != "merge_suggestion":
            return Error("Candidate is not a merge suggestion")
        if suggestion.review_state not in MERGEABLE_STATES:
            return Error(f"Cannot reject merge suggestion in state '{suggestion.review_state.value}'")
        suggestion.review_state = ImportReviewState.RECHAZADO
        basket.updated_at = _now_iso()
        return Ok(None)

    def _is_mergeable(self, candidate: ImportCandidate) -> bool:
        return (
            candidate.review_state in MERGEABLE_STATES
            and _kind(candidate) in MERGEABLE_KINDS
            and bool(_candidate_name(candidate))
        )

    def _mark_canon_duplicates(self, basket: ImportBasket) -> None:
        if self.project is None:
            return
        entities = list(getattr(self.project, "entities", []) or [])
        for candidate in basket.import_candidates:
            if not self._is_mergeable(candidate):
                continue
            name = _candidate_name(candidate)
            names = {_norm(name), *(_norm(alias) for alias in _candidate_aliases(candidate))}
            duplicate_ids: list[str] = []
            duplicate_payloads: list[dict[str, Any]] = []
            for entity in entities:
                entity_names = {_norm(getattr(entity, "name", ""))}
                entity_names.update(_norm(alias) for alias in getattr(entity, "aliases", []) or [])
                if names & entity_names:
                    duplicate_ids.append(getattr(entity, "id", ""))
                    duplicate_payloads.append({
                        "entity_id": getattr(entity, "id", ""),
                        "name": getattr(entity, "name", ""),
                        "reason": "name_or_alias_match",
                    })
            _append_unique(candidate.possible_duplicates, [v for v in duplicate_ids if v])
            if duplicate_payloads:
                payload = _payload(candidate)
                payload["duplicate_candidates"] = _as_list(payload.get("duplicate_candidates")) + duplicate_payloads
                candidate.proposed_data = payload

    def _build_suggestion(self, left: ImportCandidate, right: ImportCandidate) -> ImportCandidate | None:
        left_name = _candidate_name(left)
        right_name = _candidate_name(right)
        left_aliases = _candidate_aliases(left)
        right_aliases = _candidate_aliases(right)
        score = _similarity(left_name, right_name)

        alias_hit = _norm(left_name) in {_norm(a) for a in right_aliases} or _norm(right_name) in {_norm(a) for a in left_aliases}
        exact_hit = _norm(left_name) == _norm(right_name)
        if exact_hit:
            reason = "exact_name_match"
            confidence = 0.95
        elif alias_hit:
            reason = "alias_match"
            confidence = 0.92
        elif score >= 0.84:
            reason = "similar_name_match"
            confidence = min(0.86, max(0.68, score))
        else:
            return None

        return self._build_merge_suggestion([left, right], reason=reason, confidence=confidence)

    def _build_manual_suggestion(self, sources: list[ImportCandidate], *, reason: str) -> ImportCandidate:
        return self._build_merge_suggestion(sources, reason=reason, confidence=0.7)

    def _build_merge_suggestion(
        self,
        sources: list[ImportCandidate],
        *,
        reason: str,
        confidence: float,
    ) -> ImportCandidate:
        refs = [_candidate_ref(source) for source in sources]
        source_references = _dedupe_refs([
            ref
            for source in sources
            for ref in _source_references(source)
        ])
        names = [_candidate_name(source) for source in sources]
        aliases = _unique_text([
            alias
            for source in sources
            for alias in _candidate_aliases(source)
        ] + names[1:])
        type_values = _unique_text([_candidate_type_name(source) for source in sources])
        conflicting_fields: list[dict[str, Any]] = []
        if len(type_values) > 1:
            conflicting_fields.append({"field": "type", "values": type_values})
            for source in sources:
                _append_unique(source.possible_contradictions, [s.id for s in sources if s.id != source.id])

        payload = {
            "kind": "merge_suggestion",
            "title": f"Fusionar {names[0]}",
            "left_ref": refs[0] if refs else {},
            "right_ref": refs[1] if len(refs) > 1 else {},
            "candidate_refs": refs,
            "reason": reason,
            "confidence": confidence,
            "fields_to_merge": ["name", "aliases", "summary", "body", "source_references"],
            "conflicting_fields": conflicting_fields,
            "recommended_resolution": "accept_merge" if not conflicting_fields else "manual_review_required",
            "affected_candidate_ids": [source.id for source in sources],
            "aliases": aliases,
            "source_references": source_references,
        }
        return ImportCandidate(
            id=_new_id(),
            segment_id=sources[0].segment_id if sources else "",
            candidate_type=CandidateType.FUSION.value,
            proposed_data=payload,
            confidence=confidence,
            review_state=ImportReviewState.PENDIENTE,
        )

    def _merged_candidate(self, suggestion: ImportCandidate, sources: list[ImportCandidate]) -> ImportCandidate:
        first_payload = _payload(sources[0])
        source_payloads = [_payload(source) for source in sources]
        source_references = _dedupe_refs([
            ref
            for source in sources
            for ref in _source_references(source)
        ] + _source_references(suggestion))
        main_name = _candidate_name(sources[0])
        aliases = _unique_text([
            alias
            for source in sources
            for alias in _candidate_aliases(source)
        ] + [_candidate_name(source) for source in sources[1:]])
        type_values = _unique_text([_candidate_type_name(source) for source in sources])
        descriptions = _unique_text([
            payload.get("summary") or payload.get("brief_description") or payload.get("description") or payload.get("body")
            for payload in source_payloads
        ])
        body_values = _unique_text([payload.get("body") for payload in source_payloads])
        merged_payload = dict(first_payload)
        merged_payload["kind"] = _kind(sources[0])
        merged_payload["name"] = main_name
        merged_payload["title"] = main_name or _as_text(first_payload.get("title"))
        merged_payload["aliases"] = aliases
        if descriptions:
            merged_payload["summary"] = " ".join(descriptions)
        if body_values:
            merged_payload["body"] = "\n\n".join(body_values)
        merged_payload["source_references"] = source_references
        merged_payload["merged_from"] = [source.id for source in sources]
        merged_payload["merge_suggestion_id"] = suggestion.id
        merged_payload["merge_conflicts"] = _as_list(_payload(suggestion).get("conflicting_fields"))
        if type_values:
            key = "branch_type" if _kind(sources[0]) == "branch" else "entity_type"
            merged_payload[key] = type_values[0]
        return ImportCandidate(
            id=_new_id(),
            segment_id=sources[0].segment_id,
            candidate_type=sources[0].candidate_type,
            proposed_data=merged_payload,
            proposed_relations=[
                relation
                for source in sources
                for relation in list(source.proposed_relations or [])
            ],
            confidence=max([source.confidence for source in sources] + [suggestion.confidence]),
            possible_duplicates=_unique_text([
                duplicate
                for source in sources
                for duplicate in source.possible_duplicates
            ]),
            possible_contradictions=_unique_text([
                contradiction
                for source in sources
                for contradiction in source.possible_contradictions
            ]),
            review_state=ImportReviewState.PENDIENTE,
        )

    def _find_candidates(self, basket: ImportBasket, ids: list[str]) -> list[ImportCandidate]:
        wanted = {_as_text(value) for value in ids if _as_text(value)}
        return [
            candidate for candidate in basket.import_candidates
            if candidate.id in wanted and self._is_mergeable(candidate)
        ]

    def _get_candidate(self, basket: ImportBasket, candidate_id: str) -> ImportCandidate | None:
        for candidate in basket.import_candidates:
            if candidate.id == candidate_id:
                return candidate
        return None

    def _suggestion_key(self, suggestion: ImportCandidate) -> tuple[str, ...]:
        payload = _payload(suggestion)
        ids = [
            _as_text(value)
            for value in _as_list(payload.get("affected_candidate_ids"))
            if _as_text(value)
        ]
        return tuple(sorted(ids))

