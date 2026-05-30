"""Tests for ImportService (B17-T03)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.candidate_issue import Candidate, CandidateState
from packages.domain.import_models import ImportFormat
from packages.domain.project import Project
from packages.domain.result import is_ok, is_error, unwrap


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


class FakeProjectService:
    def __init__(self, project=None, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/test.json")


def make_service(project=None) -> ImportService:
    ps = FakeProjectService(project)
    return ImportService(project_service=ps)


# ═══════════════════════════════════════════════════════════════════════
# import_document
# ═══════════════════════════════════════════════════════════════════════


class TestImportDocument:
    def test_no_active_project_returns_error(self):
        svc = ImportService(project_service=FakeProjectService(project=None))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello world")
            path = Path(f.name)
        try:
            result = svc.import_document(path, ImportFormat.TEXT_PLAIN)
            assert is_error(result)
        finally:
            path.unlink(missing_ok=True)

    def test_import_simple_txt(self, tmp_path):
        doc_path = tmp_path / "test.txt"
        doc_path.write_text("Eldrin es un mago anciano.\n\nLa Torre de Marfil brilla en la noche.")

        proj_path = tmp_path / "proj.json"
        proj = Project(name="Test")
        ps = FakeProjectService(proj, proj_path)
        svc = ImportService(project_service=ps)

        result = svc.import_document(doc_path, ImportFormat.TEXT_PLAIN)
        assert is_ok(result)
        basket = unwrap(result)
        assert basket.source_id
        assert len(basket.segments) >= 1
        assert len(proj.sources) == 1
        assert proj.sources[0].source_type.value == "documento_importado"
        assert len(proj.import_baskets) == 1

    def test_import_empty_document(self, tmp_path):
        doc_path = tmp_path / "empty.txt"
        doc_path.write_text("")

        proj_path = tmp_path / "proj.json"
        proj = Project(name="Test")
        ps = FakeProjectService(proj, proj_path)
        svc = ImportService(project_service=ps)

        result = svc.import_document(doc_path, ImportFormat.TEXT_PLAIN)
        assert is_ok(result)
        basket = unwrap(result)
        assert len(basket.segments) == 0


# ═══════════════════════════════════════════════════════════════════════
# generate_import_candidates
# ═══════════════════════════════════════════════════════════════════════


class TestGenerateImportCandidates:
    def test_detects_entities_from_capitalized_names(self):
        from packages.domain.import_models import DocumentSegment

        svc = make_service()
        seg = DocumentSegment(id="seg1", raw_text="Eldrin y Gandalf caminaban por Minas Tirith.", source_id="s1")
        candidates = svc.generate_import_candidates([seg])

        names = {c.proposed_data.get("name", "") for c in candidates}
        assert "Eldrin" in names
        assert "Gandalf" in names
        assert "Minas Tirith" in names

    def test_detects_relations(self):
        from packages.domain.import_models import DocumentSegment

        svc = make_service()
        seg = DocumentSegment(id="seg1", raw_text="Eldrin protege la Torre de Marfil.", source_id="s1")
        candidates = svc.generate_import_candidates([seg])

        relation_cands = [c for c in candidates if c.candidate_type == "relacion"]
        assert len(relation_cands) >= 1


# ═══════════════════════════════════════════════════════════════════════
# accept_import_candidate
# ═══════════════════════════════════════════════════════════════════════


class TestAcceptImportCandidate:
    def test_accept_creates_candidate_pending(self, tmp_path):
        from packages.domain.import_models import DocumentSegment, ImportCandidate, ImportBasket, ImportReviewState

        proj_path = tmp_path / "proj.json"
        proj = Project(name="Test")
        ps = FakeProjectService(proj, proj_path)

        basket = ImportBasket(
            id="bsk1", source_id="src1",
            segments=[],
            import_candidates=[
                ImportCandidate(
                    id="ic1", segment_id="seg1",
                    candidate_type="entidad",
                    proposed_data={"name": "Eldrin"},
                    confidence=0.8,
                    review_state=ImportReviewState.PENDIENTE,
                )
            ],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        proj.import_baskets.append(basket)

        svc = ImportService(project_service=ps)
        result = svc.accept_import_candidate("bsk1", "ic1")
        assert is_ok(result)
        candidate = unwrap(result)
        assert isinstance(candidate, Candidate)
        assert candidate.state == CandidateState.PENDIENTE
        assert candidate.source_id == "src1"
        assert candidate.metadata.get("import_basket_id") == "bsk1"
        assert candidate.metadata.get("import_candidate_id") == "ic1"

        # Verify import candidate state changed
        assert basket.import_candidates[0].review_state == ImportReviewState.ACEPTADO

    def test_accept_twice_returns_error(self, tmp_path):
        from packages.domain.import_models import ImportCandidate, ImportBasket, ImportReviewState

        proj_path = tmp_path / "proj.json"
        proj = Project(name="Test")
        ps = FakeProjectService(proj, proj_path)

        basket = ImportBasket(
            id="bsk1", source_id="src1",
            segments=[],
            import_candidates=[
                ImportCandidate(
                    id="ic1", segment_id="seg1",
                    candidate_type="entidad",
                    proposed_data={"name": "Eldrin"},
                    confidence=0.8,
                    review_state=ImportReviewState.PENDIENTE,
                )
            ],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        proj.import_baskets.append(basket)

        svc = ImportService(project_service=ps)
        r1 = svc.accept_import_candidate("bsk1", "ic1")
        assert is_ok(r1)

        r2 = svc.accept_import_candidate("bsk1", "ic1")
        assert is_error(r2)

    def test_basket_not_found(self):
        proj = Project(name="Test")
        ps = FakeProjectService(proj, Path("/tmp/test.json"))
        svc = ImportService(project_service=ps)

        result = svc.accept_import_candidate("nonexistent", "ic1")
        assert is_error(result)


# ═══════════════════════════════════════════════════════════════════════
# reject_import_candidate
# ═══════════════════════════════════════════════════════════════════════


class TestRejectImportCandidate:
    def test_reject_changes_state_no_candidate(self, tmp_path):
        from packages.domain.import_models import ImportCandidate, ImportBasket, ImportReviewState

        proj_path = tmp_path / "proj.json"
        proj = Project(name="Test")
        ps = FakeProjectService(proj, proj_path)

        basket = ImportBasket(
            id="bsk1", source_id="src1",
            segments=[],
            import_candidates=[
                ImportCandidate(
                    id="ic1", segment_id="seg1",
                    candidate_type="entidad",
                    proposed_data={"name": "RejectMe"},
                    confidence=0.5,
                    review_state=ImportReviewState.PENDIENTE,
                )
            ],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        proj.import_baskets.append(basket)

        svc = ImportService(project_service=ps)
        result = svc.reject_import_candidate("bsk1", "ic1")
        assert is_ok(result)
        assert basket.import_candidates[0].review_state == ImportReviewState.RECHAZADO
        assert len(proj.candidates) == 0


# ═══════════════════════════════════════════════════════════════════════
# list_baskets / get_basket
# ═══════════════════════════════════════════════════════════════════════


class TestBasketQueries:
    def test_list_baskets(self, tmp_path):
        from packages.domain.import_models import ImportBasket

        proj = Project(name="Test")
        ps = FakeProjectService(proj, Path("/tmp/test.json"))
        basket = ImportBasket(id="bsk1", source_id="src1", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        proj.import_baskets.append(basket)

        svc = ImportService(project_service=ps)
        result = svc.list_baskets()
        assert is_ok(result)
        assert len(unwrap(result)) == 1

    def test_get_basket(self, tmp_path):
        from packages.domain.import_models import ImportBasket

        proj = Project(name="Test")
        ps = FakeProjectService(proj, Path("/tmp/test.json"))
        basket = ImportBasket(id="bsk1", source_id="src1", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        proj.import_baskets.append(basket)

        svc = ImportService(project_service=ps)
        result = svc.get_basket("bsk1")
        assert is_ok(result)
        assert unwrap(result).id == "bsk1"


# ═══════════════════════════════════════════════════════════════════════
# partial_import
# ═══════════════════════════════════════════════════════════════════════


class TestPartialImport:
    def test_partial_filters_characters(self, tmp_path):
        from packages.domain.import_models import ImportCandidate, ImportBasket, ImportReviewState

        proj = Project(name="Test")
        ps = FakeProjectService(proj, Path("/tmp/test.json"))
        basket = ImportBasket(
            id="bsk1", source_id="src1",
            segments=[],
            import_candidates=[
                ImportCandidate(id="ic1", segment_id="s1", candidate_type="entidad", proposed_data={},
                                confidence=0.5, review_state=ImportReviewState.PENDIENTE),
                ImportCandidate(id="ic2", segment_id="s1", candidate_type="relacion", proposed_data={},
                                confidence=0.5, review_state=ImportReviewState.PENDIENTE),
            ],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        proj.import_baskets.append(basket)

        svc = ImportService(project_service=ps)
        result = svc.partial_import("bsk1", {"characters_only": True})
        assert is_ok(result)
        filtered = unwrap(result)
        assert len(filtered.import_candidates) >= 1
