"""Pure command-bar expansion: @mentions, relation fan-out, batching."""
from __future__ import annotations

import pytest

from packages.application.ai_jobs import AIJobType, CommandAction, CommandScope
from packages.application.command_expansion import (
    MAX_RELATION_JOBS,
    consecutive_batches,
    parse_mentions,
    plan_command_jobs,
    relation_fanout_pairs,
)

A = CommandAction
S = CommandScope

# (id, name, type) — mirrors what the host derives from the active project.
KNOWN = [
    ("ent_north", "Tierras del Norte", "entity"),
    ("hito_ukto", "Invasion de los Ukto", "milestone"),
    ("hito_war", "Guerra del Trono", "milestone"),
    ("ent_mandalei", "Mandalei", "entity"),
]


# --- @mentions -------------------------------------------------------------

def test_resolves_multiword_mentions_separated_by_comma():
    # The exact example from the product spec.
    parsed = parse_mentions(
        "Explica los origenes de esta cultura @Tierras del Norte, @Invasion de los Ukto",
        KNOWN,
    )
    assert [r.ref_id for r in parsed.refs] == ["ent_north", "hito_ukto"]
    assert parsed.refs[0].ref_type == "entity"
    assert parsed.refs[1].ref_type == "milestone"
    assert parsed.unresolved == []
    assert parsed.overflow is False


def test_single_mention_is_case_insensitive():
    parsed = parse_mentions("Modifica con base en @guerra del trono", KNOWN)
    assert parsed.ref_ids == ["hito_war"]
    assert parsed.refs[0].name == "Guerra del Trono"  # canonical name, not raw casing


def test_max_two_mentions_with_overflow():
    parsed = parse_mentions(
        "@Mandalei y @Tierras del Norte y @Guerra del Trono",
        KNOWN,
        max_refs=2,
    )
    assert parsed.ref_ids == ["ent_mandalei", "ent_north"]
    assert parsed.overflow is True


def test_unresolved_mention_is_reported_not_invented():
    parsed = parse_mentions("Relaciona con @Personaje Inexistente, gracias", KNOWN)
    assert parsed.refs == []
    assert parsed.unresolved == ["Personaje Inexistente"]


def test_duplicate_mention_resolves_once():
    parsed = parse_mentions("@Mandalei y otra vez @Mandalei", KNOWN)
    assert parsed.ref_ids == ["ent_mandalei"]
    assert parsed.overflow is False


def test_longest_name_wins_over_prefix():
    known = [("a", "Tierras", "entity"), ("b", "Tierras del Norte", "entity")]
    parsed = parse_mentions("voy a @Tierras del Norte", known)
    assert parsed.ref_ids == ["b"]


# --- relation fan-out ------------------------------------------------------

@pytest.mark.parametrize(
    "n,expected_pairs",
    [(2, 1), (3, 3), (4, 6)],
)
def test_fanout_pair_counts(n, expected_pairs):
    ids = [f"e{i}" for i in range(n)]
    pairs, overflow = relation_fanout_pairs(ids)
    assert len(pairs) == expected_pairs
    assert overflow is False
    # pairs are unordered and unique
    assert len({frozenset(p) for p in pairs}) == expected_pairs


def test_fanout_four_entities_is_six_jobs_like_spec():
    pairs, overflow = relation_fanout_pairs(["a", "b", "c", "d"])
    assert len(pairs) == 6  # the spec's "4 personajes → 6 jobs"
    assert overflow is False


def test_fanout_caps_at_six_and_flags_overflow():
    pairs, overflow = relation_fanout_pairs(["a", "b", "c", "d", "e"])  # C(5,2)=10
    assert len(pairs) == MAX_RELATION_JOBS == 6
    assert overflow is True


def test_fanout_needs_two_entities():
    assert relation_fanout_pairs(["solo"]) == ([], False)
    assert relation_fanout_pairs([]) == ([], False)


def test_fanout_dedupes_and_drops_empty():
    pairs, _ = relation_fanout_pairs(["a", "a", "", "b"])
    assert pairs == [("a", "b")]


# --- consecutive batching --------------------------------------------------

def test_small_selection_is_one_batch():
    assert consecutive_batches(["a", "b", "c"]) == [["a", "b", "c"]]


def test_selection_over_six_splits_consecutively():
    ids = [f"e{i}" for i in range(7)]
    batches = consecutive_batches(ids)
    assert [len(b) for b in batches] == [6, 1]
    assert sum((b for b in batches), []) == ids


def test_empty_selection_no_batches():
    assert consecutive_batches([]) == []


# --- plan_command_jobs (orchestration) -------------------------------------

def test_plan_empty_prompt_errors():
    plan = plan_command_jobs(A.CREAR, S.HOJA, "   ")
    assert plan.error and not plan.jobs


def test_plan_crear_hoja_clamps_suggestion_count():
    plan = plan_command_jobs(A.CREAR, S.HOJA, "tres magos", suggestion_count=9)
    assert plan.error is None
    assert len(plan.jobs) == 1
    job = plan.jobs[0]
    assert job.job_type is AIJobType.GENERATE_ENTITIES
    assert job.context_overrides["suggestion_count"] == 3  # clamped to MAX


def test_plan_crear_relacion_fans_out_one_job_per_pair():
    plan = plan_command_jobs(A.CREAR, S.RELACION, "relaciona", selected_entity_ids=["a", "b", "c"])
    assert len(plan.jobs) == 3
    assert all(j.job_type is AIJobType.SUGGEST_RELATIONS for j in plan.jobs)
    pairs = {tuple(j.context_overrides["fanout_pair"]) for j in plan.jobs}
    assert pairs == {("a", "b"), ("a", "c"), ("b", "c")}


def test_plan_crear_relacion_needs_two_entities():
    plan = plan_command_jobs(A.CREAR, S.RELACION, "relaciona", selected_entity_ids=["solo"])
    assert plan.error and not plan.jobs


def test_plan_crear_relacion_overflow_warns_and_caps():
    # C(5,2) = 10 pairs, capped to 6.
    plan = plan_command_jobs(A.CREAR, S.RELACION, "rel", selected_entity_ids=list("abcde"))
    assert len(plan.jobs) == MAX_RELATION_JOBS == 6
    assert any("máx" in w for w in plan.warnings)


def test_plan_crear_anillo_rejects_selection():
    plan = plan_command_jobs(A.CREAR, S.ANILLO, "plantilla", selected_entity_ids=["x"])
    assert plan.error and not plan.jobs


def test_plan_crear_anillo_without_selection_flags_template():
    plan = plan_command_jobs(A.CREAR, S.ANILLO, "plantilla causal", active_ring_id="ring_prev")
    assert plan.error is None and len(plan.jobs) == 1
    job = plan.jobs[0]
    assert job.job_type is AIJobType.CREATE_RING_TEMPLATE
    assert job.context_overrides["ring_template"] is True
    assert job.context_overrides["previous_ring_id"] == "ring_prev"


def test_plan_analizar_small_selection_single_job():
    plan = plan_command_jobs(A.ANALIZAR, S.HOJA, "coherencia", selected_entity_ids=list("abc"))
    assert len(plan.jobs) == 1
    assert plan.jobs[0].job_type is AIJobType.ANALYZE_COHERENCE


def test_plan_analizar_large_selection_splits_consecutively():
    ids = [f"e{i}" for i in range(7)]
    plan = plan_command_jobs(A.ANALIZAR, S.HOJA, "total", selected_entity_ids=ids)
    assert len(plan.jobs) == 2  # 6 + 1
    assert any("consecutiv" in w for w in plan.warnings)


def test_plan_editar_caps_selection_at_six():
    ids = [f"e{i}" for i in range(8)]
    plan = plan_command_jobs(A.EDITAR, S.HOJA, "edit", selected_entity_ids=ids)
    assert len(plan.jobs) == 1
    assert len(plan.jobs[0].context_overrides["selected_entity_ids"]) == 6
    assert any("máx 6" in w for w in plan.warnings)


def test_plan_explicar_branches_on_mentions():
    known = [("h1", "Guerra del Trono", "milestone")]
    with_ref = plan_command_jobs(A.EXPLICAR, S.HOJA, "con @Guerra del Trono", known_mentions=known)
    assert with_ref.jobs[0].context_overrides["explain_target"] == "modify_refs"
    without = plan_command_jobs(A.EXPLICAR, S.HOJA, "explica el origen", active_ring_id="r1")
    assert without.jobs[0].context_overrides["explain_target"] == "create_in_active_ring"
    assert without.jobs[0].context_overrides["active_ring_id"] == "r1"
