"""ExportService — controlled export by audience (gm/player/public). No leak of private info. B26-T01."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from packages.domain.result import Error, Ok, Result

@dataclass
class ExportService:
    project_service: Any; entity_service: Any = None; session_service: Any = None
    secrets_service: Any = None

    def _proj(self): return self.project_service.active_project

    def _filter_entities(self, audience):
        entities = self._proj().entities
        if audience == "public": return [e for e in entities if e.visibility_state.value == "publico_mundo"]
        if audience == "player": return [e for e in entities if e.visibility_state.value not in ("privado_autor", "secreto_mundo")]
        return entities  # gm: all

    def export_public_summary(self, audience="public"):
        entities = self._filter_entities(audience)
        parts = []
        for e in entities:
            parts.append(f"{e.entity_type.value}: {e.name} — {e.brief_description or '(no desc)'}"[:120])
        if audience == "gm":
            parts.append(f"\n[GM ONLY] Secrets: {len(self._proj().secrets)}, Clues: {len(self._proj().clues)}")
            parts.append(f"[GM ONLY] Factions: {len(self._proj().factions)}, Campaigns: {len(self._proj().campaigns)}")
        return Ok("\n".join(parts))

    def export_session_player_summary(self, session_id):
        if self.session_service:
            r = self.session_service.get_session(session_id)
            if isinstance(r, Ok): return Ok(r.value.player_safe_summary or f"Session: {r.value.name}")
        return Error("Session not found")

    def export_campaign_report(self, campaign_id, audience="gm"):
        proj = self._proj()
        camp = None
        for c in proj.campaigns:
            if c.id == campaign_id: camp = c; break
        if camp is None: return Error("Campaign not found")
        parts = [f"Campaign: {camp.name}", f"System: {camp.game_system}", f"Tone: {camp.tone}", f"State: {camp.state.value}"]
        if audience == "gm": parts.append(f"GM Notes: {'; '.join(camp.private_notes) if camp.private_notes else '(none)'}")
        return Ok("\n".join(parts))

    def export_entity_profile(self, entity_id, audience="gm"):
        entity = None
        for e in self._proj().entities:
            if e.id == entity_id: entity = e; break
        if entity is None: return Error("Entity not found")
        if audience == "public" and entity.visibility_state.value != "publico_mundo": return Error("Entity not visible to public")
        parts = [f"{entity.entity_type.value}: {entity.name}", f"Description: {entity.brief_description}"]
        if audience == "gm": parts.append(f"Notes: {entity.private_notes or '(none)'}")
        return Ok("\n".join(parts))

    def export_relation_profile(self, rel_id, audience="gm"):
        for r in self._proj().relations:
            if r.id == rel_id: return Ok(f"Relation: {r.source_id} → {r.target_id} ({r.relation_type.value})")
        return Error("Relation not found")

    def export_all(self, audience="gm"):
        entities = self._filter_entities(audience)
        data = {"total_entities": len(entities), "entities": [{"id": e.id, "name": e.name, "type": e.entity_type.value} for e in entities], "total_relations": len(self._proj().relations)}
        if audience in ("gm", "player"):
            data["total_secrets"] = len(self._proj().secrets)
            data["total_clues"] = len(self._proj().clues)
            data["total_sessions"] = len(self._proj().sessions)
        return Ok(data)
