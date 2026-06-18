"""WritingService — CRUD, hierarchy, linking, coverage, IA assistance, issues (B19-T02)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4
from typing import Any

from packages.domain.candidate_issue import Candidate, CandidateType, StructuredIssue
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result
from packages.domain.writing_models import WritingUnit, WritingUnitType, RevisionState
from packages.domain.temporal_models import TimelineEvent


@dataclass
class WritingService:
    project_service: Any  # ProjectService
    entity_service: Any = None  # EntityService (optional)
    source_service: Any = None  # SourceService (optional)
    orchestrator: Any = None   # OrchestratorService (optional)

    # ── CRUD ───────────────────────────────────────────────────────

    def create_unit(self, data: dict) -> Result[WritingUnit, str]:
        proj = self._active_project()
        if not data.get("id"):
            data["id"] = str(uuid4())
        # Validate parent
        pid = data.get("parent_id")
        if pid:
            existing = [u for u in proj.writing_units if u.id == pid]
            if not existing:
                return Error(f"parent_id '{pid}' does not exist")
        unit = WritingUnit.from_dict(data)
        proj.writing_units.append(unit)
        proj.touch()
        return Ok(unit)

    def get_unit(self, unit_id: str) -> Result[WritingUnit, str]:
        proj = self._active_project()
        for u in proj.writing_units:
            if u.id == unit_id:
                return Ok(u)
        return Error(f"WritingUnit '{unit_id}' not found")

    def list_units(self, filters: dict | None = None) -> list[WritingUnit]:
        proj = self._active_project()
        units = proj.writing_units
        f = filters or {}
        # Default: exclude archived
        include_archived = f.get("include_archived", False)
        if not include_archived:
            units = [u for u in units if u.revision_state != RevisionState.ARCHIVADO]
        for key in ("unit_type", "parent_id", "revision_state"):
            if key in f and f[key] is not None:
                val = f[key]
                if hasattr(val, "value"):
                    val = val.value
                units = [u for u in units if getattr(u, key) == val]
        if "entity_id" in f and f["entity_id"]:
            eid = f["entity_id"]
            units = [u for u in units if eid in u.entity_ids]
        if "tag" in f and f["tag"]:
            tag = f["tag"]
            units = [u for u in units if tag in u.tags]
        if "domain_id" in f and f["domain_id"]:
            did = f["domain_id"]
            units = [u for u in units if did in u.domain_ids]
        if "layer_id" in f and f["layer_id"]:
            lid = f["layer_id"]
            units = [u for u in units if lid in u.layer_ids]
        if "framework_id" in f and f["framework_id"]:
            fid = f["framework_id"]
            units = [u for u in units if fid in u.framework_ids]
        return units

    def update_unit(self, unit_id: str, data: dict) -> Result[WritingUnit, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        unit = r.value
        # Never change parent_id via update
        data.pop("parent_id", None)
        for key in ("name", "content", "summary", "author_notes",
                     "canon_state", "visibility_state"):
            if key in data and data[key] is not None:
                setattr(unit, key, data[key])
        if "revision_state" in data and data["revision_state"] is not None:
            from packages.domain.writing_models import RevisionState as RS
            rs_val = data["revision_state"]
            if hasattr(rs_val, "value"):
                rs_val = rs_val.value
            try:
                unit.revision_state = RS(rs_val)
            except ValueError:
                return Error(f"Invalid revision_state: {rs_val}")
        unit.touch()
        proj = self._active_project()
        proj.touch()
        return Ok(unit)

    def archive_unit(self, unit_id: str) -> Result[WritingUnit, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        unit = r.value
        unit.revision_state = RevisionState.ARCHIVADO
        unit.touch()
        proj = self._active_project()
        proj.touch()
        return Ok(unit)

    # ── Hierarchy ──────────────────────────────────────────────────

    def reorder_unit(self, unit_id: str, new_order: int) -> Result[WritingUnit, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        r.value.order = new_order
        r.value.touch()
        self._active_project().touch()
        return Ok(r.value)

    def reparent_unit(self, unit_id: str, new_parent_id: str | None) -> Result[WritingUnit, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        unit = r.value
        if new_parent_id is not None:
            # Validate parent exists
            pr = self.get_unit(new_parent_id)
            if isinstance(pr, Error):
                return Error(f"parent_id '{new_parent_id}' does not exist")
            # Cycle detection: new parent must not be a descendant of this unit
            if self._is_descendant(unit_id, new_parent_id):
                return Error(f"Cannot reparent: '{new_parent_id}' is a descendant of '{unit_id}'")
        unit.parent_id = new_parent_id
        unit.touch()
        self._active_project().touch()
        return Ok(unit)

    def get_tree(self, root_id: str) -> dict:
        """Return nested dict {unit, children: [...]}."""
        r = self.get_unit(root_id)
        if isinstance(r, Error):
            return {}
        root = r.value
        children = [u for u in self._active_project().writing_units
                    if u.parent_id == root_id]
        return {
            "unit": root,
            "children": [self.get_tree(c.id) for c in children],
        }

    def _is_descendant(self, ancestor_id: str, target_id: str) -> bool:
        """Check if target_id is a descendant of ancestor_id."""
        proj = self._active_project()
        current = target_id
        visited = set()
        while current is not None:
            if current in visited:
                return False
            visited.add(current)
            found = None
            for u in proj.writing_units:
                if u.id == current:
                    found = u
                    break
            if found is None or found.parent_id is None:
                return False
            if found.parent_id == ancestor_id:
                return True
            current = found.parent_id
        return False

    # ── Entity linking ─────────────────────────────────────────────

    def link_entity(self, unit_id: str, entity_id: str) -> Result[WritingUnit, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        unit = r.value
        if self.entity_service:
            er = self.entity_service.get_by_id(entity_id)
            if isinstance(er, Error):
                return Error(f"entity_id '{entity_id}' does not exist")
        if entity_id not in unit.entity_ids:
            unit.entity_ids = list(unit.entity_ids) + [entity_id]
            unit.touch()
            self._active_project().touch()
        return Ok(unit)

    def unlink_entity(self, unit_id: str, entity_id: str) -> Result[WritingUnit, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        unit = r.value
        unit.entity_ids = [e for e in unit.entity_ids if e != entity_id]
        unit.touch()
        self._active_project().touch()
        return Ok(unit)

    def get_linked_entities(self, unit_id: str) -> list:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return []
        unit = r.value
        if not self.entity_service:
            return []
        result = []
        for eid in unit.entity_ids:
            er = self.entity_service.get_by_id(eid)
            if not isinstance(er, Error):
                result.append(er.value)
        return result

    def get_entity_coverage(self, entity_id: str) -> list[WritingUnit]:
        proj = self._active_project()
        return [u for u in proj.writing_units
                if entity_id in u.entity_ids
                and u.revision_state != RevisionState.ARCHIVADO]

    def get_unlinked_entities(self) -> list:
        if not self.entity_service:
            return []
        proj = self._active_project()
        all_entities = getattr(proj, "entities", [])
        linked_ids = set()
        for u in proj.writing_units:
            if u.revision_state != RevisionState.ARCHIVADO:
                linked_ids.update(u.entity_ids)
        return [e for e in all_entities if e.id not in linked_ids]

    def get_coverage_summary(self) -> dict:
        proj = self._active_project()
        all_entities = getattr(proj, "entities", [])
        linked_ids = set()
        for u in proj.writing_units:
            if u.revision_state != RevisionState.ARCHIVADO:
                linked_ids.update(u.entity_ids)
        total = len(all_entities)
        covered = sum(1 for e in all_entities if e.id in linked_ids)
        uncovered = total - covered
        by_type = {}
        for e in all_entities:
            if e.id not in linked_ids:
                et = e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type)
                by_type[et] = by_type.get(et, 0) + 1
        return {
            "total": total,
            "covered": covered,
            "uncovered": uncovered,
            "by_type": by_type,
        }

    # ── IA assistance ──────────────────────────────────────────────

    def expand_unit(self, unit_id: str, hint: str = "") -> Result[Candidate, str]:
        return self._ia_assist(unit_id, "writing_expand", hint)

    def summarize_unit(self, unit_id: str) -> Result[str, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        if not self.orchestrator:
            return Ok(f"[Simulated] Summary of '{r.value.name}': {r.value.content[:200]}...")
        resp_r = self.orchestrator.invoke("summarize", unit_id, "")
        if isinstance(resp_r, Error):
            return resp_r
        return Ok(resp_r.value.raw_text)

    def critique_unit(self, unit_id: str) -> Result[Candidate, str]:
        return self._ia_assist(unit_id, "writing_critique")

    def rewrite_unit(self, unit_id: str, style: str = "") -> Result[Candidate, str]:
        return self._ia_assist(unit_id, "writing_rewrite", style)

    def _ia_assist(self, unit_id: str, ai_mode: str, hint: str = "") -> Result[Candidate, str]:
        r = self.get_unit(unit_id)
        if isinstance(r, Error):
            return r
        unit = r.value
        source_id = None
        proj = self._active_project()
        if not self.orchestrator:
            # Simulated: create Candidate directly
            cand = Candidate(
                title=f"[Simulated {ai_mode}] {unit.name}",
                candidate_type=CandidateType.SUGERENCIA_IA,
                proposed_data={"unit_id": unit_id, "content": unit.content, "hint": hint},
                source="ia",
                source_id=source_id,
                metadata={
                    "ai_mode": ai_mode,
                    "writing_unit_id": unit_id,
                },
            )
            proj.candidates.append(cand)
            proj.touch()
            return Ok(cand)

        # Real: use orchestrator
        modes = {
            "writing_expand": "expand_entity",
            "writing_critique": "critical_analysis",
            "writing_rewrite": "rewrite_description",
        }
        aim = modes.get(ai_mode, "expand_entity")
        filters = {"audience": "author"}
        resp_r = self.orchestrator.invoke(aim, unit_id, hint, filters)
        if isinstance(resp_r, Error):
            return resp_r
        resp = resp_r.value
        # Create Source IA
        if self.source_service:
            try:
                src_r = self.source_service.add_source({
                    "name": f"AI Writing {ai_mode}",
                    "source_type": "GENERACION_IA",
                    "notes": resp.raw_text[:500],
                    "metadata": {"ai_mode": ai_mode, "writing_unit_id": unit_id},
                })
                if not isinstance(src_r, Error):
                    source_id = src_r.value.id
            except Exception:
                pass
        cand = Candidate(
            title=f"[AI {ai_mode}] {unit.name}",
            candidate_type=CandidateType.SUGERENCIA_IA,
            proposed_data={"unit_id": unit_id, "content": resp.raw_text, "hint": hint},
            source="ia",
            source_id=source_id,
            metadata={
                "ai_mode": ai_mode,
                "writing_unit_id": unit_id,
            },
        )
        proj.candidates.append(cand)
        proj.touch()
        return Ok(cand)

    # ── Issue detection ────────────────────────────────────────────

    def detect_writing_issues(self) -> list[StructuredIssue]:
        proj = self._active_project()
        issues = []

        def _make_issue(desc, subtype, unit_id=None):
            from packages.domain.candidate_issue import StructuredIssueType
            meta = {"validator": "writing", "source": "deterministic", "subtype": subtype}
            if unit_id:
                meta["writing_unit_id"] = unit_id
            return StructuredIssue(
                description=desc,
                affected_entity_ids=[],
                metadata=meta,
                type=StructuredIssueType.INVALID_ENTITY_TYPE,
            )

        all_units = [u for u in proj.writing_units
                     if u.revision_state != RevisionState.ARCHIVADO]
        # WRITING_UNIT_UNLINKED
        for u in all_units:
            if not u.entity_ids:
                issues.append(_make_issue(
                    f"WritingUnit '{u.name}' has no linked entities",
                    "WRITING_UNIT_UNLINKED", u.id))

        # WRITING_ORDER_DUPLICATE
        order_map: dict[tuple, list] = {}
        for u in all_units:
            key = (u.parent_id, u.order)
            order_map.setdefault(key, []).append(u.id)
        for key, ids in order_map.items():
            if len(ids) > 1:
                issues.append(_make_issue(
                    f"Duplicate order {key[1]} under parent_id={key[0]}: {ids}",
                    "WRITING_ORDER_DUPLICATE"))

        # WRITING_PARENT_MISSING
        active_ids = {u.id for u in all_units}
        for u in all_units:
            if u.parent_id is not None and u.parent_id not in active_ids:
                issues.append(_make_issue(
                    f"WritingUnit '{u.name}' parent_id '{u.parent_id}' does not exist",
                    "WRITING_PARENT_MISSING", u.id))

        # WRITING_ENTITY_UNCOVERED
        if self.entity_service:
            all_entities = getattr(proj, "entities", [])
            linked_ids = set()
            for u in all_units:
                linked_ids.update(u.entity_ids)
            for e in all_entities:
                et = e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type)
                if e.id not in linked_ids and et not in ("nota",):
                    issues.append(_make_issue(
                        f"Entity '{e.name}' ({et}) has no writing coverage",
                        "WRITING_ENTITY_UNCOVERED"))

        return issues

    # ── Internal ───────────────────────────────────────────────────

    def _active_project(self) -> Project:
        proj = self.project_service.active_project
        if proj is None:
            raise RuntimeError("No active project")
        return proj


__all__ = ["WritingService"]
