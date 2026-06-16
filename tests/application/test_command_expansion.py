"""Pure command-bar expansion: @mentions, relation fan-out, batching."""
from __future__ import annotations

import pytest

from packages.application.command_expansion import (
    MAX_RELATION_JOBS,
    consecutive_batches,
    parse_mentions,
    relation_fanout_pairs,
)

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
