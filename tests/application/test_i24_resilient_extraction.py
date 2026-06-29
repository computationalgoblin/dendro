"""I24 — Importación resiliente: un fallo de sección no mata el proceso (+ reanudable).

- Un rechazo POR CONTENIDO del proveedor (filtro de seguridad) en una ventana se omite
  como incidencia revisable; el resto del documento se extrae.
- Un error SISTÉMICO (auth, etc.) corta pero conserva y persiste el progreso parcial.
- Reanudar salta las ventanas ya completadas (no repite trabajo ni duplica candidatos).

Los casos sensibles al troceado en ventanas usan el servicio de extracción directamente
con ``window_chars=1`` (una ventana por párrafo) y ``max_workers=1`` (orden determinista).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_ai_extraction_service import ImportAIExtractionService
from packages.application.import_service import ImportService
from packages.domain.import_models import (
    DocumentSegment,
    ImportBasket,
    ImportFormat,
    ImportMode,
)
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider

_CONTENT_400 = ("HTTP 400: Bad Request — System detected potentially unsafe or sensitive "
                "content in input or generation.")


def _entities_payload(names):
    return json.dumps({
        "candidates": [
            {"kind": "entity", "name": n, "entity_type": "personaje", "body": f"{n}."}
            for n in names
        ]
    }, ensure_ascii=False)


class _FlaggingProvider(AIProvider):
    """Rechaza por CONTENIDO la ventana con 'NYARLA'; el resto devuelve una entidad."""

    provider_name = "i24_fake"

    def __init__(self):
        self.calls = 0

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls += 1
        if "NYARLA" in user_message:
            return None, _CONTENT_400
        return _entities_payload(["Jackson"]), None


class _SystemicProvider(AIProvider):
    """La ventana con 'BOOM' da un error SISTÉMICO (401) mientras ``fail_systemic``;
    las demás devuelven una entidad. Cuenta llamadas para verificar la reanudación."""

    provider_name = "i24_sys"

    def __init__(self):
        self.calls = 0
        self.fail_systemic = True

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls += 1
        if "BOOM" in user_message and self.fail_systemic:
            return None, "HTTP 401: Unauthorized — invalid api key"
        name = "Carlyle" if "BOOM" in user_message else "Jackson"
        return _entities_payload([name]), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i24.json")


def _basket(tmp_path, text):
    from packages.domain.project import Project
    proj = Project(name="I24")
    doc = tmp_path / "campaign.md"
    doc.write_text(text, encoding="utf-8")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    return svc, proj, basket


def _two_window_basket(texts):
    """Basket con un DocumentSegment por texto → con window_chars=1, una ventana por
    segmento (claves estables = id de segmento). Evita la dependencia del chunker, que
    funde párrafos cortos en un solo segmento."""
    segments = [
        DocumentSegment(id=f"w{i}", source_id="s", section=t[:12], raw_text=t,
                        start_offset=0, end_offset=len(t), metadata={"file_name": "c.md"})
        for i, t in enumerate(texts)
    ]
    return ImportBasket(id="b", source_id="s", segments=segments, import_candidates=[],
                        review_state="pendiente", import_mode="canon", metadata={})


def _per_paragraph_extractor(provider):
    # window_chars=1 → una ventana por segmento; max_workers=1 → orden determinista.
    return ImportAIExtractionService(provider=provider, window_chars=1, max_workers=1)


def _names(cands):
    return [(c.proposed_data or {}).get("name") for c in cands]


def _kinds(cands):
    return [(c.proposed_data or {}).get("kind") for c in cands]


# ── Servicio de extracción (troceado controlado) ─────────────────────────────

@pytest.mark.application
def test_content_rejection_keeps_other_sections():
    basket = _two_window_basket(["Parrafo de Jackson aqui.", "Ritual NYARLA prohibido aqui."])
    provider = _FlaggingProvider()
    result = _per_paragraph_extractor(provider).extract_for_basket(basket, project_context={})
    assert is_ok(result)  # NO aborta por la sección marcada

    # Una entidad de la sección limpia + una incidencia de la marcada.
    assert "Jackson" in _names(basket.import_candidates)
    assert "import_issue" in _kinds(basket.import_candidates)
    meta = basket.metadata["ai_extraction"]
    assert meta["aborted"] is False
    assert meta["skipped_sections"] == 1
    assert meta["pending_sections"] == 0


@pytest.mark.application
def test_systemic_error_cuts_but_saves_progress():
    basket = _two_window_basket(["Parrafo con Jackson.", "Parrafo con BOOM."])
    provider = _SystemicProvider()
    result = _per_paragraph_extractor(provider).extract_for_basket(basket, project_context={})
    assert is_ok(result)  # parcial, no Error duro

    meta = basket.metadata["ai_extraction"]
    assert meta["aborted"] is True
    assert "401" in meta["abort_reason"]
    assert len(meta["completed_window_keys"]) == 1  # solo la ventana de Jackson
    assert meta["pending_sections"] >= 1
    assert "Jackson" in _names(basket.import_candidates)


@pytest.mark.application
def test_resume_skips_completed_windows():
    basket = _two_window_basket(["Parrafo con Jackson.", "Parrafo con BOOM."])
    provider = _SystemicProvider()
    ext = _per_paragraph_extractor(provider)

    ext.extract_for_basket(basket, project_context={})  # corta en BOOM
    calls_after_first = provider.calls
    completed_after_first = list(basket.metadata["ai_extraction"]["completed_window_keys"])

    provider.fail_systemic = False  # proveedor disponible → reanudar
    unwrap(ext.extract_for_basket(basket, project_context={}))

    meta = basket.metadata["ai_extraction"]
    assert provider.calls == calls_after_first + 1  # solo la ventana pendiente
    assert meta["aborted"] is False
    assert meta["pending_sections"] == 0
    names = _names(basket.import_candidates)
    assert names.count("Jackson") == 1 and "Carlyle" in names  # sin duplicar lo hecho
    assert set(completed_after_first).issubset(set(meta["completed_window_keys"]))


# ── Camino completo (import_service) ─────────────────────────────────────────

@pytest.mark.application
def test_full_path_content_rejection_is_not_fatal(tmp_path):
    svc, _proj, basket = _basket(tmp_path, "Ritual NYARLA prohibido en este texto.\n")
    result = svc.extract_ai_candidates(basket.id, provider=_FlaggingProvider())
    assert is_ok(result)  # antes moría con HTTP 400; ahora degrada
    assert "import_issue" in _kinds(unwrap(result))
    assert basket.metadata["ai_extraction"]["aborted"] is False


@pytest.mark.application
def test_unconfigured_provider_still_fails_upfront(tmp_path):
    svc, _proj, basket = _basket(tmp_path, "Texto cualquiera.\n")

    class _Simulated(AIProvider):
        provider_name = "simulated"

        def chat(self, system_prompt, user_message, timeout=None):
            return "{}", None

    assert is_error(svc.extract_ai_candidates(basket.id, provider=_Simulated()))
