"""Tests for AI domain models (B15-T01).

BETA1-AI02: AIMode / AIOperation / AIResponse were removed; only the
visibility-safe AuthorizedContext remains.
"""
from packages.domain.ai_models import AuthorizedContext


class TestAuthorizedContext:
    def test_defaults(self):
        ctx = AuthorizedContext()
        assert ctx.audience == "author"
        assert ctx.output_profile == "default"
        assert ctx.context_entities == []

    def test_roundtrip(self):
        ctx = AuthorizedContext(project_name="P", audience="player", selected_entity_ids=["e1"])
        d = ctx.to_dict()
        c2 = AuthorizedContext.from_dict(d)
        assert c2.project_name == "P"
        assert c2.audience == "player"
        assert "e1" in c2.selected_entity_ids

    def test_from_dict_partial(self):
        ctx = AuthorizedContext.from_dict({})
        assert ctx.audience == "author"
        assert ctx.allowed_canon_states == []
