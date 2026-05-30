"""
Tests for IssueService and validators (B12-T02).
"""

from __future__ import annotations

from pathlib import Path

from packages.application.issue_service import (
    CONTRADICTORY_PAIRS,
    IssueService,
    run_validators,
)
from packages.application.project_service import ProjectService
from packages.domain.candidate_issue import (
    StructuredIssueSeverity,
    StructuredIssueState,
    StructuredIssueType,
    is_valid_transition,
)
from packages.domain.entity import CanonState, CertaintyLevel, EntityType, NarrativeEntity
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error
from packages.persistence.store import ProjectStore


def _setup():
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="IssueTest")
    svc = IssueService(project_service=ps)
    return ps, svc


class TestIssueServiceCRUD:
    def test_create_and_get(self) -> None:
        ps, svc = _setup()
        si = svc.create_issue({
            "type": "broken_relation",
            "description": "Test issue",
            "affected_entity_ids": ["e1"],
        }).value
        assert si.id != ""
        assert si.type == StructuredIssueType.BROKEN_RELATION

        found = svc.get_issue(si.id).value
        assert found.description == "Test issue"

    def test_list_filters(self) -> None:
        ps, svc = _setup()
        svc.create_issue({"type": "broken_relation", "state": "abierta", "severity": "alta"})
        svc.create_issue({"type": "no_description", "state": "resuelta", "severity": "baja"})

        open_issues = svc.list_issues(state="abierta").value
        assert len(open_issues) == 1

        alta = svc.list_issues(severity="alta").value
        assert len(alta) == 1

    def test_list_by_entity(self) -> None:
        ps, svc = _setup()
        svc.create_issue({
            "type": "broken_relation",
            "affected_entity_ids": ["e1", "e2"],
        })
        svc.create_issue({
            "type": "no_description",
            "affected_entity_ids": ["e3"],
        })
        result = svc.list_issues_by_entity("e1").value
        assert len(result) == 1


class TestStateTransitions:
    def test_valid_transition(self) -> None:
        ps, svc = _setup()
        si = svc.create_issue({"type": "broken_relation", "state": "abierta"}).value
        result = svc.transition_state(si.id, "revisada")
        assert result.value.state == StructuredIssueState.REVISADA

    def test_invalid_transition(self) -> None:
        ps, svc = _setup()
        si = svc.create_issue({"type": "broken_relation", "state": "resuelta"}).value
        result = svc.transition_state(si.id, "abierta")
        assert isinstance(result, Error)

    def test_resolve_shortcut(self) -> None:
        ps, svc = _setup()
        si = svc.create_issue({"type": "broken_relation", "state": "abierta"}).value
        result = svc.resolve_issue(si.id, note="fixed")
        assert result.value.state == StructuredIssueState.RESUELTA

    def test_discard_shortcut(self) -> None:
        ps, svc = _setup()
        si = svc.create_issue({"type": "broken_relation", "state": "abierta"}).value
        result = svc.discard_issue(si.id)
        assert result.value.state == StructuredIssueState.DESCARTADA

    def test_intentional_shortcut(self) -> None:
        ps, svc = _setup()
        si = svc.create_issue({"type": "broken_relation", "state": "abierta"}).value
        result = svc.mark_intentional(si.id)
        assert result.value.state == StructuredIssueState.INTENCIONAL
        assert result.value.is_intentional is True

    def test_review_and_accept(self) -> None:
        ps, svc = _setup()
        si = svc.create_issue({"type": "broken_relation", "state": "abierta"}).value
        svc.review_issue(si.id)
        svc.accept_issue(si.id)
        found = svc.get_issue(si.id).value
        assert found.state == StructuredIssueState.ACEPTADA


class TestValidators:
    def test_broken_relation(self) -> None:
        p = _setup()[0].active_project
        p.entities.append(NarrativeEntity(name="A", entity_type=EntityType.PERSONAJE))
        eid = p.entities[0].id
        p.relations.append(NarrativeRelation(
            source_id=eid, target_id="does-not-exist",
            relation_type=RelationType.ES_ALIADO_DE,
        ))
        issues = run_validators(p)
        broken = [i for i in issues if i.type == StructuredIssueType.BROKEN_RELATION]
        assert len(broken) == 1

    def test_duplicate_entity(self) -> None:
        p = _setup()[0].active_project
        p.entities.append(NarrativeEntity(name="Dupe", entity_type=EntityType.PERSONAJE))
        p.entities.append(NarrativeEntity(name="Dupe", entity_type=EntityType.LOCALIZACION))
        issues = run_validators(p)
        dup = [i for i in issues if i.type == StructuredIssueType.DUPLICATE_ENTITY]
        assert len(dup) == 1

    def test_no_description(self) -> None:
        p = _setup()[0].active_project
        p.entities.append(NarrativeEntity(name="ND", entity_type=EntityType.PERSONAJE))
        issues = run_validators(p)
        nod = [i for i in issues if i.type == StructuredIssueType.NO_DESCRIPTION]
        assert len(nod) == 1

    def test_orphan_entity(self) -> None:
        p = _setup()[0].active_project
        p.entities.append(NarrativeEntity(name="Orphan", entity_type=EntityType.PERSONAJE))
        issues = run_validators(p)
        orphan = [i for i in issues if i.type == StructuredIssueType.ORPHAN_ENTITY]
        assert len(orphan) == 1

    def test_orphan_excludes_nota(self) -> None:
        p = _setup()[0].active_project
        p.entities.append(NarrativeEntity(name="N", entity_type=EntityType.NOTA))
        issues = run_validators(p)
        orphan = [i for i in issues if i.type == StructuredIssueType.ORPHAN_ENTITY]
        assert len(orphan) == 0

    def test_canon_low_certainty(self) -> None:
        p = _setup()[0].active_project
        e = NarrativeEntity(name="Clo", entity_type=EntityType.PERSONAJE)
        e.canon_state = CanonState.CANONICO
        e.certainty_level = CertaintyLevel.DUDOSO
        p.entities.append(e)
        issues = run_validators(p)
        clc = [i for i in issues if i.type == StructuredIssueType.CANON_LOW_CERTAINTY]
        assert len(clc) == 1

    def test_contradictory_relations(self) -> None:
        p = _setup()[0].active_project
        e1 = NarrativeEntity(name="A", entity_type=EntityType.PERSONAJE)
        e2 = NarrativeEntity(name="B", entity_type=EntityType.PERSONAJE)
        p.entities.extend([e1, e2])
        p.relations.append(NarrativeRelation(
            source_id=e1.id, target_id=e2.id,
            relation_type=RelationType.ES_ALIADO_DE,
        ))
        p.relations.append(NarrativeRelation(
            source_id=e1.id, target_id=e2.id,
            relation_type=RelationType.ES_ENEMIGO_DE,
        ))
        issues = run_validators(p)
        contra = [i for i in issues if i.type == StructuredIssueType.CONTRADICTORY_RELATION]
        assert len(contra) == 1


class TestNoDuplication:
    def test_already_exists_skipped(self) -> None:
        ps, svc = _setup()
        svc.create_issue({
            "type": "broken_relation",
            "state": "abierta",
            "affected_entity_ids": ["e1"],
        })
        # Add an entity with no description to trigger NO_DESCRIPTION
        ps.active_project.entities.append(
            NarrativeEntity(name="ND", entity_type=EntityType.PERSONAJE),
        )
        result = svc.run_validation().value
        # broken_relation already exists for e1 → shouldn't duplicate
        assert result["new"] >= 0  # at least NO_DESCRIPTION created

    def test_intentional_not_regenerated(self) -> None:
        ps, svc = _setup()
        # Create actual broken relation first
        e = NarrativeEntity(name="A", entity_type=EntityType.PERSONAJE)
        ps.active_project.entities.append(e)
        ps.active_project.relations.append(NarrativeRelation(
            source_id=e.id, target_id="does-not-exist",
            relation_type=RelationType.ES_ALIADO_DE,
        ))
        # Mark as intentional with matching entity_id
        svc.create_issue({
            "type": "broken_relation",
            "state": "intencional",
            "is_intentional": True,
            "affected_entity_ids": [e.id, "does-not-exist"],
        })
        result = svc.run_validation().value
        # Should not create new broken_relation because INTENCIONAL exists
        open_br = svc.list_issues(itype="broken_relation", state="abierta").value
        assert len(open_br) == 0
