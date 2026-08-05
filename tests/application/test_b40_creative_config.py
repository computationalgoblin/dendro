"""B40/PA04 — Config creativa canónica (30 campos, 5 secciones), presets y brief.

PA04 simplificó la configuración a ``CreativeProjectConfig`` (identidad /
direccion / motor / estilo / reglas) y eliminó las generaciones previas
(``project_config`` Gen A, ``advanced_config`` Gen B, los dicts sin esquema de
B40, ``branch_config`` y los overrides locales). Estos tests cubren el modelo
nuevo: roundtrip de las 5 secciones, presets que rellenan sin pisar, y el brief
creativo que la IA recibe.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CreativeProjectConfig (5 secciones tipadas)
# ---------------------------------------------------------------------------


class TestCreativeProjectConfig:
    def test_defaults_are_empty(self):
        from packages.domain.creative_config import CreativeProjectConfig

        cc = CreativeProjectConfig()
        assert cc.identidad.premisa == ""
        assert cc.identidad.subgeneros == []
        assert cc.direccion.temas == []
        assert cc.motor.fuente_conflicto == ""
        assert cc.estilo.tono == ""
        assert cc.reglas.reglas_canon == []
        assert cc.reglas.evitar == []

    def test_roundtrip_serialization(self):
        from packages.domain.creative_config import (
            CreativeProjectConfig,
            DireccionCreativa,
            EstiloTono,
            Identidad,
            MotorNarrativo,
            ReglasLimites,
        )

        cc = CreativeProjectConfig(
            identidad=Identidad(
                premisa="Un dios caído busca redención",
                genero_principal="fantasia",
                subgeneros=["oscura"],
                formato="novela",
                estado="produccion",
            ),
            direccion=DireccionCreativa(
                promesa="Descubrirás la verdad tras el mito",
                emociones=["inquietud", "fascinación"],
                originalidad="muy_autoral",
                ambiguedad="ambiguo_interpretativo",
                tipo_impacto=["misterio"],
            ),
            motor=MotorNarrativo(
                fuente_conflicto="trauma",
                mecanismo="revelacion",
                causalidad="psicologica",
            ),
            estilo=EstiloTono(tono="Lírico y oscuro", realismo="alto", densidad="denso"),
            reglas=ReglasLimites(
                reglas_canon=["Los dioses no mienten directamente"],
                evitar=["elegido por profecía"],
            ),
        )

        d = cc.to_dict()
        cc2 = CreativeProjectConfig.from_dict(d)

        assert cc2.identidad.premisa == "Un dios caído busca redención"
        assert cc2.identidad.subgeneros == ["oscura"]
        assert cc2.direccion.emociones == ["inquietud", "fascinación"]
        assert cc2.motor.fuente_conflicto == "trauma"
        assert cc2.estilo.tono == "Lírico y oscuro"
        assert cc2.reglas.reglas_canon == ["Los dioses no mienten directamente"]
        assert cc2.reglas.evitar == ["elegido por profecía"]

    def test_to_dict_has_only_five_sections(self):
        from packages.domain.creative_config import CreativeProjectConfig

        d = CreativeProjectConfig().to_dict()
        assert set(d.keys()) == {"identidad", "direccion", "motor", "estilo", "reglas"}
        # PA04: las claves de las generaciones viejas ya no existen.
        for dead in ("genre", "tone", "ai", "import_taxonomy", "creative_intent",
                     "narrative_engine", "poetics", "canon", "negative_space"):
            assert dead not in d

    def test_from_dict_tolerates_garbage(self):
        from packages.domain.creative_config import CreativeProjectConfig

        cc = CreativeProjectConfig.from_dict({"identidad": None, "reglas": 42})
        assert cc.identidad.premisa == ""
        assert cc.reglas.evitar == []


# ---------------------------------------------------------------------------
# Creative presets
# ---------------------------------------------------------------------------


class TestCreativePresets:
    def test_all_presets_have_required_fields(self):
        from packages.domain.creative_presets import CREATIVE_PRESETS

        for key, preset in CREATIVE_PRESETS.items():
            assert "label" in preset, f"Preset {key} missing label"
            assert "description" in preset, f"Preset {key} missing description"
            assert "config" in preset, f"Preset {key} missing config"

    def test_list_presets_returns_all(self):
        from packages.domain.creative_presets import CREATIVE_PRESETS, list_presets

        result = list_presets()
        assert len(result) == len(CREATIVE_PRESETS)
        assert all("key" in p and "label" in p for p in result)

    def test_get_preset_found_and_not_found(self):
        from packages.domain.creative_presets import get_preset

        p = get_preset("weird_mystery")
        assert p is not None
        # BETA-AUDIT-13: la etiqueta se tradujo (era el único preset en inglés entre
        # diez en español). La CLAVE no cambia: es dato ya guardado en proyectos.
        assert p["label"] == "Misterio extraño"

        assert get_preset("nonexistent") is None

    def test_apply_preset_fills_all_five_sections(self):
        from packages.domain.creative_presets import apply_preset_to_project
        from packages.domain.project import Project

        proj = Project(name="Test")
        result = apply_preset_to_project(proj, "weird_mystery")

        assert result is True
        cc = proj.creative_config
        # Identidad / dirección / motor / estilo quedan rellenados desde el preset.
        assert cc.identidad.genero_principal == "weird_fiction"
        assert cc.direccion.originalidad == "muy_autoral"
        assert cc.motor.fuente_conflicto == "destino"
        assert cc.estilo.tono == "inquietante"
        assert cc.estilo.exposicion == "misteriosa"

    def test_apply_preset_does_not_overwrite_user_values(self):
        from packages.domain.creative_presets import apply_preset_to_project
        from packages.domain.project import Project

        proj = Project(name="Test")
        proj.creative_config.identidad.genero_principal = "noir"
        proj.creative_config.direccion.emociones = ["nostalgia"]

        assert apply_preset_to_project(proj, "weird_mystery") is True
        # Lo que el usuario ya configuró NO se pisa.
        assert proj.creative_config.identidad.genero_principal == "noir"
        assert proj.creative_config.direccion.emociones == ["nostalgia"]
        # Pero los campos vacíos sí se rellenan.
        assert proj.creative_config.estilo.tono == "inquietante"

    def test_apply_nonexistent_preset_returns_false(self):
        from packages.domain.creative_presets import apply_preset_to_project
        from packages.domain.project import Project

        proj = Project(name="Test")
        assert apply_preset_to_project(proj, "nonexistent") is False


# ---------------------------------------------------------------------------
# Backward compatibility (carga de proyectos)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_project_from_dict_without_creative_config(self):
        from packages.domain.project import Project

        old_data = {
            "id": "abc123",
            "name": "Old Project",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        proj = Project.from_dict(old_data)
        assert proj.name == "Old Project"
        # Config creativa vacía por defecto.
        assert proj.creative_config.identidad.premisa == ""
        assert proj.creative_config.reglas.evitar == []

    def test_project_roundtrip_with_creative_config(self):
        from packages.domain.project import Project

        proj = Project(name="New Project")
        proj.creative_config.identidad.premisa = "Un mundo en ruinas"
        proj.creative_config.direccion.emociones = ["tensión"]
        proj.creative_config.reglas.reglas_canon = ["La magia tiene coste"]

        d = proj.to_dict()
        proj2 = Project.from_dict(d)

        assert proj2.creative_config.identidad.premisa == "Un mundo en ruinas"
        assert proj2.creative_config.direccion.emociones == ["tensión"]
        assert proj2.creative_config.reglas.reglas_canon == ["La magia tiene coste"]


# ---------------------------------------------------------------------------
# Brief creativo para la IA
# ---------------------------------------------------------------------------


class TestCreativeContextForAI:
    def test_project_creative_brief_has_new_shape(self):
        from packages.application.creative_context import project_creative_brief
        from packages.domain.project import Project

        proj = Project(name="Dendro")
        proj.worldbuilding_active = True
        proj.creative_config.identidad.premisa = "Dos dioses son agujeros negros combatiendo"
        proj.creative_config.reglas.reglas_canon = [
            "La gravedad siempre deriva del conflicto divino"
        ]
        proj.creative_config.reglas.evitar = ["elegido por profecía"]
        proj.creative_config.estilo.tono = "épico"

        brief = project_creative_brief(proj)

        assert brief["project_name"] == "Dendro"
        assert brief["worldbuilding_active"] is True
        assert brief["primary_language"] == "es"
        assert brief["identidad"]["premisa"] == "Dos dioses son agujeros negros combatiendo"
        assert brief["reglas"]["reglas_canon"] == [
            "La gravedad siempre deriva del conflicto divino"
        ]
        assert brief["reglas"]["evitar"] == ["elegido por profecía"]
        assert brief["estilo"]["tono"] == "épico"

    def test_project_creative_brief_omits_empty_sections(self):
        from packages.application.creative_context import project_creative_brief
        from packages.domain.project import Project

        proj = Project(name="Vacío")
        brief = project_creative_brief(proj)
        # Solo las claves base; ninguna sección con campos rellenos.
        for section in ("identidad", "direccion", "motor", "estilo", "reglas"):
            assert section not in brief
        assert brief["project_name"] == "Vacío"

    def test_branch_and_entity_creative_context_are_empty(self):
        # PA04: la configuración por rama/entidad se eliminó.
        from packages.application.creative_context import (
            selected_branch_creative_context,
            selected_entity_creative_context,
        )
        from packages.domain.project import Project

        proj = Project(name="X")
        assert selected_branch_creative_context(proj, []) == []
        assert selected_entity_creative_context(proj, []) == []
