"""B40 — Creative config model, presets, branch config, migration.

Tests:
- CreativeProjectConfig expanded fields serialize/deserialize
- AIConfig expanded fields
- Creative presets load and apply
- Branch config helper
- Migration v21→v22
- Backward compatibility (old project data loads)
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# CreativeProjectConfig expanded
# ---------------------------------------------------------------------------


class TestCreativeProjectConfig:
    def test_original_fields_preserved(self):
        from packages.domain.project import CreativeProjectConfig

        cc = CreativeProjectConfig()
        assert cc.narrative_style == ""
        assert cc.main_themes == []
        assert cc.target_audience == ""
        assert cc.creative_rules == []

    def test_new_fields_have_defaults(self):
        from packages.domain.project import CreativeProjectConfig

        cc = CreativeProjectConfig()
        assert cc.core_premise == ""
        assert cc.short_summary == ""
        assert cc.development_status == ""
        assert cc.format == ""
        assert cc.creative_intent == {}
        assert cc.narrative_engine == {}
        assert cc.poetics == {}
        assert cc.canon == {}
        assert cc.negative_space == {}
        assert cc.taste_memory == {}
        assert cc.presets_applied == []

    def test_roundtrip_serialization(self):
        from packages.domain.project import CreativeProjectConfig

        cc = CreativeProjectConfig(
            narrative_style="Lírico y oscuro",
            core_premise="Un dios caído busca redención",
            development_status="expansion",
            format="novela",
            creative_intent={
                "reader_promise": "Descubrirás la verdad tras el mito",
                "desired_emotions": ["inquietud", "fascinación"],
                "originality": 8,
                "ambiguity": 7,
            },
            narrative_engine={
                "conflict_sources": ["cósmico", "interno"],
                "dominant_tension": "misterio",
                "character_agency": 4,
                "causality": 6,
            },
            poetics={
                "narrative_distance": "cercana",
                "description_density": 7,
            },
            canon={
                "hard_rules": ["Los dioses no mienten directamente"],
                "continuity_strictness": 9,
            },
            negative_space={
                "avoid_tropes": ["elegido por profecía"],
            },
            taste_memory={
                "accepted_patterns": ["giros ambiguos"],
            },
            presets_applied=["weird_mystery"],
        )

        d = cc.to_dict()
        cc2 = CreativeProjectConfig.from_dict(d)

        assert cc2.narrative_style == "Lírico y oscuro"
        assert cc2.core_premise == "Un dios caído busca redención"
        assert cc2.creative_intent["desired_emotions"] == ["inquietud", "fascinación"]
        assert cc2.canon["hard_rules"] == ["Los dioses no mienten directamente"]
        assert cc2.presets_applied == ["weird_mystery"]

    def test_old_data_loads_without_new_fields(self):
        from packages.domain.project import CreativeProjectConfig

        old_data = {
            "narrative_style": "Directo",
            "main_themes": ["guerra"],
            "target_audience": "adulto",
            "creative_rules": ["Sin resurrecciones"],
        }
        cc = CreativeProjectConfig.from_dict(old_data)
        assert cc.narrative_style == "Directo"
        assert cc.creative_intent == {}
        assert cc.canon == {}
        assert cc.presets_applied == []


# ---------------------------------------------------------------------------
# AIConfig expanded
# ---------------------------------------------------------------------------


class TestAIConfigExpanded:
    def test_original_fields_preserved(self):
        from packages.domain.project_config import AIConfig

        ai = AIConfig()
        assert ai.enabled is False
        assert ai.model_preference == "default"
        assert ai.creativity_level == "medium"

    def test_new_fields_have_defaults(self):
        from packages.domain.project_config import AIConfig

        ai = AIConfig()
        assert ai.default_role == "coauthor"
        assert ai.change_aggressiveness == 5
        assert ai.default_num_options == 3
        assert ai.output_mode == "contrastive_options"
        assert ai.uncertainty_policy == "conservative_proposal"
        assert ai.default_strategy == "profundizar"
        assert ai.context_depth == "balanced"


# ---------------------------------------------------------------------------
# Creative presets
# ---------------------------------------------------------------------------


class TestCreativePresets:
    def test_all_presets_have_required_fields(self):
        from packages.domain.creative_presets import CREATIVE_PRESETS

        for key, preset in CREATIVE_PRESETS.items():
            assert "label" in preset, f"Preset {key} missing label"
            assert "description" in preset, f"Preset {key} missing description"
            assert "creative_config" in preset, f"Preset {key} missing creative_config"

    def test_list_presets_returns_all(self):
        from packages.domain.creative_presets import list_presets, CREATIVE_PRESETS

        result = list_presets()
        assert len(result) == len(CREATIVE_PRESETS)
        assert all("key" in p and "label" in p for p in result)

    def test_get_preset_found_and_not_found(self):
        from packages.domain.creative_presets import get_preset

        p = get_preset("weird_mystery")
        assert p is not None
        assert p["label"] == "Weird mystery"

        assert get_preset("nonexistent") is None

    def test_apply_preset_to_project(self):
        from packages.domain.project import Project
        from packages.domain.creative_presets import apply_preset_to_project

        proj = Project(name="Test")
        result = apply_preset_to_project(proj, "weird_mystery")

        assert result is True
        assert "weird_mystery" in proj.creative_config.presets_applied
        # Should have set genre from preset
        assert proj.genre.primary_genre == "weird_fiction"

    def test_apply_nonexistent_preset_returns_false(self):
        from packages.domain.project import Project
        from packages.domain.creative_presets import apply_preset_to_project

        proj = Project(name="Test")
        result = apply_preset_to_project(proj, "nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# Branch config helper
# ---------------------------------------------------------------------------


class TestBranchConfig:
    def _make_entity(self):
        from packages.domain.entity import NarrativeEntity, EntityType

        return NarrativeEntity(
            name="Hermandad",
            entity_type=EntityType.CONTENEDOR,
        )

    def test_get_default_branch_config(self):
        from packages.domain.branch_config import get_branch_config

        entity = self._make_entity()
        cfg = get_branch_config(entity)
        assert cfg["inherits_from_project"] is True
        assert cfg["local_narrative_function"] == ""
        assert cfg["overrides"] == {}

    def test_set_and_get_branch_config(self):
        from packages.domain.branch_config import set_branch_config, get_branch_config

        entity = self._make_entity()
        cfg = {
            "inherits_from_project": False,
            "local_narrative_function": "revelar",
            "local_motifs": ["fuego"],
            "local_tone_override": "oscuro",
            "local_ai_role": "worldbuilder",
            "local_rules": ["Los miembros no traicionan"],
            "overrides": {"creative_intent": {"desired_emotions": ["tensión"]}},
        }
        set_branch_config(entity, cfg)
        result = get_branch_config(entity)
        assert result["local_narrative_function"] == "revelar"
        assert result["inherits_from_project"] is False

    def test_update_and_clear_override(self):
        from packages.domain.branch_config import (
            update_branch_override,
            clear_branch_override,
            get_branch_config,
        )

        entity = self._make_entity()
        update_branch_override(entity, "poetics.description_density", 8)
        cfg = get_branch_config(entity)
        assert cfg["overrides"]["poetics.description_density"] == 8
        assert cfg["inherits_from_project"] is False

        clear_branch_override(entity, "poetics.description_density")
        cfg = get_branch_config(entity)
        assert "poetics.description_density" not in cfg["overrides"]
        assert cfg["inherits_from_project"] is True

    def test_clear_all_overrides(self):
        from packages.domain.branch_config import (
            update_branch_override,
            clear_all_branch_overrides,
            get_branch_config,
        )

        entity = self._make_entity()
        update_branch_override(entity, "a", 1)
        update_branch_override(entity, "b", 2)

        clear_all_branch_overrides(entity)
        cfg = get_branch_config(entity)
        assert cfg["inherits_from_project"] is True
        assert cfg["overrides"] == {}


# ---------------------------------------------------------------------------
# Migration v21→v22
# ---------------------------------------------------------------------------


class TestMigrationV22:
    def test_migration_adds_creative_config_fields(self):
        from packages.persistence.schema import _apply_migration_v21_to_v22

        old_data = {
            "schema_version": 21,
            "creative_config": {
                "narrative_style": "Directo",
                "main_themes": ["guerra"],
            },
            "ai": {"enabled": True, "model_preference": "gpt-4"},
        }
        result = _apply_migration_v21_to_v22(old_data)

        assert result["schema_version"] == 22
        cc = result["creative_config"]
        assert cc["narrative_style"] == "Directo"  # preserved
        assert "creative_intent" in cc
        assert "canon" in cc
        assert "presets_applied" in cc
        ai = result["ai"]
        assert ai["default_role"] == "coauthor"
        assert ai["change_aggressiveness"] == 5

    def test_migration_preserves_existing_values(self):
        from packages.persistence.schema import _apply_migration_v21_to_v22

        old_data = {
            "schema_version": 21,
            "creative_config": {"narrative_style": "Poético"},
            "ai": {"enabled": True, "creativity_level": "high"},
        }
        result = _apply_migration_v21_to_v22(old_data)

        assert result["creative_config"]["narrative_style"] == "Poético"
        assert result["ai"]["creativity_level"] == "high"

    def test_migration_handles_missing_sections(self):
        from packages.persistence.schema import _apply_migration_v21_to_v22

        old_data = {"schema_version": 21}
        result = _apply_migration_v21_to_v22(old_data)

        assert result["schema_version"] == 22
        assert isinstance(result["creative_config"], dict)
        assert isinstance(result["ai"], dict)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_project_from_dict_with_old_schema(self):
        from packages.domain.project import Project

        # Simulate old project data without B40 fields
        old_data = {
            "id": "abc123",
            "name": "Old Project",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "schema_version": 20,
            "creative_config": {
                "narrative_style": "Directo",
                "main_themes": ["guerra"],
            },
        }
        proj = Project.from_dict(old_data)
        assert proj.name == "Old Project"
        assert proj.creative_config.narrative_style == "Directo"
        # New fields should have defaults
        assert proj.creative_config.creative_intent == {}
        assert proj.ai.default_role == "coauthor"

    def test_project_roundtrip_with_expanded_config(self):
        from packages.domain.project import Project

        proj = Project(name="New Project")
        proj.creative_config.core_premise = "Un mundo en ruinas"
        proj.creative_config.creative_intent = {"desired_emotions": ["tensión"]}
        proj.creative_config.canon = {"hard_rules": ["La magia tiene coste"]}
        proj.ai.default_role = "worldbuilder"
        proj.ai.change_aggressiveness = 7

        d = proj.to_dict()
        proj2 = Project.from_dict(d)

        assert proj2.creative_config.core_premise == "Un mundo en ruinas"
        assert proj2.creative_config.creative_intent["desired_emotions"] == ["tensión"]
        assert proj2.creative_config.canon["hard_rules"] == ["La magia tiene coste"]
        assert proj2.ai.default_role == "worldbuilder"
        assert proj2.ai.change_aggressiveness == 7


# ---------------------------------------------------------------------------
# B40-T05/T06 — Creative context in IA + branch inheritance
# ---------------------------------------------------------------------------


class TestCreativeContextForAI:
    def test_project_creative_brief_includes_behavior_driving_config(self):
        from packages.application.creative_context import project_creative_brief
        from packages.domain.project import Project

        proj = Project(name="Dendro")
        proj.worldbuilding_active = True
        proj.creative_config.core_premise = "Dos dioses son agujeros negros combatiendo"
        proj.creative_config.canon = {
            "hard_rules": ["La gravedad siempre deriva del conflicto divino"],
            "continuity_strictness": 9,
        }
        proj.creative_config.negative_space = {"avoid_tropes": ["elegido por profecía"]}
        proj.creative_config.taste_memory = {"accepted_patterns": ["causalidad descendente"]}
        proj.ai.default_role = "worldbuilder"
        proj.ai.default_strategy = "expandir_consecuencias"
        proj.ai.default_num_options = 4

        brief = project_creative_brief(proj)

        assert brief["worldbuilding_active"] is True
        assert brief["identity"]["core_premise"] == "Dos dioses son agujeros negros combatiendo"
        assert brief["canon"]["hard_rules"] == ["La gravedad siempre deriva del conflicto divino"]
        assert brief["negative_space"]["avoid_tropes"] == ["elegido por profecía"]
        assert brief["taste_memory"]["accepted_patterns"] == ["causalidad descendente"]
        assert brief["ai_preferences"]["default_role"] == "worldbuilder"
        assert brief["ai_preferences"]["default_strategy"] == "expandir_consecuencias"
        assert brief["ai_preferences"]["default_num_options"] == 4

    def test_build_model_user_message_contains_b40_profile(self):
        import json
        from packages.application.ai_jobs import build_job_plan, build_model_user_message, classify_intent

        intent = classify_intent("Expande la gravedad desde la metafísica", {"worldbuilding_active": True})
        plan = build_job_plan(
            intent,
            "Expande la gravedad desde la metafísica",
            {
                "creative_brief": {
                    "canon": {"hard_rules": ["La magia exige coste"]},
                    "negative_space": {"avoid_solutions": ["deus ex machina"]},
                    "taste_memory": {"rejected_patterns": ["final explicado por sueño"]},
                    "ai_preferences": {
                        "default_role": "worldbuilder",
                        "default_strategy": "descender_causalmente",
                        "default_num_options": 5,
                    },
                },
                "creative_context": [{"name": "Rama religiosa"}],
                "branch_creative_context": [{"name": "Culto del Peso"}],
            },
        )
        message = json.loads(build_model_user_message(plan))

        # PA03: config creativa COMPLETA en una única sección determinista
        # (canon duro, negative_space y taste_memory incluidos).
        cfg = message["configuracion_creativa"]
        assert cfg["canon"]["hard_rules"] == ["La magia exige coste"]
        assert cfg["negative_space"]["avoid_solutions"] == ["deus ex machina"]
        assert cfg["taste_memory"]["rejected_patterns"] == ["final explicado por sueño"]
        # PA03: ya no hay secciones duplicadas cerco_canon/parametros_permanentes.
        assert "cerco_canon" not in message
        assert "parametros_permanentes" not in message
        # M2: creative_brief/creative_context/branch_creative_context no se
        # duplican en contexto_autorizado (que, vacío, se poda del todo en PA03).
        auth = message.get("contexto_autorizado", {})
        assert "creative_brief" not in auth
        assert "creative_context" not in auth
        assert "branch_creative_context" not in auth
        # M2: el perfil legacy ya no viaja en el mensaje.
        assert "perfil_creativo_b40" not in message

    def test_branch_override_inheritance_uses_parent_rama_for_child_hoja(self):
        from packages.application.creative_context import selected_entity_creative_context
        from packages.domain.branch_config import update_branch_override
        from packages.domain.entity import EntityType, NarrativeEntity
        from packages.domain.project import Project
        from packages.domain.relation import NarrativeRelation, RelationType

        proj = Project(name="Herencia")
        proj.creative_config.canon = {"hard_rules": ["Regla global"]}
        rama = NarrativeEntity(name="Culto del Peso", entity_type=EntityType.CONTENEDOR)
        hoja = NarrativeEntity(name="Sacerdote de la Caída", entity_type=EntityType.PERSONAJE)
        update_branch_override(rama, "canon.hard_rules", ["Solo el peso revela la verdad"])
        update_branch_override(rama, "poetics.description_density", 8)
        proj.entities.extend([rama, hoja])
        proj.relations.append(NarrativeRelation(
            source_id=rama.id,
            target_id=hoja.id,
            relation_type=RelationType.CONTIENE,
        ))

        ctx = selected_entity_creative_context(proj, [hoja.id])

        assert len(ctx) == 1
        effective = ctx[0]["effective_config"]
        assert effective["canon"]["hard_rules"] == ["Solo el peso revela la verdad"]
        assert effective["poetics"]["description_density"] == 8

    def test_narrative_context_builder_includes_creative_brief_and_selected_effective_config(self):
        from types import SimpleNamespace
        from packages.application.narrative_context_builder import NarrativeContextBuilder
        from packages.domain.branch_config import update_branch_override
        from packages.domain.entity import EntityType, NarrativeEntity
        from packages.domain.project import Project

        proj = Project(name="Contexto IA")
        proj.creative_config.core_premise = "Un mundo gobernado por peso moral"
        proj.creative_config.canon = {"hard_rules": ["Toda ascensión exige pérdida"]}
        entity = NarrativeEntity(name="Orden del Lastre", entity_type=EntityType.CONTENEDOR)
        update_branch_override(entity, "negative_space.avoid_tropes", ["profecía elegida"])
        proj.entities.append(entity)

        ctx = NarrativeContextBuilder(SimpleNamespace(active_project=proj)).build_for_graph_selection(entity_ids=[entity.id], relation_ids=[])

        assert ctx["project"]["creative_brief"]["identity"]["core_premise"] == "Un mundo gobernado por peso moral"
        assert ctx["project"]["creative_brief"]["canon"]["hard_rules"] == ["Toda ascensión exige pérdida"]
        assert ctx["creative_context"][0]["effective_config"]["negative_space"]["avoid_tropes"] == ["profecía elegida"]
