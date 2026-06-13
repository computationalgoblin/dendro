"""E01: advanced narrative RAG contract."""

from __future__ import annotations

from pathlib import Path

from packages.application.narrative_rag_contract import (
    ContextItem,
    ContextPack,
    ContextPriority,
    CorpusItemKind,
    INDEXABLE_KINDS,
    RetrievalPlan,
    RetrievalStrategy,
)


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "architecture" / "E01_advanced_narrative_rag_contract.md"


def test_e01_indexable_kinds_cover_advanced_narrative_corpus():
    expected = {
        "entity",
        "branch",
        "relation",
        "world_layer",
        "milestone",
        "chronology",
        "candidate",
        "issue",
        "import_document",
        "creative_config",
    }

    assert {kind.value for kind in INDEXABLE_KINDS} == expected


def test_retrieval_plan_serializes_intent_scope_budget_and_visibility_flags():
    plan = RetrievalPlan(
        intent_type="analyze_coherence",
        query="revisa contradicciones",
        selected_entity_ids=["ent-1"],
        selected_relation_ids=["rel-1"],
        active_layer_ids=["layer-1"],
        include_kinds=[CorpusItemKind.ENTITY, CorpusItemKind.MILESTONE, CorpusItemKind.ISSUE],
        strategy=RetrievalStrategy.CAUSAL,
        token_budget=1600,
        timeout_ms=900,
        include_pending_candidates=True,
        audience="gm",
    )

    data = plan.to_dict()

    assert data["intent_type"] == "analyze_coherence"
    assert data["include_kinds"] == ["entity", "milestone", "issue"]
    assert data["strategy"] == "causal"
    assert data["token_budget"] == 1600
    assert data["include_pending_candidates"] is True
    assert data["include_rejected_candidates"] is False


def test_context_pack_is_structured_budgeted_and_traceable():
    plan = RetrievalPlan(intent_type="propose_milestones", query="sugiere hito")
    item = ContextItem(
        kind=CorpusItemKind.MILESTONE,
        ref_id="hito-1",
        source="project.causal_milestones",
        score=0.91,
        reason="hito vecino de la seleccion",
        priority=ContextPriority.HIGH,
        tokens_estimated=80,
        rendered_text="Hito: Fundacion de la ciudad",
        references=["entity:ent-1"],
        warnings=["fecha imprecisa"],
    )
    pack = ContextPack(plan=plan, items=[item], tokens_budget=400)

    data = pack.to_dict()

    assert data["schema"] == "context_pack/v1"
    assert data["tokens_estimated"] == 80
    assert data["items"][0]["source"] == "project.causal_milestones"
    assert data["items"][0]["reason"] == "hito vecino de la seleccion"
    assert data["items"][0]["references"] == ["entity:ent-1"]
    assert data["items"][0]["warnings"] == ["fecha imprecisa"]


def test_e01_architecture_doc_pins_pipeline_and_privacy_contract():
    text = DOC.read_text(encoding="utf-8")

    assert "AIJobService sigue siendo el runner principal" in text
    assert "No se permite crear otro runner de IA paralelo" in text
    assert "ContextPack" in text
    assert "RetrievalPlan" in text
    assert "Candidates pendientes solo se recuperan" in text
    assert "Importaciones no aceptadas no se recuperan" in text
    assert "La IA no debe recibir un fallback simulado" in text
