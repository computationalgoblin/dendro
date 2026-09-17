"""BETA-MULTIAGENT2-FIX-05 (G2-05/G2-07): el jardín puede llegar a verde y quedarse.

Ronda 2 del beta multi-agente: la directora de arte regó cuatro entidades en 16 min 30 s
de IA real y acabó con el mismo número de verdes que al empezar, porque TRES mecanismos
independientes invalidaban trabajo recién pagado:

1. la propagación de impacto disparada por Regar (marcaba por la vía topológica
   ``relacion`` páginas vigentes de vecinas regadas en otra autorización),
2. la caducidad por vecindario de ``WateringService._is_stale`` (cualquier edición de una
   vecina caducaba un diagnóstico fresco) — que ningún tester identificó,
3. y, encima, la cola de deuda no estaba priorizada ni el detector estructural acotado.

Estos tests fijan la regla elegida y protegen lo que NO se puede romper: un cambio de
CANON sigue marcando las Memorias dependientes.

Patrón de dobles tomado de ``test_beta_mfix01_riego_no_autoinvalida.py``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import timedelta

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.entity_service import EntityService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.watering_attention import thirsty_queue, top_thirsty
from packages.application.watering_service import WateringService
from packages.domain.entity import EntityType, NarrativeEntity, NarrativeImportance
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok
from packages.domain.watering import WateringStatus
from packages.infrastructure.ai_provider import AIProvider

_MUNDO_ARTE = "beta-testing/2026-08-04/direccion-arte/mundo/archipielago-pigmentos.json"
_MUNDO_CAMPANA = "beta-testing/2026-08-04/campana-larga/mundo/marjal-rojo.json"

_VALID_PAYLOAD = {
    "scores": {"arraigo": 50, "nutrida": 60, "iluminada": 40},
    "summary": "Diagnóstico de prueba.",
    "metric_explanations": {"arraigo": "ok", "nutrida": "ok", "iluminada": "ok"},
    "risks": [],
}


class _FakeWateringProvider(AIProvider):
    provider_name = "fake_watering"
    model = "fake-model-1"

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        return json.dumps(_VALID_PAYLOAD, ensure_ascii=False), None


@dataclass
class _PS:
    """ProjectService mínimo (el riego solo necesita ``active_project``)."""

    active_project: Project = None


class _StubMemoryAI:
    """``update_memory`` que escribe la página como Regada, sin IA real."""

    def __init__(self, memory_service):
        self.memory_service = memory_service

    def update_memory(self, kind, target_id, mode="regar", progress_callback=None):
        self.memory_service.upsert_memory(
            kind, target_id, resumen_editorial="página", freshness=MemoryFreshness.REGADA
        )
        return Ok({"target_id": target_id})


def _jardin() -> tuple[_PS, dict[str, str], WateringService, NarrativeMemoryService]:
    """Proyecto A—B—C encadenado, con el riego cableado de punta a punta."""
    proj = Project(name="Jardín FIX2-05")
    ids: dict[str, str] = {}
    for name in ("A", "B", "C"):
        entity = NarrativeEntity(name=name, entity_type=EntityType.PERSONAJE)
        proj.entities.append(entity)
        ids[name] = entity.id
    for src, dst in (("A", "B"), ("B", "C")):
        proj.relations.append(
            NarrativeRelation(
                source_id=ids[src],
                target_id=ids[dst],
                relation_type=RelationType.ESTA_RELACIONADO_CON,
            )
        )
    ps = _PS(active_project=proj)
    memories = NarrativeMemoryService(ps)
    impact = NarrativeImpactService(ps, memories)
    ai = AIJobService(provider=_FakeWateringProvider(), project_provider=lambda: ps.active_project)
    watering = WateringService(
        ps,
        ai_job_service=ai,
        memory_ai_service=_StubMemoryAI(memories),
        impact_service=impact,
        memory_service=memories,
    )
    return ps, ids, watering, memories


def _freshness(memories, entity_id: str):
    got = memories.get_memory(MemoryTargetKind.ENTITY, entity_id)
    return got.value.freshness if isinstance(got, Ok) and got.value is not None else None


def _status(watering, entity_id: str) -> str:
    result = watering.status_of(entity_id)
    assert isinstance(result, Ok), getattr(result, "error", "")
    return result.value.status


def _cargar(path: str) -> Project:
    if not os.path.exists(path):  # pragma: no cover — mundo de evaluación local
        pytest.skip(f"mundo de evaluación no disponible: {path}")
    with open(path, encoding="utf-8") as handle:
        return Project.from_dict(json.load(handle))


# ── (a) el bucle del jardín ─────────────────────────────────────────────────


@pytest.mark.application
def test_beta_m2fix05_riegos_separados_dejan_las_dos_verdes():
    """Criterio 2: regar A y luego B (autorizaciones DISTINTAS) deja las dos verdes.

    Antes A volvía a `falta_regar` por dos vías a la vez: la propagación de impacto y
    `_is_stale`. Este es el hallazgo de ART-06 reducido a su mínima expresión.
    """
    _ps, ids, watering, memories = _jardin()

    assert isinstance(watering.water_entity(ids["A"]), Ok)
    assert _freshness(memories, ids["A"]) == MemoryFreshness.REGADA
    assert _status(watering, ids["A"]) == WateringStatus.REGADA.value

    # Riego SEPARADO (sin batch_ids): la exclusión de lote de FIX-01 no aplica aquí.
    assert isinstance(watering.water_entity(ids["B"]), Ok)

    assert _freshness(memories, ids["A"]) == MemoryFreshness.REGADA
    assert _status(watering, ids["A"]) == WateringStatus.REGADA.value
    assert _status(watering, ids["B"]) == WateringStatus.REGADA.value


@pytest.mark.application
def test_beta_m2fix05_cambio_de_canon_si_marca():
    """Criterio 3: editar la ficha de B SIGUE marcando `Falta regar` la página de A.

    Es la funcionalidad que no se puede romper: la distinción codificada es «cambió el
    canon» (marca) vs «se reescribió otra página de wiki» (no marca).
    """
    ps, ids, watering, memories = _jardin()
    assert isinstance(watering.water_entity(ids["A"]), Ok)
    assert _freshness(memories, ids["A"]) == MemoryFreshness.REGADA

    entities = EntityService(ps)
    result = entities.update_entity(
        ids["B"],
        {"brief_description": "B cambia de verdad"},
        impact_service=NarrativeImpactService(ps, memories),
    )
    assert isinstance(result, Ok), getattr(result, "error", "")

    assert _freshness(memories, ids["A"]) == MemoryFreshness.FALTA_REGAR
    # …y el jardín lo refleja por unificación de frescura (WIKI-13).
    assert _status(watering, ids["A"]) == WateringStatus.FALTA_REGAR.value


@pytest.mark.application
def test_beta_m2fix05_vecina_editada_no_caduca_el_diagnostico_por_si_sola():
    """Regla elegida sobre `_is_stale`: el CONTENIDO de una vecina no caduca el riego.

    Lo comprueba sin Memoria (la unificación de frescura desconectada), que es donde
    vivía la tercera vía de invalidación: antes bastaba con tocar `updated_at` de una
    vecina para que el diagnóstico fresco pasara a `falta_regar`.
    """
    ps, ids, watering, _memories = _jardin()
    solo_riego = WateringService(ps, ai_job_service=watering.ai_job_service)
    assert isinstance(watering.water_entity(ids["A"]), Ok)
    assert _status(solo_riego, ids["A"]) == WateringStatus.REGADA.value

    project = ps.active_project
    diagnostico = next(d for d in project.watering_diagnostics if d.entity_id == ids["A"])
    # Timestamps explícitos (patrón de test_watering_service_states): el reloj de la
    # máquina no tiene resolución para distinguir un `touch()` del riego que acaba de
    # ocurrir, y el test mediría el reloj en vez de la regla.
    despues = diagnostico.created_at + timedelta(minutes=5)

    project.entity_by_id(ids["B"]).updated_at = despues
    project.touch()
    assert _status(solo_riego, ids["A"]) == WateringStatus.REGADA.value

    # Pero el canon PROPIO sí caduca (la mitad que no se relaja).
    project.entity_by_id(ids["A"]).updated_at = despues
    project.touch()
    assert _status(solo_riego, ids["A"]) == WateringStatus.FALTA_REGAR.value


@pytest.mark.application
def test_beta_m2fix05_lote_sigue_saliendo_verde():
    """No regresar BETA-MULTIAGENT-FIX-01: regar A, B y C en un lote deja las tres verdes."""
    _ps, ids, watering, memories = _jardin()
    lote = [ids["A"], ids["B"], ids["C"]]
    for entity_id in lote:
        assert isinstance(watering.water_batch_step(entity_id, batch_ids=lote), Ok)
    for entity_id in lote:
        assert _freshness(memories, entity_id) == MemoryFreshness.REGADA
        assert _status(watering, entity_id) == WateringStatus.REGADA.value


@pytest.mark.application
def test_beta_m2fix05_secada_sigue_ganando_a_todo():
    """La guarda que no se toca: una entidad secada no la revive ni un riego vecino."""
    ps, ids, watering, _memories = _jardin()
    assert isinstance(watering.pause(ids["C"]), Ok)
    assert isinstance(watering.water_entity(ids["B"]), Ok)
    assert _status(watering, ids["C"]) == WateringStatus.SECADA.value


@pytest.mark.application
def test_beta_m2fix05_mundo_del_beta_no_queda_30_de_30():
    """Criterio 1, sobre el mundo real entregado por la directora de arte.

    HONESTIDAD: el mundo guardado llega con las cicatrices ya persistidas (3 de sus 4
    páginas están `falta_regar` EN DISCO, y 2 de las 4 entidades regadas se editaron
    después de su propio riego por una tanda masiva a las 16:04:09). Lo que este
    arreglo recupera de un mundo CONGELADO es la única entidad cuya única causa de sed
    era la caducidad por vecindario. El bucle se cierra hacia adelante, no hacia atrás:
    la demostración de que dos riegos separados quedan verdes es
    ``test_beta_m2fix05_riegos_separados_dejan_las_dos_verdes``.
    """
    project = _cargar(_MUNDO_ARTE)
    ps = _PS(active_project=project)
    watering = WateringService(project_service=ps, memory_service=NarrativeMemoryService(ps))
    reports = watering.statuses_for(None).value
    sedientas = thirsty_queue(project, reports)
    assert len(project.entities) == 30
    assert len(sedientas) < 30  # hoy eran 30 de 30
    assert any(r.status == WateringStatus.REGADA.value for r in reports.values())


# ── (c) la deuda accionable ─────────────────────────────────────────────────


@pytest.mark.application
def test_beta_m2fix05_cola_prioriza_por_valor():
    """Criterio 6: la cola de sed no es cronológica pura cuando el valor difiere.

    «No sé cuáles diez me convienen de verdad esta semana» (ESC-09, con 800 sedientas).
    """
    from types import SimpleNamespace

    from packages.application.causal_potency import set_basal_potency

    proj = Project(name="Prioridad")
    critica = NarrativeEntity(name="Zeta crítica", narrative_importance=NarrativeImportance.CRITICO)
    menor = NarrativeEntity(name="Alfa menor", narrative_importance=NarrativeImportance.MENOR)
    proj.entities.extend([critica, menor])

    # La MENOR es la más antigua: con el orden viejo (antigüedad + nombre) iría 1ª.
    reports = {
        critica.id: SimpleNamespace(status="falta_regar", latest=None, stale=False),
        menor.id: SimpleNamespace(status="falta_regar", latest=None, stale=False),
    }
    menor.created_at = critica.created_at.replace(year=critica.created_at.year - 1)

    assert thirsty_queue(proj, reports) == [critica.id, menor.id]

    # …y la potencia causal atribuida por la IA desempata entre iguales.
    a = NarrativeEntity(name="A media", narrative_importance=NarrativeImportance.MEDIO)
    b = NarrativeEntity(name="B media", narrative_importance=NarrativeImportance.MEDIO)
    proj2 = Project(name="Potencia")
    proj2.entities.extend([a, b])
    set_basal_potency(b, 90)
    reports2 = {
        a.id: SimpleNamespace(status="falta_regar", latest=None, stale=False),
        b.id: SimpleNamespace(status="falta_regar", latest=None, stale=False),
    }
    assert thirsty_queue(proj2, reports2) == [b.id, a.id]


@pytest.mark.application
def test_beta_m2fix05_top_thirsty_acota_el_trabajo_propuesto():
    """Criterio 6: el trabajo OFRECIDO es acotado aunque la deuda total sea enorme."""
    project = _cargar(_MUNDO_ARTE)
    ps = _PS(active_project=project)
    watering = WateringService(project_service=ps, memory_service=NarrativeMemoryService(ps))
    reports = watering.statuses_for(None).value
    cola = thirsty_queue(project, reports)
    top = top_thirsty(project, reports, 10)
    assert len(top) == 10
    assert top == cola[:10]  # la cabeza de la cola priorizada, sin reordenar


@pytest.mark.slow
@pytest.mark.application
def test_beta_m2fix05_detector_800_baja_el_ruido():
    """Criterio 8: menos ruido total SIN perder los 55 desajustes plantados.

    Sobre `marjal-rojo.json` (800 entidades, 1.760 relaciones, 9 anillos) el detector
    emitía 203 hallazgos, 105 de ellos `ascending_exception` (hasta 13 tarjetas para la
    MISMA entidad). Los 55 desajustes plantados aparecen como el racimo `gap == 3`, que
    en confianza es 0.70 — y ese racimo tiene que seguir entero.
    """
    from types import SimpleNamespace

    from packages.application.structural_analysis_service import StructuralAnalysisService

    project = _cargar(_MUNDO_CAMPANA)
    service = StructuralAnalysisService(project_service=SimpleNamespace(active_project=project))
    result = service.analyze()
    assert isinstance(result, Ok)
    findings = result.value

    por_tipo: dict[str, int] = {}
    for finding in findings:
        por_tipo[finding.kind] = por_tipo.get(finding.kind, 0) + 1

    assert len(findings) < 203  # el total baja de verdad
    assert por_tipo.get("ascending_exception", 0) <= 30  # 105 → 28, medido
    # Los movimientos (ring_move + branch_move) NO se tocan: 52 + 46 = 98.
    assert por_tipo.get("ring_move", 0) == 52
    assert por_tipo.get("branch_move", 0) == 46
    # El racimo de los 55 desajustes plantados (gap == 3 ⇒ confianza 0.70) sigue entero.
    gap3 = [
        f
        for f in findings
        if f.kind in ("ring_move", "branch_move") and abs(f.confidence - 0.70) < 1e-6
    ]
    assert len(gap3) == 57

    # Y una sola tarjeta por entidad inferior en las excepciones ascendentes.
    ascendentes = [f.target_id for f in findings if f.kind == "ascending_exception"]
    assert len(ascendentes) == len(set(ascendentes))
