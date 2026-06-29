"""Guarda de contraste de accesibilidad WCAG (BETA1-UX20).

No necesita QApplication: opera sobre tokens y funciones puras.
"""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets import design_system as ds

_AA_NORMAL = 4.5  # WCAG AA, texto normal


def test_sanity_blanco_negro_y_simetria() -> None:
    assert round(ds.contrast_ratio("#FFFFFF", "#000000")) == 21
    assert ds.contrast_ratio("#34301E", "#F4EFE1") == ds.contrast_ratio("#F4EFE1", "#34301E")
    assert ds.contrast_ratio("#777777", "#777777") == 1.0


def test_texto_principal_cumple_AA_en_superficies() -> None:
    for surface in (ds.SURFACE, ds.SURFACE_HI, ds.PAPER):
        assert ds.contrast_ratio(ds.INK_STRONG, surface) >= _AA_NORMAL
        assert ds.contrast_ratio(ds.INK, surface) >= _AA_NORMAL


def test_texto_secundario_cumple_AA_en_surface() -> None:
    # INK_SOFT es el muted legible (subtítulos, captions): debe seguir siendo AA.
    assert ds.contrast_ratio(ds.INK_SOFT, ds.SURFACE) >= _AA_NORMAL


def test_ink_muted_es_sub_AA_solo_decorativo() -> None:
    # INK_MUTED es deliberadamente tenue (deshabilitado/decorativo): NO es texto
    # principal. Se guarda su rango para detectar si alguien lo asciende por error.
    ratio = ds.contrast_ratio(ds.INK_MUTED, ds.SURFACE)
    assert 2.5 <= ratio < _AA_NORMAL
