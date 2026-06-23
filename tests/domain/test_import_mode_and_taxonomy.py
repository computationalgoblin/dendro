"""Dominio I08: ImportMode, ImportBasket.import_mode y ProjectTaxonomy.

Verifica los modelos nuevos y su round-trip de serialización, con defaults
retrocompatibles (baskets/proyectos viejos = modo canon, taxonomía vacía).
"""

from __future__ import annotations

import pytest

from packages.domain.candidate_issue import CandidateType
from packages.domain.import_models import ImportBasket, ImportMode
from packages.domain.project import Project, ProjectTaxonomy


@pytest.mark.domain
def test_import_mode_values():
    assert ImportMode.CANON.value == "canon"
    assert ImportMode.CONTEXTO.value == "contexto"


@pytest.mark.domain
def test_candidate_type_has_anillo():
    assert CandidateType.ANILLO.value == "anillo"


@pytest.mark.domain
def test_basket_defaults_to_canon_mode():
    basket = ImportBasket(id="b1", source_id="s1")
    assert basket.import_mode == "canon"


@pytest.mark.domain
def test_basket_mode_round_trip():
    basket = ImportBasket(id="b1", source_id="s1", import_mode="contexto")
    restored = ImportBasket.from_dict(basket.to_dict())
    assert restored.import_mode == "contexto"


@pytest.mark.domain
def test_basket_from_legacy_dict_without_mode_is_canon():
    # Basket serializado antes de I08 (sin import_mode).
    legacy = {"id": "b1", "source_id": "s1", "segments": [], "import_candidates": []}
    restored = ImportBasket.from_dict(legacy)
    assert restored.import_mode == "canon"


@pytest.mark.domain
def test_taxonomy_defaults_are_unrestricted():
    tax = ProjectTaxonomy()
    assert tax.allowed_entity_types == []
    assert tax.allowed_branch_types == []
    assert tax.allowed_ring_ids == []
    assert tax.extraction_guidance == ""
    assert tax.strict is False


@pytest.mark.domain
def test_taxonomy_round_trip():
    tax = ProjectTaxonomy(
        allowed_entity_types=["personaje", "localizacion"],
        allowed_branch_types=["faccion"],
        allowed_ring_ids=["layer_narrativa"],
        extraction_guidance="solo el núcleo",
        strict=True,
    )
    restored = ProjectTaxonomy.from_dict(tax.to_dict())
    assert restored == tax


@pytest.mark.domain
def test_taxonomy_from_dict_tolerates_garbage():
    restored = ProjectTaxonomy.from_dict({"allowed_entity_types": None, "strict": 1})
    assert restored.allowed_entity_types == []
    assert restored.strict is True


@pytest.mark.domain
def test_project_has_default_taxonomy():
    proj = Project(name="P")
    assert isinstance(proj.import_taxonomy, ProjectTaxonomy)
    assert proj.import_taxonomy.allowed_entity_types == []


@pytest.mark.domain
def test_project_taxonomy_round_trip():
    proj = Project(name="P")
    proj.import_taxonomy = ProjectTaxonomy(allowed_entity_types=["personaje"], strict=True)
    restored = Project.from_dict(proj.to_dict())
    assert restored.import_taxonomy.allowed_entity_types == ["personaje"]
    assert restored.import_taxonomy.strict is True


@pytest.mark.domain
def test_project_from_legacy_dict_without_taxonomy():
    proj = Project(name="P")
    data = proj.to_dict()
    del data["import_taxonomy"]
    restored = Project.from_dict(data)
    assert restored.import_taxonomy == ProjectTaxonomy()
