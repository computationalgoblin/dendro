"""BETA-MULTIAGENT2-FIX-12 (G2-29) — el calendario puede empezar en 1900.

El editor unificado solo sabía encadenar eras por duración desde el año 0
(`EraService.set_eras_from_durations`, `cursor = 0` fijo). Quien escribía de ESTE
mundo quería «de 1900 a 2000»; la historiadora tuvo que inventarse una era tapón
de 1.250 años vacíos para que su eje coincidiera con el anno domini.

Aquí se guarda el ancla del ORIGEN de la cadena (no un año por era: BETA2-CAL
retiró ese editor por ser un modelo paralelo y no se reabre), su ida y vuelta por
`get_view`, el presente coherente, el cero-falsy del prompt y que la regla T03
deje de castigar a todo mundo real sin ancla.
"""

from __future__ import annotations

import pytest

from packages.application.ai_jobs import _compact_chronology
from packages.application.calendar_service import CalendarService
from packages.application.temporal_coherence import evaluate_entity
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Ok

pytestmark = pytest.mark.application


class _FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _service(project=None):
    project = project or Project(id="p-fix12", name="La casa de Santa María")
    return CalendarService(_FakeProjectService(project)), project


_SIGLO_XX = {
    "calendar_name": "Gregoriano",
    "start_year": 1900,
    "eras": [{"name": "Siglo XX", "duration": 100}],
    "present": {"era_index": 0, "year_within": 86},  # 1900 + 85 = 1985
}


# ── el ancla ────────────────────────────────────────────────────────────────


def test_beta_m2fix12_era_con_ano_de_inicio():
    svc, project = _service()
    assert isinstance(svc.configure(dict(_SIGLO_XX)), Ok)
    eras = project.project_chronology.sorted_eras()
    assert eras[0].start_year == 1900
    # Trampa 5: la ÚLTIMA era queda ABIERTA (no-atemporalidad del contrato G01).
    assert eras[-1].end_year is None


def test_beta_m2fix12_la_cadena_de_duraciones_sigue_intacta():
    """El ancla mueve el ORIGEN; las eras siguientes se encadenan igual."""
    svc, project = _service()
    result = svc.configure({
        "start_year": 1900,
        "eras": [
            {"name": "Preguerra", "duration": 36},
            {"name": "Posguerra", "duration": 40},
            {"name": "Democracia", "duration": 50},
        ],
        "present": {"era_index": 2, "year_within": 10},
    })
    assert isinstance(result, Ok)
    eras = project.project_chronology.sorted_eras()
    assert [(e.start_year, e.end_year) for e in eras] == [
        (1900, 1935), (1936, 1975), (1976, None)
    ]


def test_beta_m2fix12_get_view_devuelve_el_ancla():
    """Reabrir el editor muestra 1900: `get_view` lo DERIVA de la primera era."""
    svc, _project = _service()
    svc.configure(dict(_SIGLO_XX))
    view = svc.get_view()
    assert isinstance(view, Ok)
    assert view.value["start_year"] == 1900
    assert view.value["eras"][0]["duration"] == 100
    # Ida y vuelta sin deriva: reconfigurar con lo que devuelve get_view no mueve nada.
    assert isinstance(svc.configure(dict(view.value)), Ok)
    assert svc.get_view().value["start_year"] == 1900


def test_beta_m2fix12_presente_dentro_del_rango():
    svc, project = _service()
    svc.configure(dict(_SIGLO_XX))
    chrono = project.project_chronology
    assert chrono.present_year == 1985
    era = chrono.era_for_year(chrono.present_year)
    assert era is not None and era.name == "Siglo XX"


# ── Trampa 6: un proyecto anterior al arreglo no se mueve ni un año ──────────


def test_beta_m2fix12_proyecto_viejo_sin_ancla_se_comporta_igual():
    """Sin `start_year` en el payload, el comportamiento es el de antes, bit a bit."""
    svc, project = _service()
    assert isinstance(svc.configure({
        "eras": [{"name": "Era A", "duration": 100}, {"name": "Era B", "duration": 50}],
        "present": {"era_index": 1, "year_within": 10},
    }), Ok)
    eras = project.project_chronology.sorted_eras()
    assert [(e.start_year, e.end_year) for e in eras] == [(0, 99), (100, None)]
    assert project.project_chronology.present_year == 109
    assert svc.get_view().value["start_year"] == 0


# ── el prompt ───────────────────────────────────────────────────────────────


def test_beta_m2fix12_prompt_lleva_el_presente():
    svc, project = _service()
    svc.configure(dict(_SIGLO_XX))
    bloque = _compact_chronology(project)
    assert bloque["anyo_presente"] == 1985
    assert bloque["equivalencia_presente"] == "año absoluto 1985 = Siglo XX, año 86"
    assert bloque["eras"] == [{"nombre": "Siglo XX", "inicio": 1900}]


def test_beta_m2fix12_prompt_emite_el_presente_aunque_valga_cero():
    """El cero-falsy: `if present_year:` callaba justo en el caso más dañino.

    Es el mundo real entregado en el beta: una sola era «Presente» desde 0 y seis
    hitos entre 1901 y 1985. El modelo recibía las eras y los hitos SIN año
    presente y concluyó que el personaje quedaba «huérfano en la línea de tiempo
    oficial». No alucinó: dedujo lo que le dimos.
    """
    _svc, project = _service()
    project.project_chronology.ensure_default_era()
    project.project_chronology.present_year = 0
    bloque = _compact_chronology(project)
    assert bloque["anyo_presente"] == 0
    assert "equivalencia_presente" in bloque

    # Sin eras (cronología vacía) no se inventa un presente.
    project.project_chronology.eras = []
    vacio = _compact_chronology(project)
    assert "anyo_presente" not in vacio
    assert "equivalencia_presente" not in vacio


# ── la regla T03 ────────────────────────────────────────────────────────────


def _remedios(birth: int, death: int | None = None) -> NarrativeEntity:
    return NarrativeEntity(
        id="e-remedios",
        name="Remedios",
        entity_type=EntityType.PERSONAJE,
        birth_year=birth,
        death_year=death,
    )


def test_beta_m2fix12_t03_no_dispara_con_ancla():
    """Con el calendario anclado en 1900, nacer en 1901 deja de ser un aviso."""
    svc, project = _service()
    svc.configure(dict(_SIGLO_XX))
    issues = evaluate_entity(_remedios(1901, 1985), chronology=project.project_chronology)
    codigos = {i.code for i in issues}
    assert "T03_START_AFTER_PRESENT" not in codigos
    assert "T02_OUTSIDE_ERAS" not in codigos


def test_beta_m2fix12_t03_castigaba_al_mundo_real_sin_ancla():
    """Medición del ANTES: sin ancla, todo mundo real se llena de avisos falsos."""
    _svc, project = _service()
    project.project_chronology.ensure_default_era()  # «Presente» desde 0
    project.project_chronology.present_year = 0
    issues = evaluate_entity(_remedios(1901, 1985), chronology=project.project_chronology)
    assert "T03_START_AFTER_PRESENT" in {i.code for i in issues}
