"""BETA-MULTIAGENT2-FIX-11: lo escrito a mano sobrevive a cerrar y reabrir.

Dos cosas, sin cambio de esquema (v40 intacta):
- la **página de wiki escrita a mano** (cuerpo + tags + autoría de usuario), que
  es el criterio 1 de la fase C: escribir, guardar, cerrar, reabrir y que el texto
  siga entero;
- el **aparato de rigor** de la fase B sobre la entidad (certeza + precisión
  temporal + fecha-mundo + nota), que ya viajaba en disco y ahora tiene puerta:
  «h. 1334» tiene que quedar distinguible de un 1334 documentado.
"""

from __future__ import annotations

import pytest

from packages.domain.entity import CertaintyLevel, NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryFreshness,
    MemoryOrigin,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.domain.temporal_models import EventTemporality, TemporalPrecision
from packages.domain.temporal_span import TemporalSpan
from packages.persistence.schema import CURRENT_SCHEMA_VERSION
from packages.persistence.store import ProjectStore


@pytest.mark.persistence
def test_beta_m2fix11_el_esquema_no_se_mueve():
    """Nada de esto necesita migración: `cuerpo`/`tags` viajan desde v39."""
    assert CURRENT_SCHEMA_VERSION == 40


@pytest.mark.persistence
def test_beta_m2fix11_pagina_manual_roundtrip(tmp_path):
    project = Project(id="p", name="La escalera del olmo")
    project.entities.append(NarrativeEntity(id="e1", name="Marta Olmo"))
    project.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id="e1",
            resumen_editorial="La protagonista.",
            cuerpo="Párrafo uno.\n\nPárrafo dos.\n\nPárrafo tres.",
            tags=["protagonista", "escrito a mano"],
            origin=MemoryOrigin.USUARIO,
            freshness=MemoryFreshness.REGADA,
        )
    )
    path = tmp_path / "olmo.json"
    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)

    loaded = store.load(path)
    assert isinstance(loaded, Ok)
    page = loaded.value.narrative_memories[0]
    assert page.cuerpo.count("\n\n") == 2  # los tres párrafos, enteros
    assert page.cuerpo.endswith("Párrafo tres.")
    assert page.tags == ["protagonista", "escrito a mano"]
    assert page.origin == MemoryOrigin.USUARIO  # quién la escribió se persiste
    assert page.freshness == MemoryFreshness.REGADA  # y Regar no la pisará


@pytest.mark.persistence
def test_beta_m2fix11_rigor_de_entidad_roundtrip(tmp_path):
    entidad = NarrativeEntity(id="e1", name="María de Padilla")
    entidad.certainty_level = CertaintyLevel.PROBABLE
    entidad.set_life_span(
        TemporalSpan(
            start=EventTemporality(
                year=1334,
                precision=TemporalPrecision.APPROXIMATE,
                world_date="h. 1334",
                period="reinado de Alfonso XI",
                notes="Fecha discutida: López de Ayala no la data.",
                contradictory_sources=["Crónica de Ayala", "Zúñiga"],
            ),
            end=EventTemporality(year=1361, precision=TemporalPrecision.EXACT),
        )
    )
    project = Project(id="p", name="Castilla s. XIV")
    project.entities.append(entidad)
    path = tmp_path / "castilla.json"
    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)

    loaded = store.load(path)
    assert isinstance(loaded, Ok)
    e = loaded.value.entities[0]
    assert e.certainty_level == CertaintyLevel.PROBABLE
    span = e.life_span
    assert span is not None
    assert span.start.precision == TemporalPrecision.APPROXIMATE
    assert span.start.world_date == "h. 1334"
    assert span.start.period == "reinado de Alfonso XI"
    assert span.start.notes.startswith("Fecha discutida")
    assert span.start.contradictory_sources == ["Crónica de Ayala", "Zúñiga"]
    # El año entero sigue siendo el espejo ordenable: la cronología no se mueve.
    assert e.birth_year == 1334
    assert span.end_year == 1361
