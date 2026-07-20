"""BETA2-MEM-02: modelos de dominio de Memoria narrativa viva.

Dominio puro: round-trip to_dict/from_dict, defaults y tolerancia a datos
sucios. No toca IA, UI ni persistencia.
"""

import pytest

from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryFreshness,
    MemoryIssue,
    MemoryIssueKind,
    MemoryIssueStatus,
    MemoryOrigin,
    MemoryRevisionProposal,
    MemoryRevisionStatus,
    MemoryTargetKind,
    NarrativeMemory,
)


@pytest.mark.domain
def test_defaults():
    m = NarrativeMemory()
    assert m.target_kind == MemoryTargetKind.PROJECT
    assert m.target_id == ""
    assert m.context == ""
    assert m.freshness == MemoryFreshness.SIN_MEMORIA
    assert m.origin == MemoryOrigin.USUARIO
    assert m.issues == []
    assert m.citations == []
    assert m.pending_revision is None
    assert m.id.startswith("mem_")


@pytest.mark.domain
def test_target_key_distinguishes_context():
    base = NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id="e1")
    contextual = NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY, target_id="e1", context="era-antigua"
    )
    assert base.target_key() == ("entity", "e1", "")
    assert contextual.target_key() == ("entity", "e1", "era-antigua")
    assert base.target_key() != contextual.target_key()


@pytest.mark.domain
def test_citation_roundtrip():
    c = MemoryCitation(ref_kind=MemoryTargetKind.MILESTONE, ref_id="h1", nota="cita")
    assert MemoryCitation.from_dict(c.to_dict()) == c


@pytest.mark.domain
def test_issue_roundtrip_with_anchors():
    issue = MemoryIssue(
        kind=MemoryIssueKind.CONTRADICCION,
        texto="La reina muere antes de la coronación",
        anclado_a=[
            MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id="reina"),
            MemoryCitation(ref_kind=MemoryTargetKind.MILESTONE, ref_id="coronacion"),
        ],
        estado=MemoryIssueStatus.ABIERTA,
        origin=MemoryOrigin.IA,
    )
    restored = MemoryIssue.from_dict(issue.to_dict())
    assert restored.kind == MemoryIssueKind.CONTRADICCION
    assert restored.texto == issue.texto
    assert [c.ref_id for c in restored.anclado_a] == ["reina", "coronacion"]
    assert restored.estado == MemoryIssueStatus.ABIERTA


@pytest.mark.domain
def test_revision_proposal_roundtrip():
    prop = MemoryRevisionProposal(
        before={"resumen_editorial": "viejo"},
        after={"resumen_editorial": "nuevo"},
        origin=MemoryOrigin.IA,
        motivo="regar",
        estado=MemoryRevisionStatus.PENDIENTE,
    )
    restored = MemoryRevisionProposal.from_dict(prop.to_dict())
    assert restored.before == {"resumen_editorial": "viejo"}
    assert restored.after == {"resumen_editorial": "nuevo"}
    assert restored.estado == MemoryRevisionStatus.PENDIENTE


@pytest.mark.domain
def test_narrative_memory_roundtrip_full():
    m = NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY,
        target_id="e1",
        resumen_editorial="Resumen editorial actual.",
        estado_actual="Vive en el exilio.",
        issues=[MemoryIssue(kind=MemoryIssueKind.HUECO, texto="Falta su origen")],
        notas_causales=["Su decisión detona la guerra"],
        dependencias=[MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id="e2")],
        citations=[MemoryCitation(ref_kind=MemoryTargetKind.MILESTONE, ref_id="h1")],
        freshness=MemoryFreshness.REGADA,
        origin=MemoryOrigin.RIEGO,
        pending_revision=MemoryRevisionProposal(after={"resumen_editorial": "x"}),
    )
    restored = NarrativeMemory.from_dict(m.to_dict())
    assert restored.target_key() == m.target_key()
    assert restored.resumen_editorial == m.resumen_editorial
    assert restored.estado_actual == m.estado_actual
    assert restored.issues[0].kind == MemoryIssueKind.HUECO
    assert restored.notas_causales == ["Su decisión detona la guerra"]
    assert restored.dependencias[0].ref_id == "e2"
    assert restored.citations[0].ref_id == "h1"
    assert restored.freshness == MemoryFreshness.REGADA
    assert restored.origin == MemoryOrigin.RIEGO
    assert restored.pending_revision is not None
    assert restored.pending_revision.after == {"resumen_editorial": "x"}


@pytest.mark.domain
def test_content_snapshot_excludes_identity_fields():
    m = NarrativeMemory(resumen_editorial="r", estado_actual="s")
    snap = m.content_snapshot()
    assert set(snap.keys()) == {
        "resumen_editorial",
        "estado_actual",
        "cuerpo",
        "issues",
        "notas_causales",
        "dependencias",
        "citations",
        "wikilinks",
        "tags",
    }
    assert "id" not in snap
    assert "freshness" not in snap
    assert "created_at" not in snap


@pytest.mark.domain
def test_from_dict_is_tolerant_of_garbage():
    m = NarrativeMemory.from_dict(
        {
            "target_kind": "no-existe",
            "freshness": 123,
            "issues": "not-a-list",
            "citations": [{"ref_kind": "milestone", "ref_id": "h9"}, "basura"],
            "pending_revision": "nope",
        }
    )
    assert m.target_kind == MemoryTargetKind.PROJECT  # default por valor inválido
    assert m.freshness == MemoryFreshness.SIN_MEMORIA
    assert m.issues == []
    assert [c.ref_id for c in m.citations] == ["h9"]
    assert m.pending_revision is None
