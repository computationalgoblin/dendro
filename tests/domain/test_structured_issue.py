"""
Tests for StructuredIssue domain model (B12-T01) — enums, dataclass,
to_dict/from_dict roundtrip, state transitions.
"""

from __future__ import annotations

from packages.domain.candidate_issue import (
    StructuredIssue,
    StructuredIssueSeverity,
    StructuredIssueState,
    StructuredIssueType,
    is_valid_transition,
)


class TestStructuredIssueType:
    def test_15_values(self) -> None:
        values = list(StructuredIssueType)
        assert len(values) == 15

    def test_values_are_strings(self) -> None:
        for vt in StructuredIssueType:
            assert isinstance(vt.value, str)


class TestStructuredIssueSeverity:
    def test_4_levels(self) -> None:
        assert len(list(StructuredIssueSeverity)) == 4


class TestStructuredIssueState:
    def test_8_states(self) -> None:
        assert len(list(StructuredIssueState)) == 8


class TestTransitions:
    def test_valid(self) -> None:
        assert is_valid_transition(
            StructuredIssueState.ABIERTA, StructuredIssueState.REVISADA,
        ) is True

    def test_invalid(self) -> None:
        assert is_valid_transition(
            StructuredIssueState.RESUELTA, StructuredIssueState.ABIERTA,
        ) is False

    def test_resuelta_terminal(self) -> None:
        for s in StructuredIssueState:
            assert is_valid_transition(StructuredIssueState.RESUELTA, s) is False

    def test_intencional_only_to_abierta(self) -> None:
        assert is_valid_transition(
            StructuredIssueState.INTENCIONAL, StructuredIssueState.ABIERTA,
        ) is True
        assert is_valid_transition(
            StructuredIssueState.INTENCIONAL, StructuredIssueState.RESUELTA,
        ) is False

    def test_all_transitions(self) -> None:
        # Verify the full matrix
        from_state = StructuredIssueState.ABIERTA
        allowed = {
            StructuredIssueState.REVISADA,
            StructuredIssueState.DESCARTADA,
            StructuredIssueState.INTENCIONAL,
        }
        for s in StructuredIssueState:
            assert is_valid_transition(from_state, s) == (s in allowed)


class TestStructuredIssue:
    def test_defaults(self) -> None:
        si = StructuredIssue()
        assert si.type == StructuredIssueType.BROKEN_RELATION
        assert si.severity == StructuredIssueSeverity.MEDIA
        assert si.state == StructuredIssueState.ABIERTA
        assert si.is_intentional is False
        assert si.affected_entity_ids == []
        assert si.detected_at != ""

    def test_all_fields(self) -> None:
        si = StructuredIssue(
            id="i1",
            type=StructuredIssueType.DUPLICATE_ENTITY,
            severity=StructuredIssueSeverity.ALTA,
            state=StructuredIssueState.ABIERTA,
            affected_entity_ids=["e1", "e2"],
            affected_relation_ids=["r1"],
            affected_source_ids=["s1"],
            description="Duplicated entity",
            evidence="Entity e1 and e2 share name",
            possible_solutions=["Rename one", "Merge"],
            detected_at="2026-05-30T10:00:00",
            reviewed_at=None,
            resolution="",
            is_intentional=False,
            metadata={"validator": "check_duplicates"},
        )
        assert len(si.affected_entity_ids) == 2
        assert si.evidence != ""
        assert len(si.possible_solutions) == 2

    def test_to_dict_roundtrip(self) -> None:
        si = StructuredIssue(
            type=StructuredIssueType.NO_DESCRIPTION,
            severity=StructuredIssueSeverity.BAJA,
            state=StructuredIssueState.ABIERTA,
            affected_entity_ids=["e1"],
            description="No description",
            evidence="brief and extended are empty",
            possible_solutions=["Add description"],
            is_intentional=False,
        )
        d = si.to_dict()
        si2 = StructuredIssue.from_dict(d)
        assert si2.id == si.id
        assert si2.type == si.type
        assert si2.severity == si.severity
        assert si2.state == si.state
        assert si2.affected_entity_ids == si.affected_entity_ids
        assert si2.description == si.description
        assert si2.evidence == si.evidence
        assert si2.is_intentional == si.is_intentional
        assert si2.detected_at == si.detected_at

    def test_is_intentional_preserved(self) -> None:
        si = StructuredIssue(is_intentional=True, state=StructuredIssueState.INTENCIONAL)
        d = si.to_dict()
        si2 = StructuredIssue.from_dict(d)
        assert si2.is_intentional is True
        assert si2.state == StructuredIssueState.INTENCIONAL

    def test_detected_at_fallback(self) -> None:
        si = StructuredIssue.from_dict({"detected_at": ""})
        assert si.detected_at != ""
        assert "T" in si.detected_at  # ISO format
