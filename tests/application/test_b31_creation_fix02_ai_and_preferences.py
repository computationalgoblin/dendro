from pathlib import Path

from hosts.DesktopHostPySide import app_context as appctx
from hosts.DesktopHostPySide.app_context import AppContext
from packages.application.ai_context_actions import AIContextActionService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.domain.result import Error


def test_node_text_suggestion_does_not_create_candidates_nodes_or_relations():
    ps = ProjectService()
    assert not isinstance(ps.create("Smoke IA"), Error)
    entity_service = EntityService(ps)
    created = entity_service.create_entity(
        {
            "name": "Fosco",
            "entity_type": "personaje",
            "brief_description": "Viajero obstinado",
            "extended_description": "",
        }
    )
    assert not isinstance(created, Error)

    project = ps.active_project
    assert project is not None
    before = (len(project.entities), len(project.relations), len(project.candidates))

    result = AIContextActionService(
        ps,
        candidate_service=None,
        provider_name="simulated",
    ).run_node_text_suggestion(
        created.value.id,
        prompt_hint="Escribe un cuerpo para Fosco contando sus aventuras",
        language="es",
    )

    assert not isinstance(result, Error)
    assert "Fosco" in result.value.raw_text
    assert "Rewritten description in a different style" not in result.value.raw_text
    assert result.value.candidates == []
    assert (len(project.entities), len(project.relations), len(project.candidates)) == before


def test_app_context_persists_ai_settings_and_last_project(tmp_path, monkeypatch):
    prefs_path = tmp_path / "settings.json"
    monkeypatch.setattr(appctx, "PREFERENCES_PATH", prefs_path)

    ctx = AppContext()
    ctx.ai_provider = "openai_compatible"
    ctx.ai_base_url = "https://example.local/v1"
    ctx.ai_model = "modelo-prueba"
    ctx.ai_api_key = "SECRET_FOR_TEST_ONLY"
    ctx.ai_timeout = "60"
    ctx.ai_temperature = 0.9
    ctx.language = "en"
    ctx.font_size = "large"
    ctx.font_family = "Courier New"
    ctx.remember_project(str(tmp_path / "proyecto.json"))
    ctx.save_preferences()

    restored = AppContext()
    assert restored.ai_provider == "openai_compatible"
    assert restored.ai_base_url == "https://example.local/v1"
    assert restored.ai_model == "modelo-prueba"
    assert restored.ai_api_key == "SECRET_FOR_TEST_ONLY"
    assert restored.ai_timeout == "60"
    assert restored.ai_temperature == 0.9
    assert restored.language == "en"
    assert restored.font_size == "large"
    assert restored.font_family == "Courier New"
    assert restored.last_project_path == str(tmp_path / "proyecto.json")
    assert restored.recent_projects[:1] == [str(tmp_path / "proyecto.json")]
