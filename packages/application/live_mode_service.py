"""LiveModeService — live direction: queries, notes, provisional entities, deliver/reveal, improvise (B24-T01)."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from packages.domain.result import Error, Ok, Result

class LiveMaterialState(str, Enum):
    borrador = "borrador"
    hipotesis = "hipotesis"
    provisional_de_sesion = "provisional_de_sesion"
    candidato_post_sesion = "candidato_post_sesion"
    canon_inmediato = "canon_inmediato"

def _live_meta_default():
    return {"quick_notes": [], "player_decisions": [], "events": [], "consequences": [],
            "clues_delivered": [], "secrets_revealed": [],
            "provisional_entity_ids": [], "provisional_relation_ids": [], "improvisations": []}

def _ensure_live_meta(session):
    if "live" not in session.metadata or not isinstance(session.metadata.get("live"), dict):
        session.metadata["live"] = _live_meta_default()

@dataclass
class LiveModeService:
    project_service: Any; session_service: Any = None; secrets_service: Any = None
    faction_service: Any = None; entity_service: Any = None; relation_service: Any = None
    orchestrator: Any = None
    history_service: Any = None

    def _proj(self): return self.project_service.active_project
    def _get_session(self, sid):
        if self.session_service: return self.session_service.get_session(sid)
        return Error("SessionService unavailable")

    # ── Activate ──────────────────────────────────────────────────
    def activate_session(self, sid: str) -> Result:
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        from packages.domain.session_models import SessionState
        r.value.state = SessionState.activa
        if self.history_service:
            self.history_service.record("session_activated", f"Session '{r.value.name}' activated for live mode", metadata={"object_type":"session","object_id":r.value.id})
        self._proj().touch()
        return Ok(r.value)

    # ── Queries ───────────────────────────────────────────────────
    def _query_list(self, sid, list_attr):
        r = self._get_session(sid)
        if isinstance(r, Error): return []
        ids = set(getattr(r.value, list_attr, []))
        return [e for e in self._proj().entities if e.id in ids]

    def query_npcs(self, sid): return self._query_list(sid, "planned_npc_ids")
    def query_locations(self, sid): return self._query_list(sid, "planned_location_ids")

    def query_secrets(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return []
        ids = set(r.value.revealable_secret_ids)
        return [s for s in self._proj().secrets if s.id in ids and s.visibility_state != "privado"]

    def query_clues(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return []
        ids = set(r.value.available_clue_ids)
        return [c for c in self._proj().clues if c.id in ids]

    def query_factions(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return []
        ids = set(r.value.relevant_faction_ids)
        return [f for f in self._proj().factions if f.id in ids]

    def query_clocks(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return []
        ids = set(r.value.clock_ids)
        return [c for c in self._proj().campaign_clocks if c.id in ids]

    # ── Notes & Events ────────────────────────────────────────────
    def _append_text(self, sid, text, field):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value; _ensure_live_meta(s)
        s.private_notes.append(f"[live] {text}")
        s.metadata["live"][field].append(text); self._proj().touch()
        return Ok(s)

    def quick_note(self, sid, text): return self._append_text(sid, text, "quick_notes")
    def register_player_decision(self, sid, text): return self._append_text(sid, text, "player_decisions")
    def register_event(self, sid, text): return self._append_text(sid, text, "events")
    def register_consequence(self, sid, text): return self._append_text(sid, text, "consequences")

    # ── Provisional entities/relations ─────────────────────────────
    def create_provisional_entity(self, sid: str, name: str, entity_type: str, force_canon: bool = False):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        from packages.domain.entity import NarrativeEntity, CanonState, VisibilityState, EntityType
        state = CanonState.CANONICO if force_canon else CanonState.BORRADOR
        live_state = LiveMaterialState.canon_inmediato if force_canon else LiveMaterialState.provisional_de_sesion
        try: etype = EntityType(entity_type)
        except ValueError: return Error(f"Invalid entity_type: {entity_type}")
        entity = NarrativeEntity(name=name, entity_type=etype, canon_state=state, visibility_state=VisibilityState.VISIBLE_USUARIO)
        entity.custom_metadata["live_material_state"] = live_state.value
        entity.custom_metadata["session_id"] = sid
        entity.custom_metadata["created_in_live_mode"] = True
        self._proj().entities.append(entity)
        _ensure_live_meta(s); s.metadata["live"]["provisional_entity_ids"].append(entity.id)
        self._proj().touch()
        return Ok(entity)

    def create_provisional_relation(self, sid: str, source_id: str, target_id: str, relation_type: str):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        from packages.domain.relation import NarrativeRelation
        from packages.domain.entity import CanonState, VisibilityState
        rel = NarrativeRelation(source_id=source_id, target_id=target_id, relation_type=relation_type,
                               canon_state=CanonState.BORRADOR, visibility_state=VisibilityState.VISIBLE_USUARIO)
        rel.custom_metadata["live_material_state"] = LiveMaterialState.provisional_de_sesion.value
        rel.custom_metadata["session_id"] = sid
        rel.custom_metadata["created_in_live_mode"] = True
        self._proj().relations.append(rel)
        _ensure_live_meta(s); s.metadata["live"]["provisional_relation_ids"].append(rel.id)
        self._proj().touch()
        return Ok(rel)

    # ── Clue/Secret delivery ──────────────────────────────────────
    def mark_clue_delivered(self, sid: str, cid: str, state: str = "entregada"):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        if self.secrets_service:
            result = self.secrets_service.deliver_clue(cid, state=state)
            if isinstance(result, Error): return result
        _ensure_live_meta(s); s.metadata["live"]["clues_delivered"].append(cid)
        if self.history_service:
            self.history_service.record("clue_delivered_live", f"Clue {cid} delivered during live session {sid}", metadata={"object_type":"pista","object_id":cid,"session_id":sid})
        self._proj().touch()
        return Ok(s)

    def mark_secret_revealed(self, sid: str, sid2: str, state: str):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        if self.secrets_service:
            result = self.secrets_service.reveal_secret(sid2, state)
            if isinstance(result, Error): return result
        _ensure_live_meta(s); s.metadata["live"]["secrets_revealed"].append(sid2)
        if self.history_service:
            self.history_service.record("secret_revealed_live", f"Secret {sid2} revealed during live session {sid}", metadata={"object_type":"secreto","object_id":sid2,"session_id":sid})
        self._proj().touch()
        return Ok(s)

    # ── Continuity ────────────────────────────────────────────────
    def check_continuity(self, sid):
        if self.session_service: return self.session_service.check_continuity(sid)
        return Error("SessionService unavailable")

    # ── Improvise ─────────────────────────────────────────────────
    def improvise(self, sid: str, hint: str = "", save: bool = False):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        name = f"Improvised: {hint[:40]}" if hint else "Improvised element"
        desc = f"Quick improvisation for session {sid}"
        comp = "Raise the stakes"
        cons = "Unexpected outcome"
        if self.orchestrator:
            try:
                ctx = f"Session: {s.name}. Hint: {hint}"
                resp = self.orchestrator.improvise(ctx)
                if isinstance(resp, dict):
                    name = resp.get("name", name)
                    desc = resp.get("description", desc)
                    comp = resp.get("complication", comp)
                    cons = resp.get("consequence", cons)
            except Exception: pass
        result = {"name": name, "description": desc, "complication": comp, "consequence": cons}
        if save:
            _ensure_live_meta(s); s.metadata["live"]["improvisations"].append(result); self._proj().touch()
        return Ok(result)

    # ── Post-session ──────────────────────────────────────────────
    def prepare_post_session(self, sid: str) -> Result[dict, str]:
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value; _ensure_live_meta(s)
        return Ok(dict(s.metadata.get("live", _live_meta_default())))
