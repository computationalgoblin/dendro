"""NarrativeContextBuilder — structured context for contextual AI actions.

Application-layer service. It builds read-only dictionaries from the active
project and never mutates canon, candidates, imports or persistence.
"""
from __future__ import annotations

from dataclasses import is_dataclass
from enum import Enum
from typing import Any, Iterable


_GM_AUDIENCES = {"gm", "master", "director", "author", "autor"}
_PLAYER_AUDIENCES = {"player", "jugador", "players", "jugadores"}
_PUBLIC_AUDIENCES = {"public", "publico", "público"}
_SECRET_VISIBILITY_TOKENS = ("privado", "secreto", "no_exportable", "preparado_no_revelado")
_VISIBLE_SECRET_STATES = {"revelado"}
_VISIBLE_CLUE_STATES = {"entregada"}
_PENDING_CANDIDATE_STATES = {"pendiente", "propuesto", "suggested", "sugerido"}


def _value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _string_value(value: Any, default: str = "") -> str:
    value = _value(value)
    return str(value) if value is not None else default


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_obj(obj: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    """Small deterministic serializer for config/domain objects used in context."""
    exclude = exclude or set()
    if obj is None:
        return {}
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
    elif is_dataclass(obj):
        data = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    elif isinstance(obj, dict):
        data = dict(obj)
    else:
        data = {k: v for k, v in getattr(obj, "__dict__", {}).items() if not k.startswith("_")}
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in exclude:
            continue
        if isinstance(value, Enum):
            result[key] = value.value
        elif isinstance(value, list):
            result[key] = [_value(v) for v in value]
        elif isinstance(value, dict):
            result[key] = {str(k): _value(v) for k, v in value.items()}
        else:
            result[key] = _value(value)
    return result


class NarrativeContextBuilder:
    """Build structured, visibility-safe narrative contexts for AI callers."""

    def __init__(self, project_service):
        self.project_service = project_service

    @property
    def project(self):
        return getattr(self.project_service, "active_project", None)

    def build_for_entity(self, entity_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("entity", entity_id, audience=audience)

    def build_for_relation(self, relation_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("relation", relation_id, audience=audience)

    def build_for_session(self, session_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("session", session_id, audience=audience)

    def build_for_scene(self, scene_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("scene", scene_id, audience=audience)

    def build_for_campaign(self, campaign_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("campaign", campaign_id, audience=audience)

    def build_for_faction(self, faction_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("faction", faction_id, audience=audience)

    def build_for_front(self, front_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("front", front_id, audience=audience)

    def build_for_secret(self, secret_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("secret", secret_id, audience=audience)

    def build_for_clue(self, clue_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("clue", clue_id, audience=audience)

    def build_for_writing_unit(self, writing_unit_id: str, *, audience: str = "gm") -> dict[str, Any]:
        return self.build_context("writing_unit", writing_unit_id, audience=audience)

    def build_for_graph_selection(
        self,
        *,
        entity_ids: Iterable[str] | None = None,
        relation_ids: Iterable[str] | None = None,
        audience: str = "gm",
    ) -> dict[str, Any]:
        selected_entity_ids = [str(eid) for eid in (entity_ids or []) if eid]
        selected_relation_ids = [str(rid) for rid in (relation_ids or []) if rid]
        selected_relations = [r for r in self._relations_by_ids(selected_relation_ids) if self._can_include_relation(r, audience)]
        expanded_entity_ids = list(selected_entity_ids)
        for relation in selected_relations:
            for eid in (getattr(relation, "source_id", ""), getattr(relation, "target_id", "")):
                if eid and eid not in expanded_entity_ids:
                    expanded_entity_ids.append(str(eid))
        selected_entities = [e for e in self._entities_by_ids(expanded_entity_ids) if self._can_include_entity(e, audience)]
        selected_set = set(expanded_entity_ids)
        nearby_relations = []
        project_relations = _list(getattr(self.project, "relations", [])) if self.project is not None else []
        for relation in project_relations:
            relation_id = str(getattr(relation, "id", ""))
            if relation_id in selected_relation_ids or not self._can_include_relation(relation, audience):
                continue
            if {str(getattr(relation, "source_id", "")), str(getattr(relation, "target_id", ""))} & selected_set:
                nearby_relations.append(relation)
            if len(nearby_relations) >= 12:
                break
        nearby_entity_ids = []
        for relation in nearby_relations:
            for eid in (getattr(relation, "source_id", ""), getattr(relation, "target_id", "")):
                if eid and eid not in selected_set and eid not in nearby_entity_ids:
                    nearby_entity_ids.append(str(eid))
        nearby_entities = [e for e in self._entities_by_ids(nearby_entity_ids[:12]) if self._can_include_entity(e, audience)]
        return self._base_context("graph_selection", None, audience) | {
            "selection": {
                "entities": [self._entity_summary(e, audience) for e in selected_entities],
                "relations": [self._relation_summary(r, audience) for r in selected_relations],
            },
            "nearby_context": {
                "entities": [self._entity_summary(e, audience) for e in nearby_entities],
                "relations": [self._relation_summary(r, audience) for r in nearby_relations],
            },
        }

    def build_context(self, target_type: str, target_id: str | None = None, *, audience: str = "gm") -> dict[str, Any]:
        context = self._base_context(target_type, target_id, audience)
        context["target"] = self._target_payload(target_type, target_id, audience)
        context["neighborhood"] = self._neighborhood(target_type, target_id, audience)
        context["sessions"] = self._linked_sessions(target_type, target_id, audience)
        context["campaigns"] = self._linked_campaigns(target_type, target_id, audience)
        context["knowledge"] = self._knowledge(target_type, target_id, audience)
        context["sources"] = self._sources(target_type, target_id, audience)
        context["history"] = self._history(target_type, target_id, audience)
        context["candidates"] = self._candidates(target_type, target_id, audience)
        context["issues"] = self._issues(target_type, target_id, audience)
        return context

    def _audience_kind(self, audience: str) -> str:
        key = (audience or "gm").strip().lower()
        if key in _GM_AUDIENCES:
            return "gm"
        if key in _PLAYER_AUDIENCES:
            return "player"
        if key in _PUBLIC_AUDIENCES:
            return "public"
        return key or "gm"

    def _base_context(self, target_type: str, target_id: str | None, audience: str) -> dict[str, Any]:
        project = self.project
        audience_kind = self._audience_kind(audience)
        if project is None:
            return {
                "schema": "narrative_context/v1",
                "target_type": target_type,
                "target_id": target_id,
                "audience": audience_kind,
                "project": None,
                "constraints": self._constraints(audience_kind),
            }
        return {
            "schema": "narrative_context/v1",
            "target_type": target_type,
            "target_id": target_id,
            "audience": audience_kind,
            "project": {
                "id": getattr(project, "id", ""),
                "name": getattr(project, "name", ""),
                "description": getattr(project, "description", ""),
                "primary_language": getattr(project, "primary_language", "es"),
                "tone": _safe_obj(getattr(project, "tone", None)),
                "genre": _safe_obj(getattr(project, "genre", None)),
                "realism": _safe_obj(getattr(project, "realism", None)),
                "general": _safe_obj(getattr(project, "general", None)),
                "world_layers": [self._layer_summary(layer) for layer in _list(getattr(project, "world_layers", []))],
                "domains": list(getattr(project, "domains", []) or []),
            },
            "constraints": self._constraints(audience_kind),
        }

    def _constraints(self, audience: str) -> dict[str, Any]:
        return {
            "ai_may_mutate_canon": False,
            "canon_is_source_of_truth": True,
            "candidates_are_non_canon_until_accepted": True,
            "audience_profile": audience,
            "hide_unrevealed_secrets": audience != "gm",
            "hide_undelivered_clues": audience != "gm",
        }

    def _target_payload(self, target_type: str, target_id: str | None, audience: str) -> dict[str, Any] | None:
        if target_id is None:
            return None
        mapping = {
            "entity": (self._entity_by_id, self._entity_summary, self._can_include_entity),
            "relation": (self._relation_by_id, self._relation_summary, self._can_include_relation),
            "session": (self._session_by_id, self._session_summary, self._can_include_session),
            "campaign": (self._campaign_by_id, self._campaign_summary, lambda obj, aud: True),
            "faction": (self._faction_by_id, self._generic_summary, lambda obj, aud: True),
            "front": (self._front_by_id, self._generic_summary, lambda obj, aud: True),
            "secret": (self._secret_by_id, self._secret_summary, self._can_include_secret),
            "clue": (self._clue_by_id, self._clue_summary, self._can_include_clue),
            "writing_unit": (self._writing_unit_by_id, self._generic_summary, lambda obj, aud: True),
        }
        if target_type == "scene":
            scene = self._scene_by_id(target_id)
            return self._scene_summary(scene, audience) if scene else None
        resolver = mapping.get(target_type)
        if resolver is None:
            return None
        getter, serializer, allowed = resolver
        obj = getter(target_id)
        if obj is None or not allowed(obj, audience):
            return {"redacted": True, "reason": "not_visible_for_audience"}
        return serializer(obj, audience)

    def _entity_summary(self, entity, audience: str) -> dict[str, Any]:
        entity_id = getattr(entity, "id", "")
        # Compute tree membership (which containers this entity belongs to)
        tree_names = []
        if self.project is not None:
            for r in _list(getattr(self.project, "relations", [])):
                rtype = _string_value(getattr(r, "relation_type", ""))
                if rtype == "contiene" and getattr(r, "target_id", "") == entity_id:
                    parent = self._entity_by_id(getattr(r, "source_id", ""))
                    if parent is not None:
                        tree_names.append(getattr(parent, "name", ""))
        return {
            "id": entity_id,
            "name": getattr(entity, "name", ""),
            "type": _string_value(getattr(entity, "entity_type", "")),
            "brief_description": getattr(entity, "brief_description", ""),
            "extended_description": getattr(entity, "extended_description", ""),
            "canon_state": _string_value(getattr(entity, "canon_state", "")),
            "visibility_state": _string_value(getattr(entity, "visibility_state", "")),
            "certainty_level": _string_value(getattr(entity, "certainty_level", "")),
            "tags": list(getattr(entity, "tags", []) or []),
            "domain": getattr(entity, "domain", ""),
            "layers": list(getattr(entity, "layers", []) or []),
            "private_notes": getattr(entity, "private_notes", "") if self._audience_kind(audience) == "gm" else "",
            "exportable_notes": getattr(entity, "exportable_notes", ""),
            "narrative_importance": _string_value(getattr(entity, "narrative_importance", "")),
            "development_level": _string_value(getattr(entity, "development_level", "")),
            "tree_membership": tree_names,
        }

    def _relation_summary(self, relation, audience: str) -> dict[str, Any]:
        source = self._entity_by_id(getattr(relation, "source_id", ""))
        target = self._entity_by_id(getattr(relation, "target_id", ""))
        return {
            "id": getattr(relation, "id", ""),
            "source": self._entity_ref(source),
            "target": self._entity_ref(target),
            "relation_type": _string_value(getattr(relation, "relation_type", "")),
            "direction": _string_value(getattr(relation, "direction", "")),
            "description": getattr(relation, "description", ""),
            "intensity": _string_value(getattr(relation, "intensity", "")),
            "temporality": getattr(relation, "temporality", ""),
            "causality": getattr(relation, "causality", ""),
            "canon_state": _string_value(getattr(relation, "canon_state", "")),
            "visibility_state": _string_value(getattr(relation, "visibility_state", "")),
            "source_note": getattr(relation, "source", "") if self._audience_kind(audience) == "gm" else "",
            "tags": list(getattr(relation, "tags", []) or []),
        }

    def _session_summary(self, session, audience: str) -> dict[str, Any]:
        gm = self._audience_kind(audience) == "gm"
        return {
            "id": getattr(session, "id", ""),
            "name": getattr(session, "name", ""),
            "campaign_id": getattr(session, "campaign_id", ""),
            "session_number": getattr(session, "session_number", 0),
            "state": _string_value(getattr(session, "state", "")),
            "context_summary": getattr(session, "context_summary", ""),
            "player_safe_summary": getattr(session, "player_safe_summary", ""),
            "gm_objectives": list(getattr(session, "gm_objectives", []) or []) if gm else [],
            "player_known_objectives": list(getattr(session, "player_known_objectives", []) or []),
            "planned_scenes": [self._scene_summary(scene, audience) for scene in _list(getattr(session, "planned_scenes", []))],
            "optional_scenes": [self._scene_summary(scene, audience) for scene in _list(getattr(session, "optional_scenes", []))] if gm else [],
            "rumors": list(getattr(session, "rumors", []) or []),
            "open_questions": list(getattr(session, "open_questions", []) or []) if gm else [],
        }

    def _scene_summary(self, scene, audience: str) -> dict[str, Any]:
        return {
            "id": getattr(scene, "id", ""),
            "name": getattr(scene, "name", ""),
            "description": getattr(scene, "description", ""),
            "scene_type": _string_value(getattr(scene, "scene_type", "")),
            "order": getattr(scene, "order", 0),
            "location": self._entity_ref(self._entity_by_id(getattr(scene, "location_id", "") or "")),
            "npcs": [self._entity_ref(e) for e in self._entities_by_ids(getattr(scene, "npc_ids", []) or [])],
            "notes": getattr(scene, "notes", "") if self._audience_kind(audience) == "gm" else "",
        }

    def _campaign_summary(self, campaign, audience: str) -> dict[str, Any]:
        gm = self._audience_kind(audience) == "gm"
        return {
            "id": getattr(campaign, "id", ""),
            "name": getattr(campaign, "name", ""),
            "pitch": getattr(campaign, "pitch", ""),
            "state": _string_value(getattr(campaign, "state", "")),
            "system": getattr(campaign, "system", ""),
            "tone": getattr(campaign, "tone", ""),
            "private_notes": getattr(campaign, "private_notes", "") if gm else "",
            "player_safe_summary": getattr(campaign, "player_safe_summary", ""),
        }

    def _secret_summary(self, secret, audience: str) -> dict[str, Any]:
        return {
            "id": getattr(secret, "id", ""),
            "content": getattr(secret, "content", ""),
            "revelation_state": _string_value(getattr(secret, "revelation_state", "")),
            "importance": getattr(secret, "importance", 0),
            "affected_entities": [self._entity_ref(e) for e in self._entities_by_ids(getattr(secret, "affected_entity_ids", []) or [])],
        }

    def _clue_summary(self, clue, audience: str) -> dict[str, Any]:
        return {
            "id": getattr(clue, "id", ""),
            "content": getattr(clue, "content", ""),
            "delivery_state": _string_value(getattr(clue, "delivery_state", "")),
            "delivery_form": _string_value(getattr(clue, "delivery_form", "")),
            "clarity": getattr(clue, "clarity", 0),
            "associated_secret_id": getattr(clue, "associated_secret_id", None) if self._audience_kind(audience) == "gm" else None,
        }

    def _generic_summary(self, obj, audience: str) -> dict[str, Any]:
        return _safe_obj(obj, exclude={"metadata"})

    def _entity_ref(self, entity) -> dict[str, Any] | None:
        if entity is None:
            return None
        return {
            "id": getattr(entity, "id", ""),
            "name": getattr(entity, "name", ""),
            "type": _string_value(getattr(entity, "entity_type", "")),
        }

    def _layer_summary(self, layer) -> dict[str, Any]:
        return {
            "id": getattr(layer, "id", ""),
            "name": getattr(layer, "name", ""),
            "kind": _string_value(getattr(layer, "kind", "")),
            "active": bool(getattr(layer, "active", True)),
        }

    def _neighborhood(self, target_type: str, target_id: str | None, audience: str) -> dict[str, Any]:
        if target_type != "entity" or not target_id:
            return {"relations": [], "entities": []}
        relations = [r for r in _list(getattr(self.project, "relations", [])) if target_id in {getattr(r, "source_id", ""), getattr(r, "target_id", "")} and self._can_include_relation(r, audience)]
        entity_ids = []
        for relation in relations:
            source_id = getattr(relation, "source_id", "")
            target = getattr(relation, "target_id", "")
            other = target if source_id == target_id else source_id
            if other and other not in entity_ids:
                entity_ids.append(other)
        entities = [e for e in self._entities_by_ids(entity_ids) if self._can_include_entity(e, audience)]
        return {
            "relations": [self._relation_summary(r, audience) for r in relations[:12]],
            "entities": [self._entity_summary(e, audience) for e in entities[:12]],
        }

    def _linked_sessions(self, target_type: str, target_id: str | None, audience: str) -> list[dict[str, Any]]:
        if not target_id:
            return []
        sessions = []
        for session in _list(getattr(self.project, "sessions", [])):
            if target_type == "session" and getattr(session, "id", "") == target_id:
                sessions.append(session)
            elif target_type == "campaign" and getattr(session, "campaign_id", "") == target_id:
                sessions.append(session)
            elif target_type == "entity" and self._session_references_entity(session, target_id):
                sessions.append(session)
            elif target_type == "clue" and target_id in _list(getattr(session, "available_clue_ids", [])):
                sessions.append(session)
            elif target_type == "secret" and target_id in _list(getattr(session, "revealable_secret_ids", [])):
                sessions.append(session)
        return [self._session_summary(s, audience) for s in sessions[:8] if self._can_include_session(s, audience)]

    def _linked_campaigns(self, target_type: str, target_id: str | None, audience: str) -> list[dict[str, Any]]:
        if not target_id:
            return []
        campaigns = []
        for campaign in _list(getattr(self.project, "campaigns", [])):
            if target_type == "campaign" and getattr(campaign, "id", "") == target_id:
                campaigns.append(campaign)
            elif target_type == "entity" and target_id in ({getattr(campaign, "world_entity_id", None)} | set(getattr(campaign, "active_location_entity_ids", []) or [])):
                campaigns.append(campaign)
        return [self._campaign_summary(c, audience) for c in campaigns[:8]]

    def _knowledge(self, target_type: str, target_id: str | None, audience: str) -> dict[str, Any]:
        secrets = [s for s in _list(getattr(self.project, "secrets", [])) if self._knowledge_matches(s, target_type, target_id) and self._can_include_secret(s, audience)]
        clues = [c for c in _list(getattr(self.project, "clues", [])) if self._knowledge_matches(c, target_type, target_id) and self._can_include_clue(c, audience)]
        return {
            "secrets": [self._secret_summary(s, audience) for s in secrets[:8]],
            "clues": [self._clue_summary(c, audience) for c in clues[:8]],
        }

    def _sources(self, target_type: str, target_id: str | None, audience: str) -> list[dict[str, Any]]:
        if self._audience_kind(audience) != "gm" or not target_id:
            return []
        result = []
        for source in _list(getattr(self.project, "sources", [])):
            data = _safe_obj(source)
            ids = set(_list(data.get("linked_entity_ids"))) | set(_list(data.get("entity_ids")))
            if target_id in ids or data.get("id") == target_id:
                result.append(data)
        return result[:8]

    def _history(self, target_type: str, target_id: str | None, audience: str) -> list[dict[str, Any]]:
        if self._audience_kind(audience) != "gm" or not target_id:
            return []
        result = []
        for entry in _list(getattr(self.project, "history", [])):
            data = _safe_obj(entry)
            ids = set(_list(data.get("affected_entity_ids"))) | set(_list(data.get("affected_relation_ids")))
            if target_id in ids:
                result.append(data)
        return result[-8:]

    def _candidates(self, target_type: str, target_id: str | None, audience: str) -> list[dict[str, Any]]:
        if not target_id:
            return []
        result = []
        for candidate in _list(getattr(self.project, "candidates", [])):
            if not self._candidate_matches(candidate, target_type, target_id):
                continue
            state = _string_value(getattr(candidate, "state", ""))
            if state and state not in _PENDING_CANDIDATE_STATES:
                continue
            result.append({
                "id": getattr(candidate, "id", ""),
                "title": getattr(candidate, "title", ""),
                "candidate_type": _string_value(getattr(candidate, "candidate_type", "")),
                "state": state,
                "proposed_data": dict(getattr(candidate, "proposed_data", {}) or {}),
                "confidence": getattr(candidate, "confidence", 0.0),
                "justification": getattr(candidate, "justification", ""),
                "canonical_status": "candidate_non_canon",
                "facts_status": "proposal_only_not_confirmed",
            })
        return result[:8]

    def _issues(self, target_type: str, target_id: str | None, audience: str) -> list[dict[str, Any]]:
        if self._audience_kind(audience) != "gm" or not target_id:
            return []
        result = []
        for issue in _list(getattr(self.project, "issues", [])):
            data = _safe_obj(issue)
            ids = set(_list(data.get("affected_entity_ids"))) | set(_list(data.get("affected_relation_ids")))
            if target_id in ids:
                result.append(data)
        return result[:8]

    def _session_references_entity(self, session, entity_id: str) -> bool:
        if getattr(session, "entity_id", None) == entity_id:
            return True
        refs = set(_list(getattr(session, "planned_location_ids", []))) | set(_list(getattr(session, "planned_npc_ids", [])))
        if entity_id in refs:
            return True
        for scene in _list(getattr(session, "planned_scenes", [])) + _list(getattr(session, "optional_scenes", [])):
            if getattr(scene, "location_id", None) == entity_id or entity_id in _list(getattr(scene, "npc_ids", [])):
                return True
        return False

    def _knowledge_matches(self, obj, target_type: str, target_id: str | None) -> bool:
        if not target_id:
            return False
        if target_type in {"secret", "clue"} and getattr(obj, "id", "") == target_id:
            return True
        if target_type == "entity":
            ids = {getattr(obj, "entity_id", None), getattr(obj, "source_entity_id", None), getattr(obj, "location_entity_id", None), getattr(obj, "associated_npc_entity_id", None)}
            ids |= set(_list(getattr(obj, "affected_entity_ids", [])))
            return target_id in ids
        return False

    def _candidate_matches(self, candidate, target_type: str, target_id: str) -> bool:
        if target_type == "entity":
            return target_id in _list(getattr(candidate, "affected_entity_ids", []))
        if target_type == "relation":
            return target_id in _list(getattr(candidate, "affected_relation_ids", []))
        return getattr(candidate, "source_id", None) == target_id

    def _can_include_entity(self, entity, audience: str) -> bool:
        if self._audience_kind(audience) == "gm":
            return True
        visibility = _string_value(getattr(entity, "visibility_state", "")).lower()
        canon = _string_value(getattr(entity, "canon_state", "")).lower()
        if any(token in visibility for token in _SECRET_VISIBILITY_TOKENS):
            return False
        if canon in {"sugerido_ia", "importado_pendiente", "descartado", "archivado"}:
            return False
        return True

    def _can_include_relation(self, relation, audience: str) -> bool:
        if self._audience_kind(audience) == "gm":
            return True
        visibility = _string_value(getattr(relation, "visibility_state", "")).lower()
        canon = _string_value(getattr(relation, "canon_state", "")).lower()
        if any(token in visibility for token in _SECRET_VISIBILITY_TOKENS):
            return False
        if canon in {"sugerido_ia", "importado_pendiente", "descartado", "archivado"}:
            return False
        source = self._entity_by_id(getattr(relation, "source_id", ""))
        target = self._entity_by_id(getattr(relation, "target_id", ""))
        return (source is None or self._can_include_entity(source, audience)) and (target is None or self._can_include_entity(target, audience))

    def _can_include_secret(self, secret, audience: str) -> bool:
        if self._audience_kind(audience) == "gm":
            return True
        return _string_value(getattr(secret, "revelation_state", "")).lower() in _VISIBLE_SECRET_STATES

    def _can_include_clue(self, clue, audience: str) -> bool:
        if self._audience_kind(audience) == "gm":
            return True
        return _string_value(getattr(clue, "delivery_state", "")).lower() in _VISIBLE_CLUE_STATES

    def _can_include_session(self, session, audience: str) -> bool:
        return self._audience_kind(audience) == "gm" or bool(getattr(session, "player_safe_summary", ""))

    def _entity_by_id(self, entity_id: str):
        for entity in _list(getattr(self.project, "entities", [])):
            if getattr(entity, "id", "") == entity_id:
                return entity
        return None

    def _entities_by_ids(self, entity_ids: Iterable[str]):
        wanted = set(entity_ids)
        return [e for e in _list(getattr(self.project, "entities", [])) if getattr(e, "id", "") in wanted]

    def _relation_by_id(self, relation_id: str):
        for relation in _list(getattr(self.project, "relations", [])):
            if getattr(relation, "id", "") == relation_id:
                return relation
        return None

    def _relations_by_ids(self, relation_ids: Iterable[str]):
        wanted = set(relation_ids)
        return [r for r in _list(getattr(self.project, "relations", [])) if getattr(r, "id", "") in wanted]

    def _session_by_id(self, session_id: str):
        for session in _list(getattr(self.project, "sessions", [])):
            if getattr(session, "id", "") == session_id:
                return session
        return None

    def _scene_by_id(self, scene_id: str):
        for session in _list(getattr(self.project, "sessions", [])):
            for scene in _list(getattr(session, "planned_scenes", [])) + _list(getattr(session, "optional_scenes", [])):
                if getattr(scene, "id", "") == scene_id:
                    return scene
        return None

    def _campaign_by_id(self, campaign_id: str):
        for campaign in _list(getattr(self.project, "campaigns", [])):
            if getattr(campaign, "id", "") == campaign_id:
                return campaign
        return None

    def _faction_by_id(self, faction_id: str):
        for faction in _list(getattr(self.project, "factions", [])):
            if getattr(faction, "id", "") == faction_id:
                return faction
        return None

    def _front_by_id(self, front_id: str):
        for front in _list(getattr(self.project, "fronts", [])):
            if getattr(front, "id", "") == front_id:
                return front
        return None

    def _secret_by_id(self, secret_id: str):
        for secret in _list(getattr(self.project, "secrets", [])):
            if getattr(secret, "id", "") == secret_id:
                return secret
        return None

    def _clue_by_id(self, clue_id: str):
        for clue in _list(getattr(self.project, "clues", [])):
            if getattr(clue, "id", "") == clue_id:
                return clue
        return None

    def _writing_unit_by_id(self, writing_unit_id: str):
        for unit in _list(getattr(self.project, "writing_units", [])):
            if getattr(unit, "id", "") == writing_unit_id:
                return unit
        return None
