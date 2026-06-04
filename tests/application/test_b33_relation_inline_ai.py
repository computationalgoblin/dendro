from typing import cast

from packages.application.ai_context_actions import AIContextActionService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.project import CreativeProjectConfig
from packages.domain.project_config import GenreConfig, RealismConfig, ToneConfig
from packages.domain.result import Error
from packages.infrastructure.ai_provider import AIProvider


class CapturingProvider:
    provider_name = "capturing"

    def __init__(self, text="Sugerencia basada en una deuda peligrosa.", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls.append((system_prompt, user_message, {"timeout": timeout}))
        return self.text, self.error


def _setup_project():
    ps = ProjectService()
    assert not isinstance(ps.create("Dendro B33"), Error)
    project = ps.active_project
    assert project is not None
    project.primary_language = "es"
    project.genre = GenreConfig(primary_genre="fantasía oscura")
    project.tone = ToneConfig(narrative_tone="tenso", dark_tone_level="alto")
    project.realism = RealismConfig(realism_level="medio")
    project.creative_config = CreativeProjectConfig(
        narrative_style="prosa sobria",
        creative_rules=["La servidumbre siempre implica coste."],
    )

    es = EntityService(ps)
    devian = es.create_entity({
        "name": "Devian",
        "entity_type": "personaje",
        "brief_description": "Deudor marcado por un juramento antiguo.",
        "extended_description": "Busca sobrevivir a una promesa imposible.",
    })
    akshan = es.create_entity({
        "name": "Akshan",
        "entity_type": "personaje",
        "brief_description": "Acreedor paciente y peligroso.",
        "extended_description": "Convierte favores en cadenas políticas.",
    })
    assert not isinstance(devian, Error)
    assert not isinstance(akshan, Error)

    rs = RelationService(ps)
    relation = rs.create_relation(
        devian.value.id,
        akshan.value.id,
        "sirve_a",
        {
            "description": "Devian sirve a Akshan.",
            "direction": "unidireccional",
            "custom_metadata": {"_body": "La deuda los une.", "_notes": "No es lealtad limpia."},
        },
    )
    assert not isinstance(relation, Error)
    return ps, project, relation.value


def test_relation_inline_ai_respects_user_prompt_and_relation_context():
    ps, _project, relation = _setup_project()
    provider = CapturingProvider()
    service = AIContextActionService(ps, candidate_service=None, provider=cast(AIProvider, provider))

    result = service.run_relation_text_suggestion(
        relation.id,
        prompt_hint="Haz que esta relación se base en una deuda peligrosa y no en lealtad limpia.",
        language="es",
    )

    assert not isinstance(result, Error)
    assert result.value.raw_text == "Sugerencia basada en una deuda peligrosa."
    system_prompt, user_prompt, _kwargs = provider.calls[0]
    assert "mejorar o completar el contenido textual de una relación narrativa" in system_prompt
    assert "No devuelvas JSON" in system_prompt
    assert "No crees entidades, relaciones, árboles, secretos ni canon nuevo" in system_prompt
    assert "Devian" in user_prompt
    assert "Akshan" in user_prompt
    assert "sirve_a" in user_prompt
    assert "La deuda los une" in user_prompt
    assert "No es lealtad limpia" in user_prompt
    assert "fantasía oscura" in user_prompt
    assert "tenso" in user_prompt
    assert "medio" in user_prompt
    assert "prosa sobria" in user_prompt
    assert "deuda peligrosa" in user_prompt


def test_relation_inline_ai_does_not_create_nodes_relations_or_candidates():
    ps, project, relation = _setup_project()
    before = (len(project.entities), len(project.relations), len(project.candidates))

    result = AIContextActionService(
        ps,
        candidate_service=None,
        provider=cast(AIProvider, CapturingProvider()),
    ).run_relation_text_suggestion(relation.id, prompt_hint="Desarrolla la tensión.", language="es")

    assert not isinstance(result, Error)
    assert result.value.candidates == []
    assert result.value.target_type == "relation"
    assert (len(project.entities), len(project.relations), len(project.candidates)) == before


def test_relation_inline_ai_error_is_returned_without_mutation():
    ps, project, relation = _setup_project()
    before = (len(project.entities), len(project.relations), len(project.candidates))

    result = AIContextActionService(
        ps,
        candidate_service=None,
        provider=cast(AIProvider, CapturingProvider(text="", error="read timeout")),
    ).run_relation_text_suggestion(relation.id, prompt_hint="Prueba timeout", language="es")

    assert isinstance(result, Error)
    assert "read timeout" in result.error
    assert (len(project.entities), len(project.relations), len(project.candidates)) == before
