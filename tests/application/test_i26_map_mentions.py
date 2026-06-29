"""I26 — Fase MAP: extracción de menciones por ventana.

Contrato nuevo del rediseño map→reduce: la IA devuelve MENCIONES (no candidatos
finales), validadas por esquema con 1 reintento; ``relation_type`` se acota al
vocabulario curado (o ``otro``); entity/branch sin body o relación sin extremos
degradan a incidencia revisable (nunca se pierden). Error sistémico corta.
"""

from __future__ import annotations

import json

from packages.application.import_ai_extraction_service import (
    _coerce_relation_type,
    _normalize_mention,
    extract_mentions_from_segments,
)
from packages.domain.import_models import DocumentSegment
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider

_CONTENT_400 = "HTTP 400: System detected potentially unsafe or sensitive content."


def _seg(seg_id: str, text: str) -> DocumentSegment:
    return DocumentSegment(id=seg_id, source_id="s1", raw_text=text)


def _mentions_json(mentions):
    return json.dumps({"mentions": mentions}, ensure_ascii=False)


class _StaticProvider(AIProvider):
    """Devuelve siempre el mismo JSON de menciones (texto fijo)."""

    provider_name = "i26_static"

    def __init__(self, payload_text):
        self._payload = payload_text
        self.calls = 0

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls += 1
        return self._payload, None


class _RetryProvider(AIProvider):
    """Primera llamada JSON inválido; segunda (reintento) válido."""

    provider_name = "i26_retry"

    def __init__(self, good_text):
        self._good = good_text
        self.calls = 0

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls += 1
        if self.calls == 1:
            return "esto no es JSON", None
        return self._good, None


class _PerWindowProvider(AIProvider):
    """Responde según el contenido de la ventana (para windowing/errores)."""

    provider_name = "i26_perwindow"

    def __init__(self):
        self.calls = 0

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls += 1
        if "BOOM" in user_message:
            return None, "HTTP 401: Unauthorized"  # sistémico
        if "NYARLA" in user_message:
            return None, _CONTENT_400  # rechazo de contenido
        name = "Uno" if "ALFA" in user_message else "Dos"
        return _mentions_json([
            {"kind": "entity", "name": name, "entity_type": "personaje",
             "body": f"{name} aparece.", "relevance": 0.8, "confidence": 0.9}
        ]), None


_CTX = {"project_name": "P", "language": "es"}


def test_coerce_relation_type_vocabulary_or_otro():
    assert _coerce_relation_type("contiene") == "contiene"
    assert _coerce_relation_type("PROTEGE") == "protege"
    assert _coerce_relation_type("ama_secretamente_a") == "otro"
    assert _coerce_relation_type("") == "otro"
    assert _coerce_relation_type(None) == "otro"


def test_valid_mentions_are_normalized_with_local_id_and_relevance():
    payload = _mentions_json([
        {"kind": "entity", "name": "Aelar", "entity_type": "personaje",
         "body": "Capitán de la guardia.", "relevance": 0.9, "confidence": 0.85},
        {"kind": "branch", "name": "Guardia", "branch_type": "institucion",
         "body": "Cuerpo de guardia.", "relevance": 0.6},
        {"kind": "relation", "source_name": "Aelar", "target_name": "Lyra",
         "relation_type": "protege", "evidence": "jura protegerla", "relevance": 0.7},
    ])
    res = extract_mentions_from_segments(_StaticProvider(payload), [_seg("s", "txt")],
                                         project_context=_CTX, window_chars=1)
    assert is_ok(res)
    mentions = unwrap(res)
    assert [m["local_id"] for m in mentions] == ["w0_m0", "w0_m1", "w0_m2"]
    assert mentions[0]["kind"] == "entity" and mentions[0]["relevance"] == 0.9
    assert mentions[1]["kind"] == "branch" and mentions[1]["branch_type"] == "institucion"
    assert mentions[2]["kind"] == "relation" and mentions[2]["relation_type"] == "protege"
    # Procedencia presente en todas.
    assert all(m["source_references"] for m in mentions)


def test_relation_type_outside_enum_becomes_otro():
    payload = _mentions_json([
        {"kind": "relation", "source_name": "A", "target_name": "B",
         "relation_type": "ama_en_secreto", "evidence": "x"},
    ])
    res = extract_mentions_from_segments(_StaticProvider(payload), [_seg("s", "t")],
                                         project_context=_CTX, window_chars=1)
    assert unwrap(res)[0]["relation_type"] == "otro"


def test_entity_without_body_degrades_to_issue():
    payload = _mentions_json([
        {"kind": "entity", "name": "X", "entity_type": "personaje", "body": "  "},
    ])
    res = extract_mentions_from_segments(_StaticProvider(payload), [_seg("s", "t")],
                                         project_context=_CTX, window_chars=1)
    m = unwrap(res)[0]
    assert m["kind"] == "issue"
    assert "body" in m["message"]


def test_relation_without_endpoints_degrades_to_issue():
    payload = _mentions_json([
        {"kind": "relation", "source_name": "A", "target_name": "", "relation_type": "contiene"},
    ])
    res = extract_mentions_from_segments(_StaticProvider(payload), [_seg("s", "t")],
                                         project_context=_CTX, window_chars=1)
    assert unwrap(res)[0]["kind"] == "issue"


def test_unknown_kind_becomes_issue():
    m = _normalize_mention({"kind": "wormhole", "name": "X"}, _seg("s", "t"), "w0_m0")
    assert m["kind"] == "issue"


def test_invalid_json_retries_then_succeeds():
    good = _mentions_json([
        {"kind": "entity", "name": "Z", "entity_type": "concepto", "body": "Algo."},
    ])
    provider = _RetryProvider(good)
    res = extract_mentions_from_segments(provider, [_seg("s", "t")],
                                         project_context=_CTX, window_chars=1)
    assert provider.calls == 2  # hubo reintento
    assert is_ok(res)
    assert unwrap(res)[0]["name"] == "Z"


def test_persistent_invalid_json_becomes_issue_not_lost():
    provider = _StaticProvider("nunca es json")
    res = extract_mentions_from_segments(provider, [_seg("s", "t")],
                                         project_context=_CTX, window_chars=1)
    assert provider.calls == 2  # original + 1 reintento
    m = unwrap(res)[0]
    assert m["kind"] == "issue"
    assert "malformado" in m["message"].lower()


def test_content_rejection_is_issue_and_continues():
    # Dos ventanas (window_chars=1): la primera NYARLA → incidencia; la segunda OK.
    provider = _PerWindowProvider()
    segs = [_seg("s0", "NYARLA habla"), _seg("s1", "ALFA aparece")]
    res = extract_mentions_from_segments(provider, segs, project_context=_CTX, window_chars=1)
    assert is_ok(res)
    mentions = unwrap(res)
    kinds = [m["kind"] for m in mentions]
    assert "issue" in kinds and "entity" in kinds
    issue = next(m for m in mentions if m["kind"] == "issue")
    assert issue.get("issue_type") == "ai_content_rejected"


def test_systemic_error_aborts():
    provider = _PerWindowProvider()
    segs = [_seg("s0", "BOOM"), _seg("s1", "ALFA")]
    res = extract_mentions_from_segments(provider, segs, project_context=_CTX, window_chars=1)
    assert is_error(res)


def test_windowing_assigns_per_window_local_ids():
    provider = _PerWindowProvider()
    segs = [_seg("s0", "ALFA uno"), _seg("s1", "otro dos")]
    res = extract_mentions_from_segments(provider, segs, project_context=_CTX, window_chars=1)
    ids = [m["local_id"] for m in unwrap(res)]
    assert ids == ["w0_m0", "w1_m0"]
