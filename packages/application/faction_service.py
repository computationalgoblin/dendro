"""FactionService — CRUD, ally/enemy symmetric, front↔clock bidirectional, detection (B22-T03)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.domain.faction_models import Faction, FactionState, Front, FrontState, FrontStage, FrontType
from packages.domain.campaign_models import CampaignClock
from packages.domain.candidate_issue import StructuredIssue, StructuredIssueType, StructuredIssueSeverity
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class FactionService:
    project_service: Any
    entity_service: Any = None
    campaign_service: Any = None
    history_service: Any = None

    def _active_project(self) -> Project:
        return self.project_service.active_project

    # ── Faction CRUD ──────────────────────────────────────────────

    def create_faction(self, data: dict) -> Result[Faction, str]:
        proj = self._active_project()
        entity_id = data.get("entity_id", "")
        if not entity_id or not isinstance(entity_id, str) or not entity_id.strip():
            return Error("entity_id is required")
        if self.entity_service is not None:
            er = self.entity_service.get_by_id(entity_id)
            if isinstance(er, Error): return Error(f"Entity '{entity_id}' not found")
            from packages.domain.entity import EntityType
            if er.value.entity_type != EntityType.FACCION:
                return Error(f"Entity '{entity_id}' is not FACCION")
        for f in proj.factions:
            if f.entity_id == entity_id: return Error(f"Faction with entity_id '{entity_id}' already exists")
        faction = Faction.from_dict(data)
        proj.factions.append(faction)
        if self.history_service:
            self.history_service.record("faction_created", f"Faction '{faction.name}' created", metadata={"object_type":"faction","object_id":faction.id})
        proj.touch()
        return Ok(faction)

    def get_faction(self, fid: str) -> Result[Faction, str]:
        for f in self._active_project().factions:
            if f.id == fid: return Ok(f)
        return Error(f"Faction '{fid}' not found")

    def list_factions(self, state: str | None = None) -> list[Faction]:
        factions = self._active_project().factions
        if state:
            from packages.domain.faction_models import _parse_enum
            target = _parse_enum(FactionState, state, None)
            if target is not None: return [f for f in factions if f.state == target]
        return list(factions)

    def update_faction(self, fid: str, data: dict) -> Result[Faction, str]:
        r = self.get_faction(fid)
        if isinstance(r, Error): return r
        f = r.value
        for field in ("name", "ideology", "methods", "relation_with_pcs", "relation_with_factions", "visibility_state"):
            if field in data: setattr(f, field, data[field])
        for lf in ("objectives", "resources", "possible_reactions", "inaction_consequences", "intervention_consequences"):
            if lf in data and isinstance(data[lf], list): setattr(f, lf, data[lf])
        if "state" in data:
            from packages.domain.faction_models import _parse_enum
            f.state = _parse_enum(FactionState, data["state"], f.state)
        f.updated_at = _ts()
        self._active_project().touch()
        return Ok(f)

    def archive_faction(self, fid: str) -> Result[Faction, str]:
        r = self.get_faction(fid)
        if isinstance(r, Error): return r
        r.value.state = FactionState.inactiva
        r.value.updated_at = _ts()
        if self.history_service:
            self.history_service.record("faction_archived", f"Faction {r.value.name} archived", metadata={"object_type":"faction","object_id":r.value.id})
        self._active_project().touch()
        return Ok(r.value)

    # ── Members / Leaders ─────────────────────────────────────────

    def add_member(self, fid: str, entity_id: str) -> Result[Faction, str]:
        r = self.get_faction(fid)
        if isinstance(r, Error): return r
        f = r.value
        if entity_id not in f.member_entity_ids: f.member_entity_ids.append(entity_id)
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    def remove_member(self, fid: str, entity_id: str) -> Result[Faction, str]:
        r = self.get_faction(fid)
        if isinstance(r, Error): return r
        f = r.value
        if entity_id in f.member_entity_ids: f.member_entity_ids.remove(entity_id)
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    def add_leader(self, fid: str, entity_id: str) -> Result[Faction, str]:
        r = self.get_faction(fid)
        if isinstance(r, Error): return r
        f = r.value
        if entity_id not in f.leader_entity_ids: f.leader_entity_ids.append(entity_id)
        f.updated_at = _ts(); self._active_project().touch()
        if self.history_service:
            self.history_service.record("faction_leader_added", f"Leader {entity_id} added to faction {f.id}", metadata={"object_type":"faction","object_id":f.id})
        return Ok(f)

    def remove_leader(self, fid: str, entity_id: str) -> Result[Faction, str]:
        r = self.get_faction(fid)
        if isinstance(r, Error): return r
        f = r.value
        if entity_id in f.leader_entity_ids: f.leader_entity_ids.remove(entity_id)
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    # ── Allies / Enemies (symmetric) ──────────────────────────────

    def _add_bilateral(self, fid: str, other_id: str, field: str, other_field: str) -> Result[Faction, str]:
        r1 = self.get_faction(fid)
        if isinstance(r1, Error): return r1
        r2 = self.get_faction(other_id)
        if isinstance(r2, Error): return Error(f"Other faction '{other_id}' not found")
        if fid == other_id: return Error("Cannot add self as ally/enemy")
        f1, f2 = r1.value, r2.value
        lst1 = getattr(f1, field)
        lst2 = getattr(f2, other_field)
        if other_id not in lst1: lst1.append(other_id)
        if fid not in lst2: lst2.append(fid)
        f1.updated_at = f2.updated_at = _ts()
        self._active_project().touch()
        return Ok(f1)

    def _remove_bilateral(self, fid: str, other_id: str, field: str, other_field: str) -> Result[Faction, str]:
        r1 = self.get_faction(fid)
        if isinstance(r1, Error): return r1
        r2 = self.get_faction(other_id)
        if isinstance(r2, Error): return r2
        f1, f2 = r1.value, r2.value
        lst1 = getattr(f1, field)
        lst2 = getattr(f2, other_field)
        if other_id in lst1: lst1.remove(other_id)
        if fid in lst2: lst2.remove(fid)
        f1.updated_at = f2.updated_at = _ts()
        self._active_project().touch()
        return Ok(f1)

    def add_ally(self, fid, other_id): return self._add_bilateral(fid, other_id, "ally_faction_ids", "ally_faction_ids")
    def remove_ally(self, fid, other_id): return self._remove_bilateral(fid, other_id, "ally_faction_ids", "ally_faction_ids")
    def add_enemy(self, fid, other_id): return self._add_bilateral(fid, other_id, "enemy_faction_ids", "enemy_faction_ids")
    def remove_enemy(self, fid, other_id): return self._remove_bilateral(fid, other_id, "enemy_faction_ids", "enemy_faction_ids")

    # ── Clocks (bidirectional) ────────────────────────────────────

    def assign_clock_to_faction(self, clock_id: str, faction_id: str) -> Result[CampaignClock, str]:
        fr = self.get_faction(faction_id)
        if isinstance(fr, Error): return fr
        proj = self._active_project()
        clock = None
        for c in proj.campaign_clocks:
            if c.id == clock_id: clock = c; break
        if clock is None: return Error(f"CampaignClock '{clock_id}' not found")
        clock.faction_id = faction_id
        if clock_id not in fr.value.clock_ids: fr.value.clock_ids.append(clock_id)
        clock.updated_at = _ts(); proj.touch()
        return Ok(clock)

    def unassign_clock_from_faction(self, clock_id: str, faction_id: str) -> Result[CampaignClock, str]:
        fr = self.get_faction(faction_id)
        if isinstance(fr, Error): return fr
        proj = self._active_project()
        clock = None
        for c in proj.campaign_clocks:
            if c.id == clock_id: clock = c; break
        if clock is None: return Error(f"CampaignClock '{clock_id}' not found")
        clock.faction_id = None
        if clock_id in fr.value.clock_ids: fr.value.clock_ids.remove(clock_id)
        clock.updated_at = _ts(); proj.touch()
        return Ok(clock)

    def advance_faction_clock(self, clock_id: str, by: int = 1, reason: str = "") -> Result[CampaignClock, str]:
        proj = self._active_project()
        clock = None
        for c in proj.campaign_clocks:
            if c.id == clock_id: clock = c; break
        if clock is None: return Error(f"CampaignClock '{clock_id}' not found")
        if by <= 0: return Error("Advance amount must be positive")
        remaining = clock.max_value - clock.current_value
        if by > remaining: return Error(f"Clock advance exceeds max_value: +{by} > remaining {remaining}")
        clock.current_value += by
        if clock.current_value >= clock.max_value:
            from packages.domain.campaign_models import CampaignClockState
            clock.state = CampaignClockState.completed
        entry = f"[{_ts()}] advanced by {by} (now {clock.current_value}/{clock.max_value})"
        if reason: entry += f" — {reason}"
        clock.history.append(entry)
        clock.updated_at = _ts(); proj.touch()
        return Ok(clock)

    # ── Fronts ────────────────────────────────────────────────────

    def create_front(self, data: dict) -> Result[Front, str]:
        proj = self._active_project()
        if not data.get("name", "").strip(): return Error("Front name is required")
        front = Front.from_dict(data)
        proj.fronts.append(front)
        proj.touch()
        return Ok(front)

    def get_front(self, fid: str) -> Result[Front, str]:
        for f in self._active_project().fronts:
            if f.id == fid: return Ok(f)
        return Error(f"Front '{fid}' not found")

    def list_fronts(self, state: str | None = None) -> list[Front]:
        fronts = self._active_project().fronts
        if state:
            from packages.domain.faction_models import _parse_enum
            target = _parse_enum(FrontState, state, None)
            if target is not None: return [f for f in fronts if f.state == target]
        return list(fronts)

    def update_front(self, fid: str, data: dict) -> Result[Front, str]:
        r = self.get_front(fid)
        if isinstance(r, Error): return r
        f = r.value
        for field in ("name", "description"):
            if field in data: setattr(f, field, data[field])
        if "state" in data:
            from packages.domain.faction_models import _parse_enum
            f.state = _parse_enum(FrontState, data["state"], f.state)
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    def add_stage(self, fid: str, data: dict) -> Result[Front, str]:
        r = self.get_front(fid)
        if isinstance(r, Error): return r
        f = r.value
        stage = FrontStage.from_dict(data)
        if not stage.name.strip(): return Error("Stage name is required")
        f.stages.append(stage)
        f.history.append(f"[{_ts()}] added stage '{stage.name}' (threshold={stage.threshold})")
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    def advance_front(self, fid: str) -> Result[Front, str]:
        r = self.get_front(fid)
        if isinstance(r, Error): return r
        f = r.value
        if not f.stages: return Error("Front has no stages")
        if f.current_stage_index + 1 >= len(f.stages):
            return Error(f"Already at last stage ({f.current_stage_index}/{len(f.stages)-1})")
        f.current_stage_index += 1
        stage = f.stages[f.current_stage_index]
        f.history.append(f"[{_ts()}] advanced to stage '{stage.name}' ({f.current_stage_index}/{len(f.stages)-1})")
        if stage.is_terminal: f.state = FrontState.resuelto
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    def retreat_front(self, fid: str) -> Result[Front, str]:
        r = self.get_front(fid)
        if isinstance(r, Error): return r
        f = r.value
        if f.current_stage_index <= 0: return Error("Already at first stage")
        f.current_stage_index -= 1
        stage = f.stages[f.current_stage_index]
        f.history.append(f"[{_ts()}] retreated to stage '{stage.name}' ({f.current_stage_index}/{len(f.stages)-1})")
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    def link_front_to_clock(self, front_id: str, clock_id: str) -> Result[Front, str]:
        fr = self.get_front(front_id)
        if isinstance(fr, Error): return fr
        proj = self._active_project()
        clock = None
        for c in proj.campaign_clocks:
            if c.id == clock_id: clock = c; break
        if clock is None: return Error(f"CampaignClock '{clock_id}' not found")
        if clock.front_id is not None and clock.front_id != front_id:
            return Error(f"CampaignClock '{clock_id}' already linked to front '{clock.front_id}'")
        f = fr.value
        f.clock_id = clock_id
        clock.front_id = front_id
        f.updated_at = clock.updated_at = _ts()
        proj.touch()
        return Ok(f)

    def unlink_front_from_clock(self, front_id: str) -> Result[Front, str]:
        fr = self.get_front(front_id)
        if isinstance(fr, Error): return fr
        f = fr.value
        if f.clock_id:
            proj = self._active_project()
            for c in proj.campaign_clocks:
                if c.id == f.clock_id: c.front_id = None; break
        f.clock_id = None
        f.updated_at = _ts(); self._active_project().touch()
        return Ok(f)

    # ── Overview ──────────────────────────────────────────────────

    def get_faction_overview(self, faction_id: str) -> Result[dict, str]:
        fr = self.get_faction(faction_id)
        if isinstance(fr, Error): return fr
        f = fr.value
        overview = {"faction": f.to_dict()}
        if self.entity_service is not None:
            es = self.entity_service
            if f.entity_id:
                er = es.get_by_id(f.entity_id)
                if isinstance(er, Ok): overview["entity_name"] = er.value.name
            members = []
            for mid in f.member_entity_ids:
                mr = es.get_by_id(mid)
                members.append({"id": mid, "name": mr.value.name if isinstance(mr, Ok) else mid})
            overview["members"] = members
            leaders = []
            for lid in f.leader_entity_ids:
                lr = es.get_by_id(lid)
                leaders.append({"id": lid, "name": lr.value.name if isinstance(lr, Ok) else lid})
            overview["leaders"] = leaders
        return Ok(overview)

    # ── Detection ─────────────────────────────────────────────────

    def find_factions_without_objectives(self) -> list[Faction]:
        return [f for f in self._active_project().factions if not f.objectives]

    def find_fronts_without_stages(self) -> list[Front]:
        return [f for f in self._active_project().fronts if not f.stages]

    def find_front_clock_mismatch(self) -> list[dict]:
        proj = self._active_project()
        mismatches = []
        for f in proj.fronts:
            if f.clock_id:
                clock = None
                for c in proj.campaign_clocks:
                    if c.id == f.clock_id: clock = c; break
                if clock and clock.front_id != f.id:
                    mismatches.append({"front_id": f.id, "clock_id": f.clock_id, "clock_front_id": clock.front_id})
        return mismatches

    def run_faction_validation(self) -> list[StructuredIssue]:
        issues = []
        for f in self.find_factions_without_objectives():
            if not self._has_open_issue("faction_without_objectives", [f.id]):
                issues.append(StructuredIssue(type=StructuredIssueType.BROKEN_RELATION, severity=StructuredIssueSeverity.MEDIA,
                    description=f"Faction '{f.name}' ({f.id}) has no objectives", affected_entity_ids=[f.id],
                    metadata={"subtype": "faction_without_objectives"}))
        for f in self.find_fronts_without_stages():
            if not self._has_open_issue("front_without_stages", [f.id]):
                issues.append(StructuredIssue(type=StructuredIssueType.NO_DESCRIPTION, severity=StructuredIssueSeverity.MEDIA,
                    description=f"Front '{f.name}' ({f.id}) has no stages", affected_entity_ids=[f.id],
                    metadata={"subtype": "front_without_stages"}))
        for m in self.find_front_clock_mismatch():
            ids = [m["front_id"], m["clock_id"]]
            if not self._has_open_issue("front_clock_mismatch", ids):
                issues.append(StructuredIssue(type=StructuredIssueType.BROKEN_RELATION, severity=StructuredIssueSeverity.MEDIA,
                    description=f"Front '{m['front_id']}' clock '{m['clock_id']}' mismatch (clock→front={m['clock_front_id']})",
                    affected_entity_ids=ids, metadata={"subtype": "front_clock_mismatch"}))
        if issues:
            proj = self._active_project()
            for i in issues: proj.issues.append(i)
        return issues

    def _has_open_issue(self, subtype: str, entity_ids: list[str]) -> bool:
        entity_set = set(entity_ids)
        for issue in self._active_project().issues:
            if issue.state.value == "abierta" and set(issue.affected_entity_ids) == entity_set:
                if issue.metadata.get("subtype") == subtype: return True
        return False
