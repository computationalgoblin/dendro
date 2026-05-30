"""Tests for FrameworkService (B13-T02)."""

from packages.application.framework_service import FrameworkService
from packages.domain.narrative_framework import FrameworkType
from packages.domain.result import Error
from packages.persistence.store import ProjectStore
from packages.application.project_service import ProjectService


def _setup():
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="FWTest")
    return ps, FrameworkService(project_service=ps)


class TestCRUD:
    def test_create_from_builtin(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("Viaje", FrameworkType.HISTORIA).value
        assert fw.name == "Viaje"
        assert len(fw.components) == 3
        assert fw.components[0].name == "Acto I — Planteamiento"

    def test_create_personalizada(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("Custom", FrameworkType.PERSONALIZADA).value
        assert fw.framework_type == FrameworkType.PERSONALIZADA
        assert fw.components == []

    def test_get_and_list(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F1", FrameworkType.HISTORIA).value
        found = svc.get_framework(fw.id).value
        assert found.name == "F1"
        all_fw = svc.list_frameworks().value
        assert len(all_fw) == 1

    def test_list_active_only(self) -> None:
        ps, svc = _setup()
        svc.create_framework("F1", FrameworkType.HISTORIA)
        svc.create_framework("F2", FrameworkType.HISTORIA)
        svc.activate(svc.list_frameworks().value[0].id)
        active = svc.list_frameworks(active_only=True).value
        assert len(active) == 1

    def test_duplicate(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("Original", FrameworkType.HISTORIA).value
        dup = svc.duplicate_framework(fw.id, "Copy").value
        assert dup.name == "Copy"
        assert len(dup.components) == 3
        assert dup.id != fw.id


class TestComponents:
    def test_add_component(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.PERSONALIZADA).value
        comp = svc.add_component(fw.id, "Acto I").value
        assert comp.name == "Acto I"
        fw2 = svc.get_framework(fw.id).value
        assert len(fw2.components) == 1

    def test_associate_entity(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        from packages.domain.entity import NarrativeEntity, EntityType
        e = NarrativeEntity(name="Eldrin", entity_type=EntityType.PERSONAJE)
        ps.active_project.entities.append(e)
        comp = svc.associate_entity(fw.id, fw.components[0].id, e.id).value
        assert e.id in comp.associated_entity_ids

    def test_associate_relation(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        from packages.domain.entity import NarrativeEntity, EntityType
        from packages.domain.relation import NarrativeRelation, RelationType
        e1 = NarrativeEntity(name="A", entity_type=EntityType.PERSONAJE)
        e2 = NarrativeEntity(name="B", entity_type=EntityType.PERSONAJE)
        ps.active_project.entities.extend([e1, e2])
        r = NarrativeRelation(source_id=e1.id, target_id=e2.id, relation_type=RelationType.ES_ALIADO_DE)
        ps.active_project.relations.append(r)
        comp = svc.associate_relation(fw.id, fw.components[0].id, r.id).value
        assert r.id in comp.associated_relation_ids


class TestCoverage:
    def test_empty_framework(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        cov = svc.get_coverage(fw.id).value
        assert cov.total_components == 3
        assert cov.filled_components == 0
        assert cov.coverage_pct == 0.0

    def test_partial_coverage(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        from packages.domain.entity import NarrativeEntity, EntityType
        e = NarrativeEntity(name="E", entity_type=EntityType.PERSONAJE)
        ps.active_project.entities.append(e)
        svc.associate_entity(fw.id, fw.components[0].id, e.id)
        cov = svc.get_coverage(fw.id).value
        assert cov.filled_components == 1
        assert cov.coverage_pct == 33.3

    def test_deliberate_excluded(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        svc.mark_absence_deliberate(fw.id, fw.components[0].id)
        svc.mark_absence_deliberate(fw.id, fw.components[1].id)
        from packages.domain.entity import NarrativeEntity, EntityType
        e = NarrativeEntity(name="E", entity_type=EntityType.PERSONAJE)
        ps.active_project.entities.append(e)
        svc.associate_entity(fw.id, fw.components[2].id, e.id)
        cov = svc.get_coverage(fw.id).value
        assert cov.filled_components == 1
        assert cov.deliberate_empty == 2
        assert cov.coverage_pct == 100.0  # 1 filled / (3-2) effective

    def test_detect_empty(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        svc.mark_absence_deliberate(fw.id, fw.components[0].id)
        empty = svc.detect_empty_components(fw.id).value
        assert len(empty) == 2  # comps 1 and 2 not filled, not deliberate

    def test_mark_absence(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        comp = svc.mark_absence_deliberate(fw.id, fw.components[0].id).value
        assert comp.absence_deliberate is True


class TestTemplates:
    def test_list_templates(self) -> None:
        ps, svc = _setup()
        tmpls = svc.list_templates().value
        assert len(tmpls) == 14  # all 14 FrameworkTypes have a template  # all builtin types

    def test_save_and_create_from_template(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("Original", FrameworkType.HISTORIA).value
        tmpl = svc.save_as_template(fw.id, "MyTemplate").value
        assert tmpl.name == "MyTemplate"
        fw2 = svc.create_from_template("FromTemplate", tmpl.id).value
        assert fw2.name == "FromTemplate"
        assert len(fw2.components) == 3

    def test_activate_deactivate(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        svc.activate(fw.id)
        assert svc.get_framework(fw.id).value.is_active is True
        svc.deactivate(fw.id)
        assert svc.get_framework(fw.id).value.is_active is False

    def test_toggle(self) -> None:
        ps, svc = _setup()
        fw = svc.create_framework("F", FrameworkType.HISTORIA).value
        svc.toggle_active(fw.id)
        assert svc.get_framework(fw.id).value.is_active is True
