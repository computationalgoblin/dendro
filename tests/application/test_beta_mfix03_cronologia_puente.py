"""BETA-FIX-03: puente año absoluto ↔ era en los prompts (G-03).

La IA recibía año absoluto + fecha regnal sin puente y alegaba incoherencias
temporales falsas (arraigo hundido, walk bloqueado). Ahora `cronologia` viaja con
las eras (límites absolutos) + equivalencia del presente, y los serializadores de
riego/memoria/walk traducen cada año a «año N (Era X, año M)».
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.application.ai_jobs import _compact_chronology
from packages.application.chronology_walk_service import ChronologyWalkService
from packages.application.memory_ai_service import MemoryAIService
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.era import Era
from packages.domain.project import Project
from packages.domain.project_chronology import ProjectChronology, format_year_with_era


def _chronology_aureth() -> ProjectChronology:
    """El caso real del beta: 4 eras encadenadas, presente Reflujo 217 = abs 2716."""
    chrono = ProjectChronology(calendar_name="El Cómputo de las Mareas")
    chrono.eras = [
        Era(name="Alba", start_year=1, end_year=1200, order=0),
        Era(name="Segunda Era", start_year=1201, end_year=2100, order=1),
        Era(name="Era de la Marea", start_year=2101, end_year=2500, order=2),
        Era(name="Era del Reflujo", start_year=2500, end_year=None, order=3),
    ]
    chrono.present_year = 2716
    return chrono


# ── Helper de conversión (único, con bordes) ────────────────────────────────


def test_year_label_dentro_de_era():
    chrono = _chronology_aureth()
    assert chrono.year_label(2716) == "año 2716 (Era del Reflujo, año 217)"
    assert chrono.year_label(2140) == "año 2140 (Era de la Marea, año 40)"
    assert chrono.year_label(1) == "año 1 (Alba, año 1)"


def test_year_label_bordes():
    chrono = _chronology_aureth()
    assert chrono.year_label(None) == "sin fecha"
    assert chrono.year_label(-50) == "año -50"  # fuera de toda era → pelado
    assert ProjectChronology().year_label(100) == "año 100"  # sin eras


def test_format_year_with_era_tolera_cronologia_ausente():
    assert format_year_with_era(None, 100) == "año 100"
    assert format_year_with_era(None, None) == "sin fecha"


# ── Sección cronologia de los jobs ──────────────────────────────────────────


def test_compact_chronology_incluye_eras_y_equivalencia():
    proj = Project(name="Aureth")
    proj.project_chronology = _chronology_aureth()
    out = _compact_chronology(proj)
    assert out["anyo_presente"] == 2716
    assert out["era_actual"] == "Era del Reflujo"
    assert {"nombre": "Alba", "inicio": 1, "fin": 1200} in out["eras"]
    assert any(e["nombre"] == "Era del Reflujo" and "fin" not in e for e in out["eras"])
    assert out["equivalencia_presente"] == "año absoluto 2716 = Era del Reflujo, año 217"


def test_compact_chronology_sin_eras_degrada_sin_equivalencia():
    proj = Project(name="Simple")
    proj.project_chronology = ProjectChronology(calendar_name="Simple")
    out = _compact_chronology(proj)
    assert "equivalencia_presente" not in out
    assert "eras" not in out


# ── Serializadores: riego, memoria, walk ────────────────────────────────────


def _project_con_hito() -> tuple[Project, NarrativeEntity, CausalMilestone]:
    proj = Project(name="Aureth")
    proj.project_chronology = _chronology_aureth()
    entity = NarrativeEntity(name="Coral", entity_type=EntityType.PERSONAJE, birth_year=2100)
    proj.entities.append(entity)
    hito = CausalMilestone(title="El Canto Roto", year=2140)
    hito.affected_entity_ids = [entity.id]
    proj.causal_milestones.append(hito)
    return proj, entity, hito


def test_memoria_traduce_lapso_e_hitos():
    proj, entity, _ = _project_con_hito()
    lines = MemoryAIService._entity_temporal_lines(proj, entity.id)
    joined = "\n".join(lines)
    assert "año 2100 (Segunda Era, año 900)" in joined  # LAPSO
    assert "año 2140 (Era de la Marea, año 40)" in joined  # hito


def test_riego_traduce_lapso_e_hitos_en_contexto():
    from packages.application.watering_service import WateringService

    proj, entity, _ = _project_con_hito()

    @dataclass
    class _PS:
        active_project: Project

    ctx = WateringService(_PS(proj)).build_watering_context(entity.id)
    text = ctx.value["text"]
    assert "año 2100 (Segunda Era, año 900)" in text
    assert "año 2140 (Era de la Marea, año 40)" in text


def test_walk_brief_traduce_el_anyo():
    proj, _, hito = _project_con_hito()
    brief = ChronologyWalkService._hito_brief(hito, proj.project_chronology)
    assert brief["year"] == 2140
    assert brief["year_label"] == "año 2140 (Era de la Marea, año 40)"


def test_walk_brief_sin_cronologia_no_crashea():
    _, _, hito = _project_con_hito()
    brief = ChronologyWalkService._hito_brief(hito)
    assert brief["year"] == 2140
    assert "year_label" not in brief
