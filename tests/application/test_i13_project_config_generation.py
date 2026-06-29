"""I13 — IA genera configuración de proyecto (calendario) al importar.

Genera una propuesta revisable en basket.metadata sin tocar canon ni config.
Sin proveedor real → bloqueo. Con proveedor → propuesta normalizada (calendario,
ubicación temporal de entidades, config auxiliar).
"""

from __future__ import annotations

import json

import pytest

from packages.application.import_project_config_service import ImportProjectConfigService
from packages.domain.import_models import DocumentSegment, ImportBasket
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider, SimulatedAIProvider

_CONFIG_PAYLOAD = {
    "chronology": {
        "mode": "vague_periods",
        "calendar_name": "Eras del Norte",
        "present_year": 1200,
        "supports_exact_dates": False,
        "eras": [
            {"name": "Antigua", "start_year": 0, "end_year": 800, "description": "Edad mítica."},
            {"name": "Reciente", "start_year": 801, "end_year": None, "description": "Hoy."},
        ],
    },
    "entity_temporal": [
        {"name": "Eldrin", "birth_year": 900, "death_year": 1180,
         "nature": "mortal", "note": "mago"},
    ],
    "config": {
        "tone": "épico",
        "genre": "fantasía",
    },
    "world_layers": {
        "activate_default_layer_ids": ["layer_historia", "layer_religion", "inventado_xyz"],
        "custom_layers": [
            {"name": "Linaje real", "description": "Dinastía",
             "causal_role": "dynasty", "causal_parent_layer_ids": ["layer_historia"]},
        ],
    },
    "milestones": [
        {"title": "Caída del reino", "description": "Fin de la dinastía.",
         "milestone_type": "caida", "year": 1180,
         "affected_layer_ids": ["layer_historia"], "tags": ["clave"]},
    ],
}


class _ConfigProvider(AIProvider):
    provider_name = "i13_fake"

    def __init__(self, payload=None):
        self._payload = payload or _CONFIG_PAYLOAD
        self.calls = 0

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls += 1
        return json.dumps(self._payload, ensure_ascii=False), None


def _basket() -> ImportBasket:
    seg = DocumentSegment(
        id="seg-1", source_id="s1", section="Historia",
        raw_text="Eldrin nació en el año 900 de la Era Antigua y murió en 1180.",
        metadata={"chunk_id": "s1-chunk-0001"},
    )
    return ImportBasket(id="b1", source_id="s1", segments=[seg], import_candidates=[],
                        review_state="pendiente", import_mode="canon", metadata={})


@pytest.mark.application
def test_blocks_without_real_provider():
    basket = _basket()
    svc = ImportProjectConfigService(provider=SimulatedAIProvider(), allow_simulated=False)
    result = svc.generate_for_basket(basket)
    assert is_error(result)
    assert "project_config_suggestion" not in basket.metadata


@pytest.mark.application
def test_generates_proposal_into_metadata():
    basket = _basket()
    provider = _ConfigProvider()
    svc = ImportProjectConfigService(provider=provider)
    result = svc.generate_for_basket(basket, entity_names=["Eldrin"])
    assert is_ok(result)
    proposal = unwrap(result)
    # Calendario.
    assert proposal["chronology"]["mode"] == "vague_periods"
    assert len(proposal["chronology"]["eras"]) == 2
    assert proposal["chronology"]["present_year"] == 1200
    # Ubicación temporal de entidades.
    assert proposal["entity_temporal"][0]["name"] == "Eldrin"
    assert proposal["entity_temporal"][0]["birth_year"] == 900
    # Config auxiliar (tono/género; la taxonomía se eliminó en PA04).
    assert proposal["config"]["tone"] == "épico"
    assert proposal["config"]["genre"] == "fantasía"
    assert "taxonomy" not in proposal["config"]
    # Andamiaje: anillos. El id inválido se filtra contra el catálogo predefinido.
    activate = proposal["world_layers"]["activate_default_layer_ids"]
    assert activate == ["layer_historia", "layer_religion"]
    assert "inventado_xyz" not in activate
    assert proposal["world_layers"]["custom_layers"][0]["name"] == "Linaje real"
    assert proposal["world_layers"]["custom_layers"][0]["causal_role"] == "dynasty"
    # Andamiaje: hitos normalizados (datados, con tipo y capas afectadas).
    assert len(proposal["milestones"]) == 1
    assert proposal["milestones"][0]["year"] == 1180
    assert proposal["milestones"][0]["milestone_type"] == "caida"
    assert proposal["milestones"][0]["affected_layer_ids"] == ["layer_historia"]
    # Persistido en la cesta, marcado sin aplicar.
    assert basket.metadata["project_config_suggestion"]["applied"] is False
    assert provider.calls == 1


@pytest.mark.application
def test_generation_does_not_touch_canon_or_config():
    basket = _basket()
    svc = ImportProjectConfigService(provider=_ConfigProvider())
    svc.generate_for_basket(basket)
    # Solo metadata de la cesta; no hay entidades ni candidatos creados.
    assert basket.import_candidates == []


@pytest.mark.application
def test_empty_document_errors():
    basket = ImportBasket(id="b2", source_id="s2", segments=[], import_candidates=[],
                          review_state="pendiente", import_mode="canon", metadata={})
    result = ImportProjectConfigService(provider=_ConfigProvider()).generate_for_basket(basket)
    assert is_error(result)


@pytest.mark.application
def test_normalizes_invalid_mode_and_nature():
    payload = {
        "chronology": {"mode": "inventado", "eras": [{"name": "X"}]},
        "entity_temporal": [{"name": "Y", "nature": "raro"}],
        "config": {},
    }
    basket = _basket()
    svc = ImportProjectConfigService(provider=_ConfigProvider(payload))
    result = svc.generate_for_basket(basket)
    proposal = unwrap(result)
    assert proposal["chronology"]["mode"] == "vague_periods"  # fallback
    assert proposal["entity_temporal"][0]["nature"] == "mortal"  # fallback
    # Andamiaje ausente → normalizado a vacío (compatible hacia atrás).
    assert proposal["world_layers"] == {"activate_default_layer_ids": [], "custom_layers": []}
    assert proposal["milestones"] == []


class _RawTextProvider(AIProvider):
    """Devuelve texto crudo (p. ej. JSON truncado) para simular un fallo del modelo."""

    provider_name = "i13_raw"

    def __init__(self, raw: str):
        self._raw = raw

    def chat(self, system_prompt, user_message, timeout=None):
        return self._raw, None


@pytest.mark.application
def test_truncated_json_surfaces_clear_error():
    # JSON incompleto (techo de tokens) → error claro, nunca crash ni None silencioso.
    basket = _basket()
    svc = ImportProjectConfigService(provider=_RawTextProvider('{"chronology": {"mode": "vag'))
    result = svc.generate_for_basket(basket)
    assert is_error(result)
    assert "JSON" in result.error
    assert "project_config_suggestion" not in basket.metadata


@pytest.mark.application
def test_fenced_proposal_is_parsed():
    # El proveedor real envuelve el JSON en ```json ... ```: debe parsearse igual.
    import json as _json

    fenced = "```json\n" + _json.dumps(_CONFIG_PAYLOAD, ensure_ascii=False) + "\n```"
    basket = _basket()
    result = ImportProjectConfigService(provider=_RawTextProvider(fenced)).generate_for_basket(basket)
    assert is_ok(result)
    proposal = unwrap(result)
    assert proposal["chronology"]["mode"] == "vague_periods"
    assert proposal["world_layers"]["custom_layers"][0]["name"] == "Linaje real"


@pytest.mark.application
def test_intent_routes_to_generous_token_budget():
    # El andamiaje devuelve un objeto grande: el intent necesita techo alto o se trunca.
    from packages.application.ai_request_gateway import ModelParams
    from packages.application.import_project_config_service import IMPORT_PROJECT_CONFIG_INTENT

    params = ModelParams.from_intent(IMPORT_PROJECT_CONFIG_INTENT)
    assert params.max_tokens >= 4000


@pytest.mark.application
def test_normalizes_invalid_milestone_type():
    payload = {
        "chronology": {"mode": "none"},
        "milestones": [{"title": "Algo", "milestone_type": "no_existe", "year": 5}],
        "config": {},
    }
    basket = _basket()
    svc = ImportProjectConfigService(provider=_ConfigProvider(payload))
    proposal = unwrap(svc.generate_for_basket(basket))
    assert proposal["milestones"][0]["milestone_type"] == "otro"  # fallback
