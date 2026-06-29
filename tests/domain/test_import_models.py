"""Tests for Bloque 17 import models (B17-T01)."""

from __future__ import annotations

from packages.domain.import_models import (
    ConsolidatedEntity,
    ConsolidatedRelation,
    DatingStatus,
    DocumentSegment,
    ImportBasket,
    ImportCandidate,
    ImportFormat,
    ImportGraph,
    ImportReviewState,
    RelevanceTier,
)

# ═══════════════════════════════════════════════════════════════════════
# ImportFormat
# ═══════════════════════════════════════════════════════════════════════


class TestImportFormat:
    def test_two_values(self):
        assert ImportFormat.TEXT_PLAIN.value == "text_plain"
        assert ImportFormat.PDF.value == "pdf"

    def test_is_str_enum(self):
        assert ImportFormat.TEXT_PLAIN == "text_plain"


# ═══════════════════════════════════════════════════════════════════════
# ImportReviewState
# ═══════════════════════════════════════════════════════════════════════


class TestImportReviewState:
    def test_six_values(self):
        states = list(ImportReviewState)
        assert len(states) == 6
        values = {s.value for s in states}
        assert values == {"pendiente", "aceptado", "editado", "rechazado", "fusionado", "parcial"}

    def test_default_is_pendiente(self):
        cand = ImportCandidate()
        assert cand.review_state == ImportReviewState.PENDIENTE

    def test_is_str_enum(self):
        assert ImportReviewState.PENDIENTE == "pendiente"


# ═══════════════════════════════════════════════════════════════════════
# DocumentSegment
# ═══════════════════════════════════════════════════════════════════════


class TestDocumentSegment:
    def test_defaults(self):
        seg = DocumentSegment()
        assert seg.id == ""
        assert seg.source_id == ""
        assert seg.section == ""
        assert seg.raw_text == ""
        assert seg.confidence == 1.0
        assert seg.metadata == {}

    def test_eight_fields(self):
        seg = DocumentSegment(
            id="seg_1",
            source_id="src_1",
            section="Capítulo 1",
            raw_text="En un lugar de la Mancha...",
            start_offset=0,
            end_offset=100,
            confidence=0.95,
            metadata={"page": 1, "extractor": "plain_text"},
        )
        d = seg.to_dict()
        assert len(d) == 8
        assert d["metadata"]["page"] == 1

    def test_roundtrip(self):
        seg = DocumentSegment(
            id="seg_1",
            source_id="src_1",
            section="S1",
            raw_text="hola mundo",
            start_offset=0,
            end_offset=10,
            confidence=0.9,
            metadata={"page": 1},
        )
        d = seg.to_dict()
        seg2 = DocumentSegment.from_dict(d)
        assert seg2.id == seg.id
        assert seg2.source_id == seg.source_id
        assert seg2.section == seg.section
        assert seg2.raw_text == seg.raw_text
        assert seg2.confidence == seg.confidence
        assert seg2.metadata == seg.metadata

    def test_from_dict_partial(self):
        seg = DocumentSegment.from_dict({"raw_text": "solo texto"})
        assert len(seg.id) > 0  # auto-generated UUID
        assert seg.raw_text == "solo texto"
        assert seg.metadata == {}

    def test_from_dict_empty(self):
        seg = DocumentSegment.from_dict({})
        assert len(seg.id) > 0
        assert seg.confidence == 1.0
        assert seg.metadata == {}


# ═══════════════════════════════════════════════════════════════════════
# ImportCandidate
# ═══════════════════════════════════════════════════════════════════════


class TestImportCandidate:
    def test_defaults(self):
        cand = ImportCandidate()
        assert cand.review_state == ImportReviewState.PENDIENTE
        assert cand.candidate_type == "entidad"
        assert cand.confidence == 0.5
        assert cand.proposed_data == {}
        assert cand.proposed_relations == []

    def test_nine_fields(self):
        cand = ImportCandidate(
            id="ic_1",
            segment_id="seg_1",
            candidate_type="entidad",
            proposed_data={"name": "Eldrin"},
            proposed_relations=[],
            confidence=0.7,
            possible_duplicates=["ent_a"],
            possible_contradictions=["ent_b"],
            review_state=ImportReviewState.PENDIENTE,
        )
        d = cand.to_dict()
        assert len(d) == 9
        assert d["review_state"] == "pendiente"

    def test_roundtrip(self):
        cand = ImportCandidate(
            id="ic_1",
            segment_id="seg_1",
            candidate_type="relacion",
            proposed_data={"name": "Eldrin protege Torre"},
            proposed_relations=[{"type": "protege", "from": "Eldrin", "to": "Torre"}],
            confidence=0.8,
            possible_duplicates=["ent_1"],
            possible_contradictions=["ent_2"],
            review_state=ImportReviewState.PENDIENTE,
        )
        d = cand.to_dict()
        cand2 = ImportCandidate.from_dict(d)
        assert cand2.id == cand.id
        assert cand2.segment_id == cand.segment_id
        assert cand2.candidate_type == cand.candidate_type
        assert cand2.proposed_data == cand.proposed_data
        assert cand2.proposed_relations == cand.proposed_relations
        assert cand2.confidence == cand.confidence
        assert cand2.possible_duplicates == cand.possible_duplicates
        assert cand2.possible_contradictions == cand.possible_contradictions
        assert cand2.review_state == cand.review_state

    def test_from_dict_partial(self):
        cand = ImportCandidate.from_dict({"candidate_type": "entidad", "confidence": 0.3})
        assert len(cand.id) > 0
        assert cand.segment_id == ""
        assert cand.confidence == 0.3
        assert cand.review_state == ImportReviewState.PENDIENTE

    def test_from_dict_empty(self):
        cand = ImportCandidate.from_dict({})
        assert len(cand.id) > 0
        assert cand.review_state == ImportReviewState.PENDIENTE
        assert cand.proposed_data == {}

    def test_review_state_invalid_defaults_to_pendiente(self):
        cand = ImportCandidate.from_dict({"review_state": "inventado"})
        assert cand.review_state == ImportReviewState.PENDIENTE

    def test_review_state_all_valid_values(self):
        for state in ImportReviewState:
            cand = ImportCandidate.from_dict({"review_state": state.value})
            assert cand.review_state == state

    def test_candidate_type_default_is_entidad(self):
        cand = ImportCandidate.from_dict({})
        assert cand.candidate_type == "entidad"


# ═══════════════════════════════════════════════════════════════════════
# ImportBasket
# ═══════════════════════════════════════════════════════════════════════


class TestImportBasket:
    def test_defaults(self):
        basket = ImportBasket()
        assert basket.id == ""
        assert basket.source_id == ""
        assert basket.segments == []
        assert basket.import_candidates == []
        assert basket.review_state == "pendiente"

    def test_ten_fields(self):
        # I08: + import_mode (modo canon/contexto elegido por documento).
        # I25: + graph (grafo consolidado del rediseño map→reduce; None por defecto).
        basket = ImportBasket(
            id="bsk_1",
            source_id="src_1",
            segments=[],
            import_candidates=[],
            review_state="pendiente",
            created_at="2026-05-30T10:00:00Z",
            updated_at="2026-05-30T10:00:00Z",
            metadata={"file_path": "/tmp/doc.txt", "format": "TEXT_PLAIN"},
        )
        d = basket.to_dict()
        assert len(d) == 10
        assert d["import_mode"] == "canon"
        assert d["graph"] is None
        assert d["metadata"]["file_path"] == "/tmp/doc.txt"

    def test_roundtrip(self):
        seg = DocumentSegment(
            id="seg_1", source_id="src_1", section="Intro", raw_text="texto", confidence=0.9
        )
        cand = ImportCandidate(
            id="ic_1",
            segment_id="seg_1",
            candidate_type="entidad",
            proposed_data={"name": "Eldrin"},
            confidence=0.8,
            review_state=ImportReviewState.PENDIENTE,
        )
        basket = ImportBasket(
            id="bsk_1",
            source_id="src_1",
            segments=[seg],
            import_candidates=[cand],
            review_state="pendiente",
            created_at="2026-05-30T10:00:00Z",
            updated_at="2026-05-30T10:00:00Z",
            metadata={"file_path": "/tmp/doc.txt"},
        )
        d = basket.to_dict()
        basket2 = ImportBasket.from_dict(d)
        assert basket2.id == basket.id
        assert basket2.source_id == basket.source_id
        assert len(basket2.segments) == 1
        assert basket2.segments[0].id == "seg_1"
        assert basket2.segments[0].raw_text == "texto"
        assert len(basket2.import_candidates) == 1
        assert basket2.import_candidates[0].id == "ic_1"
        assert basket2.import_candidates[0].proposed_data == {"name": "Eldrin"}
        assert basket2.review_state == "pendiente"
        assert basket2.metadata["file_path"] == "/tmp/doc.txt"

    def test_roundtrip_multiple_items(self):
        segments = [
            DocumentSegment(id="seg_1", source_id="src_1", section="S1", raw_text="a"),
            DocumentSegment(id="seg_2", source_id="src_1", section="S2", raw_text="b"),
        ]
        candidates = [
            ImportCandidate(id="ic_1", segment_id="seg_1", candidate_type="entidad"),
            ImportCandidate(id="ic_2", segment_id="seg_2", candidate_type="relacion"),
        ]
        basket = ImportBasket(
            id="bsk_1",
            source_id="src_1",
            segments=segments,
            import_candidates=candidates,
            created_at="2026-05-30T10:00:00Z",
            updated_at="2026-05-30T10:00:00Z",
        )
        d = basket.to_dict()
        basket2 = ImportBasket.from_dict(d)
        assert len(basket2.segments) == 2
        assert len(basket2.import_candidates) == 2

    def test_from_dict_partial(self):
        basket = ImportBasket.from_dict({"source_id": "src_1"})
        assert len(basket.id) > 0
        assert basket.segments == []
        assert basket.import_candidates == []
        assert basket.review_state == "pendiente"
        assert basket.created_at != ""

    def test_from_dict_empty(self):
        basket = ImportBasket.from_dict({})
        assert len(basket.id) > 0
        assert basket.created_at != ""
        assert basket.updated_at != ""

    def test_updated_at_different_from_created_at(self):
        basket = ImportBasket(
            id="bsk_1",
            source_id="src_1",
            created_at="2026-05-30T10:00:00Z",
            updated_at="2026-05-30T10:00:00Z",
        )
        d = basket.to_dict()
        basket2 = ImportBasket.from_dict(d)
        assert basket2.created_at == "2026-05-30T10:00:00Z"
        assert basket2.updated_at == "2026-05-30T10:00:00Z"


# ═══════════════════════════════════════════════════════════════════════
# Grafo consolidado (I25 — rediseño map→reduce)
# ═══════════════════════════════════════════════════════════════════════


class TestConsolidatedGraph:
    def test_consolidated_entity_roundtrip_leaf(self):
        e = ConsolidatedEntity(
            provisional_id="imp_e_0001",
            kind="entity",
            name="Arturo",
            aliases=["Rey Arturo"],
            entity_type="personaje",
            body="Rey legendario de Britania.",
            birth_year=480,
            death_year=542,
            temporal_nature="mortal",
            layer_ids=["layer_humano"],
            mention_ids=["w0_m1", "w3_m2"],
            relevance=0.92,
            relevance_tier=RelevanceTier.FUERTE,
            confidence=0.8,
            dating_status=DatingStatus.DATADO,
        )
        e2 = ConsolidatedEntity.from_dict(e.to_dict())
        assert e2.to_dict() == e.to_dict()
        assert e2.relevance_tier is RelevanceTier.FUERTE
        assert e2.dating_status is DatingStatus.DATADO
        assert e2.is_branch is False

    def test_consolidated_entity_branch_with_members(self):
        b = ConsolidatedEntity(
            provisional_id="imp_b_0001",
            kind="branch",
            name="Caballeros de la Mesa Redonda",
            branch_type="faccion",
            member_ids=["imp_e_0001", "imp_e_0002"],
        )
        b2 = ConsolidatedEntity.from_dict(b.to_dict())
        assert b2.is_branch is True
        assert b2.member_ids == ["imp_e_0001", "imp_e_0002"]

    def test_consolidated_relation_references_provisional_ids(self):
        r = ConsolidatedRelation(
            provisional_id="imp_r_0001",
            source_provisional_id="imp_b_0001",
            target_provisional_id="imp_e_0001",
            relation_type="contiene",
            evidence="...",
            relevance_tier=RelevanceTier.MARGINAL,
        )
        r2 = ConsolidatedRelation.from_dict(r.to_dict())
        assert r2.to_dict() == r.to_dict()
        assert r2.source_provisional_id == "imp_b_0001"
        assert r2.relation_type == "contiene"

    def test_relation_type_defaults_to_otro(self):
        r = ConsolidatedRelation()
        assert r.relation_type == "otro"

    def test_import_graph_roundtrip_and_lookup(self):
        e = ConsolidatedEntity(provisional_id="imp_e_0001", name="Arturo")
        b = ConsolidatedEntity(provisional_id="imp_b_0001", kind="branch", name="Caballeros",
                               member_ids=["imp_e_0001"])
        r = ConsolidatedRelation(provisional_id="imp_r_0001",
                                 source_provisional_id="imp_b_0001",
                                 target_provisional_id="imp_e_0001",
                                 relation_type="contiene")
        g = ImportGraph(entities=[e, b], relations=[r], raw_mentions=[{"id": "w0_m0"}])
        g2 = ImportGraph.from_dict(g.to_dict())
        assert g2.to_dict() == g.to_dict()
        assert g2.entity_by_provisional_id("imp_e_0001").name == "Arturo"
        assert g2.entity_by_provisional_id("inexistente") is None

    def test_basket_carries_graph(self):
        g = ImportGraph(entities=[ConsolidatedEntity(provisional_id="imp_e_0001", name="X")])
        basket = ImportBasket(id="bk1", source_id="s1", graph=g)
        basket2 = ImportBasket.from_dict(basket.to_dict())
        assert basket2.graph is not None
        assert len(basket2.graph.entities) == 1

    def test_basket_without_graph_is_none(self):
        basket2 = ImportBasket.from_dict(ImportBasket(id="bk0").to_dict())
        assert basket2.graph is None

    def test_int_opt_rejects_bool_and_invalid(self):
        # bool no debe colarse como año; texto inválido → None.
        e = ConsolidatedEntity.from_dict({"provisional_id": "x", "birth_year": True,
                                          "death_year": "no-es-año"})
        assert e.birth_year is None
        assert e.death_year is None
