"""WateringDiagnostic y enums del sistema de riego (BETA2-FOCO-01)."""

from __future__ import annotations

from datetime import datetime

import pytest

from packages.domain.watering import (
    WateringCostClass,
    WateringDiagnostic,
    WateringMetric,
    WateringStatus,
)


@pytest.mark.domain
class TestWateringEnums:
    def test_metric_values(self):
        assert {m.value for m in WateringMetric} == {
            "arraigo",
            "nutrida",
            "iluminada",
            "relevancia",
        }

    def test_status_values(self):
        assert {s.value for s in WateringStatus} == {"falta_regar", "regada", "secada"}

    def test_cost_values(self):
        assert {c.value for c in WateringCostClass} == {"bajo", "medio", "alto"}


@pytest.mark.domain
class TestWateringDiagnostic:
    def test_defaults(self):
        d = WateringDiagnostic(entity_id="e1")
        assert d.id
        assert d.entity_id == "e1"
        assert d.scores == {}
        assert d.resulting_status == WateringStatus.REGADA.value
        assert d.cost_class == WateringCostClass.BAJO.value
        assert d.origin == "single"
        assert d.error == ""
        assert d.created_at.tzinfo is not None

    def test_roundtrip(self):
        d = WateringDiagnostic(
            entity_id="e1",
            scores={"arraigo": 40, "nutrida": 80, "iluminada": 10, "relevancia": 60},
            summary="Le falta sostén causal.",
            metric_explanations={"arraigo": "Sin raíces en anillos previos."},
            risks=["Entidad flotante sin causa verosímil"],
            context_manifest={"entity_ids": ["e1", "e2"], "estimated_tokens": 1200},
            provider="openai_compatible",
            model="gpt-x",
            cost_class="medio",
            origin="single",
            resulting_status="regada",
        )
        restored = WateringDiagnostic.from_dict(d.to_dict())
        assert restored.to_dict() == d.to_dict()

    def test_from_dict_tolerant(self):
        restored = WateringDiagnostic.from_dict({})
        assert restored.entity_id == ""
        assert restored.scores == {}
        d2 = WateringDiagnostic.from_dict({"created_at": "no-es-fecha", "scores": "basura"})
        assert isinstance(d2.created_at, datetime)
        assert d2.scores == {}

    def test_scores_clamped(self):
        d = WateringDiagnostic.from_dict(
            {"scores": {"arraigo": 250, "nutrida": -5, "iluminada": "60", "x": "no"}}
        )
        assert d.scores == {"arraigo": 100, "nutrida": 0, "iluminada": 60}

    def test_batch_failure_record(self):
        d = WateringDiagnostic(
            entity_id="e9",
            origin="batch",
            error="timeout del proveedor",
            resulting_status=WateringStatus.FALTA_REGAR.value,
        )
        restored = WateringDiagnostic.from_dict(d.to_dict())
        assert restored.error == "timeout del proveedor"
        assert restored.resulting_status == "falta_regar"
        assert restored.origin == "batch"
