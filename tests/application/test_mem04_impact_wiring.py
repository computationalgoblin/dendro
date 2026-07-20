"""BETA2-MEM-04: el disparo uniforme del motor desde los controllers de aplicacion.

Editar canon por el controller (mismo camino que Foco) propaga impacto y marca
Falta regar la Memoria del dependiente. Sin Qt: los controllers son clases Python
que envuelven servicios + project_service.
"""

import pytest

from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.project_service import ProjectService
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.relation import NarrativeRelation, RelationType


def _project_with_pair():
    ps = ProjectService()
    ps.create("Impacto")
    p = ps.active_project
    p.entities.append(NarrativeEntity(id="e1", name="Ana"))
    p.entities.append(NarrativeEntity(id="e2", name="Beto"))
    p.relations.append(
        NarrativeRelation(
            id="r", source_id="e1", target_id="e2", relation_type=RelationType.ES_ALIADO_DE
        )
    )
    p.touch()
    # e2 tiene Memoria vigente (REGADA) que puede quedar obsoleta.
    NarrativeMemoryService(ps).upsert_memory(
        MemoryTargetKind.ENTITY, "e2", resumen_editorial="Beto, aliado de Ana"
    )
    return ps, p


@pytest.mark.application
def test_entity_controller_update_propagates_impact():
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController

    ps, p = _project_with_pair()
    ctrl = EntityController(ps)

    ctrl.update("e1", {"brief_description": "Ana cambia de bando"})

    mem = NarrativeMemoryService(ps).get_memory(MemoryTargetKind.ENTITY, "e2").value
    assert mem.freshness == MemoryFreshness.FALTA_REGAR
    assert mem.resumen_editorial == "Beto, aliado de Ana"  # no borra contenido


@pytest.mark.application
def test_relation_controller_update_propagates_to_endpoints():
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController

    ps, p = _project_with_pair()
    ctrl = RelationController(ps)

    ctrl.update("r", {"description": "una alianza tensa"})

    mem = NarrativeMemoryService(ps).get_memory(MemoryTargetKind.ENTITY, "e2").value
    assert mem.freshness == MemoryFreshness.FALTA_REGAR


@pytest.mark.application
def test_update_without_dependent_memory_is_noop_but_saves():
    """Editar sin dependientes con Memoria no rompe el guardado (impacto no-op)."""
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController

    ps = ProjectService()
    ps.create("Solo")
    ps.active_project.entities.append(NarrativeEntity(id="x", name="Solo"))
    ps.active_project.touch()
    ctrl = EntityController(ps)

    result = ctrl.update("x", {"brief_description": "cambia"})
    from packages.domain.result import Ok

    assert isinstance(result, Ok)
    assert result.value.brief_description == "cambia"
