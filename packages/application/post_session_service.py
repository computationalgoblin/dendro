"""PostSessionService — converts live metadata to reviewable Candidates (B25-T01). Idempotent. No auto-canon."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from packages.domain.result import Error, Ok, Result

def _ts(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass
class PostSessionService:
    project_service: Any; session_service: Any = None; candidate_service: Any = None
    history_service: Any = None; entity_service: Any = None

    def _proj(self): return self.project_service.active_project
    def _get_session(self, sid):
        if self.session_service: return self.session_service.get_session(sid)
        return Error("SessionService unavailable")

    def close_session(self, sid: str) -> Result:
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        from packages.domain.session_models import SessionState
        s.state = SessionState.completada
        summary = {"closed_at": _ts(), "summary": f"Session '{s.name}' completed", "candidates_generated": 0, "candidates_accepted": 0, "candidates_rejected": 0, "issues_detected": 0, "source_id": None}
        s.metadata["post_session"] = summary
        s.post_session_summary = summary["summary"]
        if self.history_service:
            self.history_service.record("session_closed", f"Session '{s.name}' closed", metadata={"object_type": "session", "object_id": s.id})
        self._proj().touch()
        return Ok(s)

    def convert_live_to_candidates(self, sid: str) -> Result[list, str]:
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        live = s.metadata.get("live", {})
        existing_keys = self._existing_live_keys(sid)
        candidates = []
        proj = self._proj()

        for idx, text in enumerate(live.get("quick_notes", [])):
            key = f"quick_notes:{idx}"
            if key not in existing_keys:
                c = self._create_candidate("NOTA", {"text": text}, sid, key, f"Quick note: {text[:60]}")
                if c: candidates.append(c)

        for idx, text in enumerate(live.get("player_decisions", [])):
            key = f"player_decisions:{idx}"
            if key not in existing_keys:
                c = self._create_candidate("NOTA", {"text": text, "type": "decision"}, sid, key, f"Decision: {text[:60]}")
                if c: candidates.append(c)

        for idx, text in enumerate(live.get("events", [])):
            key = f"events:{idx}"
            if key not in existing_keys:
                c = self._create_candidate("NOTA", {"text": text, "type": "event"}, sid, key, f"Event: {text[:60]}")
                if c: candidates.append(c)

        for idx, text in enumerate(live.get("consequences", [])):
            key = f"consequences:{idx}"
            if key not in existing_keys:
                c = self._create_candidate("NOTA", {"text": text, "type": "consequence"}, sid, key, f"Consequence: {text[:60]}")
                if c: candidates.append(c)

        for imp in live.get("improvisations", []):
            idx = imp.get("name", "imp")[:30]
            key = f"improvisations:{idx}"
            if key not in existing_keys:
                c = self._create_candidate("SUGERENCIA_IA", imp, sid, key, f"Improvisation: {imp.get('name','')}")
                if c: candidates.append(c)

        # Provisional entities → CAMBIO_ESTADO
        for eid in live.get("provisional_entity_ids", []):
            key = f"provisional_entity:{eid}"
            if key not in existing_keys:
                entity = None
                for e in proj.entities:
                    if e.id == eid: entity = e; break
                if entity and entity.canon_state.value == "borrador":
                    c = self._create_candidate("CAMBIO_ESTADO", {"target_entity_id": eid, "from_canon_state": "borrador", "to_canon_state": "canonico", "entity_name": entity.name}, sid, key, f"Canonize entity '{entity.name}'")
                    if c: candidates.append(c)

        # Provisional relations → CAMBIO_ESTADO
        for rid in live.get("provisional_relation_ids", []):
            key = f"provisional_relation:{rid}"
            if key not in existing_keys:
                rel = None
                for r_ in proj.relations:
                    if r_.id == rid: rel = r_; break
                if rel and rel.canon_state.value == "borrador":
                    c = self._create_candidate("CAMBIO_ESTADO", {"target_relation_id": rid, "from_canon_state": "borrador", "to_canon_state": "canonico"}, sid, key, f"Canonize relation {rid}")
                    if c: candidates.append(c)

        # clue_delivered + secret_revealed → evidence, NOT candidates (already mutated in B24)
        if self.history_service:
            for cid in live.get("clues_delivered", []):
                self.history_service.record("clue_delivered_post", f"Clue {cid} delivered (confirmed post-session)", metadata={"object_type": "pista", "object_id": cid, "session_id": sid})
            for sid2 in live.get("secrets_revealed", []):
                self.history_service.record("secret_revealed_post", f"Secret {sid2} revealed (confirmed post-session)", metadata={"object_type": "secreto", "object_id": sid2, "session_id": sid})

        if self.history_service and candidates:
            self.history_service.record("post_session_candidates", f"Generated {len(candidates)} candidates for session {sid}", metadata={"object_type": "session", "object_id": sid})

        if self.candidate_service:
            for c in candidates:
                self.candidate_service.add_candidate(c)
                self._proj().candidates.append(c)
        self._proj().touch()
        return Ok(candidates)

    def _existing_live_keys(self, sid):
        keys = set()
        for c in self._proj().candidates:
            if c.metadata.get("session_id") == sid:
                key = c.metadata.get("source_live_key")
                if key: keys.add(key)
        return keys

    def _create_candidate(self, ctype, data, sid, key, title):
        try:
            from packages.domain.candidate_issue import Candidate, CandidateType, CandidateState
            ctype_map = {"NOTA": CandidateType.ENTIDAD, "SUGERENCIA_IA": CandidateType.SUGERENCIA_IA, "CAMBIO_ESTADO": CandidateType.ENTIDAD}
            ct = ctype_map.get(ctype, CandidateType.ENTIDAD)
            return Candidate(candidate_type=ct, title=title, proposed_data=data,
                           metadata={"session_id": sid, "source_live_key": key, "post_session_candidate": True})
        except Exception:
            return None

    def generate_private_summary(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value; live = s.metadata.get("live", {})
        parts = [f"Session: {s.name}", f"Notes: {len(live.get('quick_notes',[]))}", f"Decisions: {len(live.get('player_decisions',[]))}",
                 f"Events: {len(live.get('events',[]))}", f"Consequences: {len(live.get('consequences',[]))}",
                 f"Clues delivered: {len(live.get('clues_delivered',[]))}", f"Secrets revealed: {len(live.get('secrets_revealed',[]))}",
                 f"Provisional entities: {len(live.get('provisional_entity_ids',[]))}", f"Relations: {len(live.get('provisional_relation_ids',[]))}"]
        return Ok("\n".join(parts))

    def generate_public_summary(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value; live = s.metadata.get("live", {})
        parts = [s.player_safe_summary or f"Session: {s.name}", f"Events: {len(live.get('events',[]))}", f"Rumors: {', '.join(s.rumors) if s.rumors else '(none)'}"]
        return Ok("\n".join(parts))

    def create_session_source(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return r
        s = r.value
        try:
            from packages.domain.source import Source, SourceType
            st = SourceType.SESION if hasattr(SourceType, 'SESION') else SourceType.NOTA_SESION
        except Exception:
            st = "sesion"
        src = type('Source', (), {"id": f"src_ses_{sid[:8]}", "source_type": st, "title": f"Session: {s.name}", "content": s.post_session_summary or s.name, "metadata": {"session_id": sid}})()
        s.source_id = src.id
        if "post_session" in s.metadata: s.metadata["post_session"]["source_id"] = src.id
        self._proj().touch()
        return Ok(src)

    def generate_session_issues(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return []
        linked = set(r.value.available_clue_ids + r.value.revealable_secret_ids + r.value.relevant_faction_ids + r.value.clock_ids)
        return [i for i in self._proj().issues if i.state.value == "abierta" and set(i.affected_entity_ids) & linked]

    def generate_next_session_seeds(self, sid):
        r = self._get_session(sid)
        if isinstance(r, Error): return []
        s = r.value; live = s.metadata.get("live", {})
        seeds = [f"Follow up on event: {e[:40]}" for e in live.get("events", [])[:3]]
        seeds += [f"Resolve consequence: {c[:40]}" for c in live.get("consequences", [])[:3]]
        seeds += [f"Continue from improvisation: {i.get('name','?')[:40]}" for i in live.get("improvisations", [])[:2]]
        return seeds or ["No seeds generated"]
