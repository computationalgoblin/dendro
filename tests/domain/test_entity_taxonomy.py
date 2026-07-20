"""BETA1-J08 — Tabla de taxonomía curada (tipos ofrecidos + naturaleza por tipo)."""

from __future__ import annotations

from packages.domain import entity_taxonomy as tax
from packages.domain.entity import EntityType
from packages.domain.relation import RelationType
from packages.domain.temporal_models import TemporalNature


def test_hidden_entity_types_not_offered():
    # Subsistemas dedicados + rol contenedor + tipos retirados por el usuario
    # (evento, conflicto, regla_del_mundo, trama, nota).
    for hidden in (
        EntityType.ESCENA,
        EntityType.SESION,
        EntityType.PISTA,
        EntityType.SECRETO,
        EntityType.CONTENEDOR,
        EntityType.EVENTO,
        EntityType.CONFLICTO,
        EntityType.REGLA_DEL_MUNDO,
        EntityType.TRAMA,
        EntityType.NOTA,
    ):
        assert hidden not in tax.OFFERED_ENTITY_TYPES
        assert hidden in tax.HIDDEN_ENTITY_TYPES


def test_leaf_and_branch_are_distinct_subsets():
    # J08-fix: hoja y rama ofrecen subconjuntos DISTINTOS.
    assert tax.LEAF_ENTITY_TYPES == (
        EntityType.PERSONAJE,
        EntityType.CRIATURA,
        EntityType.OBJETO,
        EntityType.TECNOLOGIA,
        EntityType.IDIOMA,
    )
    assert tax.BRANCH_ENTITY_TYPES == (
        EntityType.FACCION,
        EntityType.CULTURA,
        EntityType.RELIGION,
        EntityType.INSTITUCION,
        EntityType.SISTEMA_MAGICO,
        EntityType.LOCALIZACION,
    )
    # Hoy no se solapan; OFFERED es la unión.
    assert set(tax.LEAF_ENTITY_TYPES).isdisjoint(tax.BRANCH_ENTITY_TYPES)
    assert set(tax.OFFERED_ENTITY_TYPES) == set(tax.LEAF_ENTITY_TYPES) | set(
        tax.BRANCH_ENTITY_TYPES
    )


def test_is_branch_type_derives_from_type():
    # UI2-20: la ramitud se deriva del tipo. Los 6 tipos de rama SON rama.
    for branch in tax.BRANCH_ENTITY_TYPES:
        assert tax.is_branch_type(branch)
        assert tax.is_branch_type(branch.value)  # acepta también el string
    # El rol legado CONTENEDOR se sigue reconociendo (proyectos antiguos).
    assert tax.is_branch_type(EntityType.CONTENEDOR)
    assert tax.is_branch_type("contenedor")
    # Las hojas y los tipos personalizados NO son rama.
    for leaf in tax.LEAF_ENTITY_TYPES:
        assert not tax.is_branch_type(leaf)
    assert not tax.is_branch_type("personaje")
    assert not tax.is_branch_type("un_tipo_personalizado")
    assert not tax.is_branch_type(None)


def test_is_branch_reads_entity_type():
    from packages.domain.entity import NarrativeEntity

    rama = NarrativeEntity(name="Facción", entity_type=EntityType.FACCION)
    contenedor = NarrativeEntity(name="Orden", entity_type=EntityType.CONTENEDOR)
    hoja = NarrativeEntity(name="Héroe", entity_type=EntityType.PERSONAJE)
    assert tax.is_branch(rama)
    assert tax.is_branch(contenedor)
    assert not tax.is_branch(hoja)


def test_beings_are_leaf_only():
    # Los seres (con naturaleza temporal) solo son hoja, nunca rama.
    for being in tax.BEING_TYPES:
        assert being in tax.LEAF_ENTITY_TYPES
        assert being not in tax.BRANCH_ENTITY_TYPES


def test_only_beings_have_nature():
    assert tax.has_temporal_nature(EntityType.PERSONAJE)
    assert tax.has_temporal_nature(EntityType.CRIATURA)
    assert not tax.has_temporal_nature(EntityType.OBJETO)
    assert not tax.has_temporal_nature(EntityType.FACCION)


def test_allowed_natures():
    assert tax.allowed_natures(EntityType.CRIATURA) == (
        TemporalNature.MORTAL,
        TemporalNature.INMORTAL,
        TemporalNature.ETERNO,
    )
    assert tax.allowed_natures(EntityType.OBJETO) == ()


def test_clamp_nature_non_being_is_mortal():
    # Un objeto eterno propuesto por la IA → mortal (no existe objeto eterno).
    assert tax.clamp_nature(EntityType.OBJETO, TemporalNature.ETERNO) is TemporalNature.MORTAL


def test_clamp_nature_being_keeps_allowed():
    assert tax.clamp_nature(EntityType.CRIATURA, TemporalNature.ETERNO) is TemporalNature.ETERNO


def test_clamp_nature_being_disallowed_falls_to_mortal():
    # ATEMPORAL no es de seres → cae a mortal.
    assert tax.clamp_nature(EntityType.PERSONAJE, TemporalNature.ATEMPORAL) is TemporalNature.MORTAL


def test_hidden_relations_not_offered():
    # Familia conocimiento (B25) + familia del motor causal (hitos).
    for hidden in (
        RelationType.SABE,
        RelationType.CREE,
        RelationType.IGNORA,
        RelationType.CONOCE,
        RelationType.CAUSO,
        RelationType.FUE_CAUSADO_POR,
        RelationType.PRODUCE_CONSECUENCIA_EN,
        RelationType.CONDICIONA,
        RelationType.DERIVA_DE,
        RelationType.EXPLICA,
        RelationType.CONTRADICE,
        RelationType.DEPENDE_DE,
    ):
        assert hidden not in tax.OFFERED_RELATION_TYPES


def test_offered_relations_keep_core():
    for kept in (
        RelationType.PERTENECE_A,
        RelationType.CONTIENE,
        RelationType.ES_ALIADO_DE,
        RelationType.ES_ENEMIGO_DE,
        RelationType.GOBIERNA,
    ):
        assert kept in tax.OFFERED_RELATION_TYPES
