"""Migración v30 → v31 (PA04): config creativa canónica de 30 campos.

Verifica que ``_apply_migration_v30_to_v31`` colapsa las tres generaciones de
configuración (``genre/tone/realism/ai`` Gen A, ``advanced_config`` Gen B y los
dicts sin esquema de B40 dentro de ``creative_config``) en una única
``creative_config`` tipada de 5 secciones, convierte sliders a categorías, fusiona
las listas de espacio negativo en ``reglas.evitar`` y descarta lo eliminado.
"""

from __future__ import annotations

import pytest

from packages.domain.project import Project
from packages.persistence.schema import _apply_migration_v30_to_v31


def _v30_project() -> dict:
    """Proyecto v30 con la config vieja (las tres generaciones)."""
    return {
        "schema_version": 30,
        "id": "proj-v30",
        "name": "Proyecto v30",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        # B40: creative_config con sub-dicts sin esquema.
        "creative_config": {
            "core_premise": "Un dios caído busca redención",
            "short_summary": "Mito y deuda",
            "format": "novela",
            "development_status": "expansion",
            "main_themes": ["redención", "deuda"],
            "narrative_style": "Lírico y oscuro",
            "creative_intent": {
                "reader_promise": "Descubrirás la verdad tras el mito",
                "central_question": "¿Puede un dios cambiar?",
                "desired_emotions": ["inquietud", "fascinación"],
                "aftertaste": "Duelo silencioso",
                "originality": 9,
                "ambiguity": 8,
                "impact_types": ["misterio"],
            },
            "narrative_engine": {
                "conflict_sources": ["trauma"],
                "progression_mechanism": "revelacion",
                "causality": 8,
                "character_agency": 2,
                "escalation": "ciclica",
                "character_change": "caida",
            },
            "poetics": {
                "description_density": 8,
                "exposition_modes": ["por_pistas"],
                "forbidden_style_habits": ["adverbios en -mente"],
            },
            "canon": {
                "hard_rules": ["Los dioses no mienten directamente"],
                "continuity_strictness": 9,
            },
            "negative_space": {
                "avoid_tropes": ["elegido por profecía"],
                "avoid_solutions": ["deus ex machina"],
            },
        },
        # Gen A: genre / tone / realism / ai.
        "genre": {"primary_genre": "fantasia", "subgenres": ["oscura"]},
        "tone": {"narrative_tone": "melancólico"},
        "realism": {"realism_level": "medium", "magic_level": "high"},
        "ai": {"enabled": True, "default_role": "worldbuilder"},
        # Gen B: advanced_config (placeholder).
        "advanced_config": {"primary_genre": "ignorado"},
        # Otros campos eliminados que deben desaparecer.
        "project_metadata": {"author": "Alguien"},
        "general": {"theme": "x"},
        "import_taxonomy": {"allowed_entity_types": ["personaje"]},
        "novela_config": {"foo": "bar"},
    }


@pytest.mark.persistence
def test_migration_bumps_version_and_builds_five_sections():
    result = _apply_migration_v30_to_v31(_v30_project())

    assert result["schema_version"] == 31
    cc = result["creative_config"]
    assert set(cc.keys()) == {"identidad", "direccion", "motor", "estilo", "reglas"}


@pytest.mark.persistence
def test_migration_maps_premise_genre_and_realism():
    cc = _apply_migration_v30_to_v31(_v30_project())["creative_config"]

    # premisa migrada desde core_premise
    assert cc["identidad"]["premisa"] == "Un dios caído busca redención"
    # genero_principal desde genre.primary_genre
    assert cc["identidad"]["genero_principal"] == "fantasia"
    assert cc["identidad"]["subgeneros"] == ["oscura"]
    # realismo: medium → medio
    assert cc["estilo"]["realismo"] == "medio"


@pytest.mark.persistence
def test_migration_scales_slider_to_category():
    cc = _apply_migration_v30_to_v31(_v30_project())["creative_config"]
    # originality=9 cae en el bucket (8, 10] → "muy_autoral" (5º nivel).
    assert cc["direccion"]["originalidad"] == "muy_autoral"


@pytest.mark.persistence
def test_migration_fuses_negative_space_into_evitar():
    cc = _apply_migration_v30_to_v31(_v30_project())["creative_config"]
    evitar = cc["reglas"]["evitar"]
    assert "elegido por profecía" in evitar  # avoid_tropes
    assert "deus ex machina" in evitar  # avoid_solutions
    assert "adverbios en -mente" in evitar  # poetics.forbidden_style_habits
    # reglas_canon preserva las hard_rules del canon viejo.
    assert cc["reglas"]["reglas_canon"] == ["Los dioses no mienten directamente"]


@pytest.mark.persistence
def test_migration_drops_removed_top_level_keys():
    result = _apply_migration_v30_to_v31(_v30_project())
    for dead in (
        "genre", "tone", "realism", "ai", "general", "visibility", "export",
        "project_metadata", "advanced_config", "import_taxonomy", "novela_config",
    ):
        assert dead not in result, f"clave eliminada no debería sobrevivir: {dead}"


@pytest.mark.persistence
def test_migration_result_loads_into_project_end_to_end():
    result = _apply_migration_v30_to_v31(_v30_project())
    proj = Project.from_dict(result)

    assert proj.name == "Proyecto v30"
    cc = proj.creative_config
    assert cc.identidad.premisa == "Un dios caído busca redención"
    assert cc.identidad.genero_principal == "fantasia"
    assert cc.estilo.realismo == "medio"
    assert cc.direccion.originalidad == "muy_autoral"
    assert "deus ex machina" in cc.reglas.evitar
    assert cc.reglas.reglas_canon == ["Los dioses no mienten directamente"]
