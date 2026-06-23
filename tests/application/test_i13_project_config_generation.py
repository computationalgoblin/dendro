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
        "taxonomy": {"allowed_entity_types": ["personaje", "lugar"],
                     "extraction_guidance": "núcleo"},
    },
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
    # Config auxiliar.
    assert proposal["config"]["taxonomy"]["allowed_entity_types"] == ["personaje", "lugar"]
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
