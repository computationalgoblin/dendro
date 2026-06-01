"""SessionService — CRUD, duplicate, scenes, links, summaries, continuity, IA (B23-T03)."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from packages.domain.session_models import Session, SessionScene, SessionState, SceneType
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result

def _ts(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass
class SessionService:
    project_service: Any
    entity_service: Any = None
    campaign_service: Any = None
    orchestrator: Any = None
    history_service: Any = None

    def _active_project(self) -> Project: return self.project_service.active_project

    # ── CRUD ──────────────────────────────────────────────────────

    def create_session(self, data: dict) -> Result[Session, str]:
        proj = self._active_project()
        cid = data.get("campaign_id", "")
        if not cid or not isinstance(cid, str) or not cid.strip(): return Error("campaign_id is required")
        if self.campaign_service is not None:
            cr = self.campaign_service.get_campaign(cid)
            if isinstance(cr, Error): return Error(f"Campaign '{cid}' not found")
        eid = data.get("entity_id")
        if eid and self.entity_service is not None:
            er = self.entity_service.get_by_id(eid)
            if isinstance(er, Error): return Error(f"Entity '{eid}' not found")
            from packages.domain.entity import EntityType
            if er.value.entity_type != EntityType.SESION: return Error(f"Entity '{eid}' is not SESION")
        session = Session.from_dict(data)
        proj.sessions.append(session)
        if self.history_service:
            self.history_service.record("session_created", f"Session '{session.name}' created", metadata={"object_type":"session","object_id":session.id})
        if self.campaign_service is not None:
            cr = self.campaign_service.get_campaign(cid)
            if isinstance(cr, Ok):
                camp = cr.value
                if session.id not in camp.session_ids: camp.session_ids.append(session.id)
        proj.touch()
        return Ok(session)

    def get_session(self, sid: str) -> Result[Session, str]:
        for s in self._active_project().sessions:
            if s.id == sid: return Ok(s)
        return Error(f"Session '{sid}' not found")

    def list_sessions(self, campaign_id: str | None = None, state: str | None = None) -> list[Session]:
        sessions = self._active_project().sessions
        if campaign_id: sessions = [s for s in sessions if s.campaign_id == campaign_id]
        if state:
            from packages.domain.session_models import _parse_enum
            t = _parse_enum(SessionState, state, None)
            if t is not None: sessions = [s for s in sessions if s.state == t]
        return sessions

    def update_session(self, sid: str, data: dict) -> Result[Session, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        editable_fields = {
            "name", "campaign_id", "entity_id", "session_number", "real_date",
            "internal_date", "context_summary", "gm_objectives",
            "player_known_objectives", "planned_scenes", "optional_scenes",
            "planned_location_ids", "planned_npc_ids", "relevant_faction_ids",
            "active_conflict_ids", "available_clue_ids", "revealable_secret_ids",
            "clock_ids", "rumors", "encounters", "rewards", "complications",
            "expected_consequences", "open_questions", "improvised_material",
            "private_notes", "player_safe_summary", "continuity_checklist",
            "ia_suggestion_candidate_ids", "state", "post_session_summary",
            "source_id", "metadata",
        }
        merged = s.to_dict()
        for f in editable_fields:
            if f in data:
                merged[f] = data[f]
        updated = Session.from_dict(merged)
        for f in editable_fields:
            setattr(s, f, getattr(updated, f))
        s.updated_at = _ts(); self._active_project().touch()
        return Ok(s)

    # ── Duplicate ─────────────────────────────────────────────────

    def duplicate_session(self, sid: str, new_name: str | None = None) -> Result[Session, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        orig = r.value
        new = Session(name=new_name or f"{orig.name} (copia)", campaign_id=orig.campaign_id, session_number=orig.session_number,
                      real_date=orig.real_date, internal_date=orig.internal_date,
                      context_summary=orig.context_summary, gm_objectives=list(orig.gm_objectives),
                      player_known_objectives=list(orig.player_known_objectives),
                      planned_scenes=[SessionScene.from_dict(s.to_dict()) for s in orig.planned_scenes],
                      optional_scenes=[SessionScene.from_dict(s.to_dict()) for s in orig.optional_scenes],
                      rumors=list(orig.rumors), encounters=list(orig.encounters), rewards=list(orig.rewards),
                      complications=list(orig.complications), expected_consequences=list(orig.expected_consequences),
                      open_questions=list(orig.open_questions), continuity_checklist=list(orig.continuity_checklist))
        for sc in new.planned_scenes + new.optional_scenes:
            sc.id = f"scn_{__import__('uuid').uuid4().hex[:6]}"
        self._active_project().sessions.append(new)
        self._active_project().touch()
        return Ok(new)

    # ── Scenes ────────────────────────────────────────────────────

    def add_scene(self, sid: str, data: dict, target: str = "planned") -> Result[SessionScene, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        scene = SessionScene.from_dict(data)
        if target == "optional": r.value.optional_scenes.append(scene)
        else: r.value.planned_scenes.append(scene)
        r.value.updated_at = _ts(); self._active_project().touch()
        return Ok(scene)

    def remove_scene(self, sid: str, scene_id: str, target: str = "planned") -> Result[Session, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        lst = r.value.optional_scenes if target == "optional" else r.value.planned_scenes
        for i, sc in enumerate(lst):
            if sc.id == scene_id: lst.pop(i); r.value.updated_at = _ts(); self._active_project().touch(); return Ok(r.value)
        return Error(f"Scene '{scene_id}' not found")

    def reorder_scene(self, sid: str, scene_id: str, new_order: int, target: str = "planned") -> Result[Session, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        lst = r.value.optional_scenes if target == "optional" else r.value.planned_scenes
        for sc in lst:
            if sc.id == scene_id: sc.order = new_order; r.value.updated_at = _ts(); self._active_project().touch(); return Ok(r.value)
        return Error(f"Scene '{scene_id}' not found")

    # ── Links ─────────────────────────────────────────────────────

    def _link_ids(self, sid, entity_id, list_attr):
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        lst = getattr(r.value, list_attr)
        if entity_id not in lst: lst.append(entity_id)
        r.value.updated_at = _ts(); self._active_project().touch()
        return Ok(r.value)

    def link_entity(self, sid, eid, role):
        if role == "location": return self._link_ids(sid, eid, "planned_location_ids")
        if role == "npc": return self._link_ids(sid, eid, "planned_npc_ids")
        if role == "conflict": return self._link_ids(sid, eid, "active_conflict_ids")
        return Error(f"Invalid role '{role}'. Valid: location, npc, conflict")

    def link_clue(self, sid, cid):
        proj = self._active_project()
        if not any(c.id == cid for c in proj.clues): return Error(f"Clue '{cid}' not found")
        return self._link_ids(sid, cid, "available_clue_ids")

    def link_secret(self, sid, sid2):
        proj = self._active_project()
        if not any(s.id == sid2 for s in proj.secrets): return Error(f"Secret '{sid2}' not found")
        return self._link_ids(sid, sid2, "revealable_secret_ids")

    def link_faction(self, sid, fid):
        proj = self._active_project()
        if not any(f.id == fid for f in proj.factions): return Error(f"Faction '{fid}' not found")
        return self._link_ids(sid, fid, "relevant_faction_ids")

    def link_clock(self, sid, cid):
        proj = self._active_project()
        if not any(c.id == cid for c in proj.campaign_clocks): return Error(f"CampaignClock '{cid}' not found")
        return self._link_ids(sid, cid, "clock_ids")

    # ── Summaries ─────────────────────────────────────────────────

    def generate_private_summary(self, sid: str) -> Result[str, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        parts = [f"Session: {s.name} (#{s.session_number})", f"State: {s.state.value}",
                 f"GM Objectives: {', '.join(s.gm_objectives) if s.gm_objectives else '(none)'}",
                 f"Private Notes: {', '.join(s.private_notes) if s.private_notes else '(none)'}",
                 f"Revealable Secrets: {len(s.revealable_secret_ids)}", f"Continuity: {len(s.continuity_checklist)} items"]
        return Ok("\n".join(parts))

    def generate_player_summary(self, sid: str) -> Result[str, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        parts = [s.player_safe_summary or "(no summary)", f"Objectives: {', '.join(s.player_known_objectives) if s.player_known_objectives else '(none)'}",
                 f"Planned scenes: {len(s.planned_scenes)}", f"Optional scenes: {len(s.optional_scenes)}",
                 f"Rumors: {', '.join(s.rumors) if s.rumors else '(none)'}"]
        return Ok("\n".join(parts))

    # ── Continuity & Issues ───────────────────────────────────────

    def check_continuity(self, sid: str) -> Result[dict, str]:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        s = r.value; proj = self._active_project()
        pending_clues = [c.id for c in proj.clues if c.delivery_state.value == "pendiente"]
        hidden_secrets = [sec.id for sec in proj.secrets if sec.revelation_state.value == "oculto"]
        active_clocks = [c.id for c in proj.campaign_clocks if c.state.value == "active"]
        active_factions = [f.id for f in proj.factions if f.state.value == "activa"]
        return Ok({"pendientes_pistas": len(pending_clues), "secretos_ocultos": len(hidden_secrets),
                   "relojes_activos": len(active_clocks), "facciones_activas": len(active_factions),
                   "session_clock_ids": s.clock_ids, "session_faction_ids": s.relevant_faction_ids})

    def get_relevant_issues(self, sid: str) -> list:
        r = self.get_session(sid)
        if isinstance(r, Error): return []
        s = r.value; proj = self._active_project()
        linked = set(s.available_clue_ids + s.revealable_secret_ids + s.relevant_faction_ids + s.clock_ids +
                     s.planned_location_ids + s.planned_npc_ids + s.active_conflict_ids)
        return [i for i in proj.issues if i.state.value == "abierta" and set(i.affected_entity_ids) & linked]

        # ── IA ────────────────────────────────────────────────────────

    def suggest_material(self, sid: str, hint: str = "", audience: str = "author") -> Result:
        r = self.get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        if self.orchestrator is not None:
            from packages.domain.candidate_issue import Candidate, CandidateType
            cand = Candidate(candidate_type=CandidateType.SUGERENCIA_IA, title=f"Session suggestion: {s.name}",
                           proposed_data={"hint": hint, "session_name": s.name, "audience": audience},
                           source="ia", confidence=0.7,
                           metadata={"ai_mode": "session_suggest", "session_id": sid})
            return Ok(cand)
        return Error("OrchestratorService not available")
