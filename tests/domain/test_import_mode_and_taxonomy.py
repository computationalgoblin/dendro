"""Dominio I08: ImportMode e ImportBasket.import_mode.

Verifica los modelos de modo de importación y su round-trip de serialización,
con defaults retrocompatibles (baskets viejos = modo canon).

PA04 eliminó ``ProjectTaxonomy`` (la extracción dirigida por taxonomía se
retiró); sus tests se quitaron de aquí. El modo de importación de los baskets
sigue vivo.
"""

from __future__ import annotations

import pytest

from packages.domain.candidate_issue import CandidateType
from packages.domain.import_models import ImportBasket, ImportMode


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
