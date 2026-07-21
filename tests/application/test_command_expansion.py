"""@menciones puras (parse_mentions) — único superviviente de command_expansion."""
from __future__ import annotations

from packages.application.command_expansion import parse_mentions

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
