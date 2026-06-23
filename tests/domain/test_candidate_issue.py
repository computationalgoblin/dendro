"""Tests for B05-T04: Issue and Candidate domain models."""

from datetime import datetime, timezone

from packages.domain.candidate_issue import (
    Candidate,
    CandidateState,
    CandidateType,
    Issue,
    IssueSeverity,
    IssueState,
    IssueType,
)


class TestIssueType:
    def test_has_4_values(self):
        assert len(IssueType) == 4


class TestIssueSeverity:
    def test_has_4_values(self):
        assert len(IssueSeverity) == 4


class TestIssueState:
    def test_has_4_values(self):
        assert len(IssueState) == 4


class TestCandidateType:
    def test_has_11_values(self):
        # I08: + ANILLO (extracción de anillos/WorldLayer en importación dirigida).
        assert len(CandidateType) == 11


class TestCandidateState:
    def test_has_9_values(self):
        assert len(CandidateState) == 9


class TestIssue:
    def test_defaults(self):
        i = Issue()
        assert i.issue_type == IssueType.ADVERTENCIA
        assert i.severity == IssueSeverity.MEDIA
        assert i.state == IssueState.ABIERTA
        assert i.affected_entity_id is None

    def test_id_unique(self):
        i1 = Issue()
        i2 = Issue()
        assert i1.id != i2.id

    def test_13_fields(self):
        i = Issue(title="Test")
        d = i.to_dict()
        assert len(d) == 13, f"Expected 13, got {len(d)}: {list(d.keys())}"

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        i = Issue(
            id="iss1", issue_type=IssueType.CONTRADICCION,
            severity=IssueSeverity.ALTA, state=IssueState.EN_PROGRESO,
            title="Contradiction in canon",
            description="Entity A contradicts entity B",
            affected_entity_id="e1",
            created_at=now, resolution="Fixed by updating entity B",
        )
        assert i.issue_type == IssueType.CONTRADICCION
        assert i.affected_entity_id == "e1"
        assert i.affected_relation_id is None

    def test_roundtrip(self):
        i1 = Issue(
            title="Test Issue", issue_type=IssueType.ERROR,
            severity=IssueSeverity.CRITICA,
            affected_relation_id="r1",
            resolution="Resolved",
        )
        d = i1.to_dict()
        i2 = Issue.from_dict(d)
        assert i2.title == i1.title
        assert i2.issue_type == i1.issue_type
        assert i2.affected_relation_id == "r1"

    def test_from_dict_partial(self):
        i = Issue.from_dict({"title": "Partial", "issue_type": "inconsistencia"})
        assert i.title == "Partial"
        assert i.issue_type == IssueType.INCONSISTENCIA

    def test_from_dict_empty(self):
        i = Issue.from_dict({})
        assert i.id != ""


class TestCandidate:
    def test_defaults(self):
        c = Candidate()
        assert c.candidate_type == CandidateType.ENTIDAD
        assert c.state == CandidateState.PENDIENTE
        assert c.source_id is None

    def test_id_unique(self):
        c1 = Candidate()
        c2 = Candidate()
        assert c1.id != c2.id

    def test_18_fields(self):
        c = Candidate(title="Test")
        d = c.to_dict()
        assert len(d) == 18, f"Expected 11, got {len(d)}: {list(d.keys())}"

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        c = Candidate(
            id="c1", candidate_type=CandidateType.ENTIDAD,
            state=CandidateState.PENDIENTE,
            title="New character proposal",
            proposed_data={"name": "Eldrin", "entity_type": "personaje"},
            source="IA", source_id="src1",
            created_at=now,
        )
        assert c.proposed_data["name"] == "Eldrin"
        assert c.source_id == "src1"

    def test_roundtrip(self):
        c1 = Candidate(
            title="Proposal", candidate_type=CandidateType.RELACION,
            proposed_data={"source_id": "e1", "target_id": "e2"},
            source="Import", source_id="src2",
        )
        d = c1.to_dict()
        c2 = Candidate.from_dict(d)
        assert c2.title == c1.title
        assert c2.proposed_data == c1.proposed_data
        assert c2.source_id == "src2"

    def test_from_dict_partial(self):
        c = Candidate.from_dict({"title": "Partial", "candidate_type": "fuente"})
        assert c.title == "Partial"
        assert c.candidate_type == CandidateType.FUENTE

    def test_from_dict_empty(self):
        c = Candidate.from_dict({})
        assert c.id != ""
        assert c.state == CandidateState.PENDIENTE
