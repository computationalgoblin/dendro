"""Tests for B42-T09: AI observability mínima.

Verify that AI job metadata is recorded:
job_id, intent_type, model, temperature, max_tokens, context_depth,
input_size, output_size, duration_ms, status, error_type.
No API keys stored. Raw prompt only in debug mode.
"""
import pytest

from packages.application.ai_observability import (
    AIObservabilityLog,
    AIJobRecord,
)


class TestAIJobRecord:
    def test_record_has_all_fields(self):
        r = AIJobRecord(
            job_id="j_001",
            intent_type="generate_entities",
            model="gpt-4o-mini",
            temperature=0.8,
            max_tokens=2000,
            context_depth=5,
            input_size=500,
            output_size=300,
            duration_ms=1500.0,
            status="ok",
        )
        assert r.job_id == "j_001"
        assert r.temperature == 0.8
        assert r.status == "ok"

    def test_record_error_type(self):
        r = AIJobRecord(
            job_id="j_002",
            intent_type="coherence",
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=2000,
            context_depth=3,
            input_size=400,
            output_size=0,
            duration_ms=5000.0,
            status="error",
            error_type="TimeoutError",
        )
        assert r.error_type == "TimeoutError"

    def test_record_to_dict_no_api_keys(self):
        r = AIJobRecord(
            job_id="j_003",
            intent_type="chat",
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=2000,
            context_depth=2,
            input_size=100,
            output_size=50,
            duration_ms=800.0,
            status="ok",
        )
        d = r.to_dict()
        assert "api_key" not in str(d)
        assert "api_secret" not in str(d)
        assert d["model"] == "deepseek-chat"


class TestAIObservabilityLog:
    def test_log_stores_records(self):
        log = AIObservabilityLog()
        log.record(AIJobRecord(
            job_id="j_001", intent_type="chat", model="test",
            temperature=0.7, max_tokens=2000, context_depth=1,
            input_size=100, output_size=50, duration_ms=500.0, status="ok",
        ))
        assert len(log.records) == 1

    def test_log_latest_returns_last(self):
        log = AIObservabilityLog()
        log.record(AIJobRecord(
            job_id="j_001", intent_type="chat", model="test",
            temperature=0.7, max_tokens=2000, context_depth=1,
            input_size=100, output_size=50, duration_ms=500.0, status="ok",
        ))
        log.record(AIJobRecord(
            job_id="j_002", intent_type="coherence", model="test",
            temperature=0.2, max_tokens=2000, context_depth=3,
            input_size=200, output_size=100, duration_ms=1000.0, status="ok",
        ))
        latest = log.latest
        assert latest.job_id == "j_002"

    def test_log_summary_by_intent(self):
        log = AIObservabilityLog()
        for i in range(3):
            log.record(AIJobRecord(
                job_id=f"j_{i}", intent_type="chat", model="test",
                temperature=0.7, max_tokens=2000, context_depth=1,
                input_size=100, output_size=50, duration_ms=500.0, status="ok",
            ))
        log.record(AIJobRecord(
            job_id="j_3", intent_type="coherence", model="test",
            temperature=0.2, max_tokens=2000, context_depth=3,
            input_size=200, output_size=100, duration_ms=1000.0, status="ok",
        ))
        summary = log.summary_by_intent()
        assert summary["chat"] == 3
        assert summary["coherence"] == 1

    def test_log_max_size(self):
        log = AIObservabilityLog(max_size=5)
        for i in range(10):
            log.record(AIJobRecord(
                job_id=f"j_{i}", intent_type="chat", model="test",
                temperature=0.7, max_tokens=2000, context_depth=1,
                input_size=100, output_size=50, duration_ms=500.0, status="ok",
            ))
        assert len(log.records) == 5
        assert log.records[0].job_id == "j_5"

    def test_debug_mode_stores_raw_prompt(self):
        log = AIObservabilityLog(debug=True)
        log.record(AIJobRecord(
            job_id="j_dbg", intent_type="chat", model="test",
            temperature=0.7, max_tokens=2000, context_depth=1,
            input_size=100, output_size=50, duration_ms=500.0, status="ok",
            raw_prompt="Test prompt content",
        ))
        assert log.records[0].raw_prompt == "Test prompt content"

    def test_no_debug_mode_no_raw_prompt(self):
        log = AIObservabilityLog(debug=False)
        log.record(AIJobRecord(
            job_id="j_nodbg", intent_type="chat", model="test",
            temperature=0.7, max_tokens=2000, context_depth=1,
            input_size=100, output_size=50, duration_ms=500.0, status="ok",
            raw_prompt="Should not be stored",
        ))
        assert log.records[0].raw_prompt is None
