"""Tests for B41-T05: IA propose causal milestones."""

import pytest

from packages.application.ai_jobs import AIJobType, classify_intent, classify_ai_job_intent


@pytest.mark.application
def test_classify_hito_keyword():
    intent = classify_intent("Propón tres hitos que expliquen la traición de Devian")
    assert intent.intent_type == AIJobType.PROPOSE_MILESTONES


@pytest.mark.application
def test_classify_hitos_keyword():
    intent = classify_intent("Crea una cadena de hitos para el Reino de Aster")
    assert intent.intent_type == AIJobType.PROPOSE_MILESTONES


@pytest.mark.application
def test_classify_cadena_historica():
    intent = classify_intent("Crea una cadena histórica para explicar el status quo")
    assert intent.intent_type == AIJobType.PROPOSE_MILESTONES


@pytest.mark.application
def test_classify_hito_falta():
    intent = classify_intent("Qué hito falta para justificar la relación entre A y B")
    assert intent.intent_type == AIJobType.PROPOSE_MILESTONES


@pytest.mark.application
def test_classify_origen_hito():
    intent = classify_intent("Propón un origen para la gravedad inestable")
    # "origen" is also a milestone type; "propón...origen" should classify as milestones
    assert intent.intent_type == AIJobType.PROPOSE_MILESTONES


@pytest.mark.application
def test_backward_compat_wrapper():
    jt = classify_ai_job_intent("Propón hitos para explicar la guerra")
    assert jt == AIJobType.PROPOSE_MILESTONES


@pytest.mark.application
def test_creates_for_propose_milestones():
    from packages.application.ai_jobs import _creates_for_intent
    creates = _creates_for_intent(AIJobType.PROPOSE_MILESTONES)
    assert "candidatos de hito causal" in creates or "hito" in str(creates).lower()
