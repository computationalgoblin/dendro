"""BETA-AUDIT-11: los diagnósticos de riego se podan y no dejan huérfanos.

Medido sobre el proyecto de ejemplo antes de la épica: `watering_diagnostics` era el
**41 % del fichero** (history 19 %, candidates 13 %) frente a un **16 % de canon real**
—entidades, relaciones e hitos—. No había ninguna poda: cada riego apilaba una entrada
más, y borrar una entidad dejaba sus diagnósticos flotando (15 `entity_id` distintos
para 10 entidades vivas).

Proyectado a un mundo real (~400 entidades) eso son megas de JSON que se reescriben
enteros en cada guardado, se copian en cada `.bak` y se copian en profundidad hasta 40
veces en el historial de deshacer.
"""

from __future__ import annotations

from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.watering_service import MAX_DIAGNOSTICS_PER_ENTITY, WateringService
from packages.domain.entity import NarrativeEntity
from packages.domain.result import Ok
from packages.domain.watering import WateringDiagnostic
from datetime import UTC, datetime


def _proyecto():
    svc = ProjectService()
    assert isinstance(svc.create(name="Jardín podado"), Ok)
    entidad = NarrativeEntity(name="Nasr")
    svc.active_project.entities.append(entidad)
    return svc, entidad


def _diagnostico(entity_id: str, dia: int, mes: int = 1) -> WateringDiagnostic:
    momento = datetime(2026, mes, dia, tzinfo=UTC)
    return WateringDiagnostic(
        entity_id=entity_id,
        created_at=momento,
        scores={"arraigo": 50, "nutrida": 50, "iluminada": 50},
        summary=f"Riego de {momento.isoformat()}",
    )


def test_solo_se_conservan_los_n_mas_recientes():
    svc, entidad = _proyecto()
    proyecto = svc.active_project
    total = MAX_DIAGNOSTICS_PER_ENTITY + 3
    for i in range(total):
        proyecto.watering_diagnostics.append(
            _diagnostico(entidad.id, i + 1, mes=1)
        )
        WateringService.prune_diagnostics(proyecto, entidad.id)

    conservados = [d for d in proyecto.watering_diagnostics if d.entity_id == entidad.id]
    assert len(conservados) == MAX_DIAGNOSTICS_PER_ENTITY
    # Y son los últimos, no los primeros: el historial útil es el reciente.
    dias = sorted(d.created_at.day for d in conservados)
    assert dias[-1] == total
    assert dias[0] == total - MAX_DIAGNOSTICS_PER_ENTITY + 1


def test_la_poda_no_toca_los_de_otras_entidades():
    svc, entidad = _proyecto()
    proyecto = svc.active_project
    otra = NarrativeEntity(name="Sharif")
    proyecto.entities.append(otra)
    for i in range(MAX_DIAGNOSTICS_PER_ENTITY + 4):
        proyecto.watering_diagnostics.append(
            _diagnostico(entidad.id, i + 1, mes=2)
        )
    proyecto.watering_diagnostics.append(_diagnostico(otra.id, 1, mes=2))

    WateringService.prune_diagnostics(proyecto, entidad.id)
    assert len([d for d in proyecto.watering_diagnostics if d.entity_id == otra.id]) == 1


def test_borrar_una_entidad_se_lleva_sus_diagnosticos():
    svc, entidad = _proyecto()
    proyecto = svc.active_project
    proyecto.watering_diagnostics.append(_diagnostico(entidad.id, 1, mes=3))
    superviviente = NarrativeEntity(name="Sharif")
    proyecto.entities.append(superviviente)
    proyecto.watering_diagnostics.append(
        _diagnostico(superviviente.id, 2, mes=3)
    )

    assert isinstance(EntityService(project_service=svc).delete_entity(entidad.id), Ok)
    restantes = {d.entity_id for d in proyecto.watering_diagnostics}
    assert entidad.id not in restantes, "el borrado dejó diagnósticos huérfanos"
    assert superviviente.id in restantes, "la poda se llevó por delante a otra entidad"


def test_el_historial_visible_sigue_funcionando_tras_podar():
    """La pestaña Cultivo lee `history_for`: debe seguir devolviendo lo conservado."""
    svc, entidad = _proyecto()
    proyecto = svc.active_project
    for i in range(MAX_DIAGNOSTICS_PER_ENTITY + 2):
        proyecto.watering_diagnostics.append(
            _diagnostico(entidad.id, i + 1, mes=4)
        )
        WateringService.prune_diagnostics(proyecto, entidad.id)

    historial = WateringService(project_service=svc).history_for(entidad.id)
    entradas = historial.value if isinstance(historial, Ok) else historial
    assert len(entradas) == MAX_DIAGNOSTICS_PER_ENTITY
    # Más reciente primero, como espera el Cuaderno de cultivo.
    fechas = [d.created_at for d in entradas]
    assert fechas == sorted(fechas, reverse=True)


def test_el_tope_deja_margen_para_ver_evolucion():
    """Decisión de producto: no basta con guardar el último riego."""
    assert MAX_DIAGNOSTICS_PER_ENTITY >= 3, (
        "con menos de 3 entradas la pestaña Cultivo deja de mostrar evolución"
    )
