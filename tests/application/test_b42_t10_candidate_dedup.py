"""Tests for B42-T10: Candidate deduplication.

Before showing candidates:
- Detect duplicates by name/type
- Detect already-existing relations
- Detect duplicate pending candidates
- Mark as possible duplicate, never auto-delete
"""
import pytest

from packages.application.candidate_dedup import (
    CandidateDeduplicator,
    DeduplicationResult,
)


class TestNameTypeDedup:
    def test_exact_name_duplicate_detected(self):
        dedup = CandidateDeduplicator(
            existing_names={"Fosco", "Bilbo"},
            existing_relations=set(),
            pending_names=set(),
        )
        result = dedup.check({"name": "Fosco", "entity_type": "personaje"})
        assert result.is_possible_duplicate
        assert "Fosco" in result.reason

    def test_similar_name_detected(self):
        dedup = CandidateDeduplicator(
            existing_names={"Fosco"},
            existing_relations=set(),
            pending_names=set(),
        )
        result = dedup.check({"name": "fosco", "entity_type": "personaje"})
        assert result.is_possible_duplicate

    def test_different_name_not_flagged(self):
        dedup = CandidateDeduplicator(
            existing_names={"Fosco"},
            existing_relations=set(),
            pending_names=set(),
        )
        result = dedup.check({"name": "Gandalf", "entity_type": "personaje"})
        assert not result.is_possible_duplicate

    def test_same_type_different_name_not_flagged(self):
        dedup = CandidateDeduplicator(
            existing_names={"Fosco"},
            existing_relations=set(),
            pending_names=set(),
        )
        result = dedup.check({"name": "Aragorn", "entity_type": "personaje"})
        assert not result.is_possible_duplicate


class TestRelationDedup:
    def test_existing_relation_detected(self):
        dedup = CandidateDeduplicator(
            existing_names=set(),
            existing_relations={("Fosco", "es_aliado_de", "Bilbo")},
            pending_names=set(),
        )
        result = dedup.check({
            "source_name": "Fosco",
            "relation_type": "es_aliado_de",
            "target_name": "Bilbo",
        })
        assert result.is_possible_duplicate

    def test_new_relation_not_flagged(self):
        dedup = CandidateDeduplicator(
            existing_names=set(),
            existing_relations={("Fosco", "es_aliado_de", "Bilbo")},
            pending_names=set(),
        )
        result = dedup.check({
            "source_name": "Fosco",
            "relation_type": "es_enemigo_de",
            "target_name": "Sauron",
        })
        assert not result.is_possible_duplicate


class TestPendingCandidateDedup:
    def test_pending_candidate_name_detected(self):
        dedup = CandidateDeduplicator(
            existing_names=set(),
            existing_relations=set(),
            pending_names={"Fosco"},
        )
        result = dedup.check({"name": "Fosco", "entity_type": "personaje"})
        assert result.is_possible_duplicate

    def test_pending_relation_detected(self):
        dedup = CandidateDeduplicator(
            existing_names=set(),
            existing_relations=set(),
            pending_names=set(),
            pending_relations={("Fosco", "es_aliado_de", "Bilbo")},
        )
        result = dedup.check({
            "source_name": "Fosco",
            "relation_type": "es_aliado_de",
            "target_name": "Bilbo",
        })
        assert result.is_possible_duplicate


class TestBatchDedup:
    def test_batch_marks_duplicates(self):
        dedup = CandidateDeduplicator(
            existing_names={"Fosco"},
            existing_relations=set(),
            pending_names=set(),
        )
        candidates = [
            {"name": "Fosco", "entity_type": "personaje"},
            {"name": "Bilbo", "entity_type": "personaje"},
            {"name": "Gandalf", "entity_type": "personaje"},
        ]
        results = dedup.check_batch(candidates)
        assert len(results) == 3
        assert results[0].is_possible_duplicate  # Fosco
        assert not results[1].is_possible_duplicate  # Bilbo
        assert not results[2].is_possible_duplicate  # Gandalf

    def test_never_deletes(self):
        """Dedup marks but never removes candidates."""
        dedup = CandidateDeduplicator(
            existing_names={"Fosco"},
            existing_relations=set(),
            pending_names=set(),
        )
        result = dedup.check({"name": "Fosco", "entity_type": "personaje"})
        assert result.is_possible_duplicate
        # The candidate is still returned — just flagged
        assert result.candidate == {"name": "Fosco", "entity_type": "personaje"}
