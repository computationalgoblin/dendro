"""BETA2-MEM-03: al guardar prosa con @menciones se crean referencias (offscreen).

Smoke de las tres superficies editoriales exigidas por el ticket: entidad, hito y
relación. Verifica el circuito UI→servicio de aplicación→proyecto (sidecar).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.causal_milestone import CausalMilestone  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.narrative_memory import MemoryTargetKind  # noqa: E402
from packages.domain.relation import NarrativeRelation, RelationType  # noqa: E402
from packages.domain.structured_reference import ReferenceStatus  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _ctx(project_service):
    return SimpleNamespace(
        advanced_mode=False,
        log=lambda *a, **k: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service),
    )


def _refs(project_service, target_id):
    return [
        r
        for r in project_service.active_project.structured_references
        if r.target_id == target_id and r.status == ReferenceStatus.RESUELTA
    ]


def test_entity_panel_creates_reference_on_save(qapp):
    ps = ProjectService()
    ps.create("Ent")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController

    bob = NarrativeEntity(name="Bob")
    aria = NarrativeEntity(name="Aria")
    ps.active_project.entities.extend([bob, aria])
    ctrl = EntityController(ps)

    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

    panel = NodeDetailPanel(_ctx(ps), ctrl, aria.id)
    assert "brief_description" in panel._mention_supports  # @menciones adjuntas
    panel.brief_edit.setPlainText("Aria confía en @Bob")
    panel._do_save(refresh_after=False)

    hits = _refs(ps, bob.id)
    assert len(hits) == 1
    assert hits[0].source_id == aria.id
    assert hits[0].target_kind == MemoryTargetKind.ENTITY
    assert hits[0].source_field == "brief_description"


def test_milestone_panel_creates_reference_on_save(qapp):
    ps = ProjectService()
    ps.create("Hito")
    from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
        CausalMilestoneController,
    )

    bob = NarrativeEntity(name="Bob")
    ps.active_project.entities.append(bob)
    hito = CausalMilestone(title="La Caída", year=10)
    ps.active_project.causal_milestones.append(hito)
    ctrl = CausalMilestoneController(ps)

    from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

    panel = MilestoneDetailPanel(_ctx(ps), ctrl, hito.id)
    assert getattr(panel, "_mention_supports", None)
    panel.summary_edit.setPlainText("Todo empieza cuando @Bob decide huir")
    panel._do_save(reload_after=False)

    hits = _refs(ps, bob.id)
    assert len(hits) == 1
    assert hits[0].source_kind == MemoryTargetKind.MILESTONE
    assert hits[0].source_id == hito.id


def test_relation_panel_creates_reference_on_save(qapp):
    ps = ProjectService()
    ps.create("Rel")
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController

    bob = NarrativeEntity(name="Bob")
    a = NarrativeEntity(name="Alfa")
    b = NarrativeEntity(name="Beta")
    ps.active_project.entities.extend([bob, a, b])
    rel = NarrativeRelation(source_id=a.id, target_id=b.id, relation_type=RelationType.ES_ALIADO_DE)
    ps.active_project.relations.append(rel)
    ctrl = RelationController(ps)

    from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

    panel = RelationDetailPanel(_ctx(ps), ctrl, rel.id)
    assert getattr(panel, "_mention_supports", None)
    panel.description_edit.setPlainText("Su alianza nace por @Bob")
    panel._do_save(refresh_after=False)

    hits = _refs(ps, bob.id)
    assert len(hits) == 1
    assert hits[0].source_kind == MemoryTargetKind.RELATION
    assert hits[0].source_id == rel.id
