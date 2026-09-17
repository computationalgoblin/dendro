"""BETA2-FIX-11 (fase B): la puerta del servicio para el rigor.

Dos agujeros verificados el 2026-08-04:
- `RelationService` **tiraba `certainty_level` en silencio** (no estaba entre sus
  `scalar_fields`) y devolvía `Ok`: el usuario marcaba «dudoso» y la app decía que
  sí sin guardarlo. `update_relation` tampoco aceptaba `life_span`, así que la
  datación rica de una relación se podía crear pero no corregir.
- `SourceController` solo sabía `list_all`/`create`: **no había forma de enlazar
  una fuente a nada**, aunque `SourceService` lo soportaba entero.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from hosts.DesktopHostPySide.controllers.source_controller import SourceController
from packages.application.relation_service import RelationService
from packages.domain.entity import CertaintyLevel, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import RelationType
from packages.domain.result import Ok
from packages.domain.source_history import SourceType
from packages.domain.temporal_models import TemporalPrecision


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _svc():
    p = Project(id="p", name="Castilla s. XIV")
    p.entities.append(NarrativeEntity(id="e1", name="Pedro I"))
    p.entities.append(NarrativeEntity(id="e2", name="María de Padilla"))
    ps = _FakeProjectService(active_project=p)
    return RelationService(project_service=ps), ps, p


# ── B1 · certeza en la relación ─────────────────────────────────────────


@pytest.mark.application
def test_beta_m2fix11_create_relation_conserva_certainty_level():
    svc, _, _ = _svc()
    res = svc.create_relation(
        "e1",
        "e2",
        RelationType.ESTA_RELACIONADO_CON,
        data={"certainty_level": "dudoso", "birth_year": 1352},
    )
    assert isinstance(res, Ok)
    assert res.value.certainty_level == CertaintyLevel.DUDOSO  # antes se perdía


@pytest.mark.application
def test_beta_m2fix11_update_relation_conserva_certainty_level():
    svc, _, _ = _svc()
    rel = svc.create_relation(
        "e1", "e2", RelationType.ESTA_RELACIONADO_CON, data={"birth_year": 1352}
    ).value
    res = svc.update_relation(rel.id, {"certainty_level": "confirmado"})
    assert isinstance(res, Ok)
    assert res.value.certainty_level == CertaintyLevel.CONFIRMADO


@pytest.mark.application
def test_beta_m2fix11_certainty_level_invalido_no_rompe():
    """Un valor basura cae al defecto del dominio, no revienta ni crea otro modelo."""
    svc, _, _ = _svc()
    rel = svc.create_relation(
        "e1", "e2", RelationType.ESTA_RELACIONADO_CON, data={"birth_year": 1352}
    ).value
    res = svc.update_relation(rel.id, {"certainty_level": "chachi"})
    assert isinstance(res, Ok)
    assert isinstance(res.value.certainty_level, CertaintyLevel)


@pytest.mark.application
def test_beta_m2fix11_update_relation_acepta_life_span_rico():
    svc, _, _ = _svc()
    rel = svc.create_relation(
        "e1", "e2", RelationType.ESTA_RELACIONADO_CON, data={"birth_year": 1352}
    ).value
    res = svc.update_relation(
        rel.id,
        {
            "life_span": {
                "start": {
                    "year": 1353,
                    "precision": "approximate",
                    "notes": "h. 1353, según Ayala",
                },
                "ongoing": True,
            }
        },
    )
    assert isinstance(res, Ok)
    span = res.value.life_span
    assert span.start.precision == TemporalPrecision.APPROXIMATE
    assert span.start.notes.startswith("h. 1353")
    # El año entero sigue siendo el espejo: la cronología no se mueve de sitio.
    assert res.value.birth_year == 1353


# ── B3 · fuentes: crear, enlazar y consultar desde el controlador ───────


@pytest.mark.application
def test_beta_m2fix11_fuente_se_enlaza_a_la_entidad_y_se_lee():
    _, ps, p = _svc()
    ctrl = SourceController(project_service=ps)
    creada = ctrl.create(
        {
            "name": "López de Ayala — Crónica del rey don Pedro",
            "source_type": SourceType.FRAGMENTO_DOCUMENTAL.value,
            "reference": "BNE MSS/1234, f. 12r",
            "fragment": "«E el rey don Pedro tomó por manceba a doña María…»",
        }
    )
    assert isinstance(creada, Ok)
    fuente = creada.value

    enlazada = ctrl.link_to_entity(fuente.id, "e1")
    assert isinstance(enlazada, Ok)

    leidas = ctrl.sources_for_entity("e1")
    assert isinstance(leidas, Ok)
    assert [s.id for s in leidas.value] == [fuente.id]
    assert leidas.value[0].reference.startswith("BNE")
    assert "manceba" in leidas.value[0].fragment
    # El enlace vive EN LA FUENTE (no hay entity.source_ids).
    assert p.sources[0].derived_entity_ids == ["e1"]


@pytest.mark.application
def test_beta_m2fix11_enlazar_a_lo_inexistente_devuelve_error():
    _, ps, _ = _svc()
    ctrl = SourceController(project_service=ps)
    fuente = ctrl.create({"name": "Fuente"}).value
    assert not isinstance(ctrl.link_to_entity(fuente.id, "no-existe"), Ok)
    assert not isinstance(ctrl.link_to_entity("no-existe", "e1"), Ok)


@pytest.mark.application
def test_beta_m2fix11_entidad_sin_fuentes_devuelve_lista_vacia():
    _, ps, _ = _svc()
    ctrl = SourceController(project_service=ps)
    leidas = ctrl.sources_for_entity("e2")
    assert isinstance(leidas, Ok)
    assert leidas.value == []
