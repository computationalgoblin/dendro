import pytest

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project import Project
from packages.domain.project_chronology import ProjectChronology
from packages.domain.temporal_models import EventTemporality, TemporalPrecision


@pytest.mark.domain
def test_project_chronology_defaults_empty_and_not_graph_backed():
    chronology = ProjectChronology()

    data = chronology.to_dict()

    assert data["id"] == "project_chronology"
    assert data["calendar_system"] == "project"
    assert data["milestone_ids"] == []
    assert "nodes" not in data
    assert "edges" not in data


@pytest.mark.domain
def test_project_chronology_links_milestones_by_id_without_duplicates():
    chronology = ProjectChronology()

    chronology.link_milestone("hito-1")
    chronology.link_milestone("hito-1")
    chronology.link_milestone(" ")

    assert chronology.milestone_ids == ["hito-1"]
    assert chronology.includes_milestone("hito-1")

    chronology.unlink_milestone("hito-1")

    assert chronology.milestone_ids == []


@pytest.mark.domain
def test_causal_milestone_remains_temporal_milestone_model_for_project_chronology():
    milestone = CausalMilestone(
        id="hito-fundacion",
        title="Fundacion de la Ciudad Alta",
        temporality=EventTemporality(era="Primera Edad", precision=TemporalPrecision.APPROXIMATE),
        affected_entity_ids=["leaf-ciudad"],
        affected_branch_ids=["branch-politica"],
        affected_layer_ids=["ring-historia"],
        caused_relation_ids=["rel-alianza"],
    )

    data = milestone.to_dict()

    assert data["temporality"]["era"] == "Primera Edad"
    assert data["affected_entity_ids"] == ["leaf-ciudad"]
    assert data["affected_branch_ids"] == ["branch-politica"]
    assert data["affected_layer_ids"] == ["ring-historia"]
    assert data["caused_relation_ids"] == ["rel-alianza"]
    assert "node_id" not in data
    assert "graph_node" not in data


@pytest.mark.domain
def test_project_persists_chronology_container_with_existing_milestones():
    project = Project(id="proj-h", name="Cronologia")
    project.causal_milestones.append(CausalMilestone(id="hito-1", title="Origen"))
    project.project_chronology = ProjectChronology(
        calendar_name="Calendario imperial",
        milestone_ids=["hito-1"],
    )

    loaded = Project.from_dict(project.to_dict())

    assert loaded.project_chronology.calendar_name == "Calendario imperial"
    assert loaded.project_chronology.milestone_ids == ["hito-1"]
    assert loaded.causal_milestones[0].id == "hito-1"
