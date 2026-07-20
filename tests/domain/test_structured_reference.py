"""BETA2-MEM-03: modelo de dominio StructuredReference."""

import pytest

from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.structured_reference import ReferenceStatus, StructuredReference


@pytest.mark.domain
def test_defaults():
    r = StructuredReference()
    assert r.source_kind == MemoryTargetKind.ENTITY
    assert r.target_id == ""
    assert r.status == ReferenceStatus.RESUELTA
    assert r.candidate_target_ids == []
    assert r.id.startswith("ref_")


@pytest.mark.domain
def test_is_resolved():
    resolved = StructuredReference(target_id="e1", status=ReferenceStatus.RESUELTA)
    ambiguous = StructuredReference(status=ReferenceStatus.AMBIGUA, candidate_target_ids=["a", "b"])
    unresolved = StructuredReference(status=ReferenceStatus.NO_RESUELTA)
    assert resolved.is_resolved() is True
    assert ambiguous.is_resolved() is False
    assert unresolved.is_resolved() is False
    # resuelta pero sin id no cuenta como resuelta
    assert StructuredReference(status=ReferenceStatus.RESUELTA, target_id="").is_resolved() is False


@pytest.mark.domain
def test_roundtrip_full():
    r = StructuredReference(
        source_kind=MemoryTargetKind.MILESTONE,
        source_id="h1",
        source_field="description",
        target_kind=MemoryTargetKind.ENTITY,
        target_id="e9",
        alias="Aria",
        status=ReferenceStatus.AMBIGUA,
        candidate_target_ids=["e9", "e10"],
    )
    restored = StructuredReference.from_dict(r.to_dict())
    assert restored.source_key() == ("milestone", "h1")
    assert restored.source_field == "description"
    assert restored.target_kind == MemoryTargetKind.ENTITY
    assert restored.alias == "Aria"
    assert restored.status == ReferenceStatus.AMBIGUA
    assert restored.candidate_target_ids == ["e9", "e10"]


@pytest.mark.domain
def test_from_dict_tolerant():
    r = StructuredReference.from_dict(
        {"source_kind": "nope", "status": 7, "candidate_target_ids": "x", "metadata": "y"}
    )
    assert r.source_kind == MemoryTargetKind.ENTITY
    assert r.status == ReferenceStatus.RESUELTA
    assert r.candidate_target_ids == []
    assert r.metadata == {}
