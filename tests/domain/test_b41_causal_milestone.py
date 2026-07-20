import pytest

from packages.domain.causal_milestone import (
    CausalMilestone,
    CausalMilestoneStatus,
    CausalMilestoneType,
)
from packages.domain.project import Project
from packages.domain.temporal_models import EventTemporality, TemporalPrecision


@pytest.mark.domain
def test_causal_milestone_has_24_exact_fields_and_roundtrips():
    # 22 campos B41-T01 + ``year`` (BETA1-G02) + ``parent_milestone_id`` (BETA2-SUB-01).
    milestone = CausalMilestone(
        id="hito-1",
        title="Caída de la Primera Luna",
        description="La ruptura que explica la religión del equilibrio.",
        milestone_type=CausalMilestoneType.RUPTURA,
        status=CausalMilestoneStatus.HYPOTHESIS,
        temporality=EventTemporality(era="Edad Mítica", precision=TemporalPrecision.MYTHICAL),
        layer_ids=["layer_historia"],
        affected_entity_ids=["ent_cultura"],
        affected_branch_ids=["rama_religion"],
        affected_layer_ids=["layer_religion"],
        caused_relation_ids=["rel_deriva"],
        causal_parent_hito_ids=["hito-origen"],
        causal_child_hito_ids=["hito-consecuencia"],
        source_ids=["src_manual"],
        candidate_id="cand-hito",
        confidence=0.75,
        rationale="Conecta metafísica y cultura.",
        tags=["mito", "origen"],
        visibility_state="visible_usuario",
        metadata={"kind": "causal_milestone"},
        created_at="2026-06-05T21:00:00+00:00",
        updated_at="2026-06-05T21:30:00+00:00",
        year=-120,
        parent_milestone_id="hito-guerra",
    )

    data = milestone.to_dict()

    assert len(data) == 24
    assert data["milestone_type"] == "ruptura"
    assert data["status"] == "hypothesis"
    assert data["temporality"]["era"] == "Edad Mítica"
    assert data["affected_entity_ids"] == ["ent_cultura"]
    assert data["caused_relation_ids"] == ["rel_deriva"]
    assert data["year"] == -120
    assert data["parent_milestone_id"] == "hito-guerra"

    loaded = CausalMilestone.from_dict(data)

    assert loaded.id == "hito-1"
    assert loaded.title == "Caída de la Primera Luna"
    assert loaded.milestone_type == CausalMilestoneType.RUPTURA
    assert loaded.status == CausalMilestoneStatus.HYPOTHESIS
    assert loaded.temporality.precision == TemporalPrecision.MYTHICAL
    assert loaded.layer_ids == ["layer_historia"]
    assert loaded.metadata == {"kind": "causal_milestone"}
    assert loaded.parent_milestone_id == "hito-guerra"
    assert loaded.is_subhito is True


@pytest.mark.domain
def test_causal_milestone_parent_id_defaults_to_none_and_tolerates_blank():
    # BETA2-SUB-01: por defecto un hito es de primer nivel (sin marco).
    plain = CausalMilestone(id="hito-libre", title="Sin marco")
    assert plain.parent_milestone_id is None
    assert plain.is_subhito is False

    # from_dict tolerante: cadena vacía / no-string → None.
    assert CausalMilestone.from_dict({"parent_milestone_id": ""}).parent_milestone_id is None
    assert CausalMilestone.from_dict({"parent_milestone_id": 123}).parent_milestone_id is None
    assert (
        CausalMilestone.from_dict({"parent_milestone_id": "hito-marco"}).parent_milestone_id
        == "hito-marco"
    )


@pytest.mark.domain
def test_causal_milestone_from_dict_is_tolerant_and_does_not_use_empty_id_default():
    loaded = CausalMilestone.from_dict({
        "id": "",
        "title": "Hito parcial",
        "milestone_type": "tipo_invalido",
        "status": "estado_invalido",
        "layer_ids": "not-a-list",
        "confidence": "not-a-number",
        "metadata": "not-a-dict",
    })

    assert loaded.id
    assert loaded.id != ""
    assert loaded.title == "Hito parcial"
    assert loaded.milestone_type == CausalMilestoneType.ORIGEN
    assert loaded.status == CausalMilestoneStatus.CANDIDATE
    assert loaded.layer_ids == []
    assert loaded.confidence is None
    assert loaded.metadata == {}


@pytest.mark.domain
def test_project_persists_causal_milestones_collection():
    project = Project(id="proj-b41", name="B41")
    project.causal_milestones.append(
        CausalMilestone(
            id="hito-1",
            title="Combate de los dioses negros",
            affected_entity_ids=["ent_1"],
            layer_ids=["layer_metafisica"],
        )
    )

    data = project.to_dict()

    assert "causal_milestones" in data
    assert data["causal_milestones"][0]["title"] == "Combate de los dioses negros"

    loaded = Project.from_dict(data)

    assert len(loaded.causal_milestones) == 1
    assert loaded.causal_milestones[0].id == "hito-1"
    assert loaded.causal_milestones[0].affected_entity_ids == ["ent_1"]
