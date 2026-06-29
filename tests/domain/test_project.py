"""Tests del modelo de dominio Project (B02-T01 + PA04).

PA04 simplificó la configuración del proyecto: las generaciones viejas
(``general/tone/genre/realism/ai/visibility/export/project_metadata`` y
``advanced_config``) se eliminaron y se sustituyeron por una única
``creative_config`` (``CreativeProjectConfig``: identidad / direccion / motor /
estilo / reglas). El idioma sigue en ``Project.primary_language``.

Cubre:
- Creación por defecto (campos núcleo + creative_config vacío)
- Roundtrip to_dict / from_dict de las 5 secciones de creative_config
- Que to_dict ya NO emite las claves de config viejas
- Compatibilidad hacia atrás con datos v1 (mínimos)
- touch()
"""

from packages.domain.creative_config import (
    CreativeProjectConfig,
    DireccionCreativa,
    EstiloTono,
    Identidad,
    MotorNarrativo,
    ReglasLimites,
)
from packages.domain.project import Project

# ---------------------------------------------------------------------------
# 1. Default creation
# ---------------------------------------------------------------------------


class TestProjectDefaults:
    def test_project_has_auto_generated_id(self):
        p = Project()
        assert isinstance(p.id, str)
        assert len(p.id) == 12

    def test_project_has_unique_ids(self):
        assert Project().id != Project().id

    def test_default_name_is_empty(self):
        assert Project().name == ""

    def test_default_description_is_empty(self):
        assert Project().description == ""

    def test_default_primary_language_is_es(self):
        assert Project().primary_language == "es"

    def test_default_secondary_languages_is_empty_list(self):
        assert Project().secondary_languages == []

    def test_default_created_at_is_utc(self):
        assert str(Project().created_at.tzinfo) == "UTC"

    def test_default_updated_at_is_utc(self):
        assert str(Project().updated_at.tzinfo) == "UTC"

    def test_default_metadata_is_empty_dict(self):
        assert Project().metadata == {}


# ---------------------------------------------------------------------------
# 2. creative_config — defaults y composición
# ---------------------------------------------------------------------------


class TestCreativeConfigDefaults:
    def test_creative_config_is_typed(self):
        p = Project()
        cc = p.creative_config
        assert isinstance(cc, CreativeProjectConfig)
        assert isinstance(cc.identidad, Identidad)
        assert isinstance(cc.direccion, DireccionCreativa)
        assert isinstance(cc.motor, MotorNarrativo)
        assert isinstance(cc.estilo, EstiloTono)
        assert isinstance(cc.reglas, ReglasLimites)

    def test_creative_config_defaults_empty(self):
        cc = Project().creative_config
        assert cc.identidad.premisa == ""
        assert cc.identidad.subgeneros == []
        assert cc.direccion.temas == []
        assert cc.motor.fuente_conflicto == ""
        assert cc.estilo.tono == ""
        assert cc.reglas.reglas_canon == []
        assert cc.reglas.evitar == []


# ---------------------------------------------------------------------------
# 3. Prepared collections
# ---------------------------------------------------------------------------


class TestProjectCollections:
    def test_five_collections_exist(self):
        p = Project()
        assert p.entities == []
        assert p.relations == []
        assert p.sources == []
        assert p.history == []
        assert p.issues == []

    def test_collections_are_independent_instances(self):
        p1 = Project()
        p2 = Project()
        p1.entities.append("e1")
        assert p2.entities == []


# ---------------------------------------------------------------------------
# 4. to_dict / from_dict roundtrip (creative_config)
# ---------------------------------------------------------------------------


class TestCreativeConfigRoundtrip:
    def test_roundtrip_preserves_five_sections(self):
        p = Project(name="Fantasy World", description="A vast world")
        p.primary_language = "en"
        p.secondary_languages = ["fr", "de"]
        p.creative_config = CreativeProjectConfig(
            identidad=Identidad(
                premisa="Un imperio en decadencia",
                genero_principal="fantasia",
                subgeneros=["épica", "oscura"],
                estado="produccion",
            ),
            direccion=DireccionCreativa(temas=["poder", "lealtad"], originalidad="experimental"),
            motor=MotorNarrativo(fuente_conflicto="poder", mecanismo="intriga"),
            estilo=EstiloTono(tono="serio", realismo="alto"),
            reglas=ReglasLimites(reglas_canon=["Sin resurrecciones"], evitar=["deus ex machina"]),
        )

        d = p.to_dict()
        p2 = Project.from_dict(d)

        assert p2.name == "Fantasy World"
        assert p2.primary_language == "en"
        assert p2.secondary_languages == ["fr", "de"]
        cc = p2.creative_config
        assert cc.identidad.premisa == "Un imperio en decadencia"
        assert cc.identidad.subgeneros == ["épica", "oscura"]
        assert cc.direccion.temas == ["poder", "lealtad"]
        assert cc.motor.fuente_conflicto == "poder"
        assert cc.estilo.tono == "serio"
        assert cc.reglas.reglas_canon == ["Sin resurrecciones"]
        assert cc.reglas.evitar == ["deus ex machina"]


# ---------------------------------------------------------------------------
# 5. to_dict ya no emite las claves de config viejas
# ---------------------------------------------------------------------------


class TestToDict:
    def test_to_dict_has_creative_config(self):
        d = Project().to_dict()
        assert "creative_config" in d
        assert set(d["creative_config"].keys()) == {
            "identidad", "direccion", "motor", "estilo", "reglas"
        }

    def test_to_dict_drops_old_config_keys(self):
        d = Project().to_dict()
        for dead in (
            "general", "tone", "genre", "realism", "ai", "visibility", "export",
            "project_metadata", "advanced_config", "novela_config", "import_taxonomy",
        ):
            assert dead not in d, f"clave de config vieja no debería estar en to_dict: {dead}"

    def test_to_dict_serializes_empty_collections(self):
        d = Project().to_dict()
        assert d["entities"] == []
        assert d["relations"] == []
        assert d["sources"] == []
        assert d["history"] == []
        assert d["issues"] == []

    def test_to_dict_isoformat_timestamps(self):
        d = Project().to_dict()
        assert "T" in d["created_at"]
        assert "T" in d["updated_at"]


# ---------------------------------------------------------------------------
# 6. from_dict — compatibilidad hacia atrás
# ---------------------------------------------------------------------------


class TestFromDict:
    def test_from_dict_full_roundtrip(self):
        p1 = Project(name="Test", description="Desc")
        p1.creative_config.identidad.genero_principal = "terror"
        d = p1.to_dict()
        p2 = Project.from_dict(d)
        assert p2.id == p1.id
        assert p2.name == p1.name
        assert p2.creative_config.identidad.genero_principal == "terror"

    def test_from_dict_v1_compatibility(self):
        """Datos v1 mínimos cargan con defaults; sin claves de config viejas."""
        v1_data = {
            "id": "aaa111bbb222",
            "name": "old_project",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
            "metadata": {"legacy_key": "legacy_val"},
        }
        p = Project.from_dict(v1_data)

        assert p.id == "aaa111bbb222"
        assert p.name == "old_project"
        assert p.description == ""
        assert p.primary_language == "es"
        assert p.secondary_languages == []
        # creative_config vacío por defecto
        assert isinstance(p.creative_config, CreativeProjectConfig)
        assert p.creative_config.identidad.premisa == ""
        # colecciones vacías
        assert p.entities == []
        assert p.relations == []
        assert p.metadata == {"legacy_key": "legacy_val"}


# ---------------------------------------------------------------------------
# 7. touch()
# ---------------------------------------------------------------------------


class TestTouch:
    def test_touch_updates_updated_at(self):
        import time
        p = Project()
        before = p.updated_at
        time.sleep(0.001)
        p.touch()
        assert p.updated_at > before

    def test_touch_does_not_affect_other_fields(self):
        p = Project(name="DoNotChange", description="Original")
        p.touch()
        assert p.name == "DoNotChange"
        assert p.description == "Original"
        assert len(p.entities) == 0
